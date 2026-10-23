"""Execute original head movement admission with native cells and supplied body bounds."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import read_cell
from tools.probe_level7_sequence_selection import NativeHeadSelection, signed_word, supporting_column


WALL_IDS = frozenset((2, 7, 20, 25, 43))
SPACE_IDS = frozenset((0, 9, 27, 47, 49))


def middle_of_cell(x, tolerance=12):
    value = x - 229
    quotient = abs(value) // 51 * (-1 if value < 0 else 1)
    remainder = value - quotient * 51
    return 25 - tolerance <= remainder <= 25 + tolerance


def gate_blocks(actor, foreground, body_top, body_bottom):
    height = signed_word(body_bottom - body_top)
    height = signed_word(height + (46 if actor == 7 else 33))
    return ((foreground & 255) >> 2) * 2 + 11 < height + 13


def movement_reference(level, state, direction):
    column, row = state['column'], state['row']

    def cell(at_column, at_row):
        tile = read_cell(level, state['room'], at_column, at_row)
        if tile is None:
            raise ValueError('Missing-neighbor cells are outside this reference domain')
        foreground = struct.unpack_from('>H', level, tile[1])[0]
        return tile[0], foreground

    def blocked(tile):
        kind, foreground = tile
        return kind in WALL_IDS or (kind == 4 and gate_blocks(
            state['actor'], foreground, state['body_top'], state['body_bottom']))

    if direction in (0, 1):
        if (direction == 0 and column < -1) or (direction == 1 and column > 10):
            return False
        floor = row * 120 + 73
        if ((state['selected'] == 144 and state['y'] > floor)
                or (state['selected'] == 143 and state['y'] < floor)):
            return False
        ahead = signed_word(state['x'] + (26 if state['facing'] == 0 else -26))
        other_column, _ = supporting_column(ahead, 0, bytes(10))
        if other_column != column and blocked(cell(column + (-1 if direction == 0 else 1), row)):
            return False
        if direction == 1:
            kind, foreground = cell(column, row)
            if kind == 4 and gate_blocks(state['actor'], foreground, state['body_top'], state['body_bottom']):
                return False
        return True
    if direction == 2:
        return row != 2 and middle_of_cell(state['x']) and cell(column, row)[0] in SPACE_IDS
    if direction == 3:
        return row != 0 and middle_of_cell(state['x']) and cell(column, row - 1)[0] in SPACE_IDS
    return False


class NativeHeadMovement(NativeHeadSelection):
    RANGES = {
        3: ((0x4eb2, 0x4ee4), (0x4ef2, 0x4f24)),
        4: NativeHeadSelection.RANGES[4] + (
            (0x26e2, 0x28a8), (0x28b6, 0x29c0), (0x322a, 0x3262), (0x5b0e, 0x5ba8)),
        5: ((0x0004, 0x0066), (0x48b0, 0x48dc)),
        6: NativeHeadSelection.RANGES[6],
        7: ((0x0936, 0x0b02), (0x170a, 0x17ae)),
        19: ((0x4bd0, 0x4c4c),),
    }
    FIELDS = dict(actor=-0x504e, facing=-0x5054, x=-0x5052, y=-0x5050,
                  room=-0x5040, column=-0x504a, row=-0x5048, selected=-0x502e,
                  body_top=-0x502c, body_bottom=-0x5028)

    def configure(self, level, state):
        self.reset(level)
        self.cpu.mem_write(self.A5 - 0x5056, bytes(62))
        for name, value in state.items():
            self.put_word(self.FIELDS[name], value)


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    program_bytes = (directory / 'Prince of Persia 2.bin').read_bytes()
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    head = parse_resource_fork((directory / 'Head.rsrc.bin').read_bytes())
    level = prince['LEVL'][2006]['data']
    machine = NativeHeadMovement(parse_resource_fork(program_bytes), head, prince['SEQS'])
    counts, admitted = Counter(), Counter()
    digest = hashlib.sha256()

    def check(state, direction, label):
        machine.configure(level, state)
        before = bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62))
        native = machine.call(7, 0x0936, (direction,))
        expected = movement_reference(level, state, direction)
        if (native != int(expected) or machine.level_bytes(len(level)) != level
                or bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)) != before
                or machine.requests or machine.services):
            raise AssertionError(dict(state=state, direction=direction, native=native, expected=expected))
        counts[label] += 1
        admitted[str(direction)] += native
        digest.update(bytes((native,)))

    for room, row, column, actor, facing, offset, direction in product(
            range(1, 33), range(3), range(1, 9), (7, 8), (-1, 0), (-13, 0, 13), range(4)):
        state = dict(room=room, row=row, column=column, actor=actor, facing=facing,
                     x=254 + column * 51 + offset, y=row * 120 + 73,
                     selected=130, body_top=18, body_bottom=50)
        check(state, direction, 'actual_cells')
    for room, row, column, actor, facing, selected, delta, direction in product(
            (1, 3, 7, 20, 28, 32), range(3), (1, 4, 8), (7, 8), (-1, 0),
            (143, 144), (-1, 0, 1), (0, 1)):
        state = dict(room=room, row=row, column=column, actor=actor, facing=facing,
                     x=254 + column * 51, y=row * 120 + 73 + delta,
                     selected=selected, body_top=18, body_bottom=50)
        check(state, direction, 'vertical_overshoot')
    for actor, foreground, height in product(
            (7, 8), tuple(range(0, 256, 4)) + (0x8100, 0x80fc), (0, 32, 60)):
        state = dict(room=1, row=1, column=4, actor=actor, facing=-1,
                     x=458, y=193, selected=130, body_top=18, body_bottom=18 + height)
        machine.configure(level, state)
        machine.put_word(-0x34ae, foreground)
        native = machine.call(4, 0x5b0e)
        if native != int(gate_blocks(actor, foreground, 18, 18 + height)):
            raise AssertionError(dict(actor=actor, foreground=foreground, height=height))
        counts['gate_threshold'] += 1
        digest.update(bytes((native,)))
    for x, tolerance in product(range(-100, 1001), (0, 12, 25)):
        machine.reset(level)
        native = machine.call(7, 0x1768, (x, tolerance))
        if native != int(middle_of_cell(x, tolerance)):
            raise AssertionError(dict(x=x, tolerance=tolerance, native=native))
        counts['middle_window'] += 1
        digest.update(bytes((native,)))
    for column, direction in ((4, -1), (4, 4), (4, 100), (-2, 0), (11, 1)):
        state = dict(room=1, row=1, column=column, actor=7, facing=-1,
                     x=458, y=193, selected=130, body_top=18, body_bottom=50)
        check(state, direction, 'rejection_controls')
    return dict(
        level=7, cases=dict(counts), admitted=dict(admitted), mismatches=0,
        outputs_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(program_bytes).hexdigest(),
        supplied_services=[],
        scope=('Full movement-admission helper 7:0936, original overshoot/middle checks, '
               'ReadCell/CalcBlue, IsWall/IsSpace, gate predicate and signed remainder helper. '
               'Actual level-seven cells, supplied working geometry/body bounds; in-room '
               'columns 1..8 and rows 0..2. Separate gate foreground/height controls. '
               'Direct signed middle-window and early-rejection controls. '
               'No drawn-bound computation, missing-neighbor fallback, motion execution, '
               'RNG/idle selection, full collision, state reachability or AI cadence claim.'),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
