"""Baked scenery/door variants; native shapes and transparency stay untouched."""

from functools import lru_cache
import hashlib
import json
from pathlib import Path

from PIL import Image


@lru_cache(maxsize=1)
def _retouch_bundle():
    path = Path(__file__)
    data = json.loads(path.with_suffix('.json').read_text(encoding='ascii'))
    if data['schema'] != 1:
        raise ValueError('Unsupported cavern retouch schema')
    with Image.open(path.with_suffix('.png')) as image:
        atlas = image.convert('RGBA')
    return data, atlas


@lru_cache(maxsize=1)
def retouch_assets():
    data, atlas = _retouch_bundle()
    return {(r['room'], r['shape'], r['x'], r['bottom'], r['mode']):
            (r, atlas.crop(r['atlas_rect'])) for r in data['records']}


@lru_cache(maxsize=1)
def door_retouch_assets():
    data, atlas = _retouch_bundle()
    return {(r['level'], r['room'], r['shape'], r['x'], r['bottom'], r['mode']):
            (r, atlas.crop(r['atlas_rect'])) for r in data.get('doors', ())}


def _apply_retouch(record, replacement, source):
    # Changed exports must never inherit artwork baked for a different source.
    if (list(source.size) != record['size'] or
            hashlib.sha256(source.tobytes()).hexdigest() != record['source_sha256']):
        return source
    result = source.copy()
    result.paste(replacement, tuple(record['source_rect'][:2]))
    return result


def retouched_door_sprite(level, room, command, source):
    if (level not in (3, 4, 5) or len(command) < 8 or command[7] != 4
            or command[1] != 3564 or command[4] != 16):
        return source
    key = (level, room, command[1], command[2], command[3], command[4])
    item = door_retouch_assets().get(key)
    return _apply_retouch(*item, source) if item is not None else source


def retouched_sprite(room, command, source):
    if room not in (0, 1, 27, 29) or len(command) < 8 or command[7] != 4:
        return source
    key = (room, command[1], command[2], command[3], command[4])
    item = retouch_assets().get(key)
    if item is None:
        return source
    return _apply_retouch(*item, source)
