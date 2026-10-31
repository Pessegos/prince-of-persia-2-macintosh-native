"""Execute the original unarmed-runner control 4:057c against the port.

AutoCtrl's running branch 4:057c-07fc decides, for a running opponent in an
odd pose 195-199 or the last jump pose 212, whether it brakes (JumpSeq 101,
alert 0 or 2), lunges with the sword (87, exit-chasing skeletons) or runs
on; poses 192/196 of a jump-capable runner go to 4:0834 instead. The port is
`CombatEncounter._choose_unarmed_guard_action` with `_brake_guard`.

Native: 4:057c, GetCellsInFront 4:39fc, GetCellBehind 4:3a48, ReadCell
4:27ee (room links, GetUndefineCellId), GetFCharX/GetDist1/GetCharCol
4:3a72-3aea, IsExitChasingSkel 4:17aa, IsAdvancableId 6:5eca with IsWall/
IsImpassable/IsSpace, AddCharX 4:2bae and the column word 4:2a7c.
Supplied: GetOppIdxClosestToKid 6:36f2 returns the fixture's nearest
opponent (itself, none, or another slot whose X is in the bank table
a5-0x5204); GetOppInfoIdx 6:3642 returns a record whose +0x20 is the
alternate row; JumpSeq 6:0006 and the jump 4:0834 are recorded.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
from types import SimpleNamespace

from pop2.combat import CombatEncounter
from pop2.coordinates import NATIVE_X_ORIGIN
from pop2.mac_resources import parse_resource_fork
from pop2.sequence_runtime import SequenceState
from pop2.terrain import LevelMap
from tools.probe_prince_turn import (FACING, FRAME_DX, FRAME_FLAGS, KID_ROOM, POSE,
                                     ROOM, ROW, TYPE, X, NativePrinceTurn, gate_cells)

SELF, ALERT, FLAGS, ARMED = -0x5056, -0x5024, -0x501e, -0x503c
KID_X, KID_POSE, KID_ROW, KID_FACING, KID_COLUMN = -0x50ce, -0x50c8, -0x50c4, -0x50d0, -0x50c6
KID_ARMED, KID_ALIVE, KID_SPECIAL = -0x50b8, -0x50b6, -0x509e
# The second Kid copy read for the same-direction run (6:06e4-0716).
RUN_FACING, RUN_POSE, RUN_STATE = -0x5092, -0x508a, -0x5084
BANK_X = -0x5204
FRAMES = ((0, 0), (12, 0x45), (-7, 2), (20, 0x0b))


class NativeUnarmedBrake(NativePrinceTurn):
    RANGES = {**NativePrinceTurn.RANGES,
              3: NativePrinceTurn.RANGES[3] + ((0x4de2, 0x4e20),),
              4: NativePrinceTurn.RANGES[4] + ((0x057c, 0x07fc), (0x17aa, 0x17e2),
                                                (0x3a48, 0x3a70), (0x3a92, 0x3a9e),
                                                (0x3aa0, 0x3ac8)),
              6: ((0x5eca, 0x5f5c),)}
    SUPPLIED = {}
    RECORD = 0xc0000

    def dispatch(self, cpu, address, size, user):
        relative = divmod(address - self.CODE_BASE, 0x10000)
        stack = cpu.reg_read(self.registers['a7'])
        if relative in ((6, 0x36f2), (6, 0x3642), (4, 0x0834), (6, 0x0006)):
            if relative == (6, 0x36f2):
                self.services['nearest'] += 1
                value = self.nearest & 65535
            elif relative == (6, 0x3642):
                self.services['bank_record'] += 1
                record = bytearray(64)
                struct.pack_into('>h', record, 0x20, self.alternate_row)
                cpu.mem_write(self.RECORD, bytes(record))
                value = self.RECORD
            elif relative == (4, 0x0834):
                self.services['jump'] += 1
                self.jumped = True
                value = 0
            else:
                self.jumps.append(struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0])
                value = 0
            cpu.reg_write(self.registers['d0'], value)
            cpu.reg_write(self.registers['a7'], stack + 4)
            cpu.reg_write(self.registers['pc'], struct.unpack('>I', cpu.mem_read(stack, 4))[0])
            return
        super().dispatch(cpu, address, size, user)


class PortEncounter:
    """The port's decision with only the state it reads."""

    _choose_unarmed_guard_action = CombatEncounter._choose_unarmed_guard_action
    _brake_guard = CombatEncounter._brake_guard
    _guard_tile = CombatEncounter._guard_tile
    _guard_front_edge_distance = CombatEncounter._guard_front_edge_distance
    _supporting_column = CombatEncounter._supporting_column

    def __init__(self, level, terrain, player, nearest, record, kid_record):
        self.level, self.terrain, self.player = level, terrain, player
        self.nearest, self.jumped = nearest, False
        self.guard_art = SimpleNamespace(frames={index: record for index in range(512)})
        self.player_frames = {index: kid_record for index in range(512)}

    def _nearest_guard(self, side=None):
        return self.nearest

    def _choose_guard_jump(self, guard):
        self.jumped = True


def run_probe(source, only=None):
    directory = Path(source) / 'resource_forks'
    path = directory / 'Prince of Persia 2.bin'
    raw = path.read_bytes()
    machine = NativeUnarmedBrake(parse_resource_fork(raw))
    levels = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL']
    digest, totals, braked, mismatches = hashlib.sha256(), Counter(), Counter(), Counter()
    examples, services = {}, Counter()

    def case(label, level, environment, room, row, x, facing, pose, frame, kid, flags, nearest,
             alternate, actor=2):
        (kid_x, kid_row, kid_pose, kid_facing, kid_armed, kid_alive, special, run_state,
         kid_frame) = kid
        kid_contact = kid_x + (kid_frame[0] - (kid_frame[1] & 0x3f)) * (1 if kid_facing else -1)
        machine.reset(level)
        machine.jumps, machine.jumped = [], False
        machine.nearest = (2, -1, 3)[nearest[0]]
        machine.alternate_row = alternate
        for field, value in ((ROOM, room + 1), (ROW, row), (FACING, 0 if facing else -1),
                             (X, x + NATIVE_X_ORIGIN), (TYPE, actor), (POSE, pose),
                             (FRAME_DX, frame[0]), (FRAME_FLAGS, frame[1]), (KID_ROOM, room + 1),
                             (SELF, 2), (ALERT, 1), (FLAGS, flags), (ARMED, 0),
                             (KID_X, kid_x + NATIVE_X_ORIGIN), (KID_POSE, kid_pose),
                             (KID_ROW, kid_row), (KID_FACING, 0 if kid_facing else -1),
                             (KID_ARMED, kid_armed), (KID_ALIVE, -1 if kid_alive else 0),
                             (KID_SPECIAL, special), (RUN_FACING, 0 if kid_facing else -1),
                             (RUN_POSE, kid_pose), (RUN_STATE, run_state),
                             (BANK_X + 3 * 0x3e, nearest[1] + NATIVE_X_ORIGIN)):
            machine.put_word(field, value)
        machine.call(4, 0x2a7c)
        machine.put_word(KID_COLUMN, machine.call(4, 0x3ad6, (kid_contact + NATIVE_X_ORIGIN,)))
        machine.call(4, 0x057c)
        services.update(machine.services)
        native = (tuple(machine.jumps), machine.word(ALERT), machine.word(X) - NATIVE_X_ORIGIN,
                  machine.word(ARMED), machine.jumped)

        state = SequenceState(195, action=pose, target_x=x, current_x=x, facing=int(facing),
                              actor_type=actor, level_kind=environment)
        guard = SimpleNamespace(state=state, room=room, row=row, alternate_row=alternate,
                                generation_flags=flags, skeleton=object() if actor == 4 else None,
                                alert_mode=1, selected_sequence=None, sword_drawn=False)
        other = SequenceState(5, action=kid_pose, target_x=kid_x, facing=int(kid_facing),
                              actor_type=0, animation_state=run_state, sequence_mode=special)
        player = SimpleNamespace(state=other, room=room, row=kid_row, alive=kid_alive,
                                 sword_drawn=bool(kid_armed))
        neighbour = (None if nearest[0] == 1 else guard if nearest[0] == 0 else
                     SimpleNamespace(state=SequenceState(5, target_x=nearest[1])))
        encounter = PortEncounter(level, LevelMap(level), player, neighbour,
                                  SimpleNamespace(offset_x=frame[0], aux=frame[1]),
                                  SimpleNamespace(offset_x=kid_frame[0], aux=kid_frame[1]))
        encounter._choose_unarmed_guard_action(guard)
        port = (() if guard.selected_sequence is None else (guard.selected_sequence,),
                guard.alert_mode if guard.selected_sequence == 101 else 1,
                state.target_x, int(guard.sword_drawn), encounter.jumped)
        digest.update(struct.pack('>bhhh?', len(native[0]) and native[0][0], native[1],
                                  native[2], native[3], native[4]))
        totals[label] += 1
        braked[label] += native[0] == (101,)
        if native != port:
            key = (label, environment)
            mismatches[key] += 1
            if len(examples.setdefault(key, [])) < 4:
                examples[key].append(dict(level=struct.unpack_from('>H', level, 0x218a)[0],
                                          room=room, row=row, x=x, facing=facing, pose=pose,
                                          frame=frame, kid=kid, flags=flags, nearest=nearest,
                                          alternate=alternate, actor=actor,
                                          native=native, port=port))

    kids = []
    for dx in (-200, -120, -60, -20, 0, 30, 90, 170, 260):
        for kid_row_delta, kid_pose, kid_facing in ((0, 15, True), (0, 5, False), (0, 40, True),
                                                    (1, 15, False), (0, 52, True)):
            kids.append((dx, kid_row_delta, kid_pose, kid_facing))
    poses = (195, 197, 199, 212, 196, 192, 200)
    for resource, entry in sorted(levels.items()):
        if only is not None and resource not in only:
            continue
        level = entry['data']
        environment = struct.unpack_from('>H', level, 0x2186)[0]
        rooms = struct.unpack_from('>H', level, 0x2180)[0]
        number = struct.unpack_from('>H', level, 0x218a)[0]
        actor = 4 if number == 4 else 2
        index = 0
        # Terrain sweep: every room and row, X across the room, both
        # facings; the variants cycle pose, frame, Kid, flags and crowd.
        for room in range(rooms):
            for row in range(3):
                for x in range(-10, 520, 23):
                    for facing in (True, False):
                        dx, kid_delta, kid_pose, kid_facing = kids[index % len(kids)]
                        kid = (x + dx, row + kid_delta, kid_pose, kid_facing,
                               (index // 3) % 2, index % 11 != 0, 13 if index % 13 == 0 else 0,
                               7 if index % 7 == 0 else 1, FRAMES[index // 3 % len(FRAMES)])
                        nearest = ((0, 0), (1, 0), (2, x + 40), (2, x - 140))[index // 5 % 4]
                        case('terrain', level, environment, room, row, x, facing,
                             poses[index % len(poses)], FRAMES[index // 7 % len(FRAMES)], kid,
                             (0, 1, 2)[index // 2 % 3], nearest,
                             row if index % 9 == 0 else -1, actor)
                        index += 1
        # Gate sweep: a gate one cell ahead or behind across phases.
        for room, cell in gate_cells(level, rooms):
            row, column = divmod(cell, 10)
            offset = 0x780 + room * 120 + cell * 4
            original = struct.unpack_from('>H', level, offset)[0]
            for phase in range(0, 256, 13):
                patched = bytearray(level)
                struct.pack_into('>H', patched, offset, (original & 0xff00) | phase)
                patched = bytes(patched)
                for facing in (True, False):
                    for ahead in (1, -1):
                        contact = column - (ahead if facing else -ahead)
                        x = contact * 51 + 25 - NATIVE_X_ORIGIN + 22 + 4
                        for pose in (195, 212):
                            for flags in (0, 1):
                                kid = (x + (300 if facing else -300), row, 15, facing, 0, True,
                                       0, 1, (0, 0))
                                case('gate', patched, environment, room, row, x, facing, pose,
                                     (0, 0), kid, flags, (1, 0), -1, actor)
        print(resource, number, environment, dict(totals), dict(mismatches), flush=True)
    if path.read_bytes() != raw:
        raise AssertionError('Read-only original changed')
    return dict(cases=dict(totals), braked=dict(braked),
                mismatches={f'{label} env {env}': count for (label, env), count in mismatches.items()},
                examples={f'{label} env {env}': value for (label, env), value in examples.items()},
                services=dict(services),
                result_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(raw).hexdigest(),
                supplied=['GetOppIdxClosestToKid 6:36f2: the fixture slot (self 2, none, slot 3)',
                          'GetOppInfoIdx 6:3642: a record with +0x20 = the alternate row',
                          'JumpSeq 6:0006 and the jump 4:0834: recorded, no effect'],
                fixtures=['LEVL 2000-2013 as stored (gate sweep patches the low byte)',
                          'Working copy: room, row, X, facing, type 2 (4 on level four), pose,'
                          ' frame dx/flags, own slot 2, alert 1, generation flags 0-2',
                          'Kid copies a5-0x50d2 and a5-0x5094: X, row, pose, facing, armed,'
                          ' ALIVE, a5-0x509e, animation state; the Kid column word from'
                          ' GetCharCol 4:3ad6 of the Kid supporting-foot X (frame fixture)'],
                exclusions=['The armed/pose-166 branches of AutoCtrl (4:04fc)',
                            'The jump itself (4:0834, DoRunJump)',
                            'Opponents outside the Kid room (the port also tests room)'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('cases', 'braked', 'mismatches', 'examples',
                                                   'services')}))


if __name__ == '__main__':
    main()
