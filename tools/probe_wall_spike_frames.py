"""Execute original LoadFrame + GetCharEdges + CheckSpikes + CheckSpikeHit on real frames.

For level five's wall spikes (LEVL2004), the actual type0 LoadFrame 4:2a72,
SetupSword 3:0ac8 and GetCharEdges 4:5cbc compute the column and edges of a
Kid frame (FRAM/AFRM 25001, SHAP sizes from the preserved headers), then
CheckSpikes 5:3c42 (with ReadCell, 4:3b30, TriggerSpikes 5:40a0) and
CheckSpikeHit 5:3af8 (IsDeadPos, MobSpikes) run on a fresh trap. The result
for each (pose, facing, armed, X) is whether the trap was triggered and
whether the impalement 5:3cee was called; `tools/audit_wall_spike_frames.py`
compares it with the port's own inputs.
"""

import argparse
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_sprite_bounds import NativeTempleSpriteBounds, shape_sizes


SPIKE_RANGES = {4: ((0x26e2, 0x28a8), (0x28b6, 0x29c0), (0x322a, 0x3262), (0x3b30, 0x3b86),
                    (0x47a0, 0x48e8)),
                5: ((0x0004, 0x0066), (0x4e0c, 0x4e42), (0x3af8, 0x3c40), (0x3c42, 0x3cec), (0x3fa4, 0x3fd8), (0x40a0, 0x4196))}
SINKS = {(5, 0x3cee): 'impale', (5, 0x2914): 'mob', (5, 0x3f42): 'find_mob', (10, 0x1fa8): 'env2'}
DRAWING = struct.pack('>10h', -1, 53, 59, -1, 2, 61, 67, 71, 73, 79)
POSES = tuple(range(1, 15)) + (15, 49, 50, 51, 52, 55, 56, 57, 150, 151, 152, 153, 154, 155, 156,
                                157, 158, 159, 160, 161, 162, 163, 164, 165, 170, 171)


class NativeSpikeFrames(NativeTempleSpriteBounds):
    RANGES = {s: NativeTempleSpriteBounds.RANGES.get(s, ()) + SPIKE_RANGES.get(s, ())
              for s in NativeTempleSpriteBounds.RANGES.keys() | SPIKE_RANGES.keys()}

    def dispatch(self, cpu, address, size, user):
        name = SINKS.get(divmod(address - self.CODE_BASE, 0x10000))
        if name and address != self.stop_at:
            self.events.append(name)
            stack = cpu.reg_read(self.registers['a7'])
            cpu.reg_write(self.registers['d0'], 0)
            cpu.reg_write(self.registers['pc'], struct.unpack('>I', cpu.mem_read(stack, 4))[0])
            cpu.reg_write(self.registers['a7'], stack + 4)
            return
        super().dispatch(cpu, address, size, user)


def spike_cells(level):
    rooms = struct.unpack_from('>h', level, 0x2180)[0]
    return [(room, cell) for room in range(1, rooms + 1) for cell in range(30)
            if struct.unpack_from('>H', level, (room - 1) * 60 + cell * 2)[0] == 2]


def run_probe(source, room=23):
    directory = Path(source) / 'resource_forks'
    path = directory / 'Prince of Persia 2.bin'
    executable = path.read_bytes()
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    kid = parse_resource_fork((directory / 'Kid.rsrc.bin').read_bytes())
    frames, attachments = kid['FRAM'][25001]['data'], kid['AFRM'][25001]['data']
    machine = NativeSpikeFrames(parse_resource_fork(executable), frames, attachments, shape_sizes(kid))
    level = prince['LEVL'][2004]['data']
    cells = [cell for number, cell in spike_cells(level) if number == room]
    if len(cells) != 1:
        raise ValueError('Expected one wall trap in the room')
    row, column = divmod(cells[0], 10)
    foreground = 0x780 + (room - 1) * 120 + cells[0] * 4
    y = row * 120 + 118
    results, digest = [], hashlib.sha256()
    xs = range((column + 1) * 51 + 207 - 20, (column + 1) * 51 + 207 + 140)
    for pose, facing, armed, x in product(POSES, (0, -1), (0, 1), xs):
        actor = bytearray(actor_fixture(room, row, column + 2, facing, 2))
        for offset, value in ((4, x), (6, y), (10, pose), (26, armed), (40, 57)):
            put_actor(actor, offset, value)
        machine.reset(level)
        machine.events = []
        for offset, data in ((-0x5056, bytes(actor)), (-0x34c6, DRAWING)):
            machine.cpu.mem_write(machine.A5 + offset, data)
        machine.call(4, 0x2a72)
        machine.call(3, 0x0ac8)
        machine.call(4, 0x5cbc)
        native_column = machine.word(-0x504a)
        machine.call(5, 0x3c42)
        trigger = struct.unpack('>H', machine.cpu.mem_read(machine.LEVEL + foreground, 2))[0] & 255
        machine.call(5, 0x3af8)
        row_result = dict(pose=pose, facing=facing, armed=armed, x=x, column=native_column,
                          width=machine.word(-0x3562), left=machine.word(-0x3564),
                          triggered=trigger == 1, impaled='impale' in machine.events)
        results.append(row_result)
        digest.update(json.dumps(row_result, sort_keys=True).encode())
    if path.read_bytes() != executable:
        raise AssertionError('Read-only original changed')
    return dict(room=room, cell=cells[0], cases=len(results), result_sha256=digest.hexdigest(),
                executable_sha256=hashlib.sha256(executable).hexdigest(), results=results,
                supplied=['LEVL2004 with a fresh trap (foreground 0), Kid FRAM/AFRM 25001, SHAP sizes',
                          'Floor Y row*120+118; sinks: impalement 5:3cee, MOB add 5:2914, MOB lookup'
                          ' 5:3f42 (none), level-two branch 10:1fa8'],
                exclusions=['No FrameAdv/AnimChar, no MOB phase controller, one frame per case'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'results'}))


if __name__ == '__main__':
    main()
