"""Compare level 14's magic fire with the original CODE 9 (native CPU).

The original routines run in Unicorn over LEVL 2013 (environment 6, level
14), with GetRow 4:3afa run natively:

- 9:2880, the throw at pose 281, with its wall test 9:25e4, against
  `final_magic.throw_fireball` and `fire_hits_wall`;
- 9:27a0, one frame of flight or burst, with 9:25e4 and the end of the
  fire (a weak Prince's CTBL 2000 at 9:2838-2850), against
  `final_magic.advance_fireball` and `Final.advance_fireball`'s palette.

Supplied, recording their word arguments: AddCharX 4:2bae (X + 43 along
the facing), ReadCell 4:27ee and IsWall 3:4ef2 (a synthetic wall map given
to both sides), AddSound 5:4d84, PrinceResetSnd 5:5252, PoPSetPalette
3:508a and the object list's AddObject 5:2914. Excluded: the drawing and
side-room transfer 9:23a8 (the port moves the fire when it leaves a room,
the original when it enters the view room), the fire's Y and drawing
width source (the probe gives 9:25e4 the width the port reads), and the
collision 9:24ee.
"""

import argparse
from collections import Counter
from pathlib import Path
import random
import struct
from types import SimpleNamespace

from pop2 import final_magic
from pop2.final_magic import Fireball, advance_fireball, fire_hits_wall, throw_fireball
from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules

CHAR = -0x5056
FACING, X, Y, ROOM = CHAR + 2, CHAR + 4, CHAR + 6, CHAR + 0x16
SAVED_LIFE = -0x50d2 + 0x1e
FIRE_X, FIRE_Y, FIRE_ROOM, FIRE_ENDED, FIRE_SPEED, FIRE_ROW, FIRE_STATE = (
    -0x44a6, -0x44a4, -0x44a2, -0x44a0, -0x449e, -0x449a, -0x4498)
FIRE_WIDTH = -0x44e4
NATIVE_ORIGIN = 207


def is_wall(room, column, row):
    """A synthetic wall map (native room numbers), the same for both sides."""
    return (room * 7 + column * 3 + row * 5) % 4 == 0 or column in (-3, 13)


class NativeFire(NativeRules):
    RANGES = {
        **NativeRules.RANGES,
        4: (*NativeRules.RANGES[4], (0x3afa, 0x3b26)),
        9: ((0x25e4, 0x2674), (0x27a0, 0x28f0)),
    }
    SUPPLIED = {
        (4, 0x2bae): 'add_x', (4, 0x27ee): 'cell', (3, 0x4ef2): 'is_wall',
        (5, 0x4d84): 'sound', (5, 0x5252): 'reset', (3, 0x508a): 'palette',
        (5, 0x2914): 'add_object',
    }
    ARGUMENTS = {'add_x': 1, 'cell': 3, 'is_wall': 1, 'sound': 1, 'reset': 1, 'palette': 2}

    def reset(self, level):
        super().reset(level)
        self.calls = []

    def dispatch(self, cpu, address, size, user):
        segment, offset = divmod(address - self.CODE_BASE, 0x10000)
        service = self.SUPPLIED.get((segment, offset))
        if service is not None:
            count = self.ARGUMENTS.get(service, 0)
            stack = cpu.reg_read(self.registers['a7'])
            arguments = struct.unpack(f'>{count}h', cpu.mem_read(stack + 4, 2 * count))
            self.calls.append((service, *arguments))
        super().dispatch(cpu, address, size, user)
        if service == 'add_x':
            step = arguments[0]
            value = self.word(X) + (-step if self.word(FACING) else step)
            cpu.reg_write(self.registers['d0'], value & 65535)
        elif service == 'cell':
            cpu.reg_write(self.registers['d0'], int(is_wall(*arguments)))
        elif service == 'is_wall':
            cpu.reg_write(self.registers['d0'], arguments[0] & 65535)


def port_wall(room, column, row):
    return is_wall(room + 1, column, row)


def native_state(ball):
    return ball.frame | (8 if ball.burst else 0)


def outward(calls, kinds):
    return [call for call in calls if call[0] in kinds]


def probe_throw(machine, level, draw, count):
    compared, walls = 0, 0
    for _ in range(count):
        facing = draw.choice((0, 1))
        x = draw.randrange(0, 520)
        row = draw.randrange(3)
        room = draw.randrange(1, 12)
        width = draw.choice((0, 18, 26, 34))
        machine.reset(level)
        for offset, value in ((FACING, 0 if facing else -1), (X, x + NATIVE_ORIGIN),
                              (Y, row * 120 + 112), (ROOM, room), (FIRE_WIDTH, width),
                              (FIRE_ENDED, -1), (FIRE_STATE, 9)):
            machine.put_word(offset, value)
        machine.call(9, 0x2880)
        state = SimpleNamespace(facing=facing, target_x=x, current_y=0)
        ball = throw_fireball(state, room - 1, row, 0)
        sounds, resets = [], []
        hit = fire_hits_wall(ball, port_wall, width, sounds, resets)
        walls += hit
        native = (machine.word(FIRE_X), machine.word(FIRE_SPEED), machine.word(FIRE_ROOM),
                  machine.word(FIRE_ROW), machine.word(FIRE_STATE), machine.word(FIRE_ENDED),
                  outward(machine.calls, ('sound', 'reset', 'add_object')))
        wanted = (ball.x, ball.speed, ball.room + 1, ball.row, native_state(ball), 0,
                  [('sound', s) for s in sounds] + [('reset', r) for r in resets]
                  + [('add_object',), ('sound', final_magic.FIREBALL_SOUND)])
        if native != wanted:
            raise AssertionError(('9:2880', facing, x, row, room, width, native, wanted))
        compared += 1
    return compared, walls


def probe_flight(machine, level, draw, count):
    compared, outcomes = 0, Counter()
    speeds = (12, 15, 18, 21, 24, 25, 26, 13, 1)
    for _ in range(count):
        speed = draw.choice(speeds) * draw.choice((1, -1))
        x = draw.randrange(-80, 600)
        row = draw.randrange(3)
        room = draw.choice((0, 0) + tuple(range(1, 12)) * 2)
        burst = draw.random() < 0.3
        frame = draw.randrange(4)
        width = draw.choice((0, 18, 26, 34))
        life = draw.choice((1, 2, 3, 6))
        ended = draw.random() < 0.05
        machine.reset(level)
        for offset, value in ((FIRE_X, x), (FIRE_SPEED, speed), (FIRE_ROOM, room),
                              (FIRE_ROW, row), (FIRE_STATE, frame | (8 if burst else 0)),
                              (FIRE_ENDED, -1 if ended else 0), (FIRE_WIDTH, width),
                              (SAVED_LIFE, life)):
            machine.put_word(offset, value)
        machine.call(9, 0x27a0)
        ball = Fireball(None if room == 0 else room - 1, x, 0, row, speed, frame=frame,
                        burst=burst, active=not ended)
        resets = []
        sounds, finished = advance_fireball(ball, port_wall, width, resets)
        palette = finished and life <= 2
        native_ended = machine.word(FIRE_ENDED) == -1
        native = [native_ended, machine.word(FIRE_X), machine.word(FIRE_SPEED),
                  outward(machine.calls, ('sound', 'reset', 'palette'))]
        wanted = [not ball.active, ball.x, ball.speed,
                  [('sound', s) for s in sounds if s != final_magic.FIREBALL_SOUND]
                  + [('reset', r) for r in resets]
                  + [('sound', s) for s in sounds if s == final_magic.FIREBALL_SOUND]
                  + ([('palette', final_magic.SHADOW_PALETTE, 0x30)] if palette else [])]
        if not native_ended:
            native.append(machine.word(FIRE_STATE))
            wanted.append(native_state(ball))
        if native != wanted:
            raise AssertionError(('9:27a0', speed, x, row, room, burst, frame, width, life,
                                  ended, native, wanted))
        outcomes['idle' if ended else 'gone' if room == 0 else 'burst end' if finished
                 else 'wall' if any(c[0] == 'reset' for c in machine.calls)
                 else 'burst' if burst else 'flight'] += 1
        compared += 1
    return compared, dict(outcomes)


def run_probe(recovery, count=4000, seed=14):
    directory = Path(recovery) / 'resource_forks'
    executable = parse_resource_fork((directory / 'Prince of Persia 2.bin').read_bytes())
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2013]['data']
    if struct.unpack_from('>HHH', level, 0x2186) != (6, 5, 14):
        raise ValueError('Unexpected preserved final-level header')
    machine = NativeFire(executable)
    draw = random.Random(seed)
    throws, walls = probe_throw(machine, level, draw, count // 4)
    flights, outcomes = probe_flight(machine, level, draw, count)
    return {'9:2880': throws, 'thrown into a wall': walls, '9:27a0': flights,
            'outcomes': outcomes}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--recovery', default='../PoP2-Mac-Code-Recovery')
    parser.add_argument('--count', type=int, default=4000)
    args = parser.parse_args()
    print(f'Original level-14 fire agrees: {run_probe(args.recovery, args.count)}')
