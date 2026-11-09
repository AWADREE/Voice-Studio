"""Mix generated clips onto an exact-length, silent-padded timeline.

No model dependencies or source mutations. Two bounded-memory passes determine
whole-track headroom before PCM conversion; overlaps add instead of overwriting.
"""
from __future__ import annotations

from contextlib import ExitStack
import math
import os
from pathlib import Path
import shutil
import uuid

import numpy as np
import soundfile as sf

MAX_DURATION_SECONDS = 24 * 60 * 60
MAX_WAV_BYTES = 2**32 - 1024 * 1024  # Conservative classic RIFF/WAV boundary.
BLOCK_FRAMES = 65536


def _integer(value, name, maximum):
    if isinstance(value, bool):
        raise ValueError(f'{name} must be a whole number between 0 and {maximum}.')
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f'{name} must be a whole number between 0 and {maximum}.') from None
    if not math.isfinite(number) or not number.is_integer() or not 0 <= number <= maximum:
        raise ValueError(f'{name} must be a whole number between 0 and {maximum}.')
    return int(number)


def _clock(seconds):
    # A source's fractional final second must not be rounded down in guidance.
    required = math.ceil(seconds)
    return f'{required // 60}:{required % 60:02d}'


def combine_timeline(batch_result, minutes, seconds, output_root):
    """Return a new PCM-24 WAV for the existing generated clips, or raise.

    ``minutes`` and ``seconds`` specify the final timeline duration, not padding
    to add. Source timestamps are integer seconds. Partial batches are accepted
    and explicitly described in the returned status. Source audio is untouched.
    """
    minutes = _integer(minutes, 'Total minutes', 9999)
    seconds = _integer(seconds, 'Total seconds', 59)
    total_seconds = minutes * 60 + seconds
    if not 0 < total_seconds <= MAX_DURATION_SECONDS:
        raise ValueError('Total duration must be greater than zero and no more than 24 hours.')
    if not isinstance(batch_result, dict):
        raise ValueError('Generate timestamped clips before combining them.')
    clips = batch_result.get('clips')
    if not isinstance(clips, list) or not 1 <= len(clips) <= 100:
        raise ValueError('Combine requires between 1 and 100 generated clips.')
    requested = batch_result.get('requested_clips', len(clips))
    try:
        requested = max(len(clips), _integer(requested, 'Requested clip count', 100))
    except ValueError:
        requested = len(clips)
    partial = bool(batch_result.get('error')) or requested > len(clips) or batch_result.get('complete') is False
    plans = []
    overruns = []
    sample_rate = channels = None
    # Keep source handles open through both passes. This also avoids repeated
    # opens of every source for each output block on long sparse timelines.
    with ExitStack() as stack:
        for position, clip in enumerate(clips, 1):
            if not isinstance(clip, dict) or not clip.get('audio'):
                raise ValueError(f'Clip {position} has no generated audio file.')
            index = clip.get('index', position)
            start_seconds = _integer(clip.get('minutes'), f'Clip {index} minutes', 9999) * 60 + _integer(clip.get('seconds'), f'Clip {index} seconds', 59)
            try:
                reader = stack.enter_context(sf.SoundFile(Path(clip['audio']), 'r'))
            except (OSError, RuntimeError, TypeError) as exc:
                raise ValueError(f'Cannot read generated audio for clip {index}: {exc}') from exc
            if reader.frames <= 0 or reader.samplerate <= 0 or reader.channels not in (1, 2):
                raise ValueError(f'Clip {index} must contain nonempty mono or stereo audio.')
            if sample_rate is None:
                sample_rate, channels = reader.samplerate, reader.channels
            elif (reader.samplerate, reader.channels) != (sample_rate, channels):
                raise ValueError(f'Clip {index} has a different sample rate or channel count. All clips must match; audio is not resampled or downmixed.')
            start = start_seconds * sample_rate
            end = start + reader.frames
            if end > total_seconds * sample_rate:
                end_seconds = end / sample_rate
                overruns.append((index, end_seconds))
            plans.append((index, reader, start, end))
        if overruns:
            details = '; '.join(f'Clip {index} ends at {end:.3f} seconds' for index, end in overruns)
            required = max(end for _, end in overruns)
            raise ValueError(f'{details}, beyond the requested {total_seconds} seconds. Set total duration to at least {_clock(required)} (minutes:seconds). No audio was truncated.')
        total_frames = total_seconds * sample_rate
        expected_bytes = total_frames * channels * 3 + 4096
        if expected_bytes > MAX_WAV_BYTES:
            raise ValueError('This timeline exceeds the WAV file-size limit. Choose a shorter total duration; no audio will be truncated.')

        def blocks():
            for offset in range(0, total_frames, BLOCK_FRAMES):
                stop = min(offset + BLOCK_FRAMES, total_frames)
                mixed = np.zeros((stop - offset, channels), dtype=np.float64)
                for index, reader, start, end in plans:
                    left, right = max(offset, start), min(stop, end)
                    if left >= right:
                        continue
                    reader.seek(left - start)
                    audio = reader.read(right - left, dtype='float64', always_2d=True)
                    if len(audio) != right - left or not np.isfinite(audio).all():
                        raise ValueError(f'Clip {index} contains invalid, non-finite, or incomplete audio.')
                    mixed[left - offset:right - offset] += audio
                if not np.isfinite(mixed).all():
                    raise ValueError('The overlapping audio mix contains non-finite samples.')
                yield mixed

        peak = 0.0
        for block in blocks():
            peak = max(peak, float(np.max(np.abs(block))))
        # Positive PCM full scale is one quantum below 1. Leave one quantum of
        # room when attenuation is necessary, without altering quiet tracks.
        gain = (1.0 - 2**-23) / peak if peak > 1.0 else 1.0
        root = Path(output_root)
        root.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(root).free < expected_bytes + 8 * 1024 * 1024:
            raise ValueError('There is not enough free disk space for this timeline WAV.')
        target = root / ('combined-' + uuid.uuid4().hex + '.wav')
        staging = root / ('.' + target.name + '.partial')
        try:
            with sf.SoundFile(staging, mode='x', samplerate=sample_rate, channels=channels, subtype='PCM_24', format='WAV') as output:
                for block in blocks():
                    if float(np.max(np.abs(block))) > peak + 1e-12:
                        raise ValueError('Source audio changed while combining. Retry using the unchanged generated clips.')
                    output.write(block * gain)
                output.flush()
            with staging.open('r+b') as data:
                os.fsync(data.fileno())
            # Unique name; refuse even the improbable collision rather than
            # replacing a pre-existing user output.
            if target.exists():
                raise FileExistsError('The destination already exists. Try combining again.')
            staging.rename(target)
        except BaseException:
            staging.unlink(missing_ok=True)
            raise
    status = f'Combined {len(clips)} generated clips into {_clock(total_seconds)}. Gaps are silence; overlapping clips are mixed.'
    if partial:
        count = f'{len(clips)} of {requested}' if requested > len(clips) else str(len(clips))
        status += f' Partial batch: only the {count} available clips were included.'
    if gain < 1:
        status += f' Applied whole-track gain {gain:.6f} ({20 * math.log10(gain):.2f} dB) to prevent clipping.'
    return {'audio': str(target), 'status': status, 'duration_seconds': total_seconds,
            'clip_count': len(clips), 'requested_clips': requested, 'partial': partial,
            'sample_rate': sample_rate, 'channels': channels,
            'peak_before_gain': peak, 'gain': gain}

