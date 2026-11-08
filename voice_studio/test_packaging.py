import unittest
import app

class PackagingTests(unittest.TestCase):
    def test_assets_resolve_in_current_checkout(self):
        css=app.ui_asset_text('theme.css')
        self.assertIn((app.ROOT/'assets').as_posix(),css)
        self.assertNotIn('__VOICE_STUDIO_ASSETS__',css)
        self.assertNotIn('E:/AI/Apps/',css)
    def test_authorized_theme_is_self_contained(self):
        js=app.ui_asset_text('night-sky.js')
        self.assertIn('night-sky-stars-removed.png',js)
        self.assertIn('starCyclePeak',js)
        self.assertTrue((app.ROOT/'assets'/'night-sky-stars-removed.png').is_file())
        self.assertNotIn('local-background',js)
        self.assertNotIn('E:/AI/Apps/',js)
    def test_model_cache_is_configurable(self):
        import os
        if os.environ.get('HF_HOME') and not os.environ.get('VOICE_STUDIO_MODEL_CACHE'):
            self.assertEqual(app.MODEL_REPO.parent.parent,app.Path(os.environ['HF_HOME']))
