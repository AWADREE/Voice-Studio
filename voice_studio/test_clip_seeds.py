import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app
from batch_generation import validate_entries


class ClipSeedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.wav = self.root / 'audio.wav'; self.wav.write_bytes(b'RIFF-test-audio')
        self.rows = [dict(id='first', minutes=0, seconds=1, text='First'),
                     dict(id='second', minutes=0, seconds=2, text='Second')]

    def full(self, rows=None, seed=42):
        with patch.object(app, 'read_voice'), patch.object(app, 'OUTPUTS', self.root), \
             patch.object(app, 'generate', return_value=(str(self.wav), '', '')) as generate:
            outputs = app.generate_commentary_mode('batch', rows or self.rows, 'voice.pt', '', '',
                'English', seed, False, False, *app.SETTING_DEFAULTS)
        return outputs[11], [call.args[4] for call in generate.call_args_list]

    def test_first_generation_inherits_global_seed_for_every_clip(self):
        result, used = self.full(seed=123)
        self.assertEqual(used, [123, 123])
        self.assertEqual([c.get('seed') for c in result['clips']], [123, 123])
        self.assertEqual(app.batch_editor_metadata(result)['seeds'], {'first': 123, 'second': 123})

    def test_full_generation_uses_each_override_and_global_for_new_rows(self):
        rows = [dict(self.rows[0], seed=101), dict(self.rows[1], seed=202),
                dict(id='new', minutes=0, seconds=3, text='New')]
        result, used = self.full(rows, seed=999)
        self.assertEqual(used, [101, 202, 999])
        self.assertEqual([c['seed'] for c in result['clips']], used)

    def test_random_seed_is_preserved_and_override_not_global_is_used(self):
        result, used = self.full([dict(self.rows[0], seed=-1), self.rows[1]], seed=500)
        self.assertEqual(used, [-1, 500])
        self.assertEqual(result['clips'][0]['seed'], -1)

    def test_individual_regeneration_uses_override_and_keeps_it_on_commit(self):
        result, _ = self.full()
        rows = [self.rows[0], dict(self.rows[1], seed=321)]
        with patch.object(app, 'generate', return_value=(str(self.wav), '', '')) as generate:
            candidate = app.prepare_clip_regeneration(result, rows, 'second', 'generate', 'batch',
                'voice.pt', '', 'English', 999, False, False, *app.SETTING_DEFAULTS)
        self.assertEqual(generate.call_args.args[4], 321)
        updated = app.commit_clip_regeneration(candidate, result, rows)
        self.assertEqual(updated['clips'][1]['seed'], 321)
        self.assertEqual(updated['clips'][0], result['clips'][0])

    def test_late_result_does_not_overwrite_edited_seed(self):
        result, _ = self.full()
        rows = [self.rows[0], dict(self.rows[1], seed=321)]
        with patch.object(app, 'generate', return_value=(str(self.wav), '', '')):
            candidate = app.prepare_clip_regeneration(result, rows, 'second', 'generate', 'batch',
                'voice.pt', '', 'English', 999, False, False)
        before = copy.deepcopy(result)
        with self.assertRaisesRegex(ValueError, 'seed changed'):
            app.commit_clip_regeneration(candidate, result, [rows[0], dict(rows[1], seed=654)])
        with self.assertRaisesRegex(ValueError, 'seed changed'):
            app.commit_clip_regeneration(candidate, result, self.rows)
        self.assertEqual(result, before)

    def test_ui_captured_seed_commits_even_after_new_seed_changes_draft(self):
        result, _ = self.full()
        rows = [self.rows[0], dict(self.rows[1], seed=321)]
        event = app.gr.EventData(None, {'id': 'second', 'seed': 321, 'batch_id': result['batch_id']})
        with patch.object(app, 'generate', return_value=(str(self.wav), '', '')) as generate:
            candidate = app.regenerate_clip_ui(result, rows, 'generate', 'batch',
                'voice.pt', '', 'English', 999, False, False, event, *app.SETTING_DEFAULTS)
        # A future draft value is not the immutable seed of this request.
        draft = [rows[0], dict(rows[1], seed=654)]
        updated = app.commit_clip_regeneration(candidate, result, draft)
        self.assertEqual(updated['clips'][1]['seed'], 321)
        self.assertEqual(draft[1]['seed'], 654)
        self.assertEqual(generate.call_args.args[4], 321)

    def test_queued_seed_is_used_even_if_draft_changes_before_dispatch(self):
        result, _ = self.full()
        rows = [self.rows[0], dict(self.rows[1], seed=654)]
        event = app.gr.EventData(None, {'id': 'second', 'seed': 321, 'batch_id': result['batch_id']})
        with patch.object(app, 'generate', return_value=(str(self.wav), '', '')) as generate:
            candidate = app.regenerate_clip_ui(result, rows, 'generate', 'batch',
                'voice.pt', '', 'English', 999, False, False, event, *app.SETTING_DEFAULTS)
        self.assertEqual(generate.call_args.args[4], 321)
        self.assertEqual(app.commit_clip_regeneration(candidate, result, rows)['clips'][1]['seed'], 321)

    def test_captured_job_is_independent_of_invalid_future_draft_seed(self):
        result, _ = self.full()
        rows = [self.rows[0], dict(self.rows[1], seed='')]
        event = app.gr.EventData(None, {'id': 'second', 'seed': 321, 'batch_id': result['batch_id']})
        with patch.object(app, 'generate', return_value=(str(self.wav), '', '')) as generate:
            candidate = app.regenerate_clip_ui(result, rows, 'generate', 'batch',
                'voice.pt', '', 'English', 999, False, False, event, *app.SETTING_DEFAULTS)
        self.assertEqual(generate.call_args.args[4], 321)
        self.assertEqual(app.commit_clip_regeneration(candidate, result, rows)['clips'][1]['seed'], 321)
        self.assertEqual(rows[1]['seed'], '')

    def test_queued_request_cannot_target_a_replacement_batch(self):
        result, _ = self.full()
        event = app.gr.EventData(None, {'id': 'second', 'seed': 321, 'batch_id': 'previous-batch'})
        with patch.object(app, 'generate') as generate:
            candidate = app.regenerate_clip_ui(result, self.rows, 'generate', 'batch',
                'voice.pt', '', 'English', 999, False, False, event, *app.SETTING_DEFAULTS)
        generate.assert_not_called()
        self.assertIn('batch changed', candidate['error'])

    def test_seed_validation_preserves_safe_integers_and_rejects_invalid(self):
        for value in [-1, 0, 4294967295, 9007199254740991, '123']:
            self.assertEqual(validate_entries([dict(self.rows[0], seed=value)])[0].get('seed'), int(value))
        for value in ['', None, True, -2, 1.2, float('nan'), 9007199254740992]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'seed'):
                validate_entries([dict(self.rows[0], seed=value)])

    def test_invalid_override_does_not_generate_and_old_audio_is_untouched(self):
        result, _ = self.full()
        before = copy.deepcopy(result)
        with patch.object(app, 'generate') as generate:
            with self.assertRaises(ValueError):
                app.prepare_clip_regeneration(result, [self.rows[0], dict(self.rows[1], seed='')],
                    'second', 'generate', 'batch', 'voice.pt', '', 'English', 42, False, False)
        generate.assert_not_called(); self.assertEqual(result, before)

    def test_invalid_full_batch_seed_is_checked_before_any_model_call(self):
        with patch.object(app, 'read_voice'), patch.object(app, 'generate') as generate:
            with self.assertRaisesRegex(ValueError, 'seed'):
                app.generate_commentary_mode('batch', [self.rows[0], dict(self.rows[1], seed='')],
                    'voice.pt', '', '', 'English', 42, False, False)
        generate.assert_not_called()

    def test_combine_timing_does_not_depend_on_unapplied_seed_edit(self):
        result, _ = self.full()
        updated = app.current_batch_timing(result, [dict(self.rows[0], seed=''), self.rows[1]])
        self.assertEqual(updated['clips'][0]['audio'], result['clips'][0]['audio'])


if __name__ == '__main__': unittest.main()
