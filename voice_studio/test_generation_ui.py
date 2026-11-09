import unittest
import app
class GenerationUiTests(unittest.TestCase):
 def test_busy_and_finished_controls(self):
  button,notice=app.generation_started();self.assertFalse(button['interactive']);self.assertTrue(notice['visible']);self.assertIn('role="status"',notice['value'])
  button,notice=app.generation_finished();self.assertTrue(button['interactive']);self.assertFalse(notice['visible'])
 def test_shared_controls_before_tabs(self):
  source=open(app.__file__,encoding='utf-8').read().split('def compose_controls')[1].split('def output_controls')[0]
  self.assertLess(source.index("label='Delivery instruction"),source.index("with gr.Tabs"))
  self.assertLess(source.index("label='Language'"),source.index("with gr.Tabs"))
  self.assertLess(source.index('generation_settings_controls()'),source.index("with gr.Tabs"))
  self.assertIn("gr.Accordion('Generation settings'",source)
 def test_native_players_and_always_cleanup(self):
  source=open(app.__file__,encoding='utf-8').read()
  self.assertIn("player=gr.Audio(",source);self.assertIn('player.stop(',source)
  self.assertIn('workflow_completed,inputs=',source)
  self.assertNotIn('.success(workflow_completed',source)
 def test_failure_preserves_outputs_and_reports_error(self):
  from unittest.mock import patch
  with patch.object(app,'generate_commentary_mode',side_effect=RuntimeError('test failure')):
   result=app.generate_commentary_ui('single')
  self.assertEqual(len(result),15)
  self.assertIn('test failure',result[2]['value'])
  self.assertEqual(result[0],app.gr.skip())
 def test_single_visibility_is_owned_by_tab_not_server(self):
  from pathlib import Path
  source=Path(app.__file__).read_text(encoding='utf-8')
  callbacks=source.split('single_tab.select')[1].split('button = gr.Button')[0]
  self.assertNotIn('visible=',callbacks)
  self.assertNotIn('outputs=[mode,text]',callbacks)
