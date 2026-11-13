"""Compare original level12 room3 takeoff alignment and selected Catch fixtures."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from pop2.sequence_runtime import SequenceState
from pop2.terrain import LevelMap
from tools.probe_level7_rules import NativeRules
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_kid_frames import NativeKidFrameSupport


class NativeJumpGeometry(NativeKidFrameSupport):
    RANGES = {
        3: ((0x4da6, 0x4dd4), (0x4de2, 0x4e20), (0x4eb2, 0x4f24)),
        4: NativeRules.RANGES[4] + NativeKidFrameSupport.RANGES[4] + (
            (0x27ee, 0x29c0), (0x2bae, 0x2bcc), (0x37ca, 0x38aa),
            (0x393e, 0x3fea), (0x3ff8, 0x412e), (0x3a92, 0x3ad4)),
        5: NativeRules.RANGES[5] + NativeKidFrameSupport.RANGES[5],
        6: ((0x1c14, 0x1d5e), (0x5eca, 0x5f5e)),
    }
    SUPPLIED = {(6, 0x0006): 'jump_sequence', (4, 0x3e3a): 'clear_controls'}


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(executable)
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    kid = parse_resource_fork((directory / 'Kid.rsrc.bin').read_bytes())
    level = bytearray(prince['LEVL'][2011]['data'])
    if struct.unpack_from('>3H', level, 0x2186)[::2] != (2, 12):
        raise ValueError('Expected original temple level12')
    # The left gate is open in the supplied run; no other cells are edited.
    struct.pack_into('>H', level, 0x780 + 2 * 120 + 2 * 4, 184)
    machine = NativeJumpGeometry(program, kid['FRAM'][25001]['data'], kid['AFRM'][25001]['data'])
    terrain = LevelMap(level)
    count = 0
    for facing in (0, 1):
        for x in range(30, 301):
            actor = bytearray(actor_fixture(3, 0, 0, 0 if facing else -1, 1))
            for offset, value in ((4, x + 207), (6, 106), (10, 7), (28, -1), (38, 1), (40, 1)):
                put_actor(actor, offset, value)
            machine.reset(level)
            machine.cpu.mem_write(machine.A5 - 0x5056, bytes(actor))
            machine.call(4, 0x2a72)
            accepted = machine.call(6, 0x1c14, (4,))
            actual = None if not accepted else machine.word(-0x5052) - 207 - x
            state = SequenceState(1, actor_type=0, facing=facing, target_x=x)
            expected = terrain.run_jump_offset(2, 0, state)
            if actual != expected:
                raise AssertionError((facing, x, actual, expected))
            count += 1
    catches = []
    for x, y, expected in ((404, 196, False), (411, 196, True), (412, 229, True)):
        actor = bytearray(actor_fixture(3, 1, 7, 0, 4))
        for offset, value in ((4, x + 207), (6, y), (10, 106), (18, 8), (20, 27),
                              (28, -1), (30, 3), (38, 12), (40, 21)):
            put_actor(actor, offset, value)
        machine.reset(level)
        machine.cpu.mem_write(machine.A5 - 0x5056, bytes(actor))
        machine.put_word(-0x3480, -1)
        machine.put_word(-0x4fc2, 3)
        machine.call(4, 0x2a72)
        machine.call(4, 0x37ca, stop=(4, 0x38a0))
        actual = bool(machine.cpu.reg_read(machine.registers['d0']) & 65535)
        if actual != expected:
            raise AssertionError((x, y, actual))
        catches.append(dict(x=x, y=y, raw_catch=actual))
    return dict(alignment_cases=count, raw_catch_cases=catches, mismatches=0,
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                supplied=['Prepared original Kid FRAM/AFRM handles, player pose7 and room3 fixtures',
                          'Room3 left gate foreground184', 'JumpSeq and ClearControls are inert sinks',
                          'Catch stops after IsLedge before acceptance side effects'],
                exclusions=['Keyboard timing, AnimChar, takeoff reachability, full FrameAdv',
                            'Falling caller height gate (raw Catch admits Y-floor3)',
                            'Successful Catch animation/sound/alignment'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f"{result['alignment_cases']} alignment cases and 3 raw Catch fixtures; zero mismatches")


if __name__ == '__main__':
    main()
