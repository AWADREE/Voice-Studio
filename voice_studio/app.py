"""Voxover: local voice cloning, design and commentary with Qwen3-TTS."""
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

def app_setting(name, default):
    """Prefer Voxover configuration, retaining legacy launcher compatibility."""
    return os.environ.get('VOXOVER_' + name) or os.environ.get('CADENTVOX_' + name) or os.environ.get('VOICE_STUDIO_' + name) or default


MODEL_REPO = Path(app_setting('MODEL_CACHE', str(Path(os.environ.get('HF_HOME', str(Path.home()/'.cache'/'huggingface')))/'hub'/'models--Qwen--Qwen3-TTS-12Hz-1.7B-Base')))
DESIGN_MODEL_REPO = Path(app_setting('DESIGN_MODEL_CACHE', str(MODEL_REPO.parent/'models--Qwen--Qwen3-TTS-12Hz-1.7B-VoiceDesign')))

def ui_asset_text(name):
    return (ROOT/name).read_text(encoding='utf-8-sig').replace('__VOXOVER_ASSETS__', '/gradio_api/file='+ (ROOT/'assets').as_posix())
from storage_locations import StorageLocations, require_local_ui, choose_folder
STORAGE = StorageLocations(ROOT)
OUTPUTS = STORAGE.values['output']
VOICES = STORAGE.values['voice']
LOCK = threading.RLock()
_model = None
_model_kind = None


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


def load_model(kind='base'):
    global _model, _model_kind
    if kind not in ('base', 'voice_design'):
        raise ValueError('Unknown model type.')
    if _model is not None:
        if _model_kind == kind:
            return _model
        release_model()
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA GPU is unavailable. Voxover requires your NVIDIA GPU.')
    free, total = torch.cuda.mem_get_info()
    if free < 6 * 1024**3:
        raise RuntimeError(f'Only {free/1024**3:.1f} GB of GPU memory is free. Close the other Qwen server processes first (closing the browser tab is not enough). This app has not loaded a model or stopped anything.')
    repo = MODEL_REPO if kind == 'base' else DESIGN_MODEL_REPO
    revision_file = repo / 'refs' / 'main'
    if not revision_file.is_file():
        raise FileNotFoundError(f'Local {kind} checkpoint is missing: {repo}. Download it separately before using this mode.')
    revision = revision_file.read_text().strip()
    model_path = repo / 'snapshots' / revision
    if not (model_path / 'config.json').is_file():
        raise FileNotFoundError(f'Local {kind} checkpoint is incomplete: {model_path}.')
    loaded = Qwen3TTSModel.from_pretrained(str(model_path), device_map='cuda:0', dtype=torch.bfloat16, attn_implementation=None, local_files_only=True)
    actual_kind = loaded.model.tts_model_type
    if actual_kind != kind:
        del loaded
        gc.collect()
        torch.cuda.empty_cache()
        raise RuntimeError(f'Expected {kind} checkpoint but loaded {actual_kind}. Check the configured model cache.')
    _model = loaded
    _model_kind = kind
    return _model


def release_model():
    global _model, _model_kind
    _model = None
    _model_kind = None
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def unload():
    # Never wait behind a whole batch while the UI claims to be unloading.
    # Unloading is not cancellation: leave any in-flight model operation intact.
    if not LOCK.acquire(blocking=False):
        return 'Model is in use. Wait for generation or voice saving to finish, then unload. Nothing was interrupted.'
    try:
        if _model is None:
            return 'No model is loaded in this Voxover instance.'
        release_model()
        return 'Model unloaded. Other Voxover instances were not changed.'
    finally:
        LOCK.release()


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


def generate_design(text, description, language, seed, release_after, *settings):
    """Synthesize a new voice with the supported VoiceDesign API."""
    if not LOCK.acquire(blocking=False):
        raise gr.Error('Another operation is running. Wait for it to finish.')
    try:
        text = (text or '').strip()
        description = (description or '').strip()
        if not 1 <= len(text) <= 2000:
            raise ValueError('Enter design preview text between 1 and 2000 characters.')
        if not description:
            raise ValueError('Describe the voice you want to design.')
        if language not in LANGUAGES:
            raise ValueError('Choose a supported language.')
        options = generation_options(settings)
        seed = int(seed)
        start = time.time()
        model = load_model('voice_design')
        if seed >= 0:
            torch.manual_seed(seed)
            torch.cuda.manual_seed_all(seed)
        wavs, sr = model.generate_voice_design(text=text, language=language, instruct=description, **options)
        wav = np.asarray(wavs[0])
        if wav.size == 0 or not np.isfinite(wav).all():
            raise RuntimeError('The model returned empty or invalid audio.')
        OUTPUTS.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
        path = OUTPUTS / (stamp + '.wav')
        sf.write(path, wav, sr, subtype='PCM_24')
        authorize_generated_file(path)
        (OUTPUTS / (stamp + '.json')).write_text(json.dumps({'mode': 'voice_design', 'text': text, 'voice_description': description, 'language': language, 'seed': seed, 'generation_settings': options}, indent=2), encoding='utf-8')
        return str(path), str(path), f'Design audition saved as WAV: {path}\nGenerated in {time.time()-start:.1f} seconds. Listen to the sample, then save it as a voice if you want to reuse it. No .pt voice has been saved yet.'
    except Exception as exc:
        raise gr.Error(str(exc)) from exc
    finally:
        if release_after:
            release_model()
        LOCK.release()


def generate_design_preview(text, description, language, seed, release_after, *settings):
    import hashlib
    audio, download, status = generate_design(text, description, language, seed, release_after, *settings)
    transcript = text.strip()
    state = {'audio': audio, 'sha256': hashlib.sha256(Path(audio).read_bytes()).hexdigest(), 'transcript': transcript, 'source': 'design_sample'}
    return audio, download, status, state, transcript, False


def reference_audio_input(audio):
    if not audio:
        raise ValueError('Upload or record reference audio first.')
    try:
        waveform, sample_rate = sf.read(audio, dtype='float32', always_2d=False)
        if waveform.ndim > 1:
            waveform = waveform.mean(axis=1)
        return np.asarray(waveform, dtype=np.float32), int(sample_rate)
    except (OSError, RuntimeError, TypeError):
        return audio  # Retain upstream decoding for other supported formats.


def clone_audition(audio, transcript, include_transcript, text, instruction, language, seed, release_after, *settings):
    """Audition an in-memory reference prompt. No reusable voice file is written."""
    import hashlib
    from dataclasses import asdict
    if not LOCK.acquire(blocking=False):
        raise gr.Error('Another operation is running. Wait for it to finish.')
    try:
        text = (text or '').strip()
        transcript = (transcript or '').strip() if include_transcript else ''
        if not 1 <= len(text) <= 2000:
            raise ValueError('Enter audition text between 1 and 2000 characters.')
        if include_transcript and not transcript:
            raise ValueError('Enter the exact reference transcript, or turn off Include reference transcript.')
        if language not in LANGUAGES:
            raise ValueError('Choose a supported language.')
        options = generation_options(settings)
        seed = int(seed)
        model = load_model('base')
        item = model.create_voice_clone_prompt(ref_audio=reference_audio_input(audio),
            ref_text=transcript or None, x_vector_only_mode=not include_transcript)[0]
        if seed >= 0:
            torch.manual_seed(seed)
            torch.cuda.manual_seed_all(seed)
        start = time.time()
        wavs, sr = model.generate_voice_clone(text=text, language=language,
            voice_clone_prompt=[item], **options, **instruction_kwargs(model, instruction))
        wav = np.asarray(wavs[0])
        if wav.size == 0 or not np.isfinite(wav).all():
            raise RuntimeError('The model returned empty or invalid audio.')
        OUTPUTS.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
        path = OUTPUTS / (stamp + '.wav')
        sf.write(path, wav, sr, subtype='PCM_24')
        authorize_generated_file(path)
        (OUTPUTS / (stamp + '.json')).write_text(json.dumps({'mode':'clone_audition',
            'text':text,'reference_transcript':transcript,'identity_only':not include_transcript,
            'instruction':instruction,'language':language,'seed':seed,'generation_settings':options},indent=2),encoding='utf-8')
        prompt = {key: value.detach().cpu() if torch.is_tensor(value) else value
                  for key, value in asdict(item).items()}
        state = {'audio':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                 'transcript':transcript,'source':'clone_reference','prompt':prompt,
                 'sample_text':text,'identity_only':not include_transcript}
        note = 'The original reference voice will be saved when you choose Save audition as voice .pt. No .pt voice has been saved yet.'
        return str(path),str(path),f'Clone audition: {path}\nGenerated in {time.time()-start:.1f} seconds. {note}',state,transcript,False
    except Exception as exc:
        raise gr.Error(str(exc)) from exc
    finally:
        if release_after:
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
        reference_input = reference_audio_input(audio)
        model = load_model()
        items = model.create_voice_clone_prompt(ref_audio=reference_input, ref_text=(transcript or '').strip() or None, x_vector_only_mode=bool(identity_only))
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
    return clone_audition(audio, transcript, not identity_only, text, instruction,
                          language, seed, release_after, *settings)[:3]


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
    return clone_audition(audio, transcript, not identity_only, text, instruction,
                          language, seed, release_after, *settings)


def clone_reference_and_save(audio, transcript, include_transcript, text, instruction, language, seed, release_after, *settings):
    """Legacy callback shape; audition only, with no automatic .pt save."""
    try:
        result = clone_audition(audio, transcript, include_transcript, text, instruction,
                                language, seed, release_after, *settings)
        return (*result, gr.update(value=None,visible=False), gr.update(value='',visible=False))
    except Exception as exc:
        return None, None, f'Audition failed: {exc}', None, '', False, gr.update(value=None,visible=False), gr.update(value='',visible=False)


def save_preview_voice(preview, confirmed):
    import hashlib
    # Retain the legacy argument for Python callers, but saving needs no approval checkbox.
    if not preview:
        raise gr.Error('Generate an audition sample before saving a voice.')
    audio = Path(preview['audio']).resolve()
    if audio.parent not in (STORAGE.output_history | {OUTPUTS.resolve()}) or not audio.is_file() or audio.suffix.lower() != '.wav':
        raise gr.Error('The preview audio is unavailable. Generate another preview.')
    if hashlib.sha256(audio.read_bytes()).hexdigest() != preview['sha256']:
        raise gr.Error('The preview audio changed. Generate another preview before saving a voice.')
    if preview.get('source') == 'clone_reference':
        prompt = preview.get('prompt')
        if not isinstance(prompt, dict) or not torch.is_tensor(prompt.get('ref_spk_embedding')):
            raise gr.Error('The reference prompt is unavailable. Create another audition.')
        identity_only = bool(preview.get('identity_only'))
        transcript = (preview.get('transcript') or '').strip()
        if not identity_only and not transcript:
            raise gr.Error('Confirm or correct the exact words in the original reference audio.')
        item = dict(prompt, ref_text=None if identity_only else transcript)
        if not LOCK.acquire(blocking=False):
            raise gr.Error('Another operation is running. Wait for it to finish.')
        path = None
        try:
            VOICES.mkdir(parents=True, exist_ok=True)
            path = VOICES / (time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]+'.pt')
            torch.save({'items':[item]}, path)
            read_voice(path)
            authorize_generated_file(path)
            return str(path), 'Original reference voice saved. This .pt uses the original reference audio, not the generated audition WAV.'
        except Exception as exc:
            if path and path.is_file():
                path.unlink()
            raise gr.Error(str(exc)) from exc
        finally:
            LOCK.release()
    # Reference-audio/ICL mode deliberately retains delivery context, unlike identity-only.
    path, _ = save_voice(str(audio), preview['transcript'], False)
    return path, 'Voice saved from the generated audition sample. Reuse this .pt in Generate; delivery can vary on new text.'


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


def compose_controls(batch=False, clone_button=None, clone_busy=None):
    text = None
    if not batch:
        text = gr.Textbox(label='Commentary text', lines=4, placeholder='Normal summon Dark Necromancer...')
    mode = entries = None
    instruction = gr.Textbox(label='Delivery instruction (optional)', lines=2, placeholder='Speak calmly and naturally, with quiet confidence.', elem_id='base-delivery-instruction')
    language = gr.Dropdown(LANGUAGES, value='English', label='Language')
    seed, release, identity, settings = generation_settings_controls()
    if batch:
        mode = gr.State('single')
        with gr.Tabs(elem_id='commentary-mode-tabs'):
            with gr.Tab('Single commentary') as single_tab:
                text = gr.Textbox(label='Commentary text', lines=4, placeholder='Normal summon Dark Necromancer...')
                gr.HTML(ui_asset_text('single-clip-seed.html'), elem_id='single-clip-seed', css_template=ui_asset_text('clip-editor.css'))
            with gr.Tab('Multiple') as batch_tab:
                gr.Markdown('Each timestamp marks a clip start. Generate individual clips, then optionally combine them into one timeline with silent gaps. Shared settings above apply to every clip.', elem_classes=['section-note'])
                gr.HTML(ui_asset_text('clip-import.html'), elem_id='clip-import', css_template=ui_asset_text('clip-editor.css'))
        if clone_button is not None:
            single_tab.select(lambda busy:('single',gr.skip() if busy else gr.update(interactive=True,value='Clone reference & generate commentary')), inputs=clone_busy,outputs=[mode,clone_button], queue=False, api_name=False)
            batch_tab.select(lambda busy:('batch',gr.skip() if busy else gr.update(interactive=False,value='Switch to Single commentary to clone')), inputs=clone_busy,outputs=[mode,clone_button], queue=False, api_name=False)
        else:
            single_tab.select(lambda: 'single', outputs=mode, queue=False, api_name=False)
            batch_tab.select(lambda: 'batch', outputs=mode, queue=False, api_name=False)
    button = gr.Button('Generate', variant='primary', elem_classes=['primary-action'], elem_id='generate-commentary' if batch else None,interactive=not batch,preserved_by_key=['value','interactive'])
    return (text, instruction, language, seed, release, identity, button, settings, mode, entries) if batch else (text, instruction, language, seed, release, identity, button, settings)


def generation_settings_controls(include_identity=True):
    with gr.Accordion('Generation settings', open=False, elem_classes=['generation-settings']):
        with gr.Row(elem_classes=['shared-seed-row']):
            seed = gr.Number(value=42, precision=0, label='Seed', info='Used for clips without their own seed. Use -1 for random.', elem_classes=['shared-seed'])
            gr.Checkbox(value=False, label='Randomize', elem_classes=['seed-randomize'], info='Fresh seeds for each take. Per-clip edits apply to the next take.')
        release = gr.Checkbox(value=True, label='Release GPU memory after generation')
        identity = gr.Checkbox(value=False, label='Use voice identity only', info='Ignore reference delivery. This may reduce resemblance.', elem_id='base-identity-only') if include_identity else None
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
    return seed, release, identity, settings


def output_controls():
    gr.Markdown('## Listen & export')
    gr.Markdown('Review your take before saving a voice or adding it to an episode.', elem_classes=['section-note'])
    audio = gr.Audio(label='Generated audio', type='filepath', elem_classes=['studio-audio-output','studio-audio'], waveform_options=gr.WaveformOptions(waveform_color='#6e8b9f', waveform_progress_color='#d9b96e', trim_region_color='#d9b96e30'))
    download = gr.File(label='Download WAV', interactive=False, height=85, elem_classes=['studio-wav-output'])
    status = gr.Markdown(value='', elem_classes=['studio-output-status'], sanitize_html=True)
    unload_button = gr.Button('Unload model')
    bind_busy_action(unload_button,unload,[],[status],'Unload model','Unloading model...',0,queue_action=False)
    legacy_unload = gr.Button(visible=False)
    legacy_unload.click(unload,outputs=status,concurrency_limit=1)
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
    preview = result[3] or {}
    reference = preview.get('source') == 'clone_reference'
    correction_label = 'Actual words in original reference audio' if reference else 'Actual words in audition sample'
    return (*result[:5], False, controls[0],
            gr.update(value=preview.get('transcript',''), label=correction_label, visible=not (reference and preview.get('identity_only'))),
            controls[3], controls[4], gr.update(value=False, visible=not (reference and preview.get('identity_only'))))


def generate_preview_atomic(*args):
    return _atomic_preview_controls(generate_preview(*args))


def clone_reference_atomic(*args):
    return _atomic_preview_controls(clone_reference_and_save(*args))


def design_submission(*args):
    try:
        result = _atomic_preview_controls(generate_design_preview(*args))
        return (gr.update(value=result[0], visible=True), gr.update(value=result[1], visible=True),
                *result[2:])
    except Exception as exc:
        return (gr.update(value=None, visible=False), gr.update(value=None, visible=False),
                'Voice design failed: ' + str(exc), None, '', False, gr.update(visible=False),
                gr.update(value='', visible=False), gr.update(value=None, visible=False),
                gr.update(value='', visible=False), False)


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


def design_download_visibility(preview, workflow, busy):
    valid = workflow == 'design' and isinstance(preview, dict) and preview.get('source') == 'design_sample'
    return gr.update(visible=valid, interactive=valid and not busy)


def save_designed_voice(preview, workflow, confirmed, correction, use_correction):
    if workflow != 'design' or not isinstance(preview, dict) or preview.get('source') != 'design_sample':
        raise gr.Error('Generate a Design sample before downloading its voice.')
    return save_preview_corrected(preview, confirmed, correction, use_correction)


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



def current_batch_timing(result, rows):
    if (result or {}).get('streaming'):
        raise ValueError('Wait for the running batch to finish before combining or setting timestamps.')
    from batch_generation import validate_entries
    entries = validate_entries(rows, validate_seeds=False)
    if not isinstance(result, dict) or not isinstance(result.get('clips'), list):
        raise ValueError('Generate clips before combining them.')
    if len(entries) != result.get('requested_clips', len(result['clips'])):
        raise ValueError('The number of clips changed. Generate the new or changed clips before combining.')
    updated, seen = [], set()
    by_id = {entry.get('id'): entry for entry in entries if entry.get('id')}
    for clip in result['clips']:
        index = clip.get('index')
        if clip.get('id'):
            if clip['id'] in seen:
                raise ValueError('The generated paragraph identities are duplicated. Generate a new full batch.')
            seen.add(clip['id'])
            entry = by_id.get(clip['id'])
            if entry is None:
                raise ValueError('A generated paragraph was removed or replaced. Its audio was kept; generate a new full batch before combining.')
        else:
            if not isinstance(index, int) or isinstance(index, bool) or index < 1 or index > len(entries):
                raise ValueError('The generated clips no longer match the editor. Generate them again.')
            entry = entries[index - 1]
        if clip.get('text') != entry['text']:
            raise ValueError(f"Clip {entry['index']} commentary changed. Generate that clip again before combining.")
        updated.append({**clip, 'index': entry['index'], 'minutes': entry['minutes'],
                        'seconds': entry['seconds'], 'label': entry['label']})
    complete = len(updated) == len(entries)
    return {**result, 'clips': updated, 'complete': complete}


def regeneration_entry(rows, row_id):
    from batch_generation import validate_entries
    if not row_id or not isinstance(rows, list):
        raise ValueError('The paragraph changed or was removed. Generate the clips again.')
    matches = [row for row in rows if isinstance(row, dict) and row.get('id') == row_id]
    if len(matches) != 1:
        raise ValueError('The paragraph changed or was removed. Existing audio was kept.')
    return validate_entries(matches)[0]


def prepare_clip_regeneration(result, rows, row_id, workflow, mode, voice, instruction,
                              language, seed, release, identity, *settings):
    if workflow != 'generate' or mode != 'batch':
        raise ValueError('Switch to Generate / Multiple to generate a paragraph.')
    if (result or {}).get('streaming'):
        raise ValueError('Wait for the running batch to finish before starting a queued clip.')
    from batch_generation import validate_entries, validate_seed
    # Check all identities, but do not require unrelated unfinished drafts to be valid.
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError('The paragraph list changed. Existing audio was kept.')
    validate_entries([dict(id=row.get('id'), minutes=0, seconds=0, text='identity') for row in rows])
    if result:
        if not isinstance(result, dict) or not result.get('batch_id') or not isinstance(result.get('clips'), list):
            raise ValueError('The generated batch is invalid. Existing audio was kept.')
        clip_ids = [clip.get('id') for clip in result['clips']]
        if any(not isinstance(key, str) or not key for key in clip_ids) or len(set(clip_ids)) != len(clip_ids):
            raise ValueError('Generated paragraph identities are invalid or duplicated. Existing audio was kept.')
    entry = regeneration_entry(rows, row_id)
    seed_override = 'seed' in entry
    entry = {**entry, 'seed': validate_seed(entry.get('seed', seed))}
    batch_id, revision = (result or {}).get('batch_id'), (result or {}).get('revision')
    generated = generate(voice, entry['text'], instruction, language, entry['seed'], release, identity, *settings)
    path = generated[0]
    if not path and len(generated) > 2 and generated[2]:
        raise ValueError(str(generated[2]) + ' Existing audio was kept.')
    if not path or Path(path).suffix.lower() != '.wav' or not Path(path).is_file() or Path(path).stat().st_size == 0:
        raise ValueError('Generation returned no usable audio. Existing audio was kept.')
    return {'batch_id': batch_id, 'revision': revision,
            'entry': entry, 'audio': path, 'seed_override': seed_override}


def commit_clip_regeneration(candidate, result, rows):
    """Atomically add/replace one stable-ID clip without losing any prior take."""
    import shutil
    from batch_generation import write_archive, timestamp_label, validate_entries
    if any(candidate.get(key) != (result or {}).get(key) for key in ('batch_id', 'revision')):
        raise ValueError('The generated batch changed while this clip was running. Existing audio was kept.')
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError('The paragraph list changed. Existing audio was kept.')
    identities = validate_entries([dict(id=row.get('id'), minutes=0, seconds=0, text='identity') for row in rows])
    row_ids = [row['id'] for row in identities]
    row_id = candidate['entry']['id']
    # A future draft seed must not invalidate the immutable seed captured on click.
    current_rows = [{k: v for k, v in row.items() if k != 'seed'} if row.get('id') == row_id else row
                    for row in rows] if candidate.get('captured_seed') else rows
    current = regeneration_entry(current_rows, row_id)
    if current['text'] != candidate['entry']['text']:
        raise ValueError('The paragraph changed while this clip was running. Existing audio was kept; regenerate its new text.')
    if not candidate.get('captured_seed') and ((candidate.get('seed_override') and 'seed' not in current) or ('seed' in current and current['seed'] != candidate['entry']['seed'])):
        raise ValueError('The paragraph seed changed while this clip was running. Existing audio was kept; regenerate with its new seed.')
    old_clips = (result or {}).get('clips', [])
    clip_ids = [clip.get('id') for clip in old_clips]
    if any(not isinstance(key, str) or not key for key in clip_ids) or len(set(clip_ids)) != len(clip_ids):
        raise ValueError('Generated paragraph identities are invalid or duplicated. Existing audio was kept.')
    by_id = {clip['id']: dict(clip) for clip in old_clips}
    existed = row_id in by_id
    position = row_ids.index(row_id) + 1
    replacement = {**by_id.get(row_id, {}), **current, 'index': position, 'seed': candidate['entry']['seed']}
    batch_id = (result or {}).get('batch_id') or uuid.uuid4().hex
    folder = Path(result['batch_dir']) if result else Path(OUTPUTS) / ('batch-' + batch_id)
    source = Path(candidate['audio'])
    if source.suffix.lower() != '.wav' or not source.is_file() or not source.stat().st_size:
        raise ValueError('Generated audio is unavailable. Existing audio was kept.')
    # Always copy to a unique revision file: previous players/downloads stay immutable.
    filename = timestamp_label(current['minutes'], current['seconds']).replace(':', 'm') + f"s-{position:03d}-{uuid.uuid4().hex}.wav"
    target = folder / filename
    replacement.update(audio=str(target), filename=filename)
    by_id[row_id] = replacement
    clips = []
    for index, key in enumerate(row_ids, 1):
        if key in by_id:
            clips.append(dict(by_id[key], index=index))
    orphans = [dict(clip, index=len(rows)+index) for index, clip in enumerate(old_clips, 1) if clip['id'] not in row_ids]
    clips.extend(orphans)
    complete = not orphans and len(clips) == len(rows)
    if complete:
        try:
            entries = validate_entries(rows, validate_seeds=False)
            complete = all(by_id[entry['id']]['text'] == entry['text'] for entry in entries)
        except ValueError:
            complete = False
    folder.mkdir(parents=True, exist_ok=True)
    archive = None
    try:
        with source.open('rb') as reader, target.open('xb') as writer:
            shutil.copyfileobj(reader, writer)
        archive = write_archive(clips, len(rows), folder, complete=complete)
        authorize_generated_file(target)
        authorize_generated_file(Path(archive))
    except BaseException:
        target.unlink(missing_ok=True)
        if archive:
            Path(archive).unlink(missing_ok=True)
        raise
    status = f"{'Updated' if existed else 'Generated'} clip {position} ({current['label']}). All other clips were kept. Playback, downloads and the next Combine use this latest version."
    if orphans:
        status += ' Removed paragraphs still have saved audio; generate a new full batch before combining.'
    elif not complete:
        status += ' Some current paragraphs still need generation.'
    return {**(result or {}), 'batch_id': batch_id, 'batch_dir': str(folder), 'clips': clips,
            'archive': archive, 'revision': (result or {}).get('revision', 0) + 1,
            'requested_clips': len(rows), 'complete': complete, 'error': None,
            'origin_draft_id': result.get('origin_draft_id') if result else candidate.get('draft_id'),
            'highlight_id': row_id, 'status': status}


def regenerate_clip_ui(result, rows, workflow, mode, voice, instruction, language, seed,
                       release, identity, evt: gr.EventData, *settings):
    try:
        data = evt._data
        current_batch = (result or {}).get('batch_id')
        if 'batch_id' in data and data['batch_id'] != current_batch:
            same_initial_draft = (data['batch_id'] is None and data.get('draft_id')
                                  and data['draft_id'] == (result or {}).get('origin_draft_id'))
            if not same_initial_draft:
                if not (result or {}).get('batch_id'):
                    raise ValueError('The generation session was reset. Existing files were kept. Generate this clip again to restore it in the current session.')
                raise ValueError('The generated batch changed while this clip was queued. Existing audio was kept. The clip list will refresh; retry the current clip.')
        captured = 'seed' in data
        if captured:
            from batch_generation import validate_seed
            request_seed = validate_seed(data['seed'])
            rows = [dict(row, seed=request_seed) if isinstance(row, dict) and row.get('id') == data.get('id') else row for row in rows]
        candidate = prepare_clip_regeneration(result, rows, data.get('id'), workflow, mode,
                                             voice, instruction, language, seed, release, identity, *settings)
        candidate['captured_seed'] = True  # Seed is fixed once this queued request starts.
        candidate['draft_id'] = data.get('draft_id')
        return candidate
    except Exception as error:
        return {'error': str(error)}


def commit_clip_regeneration_ui(candidate, result, rows):
    try:
        if not candidate or candidate.get('error'):
            raise ValueError((candidate or {}).get('error', 'No replacement audio was generated.'))
        if not LOCK.acquire(blocking=False):
            raise ValueError('Another operation is running. Existing audio was kept; try Regenerate again.')
        try:
            updated = commit_clip_regeneration(candidate, result, rows)
        finally:
            LOCK.release()
        return updated, updated['status'], gr.update(value=updated['archive'], visible=True)
    except Exception as error:
        return gr.skip(), 'Regeneration failed: ' + str(error), gr.skip()


def batch_editor_metadata(result):
    from clip_timing import generated_timing_metadata
    result = result or {}
    return {'batch_id': result.get('batch_id'), 'origin_draft_id': result.get('origin_draft_id'), 'ids': [clip['id'] for clip in result.get('clips', []) if clip.get('id')],
            'seeds': {clip['id']: clip['seed'] for clip in result.get('clips', []) if clip.get('id') and 'seed' in clip},
            'highlight_id': result.get('highlight_id'), 'timing': generated_timing_metadata(result),
            'streaming': bool(result.get('streaming')), 'pending_ids': result.get('pending_ids', []),
            'active_id': result.get('active_id'), 'requested_ids': result.get('requested_ids', []),
            'failed_id': result.get('failed_id'),
            'version': f"{result.get('batch_id', '')}:{result.get('revision', 0)}"}


def combine_generated_clips(result, minutes, seconds, workflow, mode, rows=None):
    """Replace media only after a successful mix of the current editor timestamps."""
    if workflow != 'generate' or mode != 'batch':
        return gr.skip(), gr.skip(), 'Switch to Generate / Multiple to combine generated clips.'
    if not LOCK.acquire(blocking=False):
        return gr.skip(), gr.skip(), 'Another operation is running. Wait for it to finish, then combine.'
    try:
        from combine_clips import combine_timeline
        combined = combine_timeline(current_batch_timing(result, rows) if rows is not None else result, minutes, seconds, OUTPUTS)
        authorize_generated_file(Path(combined['audio']))
        return combined['audio'], combined['audio'], combined['status']
    except Exception as error:
        return gr.skip(), gr.skip(), 'Cannot combine: ' + str(error)
    finally:
        LOCK.release()


def timeline_minimum_status(result, rows=None):
    """Proactive guidance uses the same current-row and audio checks as Combine."""
    if not (result or {}).get('clips'):
        return ''
    try:
        from combine_clips import minimum_timeline_seconds
        current = current_batch_timing(result, rows) if rows is not None else result
        minimum = minimum_timeline_seconds(current)
        return f'Minimum total duration: **{minimum // 60}:{minimum % 60:02d}** (minutes:seconds).'
    except (ValueError, OSError, RuntimeError) as error:
        return 'Minimum unavailable: ' + str(error)


def timeline_duration_default(result, rows=None, edited=False):
    """Follow the current minimum until the user edits either duration field.

    User input, even zero or an empty field, opts out for this UI session.
    Unavailable timing leaves existing values and the last combined file alone.
    """
    if edited or not (result or {}).get('clips'):
        return gr.skip(), gr.skip()
    try:
        from combine_clips import minimum_timeline_seconds
        current = current_batch_timing(result, rows) if rows is not None else result
        return divmod(minimum_timeline_seconds(current), 60)
    except (ValueError, OSError, RuntimeError):
        return gr.skip(), gr.skip()


TIMELINE_DURATION_EDIT_JS = """() => {
    const row = document.getElementById('timeline-duration-fields');
    if (row) row.dataset.durationEdited = 'true';
    return [];
}"""
TIMELINE_DURATION_APPLY_JS = """(candidate, minutes, seconds) => {
    const row = document.getElementById('timeline-duration-fields');
    if (!row || row.dataset.durationEdited === 'true' ||
        !Array.isArray(candidate) || !candidate.every(Number.isInteger)) {
        return [minutes, seconds];
    }
    return candidate;
}"""


def render_timeline_combine(result, workflow, mode, rows=None):
    stateful = isinstance(result, gr.State)
    if not stateful and not (result or {}).get('clips'):
        return
    with gr.Column(visible=not stateful, elem_id='timeline-combine', elem_classes=['timeline-combine']) as combine_panel:
        gr.Markdown('### Combine clips')
        gr.Markdown('Choose the full timeline length. Clips use the current timestamps in the editor; gaps are silent and overlaps play together. No clip is cut short. The last combined audio stays available until a new Combine succeeds.', elem_classes=['section-note'])
        initial_duration = (0, 0) if stateful else timeline_duration_default(result, getattr(rows, 'value', rows))
        duration_edited = gr.State(False)
        with gr.Row(elem_id='timeline-duration-fields'):
            minutes = gr.Number(value=initial_duration[0] if isinstance(initial_duration[0], int) else 0, precision=0, minimum=0, maximum=1440, label='Total duration: minutes', elem_classes=['timeline-duration'])
            seconds = gr.Number(value=initial_duration[1] if isinstance(initial_duration[1], int) else 0, precision=0, minimum=0, maximum=59, label='Total duration: seconds', elem_classes=['timeline-duration'])
        gr.on(triggers=[minutes.input, seconds.input], fn=lambda: True,
              outputs=duration_edited, js=TIMELINE_DURATION_EDIT_JS,
              queue=False, show_progress='hidden', api_name=False)
        retime = gr.Button('Set timestamps back-to-back', elem_id='clip-retime')
        gr.HTML('<p role="status" aria-live="polite"></p>', elem_id='clip-timing-status')
        retime.click(fn=None, js="() => { const origin=document.getElementById('clip-retime'); window.voxoverClipEditor?.alignTimestamps(origin, text => { const status=document.querySelector('#clip-timing-status p'); if(status)status.textContent=text; }); }", api_name=False)
        combine = gr.Button('Combine', elem_classes=['primary-action'])
        minimum_status = gr.Markdown('' if stateful else timeline_minimum_status(result), elem_id='timeline-minimum-status', elem_classes=['studio-output-status','timeline-minimum-status'], sanitize_html=True)
        notice = gr.Markdown('', elem_classes=['studio-output-status'], sanitize_html=True)
        with gr.Column(elem_id='combined-timeline-result') as media_panel:
            combined_audio = gr.Audio(label='Combined audio', type='filepath', interactive=False, elem_classes=['studio-audio-output','studio-audio'], waveform_options=gr.WaveformOptions(waveform_color='#6e8b9f',waveform_progress_color='#d9b96e',trim_region_color='#d9b96e30'))
            combined_download = gr.DownloadButton('Download combined WAV')
        def start_combine():
            return gr.update(value='Combining...',interactive=False),gr.update(interactive=False),gr.update(interactive=False),'Combining generated clips...'
        def execute_combine(total_minutes,total_seconds,active_workflow,active_mode,generated_result,current_rows):
            return combine_generated_clips(generated_result,total_minutes,total_seconds,active_workflow,active_mode,current_rows)
        def finish_combine():
            return gr.update(value='Combine',interactive=True),gr.update(interactive=True),gr.update(interactive=True)
        generated_state = result if stateful else gr.State(result)
        editor_rows = rows if rows is not None else gr.State(None)
        gr.on(triggers=[generated_state.change, editor_rows.change], fn=timeline_minimum_status,
              inputs=[generated_state, editor_rows], outputs=minimum_status,
              queue=False, trigger_mode='always_last', show_progress='hidden', api_name=False)
        # Apply defaults in the browser only after checking for user input there.
        # A server calculation already in flight must not overwrite a later edit.
        duration_candidate = gr.JSON(None, visible=False)
        def calculate_duration_candidate(batch, current_rows, edited):
            return list(timeline_duration_default(batch, current_rows, edited))
        gr.on(triggers=[generated_state.change, editor_rows.change], fn=calculate_duration_candidate,
              inputs=[generated_state, editor_rows, duration_edited], outputs=duration_candidate,
              queue=False, trigger_mode='always_last', show_progress='hidden', api_name=False)
        duration_candidate.change(fn=None, js=TIMELINE_DURATION_APPLY_JS,
              inputs=[duration_candidate, minutes, seconds], outputs=[minutes, seconds],
              queue=False, show_progress='hidden', api_name=False)
        combine.click(start_combine,outputs=[combine,minutes,seconds,notice],queue=False,api_name=False).then(
            execute_combine,[minutes,seconds,workflow,mode,generated_state,editor_rows],[combined_audio,combined_download,notice],concurrency_limit=1,api_name=False,
            js="(...args) => { args[2] = document.querySelector('#voice-mode-tabs button[aria-pressed=\"true\"]')?.dataset.voiceMode || args[2]; args[3] = document.querySelector('#commentary-mode-tabs [role=\"tab\"][aria-selected=\"true\"]')?.textContent.trim() === 'Multiple' ? 'batch' : 'single'; return args; }").then(
            finish_combine,outputs=[combine,minutes,seconds],queue=False,api_name=False)
        if stateful:
            result.change(lambda batch:gr.update(visible=bool((batch or {}).get('clips'))),inputs=result,outputs=combine_panel,queue=False,api_name=False)


def generate_commentary_mode(mode, rows, voice, text, instruction, language, seed, release, identity, *settings, progress=gr.Progress()):
    if mode != 'batch':
        result = generate_preview_atomic(voice,text,instruction,language,seed,release,identity,*settings)
        return (gr.update(value=result[0],visible=True),gr.update(value=result[1],visible=True),*result[2:], None, gr.update(visible=False), '', gr.update(value=None,visible=False))
    from batch_generation import run_batch, validate_entries, validate_seed
    generation_options(settings)
    read_voice(voice)
    entries = [{**entry, 'seed': validate_seed(entry.get('seed', seed))} for entry in validate_entries(rows)]
    result = run_batch(entries, generate_clip=lambda paragraph,index: generate(voice,paragraph,instruction,language,entries[index]['seed'],False,identity,*settings)[0], output_root=OUTPUTS, lock=LOCK, release_after=release, release_model=release_model, on_progress=lambda index,total,label:progress((index,total),desc=f'Generating clip {index+1}/{total} ({label})'))
    for clip in result['clips']:
        authorize_generated_file(Path(clip['audio']))
    if result['archive']: authorize_generated_file(Path(result['archive']))
    # Existing single preview remains on disk, but cannot be mistaken for this batch.
    return (gr.update(value=None,visible=False),gr.update(value=None,visible=False),'',None,'',False,gr.update(visible=False),gr.update(value=''),gr.update(value=None,visible=False),gr.update(value='',visible=False),False,result,gr.update(visible=True),result['status'],gr.update(value=result['archive'],visible=bool(result['archive'])))

def generate_commentary_ui(*args, progress=gr.Progress()):
    # Return a normal event result even on failure so the completion event always
    # restores controls. Keep previous media and show an explicit error notice.
    try:
        return generate_commentary_mode(*args, progress=progress)
    except Exception as error:
        updates = [gr.skip() for _ in range(15)]
        updates[2] = gr.update(value='Generation failed: ' + str(error), visible=True)
        return tuple(updates)


def generate_workflow_mode(workflow, mode, rows, token, ref_audio, ref_transcript, include_transcript,
                           description, voice, text, instruction, language, seed, release, identity,
                           *settings, request: gr.Request = None, progress=gr.Progress()):
    """Audition once in Clone/Design; use saved voices for Generate singles/batches."""
    if workflow not in ('clone', 'design', 'generate'):
        raise ValueError('Choose Clone, Design, or Generate.')
    if mode not in ('single', 'batch'):
        raise ValueError('Choose single commentary or multiple clips.')
    if workflow != 'generate' or mode == 'single':
        from batch_generation import validate_seed
        seed = validate_seed(seed)
    if workflow == 'generate':
        return (*generate_commentary_mode(mode, rows, voice, text, instruction, language,
                                          seed, release, identity, *settings, progress=progress),
                gr.skip(), gr.skip(), gr.skip(), gr.skip())
    # An existing timed draft may remain selected briefly while the UI changes
    # tabs. Audition modes always use the shared single-text component.
    if workflow == 'design':
        result = _atomic_preview_controls(generate_design_preview(text, description, language,
                                                                  seed, release, *settings))
    else:
        result = _atomic_preview_controls(clone_audition(ref_audio, ref_transcript, include_transcript,
            text, instruction, language, seed, release, *settings))
    return (gr.update(value=result[0], visible=bool(result[0])),
            gr.update(value=result[1], visible=bool(result[1])), *result[2:],
            None, gr.update(visible=False), '', gr.update(value=None, visible=False),
            gr.skip(), gr.skip(), gr.skip(), gr.skip())


def generate_workflow_ui(request: gr.Request, *args, progress=gr.Progress()):
    try:
        previous = None
        if len(args) == 16 + len(SETTING_DEFAULTS):  # Final UI snapshot is not a synthesis setting.
            args, previous = args[:-1], args[-1]
        result = generate_workflow_mode(*args, request=request, progress=progress)[:-2]
        batch = result[11]
        if isinstance(batch, dict) and 'clips' in batch and (not batch['clips'] or (batch.get('error') and (previous or {}).get('clips'))):
            raise ValueError((batch.get('error') or batch['status']) + ' Previous Listen audio was kept.')
        return result
    except Exception as error:
        updates = [gr.skip() for _ in range(17)]
        updates[2] = gr.update(value='Generation failed: ' + str(error), visible=True)
        return tuple(updates)


def streamed_batch_view(result, previous):
    """Keep unreplaced takes available until a new full batch succeeds."""
    previous = previous or {}
    key = lambda clip: clip.get('id') or ('position', clip['index'])
    by_id = {key(clip): clip for clip in result['clips']}
    if result.get('streaming') or result.get('error'):
        clips = [by_id.pop(key(clip), clip) for clip in previous.get('clips', [])]
        clips.extend(by_id.values())
        order = {key: index for index, key in enumerate(result.get('requested_ids', []))}
        clips.sort(key=lambda clip: order.get(clip.get('id'), len(order)))
        result = dict(result, clips=clips)
        if previous.get('clips') and result.get('error'):
            result['status'] += ' Unreplaced previous takes are also kept.'
            # Publish a matching archive of the retained and newly completed takes.
            # An archive failure must never roll back already published audio.
            from batch_generation import write_archive
            filenames = [clip['filename'] for clip in clips]
            if len(set(filenames)) != len(filenames):
                clips = [dict(clip, filename=f"{index:03d}-{clip['filename']}")
                         for index, clip in enumerate(clips, 1)]
                result['clips'] = clips
            try:
                result['archive'] = write_archive(clips, result['requested_clips'],
                                                  result['batch_dir'], complete=False)
            except Exception as error:
                result['archive'] = None
                result['status'] += ' Download-all archive unavailable: ' + str(error)
    return result


def generate_workflow_stream(request: gr.Request, *args, progress=gr.Progress()):
    """Stream batch snapshots; keep the RLock/model lifetime on one worker thread.

    Gradio may resume a synchronous iterator on different pool threads, so holding
    an RLock across yields is unsafe. Only this worker owns inference and cleanup;
    the consumer publishes immutable snapshots and exact file authorizations.
    """
    import contextvars
    import queue
    from batch_generation import run_batch, validate_entries, validate_seed
    previous = args[-1] if len(args) == 16 + len(SETTING_DEFAULTS) else None
    values = args[:-1] if len(args) == 16 + len(SETTING_DEFAULTS) else args
    if len(values) < 2 or values[:2] != ('generate', 'batch'):
        result = generate_workflow_ui(request, *args, progress=progress)
        yield (*result, batch_editor_metadata(None) if result[11] is None else gr.skip())
        return
    latest = previous
    try:
        (_, _, rows, _, _, _, _, _, voice, _, instruction, language, seed,
         release, identity, *settings) = values
        generation_options(settings)
        read_voice(voice)
        entries = [{**entry, 'seed': validate_seed(entry.get('seed', seed))}
                   for entry in validate_entries(rows)]
        messages = queue.Queue()
        cancelled = threading.Event()
        def synthesize(paragraph, index):
            audio, _, message = generate(voice, paragraph, instruction, language,
                                         entries[index]['seed'], False, identity, *settings)
            if not audio:
                raise RuntimeError(message or 'Generation did not produce an audio file.')
            return audio
        def produce():
            try:
                run_batch(entries, generate_clip=synthesize,
                    output_root=OUTPUTS, lock=LOCK, release_after=release, release_model=release_model,
                    on_update=lambda result: messages.put(('result', result)), cancelled=cancelled.is_set)
            except Exception as error:
                messages.put(('error', error))
            finally:
                messages.put(('done', None))
        context = contextvars.copy_context()
        worker = threading.Thread(target=lambda: context.run(produce), name='voxover-batch', daemon=True)
        worker.start()
        try:
            while True:
                kind, result = messages.get()
                if kind == 'done': break
                if kind == 'error': raise result
                latest = streamed_batch_view(result, previous)
                for clip in latest['clips']:
                    authorize_generated_file(Path(clip['audio']))
                if latest['archive']: authorize_generated_file(Path(latest['archive']))
                # Do not change the top native progress surface during intermediate
                # updates. It remains an output of the running Gradio event.
                outputs = [gr.skip() for _ in range(17)]
                if not latest['streaming']:
                    outputs[:11] = [gr.update(value=None, visible=False),
                        gr.update(value=None, visible=False), '', None, '', False,
                        gr.update(visible=False), gr.update(value=''), gr.update(value=None, visible=False),
                        gr.update(value='', visible=False), False]
                outputs[11:15] = [latest, gr.update(visible=True), latest['status'],
                    gr.update(value=latest['archive'], visible=bool(latest['archive']))]
                yield (*outputs, batch_editor_metadata(latest))
                # Gradio marks output trackers as 'generating' after a yield and
                # clears their content. Re-publish native progress only AFTER the
                # snapshot reaches the client so the same top loader stays live.
                if result.get('streaming'):
                    completed = len(result['clips'])
                    description = (f'Generating clip {completed+1}/{len(entries)} ({entries[completed]["label"]})'
                                   if completed < len(entries) else 'Preparing download archive')
                    progress((completed, len(entries)), desc=description)
        finally:
            # On disconnect/cancel, finish the current inference, persist its audio,
            # stop before another row and release the lock in the owning thread.
            cancelled.set()
    except Exception as error:
        outputs = [gr.skip() for _ in range(17)]
        outputs[2] = gr.update(value='Generation failed: ' + str(error), visible=True)
        if latest is not previous and latest:
            latest = dict(latest, streaming=False, pending_ids=[], active_id=None,
                          complete=False, error=str(error))
            outputs[11] = latest
        yield (*outputs, batch_editor_metadata(latest))


def workflow_ready(workflow, mode, rows, voice, ref_audio, ref_transcript, include_transcript,
                   description, text, busy=False, *settings):
    if busy or workflow not in ('clone', 'design', 'generate'):
        return False
    if workflow == 'generate' and (not voice or not str(voice).lower().endswith('.pt')):
        return False
    if workflow == 'clone' and (not ref_audio or (include_transcript and not (ref_transcript or '').strip())):
        return False
    if workflow == 'design' and not (description or '').strip():
        return False
    try:
        generation_options(settings)
        if workflow == 'generate' and mode == 'batch':
            from batch_generation import validate_entries
            validate_entries(rows)
        elif (workflow == 'generate' and mode != 'single') or not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000:
            return False
        return True
    except (TypeError, ValueError, OverflowError):
        return False


def update_workflow_readiness(*args):
    return gr.update(interactive=workflow_ready(*args))


def workflow_started(workflow, request: gr.Request):
    ticket = begin_clone_selection(request) if workflow == 'clone' else 0
    return gr.update(interactive=False, value='Generating...'), gr.update(value='', visible=False), True, ticket


def workflow_stream_started(workflow, request: gr.Request):
    # A completed batch hides the single Audio component. Restore its native
    # loading surface before the next queued event starts, retaining old media.
    return (*workflow_started(workflow, request), gr.update(visible=True))


def workflow_completed(workflow, mode, rows, voice, ref_audio, ref_transcript, include_transcript,
                       description, text, *settings):
    return (gr.update(interactive=workflow_ready(workflow, mode, rows, voice, ref_audio, ref_transcript,
                                                 include_transcript, description, text, False, *settings),
                      value='Generate'), gr.update(value='', visible=False), False)


def commentary_ready(mode, rows, voice, text, busy=False, cloning=False, *settings):
    if busy or cloning or not voice or not str(voice).lower().endswith('.pt'):
        return False
    try:
        generation_options(settings)
        if mode=='batch':
            from batch_generation import validate_entries
            validate_entries(rows)
        elif not isinstance(text,str) or not 1<=len(text.strip())<=2000:
            return False
        return True
    except (TypeError,ValueError,OverflowError):
        return False


def update_generate_readiness(*args):
    return gr.update(interactive=commentary_ready(*args))


def generation_started_with_state():
    return gr.update(interactive=False,value='Generating commentary...'),gr.update(value='',visible=False),True


def generation_completed(mode,rows,voice,text,cloning,*settings):
    return gr.update(interactive=commentary_ready(mode,rows,voice,text,False,cloning,*settings),value='Generate commentary'),gr.update(value='',visible=False),False


def generation_started():
    return gr.update(interactive=False,value='Generating commentary...'), gr.update(value='<div class="studio-generation-running" role="status" aria-live="polite"><span class="studio-generation-spinner" aria-hidden="true"></span><span>Generating commentary. Please wait...</span></div>',visible=True)


def generation_finished():
    return gr.update(interactive=True,value='Generate commentary'), gr.update(value='',visible=False)


def bind_busy_action(button, action, inputs, outputs, label, busy_label, status_index,
                     api_name=False, begin=None, token=None, adapter=None, finish_mode=None, busy_state=None, queue_action=True):
    """One submission lifecycle: queued/running feedback, no duplicate UI requests,
    and normal error results so cleanup executes even when the action raises."""
    busy = busy_state if busy_state is not None else gr.State(False)
    def start(request: gr.Request):
        result = [gr.update(interactive=False,value=busy_label),
                  gr.update(value=busy_label,visible=True),True]
        if begin: result.append(begin(request))
        return tuple(result)
    def execute(request: gr.Request, *args):
        try:
            result = adapter(args,request) if adapter else action(*args)
            return result
        except Exception as error:
            result = [gr.skip() for _ in outputs]
            result[status_index] = gr.update(value='Operation failed: '+str(error),visible=True)
            return tuple(result) if len(outputs)>1 else result[0]
    def finish(mode='single'):
        enabled = finish_mode is None or mode=='single'
        return gr.update(interactive=enabled,value=label if enabled else 'Switch to Single commentary to clone'),False
    start_outputs=[button,outputs[status_index],busy]+([token] if begin else [])
    button.click(start,outputs=start_outputs,queue=False,api_name=False,trigger_mode='once').then(
        execute,inputs,outputs,api_name=api_name,concurrency_limit=1,trigger_mode='once',show_progress='hidden',queue=queue_action).then(
        finish,inputs=[finish_mode] if finish_mode is not None else [],outputs=[button,busy],queue=False,api_name=False)
    return busy


def commit_storage_submission(args, request):
    result=commit_storage_picker(*args,request)
    return (*result,result[2])


def clone_submission(args, request):
    result=clone_reference_selected(*args[:9],request,*args[9:])
    return (gr.update(value=result[0],visible=True),gr.update(value=result[1],visible=True),*result[2:],None,gr.update(visible=False))


def build_ui():
    with gr.Blocks(title='Voxover | Voice & Commentary') as app:
        with gr.Row(elem_id='studio-heading-row'):
            gr.HTML('<header class="studio-head"><div><h1>Voxover</h1><p>Find your voice. Shape every line. Create commentary locally.</p></div></header>', elem_id='studio-header')
            gr.HTML('<nav class="mode-tabs" aria-label="Voice workflow"><button type="button" data-voice-mode="clone" aria-pressed="true">Clone</button><button type="button" data-voice-mode="design" aria-pressed="false">Design</button><button type="button" data-voice-mode="generate" aria-pressed="false">Generate</button></nav>', elem_id='voice-mode-tabs')
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
                            with gr.Column(elem_id='clone-inputs'):
                                gr.Markdown('## Clone a reference voice')
                                gr.Markdown('Audition a reference voice. Save its reusable .pt only after listening.', elem_classes=['section-note'])
                                ref_s, transcript_s, xvec_s = reference_controls()
                                save = gr.Button('Save voice file', visible=False)
                                direct_preview = gr.Button('Clone reference & generate commentary', elem_classes=['primary-action'], elem_id='clone-reference-commentary', interactive=False, visible=False)
                                ref_s.change(fn=None, inputs=ref_s, js="(audio) => { window.voxoverReferenceReady = !!audio; document.getElementById('production-workspace')?.dispatchEvent(new Event('input',{bubbles:true})); }", api_name=False)
                                saved = gr.File(label='Saved voice file (.pt)', interactive=False, height=85, visible=False)
                                save_status = gr.Markdown(value='', visible=False, elem_classes=['studio-output-status'], sanitize_html=True)
                            with gr.Column(elem_id='design-inputs'):
                                gr.Markdown('## Design a voice')
                                gr.Markdown('Describe a new voice and create a sample to review. Each generation can vary.', elem_classes=['section-note'])
                                design_description = gr.Textbox(label='Voice design instruction', lines=3, value='', placeholder='Speak in an incredulous tone, but with a hint of panic beginning to creep into your voice.')
                                design_download = gr.Button('Download voice', visible=False, elem_id='design-download-voice', elem_classes=['studio-presence'])
                                design_file = gr.File(label='Designed voice (.pt)', interactive=False, visible=False, elem_id='design-voice-file')
                                design_save_status = gr.Markdown(value='', visible=False, elem_classes=['studio-output-status'])
                        with gr.Column(scale=1, min_width=340, elem_classes=['studio-panel'], elem_id='generate-panel'):
                            with gr.Column(elem_id='generate-top-controls'):
                                gr.Markdown('## Generate')
                                gr.Markdown('Write an audition in Clone or Design. Generate supports single commentary and multiple clips.', elem_classes=['section-note'])
                                with gr.Column(elem_id='saved-voice-inputs'):
                                    gr.Markdown('Use an existing .pt voice to create commentary.', elem_classes=['section-note'])
                                    voice = gr.File(label='Voice file (.pt)', file_types=['.pt'], type='filepath', height=130, elem_classes=['studio-voice-input'])
                                    info = gr.Markdown(value='', elem_classes=['studio-output-status'], elem_id='selected-voice-status', sanitize_html=True)
                                workflow = gr.Textbox(value='clone', label='Workflow mode', elem_id='workflow-mode')
                                clone_busy=gr.State(False)
                                text, instruction, language, seed, release, identity, button, settings, commentary_mode, clip_entries = compose_controls(batch=True)
                            clip_entries = gr.HTML([{'id':uuid.uuid4().hex,'minutes':0,'seconds':1,'text':''}], html_template=ui_asset_text('clip-editor.html'), js_on_load=ui_asset_text('clip-seeds.js')+'\n'+ui_asset_text('clip-timing.js')+'\n'+ui_asset_text('paragraph-timing.js')+'\n'+ui_asset_text('clip-editor.js'), elem_id='clip-editor', css_template=ui_asset_text('clip-editor.css'))
                    with gr.Column(scale=1, min_width=0, elem_classes=['studio-panel','result-panel'], elem_id='listen-panel'):
                        with gr.Column(elem_id='listen-top-controls'):
                            generation_busy=gr.State(False)
                            generation_notice = gr.HTML('',visible=False,elem_id='generation-notice')
                            audio, download, status = output_controls()
                            batch_result = gr.State(None)
                            batch_metadata = gr.HTML({'ids':[]}, visible='hidden', html_template='',
                                js_on_load="const publish=()=>{window.voxoverBatchMetadata=props.value;window.dispatchEvent(new Event('voxover-batch'));};watch('value',publish);publish();")
                            # Explicit completion chains publish current durations before releasing the queue.
                            # Clearing via another mode still removes stale per-clip identities.
                            batch_result.change(lambda result: gr.skip() if result else batch_editor_metadata(None), batch_result, batch_metadata, queue=False, api_name=False)
                            render_timeline_combine(batch_result, workflow, commentary_mode, clip_entries)
                            batch_status = gr.Markdown('', elem_classes=['studio-output-status'], elem_id='batch-status')
                            with gr.Row(elem_id='batch-playback-controls'):
                                play_all = gr.Button('Play all', elem_id='batch-play-all')
                                stop_all = gr.Button('Stop playback', elem_id='batch-stop-all')
                                batch_zip = gr.DownloadButton('Download all (ZIP)', visible=False)
                        with gr.Column(visible=True, elem_id='batch-output') as batch_panel:
                            def show_generated_batch(result):
                                return gr.update(visible=True) if (result or {}).get('clips') else gr.skip()
                            batch_result.change(show_generated_batch,batch_result,batch_panel,queue=False,api_name=False)
                            gr.HTML('<div class="clip-placeholders"></div>', elem_id='clip-placeholders')
                            @gr.render(inputs=batch_result)
                            def render_clips(result):
                                for clip in (result or {}).get('clips', []):
                                    updated = clip.get('id') and clip.get('id') == (result or {}).get('highlight_id')
                                    with gr.Column(elem_classes=['batch-clip']+(['batch-clip-updated'] if updated else []), elem_id='generated-clip-'+clip['id'] if clip.get('id') else None, key=clip['audio']):
                                        gr.Markdown('### '+clip['label']+(' - Updated' if updated else ''))
                                        player=gr.Audio(value=clip['audio'], type='filepath', interactive=False, label=clip['filename'], key='audio-'+clip['audio'], elem_classes=['studio-audio-output','studio-audio','batch-audio'], waveform_options=gr.WaveformOptions(waveform_color='#6e8b9f',waveform_progress_color='#d9b96e',trim_region_color='#d9b96e30'))
                                        player.stop(fn=None,js='() => window.voxoverBatchPlayback?.finished('+str(clip['index']-1)+')',api_name=False,key='ended-'+clip['audio'])
                                        gr.DownloadButton('Download '+clip['label'], value=clip['audio'])
                                        gr.HTML('<div class="wrap clip-pending-surface">'
                                            f'<div class="progress-level"><span class="progress-level-inner" role="status" aria-live="polite">Regenerating clip {clip["index"]}...</span></div>'
                                            f'<div class="progress-bar-wrap" role="progressbar" aria-label="Regenerating clip {clip["index"]}"><div class="progress-bar"></div></div>'
                                            '<div class="meta-text clip-pending-elapsed" aria-hidden="true">processing | 0.0s</div></div>',
                                            elem_classes=['clip-regeneration-loader'])
                        with gr.Column(visible=False, elem_classes=['studio-presence'], elem_id='audition-save-actions') as preview_actions:
                            preview_confirm = gr.State(False)  # Compatibility slot; no approval UI or save gate.
                            use_correction = gr.Checkbox(label='Correct transcript before saving', value=False, interactive=True, elem_id='edit-transcript')
                            correction = gr.Textbox(label='Actual words in audition sample', lines=3, visible=True, interactive=True, elem_id='correction-editor')
                            save_preview = gr.Button('Save audition as voice .pt', elem_id='save-corrected-audition', elem_classes=['primary-action','studio-presence'])
                            preview_file = gr.File(label='New preview voice (.pt)', interactive=False, visible=False, elem_classes=['studio-presence'])
                            preview_status = gr.Markdown(value='', visible=False, elem_classes=['studio-output-status'], sanitize_html=True)
                preview_state = gr.State(None)
                preview_transcript = gr.Textbox(visible=False)
                bind_busy_action(save,save_voice_display,[ref_s,transcript_s,xvec_s],[saved,save_status],'Save voice file','Saving voice...',1)
                voice.upload(select_uploaded_voice,[voice],[info],api_name='inspect_voice',queue=False)
                voice.clear(select_uploaded_voice,[voice],[info],api_name=False,queue=False)
                workflow_ticket = gr.State(0)
                button.click(workflow_stream_started, inputs=workflow, outputs=[button,generation_notice,generation_busy,workflow_ticket,audio],queue=False,api_name=False,
                    js="(workflow) => document.querySelector('#voice-mode-tabs button[aria-pressed=\"true\"]')?.dataset.voiceMode || workflow").then(
                    generate_workflow_stream,
                    [workflow,commentary_mode,clip_entries,workflow_ticket,ref_s,transcript_s,xvec_s,design_description,voice,text,instruction,language,seed,release,identity,*settings,batch_result],
                    [audio,download,status,preview_state,preview_transcript,preview_confirm,preview_actions,correction,preview_file,preview_status,use_correction,batch_result,batch_panel,batch_status,batch_zip,saved,save_status,batch_metadata],
                    api_name=False, concurrency_limit=1,concurrency_id='studio-generation',show_progress='full',
                    js="(...args) => { args[0] = document.querySelector('#voice-mode-tabs button[aria-pressed=\"true\"]')?.dataset.voiceMode || args[0]; args[1] = document.querySelector('#commentary-mode-tabs [role=\"tab\"][aria-selected=\"true\"]')?.textContent.trim() === 'Multiple' ? 'batch' : 'single'; return window.voxoverSeedRandomizer?.prepare(args) || args; }").then(
                    workflow_completed,inputs=[workflow,commentary_mode,clip_entries,voice,ref_s,transcript_s,xvec_s,design_description,text,*settings],
                    outputs=[button,generation_notice,generation_busy],queue=False,api_name=False).then(
                    batch_editor_metadata,inputs=batch_result,outputs=batch_metadata,queue=True,show_progress='hidden',api_name=False).then(
                    fn=None,js="() => window.voxoverGenerationGuard?.finish()",api_name=False)
                # Keep the established non-streaming API's inputs/output arity.
                api_generate_commentary = gr.Button(visible=False)
                api_generate_commentary.click(generate_workflow_ui,
                    [workflow,commentary_mode,clip_entries,workflow_ticket,ref_s,transcript_s,xvec_s,design_description,voice,text,instruction,language,seed,release,identity,*settings,batch_result],
                    [audio,download,status,preview_state,preview_transcript,preview_confirm,preview_actions,correction,preview_file,preview_status,use_correction,batch_result,batch_panel,batch_status,batch_zip,saved,save_status],
                    api_name='generate_commentary', concurrency_limit=1, concurrency_id='studio-generation',
                    js="(...args) => window.voxoverSeedRandomizer?.prepare(args) || args")
                regeneration_candidate = gr.State(None)
                # Commit must be queued: Gradio's direct /run responses omit
                # State.change notifications, so an unqueued commit leaves stale players.
                clip_entries.regenerate(regenerate_clip_ui,
                    [batch_result,clip_entries,workflow,commentary_mode,voice,instruction,language,seed,release,identity,*settings],
                    regeneration_candidate, concurrency_limit=1, concurrency_id='studio-generation', show_progress='hidden',api_name=False,
                    js="(...args) => { args[2] = 'generate'; args[3] = 'batch'; return args; }").then(
                    commit_clip_regeneration_ui,[regeneration_candidate,batch_result,clip_entries],
                    [batch_result,batch_status,batch_zip],queue=True,concurrency_limit=1,
                    concurrency_id='studio-generation',show_progress='hidden',api_name=False).then(
                    batch_editor_metadata,inputs=batch_result,outputs=batch_metadata,queue=True,show_progress='hidden',api_name=False).then(
                    fn=None,js="() => window.voxoverGenerationGuard?.finish()",api_name=False)
                gr.on(triggers=[workflow.change,voice.change,ref_s.change,transcript_s.change,xvec_s.change,design_description.change,text.change,clip_entries.change,commentary_mode.change,generation_busy.change]+[control.change for control in settings],
                    fn=update_workflow_readiness,inputs=[workflow,commentary_mode,clip_entries,voice,ref_s,transcript_s,xvec_s,design_description,text,generation_busy,*settings],outputs=button,queue=False,api_name=False)
                # Preserve the existing single-clip API for integrations.
                legacy_generate = gr.Button(visible=False)
                legacy_generate.click(generate_preview_atomic, [voice,text,instruction,language,seed,release,identity,*settings], [audio,download,status,preview_state,preview_transcript,preview_confirm,preview_actions,correction,preview_file,preview_status,use_correction], api_name='generate', concurrency_limit=1)
                play_all.click(fn=None,js="() => window.voxoverBatchPlayback?.play()",api_name=False)
                stop_all.click(fn=None,js="() => window.voxoverBatchPlayback?.stop()",api_name=False)
                clone_ticket=gr.State(0)
                clone_busy=bind_busy_action(direct_preview,None,[clone_ticket,ref_s,transcript_s,xvec_s,text,instruction,language,seed,release,*settings],
                    [audio,download,status,preview_state,preview_transcript,preview_confirm,saved,save_status,preview_actions,correction,preview_file,preview_status,use_correction,voice,info,batch_result,batch_panel],
                    'Clone reference & generate commentary','Cloning & generating...',2,
                    begin=begin_clone_selection,token=clone_ticket,adapter=clone_submission,finish_mode=commentary_mode,busy_state=clone_busy)
                commentary_mode.change(lambda mode,busy:gr.skip() if busy else gr.update(interactive=mode=='single',value=('Clone reference & generate commentary' if mode=='single' else 'Switch to Single commentary to clone')),[commentary_mode,clone_busy],direct_preview,api_name=False,queue=False)
                bind_busy_action(save_preview,save_preview_corrected,[preview_state,preview_confirm,correction,use_correction],[preview_file,preview_status],'Save audition as voice .pt','Saving voice...',1)
                gr.on(triggers=[preview_state.change,workflow.change,generation_busy.change], fn=design_download_visibility, inputs=[preview_state,workflow,generation_busy], outputs=design_download, queue=False, show_progress='hidden', api_name=False)
                design_download.click(save_designed_voice, inputs=[preview_state,workflow,preview_confirm,correction,use_correction], outputs=[design_file,design_save_status], api_name=False, concurrency_limit=1, trigger_mode='once').success(fn=None, js="() => { document.querySelector('#design-voice-file a[download]')?.click(); }", api_name=False)
                # Busy UI adapters use variadic signatures and extra UI-only outputs.
                # Keep the existing public API contracts attached to the original
                # typed callbacks so named clients and return tuple arity stay valid.
                legacy_save = gr.Button(visible=False)
                legacy_save.click(save_voice_display,[ref_s,transcript_s,xvec_s],[saved,save_status],api_name='save_voice',concurrency_limit=1)
                legacy_clone = gr.Button(visible=False)
                legacy_clone.click(clone_reference_selected,[clone_ticket,ref_s,transcript_s,xvec_s,text,instruction,language,seed,release,*settings],[audio,download,status,preview_state,preview_transcript,preview_confirm,saved,save_status,preview_actions,correction,preview_file,preview_status,use_correction,voice,info],api_name='clone_reference_preview',concurrency_limit=1)
                legacy_save_preview = gr.Button(visible=False)
                legacy_save_preview.click(save_preview_corrected,[preview_state,preview_confirm,correction,use_correction],[preview_file,preview_status],api_name='save_preview_voice',concurrency_limit=1)
        with gr.Accordion('General settings & model information', open=False, elem_classes=['generation-settings','studio-help','general-settings']):
            gr.Textbox(label='Clone / Generate model',value='Qwen3-TTS-12Hz-1.7B-Base',interactive=False)
            gr.Textbox(label='Design model',value='Qwen3-TTS-12Hz-1.7B-VoiceDesign',interactive=False)
            gr.Textbox(label='Base checkpoint cache',value=str(MODEL_REPO),interactive=False)
            gr.Textbox(label='VoiceDesign checkpoint cache',value=str(DESIGN_MODEL_REPO),interactive=False)
            gr.Markdown('Output directory',elem_classes=['storage-field-label'])
            output_folder=gr.Button(str(OUTPUTS),elem_classes=['storage-folder-button'])
            gr.Markdown('Saved voice directory',elem_classes=['storage-field-label'])
            voice_folder=gr.Button(str(VOICES),elem_classes=['storage-folder-button'])
            storage_status=gr.Markdown('',elem_classes=['studio-output-status'])

            gr.Markdown('Commentary, language, and generation settings are shared across Clone, Design, and Generate. GPU memory release and the random seed are inside Generation settings. Click a storage directory to browse local folders and choose its replacement. Choices persist after restart and affect future saves only; existing files are never moved. Checkpoint paths stay read-only. Switching between Base and VoiceDesign releases the previous model first.')
        with gr.Accordion('Storage & GPU help', open=False, elem_classes=['generation-settings','studio-help']):
            gr.Markdown('**Compare delivery:** try an empty instruction, then the same text and seed with a direction.\n\n**Local storage:** audio and settings are in `Outputs`; saved voices are in `Voices`.\n\n**GPU memory:** stop other Qwen servers before generating. Closing their tabs does not unload models.')
        with gr.Accordion('Use via API', open=False, elem_classes=['generation-settings','studio-help','studio-utility-section'], elem_id='inline-api-section') as api_section:
            gr.HTML('<div id="inline-api-host" class="studio-utility-host"></div>')
        with gr.Accordion('Settings', open=False, elem_classes=['generation-settings','studio-help','studio-utility-section'], elem_id='inline-settings-section') as settings_section:
            gr.HTML('<div id="inline-settings-host" class="studio-utility-host"></div>')
        api_section.expand(fn=None,js="() => window.voxoverUtilities?.open('api')",api_name=False)
        api_section.collapse(fn=None,js="() => window.voxoverUtilities?.close('api')",api_name=False)
        settings_section.expand(fn=None,js="() => window.voxoverUtilities?.open('settings')",api_name=False)
        settings_section.collapse(fn=None,js="() => window.voxoverUtilities?.close('settings')",api_name=False)
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
            folder_note=gr.Markdown('',elem_classes=['studio-output-status'])
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
        bind_busy_action(confirm,None,[folder_kind,folder_path],[output_folder,voice_folder,storage_status,folder_dialog,folder_note],'Use this folder','Saving folder...',4,adapter=commit_storage_submission)
        cancel_folder.click(lambda:gr.update(visible=False),outputs=folder_dialog,api_name=False,queue=False)
        app.load(fn=None, js=ui_asset_text('seed-randomizer.js').replace('// SEED_HELPERS', ui_asset_text('clip-seeds.js')))
        app.load(fn=None, js=ui_asset_text('number-wheel.js'))
        app.load(fn=None, js=ui_asset_text('generation-guard.js'))
        app.load(fn=None, js=ui_asset_text('clip-loading.js'))
        app.load(fn=None, js=ui_asset_text('clip-alignment.js'))
        app.load(fn=None, js=ui_asset_text('night-sky.js'))
        app.load(fn=None, js=ui_asset_text('batch-playback.js'))
        app.load(fn=None, js=ui_asset_text('commentary-tabs.js'))
        app.load(fn=None, js=ui_asset_text('operation-feedback.js'))
        app.load(fn=None, js=ui_asset_text('generation-readiness.js'))
        app.load(fn=None, js=ui_asset_text('inline-utilities.js'))
    return app

if __name__ == '__main__':
    build_ui().queue(default_concurrency_limit=1).launch(server_name='127.0.0.1', server_port=int(app_setting('PORT', '8003')), share=False, inbrowser=False, show_error=True, favicon_path=str(ROOT/'assets'/'app-icon'/'voxover.ico'), css=ui_asset_text('theme.css'), allowed_paths=[str(ROOT/'assets')], footer_links=["api", "settings"])
