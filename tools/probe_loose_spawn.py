"""Check original AnimLoose spawn fields, with supplied removal/writeback endpoints.

Executes CODE5:446a-4566 up to AddMob. MakeSpace5:2606, its foreground
writeback at44d8-44f8, and ClearCaveBelowFloor8:39b8 are supplied no-ops.
Those endpoints do not choose spawn Y/type. AddMob allocation, later movement,
dirty drawing, audio and full FrameAdv are excluded. Also executes ordinary
guard ContactChar5:3642 at the head boundary with a supplied synthetic FRAM
foot record/bank-loader endpoint; excludes AI and the host body-sweep exception.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from itertools import product
import struct

from pop2.mac_resources import parse_resource_fork
from pop2.cavern_state import CavernState
from pop2.terrain import LevelMap, floor_y, floor_contact_x
from pop2.opponent_generation import character_column
from pop2.sequence_runtime import SequenceState
from pop2.loose_floors import FallingFloor, floor_hits_actor
from tools.probe_ruins_slab_contact import NativeSlab
from tools.probe_level7_rules import NativeRules


class NativeSpawn(NativeRules):
    RANGES = {5: ((0x446a, 0x4566),)}
    SUPPLIED = {(5, 0x2606): 'make_space', (8, 0x39b8): 'clear_cave_below'}

    def dispatch(self, cpu, address, size, user):
        if address == self.address(5, 0x44d8):
            self.services['foreground_writeback'] += 1
            cpu.reg_write(self.registers['pc'], self.address(5, 0x44f8))
            return
        super().dispatch(cpu, address, size, user)


def run(source):
    root = source / 'resource_forks'
    original = (root / 'Prince of Persia 2.bin').read_bytes()
    prince_bytes = (root / 'Prince.rsrc.bin').read_bytes()
    program, prince = parse_resource_fork(original), parse_resource_fork(prince_bytes)
    machine = NativeSpawn(program)
    counts = Counter()
    outputs = hashlib.sha256()
    for number in range(3, 14):
        level = prince['LEVL'][1999 + number]['data']
        env, controller, header_number = struct.unpack_from('>3H', level, 0x2186)
        assert header_number == number
        assert env == (3 if number <= 5 else 4 if number <= 9 else 2)
        assert controller == {3: 2, 4: 15, 5: 9, 6: 9, 7: 12, 8: 9, 9: 2,
                              10: 9, 11: 13, 12: 13, 13: 22}[number]
        for room in range(32):
            for cell in range(30):
                if struct.unpack_from('>H', level, room * 60 + cell * 2)[0] != 11:
                    continue
                counts['anchors'] += 1
                for velocity in (0, 1, 39, 64):
                    machine.reset(level)
                    for offset, value in ((-0x4818, 11), (-0x43ec, room + 1),
                                          (-0x43ee, cell), (-0x43ea, velocity)):
                        machine.put_word(offset, value)
                    machine.call(5, 0x446a, stop=(5, 0x4566))
                    fields = tuple(machine.word(offset) for offset in
                                   (-0x44a6, -0x44a4, -0x44a2, -0x44a0,
                                    -0x449e, -0x449c, -0x449a, -0x4498))
                    row, column = divmod(cell, 10)
                    expected = (column * 51, (row + 1) * 120 + (23 if env == 3 else 5),
                                room + 1, velocity, 0, 0 if env == 3 else 3, row, 0)
                    terrain = LevelMap(bytearray(level))
                    terrain.caverns = CavernState()
                    loose = terrain.caverns.loose
                    loose.tiles[room, cell] = 11, 11
                    loose.active[room, cell] = velocity
                    loose.advance_tiles(terrain)
                    block, = loose.falling
                    port = (block.x, block.y, block.room + 1, block.velocity, 0, block.mob_type, block.row, 0)
                    assert fields == port, (number, room, cell, fields, port)
                    assert fields == expected, (number, room, cell, fields, expected)
                    assert machine.services == Counter(make_space=1, foreground_writeback=1,
                                                        **({'clear_cave_below': 1} if env == 3 else {}))
                    counts['comparisons'] += 1
                    outputs.update(struct.pack('>8h', *fields))
    contact = NativeSlab(program)
    level = prince['LEVL'][2009]['data']
    record = SimpleNamespace(offset_x=0, aux=0x40)
    for facing, row, relative_y, dy in product((0, 1), range(3), (-12, 0, 6), (-1, 0, 1)):
        state = SequenceState(2, action=166, actor_type=2, facing=facing,
                              target_x=300, current_y=relative_y)
        column = character_column(floor_contact_x(300, facing, record))
        before = contact.actor(level, state, row, column, record)
        y = floor_y(row) + relative_y - 57 + dy
        block = FallingFloor(3, column, row, y, mob_type=3)
        for offset, value in ((-0x44a6, block.x), (-0x44a4, y),
                              (-0x44a2, 4), (-0x449a, row)):
            contact.put_word(offset, value)
        native = bool(contact.call(5, 0x3642, arg_bytes=struct.pack('>I', contact.ACTOR)))
        assert native == floor_hits_actor(block, SimpleNamespace(room=3, row=row), state, record)
        assert native == (dy > 0), (facing, row, relative_y, dy, native)
        assert bytes(contact.cpu.mem_read(contact.ACTOR, 62)) == before
        assert contact.level_bytes(len(level)) == level
        counts['guard_head_contacts'] += 1
    return dict(counts=dict(counts), mismatches=0, scope=__doc__, outputs_sha256=outputs.hexdigest(),
                original_sha256=hashlib.sha256(original).hexdigest(),
                prince_sha256=hashlib.sha256(prince_bytes).hexdigest())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.source)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(result['counts'], 'mismatches:', result['mismatches'])
