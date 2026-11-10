import unittest
from unittest.mock import patch
import app

class SeedRandomizerTests(unittest.TestCase):
    def arguments(self, workflow='generate', seed=123):
        return [workflow, 'single', [], None, None, '', False, 'Warm voice', 'voice.pt',
                'A sample', '', 'English', seed, False, False, *app.SETTING_DEFAULTS]

    def test_single_snapshot_uses_exact_displayed_seed(self):
        with patch.object(app, 'generate_preview_atomic', return_value=(None,) * 11) as generate:
            app.generate_workflow_mode(*self.arguments(seed=4294967295))
        self.assertEqual(generate.call_args.args[4], 4294967295)

    def test_design_and_clone_receive_displayed_seed(self):
        for workflow, callback, position in [('design', 'generate_design_preview', 3), ('clone', 'clone_audition', 6)]:
            with self.subTest(workflow=workflow), patch.object(app, callback, return_value=(None, None, '', {}, '', False)) as generate:
                app.generate_workflow_mode(*self.arguments(workflow, 741))
                self.assertEqual(generate.call_args.args[position], 741)

    def test_invalid_single_seed_is_not_truncated_or_sent_to_model(self):
        for seed in ['', 1.5, -2, 9007199254740992]:
            with self.subTest(seed=seed), patch.object(app, 'generate_preview_atomic') as generate:
                with self.assertRaisesRegex(ValueError, 'seed'):
                    app.generate_workflow_mode(*self.arguments(seed=seed))
                generate.assert_not_called()

    def test_ui_uses_snapshot_hook_and_does_not_output_editable_drafts(self):
        ui = app.build_ui()
        event = next(fn for fn in ui.fns.values() if fn.fn is app.generate_workflow_ui)
        self.assertIn('voxoverSeedRandomizer?.prepare(args)', event.js)
        self.assertFalse(any(getattr(component, 'elem_id', '') in ['single-clip-seed', 'clip-editor'] for component in event.outputs))
        self.assertTrue(any(fn.js and 'voxoverSeedRandomizer' in fn.js and '// SEED_HELPERS' not in fn.js for fn in ui.fns.values()))

if __name__ == '__main__': unittest.main()
