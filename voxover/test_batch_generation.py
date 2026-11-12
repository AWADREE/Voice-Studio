import json
from pathlib import Path
import tempfile
import threading
import unittest
import zipfile
from unittest.mock import Mock, patch

from batch_generation import run_batch, validate_entries


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.wav = self.root / 'original.wav'
        self.wav.write_bytes(b'RIFFtest-audio')
        self.lock = threading.RLock()
        self.release = Mock()
        self.generate = Mock(return_value=str(self.wav))

    def run_rows(self, rows=None, **kwargs):
        return run_batch(rows or [[0, 5, 'First.'], [1, 12, 'Second.']],
                         generate_clip=kwargs.pop('generate_clip', self.generate),
                         output_root=self.root/'out', lock=self.lock,
                         release_model=self.release, **kwargs)

    def test_order_duplicates_names_manifest_and_no_source_mutation(self):
        result = self.run_rows([[1, 2, 'One.'], [1, 2, 'Two.'], [0, 3, 'Three.']])
        self.assertIsNone(result['error'])
        self.assertEqual([c['filename'] for c in result['clips']],
                         ['01m02s-001.wav', '01m02s-002.wav', '00m03s-003.wav'])
        self.assertEqual([c.args for c in self.generate.call_args_list], [('One.',0),('Two.',1),('Three.',2)])
        self.release.assert_called_once_with()
        self.assertEqual(self.wav.read_bytes(), b'RIFFtest-audio')
        with zipfile.ZipFile(result['archive']) as z:
            manifest = json.loads(z.read('manifest.json'))
            self.assertNotIn(str(self.root), json.dumps(manifest))
            self.assertEqual(len(z.namelist()), 4)
            self.assertTrue(manifest['complete'])

    def test_validate_all_before_generation(self):
        with self.assertRaises(ValueError):
            self.run_rows([[0,0,'Good'], [0,60,'Bad']])
        self.generate.assert_not_called()
        self.release.assert_not_called()

    def test_validation(self):
        for rows in ([], None, [[0,0,'']]*101, [[0,0,' ']], [[0,0,'x'*2001]],
                     [[-1,0,'x']], [[0,60,'x']], [[float('nan'),0,'x']],
                     [[0,float('inf'),'x']], [[True,0,'x']], [[0,0,None]], [['x',0,'x']]):
            with self.subTest(rows=repr(rows)[:60]), self.assertRaises(ValueError):
                validate_entries(rows)
        self.assertEqual(validate_entries([{'minutes':'2','seconds':'3','text':' hi '}])[0]['text'], 'hi')

    def test_fractional_timestamp_labels_and_filenames(self):
        self.assertEqual(validate_entries([[0,0.5,'x']])[0]['seconds'], 0.5)
        result = self.run_rows([[1,2.125,'One.']])
        self.assertIsNone(result['error'])
        self.assertEqual(result['clips'][0]['label'], '01:02.125')
        self.assertEqual(result['clips'][0]['filename'], '01m02.125s-001.wav')

    def test_partial_failure_keeps_completed_and_releases_once(self):
        self.generate.side_effect = [str(self.wav), RuntimeError('Out of memory'), str(self.wav)]
        result = self.run_rows([[0,0,'One'],[1,0,'Two'],[2,0,'Three']])
        self.assertEqual(len(result['clips']), 1)
        self.assertEqual(self.generate.call_count, 2)
        self.assertIn('Clip 2', result['error'])
        self.assertTrue(Path(result['archive']).is_file())
        self.release.assert_called_once_with()

    def test_first_failure_no_archive(self):
        self.generate.side_effect = RuntimeError('failed')
        result = self.run_rows()
        self.assertEqual(result['clips'], [])
        self.assertIsNone(result['archive'])
        self.release.assert_called_once_with()

    def test_release_false(self):
        self.run_rows(release_after=False)
        self.release.assert_not_called()

    def test_distinct_batch_directories(self):
        a, b = self.run_rows(), self.run_rows()
        self.assertNotEqual(a['batch_dir'], b['batch_dir'])
        self.assertTrue(Path(a['archive']).exists())

    def test_lock_held_across_generation(self):
        observed = []
        def generate(text, index):
            def other_thread():
                acquired = self.lock.acquire(blocking=False)
                observed.append(acquired)
                if acquired:
                    self.lock.release()
            t = threading.Thread(target=other_thread)
            t.start(); t.join()
            return str(self.wav)
        self.run_rows(generate_clip=generate)
        self.assertEqual(observed, [False, False])

    def test_concurrent_request_does_not_unload(self):
        ready, done = threading.Event(), threading.Event()
        def hold():
            with self.lock:
                ready.set(); done.wait(5)
        t = threading.Thread(target=hold); t.start(); ready.wait(5)
        try:
            with self.assertRaises(RuntimeError): self.run_rows()
        finally:
            done.set(); t.join()
        self.release.assert_not_called()
        self.generate.assert_not_called()

    def test_release_failure_unlocks(self):
        self.release.side_effect = RuntimeError('release failure')
        result = self.run_rows()
        self.assertIn('release failure', result['error'])
        self.assertTrue(self.lock.acquire(False)); self.lock.release()

    def test_invalid_audio_stops(self):
        self.generate.return_value = str(self.root/'missing.wav')
        result = self.run_rows()
        self.assertIn('usable WAV', result['error'])
        self.release.assert_called_once_with()

    def test_archive_failure_preserves_clips(self):
        with patch('batch_generation.zipfile.ZipFile', side_effect=OSError('disk full')):
            result = self.run_rows()
        self.assertEqual(len(result['clips']), 2)
        self.assertTrue(all(Path(c['audio']).is_file() for c in result['clips']))
        self.assertIn('archive unavailable', result['error'])


if __name__ == '__main__': unittest.main()
