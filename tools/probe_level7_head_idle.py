"""Probe native head idle decisions with real movement checks and supplied random draws."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_frames import head_frame_index
from tools.probe_level7_head_movement import NativeHeadMovement, movement_reference
from tools.probe_level7_head_recovery import head_slots
from tools.probe_level7_sequence_selection import (
    NativeHeadSelection, selection_reference, signed_word, supporting_column,
)


def idle_reference(level, working, frame, tape):
    state = dict(working)
    draws, directions, requests = [], [], []

    def draw(maximum):
        if len(draws) >= len(tape) or not 0 <= tape[len(draws)] <= maximum:
            raise ValueError('Missing or out-of-range supplied random outcome')
        value = tape[len(draws)]
        draws.append((maximum, value))
        return value

    if state['pose'] != 150:
        return state, draws, directions, requests, False
    direction = draw(3)
    if direction == 3:
        selected = state['selected']
        direction = 0 if 131 <= selected <= 133 else 1 if 134 <= selected <= 136 else -1
    elif direction == 2:
        direction += draw(1)
    if direction == -1:
        return state, draws, directions, requests, False
    directions.append(direction)
    allowed = movement_reference(level, state, direction)
    # Admission can change the global division remainder without changing the actor.
    floor = state['row'] * 120 + 73
    overshoot = ((state['selected'] == 144 and state['y'] > floor)
                 or (state['selected'] == 143 and state['y'] < floor))
    if (direction in (0, 1) and not overshoot
            and not (direction == 0 and state['column'] < -1)
            and not (direction == 1 and state['column'] > 10)):
        probe_x = signed_word(state['x'] + (26 if state['facing'] == 0 else -26))
        _, state['remainder'] = supporting_column(probe_x, 0, bytes(10))
    if not allowed:
        return state, draws, directions, requests, False
    if direction == 3:
        requested = 137
    elif direction == 2:
        requested = 138
    else:
        requested = (131 if direction == 0 else 134) + draw(2)
    requests.append(requested)
    state, reload_frame = selection_reference(state, requested, True, frame)
    return state, draws, directions, requests, reload_frame


class NativeHeadIdle(NativeHeadMovement):
    RANGES = {**NativeHeadMovement.RANGES,
              7: NativeHeadMovement.RANGES[7] + ((0x1268, 0x1322),)}
    FIELDS = {**NativeHeadMovement.FIELDS, **NativeHeadSelection.FIELDS}

    def reset(self, level):
        super().reset(level)
        self.tape, self.draws, self.directions = (), [], []

    def dispatch(self, cpu, address, size, user):
        if address == self.address(7, 0x0936):
            stack = cpu.reg_read(self.registers['a7'])
            self.directions.append(struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0])
        if address == self.address(17, 0x6e06):
            stack = cpu.reg_read(self.registers['a7'])
            maximum = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
            if len(self.draws) >= len(self.tape) or not 0 <= self.tape[len(self.draws)] <= maximum:
                raise AssertionError('Unexpected native random request')
            value = self.tape[len(self.draws)]
            self.draws.append((maximum, value))
            cpu.reg_write(self.registers['d0'], value)
            destination = struct.unpack('>I', cpu.mem_read(stack, 4))[0]
            cpu.reg_write(self.registers['a7'], stack + 4)
            cpu.reg_write(self.registers['pc'], destination)
            return
        super().dispatch(cpu, address, size, user)


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    program_bytes = (directory / 'Prince of Persia 2.bin').read_bytes()
    prince_bytes = (directory / 'Prince.rsrc.bin').read_bytes()
    head_bytes = (directory / 'Head.rsrc.bin').read_bytes()
    program, prince, head = (parse_resource_fork(data) for data in
                            (program_bytes, prince_bytes, head_bytes))
    if not set(range(131, 139)) <= set(prince['SEQS']):
        raise AssertionError('Original idle sequences missing')
    level = prince['LEVL'][2006]['data']
    machine = NativeHeadIdle(program, head, prince['SEQS'])
    tapes = [(first, variant) for first in (0, 1, 3) for variant in range(3)] + [(2, 0), (2, 1)]
    counts, sequences, random_bounds = Counter(), Counter(), Counter()
    digest = hashlib.sha256()
    for room, _slot, _offset, actor in head_slots(level):
        for pose, facing, selected, row, delta, tape in product(
                (149, 150, 159), (-1, 0), (130, 131, 133, 134, 136, 137, 138, 139),
                range(3), (-13, 0, 13), tapes):
            initial = dict(room=room, row=row, column=4, actor=actor, facing=facing,
                           x=458 + delta, y=row * 120 + 73, selected=selected,
                           body_top=18, body_bottom=50, pose=pose,
                           sequence=170, cursor=9, remainder=45)
            machine.configure(level, initial)
            machine.tape = tape
            machine.call(4, 0x2a8e)
            before = bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62))
            index = head_frame_index(actor, pose)
            frame = head['FRAM'][750]['data'][index * 10:(index + 1) * 10]
            expected, draws, directions, requests, reload_frame = idle_reference(level, initial, frame, tape)
            expected_bytes = bytearray(before)
            for name, value in expected.items():
                if name != 'remainder':
                    struct.pack_into('>h', expected_bytes, machine.FIELDS[name] + 0x5056, value)
            machine.call(7, 0x1268)
            actual = bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62))
            if (actual != expected_bytes or machine.working() != expected
                    or machine.level_bytes(len(level)) != level
                    or machine.draws != draws or machine.directions != directions
                    or machine.requests != requests or machine.reloads != int(reload_frame)
                    or machine.frame_bytes() != frame
                    or machine.attachment_bytes() != head['AFRM'][750]['data'][:8]):
                raise AssertionError(dict(initial=initial, tape=tape, actual=machine.working(),
                                          expected=expected, draws=machine.draws, expected_draws=draws,
                                          directions=machine.directions, requests=machine.requests))
            counts['idle'] += 1
            counts['pose_rejection'] += pose != 150
            counts['selections'] += bool(requests)
            counts['admission_queries'] += len(directions)
            sequences.update(requests)
            random_bounds.update(maximum for maximum, _value in draws)
            digest.update(actual + struct.pack('>h', machine.word(-0x481c)))
    return dict(
        level=7, cases=dict(counts), requested_sequences=dict(sequences),
        random_calls_by_maximum=dict(random_bounds), mismatches=0,
        outputs_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(program_bytes).hexdigest(),
        prince_sha256=hashlib.sha256(prince_bytes).hexdigest(),
        head_sha256=hashlib.sha256(head_bytes).hexdigest(),
        supplied=['17:6e06 Rnd: bounded explicit outcomes, requests/order checked',
                  '17:330e GetResource: actual Prince SEQS existence'],
        scope=('Full idle helper 7:1268, original movement-admission/cells/gate/math '
               'and JumpSeq/frame/supporting-column helpers. Supplied working state/body '
               'bounds at column 4 in actual head-slot rooms, explicit random tapes; '
               'no motion/animation ticks, RNG seed evolution/distribution, live '
               'reachability, wrapper scheduling or full AI claim.'),
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
