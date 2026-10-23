"""Execute native CheckPress admission with real ReadCell and request-only endpoints."""

import argparse
from collections import Counter
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_temple_slide_rock_geometry import NativeSlideRockGeometry, TempleCellReader


@dataclass(frozen=True)
class PressureActor:
    room: int
    column: int
    row: int
    y: int
    kind: int = 0
    pose: int = 15
    mode: int = 0
    selected: int = 15
    alive: int = -1
    floating: int = 0
    aux: int = 0x40


def admission_reference(actor, reader, flag=4321):
    """The supporting column is supplied; this does not recover its calculation."""
    events = []
    if (actor.kind in (10, 11) or actor.kind == 0 and actor.floating
            or actor.kind == 1 and 29 <= actor.selected <= 42):
        return events, flag
    pose = actor.pose & 65535
    if 87 <= pose <= 99 or 135 <= pose < 141:
        kind = reader.read(actor.room, actor.column, actor.row - 1)
    elif actor.mode < 2 or actor.mode in (5, 7, 8):
        kind = reader.read(actor.room, actor.column, actor.row - 1)
        if actor.pose == 79 and kind in (11, 15):
            return [('loose' if kind == 11 else 'trapdoor', (0,) if kind == 11 else ())], flag
        kind = reader.read(actor.room, actor.column, actor.row) if actor.aux & 0x40 else 0
    else:
        kind = 0
    if actor.y < actor.row * 120 + 95:
        return events, flag
    if kind in (5, 6, 34):
        if actor.alive < 0 or actor.kind == 4:
            events.append(('push', (0, -1)))
        else:
            events.append(('permanent', ()))
    elif kind in (11, 15):
        flag = 1
        events.append(('loose' if kind == 11 else 'trapdoor', (0,) if kind == 11 else ()))
    return events, flag


class NativePressureAdmission(NativeSlideRockGeometry):
    RANGES = NativeSlideRockGeometry.RANGES | {
        4: NativeSlideRockGeometry.RANGES[4] + ((0x35a6, 0x35b8), (0x3ff8, 0x400e)),
        5: NativeSlideRockGeometry.RANGES[5] + ((0x127e, 0x13dc),),
    }
    SUPPLIED = {(5, 0x240c): 'push', (5, 0x252e): 'permanent',
                (5, 0x2710): 'loose', (7, 0x36a0): 'trapdoor'}

    def reset(self, level):
        super().reset(level)
        self.events = []

    def dispatch(self, cpu, address, size, user):
        segment, offset = divmod(address - self.CODE_BASE, 0x10000)
        name = self.SUPPLIED.get((segment, offset))
        if name is not None:
            count = 2 if name == 'push' else 1 if name == 'loose' else 0
            stack = cpu.reg_read(self.registers['a7'])
            args = struct.unpack(f'>{count}h', cpu.mem_read(stack + 4, count * 2)) if count else ()
            self.events.append((name, args))
        super().dispatch(cpu, address, size, user)


def actor_bytes(actor):
    data = bytearray((i * 11 + 3) % 256 for i in range(62))
    for offset, value in ((6, actor.y), (8, actor.kind), (10, actor.pose),
                          (12, actor.column), (14, actor.row), (16, actor.mode),
                          (22, actor.room), (28, actor.alive), (40, actor.selected)):
        struct.pack_into('>h', data, offset, value)
    return bytes(data)


def variants(actor):
    yield 'ordinary', actor
    for kind in (-1, 0, 1, 4, 5, 9, 10, 11, 12):
        for alive in (-1, 0, 1):
            yield 'actor-alive', replace(actor, kind=kind, alive=alive)
    for pose in (-1, 78, 79, 80, 86, 87, 99, 100, 134, 135, 140, 141, 185):
        for aux in (0, 0x40):
            yield 'pose-aux', replace(actor, pose=pose, aux=aux)
    for mode in (-1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9):
        yield 'mode', replace(actor, mode=mode)
    for delta in (-1, 0, 1):
        yield 'height', replace(actor, y=actor.row * 120 + 95 + delta)
    for kind in (0, 1, 4):
        for floating in (0, 1, -1):
            yield 'float', replace(actor, kind=kind, floating=floating)
    for selected in (28, 29, 42, 43):
        yield 'selected', replace(actor, kind=1, selected=selected)


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    resources = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    machine = NativePressureAdmission(parse_resource_fork(executable))
    counts, outcomes, hashes, inventory = Counter(), Counter(), {}, Counter()
    digest = hashlib.sha256()

    def compare(level, actor, label):
        reader = TempleCellReader(level, actor.room)
        expected, flag = admission_reference(actor, reader)
        machine.reset(level)
        current = actor_bytes(actor)
        saved = bytes((i * 7 + 17) % 256 for i in range(62))
        machine.cpu.mem_write(machine.A5 - 0x5056, current)
        machine.cpu.mem_write(machine.A5 - 0x50d2, saved)
        for offset, value in ((-0x4fc2, actor.room), (-0x520a, actor.aux),
                              (-0x4fa6, actor.floating), (-0x4f9e, 4321)):
            machine.put_word(offset, value)
        machine.call(5, 0x127e)
        actual = (machine.events, machine.word(-0x4f9e), machine.reads, machine.cache())
        wanted = (expected, flag, reader.requests, reader.cache)
        if (actual != wanted or machine.services != Counter(event[0] for event in expected)
                or machine.level_bytes(len(level)) != level
                or bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)) != current
                or bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62)) != saved):
            raise AssertionError(dict(label=label, actor=actor, actual=actual, expected=wanted))
        counts[label] += 1
        outcomes.update(name for name, _args in expected)
        outcomes['no_request'] += not expected
        digest.update(json.dumps(actual).encode('ascii'))

    for number in range(10, 14):
        level = resources['LEVL'][1999 + number]['data']
        if struct.unpack_from('>3h', level, 0x2186)[::2] != (2, number):
            raise ValueError('Inconsistent temple resource header')
        hashes[str(number)] = hashlib.sha256(level).hexdigest()
        maximum = struct.unpack_from('>h', level, 0x2180)[0]
        for room in range(1, maximum + 1):
            for cell in range(30):
                row, col = divmod(cell, 10)
                actor = PressureActor(room, col, row, row * 120 + 116)
                kind = struct.unpack_from('>h', level, (room - 1) * 60 + cell * 2)[0]
                compare(level, actor, 'original-cell')
                if kind in (5, 6, 34, 11, 15):
                    inventory[str(kind)] += 1
                    for label, varied in variants(actor):
                        compare(level, varied, label)
        for room in range(1, maximum + 1):
            for col in (-1, 10):
                for row in (0, 1, 2):
                    compare(level, PressureActor(room, col, row, row * 120 + 116), 'linked-column')
    # Absent source kinds are explicit supplied controls, not original placements.
    base = bytearray(resources['LEVL'][2009]['data'])
    for above in (5, 6, 34, 11, 15, 1):
        for below in (5, 6, 34, 11, 15, 1):
            struct.pack_into('>h', base, 3 * 2, above)
            struct.pack_into('>h', base, 13 * 2, below)
            for label, actor in variants(PressureActor(1, 3, 1, 236)):
                compare(bytes(base), actor, 'supplied-' + label)
    return dict(cases=dict(counts), outcomes=dict(outcomes), original_sources=dict(inventory),
                mismatches=0, executable_sha256=hashlib.sha256(executable).hexdigest(),
                level_sha256=hashes, outputs_sha256=digest.hexdigest(),
                scope='Native CheckPress, above/current ReadCell helpers and original temple cell traversal. '
                      'Supporting column/row, FRAM auxiliary word and actor state are supplied. '
                      'PushPlate, permanent plate, loose-floor and trapdoor calls are no-op request sinks. '
                      'No mechanism effects, supporting-foot calculation, FrameAdv scheduling, sound, '
                      'pixels, saves/reset or playable temple integration are claimed.')


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
