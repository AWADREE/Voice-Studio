"""Timestamp-labelled sequential commentary batches; no UI or model dependencies."""
from __future__ import annotations

import json
from decimal import Decimal
import math
import re
from pathlib import Path
import shutil
import uuid
import zipfile

MAX_CLIPS = 100
MAX_TEXT = 2000
MAX_SEED = 9007199254740991  # Largest integer the browser can preserve exactly.


def validate_seed(value):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError('Clip seed must be -1 (random) or a whole nonnegative number.') from exc
    if isinstance(value, bool) or not math.isfinite(number) or not number.is_integer() or not -1 <= number <= MAX_SEED:
        raise ValueError(f'Clip seed must be a whole number between -1 and {MAX_SEED}.')
    return int(number)


def _integer(value, name, maximum):
    if isinstance(value, bool):
        raise ValueError(f'{name} must be a whole number.')
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'{name} must be a whole number.') from exc
    if not math.isfinite(number) or not number.is_integer() or not 0 <= number <= maximum:
        raise ValueError(f'{name} must be a whole number between 0 and {maximum}.')
    return int(number)


def validate_timestamp_seconds(value, name='Clip seconds'):
    """Finite sub-minute seconds, including sample-accurate fractional values."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'{name} must be a number from 0 up to (but not including) 60.') from exc
    if isinstance(value, bool) or not math.isfinite(number) or not 0 <= number < 60:
        raise ValueError(f'{name} must be a number from 0 up to (but not including) 60.')
    return int(number) if number.is_integer() else number


def timestamp_label(minutes, seconds):
    # Decimal fixed notation avoids exponents and retains float round-trip precision.
    value = format(Decimal(str(seconds)), 'f')
    if '.' in value:
        value = value.rstrip('0').rstrip('.')
    if seconds < 10:
        value = '0' + value
    return f'{minutes:02d}:{value}'


def timestamp_to_frames(minutes, seconds, sample_rate):
    minutes = _integer(minutes, 'Clip minutes', 9999)
    seconds = validate_timestamp_seconds(seconds)
    # Round, never truncate: frame/rate timestamps survive a JSON float round trip.
    return math.floor((minutes * 60 + seconds) * sample_rate + 0.5)


def validate_entries(rows, *, validate_seeds=True):
    """Validate every entry before any model operation; preserve editor order."""
    if not isinstance(rows, (list, tuple)) or not 1 <= len(rows) <= MAX_CLIPS:
        raise ValueError(f'Add between 1 and {MAX_CLIPS} commentary clips.')
    result, identities = [], set()
    for index, row in enumerate(rows, 1):
        if isinstance(row, dict):
            minutes, seconds, text = row.get('minutes'), row.get('seconds'), row.get('text')
        elif isinstance(row, (list, tuple)) and len(row) == 3:
            minutes, seconds, text = row
        else:
            raise ValueError(f'Clip {index}: expected minutes, seconds and commentary.')
        minutes = _integer(minutes, f'Clip {index} minutes', 9999)
        seconds = validate_timestamp_seconds(seconds, f'Clip {index} seconds')
        if not isinstance(text, str) or not text.strip() or len(text.strip()) > MAX_TEXT:
            raise ValueError(f'Clip {index}: enter 1 to {MAX_TEXT} commentary characters.')
        result.append({'index': index, 'minutes': minutes, 'seconds': seconds,
                       'label': timestamp_label(minutes, seconds), 'text': text.strip()})
        if isinstance(row, dict) and 'id' in row:
            identity = row['id']
            if not isinstance(identity, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', identity) or identity in identities:
                raise ValueError(f'Clip {index}: invalid or duplicate paragraph identity.')
            identities.add(identity)
            result[-1]['id'] = identity
        if validate_seeds and isinstance(row, dict) and 'seed' in row:
            result[-1]['seed'] = validate_seed(row['seed'])
    return result


def write_archive(clips, requested_clips, folder, *, complete=None):
    """Publish an immutable archive of exactly this clip revision, or publish nothing."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / ('commentary-clips-' + uuid.uuid4().hex + '.zip')
    staging = archive.with_suffix('.tmp')
    manifest = {'timestamps_are_labels': True, 'requested_clips': requested_clips,
                'completed_clips': len(clips), 'complete': len(clips) == requested_clips if complete is None else bool(complete),
                'clips': [{k: v for k, v in clip.items() if k != 'audio'} for clip in clips]}
    try:
        with zipfile.ZipFile(staging, 'x', compression=zipfile.ZIP_DEFLATED) as bundle:
            for clip in clips:
                bundle.write(clip['audio'], arcname=clip['filename'])
            bundle.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        staging.replace(archive)
    except Exception:
        staging.unlink(missing_ok=True)
        raise
    return str(archive)


def run_batch(rows, *, generate_clip, output_root, lock, release_after=True,
              release_model=lambda: None, on_progress=None):
    """Generate in row order with one model lifetime, returning partial successes.

    ``generate_clip(text, zero_based_index)`` must return a WAV path and must not
    unload the model. The callback may acquire the supplied reentrant lock again.
    Source files are never moved/deleted. Names carry an ordinal so duplicate
    timestamp labels are valid. Timestamps do not insert silence or time-stretch.
    """
    entries = validate_entries(rows)
    if not lock.acquire(blocking=False):
        raise RuntimeError('Generation is already running. Wait for it to finish.')
    clips, error, folder, archive = [], None, None, None
    try:
        root = Path(output_root)
        root.mkdir(parents=True, exist_ok=True)
        folder = root / ('batch-' + uuid.uuid4().hex)
        folder.mkdir(exist_ok=False)
        for position, entry in enumerate(entries):
            if on_progress:
                on_progress(position, len(entries), entry['label'])
            try:
                source = Path(generate_clip(entry['text'], position))
                if source.suffix.lower() != '.wav' or not source.is_file() or source.stat().st_size == 0:
                    raise ValueError('Generation returned no usable WAV file.')
                filename = entry['label'].replace(':', 'm') + f"s-{entry['index']:03d}.wav"
                target = folder / filename
                shutil.copyfile(source, target)
                clips.append({**entry, 'audio': str(target), 'filename': filename})
            except Exception as exc:
                error = f"Clip {entry['index']} ({entry['label']}) failed: {exc}"
                break
    except Exception as exc:
        error = f'Batch could not finish: {exc}'
    finally:
        try:
            if release_after:
                release_model()
        except Exception as exc:
            error = (error + '\n' if error else '') + f'GPU memory release failed: {exc}'
        finally:
            lock.release()
    # Archive only generated audio plus a portable manifest, never voice files,
    # absolute source paths, delivery prompts or model/session internals.
    if clips:
        try:
            manifest = {'timestamps_are_labels': True, 'requested_clips': len(entries),
                        'completed_clips': len(clips), 'complete': len(clips) == len(entries),
                        'clips': [{k: v for k, v in clip.items() if k != 'audio'} for clip in clips]}
            manifest_path = folder / 'manifest.json'
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
            zip_path = folder / 'commentary-clips.zip'
            with zipfile.ZipFile(zip_path, 'x', compression=zipfile.ZIP_DEFLATED) as bundle:
                for clip in clips:
                    bundle.write(clip['audio'], arcname=clip['filename'])
                bundle.write(manifest_path, arcname='manifest.json')
            archive = str(zip_path)
        except Exception as exc:
            error = (error + '\n' if error else '') + f'Download-all archive unavailable: {exc}'
    status = f'Generated {len(clips)} of {len(entries)} clips.'
    if error:
        status += ' ' + error + ' Completed clips are kept. Fix the issue, then generate only the remaining rows to avoid duplicate work.'
    else:
        status += ' Timestamps label the clips; they do not add silence.'
    return {'clips': clips, 'archive': archive, 'error': error, 'status': status,
            'batch_id': uuid.uuid4().hex, 'revision': 0,
            'requested_clips': len(entries), 'complete': len(clips) == len(entries),
            'batch_dir': str(folder) if folder else None}
