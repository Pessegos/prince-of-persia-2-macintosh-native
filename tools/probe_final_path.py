"""Compare CODE 9:16fe (the final Jaffar's palace controller) with the port.

The original CODE 9 path controller runs in Unicorn with all of its own
callees: the decision 16fe-1858, close in 0a42, flee 0b28, face-and-cast
09ca, the range test 0ba6, the position steps 0cac/0cec, the routes 0d28
(0ed2, 107c, 11fe, 136e), HoneIn 0dac, the kill 14c8, ShadowInRange 1954
and CharDistance 4:49ee. The DATA tables (positions a5-0x2a06, column X
a5-0x4b88, facing signs a5-0x4b98) are the original's, expanded from CODE 0.

Supplied endpoints, each recording its word arguments: the opponent record
lookup 6:3642 (returns a record holding the case's +0x1c/+0x1e/+0x20),
SetSeq 6:0006, AddSound 5:4d84, AddSong 5:4d58, the record swaps 4:4a46,
4:4b02, 4:4ac0 and 4:335a, DecLifePts 4:34f2, the death method 4:3196, the
Kid routines 6:11a0, 6:15ea, 6:1600, 6:1998, 6:1a84, 6:1c14, 6:0e8e and
6:1276, and AddCharX 4:2bae (returns the record's X unchanged). Their own
effects are excluded. The FRAM flag table is synthetic and is given to both
sides; it is not the original's.
"""

import argparse
from collections import Counter
from dataclasses import replace
from pathlib import Path
import random
import struct

from pop2.final_path import Controller, Figure, PathInfo
from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules

CHAR, OPP = -0x5056, -0x5094
INFO, FRAM_HANDLE, FRAM_BASE = 0xd0000, 0xc0000, 0xc0010
# Record offsets (CODE 9 reads: -0x5054 facing, -0x5052 X, -0x504e type,
# -0x504c pose, -0x504a column, -0x5048 row, -0x5040 room, -0x503c armed,
# -0x503a ALIVE, -0x5038 life, -0x502e selected SEQS, -0x5022 mode).
FIELDS = {'facing': 2, 'x': 4, 'actor_type': 8, 'pose': 0xa, 'column': 0xc, 'row': 0xe,
          'room': 0x16, 'armed': 0x1a, 'life': 0x1e, 'selected': 0x28, 'mode': 0x34}
KID_ROUTINES = {
    (6, 0x11a0): 'forward', (6, 0x15ea): 'stand_jump', (6, 0x1600): 'jump_up',
    (6, 0x1998): 'climb', (6, 0x1a84): 'release', (6, 0x1c14): 'run_jump',
    (6, 0x0e8e): 'descend', (6, 0x1276): 'step', (4, 0x2bae): 'add_x',
}
ONE_ARGUMENT = {'select', 'run_jump', 'step', 'add_x', 'sound', 'song', 'life', 'death'}


class NativePath(NativeRules):
    RANGES = {
        **NativeRules.RANGES,
        4: (*NativeRules.RANGES[4], (0x49ee, 0x4a46)),
        9: ((0x09ca, 0x1526), (0x16fe, 0x1a00)),
    }
    SUPPLIED = {
        (6, 0x3642): 'record', (6, 0x0006): 'select', (5, 0x4d84): 'sound',
        (5, 0x4d58): 'song', (4, 0x4a46): 'save_char', (4, 0x4b02): 'load_opp',
        (4, 0x4ac0): 'restore_char', (4, 0x335a): 'restore_kid', (4, 0x34f2): 'life',
        (4, 0x3196): 'death', **KID_ROUTINES,
    }

    def reset(self, level):
        super().reset(level)
        self.calls = []

    def dispatch(self, cpu, address, size, user):
        segment, offset = divmod(address - self.CODE_BASE, 0x10000)
        service = self.SUPPLIED.get((segment, offset))
        if service is not None:
            stack = cpu.reg_read(self.registers['a7'])
            if service in ONE_ARGUMENT:
                argument = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
                self.calls.append((service, argument))
            elif service != 'record':
                self.calls.append((service,))
        super().dispatch(cpu, address, size, user)
        if service == 'record':
            cpu.reg_write(self.registers['d0'], INFO)
        elif service == 'add_x':
            cpu.reg_write(self.registers['d0'], self.word(CHAR + FIELDS['x']) & 65535)

    def put_record(self, base, figure):
        for name, offset in FIELDS.items():
            self.put_word(base + offset, getattr(figure, name))

    def put_frames(self, flags):
        self.cpu.mem_write(self.A5 - 0x3472, struct.pack('>I', FRAM_HANDLE))
        self.cpu.mem_write(FRAM_HANDLE, struct.pack('>I', FRAM_BASE))
        table = bytearray(10 * len(flags))
        for pose, value in enumerate(flags):
            struct.pack_into('>H', table, pose * 10 + 8, value)
        self.cpu.mem_write(FRAM_BASE, bytes(table))


class Recorder:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def call(*args):
            self.calls.append((name, *args))
        return call


def frame_flags(seed=14):
    """A synthetic FRAM +8 table: about half the poses carry flag 0x40."""
    draw = random.Random(seed)
    return [0x40 if draw.random() < 0.5 else draw.choice((0, 0x80, 0x20)) for _ in range(400)]


def expected_calls(jaffar, prince, info, flags):
    frames = [type('Frame', (), {'aux': value})() for value in flags]
    kid = Recorder()
    events = Controller(jaffar, prince, info, frames, kid).run()
    calls = []
    for event in events:
        if event[0] == 'dissolve':
            calls += [('save_char',), ('load_opp',), ('select', event[1]), ('song', event[2]),
                      ('restore_char',)]
        elif event[0] == 'sound':
            calls.append(('sound', event[1]))
    for call in kid.calls:
        calls.append(call if call[0] != 'run_jump' else ('run_jump', 4))
    if any(event[0] == 'kill' for event in events):
        calls += [('save_char',), ('load_opp',), ('select', 71), ('sound', 12), ('life', 100),
                  ('death', 17), ('restore_kid',)]
    hits = sum(event[0] == 'hit' for event in events)
    return calls, hits


JAFFAR_POSES = (15, 1, 7, 11, 14, 49, 56, 87, 89, 91, 109, 135, 158, 190, 191, 205, 207, 210,
                272, 280, 281, 282, 300)
SELECTED = (2, 1, 4, 5, 13, 17, 49, 230, 241, 242, 244)


def random_case(draw):
    room = draw.choice((7, 8))
    jaffar = Figure(pose=draw.choice(JAFFAR_POSES), selected=draw.choice(SELECTED),
                    facing=draw.choice((0, -1)), x=draw.randrange(150, 760),
                    column=draw.randrange(-1, 11), row=draw.randrange(3), room=room,
                    life=draw.randrange(1, 4), armed=0, actor_type=6,
                    mode=draw.choice((0, 0, 12)))
    prince = Figure(pose=draw.choice((15, 1, 7, 109, 150, 191, 341)),
                    selected=draw.choice(SELECTED), facing=draw.choice((0, -1)),
                    x=draw.randrange(150, 760), column=draw.randrange(-1, 11),
                    row=draw.choice((jaffar.row, jaffar.row, draw.randrange(3))),
                    room=draw.choice((room, room, 7, 8, 6)), life=draw.randrange(0, 6),
                    armed=draw.choice((-1, 0, 1)), actor_type=draw.choice((0, 0, 0, 1)),
                    mode=0, turns=draw.randrange(0, 9))
    info = PathInfo(draw.choice((0, 1, 2)), draw.randrange(4), draw.randrange(4))
    bias = draw.random()
    if bias < 0.4:
        # Closing in on a Prince without a sword: the routes and the cast.
        prince = replace(prince, armed=-1, actor_type=0, turns=draw.randrange(4),
                         life=draw.randrange(1, 6), selected=draw.choice((2, 1, 5, 13)))
        jaffar = replace(jaffar, selected=draw.choice((2, 1, 5, 13, 4)),
                         pose=draw.choice((15, 15, 15, 7, 11, 91, 109, 87, 1, 49)))
        info = replace(info, mode=2)
    elif bias < 0.55:
        jaffar = replace(jaffar, selected=242, pose=draw.choice((281, 282, 282, 276)))
        prince = replace(prince, armed=-1, actor_type=0, turns=0, row=jaffar.row,
                         life=draw.randrange(0, 4), room=draw.choice((7, 8)))
        info = replace(info, mode=2)
    elif bias < 0.7:
        # Fleeing from a strong Prince or shadow.
        prince = replace(prince, row=jaffar.row, turns=draw.randrange(4, 9),
                         life=draw.randrange(1, 6))
    return jaffar, prince, info


def run_probe(recovery, count=6000, seed=1):
    directory = Path(recovery) / 'resource_forks'
    executable = parse_resource_fork((directory / 'Prince of Persia 2.bin').read_bytes())
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2013]['data']
    if (len(level), struct.unpack_from('>H', level, 0x2186)[0]) != (18890, 6):
        raise ValueError('Unexpected preserved final-level header')
    machine = NativePath(executable)
    flags = frame_flags()
    draw = random.Random(seed)
    totals = {'cases': 0, 'with_calls': 0, 'kills': 0, 'dissolves': 0, 'flee': 0, 'close': 0}
    kinds = Counter()
    for _ in range(count):
        jaffar, prince, info = random_case(draw)
        machine.reset(level)
        machine.put_frames(flags)
        machine.put_record(CHAR, jaffar)
        machine.put_record(OPP, prince)
        machine.put_word(CHAR, 1)
        machine.put_word(-0x5004, prince.turns)
        machine.put_word(-0x4f92, 0)
        for offset, value in zip((0x1c, 0x1e, 0x20), (info.mode, info.pos, info.prev)):
            machine.cpu.mem_write(INFO + offset, struct.pack('>H', value))
        machine.call(9, 0x16fe)
        native_info = struct.unpack('>3h', machine.cpu.mem_read(INFO + 0x1c, 6))
        port_info = PathInfo(info.mode, info.pos, info.prev)
        calls, hits = expected_calls(jaffar, prince, port_info, flags)
        actual = (machine.calls, native_info, machine.word(-0x4f92))
        wanted = (calls, (port_info.mode, port_info.pos, port_info.prev), hits)
        if actual != wanted:
            raise AssertionError({'jaffar': jaffar, 'prince': prince, 'info': info,
                                  'native': actual, 'port': wanted})
        totals['cases'] += 1
        kinds.update(call[0] for call in calls)
        totals['with_calls'] += bool(calls)
        totals['kills'] += ('death', 17) in calls
        totals['dissolves'] += ('song', 264) in calls
        totals['flee'] += native_info[0] == 1 and info.mode != 1
        totals['close'] += native_info[0] == 2 and info.mode != 2
    return totals, dict(kinds)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--recovery', default='../PoP2-Mac-Code-Recovery')
    parser.add_argument('--count', type=int, default=6000)
    args = parser.parse_args()
    totals, kinds = run_probe(args.recovery, args.count)
    print(f"{totals['cases']} original CODE 9:16fe cases agree ({totals}); calls {kinds}")
