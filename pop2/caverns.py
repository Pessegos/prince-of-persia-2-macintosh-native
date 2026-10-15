"""Portable drawing commands for the recovered level-three scenery."""

import json
import struct
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageOps

from pop2.paths import ASSET_DIR
from pop2.opponent_generation import EMPTY_TILES, character_column
from pop2.render_opening import OpeningRoom, decode_ctbl, decode_shap, load_resource_file
from pop2.terrain import character_row, floor_contact_x


def drawn_actor_columns(bounds, facing):
    left, _, right, _ = bounds
    return (max(0, character_column(left + (21 if facing else 22))),
            min(9, character_column(right + (23 if facing else 24))))


def floor_redraw_cells(state, bounds):
    # QuickFloor 2:69b6-6ac4; the right-facing climb uses MarkHalf instead.
    if state.facing and 135 <= state.action <= 144:
        return ()
    top_row, bottom_row = character_row(min(365, bounds[1])), character_row(bounds[3])
    if bottom_row == -1:
        bottom_row = 3
    mode = state.animation_state
    if (mode not in (2, 3, 4, 6) and not (mode == 5 and top_row != bottom_row)
            and state.action not in (79, 81)):
        return ()
    rows = []
    if min(365, bounds[3] + 1) > bottom_row * 120 + 106:
        rows.append(bottom_row)
    if top_row != bottom_row:
        rows.append(top_row)
    first, last = drawn_actor_columns(bounds, state.facing)
    return tuple((column, row) for row in rows if 0 <= row < 3
                 for column in range(first, last + 1))


def falling_floor_redraw_cells(x, y):
    # Cave loose MOB: 5:3128-32e0 marks the next column at the bottom
    # and, if different, at the top of its 43-unit bounding rectangle.
    column = x // 51 + 1
    bottom, top = character_row(y), character_row(y - 43)
    rows = (bottom,) if top == bottom else (bottom, top)
    return tuple((column, row) for row in rows if 0 <= column < 10 and -1 <= row < 3)


@dataclass(frozen=True)
class CavernRoom(OpeningRoom):
    climb_redraw: dict | None = None
    floor_redraw: dict | None = None

    def draw_actor_foreground(self, frame, state, bounds):
        # QuickFloor 2:69b6-69e2 marks DrawHalf only for right-facing
        # poses 135-144, using the drawn left column and top row.
        clip = None
        if self.climb_redraw and state.facing and 135 <= state.action <= 144:
            column, _ = drawn_actor_columns(bounds, state.facing)
            row = character_row(min(365, bounds[1]))
            records = self.climb_redraw.get((state.action, column, row), ())
        elif self.floor_redraw:
            records = [record for cell in floor_redraw_cells(state, bounds)
                       for record in self.floor_redraw.get(cell, ())]
            clip = (max(0, bounds[0] + int(bool(state.facing))), max(0, bounds[1]),
                    min(510, bounds[2] + 1), min(365, bounds[3] + 1))
        else:
            return frame
        return self.draw_floor_records(frame, records, clip)

    def draw_falling_foreground(self, frame, x, y):
        records = [record for cell in falling_floor_redraw_cells(x, y)
                   for record in (self.floor_redraw or {}).get(cell, ())]
        # ComputeMobRect 5:32f6 uses width 87, bottom Y+1.
        return self.draw_floor_records(frame, records, (x, y - 43, x + 87, y + 1))

    def draw_floor_records(self, frame, records, clip):
        for sprite, position in records:
            if clip is not None:
                x, y = position
                left, top = max(x, clip[0]), max(y, clip[1])
                right, bottom = min(x + sprite.width, clip[2]), min(y + sprite.height, clip[3])
                if left >= right or top >= bottom:
                    continue
                sprite = sprite.crop((left - x, top - y, right - x, bottom - y))
                position = (left, top)
            frame.paste(sprite, position, sprite)
            # RedrawCell emits DrawHalf before DrawForeImg. Keep ordinary
            # foreground pillars in front of the repainted floor strip.
            x, y = position
            cover = self.foreground.crop((x, y, x + sprite.width, y + sprite.height))
            frame.paste(cover, position, cover)
        return frame


def cavern_exit_clip(terrain, room, row, state, record):
    # ClipChar 4:416a-420c: cavern DATA rectangle (17, 0, 364, 71).
    if state.actor_type != 0 or not 217 <= state.action <= 226 or state.current_y >= -24:
        return None
    column = character_column(floor_contact_x(state.target_x, state.facing, record))
    column += int(terrain.tile(room, column, row).kind == 16)
    return max(0, row * 120 + 17), min(510, column * 51 + 71)


def cavern_clip_top(terrain, room, row, state, bounds):
    """ClipChar 4:4230-43de, for the cavern environment (kind 3)."""
    if state.animation_state == 9 or state.actor_type in (7, 8):
        return 0
    # Entry/exit poses use a separate environment rectangle at 4:416a-420c.
    # Do not apply the ordinary-body branch to those poses.
    if state.actor_type == 0 and 217 <= state.action <= 226:
        return 0
    left, top, right, bottom = bounds
    boundary = row * 120 + 5
    char_top = min(365, top)
    if row != 0 and (bottom <= boundary or char_top <= boundary - 28):
        return 0
    if top - 1 >= boundary:
        return 0
    level_number = struct.unpack_from('>H', terrain.level, 0x218a)[0]
    if ((room == 15 and level_number == 9) or (room == 26 and level_number == 6)
            or (room == 0 and level_number == 14)):
        return 0
    if not (state.facing and 87 <= state.action <= 99):
        # GetCharEdges 4:5d20-5e52 expands width by one before GetCharCol.
        # character_column accepts foot-space X; drawn-space X is 21/22
        # pixels further right, depending on the mirrored sprite anchor.
        first, last = drawn_actor_columns(bounds, state.facing)
        top_row = character_row(char_top)
        first_tile = terrain.tile(room, first, top_row)
        if first_tile.kind in EMPTY_TILES:
            return 0
        if first_tile.room == 0 and level_number == 14:
            return 0
        if not (state.animation_state == 0 and state.action in (79, 81)):
            if terrain.tile(room, last, top_row).kind in EMPTY_TILES:
                return 0
    return boundary


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


def clipped_sprite(sprite, command):
    x, bottom = command[2:4]
    if len(command) >= 7:
        top, left, end_y, right = command[6]
        rect = (max(0, left - x), max(0, top - (bottom - sprite.height)),
                min(sprite.width, right - x), min(sprite.height, end_y - (bottom - sprite.height)))
        if rect[0] >= rect[2] or rect[1] >= rect[3]:
            return None
        x, bottom = x + rect[0], bottom - sprite.height + rect[3]
        sprite = sprite.crop(rect)
    return sprite, (x, bottom - sprite.height)


def merge_positioned_mask(existing, source, position):
    box = source.getbbox()
    if box is None:
        return existing
    x, y = position[0] + box[0], position[1] + box[1]
    source = source.crop(box)
    if existing is None:
        return source, (x, y)

    previous, previous_position = existing
    left, top = min(x, previous_position[0]), min(y, previous_position[1])
    right = max(x + source.width, previous_position[0] + previous.width)
    bottom = max(y + source.height, previous_position[1] + previous.height)
    combined = Image.new('L', (right - left, bottom - top))
    combined.paste(previous, (previous_position[0] - left, previous_position[1] - top))
    added = Image.new('L', combined.size)
    added.paste(source, (x - left, y - top))
    return ImageChops.lighter(combined, added), (left, top)


def draw_cavern_torches(frame, room_id, state):
    program, resources, palette, shapes = cavern_assets()
    for record in program.get('torches', {}).get(str(room_id), ()):
        tile = state.loose.tiles.get((record['room'], record['cell']))
        if tile is not None and tile[0] != 19:
            continue
        value = state.foreground(record['room'], record['cell'], record['foreground'])
        index = 3581 + (value & 15)
        if index not in shapes:
            shapes[index] = decode_shap(resources['SHAP'][index]['data'], palette)
        clipped = clipped_sprite(shapes[index], record['command'])
        if clipped is not None:
            sprite, position = clipped
            frame.paste(sprite, position, sprite)
    return frame


def recessed_lava_surface(palette):
    """Port-authored shallow cavity, indexed into the imported cavern palette."""
    artwork = json.loads(Path(__file__).with_name('lava_recess.json').read_text(encoding='ascii'))
    sprite = Image.new('RGBA', tuple(artwork['size']))
    for y, (left, row) in enumerate(artwork['rows']):
        for offset in range(0, len(row), 2):
            index = row[offset:offset + 2]
            if index != '--':
                sprite.putpixel((left + offset // 2, y), palette[int(index, 16)])
    return sprite


def recessed_lava_foreground_mask(surface):
    """Protect inset rock, near-side floor and crust embedded in the liquid."""
    mask = Image.new('L', surface.size)
    for x in range(surface.width):
        column = [surface.getpixel((x, y)) for y in range(surface.height)]
        liquid = [y for y, (r, g, b, a) in enumerate(column) if a and r == 255 and b == 0]
        crust = {y for y, pixel in enumerate(column) if pixel == (127, 0, 0, 255)}
        molten = set(liquid) | crust
        if not molten:
            continue
        for y in range(min(molten) + 1, surface.height):
            # The rear crust stays behind rising bubbles; only crust with
            # liquid both above and below belongs to an inset contour.
            if y not in molten or y in crust and liquid and liquid[0] < y < liquid[-1]:
                mask.putpixel((x, y), 255)
    return mask


def recessed_lava_liquid_mask(surface):
    mask = Image.new('L', surface.size)
    for y in range(surface.height):
        for x in range(surface.width):
            red, _, blue, alpha = surface.getpixel((x, y))
            if alpha and red == 255 and blue == 0:
                mask.putpixel((x, y), 255)
    return mask


def recessed_lava_inset_mask(surface):
    """Keep embedded stone/crust in front of even the raised particles."""
    liquid = recessed_lava_liquid_mask(surface)
    mask = Image.new('L', surface.size)
    for x in range(surface.width):
        rows = [y for y in range(surface.height) if liquid.getpixel((x, y))]
        if rows:
            for y in range(rows[0] + 1, rows[-1]):
                if surface.getpixel((x, y))[3] and not liquid.getpixel((x, y)):
                    mask.putpixel((x, y), 255)
    return mask


# Upper seed bands identify raised bodies in the native SHAPs. Follow their
# four-connected pixels, leaving the separate contact waves on the surface.
# These seeds are port presentation metadata, not Macintosh logic.
LAVA_AIR_ROWS = {3619: 4, 3620: 3, 3621: 3, 3625: 8, 3626: 5,
                 3632: 9, 3633: 7, 3634: 6, 3635: 5,
                 3639: 3, 3640: 2, 3641: 2, 3642: 2}


def split_lava_bubble(sprite, shape):
    surface, airborne = sprite.copy(), Image.new('RGBA', sprite.size)
    rows = min(sprite.height, LAVA_AIR_ROWS.get(shape, 0))
    pending = [(x, y) for y in range(rows) for x in range(sprite.width)
               if sprite.getpixel((x, y))[3]]
    visited = set()
    while pending:
        x, y = pending.pop()
        if not (0 <= x < sprite.width and 0 <= y < sprite.height) or (x, y) in visited:
            continue
        visited.add((x, y))
        pixel = sprite.getpixel((x, y))
        if not pixel[3]:
            continue
        airborne.putpixel((x, y), pixel)
        surface.putpixel((x, y), (0, 0, 0, 0))
        pending.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
    return surface, airborne


def draw_cavern_lava(frame, room_id, state):
    program, resources, palette, shapes = cavern_assets()
    for record in program.get('lava', {}).get('rooms', {}).get(str(room_id), ()):
        pool = state.lava.pools.get((record['room'], record['cell']))
        if pool is None:
            continue
        foreground = inset_foreground = None
        airborne = []
        if pool.enhanced:
            if ('recessed', 3614) not in shapes:
                shapes['recessed', 3614] = recessed_lava_surface(palette)
            base = shapes['recessed', 3614]
            if ('recessed-liquid', 3614) not in shapes:
                shapes['recessed-liquid', 3614] = recessed_lava_liquid_mask(base)
            liquid = shapes['recessed-liquid', 3614]
            base_dx, base_dy = pool.tables['piece_offsets']
            liquid_x, liquid_y = record['x'] + base_dx, record['bottom'] + base_dy - base.height
        for shape, dx, dy, mirrored in pool.drawings():
            key = ('recessed', shape) if pool.enhanced and shape == 3614 else shape
            if key not in shapes:
                shapes[key] = (recessed_lava_surface(palette) if key != shape else
                               decode_shap(resources['SHAP'][shape]['data'], palette))
            sprite = shapes[key]
            if mirrored:
                sprite = ImageOps.mirror(sprite)
            position = record['x'] + dx, record['bottom'] + dy - sprite.height
            if pool.enhanced and 3616 <= shape <= 3645:
                effect_key = ('recessed-effect', shape)
                if effect_key not in shapes:
                    shapes[effect_key] = split_lava_bubble(sprite, shape)
                surface, raised = shapes[effect_key]
                x, y = position[0] - liquid_x, position[1] - liquid_y
                clip = liquid.crop((x, y, x + sprite.width, y + sprite.height))
                sprite = surface.copy()
                sprite.putalpha(ImageChops.multiply(surface.getchannel('A'), clip))
                if raised.getbbox() is not None:
                    airborne.append((raised, position))
            frame.paste(sprite, position, sprite)
            if key != shape:
                mask_key = ('recessed-front', shape)
                if mask_key not in shapes:
                    shapes[mask_key] = recessed_lava_foreground_mask(sprite)
                inset_key = ('recessed-inset', shape)
                if inset_key not in shapes:
                    shapes[inset_key] = recessed_lava_inset_mask(sprite)
                x, y = position
                snapshot = frame.crop((x, y, x + sprite.width, y + sprite.height))
                foreground = (snapshot, position, shapes[mask_key])
                inset_foreground = (snapshot, position, shapes[inset_key])
        if foreground is not None:
            # Restore solid contours, never the liquid or rear rim.
            frame.paste(*foreground)
        for sprite, position in airborne:
            frame.paste(sprite, position, sprite)
        if inset_foreground is not None and airborne:
            # Raised drops may cross the rear rim, never the near-side rock.
            frame.paste(*foreground)
            frame.paste(*inset_foreground)
    return frame


def cavern_scene_signature(program, room_id, state):
    metadata = program.get('loose_floors', {})
    cells = metadata.get('rooms', {}).get(str(room_id), {}).get('cells', ())
    indices = []
    for room, cell in cells:
        choices = metadata['cells'][f'{room}:{cell}']
        kind, foreground = state.loose.tiles.get((room, cell), choices[0])
        if choices[0][0] == 11:
            index = (int(bool(metadata['shifts'][foreground & 15])) if kind == 11 else
                     2 if (room, cell) in state.loose.cleared or len(choices) == 3 else 3)
        else:
            index = next(i for i, value in enumerate(choices) if value[0] == kind and
                         (choices[0][0] != choices[1][0]
                          or value[1] & 0xf0ff == foreground & 0xf0ff))
        indices.append(str(index))
    return ''.join(indices)


def draw_cavern_falling(frame, room_id, state, level, art):
    from pop2.terrain import LevelMap

    _program, resources, palette, shapes = cavern_assets()
    terrain = LevelMap(level)
    redraw = []
    for block in state.loose.falling:
        if block.room == room_id:
            y = block.y
        elif block.room == terrain.neighbor(room_id, 'up') and block.room is not None:
            y = block.y - 364
        elif block.room == terrain.neighbor(room_id, 'down') and block.room is not None:
            y = block.y + 364
        else:
            continue
        # DrawObjCaveLoose 8:2bb4-2bf4 adds the upper lip and stone body.
        for index, bottom in ((3557, y - 18), (3604, y)):
            sprite = cavern_command_sprite(['back', index, block.x, bottom, 16],
                                            resources, palette, shapes)
            frame.paste(sprite, (block.x, bottom - sprite.height), sprite)
        redraw.append((block.x, y))
    for x, y in redraw:
        art.draw_falling_foreground(frame, x, y)
    return frame


def cavern_command_sprite(command, resources, palette, shapes):
    library = command[7] if len(command) >= 8 else 4
    index, flags = command[1], command[4]
    key = (library, index, flags) if library == 1 else index
    if key not in shapes:
        if library == 1:
            source, colors = flask_assets()
            shapes[key] = flask_shape(source['SHAP'][index]['data'], colors, flags)
        elif library == 4:
            shapes[key] = decode_shap(resources['SHAP'][index]['data'], palette)
        else:
            raise ValueError(f'Unsupported cavern shape library {library}')
    return shapes[key]


def cavern_pressure_signature(program, room_id, state):
    records = program.get('pressure_plates', {}).get('rooms', {}).get(str(room_id), ())
    phases = []
    for record in records:
        value = state.plates.foreground.get((record['room'], record['cell']), record['foreground'])
        phases.append(min(value & 255, 184) // 4 if record['kind'] == 4 else
                      min(value & 255, 79) if record['kind'] == 17 else int(bool(value & 0x2000)))
    return tuple(phases)


def pressure_drawing_commands(commands, records, phases, resources):
    overrides = {tuple(key): (record, phase) for record, phase in zip(records, phases)
                 for key in record['commands']}
    # DrawHalf reuses the plate's drawing slot in its front-only climb repaint.
    for key, item in tuple(overrides.items()):
        if item[0]['kind'] not in (4, 17):
            overrides[('front', *key[1:])] = item
    result = []
    for source in commands:
        key = (source[0], 3554 if source[1] == 3555 else source[1], *source[7:10])
        item = overrides.get(key)
        if item is None:
            result.append(source)
            continue
        record, phase = item
        command = list(source)
        if record['kind'] in (4, 17):
            # Stone gates move two pixels/quarter-phase; exits move one pixel.
            # Both keep their native row clip and the SHAP's bottom alignment.
            exit_door = record['kind'] == 17
            initial = (min(record['foreground'] & 255, 79) if exit_door else
                       min(record['foreground'] & 255, 184) // 4)
            command[3] -= (1 if exit_door else 2) * (phase - initial)
            height = struct.unpack_from('>H', resources['SHAP'][command[1]]['data'], 6)[0]
            clip = list(command[6])
            clip[0] = max(0, command[5] * 120 + (1 if exit_door else -31), command[3] - height)
            clip[2] = min(365, command[3])
            if clip[0] >= clip[2]:
                continue
            command[6] = clip
        else:
            command[1] = 3554 + phase
        result.append(command)
    return result


def cavern_room(room_id=0, entry_frame=0, animated=False, loose_key='', pressure_key=()):
    program, resources, palette, shapes = cavern_assets()
    if program.get('version') in (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13) and program.get('level') == 3:
        commands = program['rooms'][str(room_id)]
    elif (program.get('version'), program.get('level'), program.get('room')) == (1, 3, room_id):
        commands = program['commands']
    else:
        raise ValueError('Unsupported cavern drawing export')
    entry = program.get('entry_exit')
    variant = program.get('loose_floors', {}).get('rooms', {}).get(str(room_id), {}).get(
        'variants', {}).get(loose_key)
    if variant is not None:
        commands = variant['commands']
    if entry is not None and room_id == entry['room']:
        commands = (variant['entry_frames'][entry_frame] if variant is not None else
                    entry['frames'][entry_frame]['commands'])
    if pressure_key:
        records = program.get('pressure_plates', {}).get('rooms', {}).get(str(room_id), ())
        commands = pressure_drawing_commands(commands, records, pressure_key, resources)
    background = Image.new('RGBA', (510, 365), (0, 0, 0, 255))
    foreground = Image.new('RGBA', background.size)
    masks = {row: Image.new('L', background.size) for row in range(-1, 5)}
    cell_masks = {} if program.get('version') >= 6 else None
    for command in commands:
        layer, index, _, _, _, row = command[:6]
        library = command[7] if len(command) >= 8 else 4
        if animated and program.get('version') >= 4 and library == 4 and 3581 <= index <= 3589:
            continue
        clipped = clipped_sprite(cavern_command_sprite(command, resources, palette, shapes), command)
        if clipped is None:
            continue
        sprite, position = clipped
        destination = background if layer == 'back' else foreground
        destination.paste(sprite, position, sprite)
        if layer == 'front':
            mask = Image.new('L', background.size)
            mask.paste(sprite.getchannel('A'), position)
            if row in masks:
                masks[row] = ImageChops.lighter(masks[row], mask)
            if cell_masks is not None and len(command) >= 10:
                cell = (command[8], command[9])
                merged = merge_positioned_mask(cell_masks.get(cell), sprite.getchannel('A'), position)
                if merged is not None:
                    cell_masks[cell] = merged
    redraw = {}
    climb_commands = (variant['climb_redraw'] if variant is not None else
                      program.get('climb_redraw', {}).get(str(room_id), {}))
    for action, redraw_commands in climb_commands.items():
        if pressure_key:
            redraw_commands = pressure_drawing_commands(redraw_commands, records, pressure_key, resources)
        for command in redraw_commands:
            clipped = clipped_sprite(cavern_command_sprite(command, resources, palette, shapes), command)
            if clipped is not None:
                cell = (int(action), command[8], command[9])
                redraw.setdefault(cell, []).append(clipped)
    floors = {}
    floor_commands = (variant['floor_redraw'] if variant is not None else
                      program.get('floor_redraw', {}).get(str(room_id), ()))
    if pressure_key:
        floor_commands = pressure_drawing_commands(floor_commands, records, pressure_key, resources)
    for command in floor_commands:
        clipped = clipped_sprite(cavern_command_sprite(command, resources, palette, shapes), command)
        if clipped is not None:
            floors.setdefault(tuple(command[8:10]), []).append(clipped)
    return CavernRoom(background, foreground, masks, (), (), room_id, 3, cell_masks, redraw, floors)
