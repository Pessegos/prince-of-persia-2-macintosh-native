"""Approved local scenery variants, leaving imported native resources intact."""

from functools import lru_cache
import hashlib
import json
from pathlib import Path

from PIL import Image


def retouched_room_commands(level, room, commands):
    """Room-local continuations made from the existing native drawing pieces."""
    if (level, room) == (6, 14):
        if any(command[:6] == ['back', 3506, 40, 340, 0, 2] for command in commands):
            # Fill the unpainted strip; otherwise DoCleanCut retains the
            # previous room there. Continue the same102-pixel sky repeat.
            return commands + [['back', 3506, -62, 340, 0, 2,
                                [0, 0, 335, 40], 4, 0, 2]]
        return commands
    if (level, room) != (6, 1):
        return commands
    walls = [command for command in commands if command[:6] in (
        ['front', 3527, 408, 365, 16, 2], ['front', 3527, 459, 365, 16, 2])
        and len(command) >= 10 and command[7] == 4]
    if {command[2] for command in walls} != {408, 459}:
        return commands
    extension = []
    for command in walls:
        for row in (-1, 0, 1):
            bottom = 125 + row * 120
            x = command[2]
            extension.append(['front', 3527, x, bottom, 16, row,
                              [max(0, bottom - 120), x, bottom, x + 51], 4, x // 51, row])
    return commands + extension


@lru_cache(maxsize=1)
def _retouch_bundle():
    path = Path(__file__)
    data = json.loads(path.with_suffix('.json').read_text(encoding='ascii'))
    if data['schema'] != 1:
        raise ValueError('Unsupported cavern retouch schema')
    with Image.open(path.with_suffix('.png')) as image:
        atlas = image.convert('RGBA')
    return data, atlas


@lru_cache(maxsize=3)
def retouch_assets(level_number=3):
    data, atlas = _retouch_bundle()
    return {(r['room'], r['shape'], r['x'], r['bottom'], r['mode']):
            (r, atlas.crop(r['atlas_rect'])) for r in data['records']
            if r.get('level', 3) == level_number}


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


def retouched_sprite(room, command, source, *, level_number=3):
    approved = (room in (0, 1, 27, 29) if level_number == 3
                else room in (4, 11, 13, 21, 22, 25, 27) if level_number == 4
                else level_number == 5 and room in (5, 6, 13, 14, 15, 16, 22, 24))
    if not approved or len(command) < 8 or command[7] != 4:
        return source
    key = (room, command[1], command[2], command[3], command[4])
    item = retouch_assets(level_number).get(key)
    if item is None:
        return source
    return _apply_retouch(*item, source)
