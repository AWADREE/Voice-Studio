import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
import soundfile as sf
import gradio as gr
import app

class CombineUiTests(unittest.TestCase):
    def test_controls_only_exist_after_generated_clips(self):
        for result, expected in [(None,False),({'clips':[]},False),({'clips':[{'audio':'one.wav'}]},True)]:
            with gr.Blocks() as ui:
                workflow=gr.Textbox(value='generate');mode=gr.State('batch')
                app.render_timeline_combine(result,workflow,mode)
            config=ui.get_config_file()
            self.assertEqual(any(c['props'].get('elem_id')=='timeline-combine' for c in config['components']),expected)
            if expected:
                labels={c['props'].get('label'):c['props'] for c in config['components']}
                self.assertTrue(labels['Combined audio']['visible'])
                self.assertIsNone(labels['Combined audio'].get('value'))
                self.assertTrue('Total duration: minutes' in labels)
                self.assertTrue('Total duration: seconds' in labels)
                download=next(c for c in config['components'] if c['props'].get('label')=='Download combined WAV')
                self.assertTrue(download['props']['visible'])
                self.assertIsNone(download['props'].get('value'))
                media=next(c for c in config['components'] if c['props'].get('elem_id')=='combined-timeline-result')
                self.assertTrue(media['props']['visible'])
    def test_exact_output_and_failure_clear_previous_media(self):
        with tempfile.TemporaryDirectory() as folder:
            wav=Path(folder)/'clip.wav';sf.write(wav,np.ones(24000)*.25,24000,subtype='PCM_24')
            result={'clips':[{'audio':str(wav),'minutes':0,'seconds':2,'index':1}]}
            with patch.object(app,'OUTPUTS',Path(folder)/'output'),patch.object(app,'authorize_generated_file') as authorize:
                good=app.combine_generated_clips(result,0,4,'generate','batch')
                self.assertEqual(len(good),3);self.assertEqual(good[0],good[1])
                audio,sr=sf.read(good[0]);self.assertEqual(len(audio),4*sr)
                authorize.assert_called_once()
                bad=app.combine_generated_clips(result,0,2,'generate','batch')
                self.assertEqual(bad[:2],(None,None))
                self.assertIn('No audio was truncated',bad[2])
    def test_other_modes_cannot_combine(self):
        for workflow,mode in [('clone','batch'),('design','single'),('generate','single')]:
            with patch('combine_clips.combine_timeline') as combine:
                result=app.combine_generated_clips(None,0,10,workflow,mode)
                combine.assert_not_called();self.assertEqual(result[:2],(None,None))
    def test_duration_edits_clear_output_and_start_disables_fields(self):
        with gr.Blocks() as ui:
            app.render_timeline_combine({'clips':[{'audio':'x.wav'}]},gr.Textbox(value='generate'),gr.State('batch'))
        funcs={f.fn.__name__:f.fn for f in ui.fns.values() if f.fn}
        result=funcs['start_combine']()
        self.assertTrue(all(not x['interactive'] for x in result[:3]))
        self.assertEqual(result[3:5],(None,None))
        self.assertEqual(len(result),6)
        self.assertTrue(all(x['interactive'] for x in funcs['finish_combine']()))
        self.assertEqual(funcs['clear_combined'](),(None,None,''))

    def test_data_derived_media_visibility_and_static_group_not_event_output(self):
        css=Path(app.ROOT/'theme.css').read_text(encoding='utf-8-sig')
        self.assertRegex(css,r'#combined-timeline-result:not\(:has\(a\.download-link\[href\]\)\)\s*\{[^}]*display\s*:\s*none')
        with gr.Blocks() as ui:
            app.render_timeline_combine(gr.State(None),gr.Textbox(value='generate'),gr.State('batch'))
        config=ui.get_config_file()
        media=next(c for c in config['components'] if c['props'].get('elem_id')=='combined-timeline-result')
        self.assertTrue(media['props']['visible'])
        self.assertFalse(any(media['id'] in d['outputs'] for d in config['dependencies']))
        clear_events=[f for f in ui.fns.values() if f.fn and f.fn.__name__=='clear_combined']
        self.assertEqual(len(clear_events),2,'duration edits and generated-batch changes both clear stale media')
        for event in clear_events:self.assertEqual(len(event.outputs),3)

if __name__=='__main__':unittest.main()
