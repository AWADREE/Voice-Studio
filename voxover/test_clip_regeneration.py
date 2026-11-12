import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

from batch_generation import run_batch, validate_entries
import app


class RegenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.old = self.root / 'old.wav'; self.old.write_bytes(b'old-audio')
        self.new = self.root / 'new.wav'; self.new.write_bytes(b'new-audio')
        self.rows = [dict(id='first', minutes=0, seconds=2, text='Same text'),
                     dict(id='second', minutes=0, seconds=5, text='Same text')]
        self.result = run_batch(self.rows, generate_clip=lambda *_: self.old,
                               output_root=self.root, lock=threading.RLock())

    def prepare(self, rows=None, row_id='second'):
        with patch.object(app, 'generate', return_value=(str(self.new), '', '')) as generate:
            candidate = app.prepare_clip_regeneration(self.result, rows or self.rows, row_id,
                'generate', 'batch', 'latest.pt', 'Softly', 'French', 9, False, True,
                *app.SETTING_DEFAULTS)
        self.assertEqual(generate.call_args.args,
            ('latest.pt', 'Same text', 'Softly', 'French', 9, False, True, *app.SETTING_DEFAULTS))
        return candidate

    def test_ids_are_preserved_and_duplicates_rejected(self):
        self.assertEqual([r.get('id') for r in validate_entries(self.rows)], ['first', 'second'])
        self.assertEqual([c.get('id') for c in self.result['clips']], ['first', 'second'])
        with self.assertRaisesRegex(ValueError, 'identity'):
            validate_entries([self.rows[0], self.rows[0]])

    def test_replacement_changes_only_matching_clip_and_zip(self):
        candidate = self.prepare()
        before = copy.deepcopy(self.result)
        updated = app.commit_clip_regeneration(candidate, self.result, self.rows)
        self.assertEqual(self.result, before)
        self.assertEqual(updated['clips'][0], self.result['clips'][0])
        self.assertEqual(Path(updated['clips'][1]['audio']).read_bytes(), b'new-audio')
        self.assertNotEqual(updated['archive'], self.result['archive'])
        self.assertEqual(updated['highlight_id'], 'second')
        self.assertEqual(updated['revision'], self.result['revision'] + 1)
        with zipfile.ZipFile(updated['archive']) as z:
            self.assertEqual(z.read(updated['clips'][0]['filename']), b'old-audio')
            self.assertEqual(z.read(updated['clips'][1]['filename']), b'new-audio')
            self.assertNotIn(str(self.root), z.read('manifest.json').decode())
        self.assertEqual(Path(before['clips'][1]['audio']).read_bytes(), b'old-audio')

    def test_late_result_rejects_new_batch_or_newer_version(self):
        candidate = self.prepare()
        for result in [dict(self.result, batch_id='new-batch'), dict(self.result, revision=20)]:
            with self.assertRaisesRegex(ValueError, 'changed'):
                app.commit_clip_regeneration(candidate, result, self.rows)

    def test_late_result_rejects_edited_removed_or_replaced_row(self):
        candidate = self.prepare()
        for rows in [self.rows[:1], [self.rows[0], dict(self.rows[1], text='Edited')],
                     [self.rows[0], dict(self.rows[1], id='new-row')]]:
            with self.assertRaisesRegex(ValueError, 'changed|removed'):
                app.commit_clip_regeneration(candidate, self.result, rows)

    def test_reordering_identical_text_cannot_misassociate_replacement(self):
        candidate = self.prepare()
        updated = app.commit_clip_regeneration(candidate, self.result, list(reversed(self.rows)))
        self.assertEqual([clip['id'] for clip in updated['clips']], ['second', 'first'])
        self.assertEqual([clip['index'] for clip in updated['clips']], [1, 2])
        self.assertEqual(updated['clips'][1]['audio'], self.result['clips'][0]['audio'])
        self.assertEqual(Path(updated['clips'][0]['audio']).read_bytes(), b'new-audio')

    def test_new_timing_is_used_without_overwriting_editor(self):
        candidate = self.prepare()
        rows = [self.rows[0], dict(self.rows[1], seconds=8)]
        updated = app.commit_clip_regeneration(candidate, self.result, rows)
        self.assertEqual(updated['clips'][1]['seconds'], 8)
        self.assertEqual(self.result['clips'][1]['seconds'], 5)

    def test_unrelated_invalid_draft_does_not_block_one_clip(self):
        rows = [dict(self.rows[0], text=''), self.rows[1]]
        candidate = self.prepare(rows)
        updated = app.commit_clip_regeneration(candidate, self.result, rows)
        self.assertEqual(updated['clips'][0], self.result['clips'][0])

    def test_failure_does_not_mutate_previous_result(self):
        before = copy.deepcopy(self.result)
        candidate = self.prepare()
        with patch('batch_generation.zipfile.ZipFile', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'):
                app.commit_clip_regeneration(candidate, self.result, self.rows)
        self.assertEqual(before, self.result)

    def test_cannot_regenerate_unmatched_row_or_wrong_mode(self):
        with patch.object(app, 'generate') as generate:
            for workflow, mode, row_id in [('clone', 'batch', 'second'), ('generate', 'single', 'second'), ('generate', 'batch', 'new')]:
                with self.assertRaises(ValueError):
                    app.prepare_clip_regeneration(self.result, self.rows, row_id, workflow, mode,
                        'voice.pt', '', 'English', 42, True, False)
            generate.assert_not_called()

    def test_ui_has_regenerate_event_and_guard_without_editor_output(self):
        ui = app.build_ui()
        events = [f for f in ui.fns.values() if f.fn and f.fn.__name__ == 'regenerate_clip_ui']
        self.assertEqual(len(events), 1)
        self.assertFalse(any(getattr(output, 'elem_id', '') == 'clip-editor' for output in events[0].outputs))
        self.assertIn('generation-guard.js', Path(app.__file__).read_text())
        commit = next(f for f in ui.fns.values() if f.fn and f.fn.__name__ == 'commit_clip_regeneration_ui')
        self.assertTrue(commit.queue, 'Gradio nonqueued responses omit State.change notifications, leaving old players visible.')
        self.assertEqual(events[0].show_progress, 'hidden')
        self.assertTrue(any(f.js == app.ui_asset_text('clip-loading.js') for f in ui.fns.values()))

    def test_completed_clip_publishes_metadata_before_unlocking_queue(self):
        ui = app.build_ui()
        config = ui.get_config_file()
        commit = next(i for i, fn in ui.fns.items() if fn.fn and fn.fn.__name__ == 'commit_clip_regeneration_ui')
        metadata = next(dep for dep in config['dependencies'] if dep.get('trigger_after') == commit)
        self.assertEqual(ui.fns[metadata['id']].fn, app.batch_editor_metadata)
        finish = next(dep for dep in config['dependencies'] if dep.get('trigger_after') == metadata['id'])
        self.assertIn('GenerationGuard?.finish()', finish['js'])

    def test_new_batch_restores_hidden_panel(self):
        ui = app.build_ui()
        panel = next(block for block in ui.blocks.values() if getattr(block, 'elem_id', None) == 'batch-output')
        refresh = next(fn for fn in ui.fns.values() if fn.fn and fn.fn.__name__ == 'show_generated_batch')
        self.assertIn(panel, refresh.outputs)
        self.assertTrue(refresh.fn(self.result)['visible'])
        self.assertEqual(refresh.fn(None), app.gr.skip())

    def test_failed_full_batch_preserves_previous_audio(self):
        failed = [app.gr.skip() for _ in range(19)]
        failed[11] = dict(self.result, clips=[], error='synthesis failed', status='synthesis failed')
        with patch.object(app, 'generate_workflow_mode', return_value=tuple(failed)):
            updates = app.generate_workflow_ui(None)
        self.assertEqual(updates[11], app.gr.skip())
        self.assertIn('synthesis failed', updates[2]['value'])

    def test_partial_full_batch_keeps_existing_batch(self):
        partial = [app.gr.skip() for _ in range(19)]
        partial[11] = dict(self.result, clips=self.result['clips'][:1], error='second failed', status='second failed')
        with patch.object(app, 'generate_workflow_mode', return_value=tuple(partial)):
            updates = app.generate_workflow_ui(None, *([None] * 25), self.result)
        self.assertEqual(updates[11], app.gr.skip())
        self.assertIn('second failed', updates[2]['value'])

    def test_ui_error_keeps_all_previous_media_and_archive(self):
        for candidate in [{'error': 'synthesis failed'}, None]:
            updates = app.commit_clip_regeneration_ui(candidate, self.result, self.rows)
            self.assertEqual(updates[0], app.gr.skip())
            self.assertEqual(updates[2], app.gr.skip())
            self.assertIn('Regeneration failed', updates[1])

    def test_current_timing_matches_row_identity_after_reordering(self):
        rows = [dict(self.rows[1], seconds=8), dict(self.rows[0], seconds=3)]
        updated = app.current_batch_timing(self.result, rows)
        self.assertEqual([c['seconds'] for c in updated['clips']], [3, 8])
        self.assertEqual([c['audio'] for c in updated['clips']], [c['audio'] for c in self.result['clips']])

    def test_busy_commit_does_not_replace_or_unload_audio(self):
        candidate = self.prepare()
        lock = threading.Lock()
        with lock, patch.object(app, 'LOCK', lock):
            updates = app.commit_clip_regeneration_ui(candidate, self.result, self.rows)
        self.assertEqual(updates[0], app.gr.skip())
        self.assertEqual(updates[2], app.gr.skip())
        self.assertIn('Another operation', updates[1])


    def single_candidate(self, result, rows, row_id, **data):
        from types import SimpleNamespace
        event = SimpleNamespace(_data=dict(id=row_id, seed=123, batch_id=(result or {}).get('batch_id'), **data))
        with patch.object(app, 'generate', return_value=(str(self.new), '', '')) as generate:
            candidate = app.regenerate_clip_ui(result, rows, 'generate', 'batch',
                'voice.pt', '', 'English', 42, False, False, event, *app.SETTING_DEFAULTS)
        self.assertNotIn('error', candidate)
        generate.assert_called_once()
        self.assertEqual(generate.call_args.args[1], next(row['text'].strip() for row in rows if row['id'] == row_id))
        return candidate

    def test_first_row_generation_creates_partial_batch_then_completes(self):
        candidate = self.single_candidate(None, self.rows, 'second', draft_id='draft-1')
        with patch.object(app, 'OUTPUTS', self.root):
            first = app.commit_clip_regeneration(candidate, None, self.rows)
        self.assertEqual([clip['id'] for clip in first['clips']], ['second'])
        self.assertEqual(first['clips'][0]['index'], 2)
        self.assertEqual(first['origin_draft_id'], 'draft-1')
        self.assertEqual(first['requested_clips'], 2)
        self.assertFalse(first['complete'])
        self.assertTrue(Path(first['archive']).is_file())
        candidate = self.single_candidate(first, self.rows, 'first', draft_id='draft-1')
        second = app.commit_clip_regeneration(candidate, first, self.rows)
        self.assertTrue(second['complete'])
        self.assertEqual([clip['id'] for clip in second['clips']], ['first', 'second'])
        self.assertEqual(second['clips'][1]['audio'], first['clips'][0]['audio'])
        self.assertTrue(app.current_batch_timing(second, self.rows)['complete'])
        with zipfile.ZipFile(first['archive']) as z:
            self.assertFalse(json.loads(z.read('manifest.json'))['complete'])

    def test_add_new_row_then_regenerate_edited_existing_row_repro(self):
        candidate = self.prepare()
        first = app.commit_clip_regeneration(candidate, self.result, self.rows)
        rows = [self.rows[0], dict(self.rows[1], text='Same'),
                dict(id='new', minutes=0, seconds=9, text='text')]
        candidate = self.single_candidate(first, rows, 'second')
        updated = app.commit_clip_regeneration(candidate, first, rows)
        self.assertEqual(updated['clips'][1]['text'], 'Same')
        self.assertNotEqual(updated['clips'][1]['audio'], first['clips'][1]['audio'])
        self.assertEqual(updated['clips'][0]['audio'], first['clips'][0]['audio'])
        self.assertFalse(updated['complete'])
        self.assertEqual(updated['requested_clips'], 3)
        candidate = self.single_candidate(updated, rows, 'new')
        added = app.commit_clip_regeneration(candidate, updated, rows)
        self.assertTrue(added['complete'])
        self.assertEqual([c['id'] for c in added['clips']], ['first','second','new'])
        self.assertEqual([c['index'] for c in added['clips']], [1,2,3])
        self.assertEqual(added['clips'][:2], updated['clips'])
        self.assertTrue(app.current_batch_timing(added, rows)['complete'])

    def test_queued_null_batch_requires_same_draft_origin(self):
        from types import SimpleNamespace
        candidate = self.single_candidate(None, self.rows, 'first', draft_id='draft-1')
        with patch.object(app, 'OUTPUTS', self.root):
            first = app.commit_clip_regeneration(candidate, None, self.rows)
        for draft_id, result, allowed in [('draft-1',first,True),('other',first,False),('draft-1',self.result,False)]:
            event = SimpleNamespace(_data=dict(id='second', seed=9, batch_id=None, draft_id=draft_id))
            with patch.object(app, 'generate', return_value=(str(self.new), '', '')) as generate:
                queued = app.regenerate_clip_ui(result, self.rows, 'generate', 'batch',
                    'voice.pt', '', 'English', 42, False, False, event)
            if allowed:
                generate.assert_called_once()
                self.assertNotIn('error', queued)
                self.assertTrue(app.commit_clip_regeneration(queued, first, self.rows)['complete'])
            else:
                generate.assert_not_called()
                self.assertIn('batch changed', queued['error'])

    def test_orphans_kept_but_never_marked_complete_or_combined(self):
        rows = [self.rows[1], dict(id='new', minutes=0, seconds=8, text='New')]
        candidate = self.single_candidate(self.result, rows, 'second')
        updated = app.commit_clip_regeneration(candidate, self.result, rows)
        self.assertFalse(updated['complete'])
        self.assertEqual(updated['requested_clips'], 2)
        self.assertEqual({c['id'] for c in updated['clips']}, {'first','second'})
        self.assertEqual(next(c['audio'] for c in updated['clips'] if c['id']=='first'), self.result['clips'][0]['audio'])
        with zipfile.ZipFile(updated['archive']) as z:
            self.assertFalse(json.loads(z.read('manifest.json'))['complete'])
        with self.assertRaisesRegex(ValueError, 'removed or replaced'):
            app.current_batch_timing(updated, rows)

    def test_new_first_candidate_cannot_replace_batch_born_during_synthesis(self):
        candidate = self.single_candidate(None, self.rows, 'first')
        with self.assertRaisesRegex(ValueError, 'batch changed'):
            app.commit_clip_regeneration(candidate, self.result, self.rows)

    def test_repeated_source_filename_still_creates_immutable_takes(self):
        first = app.commit_clip_regeneration(self.prepare(), self.result, self.rows)
        self.new.write_bytes(b'newer-audio')
        second = app.commit_clip_regeneration(self.single_candidate(first, self.rows, 'second'), first, self.rows)
        self.assertNotEqual(first['clips'][1]['audio'], second['clips'][1]['audio'])
        self.assertEqual(Path(first['clips'][1]['audio']).read_bytes(), b'new-audio')
        self.assertEqual(Path(second['clips'][1]['audio']).read_bytes(), b'newer-audio')
        with zipfile.ZipFile(first['archive']) as z:
            self.assertEqual(z.read(first['clips'][1]['filename']), b'new-audio')

    def test_synthesis_status_survives_ui_failure_without_mutation(self):
        from types import SimpleNamespace
        before = copy.deepcopy(self.result)
        event = SimpleNamespace(_data=dict(id='second', batch_id=self.result['batch_id']))
        with patch.object(app, 'generate', return_value=(None, None, 'Error: Select a voice file first.')):
            candidate = app.regenerate_clip_ui(self.result, self.rows, 'generate', 'batch',
                None, '', 'English', 42, False, False, event)
        updates = app.commit_clip_regeneration_ui(candidate, self.result, self.rows)
        self.assertIn('Select a voice file first.', updates[1])
        self.assertEqual(updates[0], app.gr.skip())
        self.assertEqual(updates[2], app.gr.skip())
        self.assertEqual(self.result, before)

    def test_duplicate_current_ids_block_before_synthesis(self):
        with patch.object(app, 'generate') as generate, self.assertRaisesRegex(ValueError, 'identity'):
            app.prepare_clip_regeneration(self.result, [self.rows[0], self.rows[0]], 'first',
                'generate','batch','voice.pt','','English',42,False,False)
        generate.assert_not_called()


    def test_batch_revision_is_captured_before_synthesis(self):
        original_revision = self.result['revision']
        def generation(*args):
            self.result['revision'] += 1
            return str(self.new), '', ''
        with patch.object(app, 'generate', side_effect=generation):
            candidate = app.prepare_clip_regeneration(self.result, self.rows, 'first',
                'generate','batch','voice.pt','','English',42,False,False)
        self.assertEqual(candidate['revision'], original_revision)
        with self.assertRaisesRegex(ValueError, 'batch changed'):
            app.commit_clip_regeneration(candidate, self.result, self.rows)


    def test_full_batch_regeneration_cannot_adopt_first_generation_draft(self):
        from types import SimpleNamespace
        candidate = self.single_candidate(self.result, self.rows, 'second', draft_id='draft-1')
        updated = app.commit_clip_regeneration(candidate, self.result, self.rows)
        self.assertIsNone(updated['origin_draft_id'])
        self.assertEqual(updated['batch_id'], self.result['batch_id'])
        event = SimpleNamespace(_data=dict(id='first', seed=9, batch_id=None, draft_id='draft-1'))
        with patch.object(app, 'generate') as generate:
            rejected = app.regenerate_clip_ui(updated, self.rows, 'generate', 'batch',
                'voice.pt', '', 'English', 42, False, False, event)
        generate.assert_not_called()
        self.assertIn('batch changed', rejected['error'])


if __name__ == '__main__': unittest.main()
