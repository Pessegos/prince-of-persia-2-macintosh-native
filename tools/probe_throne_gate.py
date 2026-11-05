"""Bounded native throne-grille foreground, rear-contact and camera-cut checks.

The displayed-room drawing branch7:2b22-2b4a calls7:383a for this special
gate. The latter temporarily promotes CUST record6. Its DrawCustomImg
endpoint is recorded, not rasterized. CheckGateInFore3:2722-2764 runs with
supplied actor row/column/mode and piece column9/row2; no services execute
in that selector. Full drawing lists, QuickDraw and FrameAdv are excluded.
"""

import argparse
import hashlib
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules
from tools.probe_gate_barriers import merged_ranges
from tools.probe_kid_engarde import NativeKidEngarde
from tools.probe_temple_collision_decision import NativeTempleCollisionDecision
from tools.probe_temple_collision_history import TABLES
from tools.probe_temple_gate_distance import NEIGHBOR_SLOTS
from tools.probe_temple_ground_collision import NativeTempleGroundCollision


class NativeThroneForeground(NativeRules):
    RANGES = {3: ((0x2722, 0x2764),), 7: ((0x383a, 0x3862),)}
    SUPPLIED = {(3, 0x2438): 'draw_custom'}
    CUSTOM = 0xc0000

    def dispatch(self, cpu, address, size, user):
        if address == self.address(3, 0x2438):
            stack = cpu.reg_read(self.registers['a7'])
            self.draws.append((struct.unpack('>2h', cpu.mem_read(stack + 4, 4)),
                               struct.unpack('>6h', cpu.mem_read(self.CUSTOM + 222, 12))))
        super().dispatch(cpu, address, size, user)


def foreground_probe(source):
    from unicorn.m68k_const import UC_M68K_REG_A6

    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    prince = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())
    ruins = parse_resource_fork((forks / 'Ruins.rsrc.bin').read_bytes())
    level, custom = prince['LEVL'][2007]['data'], ruins['CUST'][4200]['data']
    if struct.unpack_from('>3h', level, 0x2186)[::2] != (4, 8):
        raise AssertionError('Expected the original level-eight ruins header')
    machine = NativeThroneForeground(parse_resource_fork(executable))
    machine.reset(level)
    machine.draws = []
    machine.cpu.mem_write(machine.CUSTOM, custom)
    machine.cpu.mem_write(machine.A5 - 0x4c9e, struct.pack('>I', machine.CUSTOM))
    machine.call(7, 0x383a)
    expected = struct.unpack_from('>6h', custom, 222)
    promoted = (*expected[:3], 1, *expected[4:])
    if (machine.draws != [((6, 1), promoted)] or
            bytes(machine.cpu.mem_read(machine.CUSTOM, len(custom))) != custom):
        raise AssertionError('Native temporary front-pass promotion differs')
    selected, count = 0, 0
    for row in range(3):
        for column in range(10):
            for mode in range(10):
                machine.reset(level)
                machine.cpu.reg_write(UC_M68K_REG_A6, 0xe0000)
                for offset, value in ((-0x50c4, row), (-0x50c6, column), (-0x50c2, mode),
                                      (-0x45f8, 9), (-0x45f6, 2)):
                    machine.put_word(offset, value)
                actual = machine.call(3, 0x2722, stop=(3, 0x2764))
                wanted = row == 2 and column in (7, 8) and mode not in (2, 6)
                if bool(actual) != wanted or machine.services:
                    raise AssertionError((row, column, mode, actual, wanted))
                count += 1
                selected += bool(actual)
    return dict(selector_cases=count, promoted_cases=selected, custom_record=6,
                shape=struct.unpack_from('>H', custom, 2)[0] + expected[0],
                draw_arguments=[6, 1], original_pass=expected[3], restored=True,
                executable_sha256=hashlib.sha256(executable).hexdigest(), scope=__doc__)


class NativeThroneResponse(NativeTempleGroundCollision):
    RANGES = merged_ranges(NativeTempleGroundCollision, NativeKidEngarde)
    RANGES[4] += ((0x58de, 0x5a60), (0x3982, 0x39fc), (0x31fa, 0x322a))
    RANGES[6] += ((0x4864, 0x4908), (0x4918, 0x4c0e), (0x4dac, 0x4e7e))

    def dispatch(self, cpu, address, size, user):
        if address in (self.address(17, 0x330e), self.address(4, 0x3098)):
            stack = cpu.reg_read(self.registers['a7'])
            offset = 8 if address == self.address(17, 0x330e) else 4
            number = struct.unpack('>h', cpu.mem_read(stack + offset, 2))[0]
            self.events.append(('sequence_resource', number))
            self.return_value(self.sequences[number][0])
            return
        super().dispatch(cpu, address, size, user)


def actor(x, pose, column, *, armed=True, facing=0):
    result = bytearray(62)
    for offset, value in ((2, facing), (4, x + 207), (6, 346), (8, 0), (10, pose),
                          (12, column), (14, 2), (16, int(armed)), (22, 9), (26, int(armed)),
                          (28, -1), (30, 3), (38, 55 if armed else 2), (40, 55 if armed else 2)):
        struct.pack_into('>h', result, offset, value)
    return bytes(result)


def movement_probe(source):
    from unicorn.m68k_const import UC_M68K_REG_D5

    from pop2.sequence_runtime import SequenceState
    from pop2.terrain import LevelMap, RooftopPhysics, TerrainMotion

    forks = Path(source) / 'resource_forks'
    executable = parse_resource_fork((forks / 'Prince of Persia 2.bin').read_bytes())
    prince = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())
    kid = parse_resource_fork((forks / 'Kid.rsrc.bin').read_bytes())
    level = prince['LEVL'][2007]['data']
    if struct.unpack_from('>H', level, 8 * 60 + 28 * 2)[0] != 4:
        raise AssertionError('Expected the actual throne gate at native9/cell28')
    contact = NativeTempleCollisionDecision(executable)
    response = NativeThroneResponse(executable,
        {n: prince['SEQS'][n]['data'] for n in (2, 55, 64, 65, 227)},
        kid['FRAM'][25001]['data'], kid['AFRM'][25201]['data'])
    results = []
    for x in (385, 402, 415, 430):
        contact.reset(level)
        contact.cpu.mem_write(contact.A5 - 0x4496, struct.pack('>I', 0xb0000))
        contact.put_word(-0x4490, 0)
        for offset in NEIGHBOR_SLOTS:
            contact.put_word(offset, 0)
        for name, offset in TABLES.items():
            values = [9] * 10 if name.endswith('tags') else [0] * 10
            contact.cpu.mem_write(contact.A5 + offset, struct.pack('>10H', *values))
        # Explicit previous standing rectangle and first drawing rectangle.
        # Run CheckBarr twice: its previous bank precedes the draw reservation.
        for sample, bounds in ((actor(473, 15, 8, armed=False), (459, 268, 476, 346)),
                               (actor(x, 207, 7), (x - 14, 269, x + 14, 346))):
            contact.cpu.mem_write(contact.A5 - 0x5056, sample)
            for offset, value in ((-0x4fc2, 9), (-0x357c, 2), (-0x3564, bounds[0] + 207),
                                  (-0x3566, bounds[2] + 208), (-0x3560, bounds[3] - bounds[1] + 1),
                                  (-0x502c, bounds[1]), (-0x5028, bounds[3] + 1),
                                  (-0x36bc, 0), (-0x4fa6, 0)):
                contact.put_word(offset, value)
            contact.call(4, 0x4e34)
        contact.responses = []
        contact.call(4, 0x54da)
        delta = 470 - x
        if contact.responses != [('collide', delta, 0)]:
            raise AssertionError((x, contact.responses, delta))
        response.reset(level)
        response.cpu.mem_write(response.A5 - 0x5056, actor(x, 207, 7))
        response.put_word(-0x4fc2, 9)
        response.put_word(-0x4fa6, 0)
        response.call(4, 0x27ee, (9, 8, 2))
        response.call(4, 0x5738, (delta, 0))
        native = response.word(-0x5052) - 207, response.word(-0x504c), response.word(-0x502e)
        if native != (493, 160, 65):
            raise AssertionError((x, native))
        response.call(6, 0x4864, (1,), stop=(6, 0x4908))
        rebased = response.word(-0x5040), response.word(-0x5052) - 207
        if rebased != (21, -17):
            raise AssertionError((x, rebased))
        results.append(dict(x=x, correction=delta, final_x=native[0], pose=native[1], source=native[2],
                            cut_room=rebased[0], cut_x=rebased[1]))
    cuts = 0
    for facing in (-1, 0):
        for left in (458, 509, 510):
            for right in (515, 523, 524, 529):
                response.reset(level)
                response.cpu.mem_write(response.A5 - 0x5056, actor(493, 170, 9, facing=facing))
                for offset, value in ((-0x4fc2, 9), (-0x3570, right - left + 1),
                                      (-0x3572, left + 207), (-0x3574, right + 208)):
                    response.put_word(offset, value)
                response.call(6, 0x4918, stop=(6, 0x4c0e))
                direction = response.cpu.reg_read(UC_M68K_REG_D5) & 65535
                state = SequenceState(227, action=170, target_x=493,
                                      facing=int(facing == 0), actor_type=0, level_kind=4)
                motion = TerrainMotion(8, 2)
                changed = RooftopPhysics(LevelMap(level)).cut_horizontal(
                    motion, state, (left, 282, right, 348))
                if changed != (direction == 1) or changed and motion.room != 20:
                    raise AssertionError((facing, left, right, direction, changed, motion.room))
                cuts += 1
    return dict(rear_contacts=results, horizontal_cut_cases=cuts,
                supplied=['Type0 actor, preceding/current half-open body rectangles and empty MOB bank',
                          'Prepared original Kid FRAM25001/AFRM25201 and SEQS handles',
                          'Resource/Memory Manager handle boundaries; hGetSequence lookups',
                          'Collide is recorded in CheckCollide1, then executed separately with real animation'],
                executed=['CheckBarr/history/ReadCell/CheckCollide1; Collide/rear response/JumpSeq/AnimChar/LoadFrame',
                          'CutChar4918 to4c0e decision prefix and Cut4864 to4908 rebase; actual level8/header/links/gate'],
                excluded=['ShapeBounds input construction/rasterization, full FrameAdv, Cut reverse-link/redraw tail'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = dict(foreground=foreground_probe(args.source), movement=movement_probe(args.source))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
