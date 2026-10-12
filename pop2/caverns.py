"""Portable drawing commands for the recovered level-three scenery."""

import json
from functools import lru_cache

from PIL import Image, ImageChops

from pop2.paths import ASSET_DIR
from pop2.render_opening import OpeningRoom, decode_ctbl, decode_shap, load_resource_file


@lru_cache(maxsize=1)
def cavern_assets():
    program = json.loads((ASSET_DIR / 'caverns_entry.json').read_text(encoding='ascii'))
    resources = load_resource_file('Caverns.rsrc')
    return program, resources, decode_ctbl(resources['CTBL'][3500]['data']), {}


def cavern_room(room_id=0):
    program, resources, palette, shapes = cavern_assets()
    if program.get('version') == 2 and program.get('level') == 3:
        commands = program['rooms'][str(room_id)]
    elif (program.get('version'), program.get('level'), program.get('room')) == (1, 3, room_id):
        commands = program['commands']
    else:
        raise ValueError('Unsupported cavern drawing export')
    background = Image.new('RGBA', (510, 365), (0, 0, 0, 255))
    foreground = Image.new('RGBA', background.size)
    masks = {row: Image.new('L', background.size) for row in range(-1, 5)}
    for command in commands:
        layer, index, x, bottom, flags, row = command[:6]
        if index not in shapes:
            shapes[index] = decode_shap(resources['SHAP'][index]['data'], palette)
        sprite = shapes[index]
        if len(command) == 7:
            top, left, end_y, right = command[6]
            rect = (max(0, left - x), max(0, top - (bottom - sprite.height)),
                    min(sprite.width, right - x), min(sprite.height, end_y - (bottom - sprite.height)))
            if rect[0] >= rect[2] or rect[1] >= rect[3]:
                continue
            sprite = sprite.crop(rect)
            x, bottom = x + rect[0], bottom - shapes[index].height + rect[3]
        destination = background if layer == 'back' else foreground
        position = x, bottom - sprite.height
        destination.paste(sprite, position, sprite)
        if layer == 'front':
            mask = Image.new('L', background.size)
            mask.paste(sprite.getchannel('A'), position)
            if row in masks:
                masks[row] = ImageChops.lighter(masks[row], mask)
    return OpeningRoom(background, foreground, masks, (), (), room_id, 3)
