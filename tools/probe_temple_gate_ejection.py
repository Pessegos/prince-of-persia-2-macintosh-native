"""Recover gate ejection and compose the actual temple hard-contact caller.

Runs4:6202, both real distance services and AddCharX, and4:60e4's hard
branch with real ReadCell/admission. Actor/collision edges, neighbor slots
and overlap banks are prepared inputs. No geometry/ejection/sequence endpoint
is supplied on these paths. General soft distance4:5eae, bank construction,
frame loading, physical support and complete FrameAdv remain excluded.
"""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_sequence_selection import signed_word
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_contact import ContactCellReader, NativeTempleGateContact, contact_reference
from tools.probe_temple_gate_distance import (
    NEIGHBOR_SLOTS, NativeTempleGateDistance, distance_reference,
)
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_gate_standing import COLD_CACHE
from tools.probe_temple_slide_rock_update import actor_word


def ejection_reference(actor, foreground, room, column, edges, view, neighbors, *, anchor=73):
    face = distance_reference(actor, foreground, room, column, edges, view, neighbors,
                              anchor=anchor)
    back = distance_reference(actor, foreground, room, column, edges, view, neighbors,
                              back=True, anchor=face['anchor'])
    # Native negates in32 bits then stores a word; abs(-32768) stores-32768.
    front_distance = signed_word(abs(face['distance']))
    back_distance = signed_word(abs(back['distance']))
    if front_distance < back_distance:
        delta = signed_word(-signed_word(front_distance + 3))
        if actor_word(actor, 8) == 4:
            delta = signed_word(delta - 8)
    else:
        delta = back_distance
    result = bytearray(actor)
    displacement = -delta if actor_word(actor, 2) == -1 else delta
    put_actor(result, 4, actor_word(actor, 4) + displacement)
    return dict(actor=bytes(result), anchor=back['anchor'], delta=delta,
                calls=['face', 'face', 'back', 'back'])


def hard_contact_reference(actor, reader, overlap, edges, view, neighbors, *, mark=79, anchor=73):
    contact = contact_reference(actor, reader, overlap, 25, mark=mark)
    if contact['events'] not in ([], [('eject',)]):
        raise ValueError('Soft/cave contact is outside this caller corpus')
    geometry = (ejection_reference(contact['actor'], reader.cache[1] & 65535,
                                  reader.cache[3], reader.cache[4], edges, view, neighbors,
                                  anchor=anchor)
                if contact['events'] else dict(actor=actor, anchor=anchor, calls=[]))
    return {**geometry, 'events': contact['events'], 'mark': contact['mark']}


class NativeTempleGateEjection(NativeTempleGateDistance):
    RANGES = dict(NativeTempleGateDistance.RANGES)
    RANGES[4] += ((0x6202, 0x62b0),)

    def reset(self, level):
        super().reset(level)
        self.geometry = []

    def dispatch(self, cpu, address, size, user):
        if address in (self.address(4, 0x6562), self.address(4, 0x6610)):
            self.geometry.append('face' if address == self.address(4, 0x6562) else 'back')
        super().dispatch(cpu, address, size, user)


class NativeHardGateContact(NativeTempleGateContact):
    RANGES = dict(NativeTempleGateContact.RANGES)
    RANGES[4] += NativeTempleGateEjection.RANGES[4]

    def reset(self, level):
        super().reset(level)
        self.geometry = []

    def dispatch(self, cpu, address, size, user):
        if address == self.address(4, 0x6202):
            self.events.append(('eject',))
            # Bypass only the old log-only ejection stub; execute the helper.
            NativeTempleGateDistance.dispatch(self, cpu, address, size, user)
            return
        if address in (self.address(4, 0x6562), self.address(4, 0x6610)):
            self.geometry.append('face' if address == self.address(4, 0x6562) else 'back')
        super().dispatch(cpu, address, size, user)


def run_probe(source):
    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(executable)
    levels = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())['LEVL']
    direct, caller = NativeTempleGateEjection(program), NativeHardGateContact(program)
    counts, outcomes, digest = Counter(), Counter(), hashlib.sha256()

    def check(machine, level, actor, room, column, foreground, edges, view, neighbors,
              label, overlap=None):
        machine.reset(level)
        machine.cpu.mem_write(machine.A5 - 0x5056, actor)
        machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(range(62)))
        machine.cpu.mem_write(machine.A5 - 0x448e, bytes(range(160)))
        for offset, value in ((-0x4fc2, view), (-0x35fc, 73), (-0x4f9e, 79),
                              (-0x3564, edges[0]), (-0x3566, edges[1])):
            machine.put_word(offset, value)
        for offset, value in zip(NEIGHBOR_SLOTS, neighbors):
            machine.put_word(offset, value)
        machine.cpu.mem_write(machine.A5 - 0x34b0, struct.pack('>6h', *COLD_CACHE))
        reader, events, mark = None, [], 79
        if overlap is None:
            machine.put_word(-0x34ae, foreground)
            machine.put_word(-0x34aa, room)
            machine.put_word(-0x34a8, column)
            expected = ejection_reference(actor, foreground, room, column, edges, view, neighbors)
        else:
            for offset, bank in zip((-0x355e, -0x354a), overlap):
                machine.cpu.mem_write(machine.A5 + offset, struct.pack('>10H', *bank))
            reader = ContactCellReader(level, view)
            expected = hard_contact_reference(actor, reader, overlap, edges, view, neighbors)
            events, mark = expected['events'], expected['mark']
        before = bytearray(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        machine.call(4, 0x6202 if overlap is None else 0x60e4)
        before[len(machine.data) - 0x5056:len(machine.data) - 0x5056 + 62] = expected['actor']
        struct.pack_into('>h', before, len(machine.data) - 0x35fc, expected['anchor'])
        struct.pack_into('>h', before, len(machine.data) - 0x4f9e, mark)
        if reader is not None:
            struct.pack_into('>6h', before, len(machine.data) - 0x34b0, *reader.cache)
            if reader.pointer_room is not None:
                r = reader.pointer_room
                struct.pack_into('>II', before, len(machine.data) - 0x4824,
                                 machine.LEVEL + 0x780 + (r - 1) * 120,
                                 machine.LEVEL + (r - 1) * 60)
        after = bytes(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        if (after != before or machine.geometry != expected['calls'] or machine.services
                or machine.level_bytes(len(level)) != level
                or reader is not None and (machine.events != events or machine.reads != reader.requests)
                or reader is None and machine.reads):
            raise AssertionError(dict(label=label, actor=actor.hex(), edges=edges, room=room,
                                      column=column, foreground=foreground, calls=machine.geometry,
                                      expected=expected, changed=[(hex(i - len(machine.data)), a, b)
                                      for i, (a, b) in enumerate(zip(before, after)) if a != b]))
        counts[label] += 1
        outcomes['ejected' if expected['actor'] != actor else 'unchanged'] += 1
        digest.update(bytes(level) + expected['actor'] + struct.pack('>2h', mark, expected['anchor']))

    level = levels[2009]['data']
    for facing, kind, edges, foreground, neighbors in product(
            (-1, 0), (0, 1, 4),
            ((400, 430), (450, 480), (470, 486), (473, 493), (-32768, 32767),
             (32767, -32768), (483, 473), (-32285, 500), (480, -32295)), (0, 96, 184, 255),
            ((0,) * 6, (2, 0, 0, 0, 0, 0), (0, 0, 0, 2, 0, 0))):
        actor = bytearray(actor_fixture(1, 1, 4, facing, 0))
        for offset, value in ((4, 460), (8, kind), (42, 20), (46, 94)):
            put_actor(actor, offset, value)
        check(direct, level, bytes(actor), 2, 4, foreground, edges, 1, neighbors, 'direct')
    gates = 0
    for number in range(10, 14):
        original = levels[1999 + number]['data']
        for room, cell in product(range(1, 33), range(30)):
            if struct.unpack_from('>H', original, (room - 1) * 60 + cell * 2)[0] != 4:
                continue
            gates += 1
            row, column = divmod(cell, 10)
            for facing, foreground, source, alive, (pose, armed), delta, intersection in product(
                    (-1, 0), (0, 96, 184), (9, 118), (-1, 0), ((1, 1), (109, 0)),
                    (-25, 0, 25, 51), ((255, 255), (511, 511), (511, 255))):
                level = bytearray(original)
                struct.pack_into('>H', level, 0x780 + (room - 1) * 120 + cell * 4, foreground)
                actor = bytearray(actor_fixture(room, row, column, facing, 0))
                anchor = 229 + column * 51
                for offset, value in ((4, anchor + delta), (10, pose), (26, armed),
                                      (28, alive), (40, source), (42, 20), (46, 94)):
                    put_actor(actor, offset, value)
                overlap = tuple((value,) * 10 for value in intersection)
                check(caller, bytes(level), bytes(actor), room, column, foreground,
                      (anchor + delta, anchor + delta + 30), room, (0,) * 6,
                      'original_hard_contact', overlap)
    return dict(gates=gates, comparisons=dict(counts), outcomes=dict(outcomes), mismatches=0,
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                outputs_sha256=digest.hexdigest(), supplied=[], scope=__doc__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
