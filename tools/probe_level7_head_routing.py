"""Execute head-mode routing with native record/frame loading and explicit leaf boundaries."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_frames import NativeHeadFrames


def head_route(mode, target_flag, target_sequence, target_pose, own_pose, visibility,
               *, native_alive=-1, record_present=True):
    if native_alive >= 0 or not record_present:
        return None
    target_available = bool(target_flag) and not (
        target_sequence == 70 and (target_pose == 0 or target_pose >= 223))
    if mode == 0:
        return ('angry' if target_available and own_pose in (150, 165, 166, 159, 173)
                and visibility != -1 else 'idle')
    if mode == 1:
        return 'attack' if target_available else 'done'
    if mode == 2:
        return 'flee'
    if mode == 3:
        return 'locked' if target_available else 'done'
    return None


class NativeHeadRouting(NativeHeadFrames):
    RANGES = {
        4: ((0x2a8e, 0x2bac), (0x3272, 0x3284), (0x338e, 0x33b4), (0x4a46, 0x4aa0)),
        6: ((0x3642, 0x36de),),
        7: ((0x1324, 0x1452),),
    }
    LEAVES = {0x1268: 'idle', 0x0f88: 'angry', 0x064c: 'attack',
              0x0b16: 'done', 0x0cae: 'flee', 0x1164: 'locked'}

    def dispatch(self, cpu, address, size, user):
        segment, offset = divmod(address - self.CODE_BASE, 0x10000)
        result = None
        handled = False
        if segment == 7 and offset in self.LEAVES:
            self.leaves.append(self.LEAVES[offset])
            handled = True
        elif (segment, offset) == (7, 0x00f8):
            self.visibility_calls += 1
            result = self.visibility
            handled = True
        elif (segment, offset) == (4, 0x5cbc):
            self.bounds_calls += 1
            handled = True
        if handled:
            stack = cpu.reg_read(self.registers['a7'])
            destination = struct.unpack('>I', cpu.mem_read(stack, 4))[0]
            cpu.reg_write(self.registers['a7'], stack + 4)
            if result is not None:
                cpu.reg_write(self.registers['d0'], result & 0xffffffff)
            cpu.reg_write(self.registers['pc'], destination)
            return
        super().dispatch(cpu, address, size, user)

    def configure(self, level, room, slot, actor, pose, target_flag, target_sequence,
                  target_pose, visibility, alive=-1):
        self.reset(level)
        self.cpu.mem_write(self.A5 - 0x5056, bytes(62))
        for offset, value in ((-0x5056, slot), (-0x5040, room), (-0x504e, actor),
                              (-0x504c, pose), (-0x503a, alive), (-0x502e, 130)):
            self.put_word(offset, value)
        target = bytearray(62)
        struct.pack_into('>h', target, 0x1e, target_flag)
        struct.pack_into('>h', target, 0x28, target_sequence)
        struct.pack_into('>h', target, 0x0a, target_pose)
        self.cpu.mem_write(self.A5 - 0x50d2, bytes(target))
        self.target = bytes(target)
        self.visibility = visibility
        self.leaves = []
        self.visibility_calls = 0
        self.bounds_calls = 0


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    program_bytes = (directory / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(program_bytes)
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    head = parse_resource_fork((directory / 'Head.rsrc.bin').read_bytes())
    level = prince['LEVL'][2006]['data']
    machine = NativeHeadRouting(program, head)
    counts, leaves = Counter(), Counter()
    digest = hashlib.sha256()
    for room in range(1, 33):
        base = 0x20e6 + room * 0xc0
        count = struct.unpack_from('>H', level, base)[0]
        for slot in range(count):
            offset = base + 2 + slot * 38
            kind = struct.unpack_from('>h', level, offset + 0x18)[0]
            if kind not in (5, 6):
                continue
            actor = 7 if kind == 5 else 8
            for mode, flag, selected, target_pose, own_pose, visibility in product(
                    (-1, 0, 1, 2, 3, 4), (0, 1), (5, 70), (0, 15, 222, 223, 250),
                    (149, 150, 159, 164, 165, 166, 173), (-1, 0, 4)):
                supplied = bytearray(level)
                struct.pack_into('>h', supplied, offset + 0x1c, mode)
                machine.configure(supplied, room, slot, actor, own_pose, flag,
                                  selected, target_pose, visibility)
                machine.call(7, 0x1324)
                expected = head_route(mode, flag, selected, target_pose, own_pose, visibility)
                expected_calls = [] if expected is None else [expected]
                if machine.leaves != expected_calls:
                    raise AssertionError(dict(room=room, slot=slot, mode=mode, flag=flag,
                                              selected=selected, target_pose=target_pose,
                                              own_pose=own_pose, visibility=visibility,
                                              native=machine.leaves, expected=expected_calls))
                if (machine.level_bytes(len(level)) != supplied
                        or bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62)) != machine.target):
                    raise AssertionError('Routing with inert leaves changed its record/Prince snapshot')
                counts['mode_routing'] += 1
                leaves[expected or 'no_leaf'] += 1
                digest.update((expected or 'no_leaf').encode('ascii') + b'\0')
            for alive in (0, 1, 20):
                machine.configure(level, room, slot, actor, 150, 1, 5, 15, 4, alive)
                machine.call(7, 0x1324)
                if machine.leaves or machine.visibility_calls or machine.bounds_calls:
                    raise AssertionError('Nonnegative ALIVE did not reject head control')
                counts['nonnegative_alive'] += 1
    for room in range(1, 33):
        base = 0x20e6 + room * 0xc0
        slot = struct.unpack_from('>H', level, base)[0]
        machine.configure(level, room, slot, 7, 150, 1, 5, 15, 4)
        machine.call(7, 0x1324)
        if machine.leaves or machine.bounds_calls or machine.visibility_calls:
            raise AssertionError('Missing record did not reject head control')
        counts['missing_record'] += 1
    return dict(
        level=7, cases=dict(counts), leaves=dict(leaves), mismatches=0,
        outputs_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(program_bytes).hexdigest(),
        supplied=['4:5cbc shape bounds inert', '7:00f8 visibility supplied as -1/0/4',
                  '7:1268/0f88/064c/0b16/0cae/1164 leaves record request and return'],
        scope=('Original 7:1324 wrapper with native GetOppInfoIdx, cached-Prince copy, '
               'LoadFrame using real Head FRAM/AFRM, and native working-bank save. '
               'Modes, working state, cached-Prince fields and visibility are supplied. '
               'No leaf effects, actual sight geometry, movement or full AI parity claim.'),
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
