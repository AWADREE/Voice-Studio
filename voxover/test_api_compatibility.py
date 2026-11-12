"""Existing public API contracts, captured from origin/main before batch UI work."""
import unittest
from unittest.mock import patch
import app

class LegacyApiContractTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  with patch.object(app,'load_model') as load:
   cls.ui=app.build_ui()
   cls.info=cls.ui.get_api_info()['named_endpoints']
  load.assert_not_called()

 def check_endpoint(self,name,names,outputs):
  info=self.info[name]
  self.assertEqual([p['parameter_name'] for p in info['parameters']],names)
  self.assertEqual(len(info['returns']),outputs)

 def test_save_voice_named_parameters(self):
  self.check_endpoint('/save_voice',['audio','transcript','include_transcript'],2)

 def test_clone_reference_named_parameters_and_return_arity(self):
  self.check_endpoint('/clone_reference_preview',['audio','transcript','include','text','instruction','language','seed','release']+[f'param_{i}' for i in range(9,19)],12)

 def test_save_preview_named_parameters(self):
  self.check_endpoint('/save_preview_voice',['correction','use_correction'],2)

 def test_single_generate_legacy_contract(self):
  self.check_endpoint('/generate',[f'param_{i}' for i in range(17)],8)

 def test_unload_endpoints_are_retained(self):
  self.check_endpoint('/unload',[],1)
  self.check_endpoint('/unload_1',[],1)

 def test_ui_busy_wrappers_are_not_public_api(self):
  exposed=[f for f in self.ui.fns.values() if f.fn and f.fn.__name__=='execute' and f.api_name is not False]
  self.assertEqual(exposed,[])

if __name__=='__main__':unittest.main()
