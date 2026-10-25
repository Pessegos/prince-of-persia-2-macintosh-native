"""Connect native temple press, held refresh, release, compaction and re-press."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_temple_fresh_plate_setup import NativeFreshPlateSetup, plate_reference, source_fixtures
from tools.probe_temple_mixed_plate_links import NativeMixedPlateLinks
from tools.probe_temple_plate_release import NativePlateRelease, animate_bank
from tools.probe_temple_slide_rock_admission import link_chain
from tools.probe_temple_slide_rock_geometry import TempleCellReader
from tools.probe_temple_slide_rock_lifecycle import store_bank


PLANS = {
    'tap-release-repress': ('press',) + ('animate',) * 7 + ('press',) + ('animate',) * 7,
    'held-refresh': ('press', 'animate') * 8 + ('animate',) * 6 + ('press',) + ('animate',) * 5,
    'animation-before-pressure': ('animate', 'press') * 8 + ('animate',) * 6 + ('press',) + ('animate',) * 5,
}


def lifetime_step(state, reader, operation, context, room, cell):
    if operation == 'press':
        reader.read(room, cell % 10, cell // 10)
        return plate_reference(state, reader, context)
    if operation != 'animate':
        raise ValueError('Expected a supplied press or animation operation')
    result = animate_bank(dict(level=bytes(reader.level), trobs=state['trobs'],
                               trob_storage=state['trob_storage'], scratch=state['trob_scratch'],
                               os=state['os'], events=[]))
    reader.level = result['level']
    events = [('release_redraw', *event[1:]) if event[0] == 'redraw' else event for event in result['events']]
    return dict(state, trobs=result['trobs'], trob_storage=result['trob_storage'],
                trob_scratch=result['scratch'], os=result['os'], events=state['events'] + events)


class NativePlateLifetime(NativeFreshPlateSetup):
    RANGES = NativeFreshPlateSetup.RANGES | {
        5: NativeFreshPlateSetup.RANGES[5] + NativePlateRelease.RANGES[5],
    }

    def dispatch(self, cpu, address, size, user):
        if address == self.address(5, 0x0cd6):
            stack = cpu.reg_read(self.registers['a7'])
            index = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
            record = struct.unpack('>4h', cpu.mem_read(self.A5 - 0x43ee, 8))
            self.events.append(('visit', index, *record))
        elif address == self.address(5, 0x0f38) and self.operation == 'animate':
            cell, room, _phase, _kind = struct.unpack('>4h', cpu.mem_read(self.A5 - 0x43ee, 8))
            foreground = self.word(-0x4818) & 65535
            timer = struct.unpack('>h', cpu.mem_read(self.LEVEL + 0x1680 + (foreground & 255) * 10 + 4, 2))[0]
            self.events.append(('release_redraw', room, cell, foreground, timer))
            # Release redraw uses TROB scratch/OS, not PushPlate's ReadCell cache.
            NativeMixedPlateLinks.dispatch(self, cpu, address, size, user)
            return
        super().dispatch(cpu, address, size, user)


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    resources = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    fixtures, excluded = source_fixtures(resources)
    fixtures = [entry for entry in fixtures if entry[0].startswith('original')
                and all(target[3] == 25 for target in link_chain(
                    entry[1], struct.unpack_from('>H', entry[1], 0x780 + (entry[2] - 1) * 120 + entry[3] * 4)[0] & 255))]
    if len(fixtures) != 5:
        raise ValueError(('Expected five original admitted rock-only sources', fixtures))
    machine = NativePlateLifetime(parse_resource_fork(executable))
    counts, services, outcomes, digest = Counter(), Counter(), Counter(), hashlib.sha256()
    canary = bytes((i * 37 + 11) % 256 for i in range(512))
    scratch = (11, 13, 17, 19, 23, 29, 31, 37)
    for label, original, room, cell in fixtures:
        offset = 0x780 + (room - 1) * 120 + cell * 4
        foreground = struct.unpack_from('>H', original, offset)[0]
        index = foreground & 255
        tr, tc = link_chain(original, index)[0][1:3]
        row, col = divmod(tc, 10)
        rock = (col * 51, 116 + row * 120, tr, 0, -2, 6, row, col * 51)
        filler = (9, room % 32 + 1, 1, 1)
        trobs = ((), (filler,) * 19, (filler,) * 20,
                 ((cell, room, -1, 6),) + (filler,) * 19)
        banks = ((), (rock,), ((*rock[:4], 2, *rock[5:]),),
                 ((*rock[:4], 100, *rock[5:]),),
                 ((0, 116, tr % 32 + 1, 0, 2, 6, 0, 0),) * 30)
        for (plan_name, plan), timer, bank, trob_bank in product(PLANS.items(), (0, 31), banks, trobs):
            level = bytearray(original)
            struct.pack_into('>h', level, 0x1680 + index * 10 + 4, timer)
            struct.pack_into('>H', level, offset, foreground & ~0x2000)
            machine.reset(level)
            machine.operation = 'press'
            context = (0, -1, room, 0)
            actor = bytearray((i * 11 + 3) % 256 for i in range(62))
            for location, value in ((8, 0), (10, 0), (22, room), (28, -1)):
                struct.pack_into('>h', actor, location, value)
            machine.cpu.mem_write(machine.A5 - 0x5056, bytes(actor))
            machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(actor))
            machine.put_word(-0x4fc2, room)
            machine.put_word(-0x4fc4, 0)
            machine.put_word(-0x439e, 1234)
            machine.put_word(-0x4f9e, 4321)
            storage = bytearray((i * 19 + 7) % 256 for i in range(160))
            for i, record in enumerate(trob_bank):
                struct.pack_into('>4h', storage, i * 8, *record)
            state = dict(mob=scratch, bank=tuple(bank), bank_storage=store_bank(canary, bank),
                         trobs=tuple(trob_bank), trob_storage=bytes(storage), trob_scratch=(41, 43, 47, 53),
                         os=bytes((11, 13, 17, 19, 23, 29)),
                         object_calls=[], rock_calls=[], events=[], press_flag=4321)
            machine.cpu.mem_write(machine.A5 - 0x44a6, struct.pack('>8h', *scratch))
            machine.cpu.mem_write(machine.BANK - 16, state['bank_storage'])
            machine.cpu.mem_write(machine.A5 - 0x4496, struct.pack('>I', machine.BANK))
            machine.put_word(-0x4490, len(bank))
            machine.cpu.mem_write(machine.A5 - 0x448e, state['trob_storage'])
            machine.cpu.mem_write(machine.A5 - 0x43ee, struct.pack('>4h', *state['trob_scratch']))
            machine.cpu.mem_write(machine.A5 - 0x4818, state['os'])
            machine.put_word(-0x43e6, len(trob_bank))
            reader = TempleCellReader(level, room)
            for step, operation in enumerate(plan):
                machine.clear_events()
                machine.services.clear()
                machine.operation = operation
                reader.requests.clear()
                state = dict(state, object_calls=[], rock_calls=[], events=[])
                state = lifetime_step(state, reader, operation, context, room, cell)
                if operation == 'press':
                    machine.call(4, 0x27ee, (room, cell % 10, cell // 10))
                    machine.call(5, 0x240c, (0, -1))
                else:
                    machine.call(5, 0x0c38)
                mob_count, trob_count = machine.word(-0x4490), machine.word(-0x43e6)
                if not 0 <= mob_count <= 30 or not 0 <= trob_count <= 20:
                    raise AssertionError(('Invalid bank count', mob_count, trob_count))
                actual = dict(mob=struct.unpack('>8h', machine.cpu.mem_read(machine.A5 - 0x44a6, 16)),
                              bank=tuple(struct.unpack('>8h', machine.cpu.mem_read(machine.BANK + i * 16, 16))
                                         for i in range(mob_count)),
                              bank_storage=bytes(machine.cpu.mem_read(machine.BANK - 16, 512)),
                              trobs=tuple(struct.unpack('>4h', machine.cpu.mem_read(machine.A5 - 0x448e + i * 8, 8))
                                          for i in range(trob_count)),
                              trob_storage=bytes(machine.cpu.mem_read(machine.A5 - 0x448e, 160)),
                              trob_scratch=struct.unpack('>4h', machine.cpu.mem_read(machine.A5 - 0x43ee, 8)),
                              os=bytes(machine.cpu.mem_read(machine.A5 - 0x4818, 6)),
                              object_calls=machine.object_calls, rock_calls=machine.rock_calls,
                              events=machine.events, press_flag=machine.word(-0x4f9e))
                expected_services = Counter('audio_request' if event[0] == 'sound' else 'plate_redraw'
                                            for event in state['events']
                                            if event[0] in ('sound', 'redraw', 'release_redraw'))
                if (actual != state or machine.services != expected_services
                        or machine.level_bytes(len(reader.level)) != reader.level
                        or machine.reads != reader.requests or machine.cache() != reader.cache
                        or bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)) != actor
                        or bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62)) != actor
                        or machine.word(-0x439e) != 1234):
                    raise AssertionError(dict(label=label, plan=plan_name, step=step, operation=operation,
                                              initial=(timer, len(bank), len(trob_bank)),
                                              differences={key: (actual[key], state[key]) for key in state
                                                           if actual[key] != state[key]},
                                              cache=(machine.cache(), reader.cache), services=machine.services))
                counts[operation] += 1
                services.update(machine.services)
                digest.update(bytes(reader.level) + actual['bank_storage'] + actual['trob_storage'] + actual['os'])
                digest.update(json.dumps([actual['events'], actual['press_flag'], actual['mob'], actual['trob_scratch'],
                                         mob_count, trob_count, machine.cache(), machine.reads]).encode('ascii'))
            counts['traces'] += 1
            final_timer = struct.unpack_from('>h', reader.level, 0x1680 + index * 10 + 4)[0]
            final_foreground = struct.unpack_from('>H', reader.level, offset)[0]
            outcomes['depressed_without_trob'] += bool(final_foreground & 0x2000) and not state['trobs']
            outcomes[f'final_timer_{final_timer}'] += 1
    return dict(cases=dict(counts), outcomes=dict(outcomes), mismatches=0, services=dict(services),
                source_labels=[entry[0] for entry in fixtures], excluded_raw_sources=excluded,
                plans={name: list(steps) for name, steps in PLANS.items()},
                outputs_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(executable).hexdigest(),
                supplied_services=['5:4d84 AddSound: request sink',
                                   '5:0f38 RedrawPlate: request sink; distinct cache/OS snapshots per caller'],
                scope=('Connected native PushPlate/Trigger/rock activation/AnimTrobs/AnimTrob/plate release '
                       'and compaction, persistent level/MOB/TROB/OS/cache on five admitted rock-only original '
                       'sources. Three supplied schedules include press-first and animation-first; neither '
                       'is asserted to be native FrameAdv order. Audio/redraw are supplied. No rock movement, '
                       'target gate animation, actual pressure admission, real sound/pixels or saves/reset.'))


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
