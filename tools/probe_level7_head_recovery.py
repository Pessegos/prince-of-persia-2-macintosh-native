"""Probe original head peaceful/attack-recovery leaves, including native JumpSeq."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_frames import head_frame_index
from tools.probe_level7_sequence_selection import (
    NativeHeadSelection, selection_reference, supporting_column,
)


def peaceful_reference(working, frame):
    state, reload_frame = selection_reference(working, 139, True, frame)
    state['column'], state['remainder'] = supporting_column(state['x'], state['facing'], frame)
    state.update(x=207 + state['column'] * 51 + 47, y=state['row'] * 120 + 73,
                 horizontal_velocity=0, vertical_velocity=0, armed=0, alert=0)
    return state, reload_frame


def recovery_reference(working, frame, cached_alive):
    if cached_alive >= 6:
        state, reload_frame = peaceful_reference(working, frame)
        requested, clear_mode = [139], True
    elif working['selected'] != 166:
        state = dict(working, y=working['row'] * 120 + 73)
        state, reload_frame = selection_reference(state, 166, True, frame)
        requested, clear_mode = [166], False
    else:
        state, reload_frame, requested, clear_mode = dict(working), False, [], False
    state['special'] = 0
    return state, reload_frame, requested, clear_mode


class NativeHeadRecovery(NativeHeadSelection):
    RANGES = {
        **NativeHeadSelection.RANGES,
        4: NativeHeadSelection.RANGES[4] + ((0x31fa, 0x3228), (0x34e2, 0x34f0)),
        7: ((0x0b16, 0x0b54), (0x1012, 0x1064)),
    }
    FIELDS = dict(NativeHeadSelection.FIELDS, slot=-0x5056, room=-0x5040,
                  row=-0x5048, y=-0x5050, horizontal_velocity=-0x5044,
                  vertical_velocity=-0x5042, armed=-0x503c, alert=-0x5024,
                  special=-0x5022)

    def configure(self, level, initial, cached_alive):
        self.reset(level)
        self.cpu.mem_write(self.A5 - 0x5056, bytes(62))
        for name, value in initial.items():
            self.put_word(self.FIELDS[name], value)
        self.cpu.mem_write(self.A5 - 0x5094, bytes(62))
        self.put_word(-0x5078, cached_alive)
        self.call(4, 0x2a8e)


class NativeHeadRecoveryRouting(NativeHeadRecovery):
    RANGES = {
        **NativeHeadRecovery.RANGES,
        4: NativeHeadRecovery.RANGES[4] + (
            (0x3272, 0x3284), (0x338e, 0x33b4), (0x4a46, 0x4aa0)),
        6: NativeHeadRecovery.RANGES[6] + ((0x3642, 0x36de),),
        7: NativeHeadRecovery.RANGES[7] + ((0x1324, 0x1452),),
    }

    def dispatch(self, cpu, address, size, user):
        if address == self.address(4, 0x5cbc):
            self.bounds_calls += 1
            stack = cpu.reg_read(self.registers['a7'])
            destination = struct.unpack('>I', cpu.mem_read(stack, 4))[0]
            cpu.reg_write(self.registers['a7'], stack + 4)
            cpu.reg_write(self.registers['pc'], destination)
            return
        if address == self.address(7, 0x0b16):
            self.done_calls += 1
        super().dispatch(cpu, address, size, user)

    def reset(self, level):
        super().reset(level)
        self.bounds_calls = self.done_calls = 0


def head_slots(level):
    for room in range(1, 33):
        base = 0x20e6 + room * 0xc0
        for slot in range(struct.unpack_from('>H', level, base)[0]):
            offset = base + 2 + slot * 38
            kind = struct.unpack_from('>h', level, offset + 0x18)[0]
            if kind in (5, 6):
                yield room, slot, offset, 7 if kind == 5 else 8


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    program_bytes = (directory / 'Prince of Persia 2.bin').read_bytes()
    prince_bytes = (directory / 'Prince.rsrc.bin').read_bytes()
    head_bytes = (directory / 'Head.rsrc.bin').read_bytes()
    program, prince, head = (parse_resource_fork(data) for data in
                            (program_bytes, prince_bytes, head_bytes))
    if not {139, 166} <= set(prince['SEQS']):
        raise AssertionError('Required original head sequences missing')
    level = prince['LEVL'][2006]['data']
    machine = NativeHeadRecoveryRouting(program, head, prince['SEQS'])
    counts = Counter()
    digest = hashlib.sha256()

    def check(initial, record_offset, mode, cached_alive, leaf, target=None):
        supplied = bytearray(level)
        struct.pack_into('>h', supplied, record_offset + 0x1c, mode)
        machine.configure(supplied, initial, cached_alive)
        if target is not None:
            machine.put_word(-0x503a, -1)
            target_bytes = bytearray(62)
            struct.pack_into('>h', target_bytes, 0x1c, cached_alive)
            for offset, value in zip((0x1e, 0x28, 0x0a), target):
                struct.pack_into('>h', target_bytes, offset, value)
            machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(target_bytes))
        initial_bytes = bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62))
        cached_bytes = (bytes(target_bytes) if target is not None else
                        bytes(machine.cpu.mem_read(machine.A5 - 0x5094, 62)))
        frame_index = head_frame_index(initial['actor'], initial['pose'])
        frame = head['FRAM'][750]['data'][frame_index * 10:(frame_index + 1) * 10]
        if leaf == 'peaceful':
            expected, reload_frame = peaceful_reference(initial, frame)
            requests, clear_mode, entry = [139], True, 0x1012
        else:
            expected, reload_frame, requests, clear_mode = recovery_reference(initial, frame, cached_alive)
            entry = 0x0b16
        expected_level = bytearray(supplied)
        if clear_mode:
            struct.pack_into('>h', expected_level, record_offset + 0x1c, 0)
        expected_bytes = bytearray(initial_bytes)
        for name, value in expected.items():
            if name != 'remainder':
                struct.pack_into('>h', expected_bytes, machine.FIELDS[name] + 0x5056, value)
        if target is None:
            machine.call(7, entry, arg_bytes=struct.pack('>I', machine.LEVEL + record_offset + 0x1c))
        else:
            machine.call(7, 0x1324)
        actual = bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62))
        if (actual != expected_bytes or machine.working() != expected
                or machine.level_bytes(len(level)) != expected_level
                or bytes(machine.cpu.mem_read(machine.A5 - 0x5094, 62)) != cached_bytes
                or machine.requests != requests or machine.reloads != int(reload_frame)
                or machine.frame_bytes() != frame
                or machine.attachment_bytes() != head['AFRM'][750]['data'][:8]):
            raise AssertionError(dict(leaf=leaf, initial=initial, cached_alive=cached_alive,
                                      actual=machine.working(), expected=expected,
                                      requests=machine.requests, reloads=machine.reloads))
        if target is not None:
            bank = machine.A5 - 0x5208 + initial['slot'] * 62
            if (bytes(machine.cpu.mem_read(bank, 62)) != expected_bytes
                    or bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62)) != cached_bytes
                    or machine.done_calls != 1):
                raise AssertionError('Wrapper recovery did not save the native actor/restore Prince')
        counts[leaf] += 1
        counts['peaceful_transitions'] += clear_mode
        digest.update(actual + machine.level_bytes(len(level)))

    for room, slot, offset, actor in head_slots(level):
        for pose, facing, x, row, mode in product(
                (149, 150, 159, 165, 166, 173, 181, 182), (-1, 0),
                (249, 458, 713), (0, 1, 2), (-1, 1, 3)):
            initial = dict(actor=actor, pose=pose, facing=facing, x=x, column=7,
                           sequence=170, selected=175, cursor=9, remainder=45,
                           room=room, slot=slot, row=row, y=333,
                           horizontal_velocity=7, vertical_velocity=-9,
                           armed=1, alert=3, special=6)
            check(initial, offset, mode, -1, 'peaceful')
        for pose, facing, x, row, selected, cached_alive in product(
                (150, 159, 166), (-1, 0), (249, 458, 713), (0, 1, 2),
                (130, 166, 175), (-1, 0, 5, 6, 7, 20)):
            initial = dict(actor=actor, pose=pose, facing=facing, x=x, column=7,
                           sequence=170, selected=selected, cursor=9, remainder=45,
                           room=room, slot=slot, row=row, y=333,
                           horizontal_velocity=7, vertical_velocity=-9,
                           armed=1, alert=3, special=6)
            check(initial, offset, 3, cached_alive, 'done')
        for pose, facing, mode, cached_alive, target in product(
                (150, 159, 166), (-1, 0), (1, 3), (-1, 0, 5, 6, 7, 20),
                ((0, 5, 15), (1, 70, 0), (1, 70, 223))):
            initial = dict(actor=actor, pose=pose, facing=facing, x=458, column=7,
                           sequence=170, selected=175, cursor=9, remainder=45,
                           room=room, slot=slot, row=1, y=333,
                           horizontal_velocity=7, vertical_velocity=-9,
                           armed=1, alert=3, special=6)
            check(initial, offset, mode, cached_alive, 'wrapper_done', target)
    return dict(
        level=7, cases=dict(counts), mismatches=0, outputs_sha256=digest.hexdigest(),
        executable_sha256=hashlib.sha256(program_bytes).hexdigest(),
        prince_sha256=hashlib.sha256(prince_bytes).hexdigest(),
        head_sha256=hashlib.sha256(head_bytes).hexdigest(),
        supplied=['17:330e GetResource: actual Prince SEQS existence; no animation data returned',
                  '4:5cbc shape bounds inert in additional wrapper checks'],
        scope=('Full HeadGetPeaceful 7:1012 and HeadDoneAttackingKid 7:0b16 with native '
               'JumpSeq, frame/supporting-column helpers, velocity clear and floor placement. '
               'Actual head slots, supplied working states/cached ALIVE, directly supplied '
               'record-mode pointer in direct leaf checks. Additional native wrapper checks '
               'cover target rejection, record lookup, mode-pointer derivation, bank save and '
               'Prince restore with inert shape bounds. No other wrapper routes, animation, record serialization, '
               'reachability, actual death timing, drawing, collision or full AI claim.'),
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
