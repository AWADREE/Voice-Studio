import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from storage_locations import StorageLocations,require_local_ui
class StorageTests(unittest.TestCase):
 def test_persistence_and_cancel(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);s=StorageLocations(root);target=root/'audio';v=root/'voices'
   self.assertTrue(s.set('output',target));self.assertTrue(s.set('voice',v));self.assertFalse(s.set('output',''))
   target.joinpath('test.wav').write_bytes(b'RIFF');v.joinpath('test.pt').write_bytes(b'test')
   reloaded=StorageLocations(root);self.assertEqual(reloaded.values['output'],target);self.assertEqual(reloaded.values['voice'],v)
   self.assertEqual(target.joinpath('test.wav').read_bytes(),b'RIFF')
 def test_reject_remote_and_cross_origin(self):
  for host,origin in [('8.8.8.8','http://127.0.0.1:8003'),('127.0.0.1','https://evil.example'),('127.0.0.1','http://127.0.0.1:9000')]:
   with self.assertRaises(ValueError):require_local_ui(SimpleNamespace(client=SimpleNamespace(host=host),headers={'origin':origin,'host':'127.0.0.1:8003'}))
  require_local_ui(SimpleNamespace(client=SimpleNamespace(host='127.0.0.1'),headers={'origin':'http://127.0.0.1:8003','host':'127.0.0.1:8003'}))
 def test_paths(self):
  for p in ['relative',r'\\server\share']:
   with self.assertRaises(ValueError):StorageLocations.validate(p)
if __name__=='__main__':unittest.main()
