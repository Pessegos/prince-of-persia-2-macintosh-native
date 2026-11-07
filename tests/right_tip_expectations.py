"""Keep earlier art goldens independent of the newly reviewed right-tip layer.

The fixture records EXACT pixels from the user's approved comparisons. Restoring
only those pixels to their native values recreates the previous sprite, whose
full RGBA hash is checked. Full production images are tested without this
adapter in test_right_tip_batch_artwork; neither set of goldens is discarded.
"""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from pop2.cavern_retouch import retouched_sprite


@lru_cache(maxsize=1)
def approved_rooms():
    return json.loads(Path(__file__).with_name('right_tip_goldens.json').read_text(encoding='ascii'))['rooms']


@lru_cache(maxsize=1)
def approved_sources():
    return {(int(key.split(':')[0]), int(key.split(':')[1])-1,
             s['shape'], s['x'], s['bottom'], s['mode']): s
            for key, item in approved_rooms().items() for s in item['sources']}


def right_tip_rooms(level):
    return {int(key.split(':')[1])-1 for key in approved_rooms()
            if int(key.split(':')[0]) == level}


def without_new_right_tips(room, command, source, *, level_number=3):
    result = retouched_sprite(room, command, source, level_number=level_number)
    if len(command) < 8 or command[7] != 4:
        return result
    item = approved_sources().get((level_number, room, *command[1:5]))
    if item is None or hashlib.sha256(source.tobytes()).hexdigest() != item['native_sha256']:
        return result
    result = result.copy()
    for offset in item['offsets']:
        point = offset % source.width, offset // source.width
        result.putpixel(point, source.getpixel(point))
    assert hashlib.sha256(result.tobytes()).hexdigest() == item['previous_sha256'], \
        'Previously approved artwork changed outside the new right tip'
    return result


class PreviousArtworkMixin:
    """Prior wall, column, left-join and door assertions exclude only this layer."""

    def setUp(self):
        super().setUp()
        context = patch('pop2.caverns.retouched_sprite', side_effect=without_new_right_tips)
        context.start()
        self.addCleanup(context.stop)
