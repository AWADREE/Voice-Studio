import copy
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import soundfile as sf
from batch_generation import timestamp_to_frames, validate_entries
from clip_timing import align_clip_timestamps, generated_timing_metadata
from combine_clips import combine_timeline

class ClipTimingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rate = 44100
        self.frames = [44099, 12577, 7023]
        self.rows = [dict(id=f'row-{i}', minutes=0, seconds=59.5 if i == 0 else 7,
                          text=f'  Speech {i}  ', seed=100+i, extra={'kept': True}) for i in range(3)]
        self.clips = []
        for i, count in enumerate(self.frames):
            path = self.root / f'{i}.wav'
            sf.write(path, np.full(count, (i+1)/8), self.rate, subtype='DOUBLE')
            self.clips.append(dict(validate_entries([self.rows[i]])[0], audio=str(path)))
        self.batch = dict(clips=self.clips, requested_clips=3, complete=True, error=None)

    def test_frame_exact_minute_carry_and_immutable_rows(self):
        before = copy.deepcopy((self.rows, self.batch))
        result = align_clip_timestamps(self.batch, self.rows)
        self.assertEqual((self.rows, self.batch), before)
        self.assertEqual(result['rows'][0], self.rows[0])
        cursor = timestamp_to_frames(0, 59.5, self.rate)
        for original, row, timing in zip(self.rows, json.loads(json.dumps(result['rows'])), result['timings']):
            self.assertEqual(timestamp_to_frames(row['minutes'], row['seconds'], self.rate), cursor)
            self.assertEqual(timing['start_frame'], cursor)
            self.assertEqual({k:v for k,v in row.items() if k not in ('minutes','seconds')},
                             {k:v for k,v in original.items() if k not in ('minutes','seconds')})
            cursor += timing['frames']
        self.assertEqual(result['rows'][1]['minutes'], 1)
        self.assertEqual(result['minimum_seconds'], (cursor+self.rate-1)//self.rate)

    def test_shuffled_editor_order_is_authoritative(self):
        rows = [self.rows[2], self.rows[0], self.rows[1]]
        result = align_clip_timestamps(self.batch, rows)
        self.assertEqual([c['id'] for c in result['clips']], ['row-2','row-0','row-1'])
        self.assertEqual(result['rows'][0], rows[0])
        self.assertEqual([t['frames'] for t in result['timings']], [7023,44099,12577])

    def test_mapping_and_stale_text_fail_closed(self):
        mutations = [lambda b,r: r.pop(), lambda b,r: r.append(dict(r[0], id='new')),
                     lambda b,r: r[0].update(id='new'), lambda b,r: r[1].update(id=r[0]['id']),
                     lambda b,r: r[0].pop('id'), lambda b,r: r[0].update(text='new text'),
                     lambda b,r: b.update(complete=False), lambda b,r: b.update(requested_clips=4),
                     lambda b,r: b.update(error='failed'), lambda b,r: b['clips'].pop(),
                     lambda b,r: b['clips'][1].update(id=b['clips'][0]['id']),
                     lambda b,r: b['clips'][0].pop('id')]
        for mutation in mutations:
            b,r = copy.deepcopy((self.batch,self.rows))
            mutation(b,r)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                align_clip_timestamps(b,r)

    def test_invalid_audio_and_mismatches_fail_without_mutation(self):
        path = self.root / 'bad.wav'
        for kind in ('missing','junk','empty','nan','rate','channels','not-wav'):
            b = copy.deepcopy(self.batch)
            b['clips'][1]['audio'] = str(path)
            if kind == 'junk': path.write_bytes(b'not a WAV')
            elif kind == 'empty': sf.write(path, np.array([]), self.rate)
            elif kind == 'nan': sf.write(path, np.array([np.nan]), self.rate, subtype='DOUBLE')
            elif kind == 'rate': sf.write(path, np.ones(5), 48000)
            elif kind == 'channels': sf.write(path, np.ones((5,2)), self.rate)
            elif kind == 'not-wav': sf.write(path, np.ones(5), self.rate, format='FLAC')
            before = copy.deepcopy(b)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                align_clip_timestamps(b, self.rows)
            metadata = generated_timing_metadata(b)
            self.assertEqual(metadata['clips'], [])
            self.assertTrue(metadata['error'])
            self.assertEqual(b, before)

    def test_metadata_and_empty_metadata(self):
        metadata = generated_timing_metadata(self.batch)
        self.assertNotIn('error', metadata)
        self.assertEqual([t['frames'] for t in metadata['clips']], self.frames)
        self.assertEqual(metadata['clips'][0]['text'], 'Speech 0')
        self.assertIn('error', generated_timing_metadata(None))

    def test_pcm_combine_has_no_sample_gap_or_overlap(self):
        self.rows[0]['seconds'] = 0.0001
        result = align_clip_timestamps(self.batch, self.rows)
        updated = dict(self.batch, clips=json.loads(json.dumps(result['clips'])))
        output = combine_timeline(updated, 0, result['minimum_seconds'], self.root/'out')
        samples, rate = sf.read(output['audio'])
        self.assertEqual(rate, self.rate)
        cursor = timestamp_to_frames(0, .0001, rate)
        np.testing.assert_array_equal(samples[:cursor], 0)
        for i, count in enumerate(self.frames):
            np.testing.assert_array_equal(samples[cursor:cursor+count], (i+1)/8)
            cursor += count
        np.testing.assert_array_equal(samples[cursor:], 0)
        self.assertEqual(output['gain'], 1)

    def test_half_frame_rounds_like_javascript(self):
        self.assertEqual(timestamp_to_frames(0, .005, 100), 1)
        self.assertEqual(timestamp_to_frames(0, .025, 100), 3)

    def test_many_fractional_frames_do_not_accumulate_rounding(self):
        for rate in (8000, 24000, 44100, 48000, 96000):
            cursor = rate * 59 + 1
            for i in range(100):
                minutes, remainder = divmod(cursor, rate*60)
                self.assertEqual(timestamp_to_frames(minutes, remainder/rate, rate), cursor)
                cursor += 12345+i

if __name__ == '__main__':
    unittest.main()
