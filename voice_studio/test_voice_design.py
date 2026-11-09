"""VoiceDesign wiring and preview safety regressions."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import soundfile as sf
import torch
import app


class VoiceDesignTests(unittest.TestCase):
    def test_reference_gui_and_cli_parity(self):
        from qwen_tts.cli.demo import build_demo, build_parser
        upstream_model = SimpleNamespace(
            tts_model_type='voice_design',
            get_supported_languages=lambda: [language.lower() for language in app.LANGUAGES],
            get_supported_speakers=lambda: [],
        )
        reference = build_demo(SimpleNamespace(model=upstream_model), 'local VoiceDesign', {}).get_config_file()
        ref_controls = [c for c in reference['components'] if c['type'] in ('textbox', 'dropdown', 'button', 'audio')]
        self.assertEqual([c['type'] for c in ref_controls], ['textbox', 'dropdown', 'textbox', 'button', 'audio', 'textbox'])
        ref_text, ref_language, ref_instruction = ref_controls[:3]
        studio = app.build_ui().get_config_file()
        components = {c['id']: c for c in studio['components']}
        design = next(d for d in studio['dependencies'] if d.get('api_name') == 'generate_commentary')
        labels = [components[i]['props'].get('label') for i in design['inputs']]
        instruction = components[design['inputs'][labels.index('Voice design instruction')]]['props']
        language = components[design['inputs'][labels.index('Language')]]['props']
        self.assertIn('Commentary text', labels)
        self.assertNotIn('Preview text', labels)
        self.assertEqual(instruction['value'], '')
        self.assertEqual(instruction['placeholder'], ref_instruction['props']['value'])
        self.assertEqual(language['value'], 'English')
        self.assertEqual({choice[1] for choice in language['choices']}, {choice[1] for choice in ref_language['props']['choices']})
        self.assertEqual({action.dest for action in build_parser()._actions if action.dest in app.SETTING_NAMES},
                         set(app.SETTING_NAMES) - {'do_sample', 'subtalker_dosample'})

    def test_cached_design_defaults(self):
        revision_file = app.DESIGN_MODEL_REPO/'refs'/'main'
        if not revision_file.is_file():
            self.skipTest('VoiceDesign checkpoint is not cached')
        config_file = app.DESIGN_MODEL_REPO/'snapshots'/revision_file.read_text().strip()/'generation_config.json'
        self.assertEqual(app.generation_options([]), json.loads(config_file.read_text()))

    def test_design_forwards_public_api_and_sampling(self):
        fake = MagicMock()
        fake.generate_voice_design.return_value = ([np.zeros(2400, dtype=np.float32)], 24000)
        settings = list(app.SETTING_DEFAULTS)
        settings[1] = 1.2
        settings[5] = False
        with tempfile.TemporaryDirectory() as folder, patch.object(app, 'OUTPUTS', Path(folder)), patch.object(app, 'load_model', return_value=fake) as load, patch.object(app, 'release_model') as release:
            wav, download, _ = app.generate_design('  Hello.  ', '  A warm baritone.  ', 'English', 19, True, *settings)
            self.assertEqual(wav, download)
            self.assertTrue(Path(wav).is_file())
            load.assert_called_once_with('voice_design')
            release.assert_called_once_with()
            kwargs = fake.generate_voice_design.call_args.kwargs
            self.assertEqual(kwargs, dict(text='Hello.', language='English', instruct='A warm baritone.', **app.generation_options(settings)))
            self.assertEqual(json.loads(Path(wav).with_suffix('.json').read_text())['mode'], 'voice_design')

    def test_validation_precedes_model_load_and_busy_is_rejected(self):
        with patch.object(app, 'load_model') as load, patch.object(app, 'release_model'):
            for text, design, language in [('', 'voice', 'English'), ('Hi', '', 'English'), ('Hi', 'voice', 'invalid')]:
                with self.assertRaises(Exception):
                    app.generate_design(text, design, language, 42, True)
            settings = list(app.SETTING_DEFAULTS); settings[3] = 2
            with self.assertRaises(Exception):
                app.generate_design('Hi', 'voice', 'English', 42, True, *settings)
            load.assert_not_called()
        held, free = threading.Event(), threading.Event()
        def occupy():
            with app.LOCK:
                held.set(); free.wait(2)
        worker = threading.Thread(target=occupy); worker.start(); self.assertTrue(held.wait(1))
        try:
            with self.assertRaisesRegex(Exception, 'operation is running'):
                app.generate_design('Hi', 'voice', 'English', 42, True)
        finally:
            free.set(); worker.join(2)

    def test_model_switch_releases_previous_and_checks_kind(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder)/'design'; (repo/'refs').mkdir(parents=True)
            (repo/'refs'/'main').write_text('revision')
            (repo/'snapshots'/'revision').mkdir(parents=True)
            (repo/'snapshots'/'revision'/'config.json').write_text('{}')
            design = SimpleNamespace(model=SimpleNamespace(tts_model_type='voice_design'))
            old = object()
            with patch.object(app, 'DESIGN_MODEL_REPO', repo), patch.object(app, '_model', old), patch.object(app, '_model_kind', 'base'), patch.object(app.torch.cuda, 'is_available', return_value=True), patch.object(app.torch.cuda, 'mem_get_info', return_value=(8*1024**3, 12*1024**3)), patch.object(app.Qwen3TTSModel, 'from_pretrained', return_value=design) as factory:
                self.assertIs(app.load_model('voice_design'), design)
                self.assertEqual(app._model_kind, 'voice_design')
                self.assertIs(app.load_model('voice_design'), design)
                factory.assert_called_once()
                self.assertEqual(factory.call_args.kwargs['local_files_only'], True)
                self.assertEqual(factory.call_args.kwargs['attn_implementation'], None)
                app.release_model()
                self.assertIsNone(app._model_kind)
            with patch.object(app, 'DESIGN_MODEL_REPO', repo), patch.object(app.torch.cuda, 'is_available', return_value=True), patch.object(app.torch.cuda, 'mem_get_info', return_value=(8*1024**3, 12*1024**3)), patch.object(app.Qwen3TTSModel, 'from_pretrained', return_value=SimpleNamespace(model=SimpleNamespace(tts_model_type='base'))):
                with self.assertRaisesRegex(RuntimeError, 'Expected voice_design'):
                    app.load_model('voice_design')
                self.assertIsNone(app._model)

    def test_design_preview_saves_without_confirmation(self):
        with tempfile.TemporaryDirectory() as folder:
            wav = Path(folder)/'take.wav'; wav.write_bytes(b'preview')
            with patch.object(app, 'generate_design', return_value=(str(wav), str(wav), 'ok')):
                result = app.generate_design_preview('  Hello. ', 'voice', 'English', 42, True)
            self.assertEqual(result[3]['transcript'], 'Hello.')
            self.assertFalse(result[5])
            with patch.object(app, 'save_voice', return_value=('voice.pt', 'ok')) as save:
                with patch.object(app, 'OUTPUTS', Path(folder)):
                    path, _ = app.save_preview_voice(result[3], False)
                self.assertEqual(path, 'voice.pt')
                save.assert_called_once_with(str(wav.resolve()), 'Hello.', False)

    def test_failed_design_clears_stale_preview(self):
        with patch.object(app, 'generate_design_preview', side_effect=RuntimeError('model unavailable')):
            result = app.design_submission('Hello', 'voice', 'English', 42, True)
        self.assertEqual(len(result), 11)
        self.assertIn('model unavailable', result[2])
        self.assertIsNone(result[3])
        self.assertFalse(result[5])
        self.assertFalse(result[6]['visible'])

    def test_successful_design_exposes_save_controls(self):
        state = {'audio': 'preview.wav', 'sha256': 'hash', 'transcript': 'Hello.'}
        with patch.object(app, 'generate_design_preview', return_value=('preview.wav', 'preview.wav', 'ok', state, 'Hello.', False)):
            result = app.design_submission('Hello.', 'voice', 'English', 42, True)
        self.assertEqual(len(result), 11)
        self.assertEqual(result[3], state)
        self.assertTrue(result[6]['visible'])
        self.assertFalse(result[5])

    def test_design_ui_has_all_inputs_and_shared_preview_state(self):
        cfg = app.build_ui().get_config_file()
        components = {c['id']: c for c in cfg['components']}
        design = next(d for d in cfg['dependencies'] if d.get('api_name') == 'generate_commentary')
        labels = [components[i]['props'].get('label') for i in design['inputs']]
        self.assertEqual(labels[:15], ['Workflow mode',None,None,None,'Reference audio','Reference transcript','Include reference transcript','Voice design instruction','Voice file (.pt)','Commentary text','Delivery instruction (optional)','Language','Seed','Release GPU memory after generation','Use voice identity only'])
        self.assertEqual(labels[15:], ['Maximum new tokens','Temperature','Top-k','Top-p','Repetition penalty','Enable speech sampling','Subtalker temperature','Subtalker top-k','Subtalker top-p','Enable subtalker sampling'])
        self.assertEqual(len(design['outputs']), 19)
        self.assertTrue(any(c['props'].get('elem_id') == 'design-inputs' for c in cfg['components']))
        self.assertEqual(sum(label == 'Preview text' for label in labels), 0)
        self.assertEqual(sum(label == 'Voice design instruction' for label in labels), 1)
        self.assertEqual(sum(label == 'Commentary text' for label in labels), 1)
        self.assertEqual(sum(label == 'Maximum new tokens' for label in labels), 1)
        self.assertEqual(components[design['inputs'][7]]['props']['value'], '')
        self.assertIn('incredulous tone', components[design['inputs'][7]]['props']['placeholder'])
        self.assertEqual({choice[1] for choice in components[design['inputs'][11]]['props']['choices']}, set(app.LANGUAGES))

    def test_shared_workflow_readiness(self):
        rows = [{'minutes': 0, 'seconds': 1, 'text': 'First line'}]
        def ready(workflow, mode='single', *, voice=None, ref=None, transcript='', include=True,
                  description='', text='Shared commentary'):
            return app.workflow_ready(workflow, mode, rows, voice, ref, transcript, include,
                                      description, text, False, *app.SETTING_DEFAULTS)
        self.assertTrue(ready('design', description='Warm voice'))
        self.assertTrue(ready('design', 'batch', description='Warm voice'))
        self.assertFalse(ready('design'))
        self.assertTrue(ready('clone', ref='reference.wav', transcript='Spoken reference'))
        self.assertTrue(ready('clone', 'batch', ref='reference.wav', include=False))
        self.assertFalse(ready('clone', ref='reference.wav'))
        self.assertTrue(ready('generate', voice='saved.pt'))
        self.assertFalse(ready('generate'))

    def test_design_placeholder_cannot_be_submitted(self):
        with patch.object(app, 'load_model') as load:
            with self.assertRaisesRegex(ValueError, 'Describe the voice'):
                app.generate_workflow_mode('design', 'single', None, 0, None, '', True,
                    '', None, 'Actual commentary', '', 'English', 42, True, False,
                    *app.SETTING_DEFAULTS)
            load.assert_not_called()

    def test_design_single_uses_shared_composer_values(self):
        state = {'audio': 'preview.wav', 'sha256': 'hash', 'transcript': 'Shared commentary'}
        with patch.object(app, 'generate_design_preview', return_value=('preview.wav', 'preview.wav',
                'ok', state, 'Shared commentary', False)) as design:
            result = app.generate_workflow_mode('design', 'single', None, 0, None, '', True,
                'Warm voice', None, 'Shared commentary', 'Ignored Base direction', 'Japanese', 7,
                True, False, *app.SETTING_DEFAULTS)
        design.assert_called_once_with('Shared commentary', 'Warm voice', 'Japanese', 7, True,
                                       *app.SETTING_DEFAULTS)
        self.assertEqual(len(result), 19)
        self.assertEqual(result[3], state)
        self.assertTrue(result[6]['visible'])

    def test_design_ignores_timed_draft_and_auditions_single_text(self):
        rows=[{'minutes':0,'seconds':1,'text':'Do not synthesize this'}]
        state={'audio':'a.wav','sha256':'hash','transcript':'Single sample'}
        with patch.object(app,'generate_design_preview',return_value=('a.wav','a.wav','ok',state,'Single sample',False)) as design,patch.object(app,'save_voice') as save:
            result=app.generate_workflow_mode('design','batch',rows,0,None,'',True,'Warm voice',None,'Single sample','','English',11,True,False,*app.SETTING_DEFAULTS)
        design.assert_called_once_with('Single sample','Warm voice','English',11,True,*app.SETTING_DEFAULTS)
        save.assert_not_called();self.assertIsNone(result[11]);self.assertEqual(result[3],state)

    def test_clone_ignores_timed_draft_and_does_not_auto_save(self):
        rows=[{'minutes':0,'seconds':1,'text':'Do not synthesize this'}]
        state={'audio':'a.wav','sha256':'hash','transcript':'Reference','source':'clone_reference'}
        with patch.object(app,'clone_audition',return_value=('a.wav','a.wav','ok',state,'Reference',False)) as clone,patch.object(app,'save_voice') as save:
            result=app.generate_workflow_mode('clone','batch',rows,0,'ref.wav','Reference',True,'',None,'Single sample','Calm','English',11,True,False,*app.SETTING_DEFAULTS)
        clone.assert_called_once_with('ref.wav','Reference',True,'Single sample','Calm','English',11,True,*app.SETTING_DEFAULTS)
        save.assert_not_called();self.assertIsNone(result[11]);self.assertEqual(result[3],state)

    def test_clone_decodes_local_wav_without_slow_path_loader(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'source.wav'
            sf.write(source, np.zeros((2400, 2), dtype=np.float32), 24000)
            prompt = app.VoiceClonePromptItem(ref_code=None, ref_spk_embedding=torch.zeros(8),
                x_vector_only_mode=True, icl_mode=False, ref_text=None)
            fake = MagicMock()
            fake.create_voice_clone_prompt.return_value = [prompt]
            with patch.object(app, 'VOICES', Path(folder)/'voices'), \
                 patch.object(app, 'load_model', return_value=fake), \
                 patch.object(app, 'release_model'), patch.object(app, 'read_voice'):
                path, _ = app.save_voice(str(source), '', True)
            self.assertTrue(Path(path).is_file())
            ref_audio = fake.create_voice_clone_prompt.call_args.kwargs['ref_audio']
            self.assertIsInstance(ref_audio, tuple)
            self.assertEqual(ref_audio[0].shape, (2400,))
            self.assertEqual(ref_audio[1], 24000)

    def test_clone_audition_failure_honors_model_release(self):
        with patch.object(app,'load_model',side_effect=RuntimeError('bad reference')),patch.object(app,'release_model') as release:
            with self.assertRaisesRegex(Exception,'bad reference'):
                app.generate_workflow_mode('clone','batch',[],0,'reference.wav','',False,'',None,'Sample','','English',42,True,False,*app.SETTING_DEFAULTS)
        release.assert_called_once()

if __name__ == '__main__':
    unittest.main()
