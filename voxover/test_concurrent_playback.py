"""Regression contract for native media preserved by dynamic clip rendering."""
import tempfile
import unittest
from pathlib import Path

import app


class ConcurrentPlaybackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.render_clips = staticmethod(app.build_ui().renderables[0].fn)

    def render_player(self, path):
        with app.gr.Blocks() as rendered:
            self.render_clips({'clips': [{'id': 'first', 'index': 1,
                'label': '00:01', 'filename': path.name, 'audio': str(path)}]})
        return next(component for component in rendered.get_config_file()['components']
                    if component['type'] == 'audio')

    def test_unchanged_take_preserves_playhead_and_waveform_configuration(self):
        # A fresh playback_position=0 seeks backwards. A fresh waveform_options
        # object causes Gradio's URL effect to reload the already buffered WAV.
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'clip.wav'
            app.sf.write(path, app.np.zeros(2400), 24000)
            player = self.render_player(path)
        preserved = player['props']['preserved_by_key']
        for prop in ('value', 'playback_position', 'waveform_options'):
            self.assertIn(prop, preserved, f'An unrelated render must preserve {prop}')

    def test_continuously_present_take_omits_reset_props(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'clip.wav'
            app.sf.write(path, app.np.zeros(2400), 24000)
            state = set()
            result = {'clips': [{'id': 'first', 'index': 1, 'label': '00:01',
                                'filename': path.name, 'audio': str(path)}]}
            def render(value):
                with app.gr.Blocks() as blocks:
                    self.render_clips(value, state)
                return [c for c in blocks.get_config_file()['components'] if c['type'] == 'audio']
            initial = render(result)[0]
            repeated = render(result)[0]
            for prop in ('value', 'playback_position', 'waveform_options'):
                self.assertIn(prop, initial['props'])
                self.assertNotIn(prop, repeated['props'])
            render(None)
            remounted = render(result)[0]
            for prop in ('value', 'playback_position', 'waveform_options'):
                self.assertIn(prop, remounted['props'])

    def test_replaced_take_receives_a_new_media_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            old, new = (Path(folder) / name for name in ('old.wav', 'new.wav'))
            for path in (old, new):
                app.sf.write(path, app.np.zeros(2400), 24000)
            self.assertEqual(self.render_player(old)['key'], self.render_player(old)['key'])
            self.assertNotEqual(self.render_player(old)['key'], self.render_player(new)['key'])
            old_classes = self.render_player(old)['props']['elem_classes']
            new_classes = self.render_player(new)['props']['elem_classes']
            old_take = next(c for c in old_classes if c.startswith('batch-take-'))
            new_take = next(c for c in new_classes if c.startswith('batch-take-'))
            self.assertNotEqual(old_take, new_take)
            self.assertIn(old_take, self.render_player(old)['props']['elem_classes'])


if __name__ == '__main__':
    unittest.main()
