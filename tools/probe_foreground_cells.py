"""Run the original front drawers per dirty cell against the port's actor cell masks.

Characters are drawn once, after every dirty cell (DrawObjs 3:3326), and
the foreground table follows them (DumpTable 0, 3, 1 at 3:3362-3378). Each
character marks the cells its rectangle covers (MarkBufsForRect 5:19f8 with
MarkFRedraw 5:1990, from SetupSword/SetupOpponent 3:0d18-0f62 and 4:26b8),
and RedrawCell 3:1d3a/1f04-1f30 then runs DrawForeImg 3:2598 for each one,
clipped to that cell (GetCells 5:0aaa -> ComputeClipRect 5:0162: row*120+5,
column*51, 120 by 51) and the marked rectangle. So the scenery in front of a
character is, cell by cell, what that cell's own redraw draws inside it.

The port keeps the clean-cut export's front commands under the cell that
drew them (`CavernRoom.actor_cell_occlusion`, clipped to that cell) and unites the
cells the character's rectangle covers. Here every room of the imported
levels 3-14 is drawn by the original drawers again, one cell at a time in
dirty-cell mode (`recover_room(cell_redraw=True)`: A5-4832 clear, the cell
clip), and compared, per cell, with the port's masks:

- `missing`: pixels the cell's own redraw draws that its port mask lacks.
  With only that cell marked, the port shows the character there and the
  original hides him.
- `bleed`: port pixels inside a cell that the cell's redraw does not draw,
  by the neighbouring cell whose mask reaches into it. The original never
  repaints them over a character (the port clips each cell's mask to the
  cell, `clip_cell_masks`).
- `own_extra`: port pixels in a cell's own mask that its redraw does not draw.

Row -1 is the border row, the upper room's last row in the top five
pixels: MarkTop 5:16f2 marks its cells and RedrawTopFast 3:1f4e redraws
them with the same front pass (recover_room's row -1). A customized room
(any foreground word with 0xc000, IsCustomizedRoom 3:1310) has no border
row (3:32c8-32cc), and its row 0's clip reaches the top (5:01ba-01c4).

Both sides leave out what the port draws elsewhere: items and flames
(libraries 0, 1, 5), level 3-5 torch frames and level 14's moving fangs
(the animated room), and CUST front records (`custom_occlusion`, repeated
for every dirty cell). Alpha comes from the port's own SHAP decoder on both
sides, so this checks which pieces are drawn where, not the decoder. Not
covered: DrawFloorBuf/DrawHalf (QuickFloor), CheckGateInFore's actor test
(`tools/probe_gate_peel.py`) and the rectangle marking itself.

`--variants` and `--pressure` probe rooms in motion: each slot unit's
other states (loose floors, crevices, scythes, planks, the entry door) or
each trigger target's other phases (gates, exits, plates, bars, darts),
one at a time with the rest at rest, the native level words changed to
match. Two units moving at once and on-screen crevice reveals are not
covered.
"""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

import numpy as np

from pop2.caverns import (FINAL_MOVING_SHAPES, SCENERY_LEVELS, cavern_command_sprite, cavern_room,
                          clipped_sprite, custom_foreground_records, room_assets, scenery_available,
                          scenery_resource)
from pop2.level_data import LevelDefinition
from pop2.mac_resources import parse_resource_fork
from tools.extract_caverns import CavernRecovery, customized_room, dirty_cell_top, hide_crevices, recover_room

SIZE = (365, 510)
LEVELS = tuple(number for numbers in SCENERY_LEVELS.values() for number in numbers)


def cell_clip(column, row, customized=False):
    return dirty_cell_top(row, customized), column * 51, (row + 1) * 120 + 5, (column + 1) * 51


def animated_scenery(number, room, command):
    """The commands an animated `cavern_room` draws with its scenery."""
    library = command[7] if len(command) >= 8 else 4
    if library in (0, 1, 5):
        return False
    if number in SCENERY_LEVELS[3] and library == 4 and 3581 <= command[1] <= 3589:
        return False
    return not (number in SCENERY_LEVELS[6] and library == 4
                and command[1] in FINAL_MOVING_SHAPES.get(room, ()))


def native_cell(commands, art, custom, number, room):
    covered = np.zeros(SIZE, bool)
    for command in commands:
        if (command[0] != 'front' or not animated_scenery(number, room, command)
                or tuple(command[1:5]) in custom):
            continue
        decoded = clipped_sprite(cavern_command_sprite(command, *art), command)
        if decoded is None:
            continue
        sprite, (x, y) = decoded
        alpha = np.asarray(sprite.getchannel('A')) > 0
        top, left = max(0, y), max(0, x)
        bottom, right = min(SIZE[0], y + sprite.height), min(SIZE[1], x + sprite.width)
        if top < bottom and left < right:
            covered[top:bottom, left:right] |= alpha[top - y:bottom - y, left - x:right - x]
    return covered


def port_cells(room_art):
    cells = {}
    for cell, (mask, (x, y)) in (room_art.actor_cell_occlusion or {}).items():
        covered = np.zeros(SIZE, bool)
        alpha = np.asarray(mask) > 0
        covered[y:y + alpha.shape[0], x:x + alpha.shape[1]] = alpha[:SIZE[0] - y, :SIZE[1] - x]
        cells[cell] = covered
    return cells


def compare_room(machine, sources, level, number, room, room_art, totals, digest, cells=None):
    """The cases where `room_art`'s cell masks differ from each dirty cell's redraw."""
    executable, scenery, prince = sources
    _program, resources, palette, shapes = room_assets(number, room)
    art = (resources, palette, shapes)
    custom = custom_foreground_records(resources, room)
    port = port_cells(room_art)
    extra_cover = (np.asarray(room_art.custom_occlusion) > 0
                   if room_art.custom_occlusion is not None else np.zeros(SIZE, bool))
    customized = customized_room(level, room)
    cases = []
    for row, column in product(range(-1, 3), range(10)):
        if cells is not None and (column, row) not in cells:
            continue
        if row == -1 and customized:
            # 3:32c8-32cc: no border redraw (RedrawTopFast 3:1f4e).
            native = np.zeros(SIZE, bool)
        else:
            commands = recover_room(executable, scenery, level, room, prince, _machine=machine,
                                    cell_redraw=True, only={(row, column, 1)})['commands']
            native = native_cell(commands, art, custom, number, room)
        top, left, bottom, right = cell_clip(column, row, customized)
        outside = native.copy()
        outside[top:bottom, left:right] = False
        if outside.any():
            raise AssertionError(f'Level {number} room {room} cell {column},{row} drew outside its clip')
        inside = native[top:bottom, left:right]
        own = port.get((column, row), np.zeros(SIZE, bool))[top:bottom, left:right]
        missing = int((inside & ~own).sum())
        bleed = {}
        for (other_column, other_row), covered in port.items():
            if (other_column, other_row) == (column, row):
                continue
            part = covered[top:bottom, left:right] & ~inside & ~extra_cover[top:bottom, left:right]
            if part.any():
                bleed[f'{other_column},{other_row}'] = int(part.sum())
        own_extra = int((own & ~inside & ~extra_cover[top:bottom, left:right]).sum())
        totals['cells'] += 1
        totals['native_pixels'] += int(inside.sum())
        totals['missing_pixels'] += missing
        totals['bleed_pixels'] += sum(bleed.values())
        totals['own_extra_pixels'] += own_extra
        if missing or bleed or own_extra:
            cases.append(dict(cell=[column, row], missing=missing, bleed=bleed, own_extra=own_extra))
        digest.update(struct.pack('>4h', number, room, column, row))
        digest.update(np.packbits(inside).tobytes())
    return cases


def probe_level(number, prince):
    definition = LevelDefinition.read(parse_resource_fork(prince), number)
    return hide_crevices(definition.data) if definition.kind == 4 else definition.data


def probed_rooms(number, program, rooms):
    for room in sorted(int(key) for key in program['rooms']):
        if rooms is not None and (number, room) not in rooms:
            continue
        if number in SCENERY_LEVELS[6] and room in (8, 9):
            continue  # Views of rooms 3 and 8 (cavern_room), not their own scenery.
        yield room


def run_probe(source, levels=LEVELS, rooms=None):
    directory = Path(source) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    prince = (directory / 'Prince.rsrc.bin').read_bytes()
    digest, totals = hashlib.sha256(), Counter()
    results = {}
    for number in levels:
        if not scenery_available(number):
            continue
        level = probe_level(number, prince)
        scenery = (directory / f'{scenery_resource(number)}.bin').read_bytes()
        program = room_assets(number, 0)[0]
        with CavernRecovery(executable, scenery, prince) as machine:
            for room in probed_rooms(number, program, rooms):
                room_art = cavern_room(room, animated=True, level_number=number)
                cases = compare_room(machine, (executable, scenery, prince), level, number, room,
                                     room_art, totals, digest)
                if cases:
                    results[f'{number}:{room}'] = cases
    return dict(totals=dict(totals), cases=results, native_sha256=digest.hexdigest(),
                executable_sha256=hashlib.sha256(executable).hexdigest(), scope=__doc__)


def variant_arguments(record, states):
    """`cavern_room` keywords for slot unit states (loose cells, scythes, planks, door frame)."""
    units, scythes, planks = len(record['units']), len(record['scythes']), len(record['planks'])
    key = ['0'] * len(record['cells'])
    for group, state in zip(record['units'], states[:units]):
        for index in group:
            key[index] = str(state)
    arguments = {'loose_key': ''.join(key) if any(states[:units]) else ''}
    if scythes:
        arguments['scythe_patch'] = ('slots', tuple(states[units:units + scythes]))
    plank_states = states[units + scythes:units + scythes + planks]
    arguments['bridge_fallen'] = frozenset(cell % 10 for (_room, cell), state
                                           in zip(record['planks'], plank_states) if state == 3)
    arguments['bridge_wobble'] = frozenset((cell % 10, state) for (_room, cell), state
                                           in zip(record['planks'], plank_states) if state in (1, 2))
    if record['door']:
        arguments['entry_frame'] = states[-1]
    return arguments


def pair_states(counts):
    """Two units moving at once: for every pair, each unit's first and last
    moving state, the other units at rest."""
    for first in range(len(counts)):
        for second in range(first + 1, len(counts)):
            for a in sorted({1, counts[first] - 1}):
                for b in sorted({1, counts[second] - 1}):
                    if 0 < a < counts[first] and 0 < b < counts[second]:
                        states = [0] * len(counts)
                        states[first], states[second] = a, b
                        yield f'{first}={a},{second}={b}', states


def run_variant_probe(source, levels=LEVELS, rooms=None, units=None, pairs=False, revealed=False):
    """Each slot unit's other states, one at a time, the other units at rest
    (or, with `pairs`, two units at once: `pair_states`). With `revealed`,
    only crevice runs, revealed while the room was on screen (`redrawn`):
    the covered drawing plus their cells' redraw."""
    from functools import partial

    from tools.extract_slots import room_renderer, slot_context

    directory = Path(source) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    prince = (directory / 'Prince.rsrc.bin').read_bytes()
    digest, totals = hashlib.sha256(), Counter()
    results = {}
    for number in levels:
        if not scenery_available(number):
            continue
        level = probe_level(number, prince)
        scenery = (directory / f'{scenery_resource(number)}.bin').read_bytes()
        program = room_assets(number, 0)[0]
        with CavernRecovery(executable, scenery, prince) as machine:
            context = slot_context(executable, scenery, prince, level, program)
            recover = partial(recover_room, _machine=machine)
            for room in probed_rooms(number, program, rooms):
                prepared = room_renderer(context, room, recover)
                if prepared is None:
                    continue
                record, render, counts, _unit_cells = prepared
                exported = program.get('loose_floors', {}).get('rooms', {}).get(str(room), {})
                if exported.get('cells') != record['cells']:
                    raise AssertionError(f'Level {number} room {room}: the export has other slot cells')
                if revealed:
                    cases_of = ((f'{unit}={state}r', [0] * unit + [state] + [0] * (len(counts) - unit - 1))
                                for unit in record.get('crevices', ()) for state in range(1, counts[unit]))
                elif pairs:
                    cases_of = pair_states(counts)
                else:
                    cases_of = ((f'{unit}={state}', [0] * unit + [state] + [0] * (len(counts) - unit - 1))
                                for unit, count in enumerate(counts)
                                if units is None or unit in units for state in range(1, count))
                for label, states in cases_of:
                    arguments = variant_arguments(record, states)
                    if revealed:
                        unit = int(label.split('=')[0])
                        arguments['redrawn'] = frozenset(tuple(record['cells'][index])
                                                         for index in record['units'][unit])
                    room_art = cavern_room(room, animated=True, level_number=number, **arguments)
                    totals['states'] += 1
                    cases = compare_room(machine, (executable, scenery, prince),
                                         render.scene_level(tuple(states)), number, room,
                                         room_art, totals, digest)
                    if cases:
                        results[f'{number}:{room}:{label}'] = cases
    return dict(totals=dict(totals), cases=results, native_sha256=digest.hexdigest(),
                executable_sha256=hashlib.sha256(executable).hexdigest(), scope=__doc__)


def pressure_phase(kind, foreground):
    """The port's drawing phase of a trigger target (cavern_pressure_signature)."""
    if kind == 4:
        return min(foreground & 255, 184) // 4
    if kind == 17:
        return min(foreground & 255, 79)
    if kind in (27, 33):
        return foreground & 7
    return int(bool(foreground & 0x2000))


def pressure_states(record):
    """Foreground words of one trigger target's other phases: a sample of a
    gate's heights and an exit's openings, every bar and dart phase, a plate
    pressed or released."""
    foreground, kind = record['foreground'], record['kind']
    if kind == 4:
        words = [(foreground & 0xff00) | phase * 4 for phase in (0, 1, 2, 5, 10, 20, 30, 40, 46)]
    elif kind == 17:
        words = [(foreground & 0xff00) | phase for phase in (0, 1, 2, 5, 10, 20, 40, 60, 79)]
    elif kind in (27, 33):
        words = [(foreground & ~7) | phase for phase in range(4 if kind == 27 else 7)]
    else:
        words = [foreground ^ 0x2000]
    rest = pressure_phase(kind, foreground)
    return [word for word in words if pressure_phase(kind, word) != rest]


def run_pressure_probe(source, levels=LEVELS, rooms=None):
    """Each trigger target's other phases (gates, exits, plates, bars, darts), one at a time."""
    directory = Path(source) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    prince = (directory / 'Prince.rsrc.bin').read_bytes()
    digest, totals = hashlib.sha256(), Counter()
    results = {}
    for number in levels:
        if not scenery_available(number):
            continue
        level = probe_level(number, prince)
        scenery = (directory / f'{scenery_resource(number)}.bin').read_bytes()
        program = room_assets(number, 0)[0]
        with CavernRecovery(executable, scenery, prince) as machine:
            for room in probed_rooms(number, program, rooms):
                records = program.get('pressure_plates', {}).get('rooms', {}).get(str(room), ())
                for record in records:
                    offset = 0x780 + record['room'] * 120 + record['cell'] * 4
                    if struct.unpack_from('>H', level, offset)[0] != record['foreground']:
                        raise AssertionError(f"Level {number} room {room}: record {record['room']}:"
                                             f"{record['cell']} has another foreground")
                rest = [pressure_phase(record['kind'], record['foreground']) for record in records]
                for index, record in enumerate(records):
                    for word in pressure_states(record):
                        mutable = bytearray(level)
                        struct.pack_into('>H', mutable, 0x780 + record['room'] * 120 + record['cell'] * 4, word)
                        phase = pressure_phase(record['kind'], word)
                        phases = tuple(phase if other == index else value for other, value in enumerate(rest))
                        room_art = cavern_room(room, animated=True, level_number=number, pressure_key=phases)
                        totals['states'] += 1
                        cases = compare_room(machine, (executable, scenery, prince), bytes(mutable),
                                             number, room, room_art, totals, digest)
                        if cases:
                            results[f"{number}:{room}:{record['room']}:{record['cell']}={phase}"] = cases
    return dict(totals=dict(totals), cases=results, native_sha256=digest.hexdigest(),
                executable_sha256=hashlib.sha256(executable).hexdigest(), scope=__doc__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='The original recovery folder')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--level', type=int, action='append', help='Only these levels (repeatable)')
    parser.add_argument('--variants', action='store_true',
                        help="Each slot unit's other states (loose floors, scythes, planks, door)")
    parser.add_argument('--pairs', action='store_true',
                        help='With --variants: two units at once (first and last state of each)')
    parser.add_argument('--revealed', action='store_true',
                        help='With --variants: crevice runs revealed on screen')
    parser.add_argument('--pressure', action='store_true',
                        help="Each trigger target's other phases (gates, exits, plates, bars, darts)")
    args = parser.parse_args()
    levels = tuple(args.level) if args.level else LEVELS
    if args.variants:
        report = run_variant_probe(args.source, levels, pairs=args.pairs, revealed=args.revealed)
    else:
        report = (run_pressure_probe if args.pressure else run_probe)(args.source, levels)
    text = json.dumps(report, indent=1) + '\n'
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding='utf-8')
    print(json.dumps(report['totals']))
    for key, cases in report['cases'].items():
        print(key, cases)
    if any(report['totals'].get(key) for key in ('missing_pixels', 'bleed_pixels', 'own_extra_pixels')):
        raise SystemExit(1)
