"""Download controls must follow saved artifacts, not unrelated generation state."""
import unittest
import hashlib
import tempfile
import threading
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch
import numpy as np
import soundfile as sf
import torch
import app
from test_fixture import TEST_VOICE

class VoiceDownloadTests(unittest.TestCase):
    def test_download_waits_for_generation_then_saves_the_requested_audition(self):
        """An enabled download must wait, not fail at the model's busy lock."""
        item = app.read_voice(TEST_VOICE)
        class Encoder:
            def create_voice_clone_prompt(self, ref_audio, ref_text, x_vector_only_mode):
                return [replace(item, ref_text=ref_text)]
        for source in ('design_sample', 'clone_reference'):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                wav = root / 'audition.wav'
                sf.write(wav, np.zeros(2400, dtype=np.float32), 24000)
                preview = {'audio': str(wav), 'sha256': hashlib.sha256(wav.read_bytes()).hexdigest(),
                           'source': source, 'transcript': 'Original audition words',
                           'prompt': asdict(item), 'identity_only': False}
                started, finished = threading.Event(), threading.Event()
                results, errors = [], []
                def save():
                    started.set()
                    try:
                        if source == 'design_sample':
                            # The visual mode tabs may be ahead of Gradio's hidden
                            # workflow textbox. The audition's source is authoritative.
                            results.append(app.save_designed_voice(preview, 'clone', False, 'Corrected audition words', True))
                        else:
                            results.append(app.save_preview_corrected(preview, False, 'Corrected audition words', True))
                    except Exception as error:
                        errors.append(error)
                    finally:
                        finished.set()
                with patch.object(app, 'OUTPUTS', root), patch.object(app, 'VOICES', root / 'voices'), \
                     patch.object(app, 'load_model', return_value=Encoder()), patch.object(app, 'release_model'):
                    with app.LOCK:
                        worker = threading.Thread(target=save)
                        worker.start()
                        self.assertTrue(started.wait(2))
                        completed_while_busy = finished.wait(0.1)
                        self.assertFalse((root / 'voices').exists())
                    worker.join(5)
                    self.assertFalse(worker.is_alive(), 'Save must complete once generation releases its lock')
                    self.assertFalse(completed_while_busy, f'Download failed instead of waiting: {errors}')
                    self.assertEqual(errors, [])
                    saved = torch.load(results[0][0]['value'], weights_only=True, map_location='cpu')
                    self.assertEqual(saved['items'][0]['ref_text'], 'Corrected audition words')
                    self.assertEqual(preview['transcript'], 'Original audition words')
                    self.assertEqual(len(list((root / 'voices').glob('*.pt'))), 1)

    def test_existing_design_remains_downloadable_while_generating(self):
        preview = {'source': 'design_sample', 'audio': 'sample.wav'}
        result = app.design_download_visibility(preview, 'design', True)
        self.assertTrue(result['visible'])
        self.assertTrue(result['interactive'])

    def test_design_download_does_not_depend_on_stale_hidden_workflow(self):
        result = app.design_download_visibility({'source': 'design_sample'}, 'clone', False)
        self.assertTrue(result['visible'])
        self.assertTrue(result['interactive'])

    def test_generation_completion_refreshes_design_download(self):
        ui = app.build_ui()
        cfg = ui.get_config_file()
        completed = {index for index, fn in ui.fns.items() if fn.fn is app.workflow_completed}
        refreshes = [d for d in cfg['dependencies'] if d.get('trigger_after') in completed
                     and ui.fns[d['id']].fn is app.design_download_visibility]
        self.assertTrue(refreshes, 'Streaming completion must explicitly refresh Design Download')

    def test_no_download_without_a_design_sample(self):
        for preview, workflow in [(None, 'design'), ({'source': 'clone_reference'}, 'design')]:
            self.assertFalse(app.design_download_visibility(preview, workflow, False)['visible'])

    def test_both_voice_files_trigger_download_from_the_returned_file(self):
        config = app.build_ui().get_config_file()
        for label in ['Designed voice (.pt)', 'New preview voice (.pt)']:
            component = next(c for c in config['components'] if c['props'].get('label') == label)
            downloads = [d for d in config['dependencies']
                         if (component['id'], 'change') in [tuple(target) for target in d['targets']] and d.get('js')]
            self.assertEqual(len(downloads), 1, label + ' must start a download on successful save')
            self.assertEqual(downloads[0]['inputs'], [component['id']])

if __name__ == '__main__':
    unittest.main()
