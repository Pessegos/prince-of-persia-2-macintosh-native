"""Compare level 14's turn rules with the original CODE 4 (native CPU).

Three original routines run in Unicorn over LEVL 2013 (environment 6,
level 14):

- 4:250a, the turn flash (with the division helper 19:4bd0), for every
  pose 0-399 and turn count 0-15 against `final_magic.turn_flash`;
- 4:2174, GenCtrl's per-frame turn count, against `count_turn_frame`;
  supplied: the palette restore 3:5f1c (recorded);
- 4:1fb2, the standing turn, with DecLifePts 4:34f2 and IsShadowImbued
  4:2590 run natively, against `Final.standing_turn` on a minimal scene.
  Supplied, recording their arguments: PoPSetPalette 3:508a, SetSeq 6:0006,
  the death method 4:3196, LeaveBody 4:2206, AddSound 5:4d84 and AddSong
  5:4d58. The port's own kill and body-leaving are recorded, not run. The
  room gate 6:116c (no count in native rooms 1/2) is outside 4:1fb2 and is
  excluded, and so is the port's same-frame order (`fresh_turn`).

Where 4:2174 leaves the draw mode alone (standing), the port also clears
its flash flag; that presentation choice is not compared.
"""

import argparse
from collections import Counter
from itertools import product
from pathlib import Path
import struct
from types import SimpleNamespace

from pop2.final_magic import FinalMagic, count_turn_frame, turn_flash
from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules

CHAR = -0x5056
TURNS, DRAW_MODE = -0x5004, -0x5020
TYPE, POSE, ROOM, LIFE, MAX_LIFE, PENDING, SELECTED, MODE = (
    CHAR + 8, CHAR + 0xa, CHAR + 0x16, CHAR + 0x1e, CHAR + 0x20, CHAR + 0x22,
    CHAR + 0x28, CHAR + 0x34)


class NativeMagic(NativeRules):
    RANGES = {
        **NativeRules.RANGES,
        4: (*NativeRules.RANGES[4], (0x1fb2, 0x20b0), (0x2174, 0x2206), (0x250a, 0x25bc),
            (0x34f2, 0x3598)),
        19: ((0x4bd0, 0x4cc0),),
    }
    SUPPLIED = {
        (3, 0x5f1c): 'restore_palette', (3, 0x508a): 'palette', (6, 0x0006): 'select',
        (4, 0x3196): 'death', (4, 0x2206): 'leave_body', (5, 0x4d84): 'sound',
        (5, 0x4d58): 'song',
    }
    ARGUMENTS = {'restore_palette': 1, 'palette': 2, 'select': 1, 'death': 1, 'sound': 1, 'song': 1}

    def reset(self, level):
        super().reset(level)
        self.calls = []

    def dispatch(self, cpu, address, size, user):
        segment, offset = divmod(address - self.CODE_BASE, 0x10000)
        service = self.SUPPLIED.get((segment, offset))
        if service is not None:
            count = self.ARGUMENTS.get(service, 0)
            stack = cpu.reg_read(self.registers['a7'])
            self.calls.append((service, *struct.unpack(f'>{count}h', cpu.mem_read(stack + 4, 2 * count))))
        super().dispatch(cpu, address, size, user)


def probe_flash(machine, level):
    compared = 0
    for pose, turns in product(range(400), range(16)):
        machine.reset(level)
        value = machine.call(4, 0x250a, (pose, turns))
        if bool(value) != turn_flash(pose, turns):
            raise AssertionError(('4:250a', pose, turns, value))
        compared += 1
    return compared


def probe_turn_count(machine, level):
    compared = 0
    for pose, selected, turns, room in product(
            (15, 14, 44, 45, 46, 48, 50, 51, 52, 53, 109, 179), (5, 2, 1, 71),
            range(10), (1, 2, 3, 7, 8)):
        machine.reset(level)
        for offset, value in ((POSE, pose), (SELECTED, selected), (TURNS, turns),
                              (ROOM, room), (DRAW_MODE, 7)):
            machine.put_word(offset, value)
        machine.call(4, 0x2174)
        magic = FinalMagic(turns=turns, flash=None)
        count_turn_frame(magic, pose, selected, room - 1)
        mode = machine.word(DRAW_MODE)
        native_flash = {0x30: True, 0: False, 7: None}[mode]
        restored = machine.calls == [('restore_palette', 6)]
        port_flash = magic.flash
        if machine.calls and not restored:
            raise AssertionError(('4:2174 calls', machine.calls))
        # The restore runs where the port clears the flag outside standing.
        if (machine.word(TURNS) != magic.turns
                or native_flash is not None and native_flash != port_flash
                or restored != (pose != 15 and port_flash is False and native_flash is None)):
            raise AssertionError(('4:2174', pose, selected, turns, room,
                                  machine.word(TURNS), mode, machine.calls, magic))
        compared += 1
    return compared


class Scene:
    """What Final.standing_turn reads and writes."""

    def __init__(self, life, capacity, shadow, selected, mode, turns):
        self.room_id = 6
        self.god_mode = False
        self.game = SimpleNamespace(caverns=SimpleNamespace(
            final_magic=FinalMagic(turns=turns, shadow=shadow, palette=-1)))
        self.sequence_state = SimpleNamespace(selected_sequence_id=selected, sequence_mode=mode,
                                              sound_events=[])
        self.combat = SimpleNamespace(player=SimpleNamespace(life=life, max_life=capacity))


def port_turn(life, capacity, shadow, selected, mode, turns):
    from pop2.environments import Final

    scene = Scene(life, capacity, shadow, selected, mode, turns)
    final = Final(scene)
    outcome = []

    def kill():
        # Final.kill_prince: life 0, SEQS 71, death method 17.
        outcome.append('kill')
        scene.combat.player.life = 0

    final.kill_prince = kill
    final.leave_body = lambda: outcome.append('leave')
    replaced = final.standing_turn()
    magic = scene.game.caverns.final_magic
    return SimpleNamespace(replaced=replaced, outcome=outcome, turns=magic.turns,
                           palette=magic.palette, sounds=scene.sequence_state.sound_events,
                           life=scene.combat.player.life, capacity=scene.combat.player.max_life)


def probe_standing_turn(machine, level):
    compared, outcomes = 0, Counter()
    for life, capacity, shadow, selected, mode, turns in product(
            range(1, 9), (8, 12), (False, True), (5, 2), (0, 13), range(9)):
        if life > capacity:
            continue
        machine.reset(level)
        for offset, value in ((TYPE, int(shadow)), (SELECTED, selected), (TURNS, turns),
                              (LIFE, life), (MAX_LIFE, capacity), (PENDING, 0), (MODE, mode),
                              (ROOM, 7)):
            machine.put_word(offset, value)
        machine.call(4, 0x1fb2)
        port = port_turn(life, capacity, shadow, selected, mode, turns)
        calls = machine.calls
        palettes = [call[1] for call in calls if call[0] == 'palette']
        native = SimpleNamespace(
            turns=machine.word(TURNS),
            killed=('death', 17) in calls or ('select', 71) in calls,
            left=('leave_body',) in calls,
            sound=('sound', 288) in calls,
            life=machine.word(LIFE) + machine.word(PENDING),
            capacity=machine.word(MAX_LIFE))
        wanted = SimpleNamespace(
            turns=port.turns, killed='kill' in port.outcome, left='leave' in port.outcome,
            sound=288 in port.sounds, life=port.life, capacity=port.capacity)
        if native.left and (machine.word(TYPE) != 1 or ('select', 2) not in calls
                            or ('sound', 260) not in calls or ('song', 290) not in calls):
            raise AssertionError(('4:2052-2076', calls))
        if (vars(native) != vars(wanted)
                or palettes != ([port.palette] if port.palette != -1 else [])):
            raise AssertionError(('4:1fb2', life, capacity, shadow, selected, mode, turns,
                                  vars(native), vars(wanted), palettes, port.palette, calls))
        outcomes['kill' if native.killed else 'leave' if native.left else
                 'flash' if palettes else 'count'] += 1
        compared += 1
    return compared, dict(outcomes)


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = parse_resource_fork((directory / 'Prince of Persia 2.bin').read_bytes())
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2013]['data']
    if struct.unpack_from('>HHH', level, 0x2186) != (6, 5, 14):
        raise ValueError('Unexpected preserved final-level header')
    machine = NativeMagic(executable)
    flash = probe_flash(machine, level)
    count = probe_turn_count(machine, level)
    turns, outcomes = probe_standing_turn(machine, level)
    return {'4:250a': flash, '4:2174': count, '4:1fb2': turns, 'outcomes': outcomes}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--recovery', default='../PoP2-Mac-Code-Recovery')
    args = parser.parse_args()
    print(f'Original level-14 turn rules agree: {run_probe(args.recovery)}')
