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
    def test_exact_output_and_failure_preserves_previous_media(self):
        with tempfile.TemporaryDirectory() as folder:
            wav=Path(folder)/'clip.wav';sf.write(wav,np.ones(24000)*.25,24000,subtype='PCM_24')
            result={'clips':[{'audio':str(wav),'minutes':0,'seconds':2,'index':1}]}
            with patch.object(app,'OUTPUTS',Path(folder)/'output'),patch.object(app,'authorize_generated_file') as authorize:
                good=app.combine_generated_clips(result,0,4,'generate','batch')
                self.assertEqual(len(good),3);self.assertEqual(good[0],good[1])
                audio,sr=sf.read(good[0]);self.assertEqual(len(audio),4*sr)
                authorize.assert_called_once()
                bad=app.combine_generated_clips(result,0,2,'generate','batch')
                self.assertEqual(bad[:2],(gr.skip(),gr.skip()))
                self.assertTrue(Path(good[0]).is_file())
                self.assertIn('No audio was truncated',bad[2])
    def test_recombine_uses_current_editor_time_and_rejects_changed_text(self):
        with tempfile.TemporaryDirectory() as folder:
            wav=Path(folder)/'clip.wav';sf.write(wav,np.ones(100)*.25,100,subtype='PCM_24')
            original={'clips':[{'audio':str(wav),'minutes':0,'seconds':1,'index':1,'text':'hello'}], 'requested_clips':1}
            rows=[{'minutes':0,'seconds':3,'text':'hello'}]
            with patch.object(app,'OUTPUTS',Path(folder)/'out'),patch.object(app,'authorize_generated_file'):
                path,_,_=app.combine_generated_clips(original,0,5,'generate','batch',rows)
                audio,sr=sf.read(path);self.assertEqual(sr,100)
                np.testing.assert_array_equal(audio[:300],0)
                np.testing.assert_allclose(audio[300:400],.25,atol=2**-23)
                self.assertEqual(original['clips'][0]['seconds'],1)
                bad=app.combine_generated_clips(original,0,5,'generate','batch',[{'minutes':0,'seconds':3,'text':'changed'}])
                self.assertEqual(bad[:2],(gr.skip(),gr.skip()));self.assertIn('commentary changed',bad[2])
                missing=app.combine_generated_clips(original,0,5,'generate','batch',[])
                self.assertEqual(missing[:2],(gr.skip(),gr.skip()))

    def test_other_modes_cannot_combine(self):
        for workflow,mode in [('clone','batch'),('design','single'),('generate','single')]:
            with patch('combine_clips.combine_timeline') as combine:
                result=app.combine_generated_clips(None,0,10,workflow,mode)
                combine.assert_not_called();self.assertEqual(result[:2],(gr.skip(),gr.skip()))
    def test_start_disables_fields_without_touching_media(self):
        with gr.Blocks() as ui:
            app.render_timeline_combine({'clips':[{'audio':'x.wav'}]},gr.Textbox(value='generate'),gr.State('batch'))
        funcs={f.fn.__name__:f.fn for f in ui.fns.values() if f.fn}
        result=funcs['start_combine']()
        self.assertTrue(all(not x['interactive'] for x in result[:3]))
        self.assertEqual(result[3],'Combining generated clips...')
        self.assertEqual(len(result),4)
        self.assertTrue(all(x['interactive'] for x in funcs['finish_combine']()))

    def test_data_derived_media_visibility_and_static_group_not_event_output(self):
        css=Path(app.ROOT/'theme.css').read_text(encoding='utf-8-sig')
        self.assertRegex(css,r'#combined-timeline-result:not\(:has\(a\.download-link\[href\]\)\)\s*\{[^}]*display\s*:\s*none')
        with gr.Blocks() as ui:
            app.render_timeline_combine(gr.State(None),gr.Textbox(value='generate'),gr.State('batch'),gr.HTML([]))
        config=ui.get_config_file()
        media=next(c for c in config['components'] if c['props'].get('elem_id')=='combined-timeline-result')
        self.assertTrue(media['props']['visible'])
        self.assertFalse(any(media['id'] in d['outputs'] for d in config['dependencies']))
        media_ids={c['id'] for c in config['components'] if c['props'].get('label') in ('Combined audio','Download combined WAV')}
        writers=[f for f in ui.fns.values() if any(output._id in media_ids for output in f.outputs)]
        self.assertEqual([f.fn.__name__ for f in writers],['execute_combine'],
                         'Edits, batch changes and combine startup must not clear the last successful media.')

    def test_combine_between_unload_and_generated_batch_status(self):
        config=app.build_ui().get_config_file()
        components={c['id']:c for c in config['components']}
        ordered=[]
        def visit(node):
            if node['id'] in components:
                ordered.append(components[node['id']]['props'])
            for child in node.get('children',[]):visit(child)
        visit(config['layout'])
        unload=next(i for i,p in enumerate(ordered) if p.get('value')=='Unload model')
        combine=next(i for i,p in enumerate(ordered) if p.get('elem_id')=='timeline-combine')
        batch=next(i for i,p in enumerate(ordered) if p.get('elem_id')=='batch-output')
        self.assertLess(unload,combine)
        self.assertLess(combine,batch)

    def test_busy_operation_preserves_previous_media(self):
        import threading
        lock=threading.Lock()
        with lock,patch.object(app,'LOCK',lock):
            result=app.combine_generated_clips(None,0,10,'generate','batch')
        self.assertEqual(result[:2],(gr.skip(),gr.skip()))
        self.assertIn('Another operation',result[2])

    def test_export_failure_preserves_successful_file_and_media(self):
        with tempfile.TemporaryDirectory() as folder:
            wav=Path(folder)/'clip.wav';sf.write(wav,np.ones(100)*.25,100,subtype='PCM_24')
            result={'clips':[{'audio':str(wav),'minutes':0,'seconds':0,'index':1}]}
            output=Path(folder)/'output'
            with patch.object(app,'OUTPUTS',output):
                good=app.combine_generated_clips(result,0,2,'generate','batch')
                previous=Path(good[0]).read_bytes()
                with patch('combine_clips.os.fsync',side_effect=OSError('disk failure')):
                    bad=app.combine_generated_clips(result,0,3,'generate','batch')
            self.assertEqual(bad[:2],(gr.skip(),gr.skip()))
            self.assertIn('disk failure',bad[2])
            self.assertEqual(Path(good[0]).read_bytes(),previous)
            self.assertEqual(list(output.iterdir()),[Path(good[0])])

    def test_partial_batch_keeps_editor_identity_and_rejects_reordered_text(self):
        generated={'requested_clips':2,'clips':[{'index':1,'text':'first','minutes':0,'seconds':1,'audio':'a.wav'}]}
        rows=[{'minutes':1,'seconds':2,'text':'first'},{'minutes':0,'seconds':4,'text':'second'}]
        updated=app.current_batch_timing(generated,rows)
        self.assertEqual(updated['clips'][0]['audio'],'a.wav')
        self.assertEqual((updated['clips'][0]['minutes'],updated['clips'][0]['seconds']),(1,2))
        self.assertEqual(generated['clips'][0]['seconds'],1)
        with self.assertRaisesRegex(ValueError,'commentary changed'):
            app.current_batch_timing(generated,list(reversed(rows)))
        with self.assertRaisesRegex(ValueError,'number of clips changed'):
            app.current_batch_timing(generated,rows[:1])

if __name__=='__main__':unittest.main()
