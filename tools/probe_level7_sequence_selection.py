"""Execute original special-actor JumpSeq with resource-existence service supplied."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_frames import NativeHeadFrames, head_frame_index


def signed_word(value):
    return (value + 32768) % 65536 - 32768


def supporting_column(x, facing, frame):
    """Narrow research reference for 4:3a72 -> 4:3ad6 -> 5:48b0."""
    _, _, dx, _, flags = struct.unpack('>5h', frame)
    displacement = signed_word(dx - (flags & 63))
    foot = signed_word(x + (displacement if facing == 0 else -displacement))
    coordinate = signed_word(foot - 22)
    # DIVS truncates toward zero, unlike Python's negative floor division.
    # The original sign-extends BEFORE subtracting four from only the low word.
    # Preserve that order even at coordinate 0..3, where the low word wraps.
    dividend = (coordinate & ~65535) | ((coordinate - 4) & 65535)
    quotient = abs(dividend) // 51 * (-1 if dividend < 0 else 1)
    return quotient - 4 - (coordinate < 0), dividend - quotient * 51


def selection_reference(working, requested, exists, frame):
    state = dict(working)
    if not exists:
        return state, False
    state.update(sequence=requested, selected=requested, cursor=0)
    reload_frame = (state['actor'] in (7, 8) and state['facing'] == 0
                    and (130 <= requested <= 139 or requested == 166))
    if reload_frame:
        state['facing'] = -1
        if state['pose'] in (150, 159):
            state['x'] = signed_word(state['x'] - 12)
        state['column'], state['remainder'] = supporting_column(
            state['x'], state['facing'], frame)
    return state, reload_frame


class NativeHeadSelection(NativeHeadFrames):
    RANGES = {
        4: ((0x2a72, 0x2bcc), (0x3a72, 0x3a90), (0x3ad6, 0x3aea)),
        5: ((0x48b0, 0x48dc),),
        6: ((0x0006, 0x0098),),
    }
    FIELDS = dict(actor=-0x504e, pose=-0x504c, facing=-0x5054, x=-0x5052,
                  column=-0x504a, sequence=-0x5030, selected=-0x502e,
                  cursor=-0x5032, remainder=-0x481c)

    def __init__(self, program, head, sequences):
        super().__init__(program, head)
        self.sequence_ids = set(sequences)

    def reset(self, level):
        super().reset(level)
        self.requests = []
        self.reloads = 0

    def dispatch(self, cpu, address, size, user):
        if address == self.address(4, 0x2a72):
            self.reloads += 1
        if address == self.address(17, 0x330e):
            stack = cpu.reg_read(self.registers['a7'])
            kind, resource_id = struct.unpack('>4sh', cpu.mem_read(stack + 4, 6))
            if kind != b'SEQS':
                raise AssertionError(f'Unexpected resource type: {kind!r}')
            self.requests.append(resource_id)
            # JumpSeq only tests this handle for null; it does not dereference it.
            cpu.reg_write(self.registers['d0'], self.HANDLES + 8
                          if resource_id in self.sequence_ids else 0)
            destination = struct.unpack('>I', cpu.mem_read(stack, 4))[0]
            cpu.reg_write(self.registers['a7'], stack + 4)
            cpu.reg_write(self.registers['pc'], destination)
            return
        super().dispatch(cpu, address, size, user)

    def working(self):
        return {name: self.word(offset) for name, offset in self.FIELDS.items()}


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    program_bytes = (directory / 'Prince of Persia 2.bin').read_bytes()
    prince_bytes = (directory / 'Prince.rsrc.bin').read_bytes()
    head_bytes = (directory / 'Head.rsrc.bin').read_bytes()
    program, prince, head = (parse_resource_fork(data) for data in
                            (program_bytes, prince_bytes, head_bytes))
    level = prince['LEVL'][2006]['data']
    machine = NativeHeadSelection(program, head, prince['SEQS'])
    requested_ids = tuple(range(129, 141)) + (150, 165, 166, 167, 170, 175, 32000)
    if 32000 in machine.sequence_ids:
        raise AssertionError('Missing-resource control unexpectedly exists')
    cases = Counter()
    digest = hashlib.sha256()
    for actor, pose, facing, x, requested in product(
            (7, 8, 11), (149, 150, 151, 158, 159, 160, 181, 182), (-1, 0),
            (-51, 0, 21, 22, 207, 249, 458, 713), requested_ids):
        initial = dict(actor=actor, pose=pose, facing=facing, x=x, column=23,
                       sequence=170, selected=175, cursor=9, remainder=45)
        machine.reset(level)
        machine.cpu.mem_write(machine.A5 - 0x5056, bytes(62))
        for name, value in initial.items():
            machine.put_word(machine.FIELDS[name], value)
        machine.call(4, 0x2a8e)
        before = bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62))
        frame = head['FRAM'][750]['data']
        index = head_frame_index(actor, pose)
        expected_frame = frame[index * 10:(index + 1) * 10]
        expected, reload_frame = selection_reference(
            initial, requested, requested in machine.sequence_ids, expected_frame)
        expected_bytes = bytearray(before)
        for name, value in expected.items():
            if name != 'remainder':
                offset = machine.FIELDS[name] + 0x5056
                struct.pack_into('>h', expected_bytes, offset, value)
        machine.call(6, 0x0006, (requested,))
        actual = bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62))
        if (actual != expected_bytes or machine.working() != expected
                or machine.requests != [requested] or machine.reloads != int(reload_frame)
                or machine.frame_bytes() != expected_frame
                or machine.attachment_bytes() != head['AFRM'][750]['data'][:8]
                or machine.level_bytes(len(level)) != level):
            raise AssertionError(dict(initial=initial, requested=requested,
                                      actual=machine.working(), expected=expected,
                                      reloads=machine.reloads))
        cases['selection'] += 1
        cases['reload'] += reload_frame
        cases['missing_resource'] += requested not in machine.sequence_ids
        digest.update(actual + struct.pack('>h', machine.word(-0x481c)))
    for x in (-100, -51, -1, 0, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 207, 717):
        machine.reset(level)
        machine.call(4, 0x3ad6, (x,))
        native_column = signed_word(machine.cpu.reg_read(machine.registers['d0']))
        if (native_column, machine.word(-0x481c)) != supporting_column(x, 0, bytes(10)):
            raise AssertionError(f'Column boundary mismatch for foot X {x}')
        cases['column_boundary'] += 1
    return dict(
        level=7, cases=dict(cases), mismatches=0, outputs_sha256=digest.hexdigest(),
        executable_sha256=hashlib.sha256(program_bytes).hexdigest(),
        prince_sha256=hashlib.sha256(prince_bytes).hexdigest(),
        head_sha256=hashlib.sha256(head_bytes).hexdigest(),
        missing_resource_ids=[value for value in requested_ids if value not in machine.sequence_ids],
        supplied=['17:330e GetResource: non-null iff ID exists in actual Prince SEQS bank'],
        scope=('Full JumpSeq 6:0006 for supplied actor types 7/8/11, with native '
               'AddCharX, LoadFrame, supporting-foot and column calculations. Real Head '
               'FRAM/AFRM installed; SEQS existence supplied, no animation execution, '
               'resource-manager behavior, actor-1 hook, live reachability or cadence claim.'),
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
