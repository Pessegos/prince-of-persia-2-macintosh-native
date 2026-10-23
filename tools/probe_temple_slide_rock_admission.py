"""Recover tile-25 caller modes and bounded original pressure-link/held-plate paths."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_sequence_selection import signed_word
from tools.probe_temple_slide_rock_geometry import TempleCellReader
from tools.probe_temple_slide_rock_lifecycle import store_bank
from tools.probe_temple_slide_rock_trigger import NativeSlideRockTrigger, bank_cases, trigger_reference


def object_reference(kind, room, cell, mode, bank):
    if not 0 <= kind <= 65535 or not -32768 <= mode <= 32767:
        raise ValueError('Expected unsigned tile and signed caller-mode words')
    if kind in (4, 17, 27, 33):
        raise ValueError('Other active mechanism bodies are outside this probe')
    if kind == 25:
        how = 2 if mode == 5 else 1
        result = trigger_reference(room, cell, how, bank)
        return dict(result, how=how, result=-1)
    return dict(bank=tuple(bank), scratch=None, selected=None, appended=False, how=None, result=-1)


def link_chain(level, index):
    seen, targets = set(), []
    while index != -3:
        if not 0 <= index < 256 or index in seen:
            raise ValueError('Invalid or cyclic pressure-link fixture')
        seen.add(index)
        room, cell, _timer, _previous, following = struct.unpack_from('>5h', level, 0x1680 + index * 10)
        if room == -2 and not targets:
            return targets
        if not 1 <= room <= 32 or not 0 <= cell < 30:
            raise ValueError('Unassigned interior or invalid target outside the bounded chain domain')
        kind = struct.unpack_from('>H', level, (room - 1) * 60 + cell * 2)[0]
        targets.append((index, room, cell, kind))
        index = following
    return targets


def apply_object(state, reader, kind, room, cell, mode):
    result = object_reference(kind, room, cell, mode, state['bank'])
    state = dict(state, bank=result['bank'],
                 object_calls=state['object_calls'] + [(kind, room, cell, mode)],
                 rock_calls=state['rock_calls'] + ([] if result['how'] is None else [(room, cell, result['how'])]))
    if result['scratch'] is not None:
        reader.read(room, cell % 10, cell // 10)
        state['mob'] = result['scratch']
    state['bank_storage'] = store_bank(state['bank_storage'], state['bank'])
    return state


def apply_chain(state, reader, index, mode):
    for _, room, cell, kind in link_chain(reader.level, index):
        state = apply_object(state, reader, kind, room, cell, mode)
    return state


def held_plate_reference(state, reader, room, cell):
    kind, foreground, cached_cell, cached_room, _, _ = reader.cache
    if (cached_room, cached_cell) != (room, cell) or kind not in (5, 6, 34):
        raise ValueError(('Read the source plate before invoking PushPlate defaults', room, cell, reader.cache))
    index = foreground & 255
    timer_offset = 0x1680 + index * 10 + 4
    timer = struct.unpack_from('>h', reader.level, timer_offset)[0]
    if timer < 2:
        raise ValueError('Fresh plate redraw/audio/TROB setup is outside this probe')
    level = bytearray(reader.level)
    if timer != 31:
        struct.pack_into('>h', level, timer_offset, 5)
    reader.level = level
    state = apply_chain(state, reader, index, kind)
    struct.pack_into('>H', level, 0x780 + (room - 1) * 120 + cell * 4, (foreground | 0x2000) & 65535)
    return state, bytes(level)


class NativeSlideRockAdmission(NativeSlideRockTrigger):
    RANGES = NativeSlideRockTrigger.RANGES | {
        5: NativeSlideRockTrigger.RANGES[5] + (
            (0x1c4c, 0x1cda), (0x1ec8, 0x1fe6), (0x2238, 0x2266),
            (0x2278, 0x22a6), (0x22b8, 0x22ee), (0x2304, 0x2332),
            (0x23ce, 0x23fa), (0x240c, 0x251e)),
    }

    def reset(self, level):
        super().reset(level)
        for offset in (-0x34b0, -0x34ae, -0x34ac):
            self.put_word(offset, 0)
        self.clear_events()

    def clear_events(self):
        self.reads, self.object_calls, self.rock_calls = [], [], []

    def cache(self):
        return struct.unpack('>6h', self.cpu.mem_read(self.A5 - 0x34b0, 12))

    def dispatch(self, cpu, address, size, user):
        for segment, offset, count, name in ((4, 0x27ee, 3, 'reads'),
                                             (5, 0x1ec8, 4, 'object_calls'),
                                             (10, 0x2152, 3, 'rock_calls')):
            if address == self.address(segment, offset):
                stack = cpu.reg_read(self.registers['a7'])
                values = struct.unpack('>' + 'h' * count, cpu.mem_read(stack + 4, count * 2))
                if name == 'object_calls':
                    values = (values[0] & 65535, *values[1:])
                getattr(self, name).append(values)
        super().dispatch(cpu, address, size, user)


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    machine = NativeSlideRockAdmission(parse_resource_fork(executable))
    counts, inventory, excluded, out_of_range, hashes = Counter(), [], [], [], {}
    digest = hashlib.sha256()
    canary = bytes((i * 37 + 11) % 256 for i in range(512))
    actor = bytes((i * 11 + 3) % 256 for i in range(62))
    scratch = (11, 13, 17, 19, 23, 29, 31, 37)
    modes = (-32768, 0, 5, 6, 34, 32767)

    def prepare(level, room, bank, foreground=0):
        machine.reset(level)
        reader = TempleCellReader(level, room)
        reader.cache = (0, foreground, 0, 0, -32768, -32768)
        machine.put_word(-0x34ae, foreground)
        machine.put_word(-0x4fc2, room)
        machine.put_word(-0x439e, 1234)
        machine.put_word(-0x43e6, 19)
        state = dict(mob=scratch, bank=tuple(bank), bank_storage=store_bank(canary, bank),
                     object_calls=[], rock_calls=[])
        machine.cpu.mem_write(machine.A5 - 0x44a6, struct.pack('>8h', *scratch))
        machine.cpu.mem_write(machine.A5 - 0x5056, actor)
        machine.cpu.mem_write(machine.A5 - 0x50d2, actor)
        machine.cpu.mem_write(machine.BANK - 16, state['bank_storage'])
        machine.cpu.mem_write(machine.A5 - 0x4496, struct.pack('>I', machine.BANK))
        machine.put_word(-0x4490, len(bank))
        return state, reader

    def check(level, reader, state, label, context):
        actual = dict(mob=struct.unpack('>8h', machine.cpu.mem_read(machine.A5 - 0x44a6, 16)),
                      bank=tuple(struct.unpack('>8h', machine.cpu.mem_read(machine.BANK + i * 16, 16))
                                 for i in range(machine.word(-0x4490))),
                      bank_storage=bytes(machine.cpu.mem_read(machine.BANK - 16, 512)),
                      object_calls=machine.object_calls, rock_calls=machine.rock_calls)
        if (actual != state or machine.word(-0x4490) != len(state['bank'])
                or machine.level_bytes(len(level)) != level
                or machine.reads != reader.requests or machine.cache() != reader.cache
                or bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)) != actor
                or bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62)) != actor
                or machine.word(-0x439e) != 1234 or machine.word(-0x43e6) != 19
                or machine.services):
            raise AssertionError(dict(label=label, context=context,
                                      different=[key for key in state if actual[key] != state[key]],
                                      reads=machine.reads, expected_reads=reader.requests,
                                      cache=machine.cache(), expected_cache=reader.cache,
                                      level_changed=machine.level_bytes(len(level)) != level))
        counts[label] += 1
        digest.update(level + actual['bank_storage'] + struct.pack('>8h', *actual['mob']))
        digest.update(json.dumps([actual['object_calls'], actual['rock_calls'],
                                 machine.reads, machine.cache()]).encode('ascii'))

    for number in range(10, 14):
        level = prince['LEVL'][1999 + number]['data']
        if (struct.unpack_from('>H', level, 0x2186)[0] != 2
                or struct.unpack_from('>H', level, 0x218a)[0] != number):
            raise ValueError('Inconsistent temple level fixture')
        hashes[str(number)] = hashlib.sha256(level).hexdigest()
        for room in range(1, 33):
            for cell in range(30):
                kind = struct.unpack_from('>H', level, (room - 1) * 60 + cell * 2)[0]
                if kind == 25:
                    for (label, bank), mode, flags in product(bank_cases(room, cell // 10), modes, (0, 0x2000)):
                        state, reader = prepare(level, room, bank, flags)
                        state = apply_object(state, reader, 25, room, cell, mode)
                        returned = signed_word(machine.call(5, 0x1ec8, (25, room, cell, mode)))
                        if returned != -1:
                            raise AssertionError('Sliding rock unexpectedly requested a TROB')
                        check(level, reader, state, 'actual_anchor_dispatch', (number, room, cell, label, mode, flags))
                if kind not in (5, 6, 34):
                    continue
                foreground = struct.unpack_from('>H', level, 0x780 + (room - 1) * 120 + cell * 4)[0]
                index = foreground & 255
                chain = link_chain(level, index)
                if not any(target[3] == 25 for target in chain):
                    continue
                entry = dict(level=number, room=room, cell=cell, kind=kind, index=index, targets=chain)
                inventory.append(entry)
                state, reader = prepare(level, room, ())
                read_kind = reader.read(room, cell % 10, cell // 10)
                native_kind = machine.call(4, 0x27ee, (room, cell % 10, cell // 10))
                if native_kind != read_kind:
                    raise AssertionError('Native source-plate lookup differs')
                check(level, reader, state, 'source_plate_lookup', (number, room, cell))
                if read_kind != kind:
                    out_of_range.append(dict(entry, read_kind=read_kind,
                                             declared_rooms=struct.unpack_from('>H', level, 0x2180)[0]))
                if any(target[3] in (4, 17, 27, 33) for target in chain):
                    excluded.append(entry)
                    continue
                target = next(t for t in chain if t[3] == 25)
                tr, tc = target[1:3]
                row, col = divmod(tc, 10)
                existing = (col * 51, 116 + row * 120, tr, 0, -2, 6, row, col * 51)
                banks = ((), (existing,), ((*existing[:4], 2, *existing[5:]),),
                         ((*existing[:4], 100, *existing[5:]),),
                         ((0, 116, tr % 32 + 1, 0, 2, 6, 0, 0),) * 30)
                for bank, mode, flags in product(banks, (5, 6, 34), (0, 0x2000)):
                    state, reader = prepare(level, room, bank, flags)
                    state = apply_chain(state, reader, index, mode)
                    machine.call(5, 0x1c4c, (index, mode))
                    check(level, reader, state, 'actual_rock_only_chains', (number, room, cell, mode, flags))
                if read_kind != kind:
                    continue
                for bank, timer, depressed in product(banks, (2, 5, 31), (False, True)):
                    mutable = bytearray(level)
                    struct.pack_into('>h', mutable, 0x1680 + index * 10 + 4, timer)
                    offset = 0x780 + (room - 1) * 120 + cell * 4
                    struct.pack_into('>H', mutable, offset, foreground | (0x2000 if depressed else 0))
                    current = bytes(mutable)
                    state, reader = prepare(current, room, bank)
                    for repetition in range(3):
                        machine.clear_events()
                        reader.requests.clear()
                        state = dict(state, object_calls=[], rock_calls=[])
                        reader.read(room, cell % 10, cell // 10)
                        machine.call(4, 0x27ee, (room, cell % 10, cell // 10))
                        state, current = held_plate_reference(state, reader, room, cell)
                        machine.call(5, 0x240c, (0, -1))
                        check(current, reader, state, 'repeated_held_plate',
                              (number, room, cell, timer, depressed, repetition))

    level = prince['LEVL'][2009]['data']
    for kind, mode in product((0, 1, 5, 6, 24, 26, 43, 65535), modes):
        bank = ((306, 236, 28, 0, 2, 6, 1, 306),)
        state, reader = prepare(level, 28, bank)
        state = apply_object(state, reader, kind, 28, 16, mode)
        if signed_word(machine.call(5, 0x1ec8, (kind, 28, 16, mode))) != -1:
            raise AssertionError('Default object dispatch did not return -1')
        check(level, reader, state, 'unhandled_kind_controls', (kind, mode))

    # A supplied chain checks both row-distinct creation and repeat reuse.
    for mode in (5, 6, 34):
        mutable = bytearray(level)
        for index, cell in enumerate((16, 29, 16), 248):
            struct.pack_into('>5h', mutable, 0x1680 + index * 10,
                             28, cell, 0, -3, index + 1 if index < 250 else -3)
        state, reader = prepare(mutable, 28, ())
        state = apply_chain(state, reader, 248, mode)
        machine.call(5, 0x1c4c, (248, mode))
        check(mutable, reader, state, 'supplied_multi_target_chain', mode)
        if len(state['bank']) != (0 if mode == 5 else 2):
            raise AssertionError('Unexpected creation/reuse across linked rows')

    return dict(
        cases=dict(counts), resource_plate_chains=inventory, excluded_mixed_chains=excluded,
        out_of_range_source_plates=out_of_range,
        mismatches=0, outputs_sha256=digest.hexdigest(), level_hashes=hashes,
        executable_sha256=hashlib.sha256(executable).hexdigest(), supplied_services=[],
        scope=('Full native TriggerObject tile25/default dispatch, TriggerSlideRock lookup/creation, '
               'Trigger link traversal on six resource rock-only plate chains and a supplied multi-target '
               'chain; PushPlate held/permanent timer branches on five in-range sources across repeated calls. Original level '
               'and bank writes, actor canaries, cache, call arguments/order and TROB/audio counters '
               'checked. Caller mode5 maps to rock how2; other tested words map to how1; return-1 '
               'does not request AddTrob and does not stop link traversal. No native services supplied. '
               'Level12 raw room29 plate reads as wall because declared room count is26; no held-plate '
               'simulation is claimed for it. Fresh timer<2 PushPlate redraw/audio/TROB setup, two mixed gate/rock chains, actual '
               'actor pressure admission, motion, FrameAdv, saves or campaign parity remain excluded.'),
    )


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
