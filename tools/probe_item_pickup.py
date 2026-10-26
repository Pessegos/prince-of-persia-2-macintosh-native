"""Check native TryPickUp admission using original LEVL and Kid FRAM bytes.

Working actor fields and FRAM offset/flags are supplied. Only PickItUp's entry
is intercepted; no read-cell/admission helpers are stubbed. This checks reach
and the held-Shift gate, not animation, effects or the complete controller.
"""

import argparse
import json
from pathlib import Path
import struct
from types import SimpleNamespace

from pop2.animation_data import parse_frame_records
from pop2.mac_resources import parse_resource_fork
from pop2.potions import pickup_target
from pop2.sequence_runtime import SequenceState
from pop2.terrain import LevelMap
from tools.probe_level7_rules import NativeRules


class NativePickup(NativeRules):
    RANGES = {
        4: ((0x26e2, 0x28a8), (0x28b6, 0x29c0), (0x2bae, 0x2bcc),
            (0x322a, 0x3262), (0x35a6, 0x35b8), (0x39fc, 0x3a32), (0x3a72, 0x3aea)),
        5: ((0x0004, 0x0066), (0x48b0, 0x48dc)),
        6: ((0x0c50, 0x0c66), (0x1350, 0x13c0)),
    }
    SUPPLIED = {}

    def dispatch(self, cpu, address, size, user):
        if address == self.address(6, 0x13d0):
            self.accepted = self.reached = True
            cpu.emu_stop()
            return
        super().dispatch(cpu, address, size, user)

    def pickup(self, level, frames, x, facing, pose, room=17, row=1, held=None):
        self.reset(level)
        self.accepted = False
        self.cpu.mem_write(self.A5 - 0x5056, bytes(62))
        _shape, _attachment, offset_x, _offset_y, flags = struct.unpack_from('>5h', frames, pose * 10)
        for offset, value in ((-0x5052, x + 207), (-0x5054, -1 if facing == 0 else 0),
                              (-0x5040, room), (-0x5048, row), (-0x504c, pose),
                              (-0x520e, offset_x), (-0x520a, flags)):
            self.put_word(offset, value)
        foot = self.call(4, 0x3a72)
        column = self.call(4, 0x3ad6, (foot,))
        self.put_word(-0x504a, column)
        if held is None:
            self.call(6, 0x1350)
        else:
            self.put_word(-0x3480, -1 if held else 0)
            self.call(6, 0x0c50, stop=(6, 0x0c66))
            assert self.word(-0x3480) == (-1 if held else 0)
        return self.accepted, column


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    program, prince, kid = (parse_resource_fork((directory / name).read_bytes()) for name in
                           ('Prince of Persia 2.bin', 'Prince.rsrc.bin', 'Kid.rsrc.bin'))
    machine = NativePickup(program)
    level, frames = prince['LEVL'][2005]['data'], kid['FRAM'][25001]['data']
    terrain, records = LevelMap(level), parse_frame_records(frames)
    motion = SimpleNamespace(room=16, row=1)
    result = []
    calls = 0
    for pose in (15, 50, 51, 52, 109):
        for facing in (0, 1):
            admitted = []
            for x in range(180, 400):
                accepted, column = machine.pickup(level, frames, x, facing, pose)
                state = SequenceState(13, action=pose, target_x=x, facing=facing)
                actual = pickup_target(terrain, motion, state, records[pose])
                if (actual is not None) != accepted:
                    raise AssertionError(f'Pickup admission differs at {x=}, {facing=}, {pose=}')
                calls += 1
                if pose != 109:
                    for held in (False, True):
                        gated, _ = machine.pickup(level, frames, x, facing, pose, held=held)
                        if gated != (held and accepted):
                            raise AssertionError('StandingCtrl did not resample held Shift')
                        calls += 1
                if accepted:
                    admitted.append(x)
            result.append(dict(pose=pose, facing=facing, first=min(admitted), last=max(admitted)))
    return dict(calls=calls, admission=result, scope=__doc__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_probe(args.source), indent=2))


if __name__ == '__main__':
    main()
