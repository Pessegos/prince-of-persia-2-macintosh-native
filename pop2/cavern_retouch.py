"""Room-local scenery variants; native shapes and transparency remain untouched."""

from functools import lru_cache
import hashlib
import json
from pathlib import Path

from PIL import Image


@lru_cache(maxsize=1)
def retouch_assets():
    path = Path(__file__)
    data = json.loads(path.with_suffix('.json').read_text(encoding='ascii'))
    if data['schema'] != 1:
        raise ValueError('Unsupported cavern retouch schema')
    with Image.open(path.with_suffix('.png')) as image:
        atlas = image.convert('RGBA')
    return {(r['room'], r['shape'], r['x'], r['bottom'], r['mode']):
            (r, atlas.crop(r['atlas_rect'])) for r in data['records']}


def retouched_sprite(room, command, source):
    if room not in (0, 1, 27) or len(command) < 8 or command[7] != 4:
        return source
    key = (room, command[1], command[2], command[3], command[4])
    item = retouch_assets().get(key)
    if item is None:
        return source
    record, replacement = item
    # Do not reuse a local correction if an exported variant changes its source.
    if (list(source.size) != record['size'] or
            hashlib.sha256(source.tobytes()).hexdigest() != record['source_sha256']):
        return source
    result = source.copy()
    result.paste(replacement, tuple(record['source_rect'][:2]))
    return result
