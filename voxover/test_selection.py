import unittest
from voice_selection import VoiceSelection
class SelectionTests(unittest.TestCase):
 def test_clone_replaces_and_upload_replaces(self):
  s=VoiceSelection();s.select('a','old');ticket=s.begin('a');self.assertTrue(s.commit('a',ticket,'clone'));s.select('a','new');self.assertEqual(s.sessions['a']['path'],'new')
 def test_later_upload_beats_inflight_clone(self):
  s=VoiceSelection();t=s.begin('a');s.select('a','later');self.assertFalse(s.commit('a',t,'clone'));self.assertEqual(s.sessions['a']['path'],'later')
 def test_failed_clone_keeps_prior_and_sessions_isolated(self):
  s=VoiceSelection();s.select('a','prior');s.begin('a');s.select('b','other');self.assertEqual(s.sessions['a']['path'],'prior')
 def test_latest_clone_request_wins(self):
  s=VoiceSelection();a=s.begin('a');b=s.begin('a');self.assertFalse(s.commit('a',a,'first'));self.assertTrue(s.commit('a',b,'second'))
if __name__=='__main__':unittest.main()
