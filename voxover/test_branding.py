import os
import json
import subprocess
from pathlib import Path
import unittest
from unittest.mock import patch
import app

ROOT = Path(__file__).resolve().parent

class BrandingTests(unittest.TestCase):
    def test_ui_title_and_heading_use_voxover(self):
        ui = app.build_ui()
        self.assertEqual(ui.title, 'Voxover | Voice & Commentary')
        markup = '\n'.join(str(c.get('props', {}).get('value', '')) for c in ui.config['components'])
        self.assertIn('<h1>Voxover</h1>', markup)
        self.assertNotIn('Voice Studio', markup)
        self.assertNotIn('CadentVox', markup)

    def test_boot_splash_uses_voxover(self):
        css = app.ui_asset_text('theme.css')
        self.assertIn("content:'Voxover'", css)
        self.assertNotIn('Voice Studio', css)
        self.assertNotIn('CadentVox', css)

    def test_branded_icon_and_launcher_assets_exist(self):
        self.assertTrue((ROOT/'assets/app-icon/voxover.ico').is_file())
        self.assertTrue((ROOT/'assets/app-icon/voxover.png').is_file())
        shortcut = (ROOT/'Create-Shortcut.ps1').read_text(encoding='utf-8-sig')
        self.assertIn('Voxover.lnk', shortcut)
        self.assertIn('voxover.ico', shortcut)
        self.assertIn("GetFolderPath('Programs')", shortcut)
        self.assertEqual(ROOT.name, 'voxover')

    def test_new_config_takes_priority_and_legacy_still_works(self):
        self.assertTrue(hasattr(app, 'app_setting'), 'Brand-aware settings resolver is missing')
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(app.app_setting('PORT', '8003'), '8003')
            os.environ['VOICE_STUDIO_PORT'] = '8013'
            self.assertEqual(app.app_setting('PORT', '8003'), '8013')
            os.environ['CADENTVOX_PORT'] = '8014'
            self.assertEqual(app.app_setting('PORT', '8003'), '8014')
            os.environ['VOXOVER_PORT'] = '8015'
            self.assertEqual(app.app_setting('PORT', '8003'), '8015')
            os.environ['VOXOVER_PORT'] = ''
            self.assertEqual(app.app_setting('PORT', '8003'), '8014')
            os.environ['CADENTVOX_PORT'] = ''
            self.assertEqual(app.app_setting('PORT', '8003'), '8013')

    @unittest.skipUnless(os.name == 'nt', 'Windows launcher')
    def test_launcher_config_precedence_and_browser_destination(self):
        script = str(ROOT/'Open-GUI.ps1').replace("'", "''")
        command = "function Invoke-WebRequest { @{StatusCode=200} }; function Start-Process { param($FilePath) $script:OpenedUrl=$FilePath }; . '" + script + "'; @{python=$python;port=$port;url=$script:OpenedUrl}|ConvertTo-Json -Compress"
        cases = [
            ({}, 'python', '8003'),
            ({'VOICE_STUDIO_PYTHON':'old-python','VOICE_STUDIO_PORT':'8013'}, 'old-python', '8013'),
            ({'VOICE_STUDIO_PYTHON':'old-python','VOICE_STUDIO_PORT':'8013','CADENTVOX_PYTHON':'cadent-python','CADENTVOX_PORT':'8014'}, 'cadent-python', '8014'),
            ({'CADENTVOX_PYTHON':'cadent-python','CADENTVOX_PORT':'8014','VOXOVER_PYTHON':'new-python','VOXOVER_PORT':'8015'}, 'new-python', '8015'),
            ({'CADENTVOX_PYTHON':'cadent-python','CADENTVOX_PORT':'8014','VOXOVER_PYTHON':'','VOXOVER_PORT':''}, 'cadent-python', '8014'),
        ]
        base = {k:v for k,v in os.environ.items() if not k.startswith(('VOXOVER_', 'CADENTVOX_', 'VOICE_STUDIO_'))}
        for settings, python, port in cases:
            with self.subTest(settings=settings):
                result = subprocess.run(['powershell.exe','-NoProfile','-Command',command], env={**base, **settings}, capture_output=True, text=True, check=True)
                self.assertEqual(json.loads(result.stdout), {'python':python, 'port':port, 'url':'http://127.0.0.1:'+port})

if __name__ == '__main__':
    unittest.main()
