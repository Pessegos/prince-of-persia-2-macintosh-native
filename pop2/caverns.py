"""Portable drawing commands for the recovered cavern levels."""

import json
import struct
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageOps

from pop2.paths import ASSET_DIR
from pop2.cavern_retouch import retouched_sprite
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
    retained_mask: Image.Image | None = None
    gate_occlusion: dict | None = None

    def actor_mask(self, row, bottom=None, state=None, bounds=None, record=None):
        mask = super().actor_mask(row, bottom, state, bounds, record)
        # CheckGateInFore 3:2722-2762/2860 peels the movable gate over
        # actors in its own/preceding column, except hanging modes 2/6.
        if (not self.gate_occlusion or state is None or record is None
                or state.actor_type == 11 or state.animation_state in (2, 6)):
            return mask
        column = character_column(floor_contact_x(state.target_x, state.facing, record))
        mask = mask.copy()
        cells = ((column, row), (column + 1, row))
        if state.source_sequence_id == 118 and 264 <= state.action <= 266:
            # The flattened body's foot moves past the gate in one facing.
            # Keep the actual overlapping stone in front throughout the crush.
            cells = tuple(cell for cell in self.gate_occlusion if cell[1] == row)
        for cell in cells:
            positioned = self.gate_occlusion.get(cell)
            if positioned is not None:
                cover, (x, y) = positioned
                rect = (x, y, x + cover.width, y + cover.height)
                mask.paste(ImageChops.lighter(mask.crop(rect), cover), (x, y))
        return mask

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


# Levels whose scenery is the original renderer's export, by LEVL environment:
# caverns (3) and ruins (4, levels six and seven).
SCENERY_LEVELS = {3: (3, 4, 5), 4: (6, 7)}
RUINS_LEVELS = SCENERY_LEVELS[4]
# CUST room enter hooks loading CTBL over entries 64+ (S03_508A): level five's
# carpet room (CheckCarpetImg 8:0d30, CTBL 3501) and level six's start room
# (CUST kind 22, 7:37a6, CTBL 3502).
ROOM_PALETTES = {(5, 2): 3501, (6, 26): 3502}


def scenery_name(level_number):
    if level_number == 3:
        return 'caverns_entry.json'
    return f"{'ruins' if level_number in RUINS_LEVELS else 'caverns'}_level{level_number}.json"


# The room whose exit closes behind the Prince as he enters. Level six's
# cliff exit (S07_373E, called from CutChar 6:4d7c-4d92) brings him out of
# native room 3's door instead of its start room.
ENTRY_ROOMS = {6: 2}


def entry_room(level_number, start_room):
    return ENTRY_ROOMS.get(level_number, start_room)


def scenery_available(level_number):
    # Imports before level six's support lack the ruins files.
    return ((ASSET_DIR / scenery_name(level_number)).is_file()
            and (ASSET_DIR / scenery_resource(level_number)).is_file())


def scenery_resource(level_number):
    return 'Ruins.rsrc' if level_number in RUINS_LEVELS else 'Caverns.rsrc'


def cavern_assets(level_number=3):
    if type(level_number) is not int or level_number not in (3, 4, 5, *RUINS_LEVELS):
        raise ValueError(f'Unsupported cavern scenery level {level_number}')
    return _cavern_assets(level_number)


def room_assets(level_number, room_id):
    """cavern_assets with the palette of the room on screen.

    Room 3 of level five is a CUST kind-0 room; its enter hook CheckCarpetImg
    (8:0d30, table a5-0x4c2e) loads CTBL 3501 over entries 64-183.
    """
    program, resources, palette, shapes = cavern_assets(level_number)
    if (level_number, room_id) not in ROOM_PALETTES:
        return program, resources, palette, shapes
    return program, resources, *_custom_room_palette(level_number, room_id)


@lru_cache(maxsize=2)
def _custom_room_palette(level_number, room_id):
    _program, resources, palette, _shapes = cavern_assets(level_number)
    palette = dict(palette)
    palette.update(decode_ctbl(resources['CTBL'][ROOM_PALETTES[level_number, room_id]]['data']))
    return palette, {}


@lru_cache(maxsize=3)
def _cavern_assets(level_number):
    program = json.loads((ASSET_DIR / scenery_name(level_number)).read_text(encoding='ascii'))
    if program.get('level') != level_number:
        raise ValueError('Cavern scenery belongs to a different level')
    resources = load_resource_file(scenery_resource(level_number))
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
    # RemapCTBL 17:6a78 starts at 224, not 224 + the original first index (1).
    palette = {223 + index: color for index, color in decode_ctbl(resources['CTBL'][3000]['data']).items()}
    return resources, palette


def cavern_flask_instances(program, room_id, terrain):
    for command in program['rooms'][str(room_id)]:
        if len(command) < 10 or command[7] != 1 or command[1] not in (3001, 3002):
            continue
        tile = terrain.tile(room_id, command[8], command[9])
        if tile.room is not None and tile.kind == 10:
            yield command, tile


def draw_cavern_flasks(frame, room_id, state, terrain, *, level_number=3):
    program, resources, palette, shapes = cavern_assets(level_number)
    terrain.caverns = state
    for command, tile in cavern_flask_instances(program, room_id, terrain):
        value = tile.foreground
        kind, phase = (value >> 5) & 7, value & 31
        large = 2 <= kind < 5
        body = list(command)
        body[1] = 3002 if large else 3001
        sprite = cavern_command_sprite(body, resources, palette, shapes)
        frame.paste(sprite, (body[2], body[3] - sprite.height), sprite)
        # DrawFlask 3:46fc draws two monochrome layers, mirrored in the
        # second half of the cycle, with a quiet interval at phases 10-13/24-27.
        if not kind or phase in range(10, 14) or phase >= 24:
            continue
        ink = 233 if kind in (1, 2) else 237 if kind == 5 else 235
        mirrored = phase >= 14
        phase -= 14 if mirrored else 0
        x = body[2] - 4
        bottom = body[3] - (22 if large else 18)
        for shape, color in ((3003 + phase, ink), (3013 + phase, ink + 1)):
            bubble = cavern_command_sprite(['front', shape, x, bottom, color, 0, [], 1],
                                            resources, palette, shapes)
            if mirrored:
                bubble = ImageOps.mirror(bubble)
            frame.paste(bubble, (x, bottom - bubble.height), bubble)
    return frame


def draw_sword_items(frame, room_id, state, terrain, *, level_number=6):
    # Sword items (tile 22, library 0, a front command) leave the scenery
    # once picked up.
    program, resources, palette, shapes = cavern_assets(level_number)
    terrain.caverns = state
    for command in program['rooms'][str(room_id)]:
        if len(command) < 10 or command[7] != 0:
            continue
        tile = terrain.tile(room_id, command[8], command[9])
        if tile.room is None or tile.kind != 22:
            continue
        clipped = clipped_sprite(cavern_command_sprite(command, resources, palette, shapes), command)
        if clipped is not None:
            sprite, position = clipped
            frame.paste(sprite, position, sprite)
    return frame


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


def draw_cavern_torches(frame, room_id, state, *, level_number=3):
    program, resources, palette, shapes = room_assets(level_number, room_id)
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


def draw_cavern_lava(frame, room_id, state, *, level_number=3):
    program, resources, palette, shapes = room_assets(level_number, room_id)
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
            shifts = metadata['shifts']
            if isinstance(shifts[0], list):
                # Ruins: one shake table per column parity. Both nonzero shake
                # images share the exported phase-1 variant.
                shifts = shifts[cell % 10 & 1]
            index = (int(bool(shifts[foreground & 15])) if kind == 11 else
                     2 if (room, cell) in state.loose.cleared or len(choices) == 3 else 3)
        else:
            index = next(i for i, value in enumerate(choices) if value[0] == kind and
                         (choices[0][0] != choices[1][0]
                          or value[1] & 0xf0ff == foreground & 0xf0ff))
        indices.append(str(index))
    return ''.join(indices)


def draw_cavern_falling(frame, room_id, state, level, art, *, level_number=3):
    from pop2.terrain import LevelMap

    _program, resources, palette, shapes = room_assets(level_number, room_id)
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
        # DrawObjLoose 3:412c-41aa: the caverns' DrawObjCaveLoose (8:2bb4)
        # draws the upper lip and stone body; the ruins draw pieces 14 and 18
        # at the slab's own bottom.
        pieces = (((3514, y), (3518, y)) if level_number in RUINS_LEVELS
                  else ((3557, y - 18), (3604, y)))
        for index, bottom in pieces:
            sprite = cavern_command_sprite(['back', index, block.x, bottom, 16],
                                            resources, palette, shapes)
            frame.paste(sprite, (block.x, bottom - sprite.height), sprite)
        redraw.append((block.x, y))
    for x, y in redraw:
        art.draw_falling_foreground(frame, x, y)
    return frame


def draw_cavern_spikes(frame, room_id, state, terrain, front=False, *, level_number=3):
    _program, resources, palette, shapes = room_assets(level_number, room_id)
    for command in state.spikes.drawing_commands(terrain, room_id, front):
        sprite = cavern_command_sprite(command, resources, palette, shapes)
        frame.paste(sprite, (command[2], command[3] - sprite.height + 1), sprite)
    return frame


def draw_cavern_darts(frame, room_id, state, *, level_number=3):
    _program, resources, palette, shapes = room_assets(level_number, room_id)
    for dart in state.plates.darts.projectiles:
        # 8:2e1a emits a type-2 object only in the current room and while
        # flying. DrawObj passes one-based shape 94. AddMid stores slot 93,
        # but SHPL:3500 starts at 3501, so the resource is SHAP:3594.
        if dart.room != room_id or dart.dy in (-3, -1):
            continue
        sprite = cavern_command_sprite(['back', 3594, dart.x, dart.y, 16],
                                        resources, palette, shapes)
        frame.paste(sprite, (dart.x, dart.y - sprite.height + 1), sprite)
    return frame


def draw_bridge_planks(frame, room_id, state, *, level_number=3):
    from pop2.bridge import BRIDGE_LEVEL, BRIDGE_ROOM

    # ATMBrgFloor 8:0a5a-0a6e draws plank mobs only in level five's room 10.
    if level_number != BRIDGE_LEVEL or room_id != BRIDGE_ROOM:
        return frame
    _program, resources, palette, shapes = cavern_assets(level_number)
    for record, x, bottom in state.bridge.plank_drawings():
        # Room 10's CUST records 3-9 hold SHAP 4226-4232 (base 4225 + record - 2).
        sprite = cavern_command_sprite(['back', 4223 + record, x, bottom, 16], resources, palette, shapes)
        frame.paste(sprite, (x, bottom - sprite.height), sprite)
    return frame


@lru_cache(maxsize=1)
def carpet_palette():
    # CheckCarpetImg 8:0d30 loads CTBL 25303 over entries 32-46. Entries
    # 16-31 hold the cavern Prince palette (Kid CTBL 25003) one bank up, as
    # an emulator capture of the unused carpet confirms pixel for pixel.
    palette = {index + 15: color for index, color in
               decode_ctbl(load_resource_file('Kid.rsrc')['CTBL'][25003]['data']).items()}
    palette.update(decode_ctbl(load_resource_file('Caverns.rsrc')['CTBL'][25303]['data']))
    return palette


def carpet_sprite(shape, resources, shapes):
    key = ('carpet', shape)
    if key not in shapes:
        shapes[key] = decode_shap(resources['SHAP'][shape]['data'], carpet_palette())
    return shapes[key]


def draw_carpet(frame, room_id, state, prince=None, *, level_number=3):
    """DrawCarpet 8:0e48 (unused carpet) or SetupCarpet 8:12b6 (ridden).

    `prince` is (x, y, facing, action) for the Prince in this room.
    """
    from pop2.carpet import RIDE_FRAME, STATIC_BOTTOM, STATIC_SHAPE, STATIC_X, carpet_room

    if not carpet_room(level_number, room_id):
        return frame
    _program, resources, _palette, shapes = cavern_assets(level_number)
    carpet = state.carpet
    if not carpet.counter:
        sprite = carpet_sprite(STATIC_SHAPE, resources, shapes)
        frame.paste(sprite, (STATIC_X, STATIC_BOTTOM - sprite.height), sprite)
    elif prince is not None and prince[3] == RIDE_FRAME:
        shape, x, bottom = carpet.drawing(prince[0], prince[1], prince[2])
        sprite = carpet_sprite(shape, resources, shapes)
        frame.paste(sprite, (x, bottom - sprite.height), sprite)
    return frame


def cavern_command_sprite(command, resources, palette, shapes):
    library = command[7] if len(command) >= 8 else 4
    index, flags = command[1], command[4]
    key = (library, index, flags) if library == 1 or flags == 0 else index
    if key not in shapes:
        if library == 1:
            source, colors = flask_assets()
            shapes[key] = flask_shape(source['SHAP'][index]['data'], colors, flags)
        elif library == 4:
            shapes[key] = decode_shap(resources['SHAP'][index]['data'], palette)
            if flags == 0:
                # Native transfer mode 0 copies zero/black too; mode 16 masks it.
                shapes[key].putalpha(255)
        elif library == 0:
            # A sword item (tile 22): the sword set (SHPL 1000), drawn with
            # the ruins' sword colours (Prince CTBL 1004 at entry 239).
            source = load_resource_file('Prince.rsrc')
            colors = {239 + entry: color for entry, color in
                      decode_ctbl(source['CTBL'][1004]['data']).items()}
            shapes[key] = decode_shap(source['SHAP'][index]['data'], colors)
        else:
            raise ValueError(f'Unsupported cavern shape library {library}')
    return shapes[key]


def cavern_pressure_signature(program, room_id, state):
    records = program.get('pressure_plates', {}).get('rooms', {}).get(str(room_id), ())
    phases = []
    for record in records:
        value = state.plates.foreground.get((record['room'], record['cell']), record['foreground'])
        if record['kind'] == 4:
            presentation = state.crush.gate_phase((record['room'], record['cell']))
            if presentation is not None:
                value = (value & 0xff00) | presentation
        phases.append(min(value & 255, 184) // 4 if record['kind'] == 4 else
                      min(value & 255, 79) if record['kind'] == 17 else
                      value & 7 if record['kind'] in (27, 33) else int(bool(value & 0x2000)))
    return tuple(phases)


# Row clip of a moving door's SHAP relative to its row's top: the export
# shows the ruins gate (3542) clipped 19 pixels above it and their exit
# (3547) 10 above, against the caverns' 31 and 1 below.
DOOR_CLIP_TOP = {3562: -31, 3563: -31, 3566: 1, 3542: -19, 3547: -10}


def pressure_drawing_commands(commands, records, phases, resources):
    overrides = {tuple(key): (record, phase) for record, phase in zip(records, phases)
                 for key in record['commands']}
    # Ruins plates store the toggled state's commands for each changed slot.
    toggled = {tuple(key): command for record in records
               for key, command in zip(record['commands'], record.get('toggled', ()))}
    # DrawHalf reuses the plate's drawing slot in its front-only climb repaint.
    for key, item in tuple(overrides.items()):
        if item[0]['kind'] in (5, 6, 34):
            overrides[('front', *key[1:])] = item
    result = []
    for source in commands:
        key = (source[0], 3554 if source[1] == 3555 else source[1], *source[7:10])
        if 3591 <= source[1] <= 3593:
            key = (source[0], 3591, *source[7:10])
        if source[1] in (4052, 4053, 4064):
            key = (source[0], 4051, *source[7:10])
        item = overrides.get(key)
        if item is None:
            result.append(source)
            continue
        record, phase = item
        command = list(source)
        if 'toggled' in record:
            if phase != int(bool(record['foreground'] & 0x2000)):
                stored = toggled.get(key) or toggled[('back', *key[1:])]
                command = [source[0], *stored[1:]]
            result.append(command)
            continue
        if record['kind'] == 27:
            # DrawCaveBars 8:15c0 draws CUST record (phase + 1); a native redraw
            # of each phase only changes this SHAP.
            command[1] = (4051, 4052, 4053, 4064)[min(phase, 3)]
        elif record['kind'] == 33:
            # DrawCaveDart's DATA table at A5-2f3e. All three mouth
            # shapes share the PIEC anchor, but have different dimensions.
            command[1] = (3591, 3593, 3592, 3591, 3591, 3591, 3591)[phase]
            width, height = struct.unpack_from('>hH', resources['SHAP'][command[1]]['data'], 4)
            command[6] = [max(0, command[3] - height), max(0, command[2]),
                          min(365, command[3]), min(510, command[2] + width)]
        elif record['kind'] in (4, 17):
            # Stone gates move two pixels/quarter-phase; exits move one pixel.
            # Both keep their native row clip and the SHAP's bottom alignment.
            exit_door = record['kind'] == 17
            initial = (min(record['foreground'] & 255, 79) if exit_door else
                       min(record['foreground'] & 255, 184) // 4)
            command[3] -= (1 if exit_door else 2) * (phase - initial)
            height = struct.unpack_from('>H', resources['SHAP'][command[1]]['data'], 6)[0]
            clip = list(command[6])
            clip[0] = max(0, command[5] * 120 + DOOR_CLIP_TOP.get(command[1], 1 if exit_door else -31),
                          command[3] - height)
            clip[2] = min(365, command[3])
            if clip[0] >= clip[2]:
                continue
            command[6] = clip
        else:
            command[1] = 3554 + phase
        result.append(command)
    return result


def delta_commands(base, items):
    """Rebuild a command list stored as base slices ([start, stop]) and commands."""
    result = []
    for item in items:
        if isinstance(item[0], int):
            result.extend(base[item[0]:item[1]])
        else:
            result.append(item)
    return result


def loose_variant(program, room_id, loose_key):
    """A loose-floor variant, expanding the ruins' delta-encoded form."""
    room = program.get('loose_floors', {}).get('rooms', {}).get(str(room_id), {})
    variant = room.get('variants', {}).get(loose_key)
    if variant is None or not room.get('delta'):
        return variant
    entry = program.get('entry_exit')
    climb = program.get('climb_redraw', {}).get(str(room_id), {})
    decoded = {'commands': delta_commands(program['rooms'][str(room_id)], variant['commands']),
               'floor_redraw': delta_commands(program['floor_redraw'][str(room_id)],
                                              variant['floor_redraw']),
               'climb_redraw': {action: delta_commands(climb.get(action, []), items)
                                for action, items in variant['climb_redraw'].items()}}
    if 'entry_frames' in variant:
        decoded['entry_frames'] = [delta_commands(frame['commands'], items)
                                   for frame, items in zip(entry['frames'], variant['entry_frames'])]
    return decoded


def without_fallen_planks(commands, fallen):
    # Native room-10 redraws with the emptied bridge cells (8:0c3e-0c54) only
    # omit those cells' CUST plank (SHAP 4226), in every collapse stage.
    return [command for command in commands
            if not (command[1] == 4226 and len(command) >= 10
                    and command[9] == 1 and command[8] in fallen)]


def cavern_room(room_id=0, entry_frame=0, animated=False, loose_key='', pressure_key=(), retouched=False,
                *, level_number=3, bridge_fallen=frozenset()):
    program, resources, palette, shapes = room_assets(level_number, room_id)

    def scenery_sprite(command):
        sprite = cavern_command_sprite(command, resources, palette, shapes)
        return retouched_sprite(room_id, command, sprite) if retouched and level_number == 3 else sprite

    if (program.get('version') in (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15)
            and program.get('level') == level_number):
        commands = program['rooms'][str(room_id)]
    elif (program.get('version'), program.get('level'), program.get('room')) == (1, level_number, room_id):
        commands = program['commands']
    else:
        raise ValueError('Unsupported cavern drawing export')
    entry = program.get('entry_exit')
    variant = loose_variant(program, room_id, loose_key)
    if variant is not None:
        commands = variant['commands']
    if entry is not None and room_id == entry['room']:
        commands = (variant['entry_frames'][entry_frame] if variant is not None else
                    entry['frames'][entry_frame]['commands'])
    records = program.get('pressure_plates', {}).get('rooms', {}).get(str(room_id), ())
    if pressure_key:
        commands = pressure_drawing_commands(commands, records, pressure_key, resources)
    if bridge_fallen:
        commands = without_fallen_planks(commands, bridge_fallen)
    gate_cells = {tuple(key[-2:]) for record in records if record['kind'] == 4
                  for key in record['commands']}
    background = Image.new('RGBA', (510, 365))
    foreground = Image.new('RGBA', background.size)
    masks = {row: Image.new('L', background.size) for row in range(-1, 5)}
    cell_masks = {} if program.get('version') >= 6 else None
    gate_masks = {}
    for command in commands:
        layer, index, _, _, _, row = command[:6]
        library = command[7] if len(command) >= 8 else 4
        if animated and library in (0, 1):
            continue
        if animated and program.get('version') >= 4 and library == 4 and 3581 <= index <= 3589:
            continue
        clipped = clipped_sprite(scenery_sprite(command), command)
        if clipped is None:
            continue
        sprite, position = clipped
        destination = background if layer == 'back' else foreground
        destination.paste(sprite, position, sprite)
        cell = tuple(command[8:10])
        if layer == 'back' and library == 4 and index in (3563, 3542) and cell in gate_cells:
            # DrawCaveGate anchors the stone one column right of its tile.
            # The repaint caller may be a different cell, even on another row.
            # CheckGateInFore tests the gate's tile, not that repaint caller.
            gate_cell = (command[2] // 51 - 1, command[5])
            gate_masks[gate_cell] = merge_positioned_mask(
                gate_masks.get(gate_cell), sprite.getchannel('A'), position)
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
        if bridge_fallen:
            redraw_commands = without_fallen_planks(redraw_commands, bridge_fallen)
        for command in redraw_commands:
            if animated and len(command) >= 8 and command[7] == 1:
                continue
            clipped = clipped_sprite(scenery_sprite(command), command)
            if clipped is not None:
                cell = (int(action), command[8], command[9])
                redraw.setdefault(cell, []).append(clipped)
    floors = {}
    floor_commands = (variant['floor_redraw'] if variant is not None else
                      program.get('floor_redraw', {}).get(str(room_id), ()))
    if pressure_key:
        floor_commands = pressure_drawing_commands(floor_commands, records, pressure_key, resources)
    if bridge_fallen:
        floor_commands = without_fallen_planks(floor_commands, bridge_fallen)
    for command in floor_commands:
        if animated and len(command) >= 8 and command[7] == 1:
            continue
        clipped = clipped_sprite(scenery_sprite(command), command)
        if clipped is not None:
            floors.setdefault(tuple(command[8:10]), []).append(clipped)
    retained = ImageChops.invert(ImageChops.lighter(
        background.getchannel('A'), foreground.getchannel('A')))
    background = Image.alpha_composite(Image.new('RGBA', background.size, 'black'), background)
    return CavernRoom(background, foreground, masks, (), (), room_id, 3, cell_masks,
                      redraw, floors, retained, gate_masks)
