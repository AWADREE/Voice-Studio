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

class VoicePickerLoadingTests(unittest.TestCase):
 def test_generation_does_not_target_voice_picker_or_its_status(self):
  config=app.build_ui().get_config_file()
  components={c['id']:c for c in config['components']}
  event=next(d for d in config['dependencies'] if d.get('api_name')=='generate_commentary')
  outputs=[components[i]['props'] for i in event['outputs']]
  self.assertFalse(any(p.get('label')=='Voice file (.pt)' or p.get('elem_id')=='selected-voice-status' for p in outputs))
  self.assertTrue(any(p.get('label')=='Generated audio' for p in outputs))
 def test_error_returns_correct_number_of_outputs(self):
  from unittest.mock import patch
  with patch.object(app,'generate_workflow_mode',side_effect=RuntimeError('failure')):
   result=app.generate_workflow_ui(None)
  self.assertEqual(len(result),17)
  self.assertIn('failure',result[2]['value'])

class DesignVoiceDownloadTests(unittest.TestCase):
 def test_visibility_requires_current_design_sample_and_not_busy(self):
  design={'source':'design_sample'}
  self.assertTrue(app.design_download_visibility(design,'design',False)['visible'])
  self.assertFalse(app.design_download_visibility(design,'clone',False)['visible'])
  self.assertFalse(app.design_download_visibility({'source':'clone_reference'},'design',False)['visible'])
  self.assertFalse(app.design_download_visibility(None,'design',False)['visible'])
  self.assertFalse(app.design_download_visibility(design,'design',True)['interactive'])
 def test_download_passes_corrected_transcript_and_rejects_other_sources(self):
  from unittest.mock import patch
  preview={'source':'design_sample'}
  with patch.object(app,'save_preview_corrected',return_value=('file','status')) as save:
   self.assertEqual(app.save_designed_voice(preview,'design',False,'actual words',True),('file','status'))
   save.assert_called_once_with(preview,False,'actual words',True)
  with self.assertRaises(Exception): app.save_designed_voice({'source':'clone_reference'},'design',False,'',False)
  with self.assertRaises(Exception): app.save_designed_voice(preview,'generate',False,'',False)
 def test_save_button_is_gated_by_correction_and_design_button_is_inside_design(self):
  config=app.build_ui().get_config_file()
  elements={c['props'].get('elem_id'):c for c in config['components'] if c['props'].get('elem_id')}
  self.assertIn('design-download-voice',elements)
  self.assertFalse(elements['design-download-voice']['props']['visible'])
  from pathlib import Path
  css=(Path(app.ROOT)/'theme.css').read_text(encoding='utf-8-sig')
  self.assertIn('#save-corrected-audition{display:none!important}',css)
  self.assertIn('#listen-panel:has(#edit-transcript input:checked) #save-corrected-audition{display:flex!important}',css)
