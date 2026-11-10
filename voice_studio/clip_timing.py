"""Verified audio-frame timing for the explicit back-to-back editor action."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import numpy as np
import soundfile as sf

from batch_generation import validate_entries, timestamp_label, timestamp_to_frames


def _generated_timings(batch_result):
    if not isinstance(batch_result, dict):
        raise ValueError('Generate all clips before aligning timestamps.')
    clips = batch_result.get('clips')
    if (not isinstance(clips, list) or not 1 <= len(clips) <= 100
            or batch_result.get('complete') is not True
            or batch_result.get('error')
            or batch_result.get('requested_clips') != len(clips)):
        raise ValueError('Generate a complete batch before aligning timestamps.')
    # Validate stable identities, normalized text, and numeric timestamps first.
    entries = validate_entries(clips, validate_seeds=False)
    if any('id' not in entry for entry in entries):
        raise ValueError('Every generated clip must have a stable paragraph identity.')
    timings = []
    sample_rate = channels = None
    for entry, clip in zip(entries, clips):
        try:
            with sf.SoundFile(Path(clip['audio']), 'r') as reader:
                if reader.format not in ('WAV', 'WAVEX', 'RF64'):
                    raise ValueError('Expected generated WAV audio.')
                if reader.frames <= 0 or reader.samplerate <= 0 or reader.channels not in (1, 2):
                    raise ValueError('Expected nonempty mono or stereo audio.')
                if sample_rate is None:
                    sample_rate, channels = reader.samplerate, reader.channels
                elif (reader.samplerate, reader.channels) != (sample_rate, channels):
                    raise ValueError('All clips must have the same sample rate and channel count.')
                # Metadata alone is insufficient for truncated or non-finite WAVs.
                count = 0
                for block in reader.blocks(blocksize=65536, dtype='float64', always_2d=True):
                    if not np.isfinite(block).all():
                        raise ValueError('Audio contains non-finite samples.')
                    count += len(block)
                if count != reader.frames:
                    raise ValueError('Audio is incomplete or unreadable.')
                timings.append({'id': entry['id'], 'text': entry['text'],
                                'frames': reader.frames, 'sample_rate': reader.samplerate})
        except (OSError, RuntimeError, TypeError, KeyError, ValueError) as exc:
            raise ValueError(f"Cannot align clip {entry['index']}: {exc}") from exc
    return timings


def generated_timing_metadata(batch_result):
    """Fail closed without disrupting unrelated editor metadata/rendering."""
    try:
        return {'clips': _generated_timings(batch_result)}
    except (ValueError, TypeError) as exc:
        return {'clips': [], 'error': str(exc)}


def align_clip_timestamps(batch_result, rows):
    """Return an immutable alignment plan; callers decide when to apply it.

    The first editor timestamp and every other row field are preserved exactly.
    Subsequent starts use cumulative integer frames at the generated sample rate.
    Float seconds are a transport representation; Combine rounds back to frames.
    """
    entries = validate_entries(rows, validate_seeds=False)
    if any(not isinstance(row, dict) or 'id' not in row for row in rows):
        raise ValueError('Every current paragraph must have a stable identity.')
    timings = _generated_timings(batch_result)
    by_id = {timing['id']: timing for timing in timings}
    if {entry['id'] for entry in entries} != set(by_id):
        raise ValueError('Current paragraphs do not match the complete generated batch. Generate all current clips again.')
    for entry in entries:
        if entry['text'] != by_id[entry['id']]['text']:
            raise ValueError(f"Clip {entry['index']} text changed after generation. Regenerate it before aligning.")
    sample_rate = timings[0]['sample_rate']
    cursor = timestamp_to_frames(entries[0]['minutes'], entries[0]['seconds'], sample_rate)
    updated_rows = deepcopy(rows)
    generated = {clip['id']: clip for clip in batch_result['clips']}
    updated_clips, ordered_timings = [], []
    for index, (row, entry) in enumerate(zip(updated_rows, entries)):
        if index:
            minutes, remainder = divmod(cursor, sample_rate * 60)
            if minutes > 9999:
                raise ValueError('Aligned timestamps exceed the supported minute range.')
            row['minutes'] = minutes
            row['seconds'] = remainder / sample_rate
        normalized = validate_entries([row], validate_seeds=False)[0]
        clip = deepcopy(generated[entry['id']])
        clip.update(minutes=normalized['minutes'], seconds=normalized['seconds'],
                    label=timestamp_label(normalized['minutes'], normalized['seconds']))
        updated_clips.append(clip)
        timing = dict(by_id[entry['id']], start_frame=cursor)
        ordered_timings.append(timing)
        cursor += timing['frames']
    return {'rows': updated_rows, 'clips': updated_clips, 'sample_rate': sample_rate,
            'timings': ordered_timings, 'minimum_seconds': (cursor + sample_rate - 1) // sample_rate}
