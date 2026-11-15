"""Approved level 2 seam artwork, leaving imported native resources intact.

The stone chamber's painting (native room 1, port room 0) sits 20 pixels
lower than the shore's: its sky gradient matches the start room's exactly
once lifted. The approved edit lifts its upper part, fills the uncovered
sand, joins the cliff with a minimum-error cut and recolours the start
room's grey shallows at the join (see docs/DESERT_ARTWORK.md).
"""

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
        raise ValueError('Unsupported desert retouch schema')
    with Image.open(path.with_suffix('.png')) as image:
        atlas = image.convert('RGBA')
    return {record['room']: (record, atlas.crop(record['atlas_rect']))
            for record in data['records']}


def retouched_background(room_id, background):
    """The approved background, or the source unchanged if it is not the
    exact native picture the edit was made from."""
    entry = _retouch_bundle().get(room_id)
    if entry is None:
        return background
    record, patch = entry
    if (list(background.size) != record['size'] or background.mode != 'RGBA' or
            hashlib.sha256(background.tobytes()).hexdigest() != record['source_sha256']):
        return background
    result = background.copy()
    result.alpha_composite(patch, tuple(record['source_rect'][:2]))
    return result
