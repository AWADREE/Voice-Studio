"""Timestamp-labelled sequential commentary batches; no UI or model dependencies."""
from __future__ import annotations

import json
import math
from pathlib import Path
import shutil
import uuid
import zipfile

MAX_CLIPS = 100
MAX_TEXT = 2000


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


def validate_entries(rows):
    """Validate every entry before any model operation; preserve editor order."""
    if not isinstance(rows, (list, tuple)) or not 1 <= len(rows) <= MAX_CLIPS:
        raise ValueError(f'Add between 1 and {MAX_CLIPS} commentary clips.')
    result = []
    for index, row in enumerate(rows, 1):
        if isinstance(row, dict):
            minutes, seconds, text = row.get('minutes'), row.get('seconds'), row.get('text')
        elif isinstance(row, (list, tuple)) and len(row) == 3:
            minutes, seconds, text = row
        else:
            raise ValueError(f'Clip {index}: expected minutes, seconds and commentary.')
        minutes = _integer(minutes, f'Clip {index} minutes', 9999)
        seconds = _integer(seconds, f'Clip {index} seconds', 59)
        if not isinstance(text, str) or not text.strip() or len(text.strip()) > MAX_TEXT:
            raise ValueError(f'Clip {index}: enter 1 to {MAX_TEXT} commentary characters.')
        result.append({'index': index, 'minutes': minutes, 'seconds': seconds,
                       'label': f'{minutes:02d}:{seconds:02d}', 'text': text.strip()})
    return result


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
                filename = f"{entry['minutes']:02d}m{entry['seconds']:02d}s-{entry['index']:03d}.wav"
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
            'batch_dir': str(folder) if folder else None}
