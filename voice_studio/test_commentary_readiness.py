import unittest
import app
class ReadinessTests(unittest.TestCase):
 def ready(self,mode='single',rows=None,voice='test.pt',text='Hello',busy=False,cloning=False):return app.commentary_ready(mode,rows,voice,text,busy,cloning,*app.SETTING_DEFAULTS)
 def test_single_required_inputs(self):
  self.assertFalse(self.ready(voice=None));self.assertFalse(self.ready(text=' '));self.assertFalse(self.ready(text='a'*2001));self.assertFalse(self.ready(voice='wrong.wav'));self.assertTrue(self.ready())
 def test_batch_required_inputs(self):
  for rows in [None,[],[{'minutes':0,'seconds':60,'text':'ok'}],[{'minutes':0,'seconds':0,'text':''}]]:self.assertFalse(self.ready(mode='batch',rows=rows))
  self.assertTrue(self.ready(mode='batch',rows=[{'minutes':0,'seconds':5,'text':'ok'}],text=''))
 def test_busy_clone_and_bad_settings(self):
  self.assertFalse(self.ready(busy=True));self.assertFalse(self.ready(cloning=True))
  self.assertFalse(app.commentary_ready('single',None,'v.pt','ok',False,False,1))
 def test_completion_revalidates_changed_inputs(self):
  self.assertFalse(app.generation_completed('single',None,None,'hello',False,*app.SETTING_DEFAULTS)[0]['interactive'])
  self.assertTrue(app.generation_completed('single',None,'voice.pt','hello',False,*app.SETTING_DEFAULTS)[0]['interactive'])
 def test_no_wait_or_forbidden_cursor_styles(self):
  from pathlib import Path
  for path in app.ROOT.glob('*.css'):
   css=path.read_text(encoding='utf-8');self.assertNotIn('cursor:wait',css);self.assertNotIn('cursor:not-allowed',css)
