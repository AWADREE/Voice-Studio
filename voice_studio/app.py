"""Separate experimental Qwen Base clone + instructions UI. No vendor modifications."""
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parent
# Respect the caller's Hugging Face cache configuration.
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['GRADIO_ANALYTICS_ENABLED'] = 'False'
os.environ['GRADIO_TEMP_DIR'] = str(ROOT / 'Temp')
import gc
import json
import threading
import time
import uuid
import gradio as gr
import numpy as np
import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel
from qwen_tts.inference.qwen3_tts_model import VoiceClonePromptItem

MODEL_REPO = Path(os.environ.get('VOICE_STUDIO_MODEL_CACHE', str(Path(os.environ.get('HF_HOME', str(Path.home()/'.cache'/'huggingface')))/'hub'/'models--Qwen--Qwen3-TTS-12Hz-1.7B-Base')))

def ui_asset_text(name):
    return (ROOT/name).read_text(encoding='utf-8-sig').replace('__VOICE_STUDIO_ASSETS__', '/gradio_api/file='+ (ROOT/'assets').as_posix())
from storage_locations import StorageLocations, require_local_ui, choose_folder
STORAGE = StorageLocations(ROOT)
OUTPUTS = STORAGE.values['output']
VOICES = STORAGE.values['voice']
LOCK = threading.RLock()
_model = None


def authorize_generated_file(path):
    # Only expose this exact newly-created artifact, never its whole selected directory.
    from gradio.context import LocalContext
    blocks=LocalContext.blocks.get(None)
    if blocks is not None and str(path) not in blocks.allowed_paths:
        blocks.allowed_paths.append(str(path))
    return path


def read_voice(path):
    if not path:
        raise ValueError('Upload your saved voice .pt file first.')
    path = Path(path)
    if path.suffix.lower() != '.pt' or not path.is_file():
        raise ValueError('Choose an existing Qwen voice prompt .pt file.')
    if path.stat().st_size > 100 * 1024 * 1024:
        raise ValueError('This is too large for a voice prompt (maximum 100 MB).')
    payload = torch.load(path, map_location='cpu', weights_only=True)
    if not isinstance(payload, dict) or not isinstance(payload.get('items'), list) or len(payload['items']) != 1:
        raise ValueError('Expected a Qwen saved prompt containing exactly one voice item.')
    d = payload['items'][0]
    if not isinstance(d, dict):
        raise ValueError('Saved voice item must be a dictionary.')
    emb = d.get('ref_spk_embedding')
    if isinstance(emb, (list, tuple)):
        emb = torch.tensor(emb)
    codes = d.get('ref_code')
    if isinstance(codes, (list, tuple)):
        codes = torch.tensor(codes)
    if codes is not None and (not torch.is_tensor(codes) or codes.ndim != 2 or codes.shape[1] != 16 or codes.shape[0] < 1 or codes.dtype not in (torch.int32, torch.int64) or bool((codes < 0).any())):
        raise ValueError('Reference codes must contain valid integer codec IDs, with 16 codes per frame.')
    if codes is not None:
        revision = (MODEL_REPO / 'refs' / 'main').read_text().strip()
        config = json.loads((MODEL_REPO / 'snapshots' / revision / 'config.json').read_text())['talker_config']
        tokenizer_config = json.loads((MODEL_REPO / 'snapshots' / revision / 'speech_tokenizer' / 'config.json').read_text())
        decoder_limit = int(tokenizer_config['decoder_config']['codebook_size'])
        first_limit = min(int(config['vocab_size']), decoder_limit)
        remaining_limit = min(int(config['code_predictor_config']['vocab_size']), decoder_limit)
        if bool((codes[:, 0] >= first_limit).any()) or bool((codes[:, 1:] >= remaining_limit).any()):
            raise ValueError('Reference codec IDs exceed the installed model embedding limits.')
    if not torch.is_tensor(emb) or tuple(emb.shape) != (2048,) or not torch.isfinite(emb).all():
        raise ValueError('The saved voice must have a finite 2048-value speaker embedding.')
    icl = bool(d.get('icl_mode', not d.get('x_vector_only_mode', False)))
    if icl == bool(d.get('x_vector_only_mode', False)):
        raise ValueError('Saved voice must select exactly one of reference or identity-only mode.')
    transcript = d.get('ref_text')
    if icl and (not torch.is_tensor(codes) or codes.ndim != 2 or codes.shape[1] != 16 or not isinstance(transcript, str) or not transcript.strip()):
        raise ValueError('Reference-audio mode requires audio codes and their matching transcript.')
    return VoiceClonePromptItem(ref_code=codes, ref_spk_embedding=emb,
        x_vector_only_mode=bool(d.get('x_vector_only_mode', False)), icl_mode=icl, ref_text=transcript)


def inspect_voice(path):
    if not path:
        return ''
    try:
        it = read_voice(path)
        count = int(it.ref_code.shape[0]) if it.ref_code is not None else 0
        return f'Voice loaded for use: 2048-value identity; {count} reference frames. Original .pt is never modified.'
    except Exception as exc:
        return f'Cannot use voice: {exc}'


def instruction_kwargs(model, instruction):
    # Plain `instruct=` is not consumed by the Base API. The common core accepts
    # tokenized instruct_ids, independently from the saved voice-clone prompt.
    instruction = (instruction or '').strip()
    if not instruction:
        return {}
    return {'instruct_ids': model._tokenize_texts([model._build_instruct_text(instruction)])}


def load_model():
    global _model
    if _model is not None:
        return _model
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA GPU is unavailable. This experimental launcher uses your NVIDIA GPU.')
    free, total = torch.cuda.mem_get_info()
    if free < 6 * 1024**3:
        raise RuntimeError(f'Only {free/1024**3:.1f} GB of GPU memory is free. Close the other Qwen server processes first (closing the browser tab is not enough). This app has not loaded a model or stopped anything.')
    revision = (MODEL_REPO / 'refs' / 'main').read_text().strip()
    model_path = MODEL_REPO / 'snapshots' / revision
    _model = Qwen3TTSModel.from_pretrained(str(model_path), device_map='cuda:0', dtype=torch.bfloat16, attn_implementation=None, local_files_only=True)
    return _model


def release_model():
    global _model
    _model = None
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def unload():
    with LOCK:
        release_model()
    return 'Experimental model unloaded. The original GUIs were not changed.'


def generate(voice_path, text, instruction, language, seed, release_after, identity_only, *settings):
    if not LOCK.acquire(blocking=False):
        raise gr.Error('Generation is already running. Wait for it to finish.')
    model = None
    try:
        text = (text or '').strip()
        if not text:
            raise ValueError('Enter the commentary to speak.')
        if len(text) > 2000:
            raise ValueError('Use shorter commentary chunks (maximum 2000 characters).')
        options = generation_options(settings)
        item = read_voice(voice_path)
        if identity_only:
            item = VoiceClonePromptItem(ref_code=None, ref_spk_embedding=item.ref_spk_embedding, x_vector_only_mode=True, icl_mode=False, ref_text=None)
        start = time.time()
        model = load_model()
        seed = int(seed)
        if seed >= 0:
            torch.manual_seed(seed)
            torch.cuda.manual_seed_all(seed)
        wavs, sr = model.generate_voice_clone(text=text, language=language, voice_clone_prompt=[item],
            **options, **instruction_kwargs(model, instruction))
        wav = np.asarray(wavs[0])
        if wav.size == 0 or not np.isfinite(wav).all():
            raise RuntimeError('The model returned empty or invalid audio.')
        OUTPUTS.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
        path = OUTPUTS / (stamp + '.wav')
        sf.write(path, wav, sr, subtype='PCM_24')
        authorize_generated_file(path)
        (OUTPUTS / (stamp + '.json')).write_text(json.dumps({'voice_file': Path(voice_path).name, 'text': text, 'instruction': instruction, 'language': language, 'seed': seed, 'identity_only': bool(identity_only), 'experimental': True, 'generation_settings': generation_options(settings)}, indent=2), encoding='utf-8')
        note = 'Delivery instructions were passed to the model; listen to judge adherence.' if (instruction or '').strip() else 'Generated without delivery instructions.'
        return str(path), str(path), f'Saved: {path}\nGenerated in {time.time()-start:.1f} seconds. {note}'
    except Exception as exc:
        raise gr.Error(str(exc)) from exc
    finally:
        if release_after:
            model = None
            release_model()
        LOCK.release()


def save_voice(audio, transcript, identity_only, release_after=True):
    from dataclasses import asdict
    if not audio:
        raise gr.Error('Upload or record reference audio first.')
    if not identity_only and not (transcript or '').strip():
        raise gr.Error('Enter the exact reference transcript, or enable identity-only mode.')
    if not LOCK.acquire(blocking=False):
        raise gr.Error('Another operation is running. Wait for it to finish.')
    model = None
    try:
        model = load_model()
        items = model.create_voice_clone_prompt(ref_audio=audio, ref_text=(transcript or '').strip() or None, x_vector_only_mode=bool(identity_only))
        payload = {'items': [{k: v.detach().cpu() if torch.is_tensor(v) else v for k,v in asdict(item).items()} for item in items]}
        folder = VOICES
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]+'.pt')
        torch.save(payload, path)
        read_voice(path)
        authorize_generated_file(path)
        return str(path), f'Voice saved: {path}. Download it or load it in the saved-voice section.'
    except Exception as exc:
        raise gr.Error(str(exc)) from exc
    finally:
        if release_after:
            model = None
            release_model()
        LOCK.release()


def clone_generate(audio, transcript, identity_only, text, instruction, language, seed, release_after, *settings):
    if not (text or '').strip() or len(text.strip()) > 2000:
        raise gr.Error('Enter commentary between 1 and 2000 characters.')
    generation_options(settings)
    if not LOCK.acquire(blocking=False):
        raise gr.Error('Another operation is running. Wait for it to finish.')
    try:
        path, _ = save_voice(audio, transcript, identity_only, release_after=False)
        return generate(path, text, instruction, language, seed, release_after, identity_only, *settings)
    finally:
        if release_after:
            release_model()
        LOCK.release()


SETTING_NAMES = ['max_new_tokens','temperature','top_k','top_p','repetition_penalty','do_sample','subtalker_temperature','subtalker_top_k','subtalker_top_p','subtalker_dosample']
SETTING_DEFAULTS = [8192,0.9,50,1.0,1.05,True,0.9,50,1.0,True]


def generate_preview(voice_path, text, instruction, language, seed, release_after, identity_only, *settings):
    """Keep a server-side snapshot of the exact successful audio and its script."""
    import hashlib
    audio, download, status = generate(voice_path, text, instruction, language, seed, release_after, identity_only, *settings)
    transcript = text.strip()
    state = {'audio': audio, 'sha256': hashlib.sha256(Path(audio).read_bytes()).hexdigest(), 'transcript': transcript}
    return audio, download, status, state, transcript, False


def clone_generate_preview(audio, transcript, identity_only, text, instruction, language, seed, release_after, *settings):
    import hashlib
    wav, download, status = clone_generate(audio, transcript, identity_only, text, instruction, language, seed, release_after, *settings)
    frozen_text = text.strip()
    state = {'audio': wav, 'sha256': hashlib.sha256(Path(wav).read_bytes()).hexdigest(), 'transcript': frozen_text}
    return wav, download, status, state, frozen_text, False


def clone_reference_and_save(audio, transcript, include_transcript, text, instruction, language, seed, release_after, *settings):
    """Encode reference once, save it, and synthesize using that same saved prompt."""
    import hashlib
    path = None
    if not LOCK.acquire(blocking=False):
        raise gr.Error('Another operation is running. Wait for it to finish.')
    try:
        if not (text or '').strip() or len(text.strip()) > 2000:
            raise ValueError('Enter commentary between 1 and 2000 characters.')
        generation_options(settings)
        path, _ = save_voice(audio, transcript if include_transcript else '', not include_transcript, release_after=False)
        wav, download, status = generate(path, text, instruction, language, seed, False, not include_transcript, *settings)
        frozen = text.strip()
        state = {'audio': wav, 'sha256': hashlib.sha256(Path(wav).read_bytes()).hexdigest(), 'transcript': frozen}
        return wav, download, status, state, frozen, False, gr.update(value=path,visible=True), gr.update(value='Original-reference voice saved. The sample uses this exact voice file.',visible=True)
    except Exception as exc:
        message = f'Commentary was not generated: {exc}'
        if path:
            message += '\nThe original-reference voice was saved successfully and is available below its clone button.'
        return None, None, message, None, '', False, gr.update(value=path,visible=bool(path)), gr.update(value=('Voice saved; commentary failed. Load this .pt to retry without encoding again.' if path else ''),visible=bool(path))
    finally:
        if release_after:
            release_model()
        LOCK.release()


def save_preview_voice(preview, confirmed):
    import hashlib
    if not preview or not confirmed:
        raise gr.Error('Generate a preview, listen to it, and confirm that it says the displayed preview transcript exactly.')
    audio = Path(preview['audio']).resolve()
    if audio.parent not in (STORAGE.output_history | {OUTPUTS.resolve()}) or not audio.is_file() or audio.suffix.lower() != '.wav':
        raise gr.Error('The preview audio is unavailable. Generate another preview.')
    if hashlib.sha256(audio.read_bytes()).hexdigest() != preview['sha256']:
        raise gr.Error('The preview audio changed. Generate another preview before saving a voice.')
    # Reference-audio/ICL mode deliberately retains delivery context, unlike identity-only.
    path, _ = save_voice(str(audio), preview['transcript'], False)
    return path, 'New reference voice saved. Original voice unchanged. Reuse this .pt in the saved-voice input; delivery can vary on new text.'


def generation_options(settings):
    if not settings:
        settings = SETTING_DEFAULTS
    if len(settings) != len(SETTING_NAMES):
        raise ValueError('Incomplete generation settings.')
    options = dict(zip(SETTING_NAMES,settings))
    for key in ['max_new_tokens','top_k','subtalker_top_k']:
        options[key] = int(options[key])
    for key in ['temperature','top_p','repetition_penalty','subtalker_temperature','subtalker_top_p']:
        options[key] = float(options[key])
        if not np.isfinite(options[key]) or options[key] <= 0:
            raise ValueError(f'{key} must be a positive finite number.')
    if not 128 <= options['max_new_tokens'] <= 32768 or options['top_k'] < 0 or options['subtalker_top_k'] < 0:
        raise ValueError('Token limit must be 128-32768 and top-k must be nonnegative.')
    if options['top_p'] > 1 or options['subtalker_top_p'] > 1:
        raise ValueError('Top-p must be at most 1.')
    return options


LANGUAGES = ['Auto','English','Chinese','Japanese','Korean','German','French','Russian','Portuguese','Spanish','Italian']


def compose_controls(batch=False, clone_button=None):
    text = None
    if not batch:
        text = gr.Textbox(label='Commentary text', lines=4, placeholder='Normal summon Dark Necromancer...')
    mode = entries = None
    if batch:
        mode = gr.State('single')
        with gr.Tabs(elem_id='commentary-mode-tabs'):
            with gr.Tab('Single commentary') as single_tab:
                text = gr.Textbox(label='Commentary text', lines=4, placeholder='Normal summon Dark Necromancer...')
            with gr.Tab('Timestamped clips') as batch_tab:
                gr.Markdown('Each timestamp labels a separate clip for editing. No silence is inserted. Shared settings below apply to every clip.', elem_classes=['section-note'])
                entries = gr.HTML([{'minutes':0,'seconds':0,'text':''}], html_template='<div class="clip-list"></div><button type="button" class="clip-add">Add clip</button>', js_on_load=ui_asset_text('clip-editor.js'), elem_id='clip-editor', css_template=ui_asset_text('clip-editor.css'))
        single_tab.select(lambda:('single',gr.update(visible=True),gr.update(interactive=True,value='Clone reference & generate commentary')), outputs=[mode,text,clone_button], queue=False, api_name=False)
        batch_tab.select(lambda:('batch',gr.update(visible=False),gr.update(interactive=False,value='Switch to Single commentary to clone')), outputs=[mode,text,clone_button], queue=False, api_name=False)
    instruction = gr.Textbox(label='Delivery instruction (optional)', lines=2, placeholder='Speak calmly and naturally, with quiet confidence.')
    language = gr.Dropdown(LANGUAGES, value='English', label='Language')
    with gr.Accordion('Generation settings', open=False, elem_classes=['generation-settings']):
        seed = gr.Number(value=42, precision=0, label='Seed', info='Use -1 for random. A fixed seed helps compare delivery instructions.')
        release = gr.Checkbox(value=True, label='Release GPU memory after generation')
        identity = gr.Checkbox(value=False, label='Use voice identity only', info='Ignore reference delivery. This may reduce resemblance.')
        gr.Markdown('### Speech sampling')
        max_tokens = gr.Number(value=8192, precision=0, minimum=128, maximum=32768, label='Maximum new tokens')
        temperature = gr.Slider(0.05,2.0,value=0.9,step=0.05,label='Temperature')
        top_k = gr.Number(value=50,precision=0,minimum=0,label='Top-k')
        top_p = gr.Slider(0.05,1.0,value=1.0,step=0.05,label='Top-p')
        repetition = gr.Slider(0.5,2.0,value=1.05,step=0.05,label='Repetition penalty')
        sampling = gr.Checkbox(value=True,label='Enable speech sampling')
        gr.Markdown('### Acoustic sampling')
        sub_temp = gr.Slider(0.05,2.0,value=0.9,step=0.05,label='Subtalker temperature')
        sub_k = gr.Number(value=50,precision=0,minimum=0,label='Subtalker top-k')
        sub_p = gr.Slider(0.05,1.0,value=1.0,step=0.05,label='Subtalker top-p')
        sub_sampling = gr.Checkbox(value=True,label='Enable subtalker sampling')
        settings = [max_tokens,temperature,top_k,top_p,repetition,sampling,sub_temp,sub_k,sub_p,sub_sampling]
        reset = gr.Button('Reset sampling defaults')
        reset.click(lambda: SETTING_DEFAULTS, outputs=settings, api_name=False)
    button = gr.Button('Generate commentary', variant='primary', elem_classes=['primary-action'])
    return (text, instruction, language, seed, release, identity, button, settings, mode, entries) if batch else (text, instruction, language, seed, release, identity, button, settings)


def output_controls():
    gr.Markdown('## Listen & export')
    gr.Markdown('Review your take before adding it to an episode.', elem_classes=['section-note'])
    audio = gr.Audio(label='Generated commentary', type='filepath', elem_classes=['studio-audio-output','studio-audio'], waveform_options=gr.WaveformOptions(waveform_color='#6e8b9f', waveform_progress_color='#d9b96e', trim_region_color='#d9b96e30'))
    download = gr.File(label='Download WAV', interactive=False, height=85, elem_classes=['studio-wav-output'])
    status = gr.Markdown(value='', elem_classes=['studio-output-status'], sanitize_html=True)
    unload_button = gr.Button('Unload experimental model')
    unload_button.click(unload, outputs=status, concurrency_limit=1)
    return audio, download, status


def transcript_visibility(include_transcript):
    return gr.update(visible=bool(include_transcript))


def save_voice_with_transcript(audio, transcript, include_transcript):
    return save_voice(audio, transcript if include_transcript else '', not include_transcript)


def clone_with_transcript(audio, transcript, include_transcript, *args):
    return clone_generate(audio, transcript if include_transcript else '', not include_transcript, *args)


def clone_preview_with_transcript(audio, transcript, include_transcript, *args):
    return clone_generate_preview(audio, transcript if include_transcript else '', not include_transcript, *args)


def save_voice_display(audio, transcript, include_transcript):
    path, status = save_voice_with_transcript(audio, transcript, include_transcript)
    return gr.update(value=path, visible=True), gr.update(value=status, visible=True)


def save_preview_display(preview, confirmed):
    path, status = save_preview_voice(preview, confirmed)
    return gr.update(value=path, visible=True), gr.update(value=status, visible=True)


def preview_action_visibility(preview):
    return gr.update(visible=bool(preview)), gr.update(value=(preview or {}).get('transcript',''), visible=False), False, gr.update(value=None, visible=False), gr.update(value='', visible=False), False


def _atomic_preview_controls(result):
    # Reset all preview controls in the SAME response as the new waveform.
    # A second state.change request could otherwise hide the first user toggle.
    controls = preview_action_visibility(result[3])
    return (*result, controls[0], gr.update(value=(result[3] or {}).get('transcript',''), visible=True), controls[3], controls[4], controls[5])


def generate_preview_atomic(*args):
    return _atomic_preview_controls(generate_preview(*args))


def clone_reference_atomic(*args):
    return _atomic_preview_controls(clone_reference_and_save(*args))


def correction_toggle(use_correction, preview, current=None):
    value = current if current is not None else (preview or {}).get('transcript', '')
    return gr.update(visible=bool(use_correction), value=value), False


def save_preview_corrected(preview, confirmed, correction, use_correction=False):
    if use_correction:
        if not (correction or '').strip():
            raise gr.Error('Enter the actual spoken words, or uncheck Edit transcript to use the captured commentary.')
        if preview:
            preview = dict(preview, transcript=correction.strip())
    return save_preview_display(preview, confirmed)


def reference_controls():
    audio = gr.Audio(label='Reference audio', type='filepath', sources=['upload','microphone'], elem_classes=['studio-audio','studio-reference-audio'], waveform_options=gr.WaveformOptions(waveform_color='#6e8b9f', waveform_progress_color='#d9b96e', trim_region_color='#d9b96e30'))
    include = gr.Checkbox(label='Include reference transcript', value=True)
    transcript = gr.Textbox(label='Reference transcript', lines=3, visible=True, elem_classes=['studio-presence'], placeholder='Exactly what is spoken in the reference audio.')
    include.change(transcript_visibility, [include], [transcript], api_name=False, queue=False)
    return audio, transcript, include


from voice_selection import SELECTION

def voice_session(request):
    return request.session_hash if request and request.session_hash else 'api'

def begin_clone_selection(request: gr.Request):
    return SELECTION.begin(voice_session(request))

def select_uploaded_voice(path, request: gr.Request):
    SELECTION.select(voice_session(request),path)
    if not path:return ''
    detail=inspect_voice(path)
    return 'Active voice: '+Path(path).name+'\n'+detail

def clone_reference_selected(token, audio, transcript, include, text, instruction, language, seed, release, request: gr.Request, *settings):
    result=clone_reference_atomic(audio,transcript,include,text,instruction,language,seed,release,*settings)
    saved_update=result[6]
    path=saved_update.get('value') if isinstance(saved_update,dict) else saved_update
    # Failed cloning must leave the previous selected voice untouched. A successfully
    # saved clone may still be selected when sample synthesis failed.
    if not path:return (*result,gr.update(),gr.update())
    from gradio.processing_utils import save_file_to_cache
    from gradio.utils import get_upload_folder
    selected=save_file_to_cache(path,cache_dir=get_upload_folder())
    if not SELECTION.commit(voice_session(request),token,selected):
        return (*result,gr.update(),gr.update())
    return (*result,gr.update(value=selected),'Active voice: '+Path(path).name+'\nNewly cloned reference selected for future commentary.')


def folder_listing(path):
    path=STORAGE.validate(path)
    if not path.is_dir():raise gr.Error('Choose an existing folder.')
    try:
        choices=sorted((p.name for p in path.iterdir() if p.is_dir() and not p.name.startswith('.')),key=str.casefold)
    except OSError as exc:raise gr.Error('Cannot read this folder: '+str(exc)) from exc
    return str(path),gr.update(choices=choices,value=None)

def open_storage_picker(kind,request):
    require_local_ui(request)
    path,folders=folder_listing(STORAGE.values[kind])
    drives=[f'{c}:\\' for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if Path(f'{c}:\\').is_dir()]
    return gr.update(visible=True),kind,path,folders,gr.update(choices=drives,value=Path(path).anchor),''

def open_output_picker(request: gr.Request):return open_storage_picker('output',request)
def open_voice_picker(request: gr.Request):return open_storage_picker('voice',request)
def browse_storage_path(path,request: gr.Request):
    require_local_ui(request);return folder_listing(path)
def browse_storage_child(path,child,request: gr.Request):
    require_local_ui(request)
    if not child:return gr.update(),gr.update()
    if Path(child).name!=child:raise gr.Error('Choose a listed folder.')
    return folder_listing(Path(path)/child)
def browse_storage_parent(path,request: gr.Request):
    require_local_ui(request);return folder_listing(Path(path).parent)
def commit_storage_picker(kind,path,request: gr.Request):
    global OUTPUTS,VOICES
    require_local_ui(request)
    if not LOCK.acquire(blocking=False):raise gr.Error('Wait for the current generation or save to finish.')
    try:
        chosen=STORAGE.validate(path)
        if not chosen.is_dir():raise gr.Error('Choose an existing folder.')
        STORAGE.set(kind,chosen)
        OUTPUTS=STORAGE.values['output'];VOICES=STORAGE.values['voice']
        return str(OUTPUTS),str(VOICES),'Folder saved. Future files use this location; existing files were not moved.',gr.update(visible=False)
    finally:LOCK.release()



def generate_commentary_mode(mode, rows, voice, text, instruction, language, seed, release, identity, *settings, progress=gr.Progress()):
    if mode != 'batch':
        result = generate_preview_atomic(voice,text,instruction,language,seed,release,identity,*settings)
        return (gr.update(value=result[0],visible=True),gr.update(value=result[1],visible=True),*result[2:], None, gr.update(visible=False), '', gr.update(value=None,visible=False))
    from batch_generation import run_batch
    generation_options(settings)
    read_voice(voice)
    result = run_batch(rows, generate_clip=lambda paragraph,index: generate(voice,paragraph,instruction,language,seed,False,identity,*settings)[0], output_root=OUTPUTS, lock=LOCK, release_after=release, release_model=release_model, on_progress=lambda index,total,label:progress((index,total),desc=f'Generating clip {index+1}/{total} ({label})'))
    for clip in result['clips']:
        authorize_generated_file(Path(clip['audio']))
    if result['archive']: authorize_generated_file(Path(result['archive']))
    # Existing single preview remains on disk, but cannot be mistaken for this batch.
    return (gr.update(value=None,visible=False),gr.update(value=None,visible=False),'',None,'',False,gr.update(visible=False),gr.update(value=''),gr.update(value=None,visible=False),gr.update(value='',visible=False),False,result,gr.update(visible=True),result['status'],gr.update(value=result['archive'],visible=bool(result['archive'])))

def build_ui():
    with gr.Blocks(title='Voice Studio | Night Exchange') as app:
        with gr.Row(elem_id='studio-heading-row'):
            gr.HTML('<header class="studio-head"><div><h1>Voice Studio</h1><p>Clone a voice, save it, and shape your commentary.</p></div></header>', elem_id='studio-header')
            gr.HTML('<nav class="mode-tabs" aria-label="Voice workflow"><button type="button" data-voice-mode="clone" aria-pressed="true">Clone</button><button type="button" data-voice-mode="generate" aria-pressed="false">Generate</button></nav>', elem_id='voice-mode-tabs')
        with gr.Tabs(elem_id='workflow-tabs', selected='saved-voice'):
            with gr.Tab('Clone & Generate', id='direct-clone', visible=False):
                with gr.Row(elem_classes=['workspace']):
                    with gr.Column(scale=1, min_width=340, elem_classes=['studio-panel']):
                        gr.Markdown('## 1. Reference voice')
                        gr.Markdown('Upload or record the voice you want to use.', elem_classes=['section-note'])
                        ref, transcript, xvec = reference_controls()
                    with gr.Column(scale=1, min_width=340, elem_classes=['studio-panel']):
                        gr.Markdown('## 2. Create commentary')
                        gr.Markdown('Write your script and choose its delivery.', elem_classes=['section-note'])
                        text, instruction, language, seed, release, identity, button, settings = compose_controls()
                        identity.visible = False
                with gr.Column(elem_classes=['studio-panel','result-panel']):
                    audio, download, status = output_controls()
                button.click(clone_with_transcript, [ref,transcript,xvec,text,instruction,language,seed,release,*settings], [audio,download,status], api_name='clone_generate', concurrency_limit=1)
            with gr.Tab('Save / Load Voice', id='saved-voice'):
                with gr.Row(elem_id='production-workspace'):
                    with gr.Row(elem_classes=['workspace'], elem_id='voice-mode-workspace'):
                        with gr.Column(scale=1, min_width=340, elem_classes=['studio-panel'], elem_id='reference-panel'):
                            gr.Markdown('## Clone a reference voice')
                            gr.Markdown('Turn reference audio into a reusable voice file.', elem_classes=['section-note'])
                            ref_s, transcript_s, xvec_s = reference_controls()
                            save = gr.Button('Save voice file', visible=False)
                            gr.Markdown('Save a voice and preview your commentary in one step.', elem_classes=['section-note'])
                            direct_preview = gr.Button('Clone reference & generate commentary', elem_classes=['primary-action'])
                            saved = gr.File(label='Saved voice file (.pt)', interactive=False, height=85, visible=False)
                            save_status = gr.Markdown(value='', visible=False, elem_classes=['studio-output-status'], sanitize_html=True)
                        with gr.Column(scale=1, min_width=340, elem_classes=['studio-panel']):
                            gr.Markdown('## Load voice & generate')
                            gr.Markdown('Use an existing .pt voice to create commentary.', elem_classes=['section-note'])
                            voice = gr.File(label='Voice file (.pt)', file_types=['.pt'], type='filepath', height=130, elem_classes=['studio-voice-input'])
                            info = gr.Markdown(value='', elem_classes=['studio-output-status'], sanitize_html=True)
                            text, instruction, language, seed, release, identity, button, settings, commentary_mode, clip_entries = compose_controls(batch=True, clone_button=direct_preview)
                    with gr.Column(scale=1, min_width=0, elem_classes=['studio-panel','result-panel'], elem_id='listen-panel'):
                        audio, download, status = output_controls()
                        batch_result = gr.State(None)
                        with gr.Column(visible=False, elem_id='batch-output') as batch_panel:
                            batch_status = gr.Markdown('', elem_classes=['studio-output-status'])
                            with gr.Row():
                                play_all = gr.Button('Play all', elem_id='batch-play-all')
                                stop_all = gr.Button('Stop playback', elem_id='batch-stop-all')
                                batch_zip = gr.DownloadButton('Download all (ZIP)', visible=False)
                            @gr.render(inputs=batch_result)
                            def render_clips(result):
                                for clip in (result or {}).get('clips', []):
                                    with gr.Column(elem_classes=['batch-clip'], key=clip['audio']):
                                        gr.Markdown('### '+clip['label'])
                                        import html
                                        from urllib.parse import quote
                                        src = '/gradio_api/file='+quote(Path(clip['audio']).as_posix(),safe='/:')
                                        gr.HTML('<audio controls preload="metadata" aria-label="'+html.escape(clip['label'])+'" src="'+html.escape(src)+'"></audio>',elem_classes=['batch-audio'])
                                        gr.DownloadButton('Download '+clip['label'], value=clip['audio'])
                        with gr.Column(visible=False, elem_classes=['studio-presence']) as preview_actions:
                            preview_confirm = gr.Checkbox(label='I listened and checked the spoken words', value=False)
                            use_correction = gr.Checkbox(label='Edit transcript for this voice', value=False, interactive=True, elem_id='edit-transcript')
                            correction = gr.Textbox(label='Actual spoken words', lines=3, visible=True, interactive=True, elem_id='correction-editor')
                            save_preview = gr.Button('Save as new voice .pt', elem_classes=['primary-action'])
                            preview_file = gr.File(label='New preview voice (.pt)', interactive=False, visible=False, elem_classes=['studio-presence'])
                            preview_status = gr.Markdown(value='', visible=False, elem_classes=['studio-output-status'], sanitize_html=True)
                preview_state = gr.State(None)
                preview_transcript = gr.Textbox(visible=False)
                save.click(save_voice_display, [ref_s,transcript_s,xvec_s], [saved,save_status], api_name='save_voice', concurrency_limit=1)
                voice.upload(select_uploaded_voice,[voice],[info],api_name='inspect_voice',queue=False)
                voice.clear(select_uploaded_voice,[voice],[info],api_name=False,queue=False)
                use_correction.input(lambda: False, outputs=preview_confirm, api_name=False, queue=False)
                correction.input(lambda: False, outputs=preview_confirm, api_name=False, queue=False)
                button.click(generate_commentary_mode, [commentary_mode,clip_entries,voice,text,instruction,language,seed,release,identity,*settings], [audio,download,status,preview_state,preview_transcript,preview_confirm,preview_actions,correction,preview_file,preview_status,use_correction,batch_result,batch_panel,batch_status,batch_zip], api_name='generate_commentary', concurrency_limit=1)
                # Preserve the existing single-clip API for integrations.
                legacy_generate = gr.Button(visible=False)
                legacy_generate.click(generate_preview_atomic, [voice,text,instruction,language,seed,release,identity,*settings], [audio,download,status,preview_state,preview_transcript,preview_confirm,preview_actions,correction,preview_file,preview_status,use_correction], api_name='generate', concurrency_limit=1)
                play_all.click(fn=None,js="() => window.voiceStudioBatchPlayback?.play()",api_name=False)
                stop_all.click(fn=None,js="() => window.voiceStudioBatchPlayback?.stop()",api_name=False)
                commentary_mode.change(lambda mode:gr.update(interactive=mode=='single', value=('Clone reference & generate commentary' if mode=='single' else 'Switch to Single commentary to clone')),commentary_mode,direct_preview,api_name=False,queue=False)
                clone_ticket=gr.State(0)
                direct_preview.click(begin_clone_selection,outputs=clone_ticket,api_name=False,queue=False).then(clone_reference_selected, [clone_ticket,ref_s,transcript_s,xvec_s,text,instruction,language,seed,release,*settings], [audio,download,status,preview_state,preview_transcript,preview_confirm,saved,save_status,preview_actions,correction,preview_file,preview_status,use_correction,voice,info], api_name='clone_reference_preview', concurrency_limit=1).then(lambda:(None,gr.update(visible=False),gr.update(visible=True),gr.update(visible=True)),outputs=[batch_result,batch_panel,audio,download],api_name=False)
                save_preview.click(save_preview_corrected, [preview_state,preview_confirm,correction,use_correction], [preview_file,preview_status], api_name='save_preview_voice', concurrency_limit=1)
        with gr.Accordion('General settings & model information', open=False, elem_classes=['generation-settings','studio-help','general-settings']):
            gr.Textbox(label='Model',value='Qwen3-TTS-12Hz-1.7B-Base',interactive=False)
            gr.Textbox(label='Checkpoint',value=str(MODEL_REPO/'snapshots'/(MODEL_REPO/'refs'/'main').read_text().strip()),interactive=False)
            gr.Markdown('Output directory',elem_classes=['storage-field-label'])
            output_folder=gr.Button(str(OUTPUTS),elem_classes=['storage-folder-button'])
            gr.Markdown('Saved voice directory',elem_classes=['storage-field-label'])
            voice_folder=gr.Button(str(VOICES),elem_classes=['storage-folder-button'])
            storage_status=gr.Markdown('',elem_classes=['studio-output-status'])

            gr.Markdown('Generation settings are per workflow. GPU memory release and the random seed are inside each Generation settings section. Click a storage directory to browse local folders and choose its replacement. Choices persist after restart and affect future saves only; existing files are never moved. Model/checkpoint stay read-only.')
        with gr.Accordion('Storage & GPU help', open=False, elem_classes=['generation-settings','studio-help']):
            gr.Markdown('**Compare delivery:** try an empty instruction, then the same text and seed with a direction.\n\n**Local storage:** audio and settings are in `Outputs`; saved voices are in `Voices`.\n\n**GPU memory:** stop other Qwen servers before generating. Closing their tabs does not unload models.')
        with gr.Column(visible=False,elem_id='storage-picker-dialog') as folder_dialog:
            gr.Markdown('## Choose a storage folder')
            gr.Markdown('Local folders only. Choosing a folder affects future saves; existing files stay where they are.')
            folder_kind=gr.State('output')
            folder_path=gr.Textbox(label='Current folder',interactive=True)
            with gr.Row():
                drive=gr.Dropdown(label='Drive',choices=[],interactive=True)
                child=gr.Dropdown(label='Open a subfolder',choices=[],interactive=True)
            with gr.Row():
                up=gr.Button('Parent folder')
                browse=gr.Button('Open path')
            folder_note=gr.Markdown('')
            with gr.Row():
                confirm=gr.Button('Use this folder',variant='primary')
                cancel_folder=gr.Button('Cancel',elem_id='cancel-storage-picker')
        picker_outputs=[folder_dialog,folder_kind,folder_path,child,drive,folder_note]
        output_folder.click(open_output_picker,outputs=picker_outputs,api_name=False,queue=False)
        voice_folder.click(open_voice_picker,outputs=picker_outputs,api_name=False,queue=False)
        browse.click(browse_storage_path,[folder_path],[folder_path,child],api_name=False,queue=False)
        up.click(browse_storage_parent,[folder_path],[folder_path,child],api_name=False,queue=False)
        drive.input(browse_storage_path,[drive],[folder_path,child],api_name=False,queue=False)
        child.input(browse_storage_child,[folder_path,child],[folder_path,child],api_name=False,queue=False)
        confirm.click(commit_storage_picker,[folder_kind,folder_path],[output_folder,voice_folder,storage_status,folder_dialog],api_name=False,queue=False)
        cancel_folder.click(lambda:gr.update(visible=False),outputs=folder_dialog,api_name=False,queue=False)
        app.load(fn=None, js=ui_asset_text('night-sky.js'))
        app.load(fn=None, js=ui_asset_text('batch-playback.js'))
        app.load(fn=None, js=ui_asset_text('commentary-tabs.js'))
    return app

if __name__ == '__main__':
    build_ui().queue(default_concurrency_limit=1).launch(server_name='127.0.0.1', server_port=int(os.environ.get('VOICE_STUDIO_PORT', '8003')), share=False, inbrowser=False, show_error=True, css=ui_asset_text('theme.css'), allowed_paths=[str(ROOT/'assets')], footer_links=["api", "settings"])
