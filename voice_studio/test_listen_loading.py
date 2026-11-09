"""Regeneration keeps prior media but presents the same bounded busy surface."""
from pathlib import Path
import re
import unittest
import app

class ListenLoadingTests(unittest.TestCase):
    def setUp(self):
        css=(Path(app.ROOT)/'theme.css').read_text(encoding='utf-8-sig')
        self.rules=css[css.index('/* Keep regeneration') :]
    def test_main_busy_audio_uses_one_fixed_surface_without_empty_branch(self):
        selector='#listen-panel>.studio-audio-output:has(>.wrap:not(.hide))'
        match=re.search(re.escape(selector)+r'\s*\{([^}]+)\}',self.rules)
        self.assertIsNotNone(match)
        style=match.group(1)
        for property in ['height','min-height','max-height']:
            self.assertRegex(style,rf'(?<![\w-]){property}:166px!important')
        self.assertIn('box-sizing:border-box!important',style)
        self.assertNotIn(':has(.empty)',self.rules)
        self.assertIn(selector+'>:not(.wrap){visibility:hidden!important}',self.rules)
    def test_busy_backdrop_and_old_export_controls_are_consistent(self):
        self.assertIn('#listen-panel>.studio-audio-output>.wrap:not(.hide){background:#091a2a!important',self.rules)
        self.assertIn('#listen-panel:has(>.studio-audio-output>.wrap:not(.hide))>:is(.studio-wav-output,.studio-output-status,#batch-output,#timeline-combine,#audition-save-actions){display:none!important}',self.rules)
        cfg=app.build_ui().get_config_file()
        actions=next(c for c in cfg['components'] if c['props'].get('elem_id')=='audition-save-actions')
        self.assertIn('studio-presence',actions['props']['elem_classes'])
    def test_native_loader_and_existing_animations_are_not_disabled(self):
        self.assertNotRegex(self.rules,r'(?:animation|transition)\s*:\s*none')
        self.assertNotRegex(self.rules,r'\.studio-audio-output>\.wrap:not\(\.hide\)\s*\{[^}]*display\s*:\s*none')
        self.assertIn('>:not(.wrap){visibility:hidden',self.rules)

if __name__=='__main__':unittest.main()
