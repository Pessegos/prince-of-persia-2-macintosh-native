"""Isolate only the newly approved diagonal-floor pixel layer in older goldens.

Every restored coordinate was native before this batch. The complete restored
sprite must match its previous RGBA hash; no earlier artwork may be discarded.
New full production-frame/source goldens are checked without this adapter.
"""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from pop2.cavern_retouch import retouched_sprite


@lru_cache(maxsize=1)
def approved_floor_rooms():
    path = Path(__file__).with_name('floor_join_goldens.json')
    return json.loads(path.read_text(encoding='ascii'))['rooms']


@lru_cache(maxsize=1)
def approved_floor_sources():
    return {(int(key.split(':')[0]), int(key.split(':')[1])-1,
             source['shape'], source['x'], source['bottom'], source['mode']): source
            for key, room in approved_floor_rooms().items() for source in room['sources']}


def floor_join_rooms(level):
    return {int(key.split(':')[1])-1 for key in approved_floor_rooms()
            if int(key.split(':')[0]) == level}


def without_new_floor_joins(room, command, source, *, level_number=3):
    result = retouched_sprite(room, command, source, level_number=level_number)
    if len(command) < 8 or command[7] != 4:
        return result
    expected = approved_floor_sources().get((level_number, room, *command[1:5]))
    if expected is None or hashlib.sha256(source.tobytes()).hexdigest() != expected['native_sha256']:
        return result
    result = result.copy()
    for offset in expected['offsets']:
        point = offset % source.width, offset // source.width
        result.putpixel(point, source.getpixel(point))
    assert hashlib.sha256(result.tobytes()).hexdigest() == expected['previous_sha256'], \
        'Previously approved artwork changed outside the reviewed floor-join pixels'
    return result


class PreviousFloorArtworkMixin:
    """Earlier right-tip room goldens exclude only this new floor layer."""

    def setUp(self):
        super().setUp()
        context = patch('pop2.caverns.retouched_sprite', side_effect=without_new_floor_joins)
        context.start()
        self.addCleanup(context.stop)
