"""Mocked app integration tests. Never loads a real voice or model."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import app


class BatchIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.wav = self.folder / 'synthetic.wav'
        self.wav.write_bytes(b'RIFFsynthetic')
        self.rows = [dict(id='one', minutes=0, seconds=4, text='One.'),
                     dict(id='two', minutes=1, seconds=9, text='Two.')]
        self.args = ('voice.pt', 'single text', 'Calm.', 'English', 123, True, False)

    def call(self, mode='batch', rows=None, **changes):
        args = list(self.args)
        for index, value in changes.items(): args[int(index)] = value
        return app.generate_commentary_mode(mode, self.rows if rows is None else rows, *args, *app.SETTING_DEFAULTS)

    def test_shared_settings_and_final_release(self):
        with patch.object(app, 'read_voice'), patch.object(app, 'OUTPUTS', self.folder/'outputs'), \
             patch.object(app, 'generate', return_value=(str(self.wav),str(self.wav),'ok')) as generate, \
             patch.object(app, 'release_model') as release, patch.object(app,'authorize_generated_file') as authorize:
            result = self.call()
        self.assertEqual(len(result), 15)
        self.assertEqual(generate.call_count, 2)
        for call, text in zip(generate.call_args_list, ['One.', 'Two.']):
            self.assertEqual(call.args, ('voice.pt',text,'Calm.','English',123,False,False,*app.SETTING_DEFAULTS))
        release.assert_called_once_with()
        batch = result[11]
        self.assertEqual(len(batch['clips']), 2)
        self.assertEqual({str(c.args[0]) for c in authorize.call_args_list},
                         {c['audio'] for c in batch['clips']} | {batch['archive']})
        self.assertTrue(result[12]['visible'])
        self.assertEqual(result[14]['value'], batch['archive'])
        self.assertIsNone(result[3])  # no batch falsely becomes a single voice preview
        self.assertFalse(result[6]['visible'])

    def test_single_compatibility_clears_batch_outputs(self):
        original = tuple(range(11))
        with patch.object(app,'generate_preview_atomic',return_value=original) as single, \
             patch.object(app,'generate') as generate, patch.object(app,'release_model') as release:
            result = self.call('single')
        self.assertEqual(result[0]['value'],original[0])
        self.assertEqual(result[1]['value'],original[1])
        self.assertTrue(result[0]['visible'])
        self.assertEqual(result[2:11], original[2:])
        single.assert_called_once_with(*self.args,*app.SETTING_DEFAULTS)
        generate.assert_not_called(); release.assert_not_called()
        self.assertIsNone(result[11]); self.assertFalse(result[12]['visible'])
        self.assertFalse(result[14]['visible'])

    def test_invalid_rows_do_not_generate_or_release(self):
        with patch.object(app,'read_voice'), patch.object(app,'generate') as generate, \
             patch.object(app,'release_model') as release:
            with self.assertRaises(ValueError): self.call(rows=[[0,60,'Bad']])
        generate.assert_not_called(); release.assert_not_called()

    def test_partial_batch_is_authorized_and_kept(self):
        with patch.object(app,'read_voice'), patch.object(app,'OUTPUTS',self.folder/'outputs'), \
             patch.object(app,'generate',side_effect=[(str(self.wav),'',''),RuntimeError('synthetic failure')]), \
             patch.object(app,'release_model') as release, patch.object(app,'authorize_generated_file') as authorize:
            result = self.call()
        self.assertEqual(len(result[11]['clips']),1)
        self.assertIn('Generated 1 of 2',result[13])
        self.assertIn('synthetic failure',result[13])
        self.assertEqual(authorize.call_count,2)
        release.assert_called_once_with()

    def test_generation_error_does_not_publish_nonexistent_artifacts(self):
        with patch.object(app,'read_voice'), patch.object(app,'OUTPUTS',self.folder/'outputs'), \
             patch.object(app,'generate',side_effect=RuntimeError('synthetic failure')), \
             patch.object(app,'release_model') as release, patch.object(app,'authorize_generated_file') as authorize:
            result = self.call()
        self.assertEqual(result[11]['clips'],[])
        self.assertFalse(result[14]['visible'])
        authorize.assert_not_called(); release.assert_called_once_with()

    def test_ui_retains_legacy_and_new_api(self):
        with patch.object(app,'load_model') as load:
            cfg = app.build_ui().get_config_file()
        apis = [d.get('api_name') for d in cfg['dependencies']]
        self.assertIn('generate',apis)
        self.assertIn('generate_commentary',apis)
        load.assert_not_called()


if __name__ == '__main__': unittest.main()
