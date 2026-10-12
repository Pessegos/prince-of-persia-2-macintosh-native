"""Portable drawing commands for the recovered level-three scenery."""

import json
import struct
from functools import lru_cache

from PIL import Image, ImageChops

from pop2.paths import ASSET_DIR
from pop2.render_opening import OpeningRoom, decode_ctbl, decode_shap, load_resource_file


@lru_cache(maxsize=1)
def cavern_assets():
    program = json.loads((ASSET_DIR / 'caverns_entry.json').read_text(encoding='ascii'))
    resources = load_resource_file('Caverns.rsrc')
    return program, resources, decode_ctbl(resources['CTBL'][3500]['data']), {}


def flask_shape(data, palette, draw_mode):
    flags, stride, width, height = struct.unpack_from('>HhhH', data)
    if flags & 0xf000 != 0x9000:
        return decode_shap(data, palette)
    if stride <= 0 or not 0 < width <= stride * 8 or height <= 0:
        raise ValueError('Invalid monochrome flask dimensions')
    pixels = bytearray()
    cursor, expected = 12, stride * height
    if flags & 0x0200:
        # hGetNShapeItem 17:5f78-5fa0: whole-bitmap RLE, not color row RLE.
        while len(pixels) < expected:
            if cursor >= len(data):
                raise ValueError('Truncated monochrome flask')
            token = data[cursor]
            cursor += 1
            if token & 128:
                if cursor >= len(data):
                    raise ValueError('Truncated monochrome repeat')
                pixels.extend([data[cursor]] * ((token & 127) + 3))
                cursor += 1
            else:
                if token == 0 or cursor + token > len(data):
                    raise ValueError('Invalid monochrome literal')
                pixels.extend(data[cursor:cursor + token])
                cursor += token
        if len(pixels) != expected:
            raise ValueError('Monochrome flask exceeds its dimensions')
    else:
        pixels.extend(data[12:12 + expected])
        if len(pixels) != expected:
            raise ValueError('Truncated monochrome flask')
    image = Image.new('RGBA', (width, height))
    color = palette[draw_mode]
    image.putdata([color if pixels[y * stride + x // 8] & (128 >> (x % 8)) else (0, 0, 0, 0)
                   for y in range(height) for x in range(width)])
    return image


@lru_cache(maxsize=1)
def flask_assets():
    resources = load_resource_file('Prince.rsrc')
    # LoadFlaskSet 3:564c relocates CTBL:3000 to index 224.
    palette = {224 + index: color for index, color in decode_ctbl(resources['CTBL'][3000]['data']).items()}
    return resources, palette


def cavern_room(room_id=0, entry_frame=0):
    program, resources, palette, shapes = cavern_assets()
    if program.get('version') in (2, 3) and program.get('level') == 3:
        commands = program['rooms'][str(room_id)]
    elif (program.get('version'), program.get('level'), program.get('room')) == (1, 3, room_id):
        commands = program['commands']
    else:
        raise ValueError('Unsupported cavern drawing export')
    entry = program.get('entry_exit')
    if entry is not None and room_id == entry['room']:
        commands = entry['frames'][entry_frame]['commands']
    background = Image.new('RGBA', (510, 365), (0, 0, 0, 255))
    foreground = Image.new('RGBA', background.size)
    masks = {row: Image.new('L', background.size) for row in range(-1, 5)}
    for command in commands:
        layer, index, x, bottom, flags, row = command[:6]
        library = command[7] if len(command) >= 8 else 4
        key = (library, index, flags) if library == 1 else index
        if key not in shapes:
            if library == 1:
                source, colors = flask_assets()
                shapes[key] = flask_shape(source['SHAP'][index]['data'], colors, flags)
            elif library == 4:
                shapes[key] = decode_shap(resources['SHAP'][index]['data'], palette)
            else:
                raise ValueError(f'Unsupported cavern shape library {library}')
        sprite = shapes[key]
        if len(command) >= 7:
            top, left, end_y, right = command[6]
            rect = (max(0, left - x), max(0, top - (bottom - sprite.height)),
                    min(sprite.width, right - x), min(sprite.height, end_y - (bottom - sprite.height)))
            if rect[0] >= rect[2] or rect[1] >= rect[3]:
                continue
            sprite = sprite.crop(rect)
            x, bottom = x + rect[0], bottom - shapes[key].height + rect[3]
        destination = background if layer == 'back' else foreground
        position = x, bottom - sprite.height
        destination.paste(sprite, position, sprite)
        if layer == 'front':
            mask = Image.new('L', background.size)
            mask.paste(sprite.getchannel('A'), position)
            if row in masks:
                masks[row] = ImageChops.lighter(masks[row], mask)
    return OpeningRoom(background, foreground, masks, (), (), room_id, 3)
