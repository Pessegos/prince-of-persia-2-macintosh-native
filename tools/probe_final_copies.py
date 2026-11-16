"""Compare CODE 9:1526 (room 6's false Princes) with the port's copy_control.

The original 9:1526 and CharDistance 4:49ee run in Unicorn over LEVL 2013,
whose room-6 bank count (+0x20e6 + room * 0xc0) each case rewrites.
Supplied endpoints, recording their word arguments: SetSeq 6:0006, AddSound
5:4d84 and AddCharX 4:2bae (returns X + 15 along the facing). The FRAM flag
table is synthetic and given to both sides. The port reads one Prince view
for both the opponent record (a5-0x5094) and the saved Prince (a5-0x50d2);
the probe writes the same values to both, so a difference between those two
records is excluded.
"""

import argparse
from collections import Counter
from pathlib import Path
import random
import struct
from types import SimpleNamespace

from pop2.final_tower import COPY_ROOM, PrinceView, copy_control
from pop2.mac_resources import parse_resource_fork
from tools.probe_final_path import FRAM_BASE, FRAM_HANDLE, frame_flags
from tools.probe_level7_rules import NativeRules

CHAR, OPP, SAVED = -0x5056, -0x5094, -0x50d2
NATIVE_ROOM = COPY_ROOM + 1
BANK = 0x20e6 + NATIVE_ROOM * 0xc0


class NativeCopies(NativeRules):
    RANGES = {
        **NativeRules.RANGES,
        4: (*NativeRules.RANGES[4], (0x49ee, 0x4a46)),
        9: ((0x1526, 0x16fe),),
    }
    SUPPLIED = {(6, 0x0006): 'select', (5, 0x4d84): 'sound', (4, 0x2bae): 'add_x'}

    def reset(self, level):
        super().reset(level)
        self.calls = []

    def dispatch(self, cpu, address, size, user):
        segment, offset = divmod(address - self.CODE_BASE, 0x10000)
        service = self.SUPPLIED.get((segment, offset))
        if service is not None:
            stack = cpu.reg_read(self.registers['a7'])
            self.calls.append((service, struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]))
        super().dispatch(cpu, address, size, user)
        if service == 'add_x':
            facing = self.word(CHAR + 2)
            step = self.calls[-1][1]
            cpu.reg_write(self.registers['d0'],
                          (self.word(CHAR + 4) + (-step if facing else step)) & 65535)


def put_frames(machine, flags):
    machine.cpu.mem_write(machine.A5 - 0x3472, struct.pack('>I', FRAM_HANDLE))
    machine.cpu.mem_write(FRAM_HANDLE, struct.pack('>I', FRAM_BASE))
    table = bytearray(10 * len(flags))
    for pose, value in enumerate(flags):
        struct.pack_into('>H', table, pose * 10 + 8, value)
    machine.cpu.mem_write(FRAM_BASE, bytes(table))


def native_facing(port):
    return 0 if port else -1


def random_case(draw):
    copy_facing = draw.choice((0, 1))
    x = draw.randrange(20, 490)
    copy = SimpleNamespace(
        alive=draw.random() < 0.9, room=COPY_ROOM, row=draw.randrange(3),
        state=SimpleNamespace(action=draw.choice((15, 15, 15, 171, 52, 109, 7, 203)),
                              selected_sequence_id=draw.choice((2, 75, 240, 196, 92)),
                              facing=copy_facing, target_x=x))
    distance = draw.choice((draw.randrange(-120, 120), draw.randrange(-100, 100)))
    prince = PrinceView(
        alive=draw.choice((-1, -1, -1, 0, 1, 5)),
        selected_sequence=draw.choice((2, 1, 44, 6, 55, 47)),
        actor_type=draw.choice((0, 0, 0, 1)),
        action=draw.choice((15, 145, 109, 150, 191, 205, 206, 1, 7)),
        animation_state=draw.choice((0, 0, 1, 3, 4)),
        facing=draw.choice((0, 1)), room=draw.choice((COPY_ROOM, COPY_ROOM, 4)),
        row=draw.choice((copy.row, copy.row, draw.randrange(3))), x=x + distance)
    if draw.random() < 0.4:
        # A strike candidate: the windows' edges, both facings, a landing.
        copy.alive, copy.state.action = True, 15
        prince = PrinceView(-1, 2, 0, draw.choice((191, 205, 145, 145, 15)), 0,
                            draw.choice((0, 1)), COPY_ROOM, copy.row,
                            x + draw.randrange(-100, 101))
    return copy, prince, draw.randrange(0, 5), draw.choice((1, 2, 3))


def expected_calls(copy, prince, count, frames):
    decision = copy_control(copy, prince, count, frames)
    calls = []
    if decision.x_offset:
        calls.append(('add_x', decision.x_offset))
    if decision.sequence is not None:
        calls.append(('select', decision.sequence))
    if decision.sound is not None:
        calls.append(('sound', decision.sound))
    return decision, calls


def run_probe(recovery, count=6000, seed=6):
    directory = Path(recovery) / 'resource_forks'
    executable = parse_resource_fork((directory / 'Prince of Persia 2.bin').read_bytes())
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2013]['data']
    if (len(level), struct.unpack_from('>H', level, 0x2186)[0]) != (18890, 6):
        raise ValueError('Unexpected preserved final-level header')
    machine = NativeCopies(executable)
    flags = frame_flags()
    frames = [SimpleNamespace(aux=value) for value in flags]
    draw = random.Random(seed)
    kinds = Counter()
    for _ in range(count):
        copy, prince, bank, life = random_case(draw)
        data = bytearray(level)
        struct.pack_into('>H', data, BANK, bank)
        machine.reset(data)
        put_frames(machine, flags)
        state = copy.state
        for offset, value in ((2, native_facing(state.facing)), (4, state.target_x + 207),
                              (0xa, state.action), (0xe, copy.row), (0x16, NATIVE_ROOM),
                              (0x1a, 5), (0x1c, -1 if copy.alive else 0),
                              (0x28, state.selected_sequence_id), (8, 6)):
            machine.put_word(CHAR + offset, value)
        for base in (OPP, SAVED):
            for offset, value in ((2, native_facing(prince.facing)), (4, prince.x + 207),
                                  (8, prince.actor_type), (0xa, prince.action),
                                  (0xe, prince.row), (0x10, prince.animation_state),
                                  (0x16, prince.room + 1), (0x1c, prince.alive),
                                  (0x1e, life), (0x28, prince.selected_sequence)):
                machine.put_word(base + offset, value)
        machine.call(9, 0x1526)
        decision, calls = expected_calls(copy, prince, bank, frames)
        facing = native_facing(1 - state.facing if decision.turn else state.facing)
        armed = {None: 5, True: 1, False: 0}[decision.sword_drawn]
        actual = (machine.calls, machine.word(CHAR + 2), machine.word(CHAR + 0x1a))
        wanted = (calls, facing, armed)
        if actual != wanted:
            raise AssertionError({'copy': copy, 'prince': prince, 'bank': bank,
                                  'native': actual, 'port': wanted})
        kinds.update(call[0] if call[0] != 'select' else f'select {call[1]}' for call in calls)
        kinds['turn'] += decision.turn
    return count, dict(kinds)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--recovery', default='../PoP2-Mac-Code-Recovery')
    parser.add_argument('--count', type=int, default=6000)
    args = parser.parse_args()
    compared, kinds = run_probe(args.recovery, args.count)
    print(f'{compared} original CODE 9:1526 cases agree; decisions {kinds}')
