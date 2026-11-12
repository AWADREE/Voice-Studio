import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import soundfile as sf
import combine_clips as combine

class TimelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.output=self.root/'output';self.rate=100
    def clip(self, values, start=0, index=1, rate=None):
        path=self.root/f'input-{index}.wav'
        sf.write(path,np.asarray(values,dtype=np.float64),rate or self.rate,subtype='DOUBLE')
        return {'audio':str(path),'minutes':start//60,'seconds':start%60,'index':index}
    def combine(self,clips,duration=4,**extra):
        return combine.combine_timeline({'clips':clips,**extra},duration//60,duration%60,self.output)
    def test_exact_positions_silence_and_duration(self):
        a=self.clip(np.full(50,.25),1,1);b=self.clip(np.full(100,.5),3,2)
        originals={c['audio']:Path(c['audio']).read_bytes() for c in (a,b)}
        result=self.combine([a,b],5);audio,rate=sf.read(result['audio'])
        self.assertEqual(rate,100);self.assertEqual(audio.shape,(500,))
        np.testing.assert_array_equal(audio[:100],0);np.testing.assert_array_equal(audio[100:150],.25)
        np.testing.assert_array_equal(audio[150:300],0);np.testing.assert_array_equal(audio[300:400],.5)
        np.testing.assert_array_equal(audio[400:],0)
        self.assertEqual(sf.info(result['audio']).subtype,'PCM_24');self.assertEqual(result['gain'],1)
        for p,data in originals.items():self.assertEqual(Path(p).read_bytes(),data)
    def test_overlap_adds_and_whole_track_gain_prevents_clipping(self):
        a=self.clip(np.full(200,.75),0,1);b=self.clip(np.full(100,.75),1,2)
        result=self.combine([a,b],3);audio,_=sf.read(result['audio'])
        self.assertEqual(result['peak_before_gain'],1.5);self.assertLess(result['gain'],1)
        np.testing.assert_allclose(audio[:100],.75*result['gain'],atol=2**-23)
        np.testing.assert_allclose(audio[100:200],1.5*result['gain'],atol=2**-23)
        np.testing.assert_array_equal(audio[200:],0);self.assertIn('whole-track gain',result['status'])
    def test_stereo_and_negative_overlap(self):
        a=self.clip(np.tile([-.75,.25],(100,1)),1,1);b=self.clip(np.tile([-.75,.25],(100,1)),1,2)
        result=self.combine([a,b],2);audio,_=sf.read(result['audio'],always_2d=True)
        self.assertEqual(audio.shape,(200,2));self.assertEqual(result['channels'],2)
        np.testing.assert_allclose(audio[100:],np.tile([-1.5,.5],(100,1))*result['gain'],atol=2**-23)
    def test_overrun_fails_without_output_and_gives_required_duration(self):
        clip=self.clip(np.ones(101)*.2,3,7)
        with self.assertRaisesRegex(ValueError,r'Clip 7 ends at 4.010.*at least 0:05'):
            self.combine([clip],4)
        self.assertFalse(self.output.exists())
    def test_multiple_overruns_report_the_longest_required_duration(self):
        a=self.clip(np.full(250,.2),3,1)
        b=self.clip(np.full(210,.2),8,2)
        with self.assertRaisesRegex(ValueError,r'Clip 1 ends at 5.500.*Clip 2 ends at 10.100.*at least 0:11'):
            self.combine([a,b],4)
        self.assertFalse(self.output.exists())
    def test_invalid_durations(self):
        clip=self.clip([.2]*10)
        for minutes,seconds in [(0,0),(-1,2),(1,-1),(1,60),(1,.5),(True,0),(0,float('nan')),(9999,59),(10000,0),('bad',0)]:
            with self.subTest(minutes=minutes,seconds=seconds),self.assertRaises(ValueError):
                combine.combine_timeline({'clips':[clip]},minutes,seconds,self.output)
    def test_rejects_inconsistent_rate_or_channels(self):
        a=self.clip([.2]*10,0,1)
        for b in (self.clip([.2]*20,0,2,200),self.clip(np.full((10,2),.2),0,3)):
            with self.assertRaisesRegex(ValueError,'sample rate or channel count'):
                self.combine([a,b])
        self.assertFalse(self.output.exists())
    def test_nonfinite_and_empty_audio_fail(self):
        for values in ([float('nan')],[float('inf')],[]):
            clip=self.clip(values)
            with self.subTest(values=values),self.assertRaises(ValueError):self.combine([clip])
        self.assertFalse(self.output.exists())
    def test_partial_batch_is_explicit_and_new_outputs_never_replace(self):
        clip=self.clip([.2]*10)
        a=self.combine([clip],error='Second failed',requested_clips=2)
        b=self.combine([clip])
        self.assertTrue(a['partial']);self.assertIn('1 of 2',a['status']);self.assertFalse(b['partial'])
        self.assertNotEqual(a['audio'],b['audio']);self.assertTrue(Path(a['audio']).exists())
    def test_write_failure_removes_partial(self):
        clip=self.clip([.2]*10)
        with patch.object(combine.os,'fsync',side_effect=OSError('disk failure')):
            with self.assertRaisesRegex(OSError,'disk failure'):self.combine([clip])
        self.assertEqual(list(self.output.iterdir()),[])
    def test_no_full_timeline_allocation(self):
        clip=self.clip([.2]*10,5)
        real_zeros=np.zeros;sizes=[]
        def bounded(shape,*args,**kwargs):
            sizes.append(shape[0]);return real_zeros(shape,*args,**kwargs)
        with patch.object(combine,'BLOCK_FRAMES',37),patch.object(combine.np,'zeros',side_effect=bounded):
            result=self.combine([clip],10)
        self.assertGreater(len(sizes),2);self.assertLessEqual(max(sizes),37)
        self.assertEqual(sf.info(result['audio']).frames,1000)
    def test_disk_and_file_size_preflight(self):
        clip=self.clip([.2]*10)
        with patch.object(combine.shutil,'disk_usage',return_value=type('Disk',(),{'free':0})()):
            with self.assertRaisesRegex(ValueError,'free disk'):self.combine([clip])
        self.assertEqual(list(self.output.iterdir()),[])
        with patch.object(combine,'MAX_WAV_BYTES',10):
            with self.assertRaisesRegex(ValueError,'file-size'):self.combine([clip])
    def test_bad_or_missing_clip_data(self):
        for clips in ([],None,[{}],[{'audio':'missing.wav','minutes':0,'seconds':0}]):
            with self.subTest(clips=clips),self.assertRaises(ValueError):
                combine.combine_timeline({'clips':clips},0,1,self.output)

if __name__=='__main__':unittest.main()
