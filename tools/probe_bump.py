"""Compare the Prince's bump into an opponent with the original CODE 2.

FrameAdv's bump 2:6c64-6daa and CharDistance 4:49ee and AddCharX 4:2bae
run in Unicorn over LEVL 2000, against `CombatEncounter.choose_player_bump`
called without a previous X (the port's one-frame sweep is a port
safeguard, not compared).

Supplied: SetCharFloor 4:31fa (records the call), JumpSeq 6:0006 (records
its SEQS) and 4:2c0c (the first frame of that SEQS: the port's
`next_frame` is stubbed the same way). Compared: whether he bumps, the SEQS
chosen (46, 47 or none for poses 246-261), the X after AddCharX, and the
vertical speed cleared. Excluded: the port-only gates (`controls_locked`,
`targetable`, an already running SEQS 46/47), the opponent copy's other
fields and the frame advance itself.
"""

import argparse
from collections import Counter
from pathlib import Path
import random
import struct
from types import SimpleNamespace

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules

CHAR, OPP = -0x5056, -0x5094
NATIVE_ORIGIN = 207


class NativeBump(NativeRules):
    RANGES = {
        2: ((0x6c64, 0x6dae),),
        4: ((0x49ee, 0x4a44), (0x2bae, 0x2bcc)),
    }
    SUPPLIED = {(4, 0x31fa): 'floor', (6, 0x0006): 'jump', (4, 0x2c0c): 'frame'}

    def __init__(self, program):
        super().__init__(program)
        self.sequences = []

    def dispatch(self, cpu, address, size, user):
        segment, offset = divmod(address - self.CODE_BASE, 0x10000)
        if self.SUPPLIED.get((segment, offset)) == 'jump':
            stack = cpu.reg_read(self.registers['a7'])
            self.sequences.append(struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0])
        super().dispatch(cpu, address, size, user)


def port_bump(case):
    from pop2 import combat

    chosen = []

    def select(fighter, sequence, offset=0):
        chosen.append(sequence)
        fighter.state.sequence_id = sequence
        fighter.state.action = 102 if sequence == 46 else 50

    state = SimpleNamespace(facing=case['facing'], target_x=case['x'], current_x=case['x'],
                            current_y=-30, actor_type=case['type'], action=case['pose'],
                            sequence_id=case['seqs'], vertical_velocity=case['vy'],
                            horizontal_velocity=3, animation_state=1)
    player = SimpleNamespace(state=state, alive=case['alive'], sword_drawn=case['armed'] == 1,
                             targetable=True, controls_locked=False, room=case['room'],
                             row=case['row'], runtime=SimpleNamespace(next_frame=lambda: None))
    opp = case['opp']
    guard = SimpleNamespace(
        state=SimpleNamespace(facing=opp['facing'], target_x=opp['x'], actor_type=opp['type'],
                              action=opp['pose'], animation_state=opp['anim']),
        alive=opp['life'] != 0, alert_mode=opp['alert'], selected_sequence=opp['seqs'],
        room=opp['room'], row=opp['row'])
    host = SimpleNamespace(player=player, guard=guard, _project_fighter=lambda fighter, room: fighter)
    original = combat.select_sequence
    combat.select_sequence = select
    try:
        bumped = combat.CombatEncounter.choose_player_bump(host)
    finally:
        combat.select_sequence = original
    return (bumped, chosen[0] if chosen else None, state.target_x,
            state.vertical_velocity if bumped else case['vy'])


def native_facing(port):
    return 0 if port else -1


def random_case(draw):
    case = broad_case(draw)
    if draw.random() < 0.6:
        # Close to a bump: opposed, in reach, engaged, on the ground.
        case.update(armed=0, alive=True, vy=draw.choice((0, 0, 58, 59)))
        case['opp'].update(facing=1 - case['facing'], alert=draw.choice((2, 3)),
                           anim=draw.choice((0, 1, 1, 2)), life=3, room=5, row=1,
                           x=case['x'] + (1 if case['facing'] else -1) * draw.randrange(-25, 50))
    return case


def broad_case(draw):
    x = draw.randrange(40, 470)
    near = draw.random() < 0.8
    return {
        'facing': draw.choice((0, 1)), 'x': x,
        'type': draw.choice((0, 0, 0, 1)),
        'pose': draw.choice((15, 24, 25, 40, 41, 42, 43, 44, 102, 104, 106, 107, 246, 250, 261,
                             262, 8, 34, 35)),
        'seqs': draw.choice((1, 3, 4, 4, 4, 3, 7, 17)),
        'vy': draw.choice((0, 0, 20, 49, 50, 58, 59, 60)),
        'armed': draw.choice((0, 0, 0, 1, -1)),
        'alive': draw.random() < 0.9,
        'room': 5, 'row': 1,
        'opp': {
            'facing': draw.choice((0, 1)),
            'x': x + (draw.randrange(-90, 91) if near else draw.randrange(-300, 301)),
            'type': draw.choice((2, 2, 4, 6, 7, 8, 10, 11, 12, 0)),
            'pose': draw.choice((15, 150, 158, 171, 178, 179, 200, 235, 236, 205, 206, 207)),
            'anim': draw.choice((0, 1, 1, 1, 2, 5)),
            'seqs': draw.choice((58, 110, 105, 2, 64)),
            'alert': draw.choice((0, 1, 2, 3, 3)),
            'life': draw.choice((0, 1, 3, 3)),
            'room': 5 if draw.random() < 0.9 else 6,
            'row': 1 if draw.random() < 0.9 else 2,
        },
    }


def run_probe(recovery, count=8000, seed=11):
    directory = Path(recovery) / 'resource_forks'
    executable = parse_resource_fork((directory / 'Prince of Persia 2.bin').read_bytes())
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2000]['data']
    machine = NativeBump(executable)
    draw = random.Random(seed)
    outcomes = Counter()
    for _ in range(count):
        case = random_case(draw)
        opp = case['opp']
        machine.reset(level)
        machine.sequences.clear()
        for offset, value in ((2, native_facing(case['facing'])), (4, case['x'] + NATIVE_ORIGIN),
                              (8, case['type']), (0xa, case['pose']), (0xe, case['row']),
                              (0x14, case['vy']), (0x16, case['room']), (0x1a, case['armed']),
                              (0x1c, -1 if case['alive'] else 0), (0x28, case['seqs'])):
            machine.put_word(CHAR + offset, value)
        for offset, value in ((2, native_facing(opp['facing'])), (4, opp['x'] + NATIVE_ORIGIN),
                              (8, opp['type']), (0xa, opp['pose']), (0xe, opp['row']),
                              (0x10, opp['anim']), (0x16, opp['room']), (0x1e, opp['life']),
                              (0x28, opp['seqs']), (0x32, opp['alert'])):
            machine.put_word(OPP + offset, value)
        machine.call(2, 0x6c64)
        bumped = machine.services['floor'] > 0
        native = (bumped, machine.sequences[0] if machine.sequences else None,
                  machine.word(CHAR + 4) - NATIVE_ORIGIN, machine.word(CHAR + 0x14))
        wanted = port_bump(case)
        if native != wanted:
            raise AssertionError(('2:6c64', case, native, wanted))
        outcomes['bump' if bumped else 'none'] += 1
        if bumped:
            outcomes[f'SEQS {native[1]}'] += 1
        elif opp['type'] in (6, 7, 8, 11) and case['facing'] != opp['facing']:
            outcomes['excluded type'] += 1
    return count, dict(outcomes)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--recovery', default='../PoP2-Mac-Code-Recovery')
    parser.add_argument('--count', type=int, default=8000)
    args = parser.parse_args()
    print(f'Original bump cases agree: {run_probe(args.recovery, args.count)}')
