"""Compare native level-11 mixed gate/rock links with an independent state model."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_temple_slide_rock_admission import NativeSlideRockAdmission, apply_object, link_chain
from tools.probe_temple_slide_rock_geometry import TempleCellReader
from tools.probe_temple_slide_rock_lifecycle import store_bank


def find_trob(bank, room, cell):
    return next((i for i, record in enumerate(bank) if record[:2] == (cell, room)), None)


def add_trob(state, room, cell, phase, kind):
    bank = list(state['trobs'])
    scratch = state['trob_scratch']
    found = find_trob(bank, room, cell)
    if found is not None:
        old = bank[found]
        bank[found] = (old[0], old[1], phase, old[3])
    elif len(bank) < 20:
        scratch = (cell, room, phase, kind)
        bank.append(scratch)
    storage = bytearray(state['trob_storage'])
    for i, record in enumerate(bank):
        struct.pack_into('>4h', storage, i * 8, *record)
    return dict(state, trobs=tuple(bank), trob_scratch=scratch, trob_storage=bytes(storage),
                events=state['events'] + [('trob', room, cell, phase, kind)])


def gate_reference(foreground, mode, trobs, room, cell, context):
    """Bounded working actor: kind zero, non-level-five (temple) IsDeadPos."""
    pose, alive, actor_room, transition_room = context
    position, decoration = foreground & 255, foreground & 0xff00
    if mode == 5:
        if position == 255:
            return foreground, -1
        permanent = alive >= 0 or (transition_room != 0 and actor_room != transition_room)
        if position >= 184:
            return decoration | (255 if permanent else 237), 3 if permanent else -1
        return decoration | ((position + 3) & 0xfc), 3 if permanent else 2
    if mode != 6:
        raise ValueError('Only source plate modes 5/6 are covered')
    dead_pose = pose in (185, 242, 243, 266, 271)
    if dead_pose and alive >= 2:
        return foreground, -1
    found = find_trob(trobs, room, cell)
    if (found is None and position == 0) or (found is not None and trobs[found][2] == 4):
        return foreground, -1
    return foreground, 4


def mixed_chain(state, reader, index, mode, context):
    if struct.unpack_from('>h', reader.level, 0x218a)[0] == 5:
        raise ValueError('Level-five special IsDeadPos branch is outside this model')
    for _, room, cell, kind in link_chain(reader.level, index):
        state = dict(state, events=state['events'] + [('object', kind, room, cell, mode)])
        if kind == 25:
            state = apply_object(state, reader, kind, room, cell, mode)
            state = dict(state, events=state['events'] + [('rock', room, cell, 2 if mode == 5 else 1)])
        elif kind == 4:
            offset = 0x780 + (room - 1) * 120 + cell * 4
            foreground = struct.unpack_from('>H', reader.level, offset)[0]
            foreground, phase = gate_reference(foreground, mode, state['trobs'], room, cell, context)
            level = bytearray(reader.level)
            struct.pack_into('>H', level, offset, foreground)
            reader.level = level
            state = dict(state, object_calls=state['object_calls'] + [(kind, room, cell, mode)])
            if phase >= 0:
                state = add_trob(state, room, cell, phase, kind)
        else:
            raise ValueError('Only mixed gate/rock chains are covered')
    return state


def held_mixed_plate(state, reader, room, cell, context):
    kind, foreground, cached_cell, cached_room, _, _ = reader.cache
    if (cached_room, cached_cell) != (room, cell) or kind not in (5, 6):
        raise ValueError('Read an admitted source plate first')
    index = foreground & 255
    timer_offset = 0x1680 + index * 10 + 4
    timer = struct.unpack_from('>h', reader.level, timer_offset)[0]
    if timer < 2:
        raise ValueError('Fresh plate setup is not covered')
    level = bytearray(reader.level)
    if timer != 31:
        struct.pack_into('>h', level, timer_offset, 5)
    reader.level = level
    state = mixed_chain(state, reader, index, kind, context)
    level = bytearray(reader.level)
    struct.pack_into('>H', level, 0x780 + (room - 1) * 120 + cell * 4, (foreground | 0x2000) & 65535)
    reader.level = level
    return state


class NativeMixedPlateLinks(NativeSlideRockAdmission):
    RANGES = NativeSlideRockAdmission.RANGES | {
        4: NativeSlideRockAdmission.RANGES[4] + ((0x47a0, 0x48e8),),
        5: NativeSlideRockAdmission.RANGES[5] + (
            (0x1d50, 0x1eb6), (0x20a0, 0x2104), (0x38a6, 0x38ea)),
    }

    def clear_events(self):
        super().clear_events()
        self.events = []

    def dispatch(self, cpu, address, size, user):
        for segment, offset, count, name in ((5, 0x1ec8, 4, 'object'),
                                             (10, 0x2152, 3, 'rock'),
                                             (5, 0x20a0, 4, 'trob')):
            if address == self.address(segment, offset):
                stack = cpu.reg_read(self.registers['a7'])
                args = struct.unpack('>' + 'h' * count, cpu.mem_read(stack + 4, count * 2))
                self.events.append((name, *args))
        super().dispatch(cpu, address, size, user)


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    resources = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    original = resources['LEVL'][2010]['data']
    if struct.unpack_from('>3h', original, 0x2186)[::2] != (2, 11):
        raise ValueError('Expected original temple level 11')
    chains = {cell: link_chain(original, index) for cell, index in ((15, 54), (16, 51))}
    if chains != {15: [(54, 3, 2, 4), (50, 3, 18, 25)],
                  16: [(51, 3, 18, 25), (52, 3, 2, 4)]}:
        raise ValueError(('Unexpected original link chains', chains))
    machine = NativeMixedPlateLinks(parse_resource_fork(executable))
    counts, digest = Counter(), hashlib.sha256()
    canary = bytes((i * 37 + 11) % 256 for i in range(512))
    trob_canary = bytes((i * 19 + 7) % 256 for i in range(160))
    scratch = (11, 13, 17, 19, 23, 29, 31, 37)
    rock = (408, 236, 3, 0, -2, 6, 1, 408)
    filler = (0, 116, 4, 0, 2, 6, 0, 0)
    banks = ((), (rock,), ((*rock[:4], 2, *rock[5:]),),
             ((*rock[:4], 100, *rock[5:]),), (filler,) * 30)
    other = (9, 4, 1, 6)
    trob_banks = ((), ((2, 3, 2, 4),), ((2, 3, 4, 4),),
                  ((2, 3, -1, 99), (2, 3, 4, 4)),
                  (other,) * 19, (other,) * 20,
                  (other,) * 19 + ((2, 3, 2, 4),))
    contexts = ((0, -1, 3, 0), (0, -1, 3, 3), (0, -1, 3, 4),
                (0, 0, 3, 0), (0, 2, 3, 0), (185, 1, 3, 0),
                (185, 2, 3, 0), (242, 2, 3, 0))

    def prepare(level, bank, trobs, context):
        machine.reset(level)
        machine.put_word(-0x4fc2, 3)
        machine.put_word(-0x439e, 1234)
        machine.put_word(-0x4f9e, 4321)
        actor = bytearray((i * 11 + 3) % 256 for i in range(62))
        for offset, value in ((8, 0), (10, context[0]), (22, context[2]), (28, context[1])):
            struct.pack_into('>h', actor, offset, value)
        machine.cpu.mem_write(machine.A5 - 0x5056, bytes(actor))
        machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(actor))
        machine.put_word(-0x4fc4, context[3])
        storage = bytearray(trob_canary)
        for i, record in enumerate(trobs):
            struct.pack_into('>4h', storage, i * 8, *record)
        state = dict(mob=scratch, bank=tuple(bank), bank_storage=store_bank(canary, bank),
                     trobs=tuple(trobs), trob_storage=bytes(storage), trob_scratch=(41, 43, 47, 53),
                     object_calls=[], rock_calls=[], events=[])
        machine.cpu.mem_write(machine.A5 - 0x44a6, struct.pack('>8h', *scratch))
        machine.cpu.mem_write(machine.BANK - 16, state['bank_storage'])
        machine.cpu.mem_write(machine.A5 - 0x4496, struct.pack('>I', machine.BANK))
        machine.put_word(-0x4490, len(bank))
        machine.cpu.mem_write(machine.A5 - 0x448e, state['trob_storage'])
        machine.cpu.mem_write(machine.A5 - 0x43ee, struct.pack('>4h', *state['trob_scratch']))
        machine.put_word(-0x43e6, len(trobs))
        return state, TempleCellReader(level, 3), bytes(actor)

    def check(state, reader, actor, label, context):
        actual = dict(mob=struct.unpack('>8h', machine.cpu.mem_read(machine.A5 - 0x44a6, 16)),
                      bank=tuple(struct.unpack('>8h', machine.cpu.mem_read(machine.BANK + i * 16, 16))
                                 for i in range(machine.word(-0x4490))),
                      bank_storage=bytes(machine.cpu.mem_read(machine.BANK - 16, 512)),
                      trobs=tuple(struct.unpack('>4h', machine.cpu.mem_read(machine.A5 - 0x448e + i * 8, 8))
                                  for i in range(machine.word(-0x43e6))),
                      trob_storage=bytes(machine.cpu.mem_read(machine.A5 - 0x448e, 160)),
                      trob_scratch=struct.unpack('>4h', machine.cpu.mem_read(machine.A5 - 0x43ee, 8)),
                      object_calls=machine.object_calls, rock_calls=machine.rock_calls, events=machine.events)
        if (actual != state or machine.level_bytes(len(reader.level)) != reader.level
                or machine.reads != reader.requests or machine.cache() != reader.cache
                or bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)) != actor
                or bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62)) != actor
                or machine.word(-0x439e) != 1234 or machine.word(-0x4f9e) != 4321
                or machine.services):
            raise AssertionError(dict(label=label, context=context,
                                      differences={key: (actual[key], state[key]) for key in state
                                                   if actual[key] != state[key]},
                                      level_changed=machine.level_bytes(len(reader.level)) != reader.level,
                                      cache=(machine.cache(), reader.cache), reads=(machine.reads, reader.requests)))
        counts[label] += 1
        digest.update(bytes(reader.level) + actual['bank_storage'] + actual['trob_storage'])
        digest.update(json.dumps([actual['mob'], actual['trob_scratch'], actual['events'],
                                 len(actual['bank']), len(actual['trobs']), machine.cache(), machine.reads]).encode('ascii'))

    # Keep original link order, varying supplied bank/actor/foreground inputs only.
    for cell, position, context, trobs, bank in product(
            (15, 16), (0, 1, 180, 183, 184, 237, 254, 255), contexts, trob_banks, banks):
        level = bytearray(original)
        struct.pack_into('>H', level, 0x780 + 2 * 120 + 2 * 4, 0xa500 | position)
        state, reader, actor = prepare(level, bank, trobs, context)
        index, mode = (54, 6) if cell == 15 else (51, 5)
        state = mixed_chain(state, reader, index, mode, context)
        machine.call(5, 0x1c4c, (index, mode))
        check(state, reader, actor, 'original_mixed_chains', (cell, position, context, len(trobs), len(bank)))

    # Every foreground low byte, preserving high-byte decoration, through both chains.
    for cell, position, context in product((15, 16), range(256), contexts):
        level = bytearray(original)
        struct.pack_into('>H', level, 0x780 + 2 * 120 + 2 * 4, 0x5a00 | position)
        state, reader, actor = prepare(level, (), (), context)
        index, mode = (54, 6) if cell == 15 else (51, 5)
        state = mixed_chain(state, reader, index, mode, context)
        machine.call(5, 0x1c4c, (index, mode))
        check(state, reader, actor, 'all_gate_position_bytes', (cell, position, context))

    for cell, timer, trobs, bank in product((15, 16), (2, 5, 31), trob_banks, banks):
        level = bytearray(original)
        index = 54 if cell == 15 else 51
        struct.pack_into('>h', level, 0x1680 + index * 10 + 4, timer)
        context = contexts[0]
        state, reader, actor = prepare(level, bank, trobs, context)
        for repetition in range(3):
            machine.clear_events()
            reader.requests.clear()
            state = dict(state, object_calls=[], rock_calls=[], events=[])
            reader.read(3, cell % 10, cell // 10)
            machine.call(4, 0x27ee, (3, cell % 10, cell // 10))
            state = held_mixed_plate(state, reader, 3, cell, context)
            machine.call(5, 0x240c, (0, -1))
            check(state, reader, actor, 'repeated_held_mixed_plate', (cell, timer, repetition, len(trobs), len(bank)))

    return dict(cases=dict(counts), mismatches=0, chains=chains, supplied_services=[],
                outputs_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(executable).hexdigest(),
                level_sha256=hashlib.sha256(original).hexdigest(),
                scope=('Native Trigger/TriggerObject/TriggerGate/AddTrob/GetTrobRoomCell and rock activation, '
                       'plus held PushPlate on both original level11 room3 chains. Native IsDeadPos with '
                       'supplied kind-zero working actor contexts. Entire level, MOB/TROB banks including unused '
                       'storage, scratch, call order, cache, actor and audio/redraw canaries checked. No services '
                       'supplied. No fresh plate setup, actual actor admission, gate/rock animation, FrameAdv, '
                       'rendering, save/reset or campaign equivalence. Other actor kinds and gate modes excluded.'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='ascii')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
