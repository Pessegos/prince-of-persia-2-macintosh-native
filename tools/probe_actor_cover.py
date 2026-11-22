"""Compare what hides the Prince in the port's frame with the original's
per-character redraw.

The original draws the room, then the characters, then repaints over them
what their setup marked (SetupKid 3:0eec): GetCharEdges 4:5cbc gives the
character's rectangle, QuickFloor 2:697e marks floor cells (MarkFloor
5:1846, that rectangle) or, for the right-facing climb, half cells (MarkHalf
5:18ac), ClipChar 4:4146 clips the drawing, and MarkBufsForRect 5:19f8 marks
every cell the rectangle covers for a front redraw (MarkFRedraw 5:1990; the
border row through MarkTop 5:16f2). RedrawCell 3:1d3a then draws, per cell,
the floor records (DrawFloorBuf 3:371c clipped to the cell and the floor
rectangle) or the half records (DrawHalf 3:3480, the cell), and the front
pieces (DrawForeImg 3:2598, the cell and the front rectangle, with
CheckGateInFore 3:26e4's stone). RedrawTopFast 3:1f4e queues front pieces
in the border strip and the marked rectangle. Its back passes enter the
back table (3:00f6), dumped before the object and front tables (3:3362-3378).

`tools.native_character` runs that setup on the executable and
`recover_room` each marked cell's drawers with the Prince's fields. The
port side is the real hidden game (`tools.audit_temple_routes.Harness`):
real keys drive the Prince through short macros from floor positions of
every room, his sprite is drawn in magenta and the rendered frame tells
which of his pixels show. For each frame:

- `missing`: Prince pixels the original hides that the port shows.
- `extra`: Prince pixels the port hides that the original shows.

Supplied, not recovered: the Prince's drawn position and shape (the port's
bounds and sprite; GetCharEdges gets their anchor, bottom and size), his
column (GetCharCol as the port computes it), his sequence mode (for
IsCharNonViewable 4:471e), the level words (as loaded, with the port's
current loose-floor tiles, flasks (drunk or bubbling, Potions) and trigger
words written in each frame: gates, plates, bars, scythe blades; level
5's planks stay at rest) and the
port's SHAP decoder for both sides. Guards are hidden (peaceful), the sword
and the hit star are not drawn, and frames whose drawn height differs
(sinking, `drawn_player`) are skipped. Counted apart, not as differences:
the approved port exceptions (`approved_exception`) and frames where a
sliding rock, a falling slab (of this room or the one above or below), a
flying dart, a spike's front piece or level 8's throne bars (7:2b22-2b4a)
overlaps the Prince (`moving_object`: objects drawn over the characters,
not modelled here), frames where he overlaps a flask ('item': both sides
draw it over him, but this painter does not mirror the bubbles of phases
14-23), the exit's frame over him on the stairs ('exit': drawn by the
exit's object, 8:1cfe-1d48 and 7:27c0) or an arrival horse statue
('statue': level 10's native room 22 and level 14's room 1, DrawHorse
3:23f0-2414 through 3:4572/4608, which recover_room does not run). Not covered: opponents, the sword's
extension of the floor rectangle (a5-0x521a, QuickFloor 2:6996) and the
sword and flame objects.
"""

import argparse
from collections import Counter
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import struct
import sys

import numpy as np
from PIL import Image, ImageOps

from pop2.caverns import cavern_command_sprite, clipped_sprite, scenery_resource
from pop2.mac_resources import parse_resource_fork
from pop2.opponent_generation import character_column
from pop2.terrain import floor_contact_x
from tools.extract_caverns import CavernRecovery, recover_room
from tools.native_character import CHARACTER, KID_COPY, RECT, NativeCharacter
from tools.probe_foreground_cells import probe_level

SIZE = (365, 510)
MAGENTA = (255, 0, 255)
SCENERY = {1: 'Rooftops.rsrc', 2: 'Desert.rsrc'}
# (name, [(tick, key, pressed)], ticks). 'F'/'B' are forward and back.
MACROS = (
    ('stand', (), 2),
    ('run', ((0, 'F', True),), 16),
    ('step', ((0, 'shift', True), (0, 'F', True), (6, 'F', False)), 12),
    ('turn', ((0, 'B', True), (2, 'B', False)), 8),
    ('jump', ((0, 'up', True), (2, 'up', False)), 20),
    ('climb', ((0, 'shift', True), (0, 'up', True)), 40),
    ('down', ((0, 'shift', True), (0, 'down', True)), 40),
    ('crouch', ((0, 'down', True),), 8),
    ('leap', ((0, 'F', True), (6, 'up', True), (8, 'up', False)), 26),
)


def scenery_file(number):
    return SCENERY.get(number) or scenery_resource(number)


def union(first, second):
    if first is None:
        return second
    return (min(first[0], second[0]), min(first[1], second[1]),
            max(first[2], second[2]), max(first[3], second[3]))


def cell_rect(row, column):
    return (max(0, row * 120 + 5), column * 51, (row + 1) * 120 + 5, (column + 1) * 51)


def section(first, second):
    return (max(first[0], second[0]), max(first[1], second[1]),
            min(first[2], second[2]), min(first[3], second[3]))


class NativeCover:
    """The original's cover over one Prince frame of one level."""

    def __init__(self, source, number):
        directory = Path(source) / 'resource_forks'
        self.executable = (directory / 'Prince of Persia 2.bin').read_bytes()
        self.prince = (directory / 'Prince.rsrc.bin').read_bytes()
        self.scenery = (directory / f'{scenery_file(number)}.bin').read_bytes()
        self.base_level = self.level = probe_level(number, self.prince)
        self.character = NativeCharacter(self.executable, self.level)
        self.machine = CavernRecovery(self.executable, self.scenery, self.prince)
        self.resources = parse_resource_fork(self.scenery)
        self.palette = {index: (index, index, index, 255) for index in range(256)}
        self.shapes = {}

    def close(self):
        self.machine.close()

    def live(self, tiles, foreground):
        """Draw from the level with the port's current cells: `tiles`
        {(room, cell): (kind, foreground)} (loose floors fallen or moving)
        and `foreground` {(room, cell): word} (trigger targets), both with
        the port's zero-based rooms (kind word room * 60 + cell * 2,
        foreground word 0x780 + room * 120 + cell * 4, as pop2.terrain)."""
        level = bytearray(self.base_level)
        for (room, cell), (kind, word) in tiles.items():
            struct.pack_into('>H', level, room * 60 + cell * 2, kind & 0xffff)
            struct.pack_into('>H', level, 0x780 + room * 120 + cell * 4, word & 0xffff)
        for (room, cell), word in foreground.items():
            struct.pack_into('>H', level, 0x780 + room * 120 + cell * 4, word & 0xffff)
        self.level = self.character.level = bytes(level)

    def paint(self, commands, covered):
        for command in commands:
            try:
                sprite = cavern_command_sprite(command, self.resources, self.palette, self.shapes)
            except KeyError:
                continue
            decoded = clipped_sprite(sprite, command)
            if decoded is None:
                continue
            sprite, (x, y) = decoded
            alpha = np.asarray(sprite.getchannel('A')) > 0
            top, left = max(0, y), max(0, x)
            bottom, right = min(SIZE[0], y + sprite.height), min(SIZE[1], x + sprite.width)
            if top < bottom and left < right:
                covered[top:bottom, left:right] |= alpha[top - y:bottom - y, left - x:right - x]

    def redraw(self, room, words, **options):
        return recover_room(self.executable, self.scenery, self.level, room, self.prince,
                            _machine=self.machine, a5_words=words, **options)

    def frame(self, room, fields, anchor, bottom, size):
        """The setup's result and the cover {kind: mask} over this frame."""
        setup = self.character.frame(fields, anchor, bottom, size)
        rect = setup['rect']
        words = {}
        for name, displacement in CHARACTER.items():
            words[displacement] = words[displacement - KID_COPY] = fields.get(name, 0)
        words[-0x5022] = words[-0x5022 - KID_COPY] = fields.get('sequence_mode', 0)
        for index, value in enumerate(rect):
            words[RECT + 2 * index] = words[RECT - KID_COPY + 2 * index] = value
        covers = {kind: np.zeros(SIZE, bool) for kind in ('floor', 'half', 'front', 'top', 'peel')}
        floors, halves, fronts, tops = {}, set(), {}, {}
        for kind, cell, marked in setup['marks']:
            # GetCellNumber 4:29d8-2a10 numbers the border row's cells
            # -(column + 1).
            row, column = (-1, -cell - 1) if cell < 0 else divmod(cell, 10)
            if row == -1:
                tops[column] = union(tops.get(column), marked)
            elif kind == 'floor':
                floors[row, column] = union(floors.get((row, column)), marked)
            elif kind == 'half':
                halves.add((row, column))
            else:
                fronts[row, column] = union(fronts.get((row, column)), marked)
        if not setup['viewable']:
            return setup, covers
        for (row, column), marked in floors.items():
            result = self.redraw(room, words, floor_redraw=True, only={(row, column, 2)},
                                 clips={(row, column, 2): marked})
            self.paint(result['commands'], covers['floor'])
        for row, column in halves - set(floors):
            result = self.redraw(room, words, climb_action=fields['action'], only={(row, column, 2)},
                                 clips={(row, column, 2): cell_rect(row, column)})
            self.paint(result['commands'], covers['half'])
        kid = (fields['action'], fields['row'], fields['column'], fields['mode'])
        for (row, column), marked in fronts.items():
            result = self.redraw(room, words, cell_redraw=True, only={(row, column, 1)},
                                 clips={(row, column, 1): marked},
                                 gate_peel={'kid': kid, 'objects': [(2, 0, rect)]})
            self.paint(result['commands'], covers['front'])
            self.paint(result['peel'], covers['peel'])
        for column, marked in tops.items():
            strip = section((0, column * 51, 5, (column + 1) * 51), marked)
            if strip[0] >= strip[2] or strip[1] >= strip[3]:
                continue
            slot = (-1, column, 1)
            result = self.redraw(room, words, cell_redraw=True, only={slot},
                                 clips={slot: strip})
            self.paint(result['commands'], covers['top'])
        return setup, covers


class PortFrames:
    """The hidden game with the Prince drawn in magenta."""

    def __init__(self, number):
        from tools.audit_temple_routes import Harness

        self.harness = harness = Harness(number, draw=True)
        scene = self.scene = harness.scene
        scene.cave_ambience_enabled = False
        scene.opening = None
        original = scene.player_sprite

        def magenta(action=None, ctbl=None):
            sprite = original(action, ctbl=ctbl)
            if sprite is None:
                return None
            painted = Image.new('RGBA', sprite.size, (*MAGENTA, 255))
            painted.putalpha(sprite.getchannel('A').point(lambda level: 255 if level else 0))
            return painted

        scene.player_sprite = magenta
        scene.sword_sprite = lambda: None
        # The hit star (an object of its own, drawn over the characters).
        scene.hit_art.draw = lambda *args, **kwargs: None
        scene.present_viewport = lambda: None

    def close(self):
        self.harness.close()

    def press(self, key, pressed, facing):
        from tools.audit_temple_routes import press

        if key in ('F', 'B'):
            forward = 'R' if facing else 'L'
            key = forward if key == 'F' else ('L' if forward == 'R' else 'R')
        press(self.harness, key, pressed)

    def visible(self):
        """(state, row, bounds, drawn alpha, shown) or None for a frame the
        probe does not compare."""
        scene = self.scene
        from pop2.scene_prototype import environment_for

        state = scene.sequence_state
        environment = environment_for(scene)
        _drawn_state, height = environment.drawn_player(state)
        if height is not None:
            return None
        sprite = scene.player_sprite(state.action)
        if sprite is None:
            return None
        bounds = scene.player_bounds()
        scene.render()
        frame = np.asarray(scene.screenshot_viewport.convert('RGB'))[:SIZE[0], 1:1 + SIZE[1]]
        if not frame.any():
            return None  # A black screen (a fade), nothing drawn to compare.
        shown = np.all(frame == MAGENTA, axis=2)
        if state.facing:
            sprite = ImageOps.mirror(sprite)
        drawn = np.zeros(SIZE, bool)
        alpha = np.asarray(sprite.getchannel('A')) > 0
        left, top = bounds[0], bounds[1]
        t, lft = max(0, top), max(0, left)
        b, r = min(SIZE[0], top + alpha.shape[0]), min(SIZE[1], left + alpha.shape[1])
        if t < b and lft < r:
            drawn[t:b, lft:r] = alpha[t - top:b - top, lft - left:r - left]
        return state, scene.terrain_motion.row, bounds, drawn, shown


def native_fields(scene, state, row, bounds):
    record = scene.frames[state.action]
    # GetCharCol 4:3ad6 (pop2.opponent_generation.character_column), as the scene.
    column = character_column(floor_contact_x(state.target_x, state.facing, record))
    return {'facing': 0 if state.facing else -1, 'x': state.target_x + 207, 'y': bounds[3],
            'type': 0, 'action': state.action, 'column': column, 'row': row,
            'mode': state.animation_state, 'room': scene.room_id + 1,
            'sequence': state.sequence_id, 'selected': state.source_sequence_id,
            'sequence_mode': state.sequence_mode}


def start_positions(terrain, room, per_row=3):
    for row in range(3):
        columns = [column for column in range(10) if terrain.tile(room, column, row).kind == 1]
        if not columns:
            continue
        picks = sorted({columns[0], columns[len(columns) // 2], columns[-1]})[:per_row]
        for column in picks:
            yield row, column * 51 + 14


def run_level(source, number, rooms=None, macros=MACROS, examples=None):
    native = NativeCover(source, number)
    port = PortFrames(number)
    scene = port.scene
    totals, cases = Counter(), {}
    digest = hashlib.sha256()
    seen = set()
    try:
        terrain = scene.level_map
        for room in range(32):
            if rooms is not None and room not in rooms:
                continue
            if number == 14 and room in (8, 9):
                continue  # Views of rooms 3 and 8 (cavern_room), not their own scenery.
            if not any(terrain.tile(room, column, row).room == room for column in range(10) for row in range(3)):
                continue
            for row, x in start_positions(terrain, room):
                for facing in (0, 1):
                    for name, presses, ticks in macros:
                        if scene.game.level.number != number:
                            # A level's end (the desert's cave) loads the next one.
                            scene.load_level(number)
                        try:
                            scene.jump_to_room(room, row=row, x=x, facing=facing, redraw=False)
                        except ValueError:
                            continue
                        for tick in range(ticks + 1):
                            if (scene.room_id != room or not scene.combat.player.alive
                                    or scene.game.level.number != number):
                                break
                            state = scene.sequence_state
                            key = (room, scene.terrain_motion.row, state.action, state.animation_state,
                                   state.source_sequence_id, state.sequence_id, state.facing, state.target_x,
                                   state.current_y, scene.player_x)
                            if key not in seen:
                                seen.add(key)
                                compare(native, port, totals, cases, digest, number, room, name, examples)
                            for at, pressed_key, pressed in presses:
                                if at == tick:
                                    port.press(pressed_key, pressed, facing)
                            port.harness.tick()
                        scene.clear_keys(None)
    finally:
        port.close()
        native.close()
    return dict(totals=dict(totals), cases=cases, native_sha256=digest.hexdigest())


def approved_exception(state, bounds):
    """The approved port exception this frame shows, or None: the climb's
    `ledge_surface_clip` (SEQS 10/68, poses 135-144: the whole slab hides
    the body below the support line instead of ComputeHalfRect's strip),
    the first temple/ruins walk-off frame's rear tip along the floor
    diagonal (`draw_walkoff_tip`), the temple running jump's first loose
    floor impact (`loose_contact_floor_cell`) and the crush presentation
    (SEQS 118, poses 264-266)."""
    from pop2.render_opening import ledge_surface_clip

    if ledge_surface_clip(state, bounds) is not None:
        return 'ledge_surface'
    sequence, action, mode = state.source_sequence_id, state.action, state.animation_state
    if (state.level_kind in (2, 4) and sequence == 7 and action == 102 and mode == 3
            and state.facing == 0):
        return 'walkoff_tip'
    if state.level_kind == 2 and sequence == 21 and action == 106 and mode == 4:
        return 'loose_contact'
    if sequence == 118 and 264 <= action <= 266:
        return 'crush'
    return None


def moving_object(scene, bounds):
    """'object' when a temple sliding rock, a falling slab, a flying dart or
    a spike's front piece overlaps the Prince: objects drawn over the
    characters that the probe does not model; 'exit' or 'item' for the
    exit's frame or a flask over him."""
    caverns = getattr(scene.game, 'caverns', None)
    if caverns is None:
        return None
    left, top, right, bottom = bounds
    rects = [(clip[1], clip[0], clip[3], clip[2])
             for _kind, _x, _y, _phase, clip in caverns.rocks.objects(scene.level_map, scene.room_id + 1)]
    # Falling slabs of this room and of the rooms above and below, placed as
    # draw_cavern_falling places them.
    terrain = scene.level_map
    shifts = {scene.room_id: 0, terrain.neighbor(scene.room_id, 'up'): -364,
              terrain.neighbor(scene.room_id, 'down'): 364}
    shifts.pop(None, None)
    for floor in caverns.loose.falling:
        if floor.room in shifts:
            y = floor.y + shifts[floor.room]
            width, height = floor.size
            rects.append((floor.x, y - height - 20, floor.x + width + 4, y + 1))
    # A flying dart (SHAP 3594, draw_cavern_darts) and the spikes' front
    # pieces (draw_cavern_spikes) are objects drawn over the characters too.
    rects.extend((dart.x, dart.y - 20, dart.x + 40, dart.y + 1)
                 for dart in caverns.plates.darts.projectiles
                 if dart.room == scene.room_id and dart.dy not in (-3, -1))
    number = scene.game.level.number
    from pop2.caverns import room_assets

    _program, resources, palette, shapes = room_assets(number, scene.room_id)
    for command in caverns.spikes.drawing_commands(scene.level_map, scene.room_id, True,
                                                   temple=number >= 10):
        sprite = cavern_command_sprite(command, resources, palette, shapes)
        rects.append((command[2], command[3] - sprite.height + 1, command[2] + sprite.width,
                      command[3] + 1))
    for x0, y0, x1, y1 in rects:
        if x0 <= right and left < x1 and y0 <= bottom and top < y1:
            return 'object'
    # The exit's irregular frame over a Prince on the stairs (SEQS 70, poses
    # 217-226): the cavern's 8:1cfe-1d48 and the ruins' 7:27c0 draw it
    # through the exit's own object, which the probe does not run.
    state = scene.sequence_state
    art = getattr(scene, 'room_cache', {}).get(scene.room_id)
    # Level 8's throne bars: DrawRuinGateMovable 7:2b22-2b4a -> 7:383a draws
    # CUST record 6 (SHAP 4206) in the front pass, another object drawer.
    if scene.game.level.number == 8 and scene.room_id == 8 and getattr(art, 'gate_occlusion', None):
        for cover, (x, y) in art.gate_occlusion.values():
            if x <= right and left < x + cover.width and y <= bottom and top < y + cover.height:
                return 'object'
    # The arrival horse statues (level 10's native room 22, level 14's room
    # 1): DrawHorse 3:23f0-2414 adds them to the front pass through
    # 3:4572/4608, which recover_room does not run.
    from pop2.caverns import ARRIVAL_HORSE_POSITIONS

    if ((scene.game.level.number, scene.room_id) in ARRIVAL_HORSE_POSITIONS
            and getattr(art, 'custom_occlusion', None)):
        box = art.custom_occlusion.getbbox()
        if box is not None and box[0] <= right and left < box[2] and box[1] <= bottom and top < box[3]:
            return 'statue'
    if getattr(art, 'exit_foreground', None) and 217 <= state.action <= 226:
        for sprite, (x, y) in art.exit_foreground:
            if x <= right and left < x + sprite.width and y <= bottom and top < y + sprite.height:
                return 'exit'
    # Flasks: both sides draw the body and bubbles over him (the port's
    # front layer, the original's front pass of the flask's dirty cell), but
    # the probe's painter does not mirror the second half's bubbles
    # (DrawFlask 3:46fc, phases 14-23), so they are counted apart.
    from pop2.caverns import cavern_assets, cavern_flask_instances

    program = cavern_assets(number)[0]
    for command, _tile in cavern_flask_instances(program, scene.room_id, scene.level_map):
        x, y = command[2], command[3]
        if x - 4 <= right and left < x + 24 and y - 60 <= bottom and top < y + 1:
            return 'item'
    return None


def compare(native, port, totals, cases, digest, number, room, macro, examples):
    observed = port.visible()
    if observed is None:
        totals['skipped'] += 1
        return
    state, row, bounds, drawn, shown = observed
    fields = native_fields(port.scene, state, row, bounds)
    caverns = getattr(port.scene.game, 'caverns', None)
    tiles = {}
    if caverns is not None:
        # The flasks as the port has them now: drunk ones gone (kind
        # changed) and each one's bubble phase (Potions.phases), which
        # DrawFlask 3:46fc draws from the foreground word's low bits.
        for flask_room, cell in set(caverns.potions.tiles) | set(caverns.potions.phases):
            tile = port.scene.level_map.tile(flask_room, cell % 10, cell // 10)
            tiles[flask_room, cell] = (tile.kind, tile.foreground)
        tiles.update(caverns.loose.tiles)
    foreground = {}
    if caverns is not None:
        foreground.update(caverns.plates.foreground)
        # The scythes' blade phases (the foreground's low byte, as the port
        # draws them).
        for scythe_room, cell in caverns.scythes.foreground:
            foreground[scythe_room, cell] = port.scene.level_map.tile(
                scythe_room, cell % 10, cell // 10).foreground
    native.live(tiles, foreground)
    anchor = bounds[2] + 1 if state.facing else bounds[0]
    size = (bounds[3] - bounds[1] + 1, bounds[2] - bounds[0] + 1)
    setup, covers = native.frame(room, fields, anchor, bounds[3], size)
    expected_rect = section((bounds[1], bounds[0], bounds[3] + 1, bounds[2] + 1), (0, 0, *SIZE))
    if expected_rect[0] >= expected_rect[2] or expected_rect[1] >= expected_rect[3]:
        expected_rect = (0, 0, 0, 0)  # SectRect empties a rectangle off the screen.
    if setup['rect'] != expected_rect:
        totals['rect_mismatch'] += 1
    top, left, bottom, right = setup['clip']
    clip = np.zeros(SIZE, bool)
    clip[max(0, top):max(0, bottom), max(0, left):max(0, right)] = True
    if not setup['viewable']:
        clip[:] = False
    covered = np.zeros(SIZE, bool)
    for kind, mask in covers.items():
        covered |= mask
    expected = drawn & clip & ~covered
    totals['frames'] += 1
    totals['drawn_pixels'] += int(drawn.sum())
    totals['native_shown_pixels'] += int(expected.sum())
    for kind in ('floor', 'half'):
        if any(mark[0] == kind for mark in setup['marks']):
            totals[f'{kind}_frames'] += 1
    digest.update(struct.pack('>4h', number, room, state.action, state.animation_state))
    digest.update(np.packbits(expected).tobytes())
    ceiling = port.scene.room_cache[port.scene.room_id].short_jump_ceiling(row, state)
    if ceiling is not None:
        cover, top = ceiling
        visible_strip = expected[top:top + cover.height]
        approved = visible_strip & (np.asarray(cover) > 0)
        hidden = int((approved & ~shown[top:top + cover.height]).sum())
        if hidden:
            totals['jump_ceiling_frames'] += 1
            totals['jump_ceiling_extra'] += hidden
        visible_strip &= ~approved
    missing, extra = int((shown & ~expected).sum()), int((expected & ~shown).sum())
    totals['missing_pixels'] += missing
    totals['extra_pixels'] += extra
    exception = approved_exception(state, bounds) or moving_object(port.scene, bounds)
    if exception and (missing or extra):
        # Counted apart: the user's approved port exceptions, not failures.
        totals[f'{exception}_frames'] += 1
        totals[f'{exception}_missing'] += missing
        totals[f'{exception}_extra'] += extra
        totals['missing_pixels'] -= missing
        totals['extra_pixels'] -= extra
        return
    if missing or extra:
        totals['different_frames'] += 1
        attribution = {kind: int((mask & drawn & clip & shown).sum()) for kind, mask in covers.items()}
        attribution['clip'] = int((drawn & ~clip & shown).sum())
        case = dict(room=room, macro=macro, row=row, action=state.action, mode=state.animation_state,
                    sequence=state.source_sequence_id, facing=state.facing, bounds=list(bounds),
                    missing=missing, extra=extra, missing_by=attribution,
                    marks=[[kind, cell] for kind, cell, _rect in setup['marks']])
        cases.setdefault(f'{number}:{room}', []).append(case)
        if examples is not None:
            examples.append((number, room, replace(state), bounds, drawn, shown, expected, covers, setup))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--source', type=Path, required=True, help='The original recovery folder')
    parser.add_argument('--level', type=int, action='append', required=True)
    parser.add_argument('--room', type=int, action='append')
    parser.add_argument('--output', type=Path)
    options = parser.parse_args(argv)
    report = {}
    for number in options.level:
        report[number] = run_level(options.source, number, set(options.room) if options.room else None)
        print(number, json.dumps(report[number]['totals']), flush=True)
    if options.output:
        options.output.write_text(json.dumps(dict(levels=report, scope=__doc__), indent=1))


if __name__ == '__main__':
    sys.exit(main())
