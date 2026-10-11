"""Portable drawing commands for the recovered level-three entrance."""

import json

from PIL import Image, ImageChops

from pop2.paths import ASSET_DIR
from pop2.render_opening import OpeningRoom, decode_ctbl, decode_shap, load_resource_file


def entrance_room():
    program = json.loads((ASSET_DIR / 'caverns_entry.json').read_text(encoding='ascii'))
    if (program.get('version'), program.get('level'), program.get('room')) != (1, 3, 0):
        raise ValueError('Unsupported cavern drawing export')
    resources = load_resource_file('Caverns.rsrc')
    palette = decode_ctbl(resources['CTBL'][3500]['data'])
    shapes = {}
    background = Image.new('RGBA', (510, 365), (0, 0, 0, 255))
    foreground = Image.new('RGBA', background.size)
    masks = {row: Image.new('L', background.size) for row in range(-1, 5)}
    for layer, index, x, bottom, flags, row in program['commands']:
        if index not in shapes:
            shapes[index] = decode_shap(resources['SHAP'][index]['data'], palette)
        sprite = shapes[index]
        destination = background if layer == 'back' else foreground
        position = x, bottom - sprite.height
        destination.paste(sprite, position, sprite)
        if layer == 'front':
            mask = Image.new('L', background.size)
            mask.paste(sprite.getchannel('A'), position)
            if row in masks:
                masks[row] = ImageChops.lighter(masks[row], mask)
    return OpeningRoom(background, foreground, masks, (), (), 0, 3)
