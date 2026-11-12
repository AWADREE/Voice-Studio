"""Multiple layout contracts: separate sections and stable native audio surfaces."""
from pathlib import Path
import unittest
import app

class ClipAlignmentLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=app.build_ui().get_config_file()
        cls.components={c['id']:c for c in cls.config['components']}
        cls.named={c['props']['elem_id']:c['id'] for c in cls.config['components'] if c['props'].get('elem_id')}
        cls.parents={}
        def visit(node,parent=None):
            cls.parents[node['id']]=parent
            for child in node.get('children',[]):visit(child,node['id'])
        visit(cls.config['layout'])
        cls.css=(Path(app.ROOT)/'theme.css').read_text(encoding='utf-8-sig')
    def ancestors(self,component_id):
        result=[]
        while component_id in self.parents:
            component_id=self.parents[component_id]
            if component_id is None:break
            result.append(component_id)
        return result
    def test_editor_and_controls_are_siblings_with_separate_listen_section(self):
        n=self.named
        self.assertEqual(self.parents[n['clip-editor']],n['generate-panel'])
        self.assertEqual(self.parents[n['generate-top-controls']],n['generate-panel'])
        self.assertNotIn(n['generate-top-controls'],self.ancestors(n['clip-editor']))
        self.assertIn(n['generate-top-controls'],self.ancestors(n['clip-import']))
        self.assertIn(n['commentary-mode-tabs'],self.ancestors(n['clip-import']))
        self.assertEqual(self.parents[n['listen-top-controls']],n['listen-panel'])
        self.assertEqual(self.parents[n['batch-output']],n['listen-panel'])
        self.assertNotIn(n['generate-panel'],self.ancestors(n['batch-output']))
        self.assertIn('batch-status',n)
        self.assertIn('#production-workspace:not(.multiple-mode) :is(#batch-status,#batch-output)',self.css)
    def test_importer_and_editor_have_distinct_templates_and_guard(self):
        importer=(Path(app.ROOT)/'clip-import.html').read_text()
        editor=(Path(app.ROOT)/'clip-editor.html').read_text()
        self.assertIn('clip-source',importer)
        self.assertNotIn('clip-list',importer)
        self.assertIn('clip-list',editor)
        self.assertNotIn('clip-source',editor)
        guard=(Path(app.ROOT)/'generation-guard.js').read_text()
        self.assertIn("getElementById('clip-import')",guard)
        self.assertIn('importer.inert=false',guard)
        coordinator=(Path(app.ROOT)/'clip-editor.js').read_text()
        self.assertIn('function bindImport()',coordinator)
        self.assertIn('if(bindImport())importMount.disconnect()',coordinator)
    def test_full_loading_selectors_follow_real_audio_ancestry(self):
        n=self.named
        audio=[c['id'] for c in self.config['components'] if c['type']=='audio' and self.parents.get(c['id'])==n['listen-top-controls']]
        self.assertEqual(len(audio),1)
        self.assertNotIn('#listen-panel:has(>.studio-audio-output',self.css)
        self.assertIn('#listen-top-controls:has(>.studio-audio-output>.wrap:not(.hide))>',self.css)
        self.assertIn('#listen-panel:has(#listen-top-controls>.studio-audio-output>.wrap:not(.hide))>#batch-output',self.css)
        self.assertIn('body:has(#voice-mode-workspace.design-mode) #production-workspace:not(.multiple-mode) #listen-panel:has(#listen-top-controls>.studio-audio-output>.wrap:not(.hide))>#audition-save-actions',self.css)
        self.assertIn('#listen-top-controls>.studio-audio-output:has(>.wrap:not(.hide))',self.css)
    def test_mobile_controls_use_separate_tracks_without_specificity_conflict(self):
        # The wide :is rule must not force both controls onto row 1. A mobile
        # inherited variable switches only Listen while preserving natural height.
        self.assertIn('#production-workspace.multiple-mode #generate-top-controls {grid-row:1;}',self.css)
        self.assertIn('#production-workspace.multiple-mode #listen-top-controls {grid-row:var(--listen-control-track,1);}',self.css)
        mobile=self.css[self.css.index('@media(max-width:1299px){\n #production-workspace.multiple-mode'):]
        self.assertIn('--listen-control-track:2;',mobile.split('\n}',1)[0])
        self.assertNotIn(':is(#generate-top-controls,#listen-top-controls) {grid-row:1',self.css)

    def test_shared_track_overlays_only_enable_real_interactive_content(self):
        # Gradio injects invisible, full-span loading trackers into both hosts.
        # Re-enabling arbitrary direct children makes those intercept top controls.
        self.assertNotIn('#clip-editor > * {pointer-events:auto;',self.css)
        self.assertNotIn('#batch-output > * {pointer-events:auto;',self.css)
        self.assertIn('#clip-editor :is(.clip-row,.clip-add) {pointer-events:auto;}',self.css)
        self.assertIn('#batch-output .batch-clip {pointer-events:auto;}',self.css)
        self.assertIn('#clip-editor {display:grid!important;grid-template-rows:subgrid;grid-row:1/-1;grid-column:1;pointer-events:none;',self.css)
        self.assertIn('#batch-output {display:grid!important;grid-template-rows:subgrid;grid-row:1/-1;grid-column:1;gap:20px!important;pointer-events:none;',self.css)

    def test_layout_has_shared_tracks_without_geometry_measurement(self):
        js=(Path(app.ROOT)/'clip-alignment.js').read_text()
        self.assertIn('grid-template-rows:subgrid',self.css)
        self.assertIn('@media(max-width:1299px)',self.css)
        self.assertIn("matchMedia('(max-width: 1299px)')",js)
        self.assertNotIn('getBoundingClientRect',js)
        self.assertNotIn('ResizeObserver',js)
        self.assertNotIn('appendChild(card)',js)

if __name__=='__main__':unittest.main()
