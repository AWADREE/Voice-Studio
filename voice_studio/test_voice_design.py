"""VoiceDesign wiring and preview safety regressions."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
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
        design = next(d for d in studio['dependencies'] if d.get('api_name') is False and any(components[i]['props'].get('label') == 'Voice design instruction' for i in d['inputs']))
        text, instruction, language = (components[i]['props'] for i in design['inputs'][:3])
        self.assertEqual(text['value'], ref_text['props']['value'])
        self.assertEqual(instruction['value'], ref_instruction['props']['value'])
        self.assertEqual(language['value'], ref_language['props']['value'])
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

    def test_design_preview_uses_existing_confirmation_flow(self):
        with tempfile.TemporaryDirectory() as folder:
            wav = Path(folder)/'take.wav'; wav.write_bytes(b'preview')
            with patch.object(app, 'generate_design', return_value=(str(wav), str(wav), 'ok')):
                result = app.generate_design_preview('  Hello. ', 'voice', 'English', 42, True)
            self.assertEqual(result[3]['transcript'], 'Hello.')
            self.assertFalse(result[5])
            with patch.object(app, 'save_voice', return_value=('voice.pt', 'ok')) as save:
                with patch.object(app, 'OUTPUTS', Path(folder)):
                    path, _ = app.save_preview_voice(result[3], True)
                self.assertEqual(path, 'voice.pt')
                save.assert_called_once_with(str(wav.resolve()), 'Hello.', False)
            with self.assertRaises(Exception):
                app.save_preview_voice(result[3], False)

    def test_failed_design_clears_stale_preview(self):
        with patch.object(app, 'generate_design_preview', side_effect=RuntimeError('model unavailable')):
            result = app.design_submission('Hello', 'voice', 'English', 42, True)
        self.assertEqual(len(result), 11)
        self.assertIn('model unavailable', result[2])
        self.assertIsNone(result[3])
        self.assertFalse(result[5])
        self.assertFalse(result[6]['visible'])

    def test_successful_design_exposes_confirmation_controls(self):
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
        design = next(d for d in cfg['dependencies'] if d.get('api_name') is False and any(components[i]['props'].get('label') == 'Voice design instruction' for i in d['inputs']))
        labels = [components[i]['props'].get('label') for i in design['inputs']]
        self.assertEqual(labels[:5], ['Preview text', 'Voice design instruction', 'Language', 'Seed', 'Release GPU memory after generation'])
        self.assertEqual(labels[5:], ['Maximum new tokens','Temperature','Top-k','Top-p','Repetition penalty','Enable speech sampling','Subtalker temperature','Subtalker top-k','Subtalker top-p','Enable subtalker sampling'])
        self.assertEqual(len(design['outputs']), 11)
        self.assertTrue(any(c['props'].get('elem_id') == 'design-inputs' for c in cfg['components']))
        self.assertIn('top drawer', components[design['inputs'][0]]['props']['value'])
        self.assertIn('incredulous tone', components[design['inputs'][1]]['props']['value'])
        self.assertEqual(components[design['inputs'][2]]['props']['value'], 'Auto')
        self.assertEqual({choice[1] for choice in components[design['inputs'][2]]['props']['choices']}, set(app.LANGUAGES))


if __name__ == '__main__':
    unittest.main()
