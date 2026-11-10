import tempfile
from pathlib import Path
import unittest
import numpy as np
import soundfile as sf
import gradio as gr
import app
import combine_clips

class MinimumDurationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
    def clip(self,frames,start=0,index=1,rate=100):
        path=self.root/f'{index}.wav';sf.write(path,np.full(frames,.1),rate)
        return {'id':str(index),'index':index,'audio':str(path),'minutes':start//60,'seconds':start%60,'text':str(index)}
    def test_ceiling_longest_end_not_sum_or_last_clip(self):
        batch={'clips':[self.clip(101,59),self.clip(200,1,2)]}
        self.assertEqual(combine_clips.minimum_timeline_seconds(batch),61)
        batch['clips'][0]=self.clip(100,59)
        self.assertEqual(combine_clips.minimum_timeline_seconds(batch),60)
    def test_matches_export_boundary_and_partial_batch(self):
        batch={'clips':[self.clip(1,4)],'requested_clips':2,'complete':False}
        minimum=combine_clips.minimum_timeline_seconds(batch)
        self.assertEqual(minimum,5)
        with self.assertRaisesRegex(ValueError,'at least 0:05'):
            combine_clips.combine_timeline(batch,0,minimum-1,self.root/'out')
        self.assertEqual(combine_clips.combine_timeline(batch,0,minimum,self.root/'out')['duration_seconds'],minimum)
    def test_invalid_audio_and_impossible_timeline_never_advertise_minimum(self):
        a=self.clip(100);b=self.clip(100,index=2,rate=200)
        with self.assertRaisesRegex(ValueError,'sample rate'):
            combine_clips.minimum_timeline_seconds({'clips':[a,b]})
        for clips in ([],[self.clip(0,index=3)],[self.clip(100,86400,index=4)]):
            with self.subTest(clips=clips),self.assertRaises(ValueError):
                combine_clips.minimum_timeline_seconds({'clips':clips})
    def test_status_tracks_current_timing_and_source_replacement(self):
        batch={'clips':[self.clip(101,0)],'requested_clips':1}
        rows=[{'id':'1','minutes':1,'seconds':0,'text':'1'}]
        self.assertIn('1:02',app.timeline_minimum_status(batch,rows))
        batch['clips'][0]=self.clip(350,0)
        self.assertIn('1:04',app.timeline_minimum_status(batch,rows))
        self.assertEqual(batch['clips'][0]['minutes'],0)
        rows[0]['text']='changed'
        self.assertIn('commentary changed',app.timeline_minimum_status(batch,rows))
        self.assertNotIn('Minimum total duration:',app.timeline_minimum_status(batch,rows))
        self.assertEqual(app.timeline_minimum_status(None,rows),'')
    def test_status_below_button_and_reacts_to_both_sources(self):
        with gr.Blocks() as ui:
            result=gr.State(None);workflow=gr.Textbox('generate');mode=gr.State('batch');rows=gr.HTML([])
            app.render_timeline_combine(result,workflow,mode,rows)
        cfg=ui.get_config_file()
        status=next(c for c in cfg['components'] if c['props'].get('elem_id')=='timeline-minimum-status')
        f=next(f for f in ui.fns.values() if f.fn and f.fn.__name__=='timeline_minimum_status')
        self.assertEqual(f.inputs,[result,rows]);self.assertEqual(f.outputs[0]._id,status['id'])
        dep=next(d for d in cfg['dependencies'] if status['id'] in d['outputs'])
        self.assertEqual({(i,event) for i,event in dep['targets']},{(result._id,'change'),(rows._id,'change')})
        ordered=[c['props'] for c in cfg['components']]
        button=next(i for i,p in enumerate(ordered) if p.get('value')=='Combine')
        self.assertEqual(ordered[button+1].get('elem_id'),'timeline-minimum-status')
    def test_duration_default_rounds_up_and_rolls_into_minutes(self):
        batch={'clips':[self.clip(101,59)]}
        self.assertEqual(app.timeline_duration_default(batch),(1,1))
        batch['clips'][0]=self.clip(100,59)
        self.assertEqual(app.timeline_duration_default(batch),(1,0))
        batch['clips'][0]=self.clip(1,3599.5)
        self.assertEqual(app.timeline_duration_default(batch),(60,0))

    def test_duration_default_tracks_current_rows_and_new_audio(self):
        batch={'clips':[self.clip(101)],'requested_clips':1}
        rows=[{'id':'1','minutes':1,'seconds':0,'text':'1'}]
        self.assertEqual(app.timeline_duration_default(batch,rows),(1,2))
        batch['clips'][0]=self.clip(350)
        self.assertEqual(app.timeline_duration_default(batch,rows),(1,4))
        rows[0]['seconds']=59
        self.assertEqual(app.timeline_duration_default(batch,rows),(2,3))
        rows[0]['seconds']=0
        rows[0]['minutes']=0
        self.assertEqual(app.timeline_duration_default(batch,rows),(0,4))

    def test_duration_default_preserves_user_input_and_unavailable_timing(self):
        batch={'clips':[self.clip(101)],'requested_clips':1}
        self.assertEqual(app.timeline_duration_default(batch,edited=True),(gr.skip(),gr.skip()))
        self.assertEqual(app.timeline_duration_default(None),(gr.skip(),gr.skip()))
        self.assertEqual(app.timeline_duration_default({'clips':[{'audio':'missing.wav'}]}),(gr.skip(),gr.skip()))
        rows=[{'id':'1','minutes':0,'seconds':0,'text':'changed'}]
        self.assertEqual(app.timeline_duration_default(batch,rows),(gr.skip(),gr.skip()))

    def test_duration_initializes_dict_and_state_inputs_without_combining(self):
        batch={'clips':[self.clip(101,59)]}
        for stateful in (False,True):
            with gr.Blocks() as ui:
                result=gr.State(None) if stateful else batch
                rows=gr.HTML(None)
                app.render_timeline_combine(result,gr.Textbox('generate'),gr.State('batch'),rows)
            cfg=ui.get_config_file()
            fields=[c for c in cfg['components'] if c['props'].get('label') in
                    ('Total duration: minutes','Total duration: seconds')]
            self.assertEqual([c['props']['value'] for c in fields],[0,0] if stateful else [1,1])
            refresh=next(f for f in ui.fns.values() if f.fn and f.fn.__name__=='calculate_duration_candidate')
            edited=refresh.inputs[2]
            self.assertFalse(edited.value)
            self.assertEqual(len(refresh.outputs),1)
            apply=next(d for d in cfg['dependencies'] if d.get('js')==app.TIMELINE_DURATION_APPLY_JS)
            self.assertEqual(apply['outputs'],[c['id'] for c in fields])
            self.assertEqual(apply['inputs'][0],refresh.outputs[0]._id)
            self.assertEqual(refresh.fn(batch,None,False),[1,1])
            edit=next(f for f in ui.fns.values() if edited in f.outputs)
            self.assertTrue(edit.fn())
            dependency=next(d for d in cfg['dependencies'] if d['outputs']==[edited._id])
            self.assertEqual(set(map(tuple,dependency['targets'])),{(c['id'],'input') for c in fields})
            # A deliberate zero or cleared field triggers input, never inferred from
            # its numeric value. Server-generated defaults use change, not input.
            self.assertEqual(refresh.fn(batch,None,edit.fn()),[gr.skip(),gr.skip()])
            self.assertEqual(dependency['js'],app.TIMELINE_DURATION_EDIT_JS)
            css=Path(app.ROOT/'theme.css').read_text(encoding='utf-8-sig')
            self.assertIn('#timeline-duration-fields > .form {gap:16px!important;}',css)

    def test_multiple_listen_skin_excludes_empty_shared_track(self):
        css=Path(app.ROOT/'theme.css').read_text(encoding='utf-8-sig')
        self.assertIn('#production-workspace.multiple-mode #listen-panel {background:transparent!important;',css)
        self.assertIn('#production-workspace.multiple-mode #listen-top-controls {background:rgba(7,20,33,.88)!important;',css)

if __name__=='__main__':unittest.main()
