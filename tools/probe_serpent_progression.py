"""Compare repeated native serpent control/frame/animation/movement steps.

Actual levels6-9 spawn records seed prepared working actors. The initializer,
cached idle Prince and constant alert0/3 are supplied, not executed. Each
frame runs4:2a72,7:1824,4:2c0c,4:341a and4:3464 against the runtime.
Resource handles, memory traps, seeded RNG and draw/audio services use the
explicit NativeRuinsAnimation harness boundaries. No LOS, damage resolution,
room-bank persistence/Cut, reachable path or complete FrameAdv claim.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
from types import SimpleNamespace

from pop2.animation_data import sequence_words
from pop2.combat import Fighter
from pop2.mac_resources import parse_resource_fork
from pop2.ruins_actors import initial_state, ruins_spawns
from pop2.ruins_ai import PrinceView, RuinsCreatures, RuinsMind
from pop2.sequence_runtime import SequenceRuntime, SequenceState
from pop2.terrain import LevelMap, floor_y
from tools.probe_ruins_runtime import (
    ANIMATED, PRINCE, WORKING, Draws, NativeRuinsAnimation, TapeRandom,
)


def run_probe(source):
    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(executable)
    prince = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())
    head = parse_resource_fork((forks / 'Head.rsrc.bin').read_bytes())
    sequences = {key: sequence_words(item['data']) for key, item in prince['SEQS'].items()}
    machine = NativeRuinsAnimation(program, head, prince['SEQS'])
    counts, mismatches, digest = Counter(), [], hashlib.sha256()
    for number in (6, 7, 8, 9):
        level = prince['LEVL'][1999 + number]['data']
        maximum = struct.unpack_from('>H', level, 0x2180)[0]
        for room in range(maximum):
            for spawn in ruins_spawns(level, room):
                if spawn.actor_type != 11:
                    continue
                counts['spawn_records'] += 1
                for distance, alert in ((-85, 3), (85, 3), (-150, 0), (150, 0)):
                    start, row = initial_state(spawn), spawn.row
                    initial = dict(slot=spawn.slot, facing=-1, x=spawn.native_x,
                        y=floor_y(row), actor=11, pose=230, column=0, row=row,
                        horizontal_velocity=0, vertical_velocity=0, room=room + 1,
                        armed=1, alive=-1, life=3, sequence=start.sequence_id, cursor=0,
                        selected=start.sequence_id, body_top=18, body_bottom=48,
                        special=start.special, alert=alert)
                    machine.reset(level)
                    machine.put_word(-0x4fc2, room + 1)
                    machine.cpu.mem_write(machine.A5 - 0x5056, bytes(62))
                    for name, value in initial.items():
                        machine.put_word(WORKING[name], value)
                    x = max(267, min(647, spawn.native_x + distance))
                    view = PrinceView((x - 229) // 51, row, x, floor_y(row), 0, 15,
                                      room, -1, 3, False, 2)
                    cached = dict(facing=0, x=x, y=floor_y(row), actor=0, pose=15,
                                  column=view.column, row=row, room=room + 1, armed=0,
                                  alive=-1, life=3, selected=2, target=-1)
                    raw = bytearray(62)
                    for name, value in cached.items():
                        struct.pack_into('>h', raw, PRINCE[name], value)
                    machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(raw))
                    machine.random, draws = Draws(707), Draws(707)
                    state = SequenceState(start.sequence_id, action=230,
                        target_x=spawn.native_x - 207, current_x=spawn.native_x - 207,
                        facing=0, actor_type=11, level_kind=4, sequence_mode=start.special)
                    runtime = SequenceRuntime(sequences, state)
                    runtime.rng = TapeRandom(draws)
                    actor = Fighter(runtime, 3, 3, room, row, sword_drawn=True)
                    actor.ruins = RuinsMind(11, 8, spawn.skill, spawn.slot,
                                            mode=start.mode, alert=alert)
                    creatures = RuinsCreatures()
                    creatures.rooms[room] = [actor]
                    creatures.prince = lambda encounter: view
                    encounter = SimpleNamespace(rng=TapeRandom(draws), terrain=LevelMap(level),
                                                player=SimpleNamespace(room=room), parry_timer=0)
                    machine.call(4, 0x2c0c)
                    runtime.next_frame()
                    record_offset = 0x20e6 + (room + 1) * 0xc0 + 2 + spawn.slot * 38
                    counts['traces'] += 1
                    for frame in range(180):
                        # LoadFrame alone omits the caller's supporting-column
                        # refresh. Real2:6512 calls4:2a72, not4:2a8e.
                        for segment, offset in ((4, 0x2a72), (7, 0x1824), (4, 0x2c0c),
                                                 (4, 0x341a), (4, 0x3464)):
                            machine.call(segment, offset)
                        creatures.control_serpent(actor, encounter)
                        runtime.next_frame()
                        creatures._after_frame(actor, encounter)
                        native = {name: machine.word(WORKING[name]) for name in ANIMATED}
                        actual = dict(facing=0 if state.facing else -1,
                            x=state.target_x + 207, y=floor_y(actor.row) + state.current_y,
                            row=actor.row, pose=state.action,
                            horizontal_velocity=state.horizontal_velocity,
                            vertical_velocity=state.vertical_velocity,
                            sequence=state.sequence_id, cursor=state.cursor,
                            selected=state.selected_sequence_id, special=state.sequence_mode)
                        difference = {name: (native[name], actual[name]) for name in ANIMATED
                                      if native[name] != actual[name]}
                        mode = struct.unpack_from('>h', machine.level_bytes(len(level)),
                                                  record_offset + 0x1c)[0]
                        if mode != actor.ruins.mode:
                            difference['mode'] = (mode, actor.ruins.mode)
                        if machine.sounds != state.sound_events:
                            difference['sounds'] = (machine.sounds, state.sound_events)
                        if machine.random.log != draws.log:
                            difference['random'] = (machine.random.log, draws.log)
                        if difference:
                            mismatches.append(dict(level=number, room=room + 1, slot=spawn.slot,
                                distance=distance, frame=frame, differences=difference))
                            break
                        counts['matching_frames'] += 1
                        digest.update(json.dumps((native, mode, machine.sounds,
                                                  machine.random.log)).encode('ascii'))
    return dict(counts=dict(counts), mismatches=mismatches,
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                outputs_sha256=digest.hexdigest(),
                supplied=['Cached Prince/alert/initial working actor',
                          'Actual SEQS handles; memory-manager traps inert',
                          'Seeded Rnd outcomes; AddSound recorded',
                          'ShapeBounds/DrawOppMeter/GetOppIdxClosestToKid harness services'],
                scope=__doc__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    if report['mismatches']:
        raise SystemExit(1)
