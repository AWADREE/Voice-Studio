"""Incremental batches publish immutable results before later inference finishes."""
import copy
import inspect
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import app
from batch_generation import run_batch

class StreamingBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.wav = self.root / 'synthetic.wav'
        app.sf.write(self.wav, app.np.zeros(2400), 24000)
        self.rows = [dict(id='one', minutes=0, seconds=1, text='One.', seed=10),
                     dict(id='two', minutes=0, seconds=6, text='Two.', seed=20)]

    def args(self, previous=None):
        return ('generate', 'batch', self.rows, 0, None, '', False, '', 'voice.pt',
                '', '', 'English', 123, True, False, *app.SETTING_DEFAULTS, previous)

    def test_full_generation_restores_native_top_audio_before_streaming(self):
        self.assertTrue(hasattr(app, 'workflow_stream_started'))
        with patch.object(app, 'workflow_started', return_value=('button','notice',True,1)):
            result=app.workflow_stream_started('generate',None)
        self.assertEqual(result[:4],('button','notice',True,1))
        self.assertTrue(result[4]['visible'])
        self.assertNotIn('value',result[4], 'The previous single take must not be cleared before success.')

    def test_native_progress_is_republished_after_each_streamed_snapshot(self):
        events=[]
        with patch.object(app,'read_voice'), patch.object(app,'OUTPUTS',self.root), \
             patch.object(app,'generate',return_value=(str(self.wav),'','')), patch.object(app,'release_model'):
            iterator=app.generate_workflow_stream(None,*self.args(),progress=lambda *a,**kw: events.append((a,kw)))
            first=next(iterator)
            before=len(events)
            second=next(iterator)
            self.assertGreater(len(events),before)
            self.assertIn('Generating clip 1/2',events[-1][1]['desc'])
            list(iterator)

    def test_publish_first_clip_before_second_inference_and_no_mutable_snapshots(self):
        self.assertIn('on_update', inspect.signature(run_batch).parameters)
        updates = []
        def generate(text, index):
            if index:
                self.assertEqual([c['id'] for c in updates[-1]['clips']], ['one'])
                self.assertEqual(updates[-1]['active_id'], 'two')
            return self.wav
        result = run_batch(self.rows, generate_clip=generate, output_root=self.root,
                           lock=threading.RLock(), on_update=updates.append)
        self.assertEqual(len(updates), 4)  # before first, after each clip, final archive
        self.assertEqual(updates[0]['clips'], [])
        self.assertEqual(updates[0]['pending_ids'], ['one', 'two'])
        self.assertEqual(updates[1]['pending_ids'], ['two'])
        self.assertEqual(updates[1]['clips'][0]['seed'], 10)
        self.assertEqual(len({r['batch_id'] for r in updates}), 1)
        self.assertEqual(len({r['revision'] for r in updates}), 4)
        self.assertFalse(updates[-1]['streaming'])
        self.assertEqual(updates[-1], result)

    def test_failure_publishes_completed_take_and_clears_pending(self):
        self.assertIn('on_update', inspect.signature(run_batch).parameters)
        updates = []
        def generate(text, index):
            if index: raise RuntimeError('inference failed')
            return self.wav
        result = run_batch(self.rows, generate_clip=generate, output_root=self.root,
                           lock=threading.RLock(), on_update=updates.append)
        self.assertEqual(len(result['clips']), 1)
        self.assertEqual(result['failed_id'], 'two')
        self.assertFalse(result['streaming'])
        self.assertEqual(result['pending_ids'], [])
        self.assertTrue(Path(result['clips'][0]['audio']).is_file())
        self.assertIn('inference failed', result['error'])

    def test_ui_stream_is_generator_and_keeps_previous_unreplaced_audio_on_failure(self):
        self.assertTrue(hasattr(app, 'generate_workflow_stream'))
        previous = run_batch(self.rows, generate_clip=lambda *_:self.wav,
                             output_root=self.root, lock=threading.RLock())
        before = copy.deepcopy(previous)
        with patch.object(app, 'read_voice'), patch.object(app, 'OUTPUTS', self.root), \
             patch.object(app, 'generate', side_effect=[(str(self.wav),'',''), RuntimeError('failure')]), \
             patch.object(app, 'release_model'):
            iterator = app.generate_workflow_stream(None, *self.args(previous))
            self.assertTrue(inspect.isgenerator(iterator))
            updates = list(iterator)
        final = updates[-1][11]
        self.assertEqual(previous, before)
        self.assertEqual(final['clips'][1]['audio'], previous['clips'][1]['audio'])
        self.assertNotEqual(final['clips'][0]['audio'], previous['clips'][0]['audio'])
        self.assertTrue(all(Path(c['audio']).is_file() for c in final['clips']))
        self.assertFalse(final['complete'])
        self.assertEqual(updates[1][-1]['ids'], ['one', 'two'])
        self.assertEqual(updates[1][-1]['pending_ids'], ['two'])
        self.assertFalse(updates[-1][-1]['streaming'])
        self.assertTrue(Path(final['archive']).is_file())

    def test_ui_stream_preserves_inference_failure_reason(self):
        with patch.object(app, 'read_voice'), patch.object(app, 'OUTPUTS', self.root), \
             patch.object(app, 'generate', return_value=(None, None, 'Model memory exhausted')), \
             patch.object(app, 'release_model'):
            updates = list(app.generate_workflow_stream(None, *self.args()))
        result = updates[-1][11]
        self.assertIn('Model memory exhausted', result['error'])
        self.assertEqual(result['failed_id'], 'one')
        self.assertFalse(result['streaming'])
        self.assertEqual(result['clips'], [])

    def test_ui_stream_owns_lock_in_one_worker_and_releases_before_final_yield(self):
        self.assertTrue(hasattr(app, 'generate_workflow_stream'))
        threads=[]
        def generate(*args):
            threads.append(threading.get_ident())
            with app.LOCK: return str(self.wav),'',''
        with patch.object(app,'read_voice'), patch.object(app,'OUTPUTS',self.root), \
             patch.object(app,'generate',side_effect=generate), patch.object(app,'release_model'):
            updates=list(app.generate_workflow_stream(None,*self.args()))
        self.assertEqual(len(set(threads)),1)
        self.assertTrue(app.LOCK.acquire(blocking=False))
        app.LOCK.release()
        self.assertEqual([c['id'] for c in updates[1][11]['clips']],['one'])
        self.assertEqual([c['id'] for c in updates[-1][11]['clips']],['one','two'])

    def test_streaming_result_rejects_concurrent_regeneration_and_combine(self):
        result=run_batch(self.rows,generate_clip=lambda *_:self.wav,output_root=self.root,lock=threading.RLock())
        result['streaming']=True
        with patch.object(app,'generate') as generate:
            with self.assertRaisesRegex(ValueError,'finish|running'):
                app.prepare_clip_regeneration(result,self.rows,'one','generate','batch','voice.pt','','English',1,True,False,*app.SETTING_DEFAULTS)
            generate.assert_not_called()
        with self.assertRaisesRegex(ValueError,'finish|running'):
            app.current_batch_timing(result,self.rows)

    def test_retained_archive_has_unique_names_after_reorder_and_partial_failure(self):
        rows = [dict(row, seconds=0) for row in self.rows]
        previous = run_batch(rows, generate_clip=lambda *_: self.wav,
                             output_root=self.root, lock=threading.RLock())
        before = copy.deepcopy(previous)
        new_wav = self.root / 'new.wav'
        app.sf.write(new_wav, app.np.ones(2400) * 0.25, 24000)
        def generate(text, index):
            if index:
                raise RuntimeError('second clip failed')
            return new_wav
        partial = run_batch(list(reversed(rows)), generate_clip=generate,
                            output_root=self.root, lock=threading.RLock())
        partial_before = copy.deepcopy(partial)
        merged = app.streamed_batch_view(partial, previous)
        self.assertEqual(previous, before)
        self.assertEqual(partial, partial_before)
        self.assertEqual([clip['id'] for clip in merged['clips']], ['two', 'one'])
        self.assertEqual(merged['clips'][1]['audio'], previous['clips'][0]['audio'])
        names = [clip['filename'] for clip in merged['clips']]
        self.assertEqual(len(set(names)), 2)
        with zipfile.ZipFile(merged['archive']) as bundle:
            self.assertEqual(len(bundle.namelist()), len(set(bundle.namelist())))
            manifest = json.loads(bundle.read('manifest.json'))
            self.assertFalse(manifest['complete'])
            self.assertEqual([clip['filename'] for clip in manifest['clips']], names)
            for clip in merged['clips']:
                self.assertEqual(bundle.read(clip['filename']), Path(clip['audio']).read_bytes())

    def test_legacy_idless_rows_survive_streaming_and_partial_failure(self):
        rows = [[0, 0, 'One.'], [0, 1, 'Two.'], [0, 2, 'Three.']]
        for fail_last in (False, True):
            with self.subTest(fail_last=fail_last):
                updates = []
                def generate(text, index):
                    if fail_last and index == 2:
                        raise RuntimeError('third clip failed')
                    return self.wav
                run_batch(rows, generate_clip=generate, output_root=self.root,
                          lock=threading.RLock(), on_update=updates.append)
                for snapshot in updates:
                    view = app.streamed_batch_view(snapshot, None)
                    self.assertEqual(view['clips'], snapshot['clips'])
                previous = run_batch(rows, generate_clip=lambda *_: self.wav,
                                     output_root=self.root, lock=threading.RLock())
                merged = app.streamed_batch_view(updates[-1], previous)
                self.assertEqual([clip['index'] for clip in merged['clips']], [1, 2, 3])
                if fail_last:
                    self.assertEqual(merged['clips'][:2], updates[-1]['clips'])
                    self.assertEqual(merged['clips'][2], previous['clips'][2])

    def test_stream_can_resume_on_different_consumer_threads(self):
        worker_ids = []
        def generate(*args):
            worker_ids.append(threading.get_ident())
            with app.LOCK:
                return str(self.wav), '', ''
        with patch.object(app, 'read_voice'), patch.object(app, 'OUTPUTS', self.root), \
             patch.object(app, 'generate', side_effect=generate), patch.object(app, 'release_model'), \
             ThreadPoolExecutor(max_workers=1) as first, ThreadPoolExecutor(max_workers=1) as second:
            self.assertNotEqual(first.submit(threading.get_ident).result(),
                                second.submit(threading.get_ident).result())
            iterator = app.generate_workflow_stream(None, *self.args())
            updates = [pool.submit(next, iterator).result(timeout=10)
                       for pool in (first, second, first, second)]
            self.assertIsNone(second.submit(lambda: next(iterator, None)).result(timeout=10))
        self.assertEqual(len(set(worker_ids)), 1)
        self.assertEqual([clip['id'] for clip in updates[-1][11]['clips']], ['one', 'two'])
        self.assertTrue(app.LOCK.acquire(blocking=False))
        app.LOCK.release()

    def test_closing_stream_saves_inflight_clip_and_stops_before_next(self):
        entered, proceed, finished = threading.Event(), threading.Event(), threading.Event()
        results, calls = [], []
        def generate(*args):
            calls.append(args)
            entered.set()
            if not proceed.wait(10):
                raise RuntimeError('test timed out waiting to release inference')
            with app.LOCK:
                return str(self.wav), '', ''
        def tracked_batch(*args, **kwargs):
            try:
                result = run_batch(*args, **kwargs)
                results.append(result)
                return result
            finally:
                finished.set()
        with patch.object(app, 'read_voice'), patch.object(app, 'OUTPUTS', self.root), \
             patch.object(app, 'generate', side_effect=generate), patch.object(app, 'release_model') as release, \
             patch('batch_generation.run_batch', side_effect=tracked_batch):
            iterator = app.generate_workflow_stream(None, *self.args())
            try:
                self.assertTrue(next(iterator)[11]['streaming'])
                self.assertTrue(entered.wait(10))
            finally:
                iterator.close()
                proceed.set()
                self.assertTrue(finished.wait(10))
            release.assert_called_once_with()
        self.assertEqual(len(calls), 1)
        self.assertEqual([clip['id'] for clip in results[0]['clips']], ['one'])
        self.assertTrue(Path(results[0]['clips'][0]['audio']).is_file())
        self.assertTrue(Path(results[0]['archive']).is_file())
        self.assertFalse(results[0]['streaming'])
        self.assertIn('stopped', results[0]['error'])
        self.assertTrue(app.LOCK.acquire(blocking=False))
        app.LOCK.release()

if __name__=='__main__': unittest.main()
