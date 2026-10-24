"""Compare the port's ruins head controller (pop2/ruins_ai.py) with the
original head wrapper 7:1324 and every leaf it reaches.

Unlike the level7 probes, the comparison side is the game's runtime code,
not a separate research reference. Supplied endpoints are listed in the
report; everything else executes natively.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import struct
from types import SimpleNamespace

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_head_idle import NativeHeadIdle
from tools.probe_level7_head_recovery import head_slots
from tools.probe_level7_sequence_selection import supporting_column

WORKING = dict(slot=-0x5056, facing=-0x5054, x=-0x5052, y=-0x5050, actor=-0x504e,
               pose=-0x504c, column=-0x504a, row=-0x5048, horizontal_velocity=-0x5044,
               vertical_velocity=-0x5042, room=-0x5040, armed=-0x503c, alive=-0x503a,
               life=-0x5038, sequence=-0x5030, cursor=-0x5032, selected=-0x502e,
               body_top=-0x502c, body_bottom=-0x5028, special=-0x5022, alert=-0x5024)
PRINCE = dict(facing=2, x=4, y=6, actor=8, pose=0xa, column=0xc, row=0xe, room=0x16,
              armed=0x1a, alive=0x1c, life=0x1e, selected=0x28, target=0x3a)
COMPARED = ('facing', 'x', 'y', 'row', 'horizontal_velocity', 'vertical_velocity', 'armed',
            'life', 'sequence', 'cursor', 'selected', 'special', 'alert')


class Draws:
    """The same bounded random outcomes for both sides, from one seed."""

    def __init__(self, seed):
        self.values = random.Random(seed)
        self.log = []

    def draw(self, maximum):
        value = self.values.randrange(maximum + 1)
        self.log.append((maximum, value))
        return value


class NativeRuinsHead(NativeHeadIdle):
    RANGES = {
        **NativeHeadIdle.RANGES,
        3: NativeHeadIdle.RANGES[3] + ((0x4da6, 0x4e30),),
        4: NativeHeadIdle.RANGES[4] + (
            (0x3272, 0x3284), (0x31fa, 0x3228), (0x338e, 0x33b4), (0x34e2, 0x34f0),
            (0x39fc, 0x3a70), (0x3a92, 0x3a9e), (0x3aa0, 0x3ad4), (0x49ee, 0x4a44),
            (0x4a46, 0x4b00), (0x52bc, 0x5360), (0x35a6, 0x35b8), (0x3a72, 0x3a90)),
        6: NativeHeadIdle.RANGES[6] + ((0x3642, 0x36de),),
        7: NativeHeadIdle.RANGES[7] + (
            (0x00f8, 0x0480), (0x0494, 0x0572), (0x064c, 0x08e6), (0x0b16, 0x0b54),
            (0x0c5e, 0x0e7a), (0x0e8c, 0x0f72), (0x0f88, 0x1000), (0x1012, 0x1064),
            (0x107a, 0x1152), (0x1164, 0x1252), (0x1324, 0x1452), (0x1454, 0x16a0),
            (0x16b8, 0x16f6), (0x17c8, 0x180a), (0x1824, 0x1b3a), (0x1b52, 0x1db0),
            (0x1dc6, 0x1e02)),
        5: NativeHeadIdle.RANGES[5] + ((0x2198, 0x21de),),
    }

    def reset(self, level):
        super().reset(level)
        self.sounds, self.songs, self.nearest_calls, self.meters = [], [], 0, 0
        self.nearest = True
        self.random = None

    def skip(self, cpu, value=None):
        stack = cpu.reg_read(self.registers['a7'])
        if value is not None:
            cpu.reg_write(self.registers['d0'], value & 0xffffffff)
        cpu.reg_write(self.registers['a7'], stack + 4)
        cpu.reg_write(self.registers['pc'], struct.unpack('>I', cpu.mem_read(stack, 4))[0])

    def argument(self, cpu, index=0):
        stack = cpu.reg_read(self.registers['a7'])
        return struct.unpack('>h', cpu.mem_read(stack + 4 + 2 * index, 2))[0]

    def dispatch(self, cpu, address, size, user):
        if address == self.address(17, 0x6e06):
            self.skip(cpu, self.random.draw(self.argument(cpu)))
            return
        if address == self.address(5, 0x4d84):
            self.sounds.append(self.argument(cpu))
            self.skip(cpu)
            return
        if address == self.address(5, 0x4d58):
            self.songs.append(self.argument(cpu))
            self.skip(cpu)
            return
        if address == self.address(5, 0x52c8):
            self.skip(cpu, 0)
            return
        if address == self.address(6, 0x3946):
            self.nearest_calls += 1
            self.skip(cpu, int(self.nearest))
            return
        if address == self.address(3, 0x4a8e):
            self.meters += 1  # DrawOppMeter: drawing only.
            self.skip(cpu)
            return
        if address == self.address(4, 0x5cbc):
            self.skip(cpu)
            return
        super().dispatch(cpu, address, size, user)


class TapeRandom:
    def __init__(self, draws):
        self.draws = draws

    def randrange(self, stop):
        return self.draws.draw(stop - 1)


def port_run(level, sequences, frames, initial, record, prince, nearest, seed, tension, banked,
             remainder, controller='control_head'):
    """Run pop2.ruins_ai's control_head on the same supplied state."""
    from pop2.combat import Fighter
    from pop2.ruins_ai import PrinceView, RuinsCreatures, RuinsMind
    from pop2.sequence_runtime import SequenceRuntime, SequenceState
    from pop2.terrain import LevelMap, floor_y

    row = initial['row']
    state = SequenceState(initial['sequence'], cursor=initial['cursor'], action=initial['pose'],
                          current_x=initial['x'] - 207, target_x=initial['x'] - 207,
                          current_y=initial['y'] - floor_y(row),
                          facing=1 if initial['facing'] == 0 else 0, actor_type=initial['actor'],
                          sequence_mode=initial['special'],
                          horizontal_velocity=initial['horizontal_velocity'],
                          vertical_velocity=initial['vertical_velocity'],
                          selected_sequence_id=initial['selected'])
    actor = Fighter(SequenceRuntime(sequences, state), initial['life'], initial['life'],
                    initial['room'] - 1, row, sword_drawn=initial['armed'] == 1)
    actor.ruins = RuinsMind(initial['actor'], record['kind'], record['skill'], initial['slot'],
                            mode=record['mode'], dest_column=record['dest_column'],
                            dest_row=record['dest_row'], timer=record['timer'],
                            song=record['song'], alert=initial['alert'])
    player_state = SequenceState(0, action=prince['pose'], target_x=prince['x'] - 207,
                                 current_x=prince['x'] - 207,
                                 facing=1 if prince['facing'] == 0 else 0, actor_type=0,
                                 selected_sequence_id=prince['selected'])
    player = Fighter(SequenceRuntime(sequences, player_state), prince['life'], 3,
                     prince['room'] - 1, prince['row'], sword_drawn=prince['armed'] == 1)
    draws = Draws(seed)
    encounter = SimpleNamespace(rng=TapeRandom(draws), terrain=LevelMap(level), player=player,
                                parry_timer=0, guard_art=None)
    creatures = RuinsCreatures(tension=tension, remainder=remainder)
    creatures.rooms[actor.room] = [actor]
    creatures.banked = actor if banked else None
    view = PrinceView(prince['column'], prince['row'], prince['x'], prince['y'], prince['facing'],
                      prince['pose'], prince['room'] - 1, prince['alive'], prince['life'],
                      prince['armed'] == 1, prince['selected'])
    creatures.prince = lambda _encounter: view
    creatures.nearest_on_side = lambda *_args: nearest
    getattr(creatures, controller)(actor, encounter)
    mind = actor.ruins
    result = dict(facing=0 if state.facing else -1, x=state.target_x + 207,
                  y=floor_y(actor.row) + state.current_y, row=actor.row,
                  horizontal_velocity=state.horizontal_velocity,
                  vertical_velocity=state.vertical_velocity, armed=int(actor.sword_drawn),
                  life=actor.life, sequence=state.sequence_id, cursor=state.cursor,
                  selected=state.selected_sequence_id, special=state.sequence_mode,
                  alert=mind.alert)
    record_after = dict(mode=mind.mode, dest_column=mind.dest_column, dest_row=mind.dest_row,
                        timer=mind.timer, song=mind.song)
    banked_after = creatures.banked is actor
    return result, record_after, state.sound_events, draws.log, banked_after, creatures.remainder


def run_probe(recovery, cases=20000, seed=2026):
    directory = Path(recovery) / 'resource_forks'
    program_bytes = (directory / 'Prince of Persia 2.bin').read_bytes()
    prince_bytes = (directory / 'Prince.rsrc.bin').read_bytes()
    head_bytes = (directory / 'Head.rsrc.bin').read_bytes()
    program, prince_rsrc, head = (parse_resource_fork(data) for data in
                                  (program_bytes, prince_bytes, head_bytes))
    from pop2.animation_data import sequence_words, parse_frame_records

    sequences = {key: sequence_words(item['data']) for key, item in prince_rsrc['SEQS'].items()}
    frames = parse_frame_records(head['FRAM'][750]['data'])
    level = prince_rsrc['LEVL'][2006]['data']
    machine = NativeRuinsHead(program, head, prince_rsrc['SEQS'])
    slots = list(head_slots(level))
    rng = random.Random(seed)
    counts, routes, mismatches = Counter(), Counter(), []
    requested, sounds = Counter(), Counter()
    digest = hashlib.sha256()
    poses = (150, 159, 165, 166, 167, 173, 181, 151, 160)
    selected_ids = (130, 131, 134, 137, 138, 139, 140, 142, 143, 144, 147, 150, 151,
                    152, 153, 155, 156, 157, 158, 159, 160, 162, 163, 166)
    for case in range(cases):
        room, slot, offset, actor = rng.choice(slots)
        facing = rng.choice((-1, 0))
        pose = rng.choice(poses)
        row = rng.randrange(3)
        column = rng.randrange(1, 9)
        x = 207 + column * 51 + rng.choice((47, 30, 20, 40, 10))
        frame_index = pose - 149 + (43 if actor == 8 and pose <= 181 else 0)
        frame = head['FRAM'][750]['data'][frame_index * 10:frame_index * 10 + 10]
        column, remainder = supporting_column(x, facing, frame)
        selected = rng.choice(selected_ids)
        initial = dict(slot=slot, facing=facing, x=x, y=row * 120 + 73 + rng.choice((0, 0, -20, 20)),
                       actor=actor, pose=pose, column=column, row=row,
                       horizontal_velocity=rng.choice((0, 5)), vertical_velocity=rng.choice((0, -6)),
                       room=room, armed=rng.choice((0, 1)), alive=-1, life=rng.choice((1, 2, 3)),
                       sequence=selected, cursor=rng.randrange(4), selected=selected,
                       body_top=18, body_bottom=48, special=rng.choice((0, 0, 1, 2)),
                       alert=rng.choice((0, 3)))
        prince_row = row if rng.random() < 0.7 else rng.randrange(3)
        prince_column = max(0, min(9, column + rng.choice((-3, -2, -1, 0, 0, 1, 1, 2, 3))))
        prince = dict(facing=rng.choice((-1, 0)), x=207 + prince_column * 51 + rng.choice((10, 25, 40)),
                      y=prince_row * 120 + 106, actor=0, pose=rng.choice((15, 157, 158, 1, 50, 140)),
                      column=prince_column, row=prince_row, room=room,
                      armed=rng.choice((0, 1)), alive=rng.choice((-1, -1, -1, 0, 6)),
                      life=rng.choice((0, 1, 3, 3)), selected=rng.choice((2, 70, 227, 75)))
        banked = rng.random() < 0.5
        # The Prince's target (+0x3a, cached at a5-0x505a) is HeadGetAngry's bank.
        prince['target'] = slot if banked else -1
        record = dict(kind=5 if actor == 7 else 6,
                      skill=struct.unpack_from('>h', level, offset + 6)[0],
                      mode=rng.choice((0, 1, 2, 3)), dest_column=rng.randrange(0, 10),
                      dest_row=rng.randrange(3), timer=rng.choice((0, 1, 2, 40)),
                      song=rng.choice((0, 1)))
        nearest = rng.random() < 0.8
        tension = rng.choice((0, 25, 35))
        draw_seed = rng.randrange(1 << 30)

        # Native side.
        supplied = bytearray(level)
        for field_offset, name in ((0x1c, 'mode'), (0x1e, 'dest_column'), (0x20, 'dest_row'),
                                   (0x22, 'timer'), (0x24, 'song')):
            struct.pack_into('>h', supplied, offset + field_offset, record[name])
        machine.reset(supplied)
        machine.cpu.mem_write(machine.A5 - 0x5056, bytes(62))
        for name, value in initial.items():
            machine.put_word(WORKING[name], value)
        machine.put_word(-0x481c, remainder)
        prince_bytes_native = bytearray(62)
        for name, value in prince.items():
            struct.pack_into('>h', prince_bytes_native, PRINCE[name], value)
        machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(prince_bytes_native))
        machine.put_word(-0x36a0, tension)
        machine.nearest = nearest
        machine.random = Draws(draw_seed)
        machine.call(7, 0x1324)
        native = {name: machine.word(WORKING[name]) for name in COMPARED}
        native_record = {name: struct.unpack_from('>h', machine.level_bytes(len(level)),
                                                  offset + field_offset)[0]
                         for field_offset, name in ((0x1c, 'mode'), (0x1e, 'dest_column'),
                                                    (0x20, 'dest_row'), (0x22, 'timer'),
                                                    (0x24, 'song'))}
        native_sounds = machine.sounds + machine.songs
        native_banked = machine.word(-0x50d2 + 0x3a) == slot

        port, port_record, port_sounds, port_draws, port_banked, port_remainder = port_run(
            level, sequences, frames, initial, record, prince, nearest, draw_seed, tension, banked,
            remainder)
        differences = {name: (native[name], port[name]) for name in COMPARED
                       if native[name] != port[name]}
        differences.update({f'record.{name}': (native_record[name], port_record[name])
                            for name in native_record if native_record[name] != port_record[name]})
        if sorted(native_sounds) != sorted(port_sounds):
            differences['sounds'] = (native_sounds, port_sounds)
        if machine.random.log != port_draws:
            differences['random'] = (machine.random.log, port_draws)
        if machine.word(-0x481c) != port_remainder:
            differences['remainder'] = (machine.word(-0x481c), port_remainder)
        if native_banked != port_banked:
            differences['banked'] = (native_banked, port_banked)
        route = (record['mode'], native['selected'])
        routes[record['mode']] += 1
        requested.update(machine.requests)
        sounds.update(native_sounds)
        if differences:
            counts['mismatch'] += 1
            if len(mismatches) < 40:
                mismatches.append(dict(case=case, initial=initial, prince=prince, record=record,
                                       nearest=nearest, tension=tension, differences=differences))
        else:
            counts['match'] += 1
        digest.update(json.dumps([native, native_record, route]).encode())
    return dict(
        cases=dict(counts), modes=dict(routes), mismatches=counts['mismatch'],
        requested_sequences=dict(sorted(requested.items())), sounds=dict(sorted(sounds.items())),
        examples=mismatches,
        outputs_sha256=digest.hexdigest(),
        executable_sha256=hashlib.sha256(program_bytes).hexdigest(),
        supplied=['17:6e06 Rnd: the same seeded bounded outcomes on both sides',
                  '5:4d84 AddSound / 5:4d58 AddSong: recorded, not played',
                  '5:52c8 IsSoundPlaying: 0', '6:3946 nearest-on-side: supplied flag',
                  '3:4a8e DrawOppMeter: skipped (drawing)',
                  '4:5cbc shape bounds: inert; body bounds supplied (height 30)',
                  '17:330e GetResource: actual Prince SEQS existence'],
        scope=('The original wrapper 7:1324 and all reached head leaves against '
               'pop2.ruins_ai.RuinsCreatures.control_head on randomized supplied states '
               'in actual level-seven head slots. One controller call per case; no '
               'animation, flight, collision or combat.'),
    )


def serpent_slots(level):
    for room in range(1, 33):
        base = 0x20e6 + room * 0xc0
        for slot in range(struct.unpack_from('>H', level, base)[0]):
            offset = base + 2 + slot * 38
            if struct.unpack_from('>h', level, offset + 0x18)[0] == 8:
                yield room, slot, offset


def run_serpent_probe(recovery, cases=20000, seed=2027):
    """SnakeComeOutOfHole 7:1824 against RuinsCreatures.control_serpent."""
    directory = Path(recovery) / 'resource_forks'
    program_bytes = (directory / 'Prince of Persia 2.bin').read_bytes()
    program, prince_rsrc, head = (parse_resource_fork((directory / name).read_bytes()) for name in
                                  ('Prince of Persia 2.bin', 'Prince.rsrc.bin', 'Head.rsrc.bin'))
    from pop2.animation_data import sequence_words, parse_frame_records

    sequences = {key: sequence_words(item['data']) for key, item in prince_rsrc['SEQS'].items()}
    frames = parse_frame_records(head['FRAM'][750]['data'])
    level = prince_rsrc['LEVL'][2006]['data']
    machine = NativeRuinsHead(program, head, prince_rsrc['SEQS'])
    slots = list(serpent_slots(level))
    rng = random.Random(seed)
    counts, requested, sounds, mismatches = Counter(), Counter(), Counter(), []
    digest = hashlib.sha256()
    for case in range(cases):
        room, slot, offset = rng.choice(slots)
        facing, pose = rng.choice((-1, 0)), rng.choice((230, 238, 254, 264, 274, 278, 279, 280, 250))
        row, column = rng.randrange(3), rng.randrange(1, 9)
        x = 207 + column * 51 + rng.randrange(0, 51)
        frame_index = pose - 149
        frame = head['FRAM'][750]['data'][frame_index * 10:frame_index * 10 + 10]
        column, remainder = supporting_column(x, facing, frame)
        selected = rng.choice((168, 170, 171, 172, 173, 175, 176, 177))
        initial = dict(slot=slot, facing=facing, x=x, y=row * 120 + 106, actor=11, pose=pose,
                       column=column, row=row, horizontal_velocity=0, vertical_velocity=0,
                       room=room, armed=1, alive=-1, life=3, sequence=selected,
                       cursor=rng.randrange(4), selected=selected, body_top=18, body_bottom=48,
                       special=rng.choice((0, 0, 6, 9)), alert=rng.choice((0, 1, 2, 3)))
        prince_column = max(0, min(9, column + rng.choice((-2, -1, 0, 1, 2))))
        prince = dict(facing=rng.choice((-1, 0)), x=207 + prince_column * 51 + rng.choice((5, 25, 45)),
                      y=row * 120 + 106, actor=0,
                      pose=rng.choice((1, 7, 14, 30, 52, 140, 157, 15)), column=prince_column,
                      row=row if rng.random() < 0.8 else (row + 1) % 3, room=room,
                      armed=rng.choice((0, 1)), alive=rng.choice((-1, -1, -1, 0, 6)),
                      life=rng.choice((0, 3)), selected=rng.choice((2, 227, 96)), target=-1)
        record = dict(kind=8, skill=struct.unpack_from('>h', level, offset + 6)[0],
                      mode=rng.choice((-1, -1, 0, 1, 5)), dest_column=0, dest_row=0, timer=0, song=0)
        draw_seed = rng.randrange(1 << 30)
        supplied = bytearray(level)
        struct.pack_into('>h', supplied, offset + 0x1c, record['mode'])
        machine.reset(supplied)
        machine.cpu.mem_write(machine.A5 - 0x5056, bytes(62))
        for name, value in initial.items():
            machine.put_word(WORKING[name], value)
        machine.put_word(-0x481c, remainder)
        prince_bytes_native = bytearray(62)
        for name, value in prince.items():
            struct.pack_into('>h', prince_bytes_native, PRINCE[name], value)
        machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(prince_bytes_native))
        machine.random = Draws(draw_seed)
        # 2:6512: the opponent pipeline loads the frame before AutoCtrl; the
        # serpent wrapper itself (unlike 7:1324) does not.
        machine.call(4, 0x2a8e)
        machine.call(7, 0x1824)
        native = {name: machine.word(WORKING[name]) for name in COMPARED}
        native_mode = struct.unpack_from('>h', machine.level_bytes(len(level)), offset + 0x1c)[0]
        port, port_record, port_sounds, port_draws, _banked, _remainder = port_run(
            level, sequences, frames, initial, record, prince, True, draw_seed, 0, False,
            remainder, 'control_serpent')
        differences = {name: (native[name], port[name]) for name in COMPARED
                       if native[name] != port[name]}
        if native_mode != port_record['mode']:
            differences['record.mode'] = (native_mode, port_record['mode'])
        if sorted(machine.sounds) != sorted(port_sounds):
            differences['sounds'] = (machine.sounds, port_sounds)
        if machine.random.log != port_draws:
            differences['random'] = (machine.random.log, port_draws)
        requested.update(machine.requests)
        sounds.update(machine.sounds)
        if differences:
            counts['mismatch'] += 1
            if len(mismatches) < 40:
                mismatches.append(dict(case=case, initial=initial, prince=prince, record=record,
                                       differences=differences))
        else:
            counts['match'] += 1
        digest.update(json.dumps([native, native_mode]).encode())
    return dict(
        cases=dict(counts), mismatches=counts['mismatch'],
        requested_sequences=dict(sorted(requested.items())), sounds=dict(sorted(sounds.items())),
        examples=mismatches, outputs_sha256=digest.hexdigest(),
        executable_sha256=hashlib.sha256(program_bytes).hexdigest(),
        supplied=['17:6e06 Rnd: the same seeded bounded outcomes on both sides',
                  '5:4d84 AddSound: recorded', '17:330e GetResource: actual SEQS existence'],
        scope=('SnakeComeOutOfHole 7:1824 with 7:1dc6/187e/19fe/1b52 against '
               'pop2.ruins_ai.RuinsCreatures.control_serpent on randomized supplied states '
               'in actual level-seven serpent slots; the alert state is supplied.'),
    )


class NativeRuinsStab(NativeRuinsHead):
    RANGES = {
        **NativeRuinsHead.RANGES,
        4: NativeRuinsHead.RANGES[4] + ((0x34f2, 0x35a4), (0x3a48, 0x3a70)),
        6: NativeRuinsHead.RANGES[6] + ((0x51f2, 0x5560), (0x5562, 0x57b0), (0x5022, 0x5090)),
    }

    def reset(self, level):
        super().reset(level)
        self.animations = self.selections = 0

    def dispatch(self, cpu, address, size, user):
        if address == self.address(4, 0x2c0c):
            self.animations += 1  # AnimChar: the port's next_frame, compared separately.
            self.skip(cpu)
            return
        if address == self.address(6, 0x36f2):
            self.selections += 1  # GetOppIdxClosestToKid: the Prince's new target.
            self.skip(cpu, 0xffff)
            return
        if address == self.address(6, 0x04aa):
            self.skip(cpu)
            return
        super().dispatch(cpu, address, size, user)


def run_stab_probe(recovery, cases=20000, seed=2028):
    """CheckStab 6:51f2 on a struck head or serpent against RuinsCreatures.stab."""
    from pop2.combat import Fighter
    from pop2.ruins_ai import PrinceView, RuinsCreatures, RuinsMind
    from pop2.sequence_runtime import SequenceRuntime, SequenceState
    from pop2.terrain import LevelMap, floor_y

    directory = Path(recovery) / 'resource_forks'
    program_bytes = (directory / 'Prince of Persia 2.bin').read_bytes()
    program, prince_rsrc, head = (parse_resource_fork((directory / name).read_bytes()) for name in
                                  ('Prince of Persia 2.bin', 'Prince.rsrc.bin', 'Head.rsrc.bin'))
    level = prince_rsrc['LEVL'][2006]['data']
    machine = NativeRuinsStab(program, head, prince_rsrc['SEQS'])
    fram = head['FRAM'][750]['data']
    slots = [(room, slot, offset, actor) for room, slot, offset, actor in head_slots(level)]
    slots += [(room, slot, offset, 11) for room, slot, offset in serpent_slots(level)]
    rng = random.Random(seed)
    counts, sequences, sounds, mismatches = Counter(), Counter(), Counter(), []
    for case in range(cases):
        room, slot, offset, actor_type = rng.choice(slots)
        is_head = actor_type != 11
        pose = rng.choice((150, 159, 166, 173) if is_head else (230, 274, 278, 280))
        facing, row, column = rng.choice((-1, 0)), rng.randrange(3), rng.randrange(1, 9)
        x = 207 + column * 51 + 47
        frame_index = pose - 149 + (43 if actor_type == 8 and pose <= 181 else 0)
        frame = fram[frame_index * 10:frame_index * 10 + 10]
        column, _remainder = supporting_column(x, facing, frame)
        selected = rng.choice((140, 147, 150, 166, 142) if is_head else (170, 173, 175, 176))
        life = rng.choice((1, 2, 3))
        initial = dict(slot=slot, facing=facing, x=x, y=row * 120 + (73 if is_head else 106),
                       actor=actor_type, pose=pose, column=column, row=row,
                       horizontal_velocity=0, vertical_velocity=rng.choice((0, -6)), room=room,
                       armed=1, alive=-1, life=life, sequence=selected, cursor=1,
                       selected=selected, body_top=18, body_bottom=48, special=0,
                       alert=rng.choice((0, 3)))
        prince = dict(facing=rng.choice((-1, 0)), x=x + rng.choice((-60, 60)), y=row * 120 + 106,
                      actor=0, pose=154, column=column, row=row, room=room, armed=1, alive=-1,
                      life=3, selected=75, target=-1)
        sword_type = rng.choice((1, 2))
        record = dict(kind=8 if not is_head else 5 if actor_type == 7 else 6,
                      skill=struct.unpack_from('>h', level, offset + 6)[0], mode=rng.choice((0, 1, 3)))
        tension = rng.choice((0, 10, 30))
        draw_seed = rng.randrange(1 << 30)

        supplied = bytearray(level)
        struct.pack_into('>h', supplied, offset + 0x1c, record['mode'])
        machine.reset(supplied)
        machine.cpu.mem_write(machine.A5 - 0x5056, bytes(62))
        for name, value in initial.items():
            machine.put_word(WORKING[name], value)
        prince_bytes_native = bytearray(62)
        for name, value in prince.items():
            struct.pack_into('>h', prince_bytes_native, PRINCE[name], value)
        machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(prince_bytes_native))
        machine.cpu.mem_write(machine.A5 - 0x5094, bytes(prince_bytes_native))
        machine.put_word(-0x500a, sword_type)
        machine.put_word(-0x36a2, 1)
        machine.put_word(-0x36a0, tension)
        machine.random = Draws(draw_seed)
        machine.call(4, 0x2a8e)
        machine.call(6, 0x51f2)
        native = {name: machine.word(WORKING[name]) for name in COMPARED}
        # DecLifePts 4:34f2 queues the damage in a5-0x5034 (applied by ChangeMeters).
        native['life'] = max(0, native['life'] + min(0, machine.word(-0x5034)))
        native_mode = struct.unpack_from('>h', machine.level_bytes(len(level)), offset + 0x1c)[0]
        native_tension = machine.word(-0x36a0)

        state = SequenceState(selected, cursor=1, action=pose, current_x=x - 207, target_x=x - 207,
                              current_y=initial['y'] - floor_y(row),
                              facing=1 if facing == 0 else 0, actor_type=actor_type,
                              vertical_velocity=initial['vertical_velocity'],
                              selected_sequence_id=selected)
        actor = Fighter(SequenceRuntime({}, state), life, life, room - 1, row, sword_drawn=True)
        actor.ruins = RuinsMind(actor_type, record['kind'], record['skill'], slot,
                                mode=record['mode'], alert=initial['alert'])
        actor.runtime.next_frame = lambda: None
        player_state = SequenceState(75, action=154, target_x=prince['x'] - 207,
                                     facing=1 if prince['facing'] == 0 else 0, actor_type=0)
        player = Fighter(SequenceRuntime({}, player_state), 3, 3, room - 1, row, sword_drawn=True)
        draws = Draws(draw_seed)
        encounter = SimpleNamespace(rng=TapeRandom(draws), terrain=LevelMap(level), player=player,
                                    parry_timer=0, guard_art=None)
        creatures = RuinsCreatures(tension_level=1, tension=tension)
        # IsAbleToFleeInRoom 7:161c reads every record of the room.
        others = []
        base = 0x20e6 + room * 0xc0
        for index in range(struct.unpack_from('>H', level, base)[0]):
            if index == slot:
                others.append(actor)
                continue
            words = struct.unpack_from('>19h', level, base + 2 + index * 38)
            others.append(SimpleNamespace(ruins=RuinsMind(0, words[12], words[3], index,
                                                          mode=words[14])))
        creatures.rooms[actor.room] = others
        view = PrinceView(column, row, prince['x'], prince['y'], prince['facing'], 154, room - 1,
                          -1, 3, True, 75)
        creatures.prince = lambda _encounter: view
        event = creatures.stab(actor, encounter, sword_type)
        port = dict(facing=0 if state.facing else -1, x=state.target_x + 207,
                    y=floor_y(actor.row) + state.current_y, row=actor.row,
                    horizontal_velocity=state.horizontal_velocity,
                    vertical_velocity=state.vertical_velocity, armed=int(actor.sword_drawn),
                    life=actor.life, sequence=state.sequence_id, cursor=state.cursor,
                    selected=state.selected_sequence_id, special=state.sequence_mode,
                    alert=actor.ruins.alert)
        differences = {name: (native[name], port[name]) for name in COMPARED
                       if native[name] != port[name]}
        if native_mode != actor.ruins.mode:
            differences['record.mode'] = (native_mode, actor.ruins.mode)
        if native_tension != creatures.tension:
            differences['tension'] = (native_tension, creatures.tension)
        # Kill songs (137) come later natively (5:4bb8, at ALIVE 6).
        port_sounds = [sound for sound in state.sound_events if sound != 137]
        if event.sound:
            port_sounds.append(event.sound)
        if sorted(machine.sounds) != sorted(port_sounds):
            differences['sounds'] = (machine.sounds, port_sounds)
        if machine.random.log != draws.log:
            differences['random'] = (machine.random.log, draws.log)
        sequences[native['selected']] += 1
        sounds.update(machine.sounds)
        if differences:
            counts['mismatch'] += 1
            if len(mismatches) < 40:
                mismatches.append(dict(case=case, initial=initial, prince=prince, record=record,
                                       sword_type=sword_type, tension=tension,
                                       differences=differences))
        else:
            counts['match'] += 1
    return dict(
        cases=dict(counts), mismatches=counts['mismatch'],
        requested_sequences=dict(sorted(sequences.items())), sounds=dict(sorted(sounds.items())),
        examples=mismatches, executable_sha256=hashlib.sha256(program_bytes).hexdigest(),
        supplied=['4:2c0c AnimChar: skipped on both sides (port next_frame not run)',
                  '6:36f2 nearest opponent: -1', '6:04aa corpse alignment: skipped',
                  '17:6e06 Rnd: the same seeded outcomes', '5:4d84 AddSound: recorded',
                  '3:4a8e DrawOppMeter: skipped'],
        scope=('CheckStab 6:51f2 (with DecLifePts, IsAbleToFleeInRoom, the death branch '
               '6:5562 and SetTensionLevel 6:5022) on a struck head or serpent of the actual '
               'level-seven slots, against pop2.ruins_ai.RuinsCreatures.stab. The kill song '
               '137 is excluded: the port plays it at once, the original at ALIVE 6.'),
    )


class NativeRuinsPrinceStab(NativeRuinsStab):
    RANGES = {
        **NativeRuinsStab.RANGES,
        6: NativeRuinsStab.RANGES[6] + ((0x04aa, 0x0560),),
        3: NativeRuinsStab.RANGES[3] + ((0x4e7c, 0x4ea2),),
        4: NativeRuinsStab.RANGES[4] + ((0x3196, 0x31e4),),
    }
    KID_FRAMES, KID_ATTACHMENTS = 0xb4000, 0xb8000

    def __init__(self, program, head, sequences, kid):
        super().__init__(program, head, sequences)
        self.cpu.mem_write(self.HANDLES + 16, struct.pack('>II', self.KID_FRAMES, self.KID_ATTACHMENTS))
        self.cpu.mem_write(self.KID_FRAMES, kid['FRAM'][25001]['data'])
        self.cpu.mem_write(self.KID_ATTACHMENTS, kid['AFRM'][25001]['data'])

    def reset(self, level):
        super().reset(level)
        # LoadFrame 4:2ad6: types 0/1/6 read the Kid handles at a5-0x3472/-0x3476.
        self.cpu.mem_write(self.A5 - 0x3472, struct.pack('>I', self.HANDLES + 16))
        self.cpu.mem_write(self.A5 - 0x3476, struct.pack('>I', self.HANDLES + 20))

    def dispatch(self, cpu, address, size, user):
        if address == self.address(4, 0x2c0c):
            # AnimChar stand-in: only SEQS 85's first pose (-7 10, 179) matters
            # to the corpse alignment that follows; both sides do the same.
            self.animations += 1
            if self.word(-0x5030) == 85 and self.word(-0x5032) == 0:
                self.put_word(-0x504c, 179)
                self.put_word(-0x5032, 3)
            self.skip(cpu)
            return
        if address == self.address(6, 0x04aa):
            NativeRuinsHead.dispatch(self, cpu, address, size, user)
            return
        super().dispatch(cpu, address, size, user)


def run_prince_probe(recovery, cases=20000, seed=2029):
    """CheckStab 6:51f2 for the Prince struck by a head or serpent against
    RuinsCreatures.stab_prince."""
    from pop2.animation_data import parse_frame_records
    from pop2.combat import Fighter
    from pop2.ruins_ai import RuinsCreatures, RuinsMind
    from pop2.sequence_runtime import SequenceRuntime, SequenceState
    from pop2.terrain import LevelMap

    directory = Path(recovery) / 'resource_forks'
    program_bytes = (directory / 'Prince of Persia 2.bin').read_bytes()
    program, prince_rsrc, head = (parse_resource_fork((directory / name).read_bytes()) for name in
                                  ('Prince of Persia 2.bin', 'Prince.rsrc.bin', 'Head.rsrc.bin'))
    kid = parse_resource_fork((directory / 'Kid.rsrc.bin').read_bytes())
    kid_frames = parse_frame_records(kid['FRAM'][25001]['data'])
    level = prince_rsrc['LEVL'][2006]['data']
    machine = NativeRuinsPrinceStab(program, head, prince_rsrc['SEQS'], kid)
    rng = random.Random(seed)
    counts, sequences, sounds, methods, mismatches = Counter(), Counter(), Counter(), Counter(), []
    poses = (15, 157, 158, 165, 166, 170, 171, 150, 161, 102, 104, 106, 191, 198, 205,
             246, 250, 255, 261, 1, 50, 120, 140, 217)
    selected_ids = (2, 227, 75, 5, 10, 14, 16, 28, 62, 45)
    for case in range(cases):
        room, row, column = rng.randrange(1, 33), rng.randrange(3), rng.randrange(1, 9)
        striker_type = rng.choice((7, 8, 11))
        pose = rng.choice(poses)
        facing = rng.choice((-1, 0))
        x = 207 + column * 51 + rng.randrange(0, 51)
        selected = rng.choice(selected_ids)
        armed = rng.choice((0, 1, 1, -1))
        life = rng.choice((1, 2, 3))
        initial = dict(slot=0, facing=facing, x=x, y=row * 120 + 106, actor=0, pose=pose,
                       column=0, row=row, horizontal_velocity=0, vertical_velocity=0, room=room,
                       armed=armed, alive=-1, life=life, sequence=selected, cursor=0,
                       selected=selected, body_top=18, body_bottom=48, special=0, alert=0)
        striker_facing = rng.choice((-1, 0))
        striker = dict(facing=striker_facing, x=x, y=row * 120 + 73, actor=striker_type,
                       pose=167 if striker_type != 11 else 280, column=column, row=row, room=room,
                       armed=1, alive=-1, life=3, selected=150 if striker_type != 11 else 173,
                       target=-1)
        tension = rng.choice((0, 10))

        machine.reset(level)
        machine.cpu.mem_write(machine.A5 - 0x5056, bytes(62))
        for name, value in initial.items():
            machine.put_word(WORKING[name], value)
        machine.call(4, 0x2a8e)
        machine.call(4, 0x2a72)  # The supporting column from the loaded frame.
        cached = bytearray(62)
        for name, value in striker.items():
            struct.pack_into('>h', cached, PRINCE[name], value)
        machine.cpu.mem_write(machine.A5 - 0x5094, bytes(cached))
        machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(cached))
        machine.put_word(-0x36a2, 1)
        machine.put_word(-0x36a0, tension)
        machine.put_word(-0x500e, 0)
        machine.random = Draws(1)
        machine.call(6, 0x51f2)
        native = {name: machine.word(WORKING[name]) for name in COMPARED}
        native['life'] = max(0, native['life'] + min(0, machine.word(-0x5034)))
        native['armed'] = 1 if native['armed'] == 1 else 0
        native_tension, native_method = machine.word(-0x36a0), machine.word(-0x500e)

        state = SequenceState(selected, action=pose, current_x=x - 207, target_x=x - 207,
                              facing=1 if facing == 0 else 0, actor_type=0,
                              selected_sequence_id=selected)
        player = Fighter(SequenceRuntime({}, state), life, 3, room - 1, row,
                         sword_drawn=armed == 1, sword_lost=armed == -1)

        def first_pose():
            if state.sequence_id == 85 and state.cursor == 0:
                state.action, state.cursor = 179, 3

        player.runtime.next_frame = first_pose
        striker_state = SequenceState(striker['selected'], action=striker['pose'],
                                      target_x=x - 207, facing=1 if striker_facing == 0 else 0,
                                      actor_type=striker_type)
        striker_actor = Fighter(SequenceRuntime({}, striker_state), 3, 3, room - 1, row,
                                sword_drawn=True)
        striker_actor.ruins = RuinsMind(striker_type, 8 if striker_type == 11 else 5, 1, 0)
        terrain = LevelMap(level)
        encounter = SimpleNamespace(player=player, terrain=terrain, player_frames=kid_frames,
                                    god_mode=False)
        creatures = RuinsCreatures(tension_level=1, tension=tension)
        event = creatures.stab_prince(striker_actor, encounter)
        port = dict(facing=0 if state.facing else -1, x=state.target_x + 207,
                    y=(row if player.row == row else player.row) * 120 + 106 + state.current_y
                    if player.row == row else None,
                    row=player.row, horizontal_velocity=0, vertical_velocity=0,
                    armed=int(player.sword_drawn), life=player.life, sequence=state.sequence_id,
                    cursor=state.cursor, selected=state.selected_sequence_id, special=0, alert=0)
        compared = [name for name in COMPARED if name not in ('y', 'horizontal_velocity',
                                                              'vertical_velocity', 'special',
                                                              'alert')]
        differences = {name: (native[name], port[name]) for name in compared
                       if native[name] != port[name]}
        if native_tension != creatures.tension:
            differences['tension'] = (native_tension, creatures.tension)
        port_method = event.death_method if event.kind == 'death' else 0
        if native_method != port_method:
            differences['death_method'] = (native_method, port_method)
        if sorted(machine.sounds) != sorted(state.sound_events):
            differences['sounds'] = (machine.sounds, state.sound_events)
        sequences[native['selected']] += 1
        sounds.update(machine.sounds)
        methods[native_method] += 1
        if differences:
            counts['mismatch'] += 1
            if len(mismatches) < 40:
                mismatches.append(dict(case=case, initial=initial, striker=striker,
                                       differences=differences))
        else:
            counts['match'] += 1
    return dict(
        cases=dict(counts), mismatches=counts['mismatch'],
        requested_sequences=dict(sorted(sequences.items())), sounds=dict(sorted(sounds.items())),
        death_methods=dict(sorted(methods.items())), examples=mismatches,
        executable_sha256=hashlib.sha256(program_bytes).hexdigest(),
        supplied=['AnimChar stand-in: SEQS 85 loads pose 179 on both sides', '5:4d84 AddSound: recorded',
                  'Kid FRAM/AFRM 25001 installed as the type-0 frame handles'],
        scope=('CheckStab 6:51f2 for the Prince (type 0) struck by a head (pose 167) or a '
               'serpent (pose 280), with its wall pushes, the unarmed and crouched reactions, '
               'fatal sequences and lost sword, DecLifePts, the ledge fall, the death branch '
               '6:5562, SetTensionLevel and SetKidDeathMethod, against '
               'pop2.ruins_ai.RuinsCreatures.stab_prince in random cells of level seven.'),
    )


class NativeRuinsStrike(NativeRuinsStab):
    RANGES = {
        **NativeRuinsStab.RANGES,
        6: NativeRuinsStab.RANGES[6] + ((0x5896, 0x5b28), (0x5b38, 0x5d46), (0x5d60, 0x5e2e),
                                        (0x5e42, 0x5eb6)),
        7: NativeRuinsStab.RANGES[7] + ((0x08fa, 0x0934),),
    }


def run_strike_probe(recovery, cases=20000, seed=2030):
    """CheckStrikes 6:5896 for ruins pairs against RuinsCreatures.contact/test_strike."""
    from pop2.combat import Fighter
    from pop2.ruins_ai import PrinceView, RuinsCreatures, RuinsMind
    from pop2.sequence_runtime import SequenceRuntime, SequenceState
    from pop2.terrain import LevelMap, floor_y

    directory = Path(recovery) / 'resource_forks'
    program_bytes = (directory / 'Prince of Persia 2.bin').read_bytes()
    program, prince_rsrc, head = (parse_resource_fork((directory / name).read_bytes()) for name in
                                  ('Prince of Persia 2.bin', 'Prince.rsrc.bin', 'Head.rsrc.bin'))
    level = prince_rsrc['LEVL'][2006]['data']
    machine = NativeRuinsStrike(program, head, prince_rsrc['SEQS'])
    slots = [(room, slot, offset, actor) for room, slot, offset, actor in head_slots(level)]
    slots += [(room, slot, offset, 11) for room, slot, offset in serpent_slots(level)]
    rng = random.Random(seed)
    counts, outcomes, mismatches = Counter(), Counter(), []
    for case in range(cases):
        room, slot, offset, ruins_type = rng.choice(slots)
        prince_strikes = rng.random() < 0.5
        row = rng.randrange(3)
        x = 207 + rng.randrange(1, 9) * 51 + rng.randrange(51)
        distance = rng.choice((-40, -20, -5, 0, 5, 20, 31, 32, 40, 55, 56, 62, 70, 79, 80,
                               92, 93, 99, 110, 126))
        if ruins_type == 11:
            ruins_pose = rng.choice((274, 280, 278, 230))
            ruins_selected = rng.choice((173, 171, 175, 170))
        else:
            ruins_pose = rng.choice((165, 166, 167, 181, 150, 154, 159))
            ruins_selected = rng.choice((147, 150, 151, 166, 140))
        prince_pose = rng.choice((153, 154, 244, 245, 161, 150, 157, 15) + (161, 150) * 3)
        prince_selected = rng.choice((75, 96, 2, 110))
        ruins = dict(facing=rng.choice((-1, 0)), x=x, row=row, actor=ruins_type, pose=ruins_pose,
                     selected=ruins_selected, armed=rng.choice((1, 1, 0)), alive=-1,
                     life=rng.choice((1, 3)), special=rng.choice((0, 1, 1, 6)),
                     y=row * 120 + (73 if ruins_type != 11 else 106) + rng.choice((0, 0, 20)),
                     room=room, slot=slot)
        prince = dict(facing=rng.choice((-1, 0)), row=row if rng.random() < 0.9 else (row + 1) % 3,
                      actor=0, pose=prince_pose, selected=prince_selected,
                      armed=rng.choice((1, 1, 0)), alive=rng.choice((-1, -1, -1, 0)),
                      life=rng.choice((3, 3, 0)), special=0, room=room, slot=0,
                      y=row * 120 + 106 + rng.choice((0, 0, -12, -20)), anim=rng.choice((0, 0, 8)))
        if prince['life'] == 0:
            # A Prince with no life whose death is not yet registered (ALIVE
            # still -1) lasts until his next control prefix 4:3d24; the port
            # has no such window, so it is not supplied.
            prince['alive'] = 0
        striker, defender = (prince, ruins) if prince_strikes else (ruins, prince)
        sign = 1 if striker['facing'] == 0 else -1
        striker['x'], defender['x'] = x, x + sign * distance
        sword_type = rng.choice((1, 2))
        parry_timer = rng.choice((0, 0, 3))

        machine.reset(level)
        machine.cpu.mem_write(machine.A5 - 0x5056, bytes(62))
        cached = bytearray(62)
        for name in ('facing', 'x', 'y', 'actor', 'pose', 'row', 'armed', 'alive', 'life',
                     'selected', 'special', 'room', 'slot'):
            machine.put_word(WORKING[name], striker[name])
        layout = dict(slot=0, facing=2, x=4, y=6, actor=8, pose=0xa, row=0xe, anim=0x10,
                      room=0x16, armed=0x1a, alive=0x1c, life=0x1e, selected=0x28, special=0x34)
        for name, field_offset in layout.items():
            if name in defender:
                struct.pack_into('>h', cached, field_offset, defender[name])
        machine.cpu.mem_write(machine.A5 - 0x5094, bytes(cached))
        machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(cached))
        machine.put_word(-0x500a, sword_type)
        machine.put_word(-0x369e, parry_timer)
        machine.random = Draws(case)
        machine.call(4, 0x2a8e) if striker['actor'] != 0 else None
        machine.call(6, 0x5896)
        native_hit = machine.word(-0x5084) == 10
        # 6:5a3c-5a58: a parry stores pose 161 and sets the parry timer to 4.
        native_parry = machine.word(-0x369e) == 4
        native_striker = dict(selected=machine.word(-0x502e), life=max(0, machine.word(-0x5038)
                                                                       + min(0, machine.word(-0x5034))))

        def fighter(values):
            state = SequenceState(values['selected'], action=values['pose'],
                                  target_x=values['x'] - 207, current_x=values['x'] - 207,
                                  current_y=values['y'] - floor_y(values['row']),
                                  facing=1 if values['facing'] == 0 else 0, actor_type=values['actor'],
                                  sequence_mode=values['special'], animation_state=values.get('anim', 0),
                                  selected_sequence_id=values['selected'])
            actor = Fighter(SequenceRuntime({}, state), values['life'], 3, room - 1, values['row'],
                            sword_drawn=values['armed'] == 1)
            actor.runtime.next_frame = lambda: None
            if values['actor'] != 0:
                actor.ruins = RuinsMind(values['actor'], 8 if values['actor'] == 11 else 5, 1, slot)
            if values['actor'] == 0 and values['alive'] >= 0:
                actor.life = 0  # Native ALIVE >= 0: the port's dead Prince.
            return actor

        port_striker, port_defender = fighter(striker), fighter(defender)
        player = port_striker if prince_strikes else port_defender
        encounter = SimpleNamespace(rng=TapeRandom(Draws(case)), terrain=LevelMap(level),
                                    player=player, parry_timer=parry_timer, guard_art=None)
        creatures = RuinsCreatures()
        ruins_actor = port_defender if prince_strikes else port_striker
        others = []
        base = 0x20e6 + room * 0xc0
        for index in range(struct.unpack_from('>H', level, base)[0]):
            words = struct.unpack_from('>19h', level, base + 2 + index * 38)
            others.append(ruins_actor if index == slot else SimpleNamespace(
                ruins=RuinsMind(0, words[12], words[3], index, mode=words[14])))
        ruins_actor.ruins.skill = struct.unpack_from('>h', level, offset + 6)[0]
        creatures.rooms[room - 1] = others
        view = PrinceView(0, prince['row'], prince['x'], prince['y'], prince['facing'],
                          prince['pose'], room - 1, prince['alive'], prince['life'],
                          prince['armed'] == 1, prince['selected'])
        creatures.prince = lambda _encounter: view
        result = (creatures.test_strike(port_striker, port_defender, encounter, sword_type)
                  if creatures.contact(port_striker, port_defender) else None)
        port_striker_after = dict(selected=port_striker.state.selected_sequence_id,
                                  life=port_striker.life)
        differences = {}
        if native_hit != (result == 'hit'):
            differences['hit'] = (native_hit, result)
        if native_parry != (result == 'parry'):
            differences['parry'] = (native_parry, result)
        if not prince_strikes and native_striker != port_striker_after:
            differences['striker'] = (native_striker, port_striker_after)
        outcomes['hit' if native_hit else 'parry' if native_parry else 'none'] += 1
        if differences:
            counts['mismatch'] += 1
            if len(mismatches) < 40:
                mismatches.append(dict(case=case, striker=striker, defender=defender,
                                       sword_type=sword_type, parry_timer=parry_timer,
                                       differences=differences))
        else:
            counts['match'] += 1
    return dict(
        cases=dict(counts), mismatches=counts['mismatch'], outcomes=dict(outcomes),
        examples=mismatches, executable_sha256=hashlib.sha256(program_bytes).hexdigest(),
        supplied=['4:2c0c AnimChar: skipped on both sides', '5:4d84 AddSound: recorded',
                  '17:6e06 Rnd: the same seeded outcomes'],
        scope=('CheckStrikes 6:5896 (IsStrikingPos, IsTheStrikePos, GetCharStrikeRanges, '
               'the parry and HeadHit 7:08fa) for a head or serpent against the Prince and the '
               'Prince against a head or serpent, against pop2.ruins_ai contact/test_strike. '
               'The miss sounds 11/239 are not compared.'),
    )


class NativeRuinsAnimation(NativeRuinsStab):
    RANGES = {
        **NativeRuinsStab.RANGES,
        4: NativeRuinsStab.RANGES[4] + ((0x2c0c, 0x3050), (0x305e, 0x308a), (0x30e0, 0x3194),
                                        (0x341a, 0x3462), (0x3464, 0x34e0), (0x48f8, 0x4970),
                                        (0x3afa, 0x3b24)),
    }
    TRAPS = {0xa029, 0xa02a, 0xa049, 0xa04a, 0xa069, 0xa06a}
    SEQUENCES = 0xc0000

    def __init__(self, program, head, sequences):
        super().__init__(program, head, sequences)
        self.sequence_handles = {}
        cursor = self.SEQUENCES + 0x1000
        for index, (key, item) in enumerate(sorted(sequences.items())):
            handle = self.SEQUENCES + index * 4
            self.cpu.mem_write(handle, struct.pack('>I', cursor))
            self.cpu.mem_write(cursor, item['data'])
            self.sequence_handles[key] = handle
            cursor += (len(item['data']) + 15) & ~15

    def dispatch(self, cpu, address, size, user):
        if address == self.address(4, 0x2c0c):
            self.animations += 1
            NativeRuinsHead.dispatch(self, cpu, address, size, user)
            return
        if address == self.address(4, 0x3098):
            self.skip(cpu, self.sequence_handles.get(self.argument(cpu), 0))
            return
        relative = address - self.CODE_BASE
        if 0 <= relative < 0x200000:
            opcode = struct.unpack('>H', cpu.mem_read(address, 2))[0]
            if opcode in self.TRAPS:
                # Memory-manager traps on the sequence handle are inert here.
                cpu.reg_write(self.registers['d0'], 0)
                cpu.reg_write(self.registers['pc'], address + 2)
                return
        super().dispatch(cpu, address, size, user)


ANIMATED = ('facing', 'x', 'y', 'row', 'pose', 'horizontal_velocity', 'vertical_velocity',
            'sequence', 'cursor', 'selected', 'special')


def run_animation_probe(recovery, cases=2000, seed=2031, frames=30):
    """AnimChar 4:2c0c, the gravity step 4:341a and MoveChar 4:3464 over whole
    head and serpent sequences against SequenceRuntime and RuinsCreatures' flight."""
    from pop2.animation_data import sequence_words
    from pop2.combat import Fighter
    from pop2.ruins_ai import RuinsCreatures, RuinsMind
    from pop2.sequence_runtime import SequenceRuntime, SequenceState
    from pop2.terrain import floor_y

    directory = Path(recovery) / 'resource_forks'
    program_bytes = (directory / 'Prince of Persia 2.bin').read_bytes()
    program, prince_rsrc, head = (parse_resource_fork((directory / name).read_bytes()) for name in
                                  ('Prince of Persia 2.bin', 'Prince.rsrc.bin', 'Head.rsrc.bin'))
    level = prince_rsrc['LEVL'][2006]['data']
    machine = NativeRuinsAnimation(program, head, prince_rsrc['SEQS'])
    sequences = {key: sequence_words(item['data']) for key, item in prince_rsrc['SEQS'].items()}
    head_ids = [key for key in range(130, 167) if key in sequences]
    serpent_ids = [key for key in range(168, 178) if key in sequences]
    rng = random.Random(seed)
    counts, started, removed, mismatches = Counter(), Counter(), 0, []
    for case in range(cases):
        actor_type = rng.choice((7, 8, 11))
        sequence = rng.choice(head_ids if actor_type != 11 else serpent_ids)
        row = rng.randrange(3)
        facing = rng.choice((-1, 0))
        x = 207 + rng.randrange(2, 8) * 51 + rng.randrange(51)
        pose = 150 if actor_type != 11 else 230
        y = row * 120 + (73 if actor_type != 11 else 106)
        initial = dict(slot=0, facing=facing, x=x, y=y, actor=actor_type, pose=pose, column=0,
                       row=row, horizontal_velocity=0, vertical_velocity=0, room=7, armed=1,
                       alive=-1, life=3, sequence=sequence, cursor=0, selected=sequence,
                       body_top=18, body_bottom=48, special=0, alert=0)
        draw_seed = rng.randrange(1 << 30)
        machine.reset(level)
        machine.cpu.mem_write(machine.A5 - 0x5056, bytes(62))
        for name, value in initial.items():
            machine.put_word(WORKING[name], value)
        machine.put_word(-0x5098, -1)
        machine.random = Draws(draw_seed)
        state = SequenceState(sequence, action=pose, current_x=x - 207, target_x=x - 207,
                              current_y=y - floor_y(row), facing=1 if facing == 0 else 0,
                              actor_type=actor_type, selected_sequence_id=sequence)
        runtime = SequenceRuntime(sequences, state)
        draws = Draws(draw_seed)
        runtime.rng = TapeRandom(draws)
        actor = Fighter(runtime, 3, 3, 6, row, sword_drawn=True)
        actor.ruins = RuinsMind(actor_type, 8 if actor_type == 11 else 5, 1, 0)
        creatures = RuinsCreatures()
        creatures.rooms[6] = [actor]
        creatures._wall_contact = lambda *_args: None
        encounter = SimpleNamespace(rng=TapeRandom(draws))
        started[sequence] += 1
        difference = None
        for frame in range(frames):
            machine.call(4, 0x2c0c)
            native_removed = machine.word(-0x5054) == 0x56
            if not native_removed:
                machine.call(4, 0x341a)
                machine.call(4, 0x3464)
            native = {name: machine.word(WORKING[name]) for name in ANIMATED}
            native['pose'] = machine.word(-0x504c)
            runtime.next_frame()
            creatures._after_frame(actor, encounter)
            port = dict(facing=0 if state.facing else -1, x=state.target_x + 207,
                        y=floor_y(actor.row) + state.current_y, row=actor.row, pose=state.action,
                        horizontal_velocity=state.horizontal_velocity,
                        vertical_velocity=state.vertical_velocity, sequence=state.sequence_id,
                        cursor=state.cursor, selected=state.selected_sequence_id,
                        special=state.sequence_mode)
            if native_removed or actor.ruins.removed:
                if native_removed != actor.ruins.removed:
                    difference = dict(frame=frame, removed=(native_removed, actor.ruins.removed))
                else:
                    removed += 1
                break
            keys = [name for name in ANIMATED if native[name] != port[name]]
            if keys:
                difference = dict(frame=frame, **{name: (native[name], port[name]) for name in keys})
                break
        if machine.sounds != [] and sorted(machine.sounds) != sorted(state.sound_events) and difference is None:
            difference = dict(sounds=(machine.sounds, state.sound_events))
        if machine.random.log != draws.log and difference is None:
            difference = dict(random=(machine.random.log, draws.log))
        if difference:
            counts['mismatch'] += 1
            if len(mismatches) < 40:
                mismatches.append(dict(case=case, initial=initial, differences=difference))
        else:
            counts['match'] += 1
    return dict(
        cases=dict(counts), mismatches=counts['mismatch'], removals=removed,
        requested_sequences=dict(sorted(started.items())), examples=mismatches,
        executable_sha256=hashlib.sha256(program_bytes).hexdigest(),
        supplied=['4:3098 hGetSequence: handles to the actual Prince SEQS bytes',
                  'HLock/HUnlock/HGetState/HSetState: inert', '17:6e06 Rnd: the same seeded outcomes',
                  '5:4d84 AddSound: recorded', '3:4a8e DrawOppMeter, 6:36f2: supplied'],
        scope=(f'Up to {frames} frames of AnimChar 4:2c0c, 4:341a and MoveChar 4:3464 from the '
               'start of every head (130-166) and serpent (168-177) sequence, against '
               'SequenceRuntime.next_frame and RuinsCreatures._after_frame (wall contact '
               'disabled). No controller runs between frames.'),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cases', type=int, default=20000)
    parser.add_argument('--serpents', action='store_true')
    parser.add_argument('--stab', action='store_true')
    parser.add_argument('--prince', action='store_true')
    parser.add_argument('--strike', action='store_true')
    parser.add_argument('--animation', action='store_true')
    args = parser.parse_args()
    report = (run_animation_probe if args.animation else run_strike_probe if args.strike else run_prince_probe if args.prince else run_stab_probe if args.stab else run_serpent_probe if args.serpents else run_probe)(
        args.source, args.cases)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('cases', 'requested_sequences', 'sounds', 'outcomes')
                      if key in report}, indent=2))


if __name__ == '__main__':
    main()
