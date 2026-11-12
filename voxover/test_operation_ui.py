import unittest
from types import SimpleNamespace
import gradio as gr
import app

class OperationUiTests(unittest.TestCase):
 def callbacks(self,action,**kwargs):
  with gr.Blocks() as ui:
   button=gr.Button('Save');value=gr.Textbox();status=gr.Markdown()
   app.bind_busy_action(button,action,[],[value,status],'Save','Saving voice...',1,**kwargs)
  return {f.fn.__name__:f.fn for f in ui.fns.values() if f.fn},ui.config
 def test_success_and_restore(self):
  f,cfg=self.callbacks(lambda:('value','done'))
  self.assertFalse(f['start'](None)[0]['interactive'])
  self.assertTrue(f['start'](None)[2])
  self.assertEqual(f['execute'](request=None),('value','done'))
  self.assertEqual(f['finish']()[0]['value'],'Save')
  self.assertTrue(f['finish']()[0]['interactive'])
  self.assertTrue(all(d['trigger_mode']=='once' for d in cfg['dependencies']))
 def test_failure_preserves_outputs_and_restores(self):
  def fail():raise RuntimeError('synthetic')
  f,_=self.callbacks(fail)
  result=f['execute'](request=None)
  self.assertEqual(result[0],gr.skip());self.assertIn('synthetic',result[1]['value'])
  self.assertTrue(f['finish']()[0]['interactive'])
 def test_request_adapter(self):
  request=SimpleNamespace(session_hash='one')
  f,_=self.callbacks(None,adapter=lambda args,r:('value',r.session_hash))
  self.assertEqual(f['execute'](request=request),('value','one'))
 def test_clone_request_position_and_cleanup(self):
  from unittest.mock import patch
  original=['a','b','status',None,'',False,None,None,None,None,None,None,False,None,None]
  with patch.object(app,'clone_reference_selected',return_value=tuple(original)) as clone:
   result=app.clone_submission(tuple(range(12)),'request')
  self.assertEqual(clone.call_args.args,(*range(9),'request',9,10,11))
  self.assertEqual(len(result),17)
  self.assertTrue(result[0]['visible']);self.assertFalse(result[-1]['visible'])
 def test_gradio_injects_request_before_variadic_inputs(self):
  from gradio.helpers import special_args
  request=gr.Request(session_hash='browser-session')
  f,_=self.callbacks(None,adapter=lambda args,r:(args[0],r.session_hash))
  inputs=special_args(f['execute'],['payload'],request=request)[0]
  self.assertEqual(f['execute'](*inputs),('payload','browser-session'))
 def test_single_output_serialization(self):
  with gr.Blocks() as ui:
   button=gr.Button('Unload');status=gr.Markdown()
   app.bind_busy_action(button,lambda:'done',[],[status],'Unload','Unloading model...',0)
  execute=next(f.fn for f in ui.fns.values() if f.fn and f.fn.__name__=='execute')
  self.assertEqual(execute(None),'done')
