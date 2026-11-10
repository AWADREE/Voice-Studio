import unittest
import app

class NumberWheelUiTests(unittest.TestCase):
    def test_wheel_guard_is_loaded_by_real_ui(self):
        ui = app.build_ui()
        guard = app.ui_asset_text('number-wheel.js')
        registrations = [fn for fn in ui.fns.values() if fn.js == guard]
        self.assertEqual(len(registrations), 1)
        self.assertIsNone(registrations[0].fn)
        # Numeric components retain Gradio's validation rather than becoming text.
        config = ui.get_config_file()
        labels = {component['props'].get('label'): component
                  for component in config['components']}
        self.assertEqual(labels['Seed']['type'], 'number')
        self.assertEqual(labels['Total duration: seconds']['props']['minimum'], 0)
        self.assertEqual(labels['Total duration: seconds']['props']['maximum'], 59)
        self.assertEqual(labels['Temperature']['type'], 'slider')
