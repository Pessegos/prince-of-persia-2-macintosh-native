"""Join original constructor/update/presentation passes in explicit supplied sequences."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_temple_trapdoor_advance import advance_reference
from tools.probe_temple_trapdoor_presentation import (
    NativeTrapDoorPresentation, presentation_reference, view_for,
)
from tools.probe_temple_trapdoors import trigger_reference


def cycle_reference(level, mobs, view, visible, pending, mapping, frames, clip):
    advanced, queries, sounds = [], [], []
    for mob in mobs:
        result, requested, added = advance_reference(mob, True, False)
        advanced.append(result)
        queries.extend(requested)
        sounds.extend(added)
    result = dict(level=bytes(level), mobs=[], pending_cue=pending, advanced_mobs=advanced,
                  queries=queries, sounds=sounds, resets=[], redraw=[], sizes=[],
                  visibility=[], rectangles=[], draws=[])
    for mob in advanced:
        if mob[3] == -1:
            continue
        presented = presentation_reference(result['level'], mob, view, visible,
                                           result['pending_cue'], mapping, frames, clip)
        result['level'], result['pending_cue'] = presented['level'], presented['pending_cue']
        result['mobs'].append(presented['mob'])
        for field in ('sounds', 'resets', 'redraw', 'sizes', 'visibility', 'rectangles', 'draws'):
            result[field].extend(presented[field])
    return result


class NativeTrapDoorLifecycle(NativeTrapDoorPresentation):
    RANGES = {**NativeTrapDoorPresentation.RANGES,
              5: NativeTrapDoorPresentation.RANGES[5] + ((0x29e8, 0x2b0e),),
              10: NativeTrapDoorPresentation.RANGES[10] + ((0x24fa, 0x253e),)}

    def reset(self, level):
        super().reset(level)
        self.queries = []

    def clear_events(self):
        for field in ('queries', 'sounds', 'resets', 'redraw', 'sizes', 'visibility', 'rectangles', 'draws'):
            setattr(self, field, [])

    def dispatch(self, cpu, address, size, user):
        if address == self.address(5, 0x52c8):
            stack = cpu.reg_read(self.registers['a7'])
            cue = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
            if cue not in (197, 198):
                raise AssertionError('Unexpected sound query in lifecycle')
            self.queries.append(cue)
            cpu.reg_write(self.registers['d0'], int(cue == 197))
            destination = struct.unpack('>I', cpu.mem_read(stack, 4))[0]
            cpu.reg_write(self.registers['a7'], stack + 4)
            cpu.reg_write(self.registers['pc'], destination)
            return
        super().dispatch(cpu, address, size, user)

    def bank_records(self):
        count = self.word(-0x4490)
        if not 0 <= count <= 30:
            raise AssertionError('Native lifecycle bank count is invalid')
        return [struct.unpack('>8h', self.cpu.mem_read(self.BANK + i * 16, 16)) for i in range(count)]


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    program_bytes = (directory / 'Prince of Persia 2.bin').read_bytes()
    temple_bytes = (directory / 'Temple.rsrc.bin').read_bytes()
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    machine = NativeTrapDoorLifecycle(parse_resource_fork(program_bytes), parse_resource_fork(temple_bytes))
    clip, canary = (-1000, -1000, 2000, 2000), bytes((i * 17 + 3) % 256 for i in range(512))
    counts, traces = Counter(), []
    digest = hashlib.sha256()
    for number in range(10, 14):
        original = prince['LEVL'][1999 + number]['data']
        for room in range(1, 33):
            for cell in range(30):
                tile_offset = (room - 1) * 60 + cell * 2
                if struct.unpack_from('>H', original, tile_offset)[0] != 26:
                    continue
                for relative_column in (0, 1):
                    for visible in (False, True):
                        view = view_for(room, 'current')
                        machine.configure(original, (0, 0, room, 0, 0, 10, 0, 1), view, visible, 198, clip)
                        machine.cpu.mem_write(machine.BANK - 16, canary)
                        machine.cpu.mem_write(machine.A5 - 0x4496, struct.pack('>I', machine.BANK))
                        machine.put_word(-0x4490, 0)
                        actor_column = cell % 10 + relative_column
                        machine.put_word(-0x504a, actor_column)
                        machine.call(4, 0x27ee, (room, cell % 10, cell // 10))
                        machine.call(10, 0x25aa)
                        constructed = trigger_reference(original, room, cell, actor_column, 0)
                        mobs, level, pending = [constructed['scratch_mob']], constructed['level'], 198
                        expected_bank = bytearray(canary)
                        expected_bank[16:32] = struct.pack('>8h', *mobs[0])
                        if (machine.bank_records() != mobs or machine.level_bytes(len(original)) != level
                                or bytes(machine.cpu.mem_read(machine.BANK - 16, 512)) != expected_bank):
                            raise AssertionError('Native lifecycle constructor differs')
                        snapshots, terminal, compacted = [], None, None
                        for step in range(1, 21):
                            expected = cycle_reference(level, mobs, view, visible, pending,
                                                       machine.mapping, machine.frames, clip)
                            for index, mob in enumerate(expected['advanced_mobs']):
                                expected_bank[16 + index * 16:32 + index * 16] = struct.pack('>8h', *mob)
                            survivors = [mob for mob in expected['advanced_mobs'] if mob[3] != -1]
                            for index, mob in enumerate(survivors):
                                expected_bank[16 + index * 16:32 + index * 16] = struct.pack('>8h', *mob)
                            machine.clear_events()
                            machine.call(5, 0x29e8)
                            if (machine.bank_records() != survivors
                                    or bytes(machine.cpu.mem_read(machine.BANK - 16, 512)) != expected_bank
                                    or machine.level_bytes(len(original)) != level):
                                raise AssertionError('Native update/compaction stage differs')
                            machine.call(5, 0x307c)
                            for index, mob in enumerate(expected['mobs']):
                                expected_bank[16 + index * 16:32 + index * 16] = struct.pack('>8h', *mob)
                            actual = dict(level=machine.level_bytes(len(original)), mobs=machine.bank_records(),
                                          pending_cue=machine.word(-0x439e))
                            for field in ('queries', 'sounds', 'resets', 'redraw', 'sizes', 'visibility', 'rectangles', 'draws'):
                                actual[field] = getattr(machine, field)
                            if (actual != {key: value for key, value in expected.items() if key != 'advanced_mobs'}
                                    or bytes(machine.cpu.mem_read(machine.BANK - 16, 512)) != expected_bank):
                                raise AssertionError(dict(level=number, room=room, cell=cell, step=step,
                                                          initial=constructed['scratch_mob'][7], visible=visible))
                            level, mobs, pending = actual['level'], actual['mobs'], actual['pending_cue']
                            if terminal is None and mobs and mobs[0][3] == -1:
                                terminal = step
                            if compacted is None and not mobs:
                                compacted = step
                            snapshots.append(dict(cycle=step, mobs=mobs,
                                                  tile=struct.unpack_from('>H', level, tile_offset)[0]))
                            counts['cycles'] += 1
                            digest.update(level + bytes(expected_bank))
                        expected_terminal = 16 if relative_column == 0 else 6
                        if (terminal, compacted, level) != (expected_terminal, expected_terminal + 1, original):
                            raise AssertionError('Native door did not restore and compact in the expected supplied order')
                        traces.append(dict(level=number, room=room, cell=cell, visible=visible,
                                           initial=constructed['scratch_mob'][7], terminal_cycle=terminal,
                                           compacted_cycle=compacted, snapshots=snapshots))
                        counts['traces'] += 1
    return dict(
        cases=dict(counts), traces=traces, mismatches=0, outputs_sha256=digest.hexdigest(),
        executable_sha256=hashlib.sha256(program_bytes).hexdigest(),
        temple_sha256=hashlib.sha256(temple_bytes).hexdigest(),
        supplied_order=['Native constructor once', 'Native MakeRubble/update then ATMLoose/presentation each cycle'],
        supplied=['All presentation probe endpoints/image cache',
                  'PrinceSndOn197 always true and198 false; not a real sound-queue lifecycle',
                  'One constructed type10 object in otherwise empty canary-guarded bank; current room'],
        scope=('40 explicit constructor-to-restoration-to-compaction traces, carrying original '
               'CPU/memory/bank/level state across800 supplied cycles. Both constructor states '
               'and visibility outcomes at all ten actual locations. This executes both native '
               'dispatchers but not complete FrameAdv call-site ordering, elapsed frames, '
               'real audio/redraw/pixels, multi-type mob scheduling, character interaction '
               'or save/restart/campaign equivalence.'),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'traces'}, indent=2))


if __name__ == '__main__':
    main()
