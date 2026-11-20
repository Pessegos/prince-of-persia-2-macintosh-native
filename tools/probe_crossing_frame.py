"""Execute FrameAdv across room crossings: which frame LoadFrame left for InitOpps.

SkelAddOpponent 4:198a (called by InitOpps 6:2ce6 for a zero-cursor skeleton
record) measures with the frame record already loaded (a5-0x5212..-0x520a).
`CombatEncounter._last_loaded_opponent_frame` reads that, from FrameAdv's
order, as the last opponent of the room being left (opponent pass 2:648c,
LoadFrame at 2:6512 and after AnimChar at 2:65e2) or, with none, the
Prince's (2:6386). This probe executes the original FrameAdv 2:6224 frame by
frame on levels 3-5 with the Kid's recorded controller held toward an edge
(RECG stream, absolute right 0x1514 / left 0x4514), from standing starts 12,
40 and 90 pixels inside every room edge that has a neighbour, on each row,
for up to 48 frames, until PrepCut (2:532c, executed, not supplied) reaches
InitOpps. Every write to the loaded-frame words is hooked with its program
counter, so a load anywhere else (also through code a static search could
miss) is seen.

Checked at each crossing: (1) the last LoadFrame 4:2a8e before InitOpps ran
inside the Prince's step 2:62e6 or the opponent pass 2:648c, and every write
to the loaded-frame words after it belongs to that call; (2) nothing writes
them between InitOpps and SkelAddOpponent; (3) the port rule, run on the
native opponents of the room left (slot order, their poses before the
frame), picks the same frame words that InitOpps sees; (4) where it does
not and a heap settles, the original 4:198a is run again with the port's
words (tools.probe_skeleton_settle) to see whether the heap's X or SEQS
changes. Rooms are run with their LEVL records and again with each of the
level's skeleton records appended to the room left (skipped when it already
holds five), so the opponent pass has someone to load.

The harness is tools.extract_attract.RecordedSimulation (the import's own
level-one demo runner), with the Kid, skeleton and cavern shape tables and
the DATA relocations (DREL) the startup code applies.
Supplied, not executed: drawing/sound segments 15, 16, 20-24 and its device
calls, the segment-17 palette routines (SetColors ... SetCTBLColors),
DrawOppMeter 3:4a8e, the checkpoint checksum 2:1504, resource lookup 17:330e, GetResource/UseResFile/
CurResFile and hGetSequence 4:3098 (handles to the original resources), Rnd
17:6e06 (its seeded generator), SectRect/EmptyRect/UnionRect and pen/rect
traps, BlockMove, NewHandle/NewPtr (fresh memory), DisposeHandle/DisposePtr/MoveHHi and the memory-manager traps. A start where
the native run stops on anything else is counted as a native failure, never
as a crossing. None of the supplied routines writes the loaded-frame words in
the listings. Level start (FirstFrame) and the Kid's death/level exits are
not covered. No game or emulator window is operated.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys
from types import SimpleNamespace

from pop2.animation_data import parse_frame_records
from pop2.combat import CombatEncounter
from pop2.mac_resources import parse_resource_fork
from tools.extract_attract import RecordedSimulation
from tools.probe_skeleton_settle import NativeSettle, native_settle

KID = -0x50d2
CACHE = -0x5212  # five words: shape, AFRM index, offset_x, offset_y, flags
SLOTS = -0x5208
LEVELS = (3, 4, 5)
TRACE = {(4, 0x2a8e): 'load', (4, 0x198a): 'settle', (6, 0x2b7e): 'initopps',
         (2, 0x62e6): 'prince_step', (2, 0x6260): 'prince_done', (2, 0x648c): 'opponent_pass',
         (2, 0x6270): 'pass_done', (2, 0x62d0): 'pass_done'}
# LoadFrame call sites (return addresses) named in the report.
SITES = {0x2638a: 'Prince 2:6386', 0x2634c: 'Prince 2:6348', 0x26516: 'opponent 2:6512',
         0x265e6: 'opponent 2:65e2', 0x439f2: 'bump/landing 4:39ee'}
KID_SLOT = 10
# Kid standing (pose 15, SEQS 2 cursor 3), as the native run reaches it.
STAND = dict(pose=15, sequence=2, cursor=3)
RIGHT, LEFT = 0x1514, 0x4514
EDGE_DISTANCES = (12, 40, 90)


class NativeCrossing(RecordedSimulation):
    DEVICE_SEGMENTS = {15, 16, 20, 21, 22, 23, 24}
    SERVICE_CALLS = RecordedSimulation.SERVICE_CALLS - {(2, 0x532c)}
    # Palette routines of segment 17 (SetColors ... SetCTBLColors) and
    # DrawOppMeter 3:4a8e: colours and drawing only.
    PALETTE = (0x02de, 0x0694, 0x06da, 0x075a, 0x0790, 0x08b0, 0x0a52, 0x0ab6, 0x0d0e, 0x0eae,
               0x0f60, 0x1520, 0x1702, 0x1826, 0x18ba, 0x1950, 0x1a78, 0x6a78)
    # SetCheckSavedGameCheckSumValues 2:1504 (checkpoint save record only).
    DEVICE_CALLS = (RecordedSimulation.DEVICE_CALLS | {(17, o) for o in PALETTE}
                    | {(3, 0x4a8e), (2, 0x1504)})
    EMPTY_RECT, UNION_RECT = 0xa00010, 0xa00020

    @classmethod
    def hook_ranges(cls, resources):
        ranges = super().hook_ranges(resources)
        ranges += [(cls.EMPTY_RECT,) * 2, (cls.UNION_RECT,) * 2]
        return ranges + [((s << 16) + o,) * 2 for s, o in TRACE]

    def __init__(self, program, banks):
        from unicorn import UC_HOOK_INTR, UC_HOOK_MEM_WRITE
        from unicorn.m68k_const import UC_M68K_REG_A0, UC_M68K_REG_A1, UC_M68K_REG_PC

        super().__init__(program, banks)
        self.a0, self.a1, self.pc = UC_M68K_REG_A0, UC_M68K_REG_A1, UC_M68K_REG_PC
        self.events, self.traps, self.failure = [], Counter(), None
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, self.cache_write,
                          begin=self.A5 + CACHE, end=self.A5 + CACHE + 9)
        # Other Toolbox traps raise the line-1010 exception (10).
        self.cpu.hook_add(UC_HOOK_INTR, self.trap)

    def cache_write(self, cpu, _access, address, _size, _value, _user):
        self.events.append(('write', cpu.reg_read(self.pc), address - self.A5))

    def cache(self):
        return struct.unpack('>5h', self.cpu.mem_read(self.A5 + CACHE, 10))

    def hook(self, cpu, address, size, user):
        a7, d0, pc = self.registers
        if address in (self.EMPTY_RECT, self.UNION_RECT):
            sp = cpu.reg_read(a7)
            back = self.long(sp)
            if address == self.EMPTY_RECT:
                top, left, bottom, right = struct.unpack('>4h', cpu.mem_read(self.long(sp + 4), 8))
                cpu.mem_write(sp + 8, bytes((int(top >= bottom or left >= right), 0)))
                cpu.reg_write(a7, sp + 8)
            else:
                one = struct.unpack('>4h', cpu.mem_read(self.long(sp + 12), 8))
                two = struct.unpack('>4h', cpu.mem_read(self.long(sp + 8), 8))
                union = (min(one[0], two[0]), min(one[1], two[1]),
                         max(one[2], two[2]), max(one[3], two[3]))
                cpu.mem_write(self.long(sp + 4), struct.pack('>4h', *union))
                cpu.reg_write(a7, sp + 16)
            cpu.reg_write(pc, back)
            return
        segment, offset = divmod(address, 0x10000)
        name = TRACE.get((segment, offset))
        if name:
            sp = cpu.reg_read(a7)
            caller = self.long(sp + 4) if self.long(sp) == 0x42a76 else self.long(sp)
            working = struct.unpack('>31h', cpu.mem_read(self.A5 - 0x5056, 62))
            record = (struct.unpack('>19h', cpu.mem_read(self.long(sp + 4), 38))
                      if name == 'settle' else None)
            self.events.append((name, caller, working[0], working[4], working[5], self.cache(), record))
            return
        super().hook(cpu, address, size, user)

    def trap(self, cpu, number, _user):
        a7, d0, pc = self.registers
        address = cpu.reg_read(pc)
        opcode = int.from_bytes(cpu.mem_read(address, 2), 'big')
        if number != 10:
            self.failure = f'CPU exception {number} at {address:#x}'
            cpu.emu_stop()
            return
        self.traps[f'{opcode:#06x}'] += 1
        sp = cpu.reg_read(a7)
        if opcode & 0xf0ff == 0xa022:  # NewHandle
            pointer = self.allocate(bytes(cpu.reg_read(d0) & 0xffffff))
            cpu.reg_write(self.a0, self.allocate(struct.pack('>I', pointer)))
            cpu.reg_write(d0, 0)
        elif opcode & 0xf0ff == 0xa02e:  # BlockMove(a0 source, a1 destination, d0 bytes)
            count = cpu.reg_read(d0) & 0xffffff
            cpu.mem_write(cpu.reg_read(self.a1), bytes(cpu.mem_read(cpu.reg_read(self.a0), count)))
            cpu.reg_write(d0, 0)
        elif opcode & 0xf0ff == 0xa01e:  # NewPtr
            cpu.reg_write(self.a0, self.allocate(bytes(cpu.reg_read(d0) & 0xffffff)))
            cpu.reg_write(d0, 0)
        elif opcode & 0xf0ff in (0xa01f, 0xa023, 0xa064):  # DisposePtr, DisposeHandle, MoveHHi: inert
            cpu.reg_write(d0, 0)
        elif opcode == 0xa9a0:  # GetResource(type, id): Handle
            kind = bytes(cpu.mem_read(sp + 2, 4)).decode('mac_roman')
            cpu.mem_write(sp + 6, struct.pack('>I', self.resource(kind, self.word(sp))))
            cpu.reg_write(a7, sp + 6)
        elif opcode == 0xa998:  # UseResFile(refNum)
            cpu.reg_write(a7, sp + 2)
        elif opcode == 0xa994:  # CurResFile: INTEGER
            cpu.mem_write(sp, struct.pack('>H', 1))
        else:
            self.failure = f'Unsupported trap {opcode:#x} at {address >> 16}:{address & 0xffff:04x}'
            cpu.emu_stop()
            return
        cpu.reg_write(pc, address + 2)

    def put(self, base, index, value):
        self.write_word(base + 2 * index, value)


def recording(number):
    """A RECG stream holding the Kid's controller to one side from frame 0."""
    body = struct.pack('>4H', 0, 1, 0, RIGHT) + bytes(4)
    return struct.pack('>3H', number, 400, len(body)) + body


def start_level(sim, number):
    """Level start as tools.extract_attract.RecordedSimulation.demo does it."""
    level_id = 1999 + number
    level = sim.banks['Prince']['LEVL'][level_id]['data']
    sim.banks['Prince'].setdefault('RECG', {})[900] = {'data': recording(number)}
    start_room = struct.unpack_from('>H', level, 0x2198)[0]
    sim.write_long(-0x5014, sim.long(sim.resource('LEVL', level_id)))
    for offset, value in ((-0x4fd2, 1), (-0x4f92, 1), (-0x4f98, 3), (-0x4fee, 1),
                          (-0x4ffe, 1), (-0x43b6, 3), (-0x43a0, 900)):
        sim.write_word(offset, value)
    for offset, kind, bank in ((-0x3472, 'FRAM', 'Kid'), (-0x3476, 'AFRM', 'Kid'),
                               (-0x347a, 'FRAM', 'Skeleton'), (-0x347e, 'AFRM', 'Skeleton')):
        sim.write_long(offset, sim.resource(kind, 750 if bank == 'Skeleton' else 25001, bank))
    for index, bank in ((2, 'Kid'), (3, 'Skeleton'), (4, 'Caverns')):
        first, count = struct.unpack('>2H', next(iter(sim.banks[bank]['SHPL'].values()))['data'])
        table = bytearray(8 + (count + 1) * 10)
        for i in range(count):
            struct.pack_into('>I', table, 8 + (i + 1) * 10 - 4, sim.resource('SHAP', first + i, bank))
        sim.write_long(-0x4a98 + index * 4, sim.allocate(table))
    sim.write_long(-0x1f58, sim.SECT_RECT)
    sim.write_long(-0x1f60, sim.EMPTY_RECT)
    sim.write_long(-0x1f5c, sim.UNION_RECT)
    sim.cpu.mem_write(sim.A5 - 0x4fec, struct.pack('>4h', 0, 0, 384, 510))
    # CODE 1 0x00f0-0x0122: every DREL word names a DATA long that gets A5
    # added (none here sets bit 0, the CODE-relative form). The demo runner
    # relocates only its level-one callback table.
    relocations = sim.resources['DREL'][0]['data']
    for (offset,) in struct.iter_unpack('>h', relocations):
        if offset & 1:
            raise ValueError('CODE-relative DREL entry')
        sim.write_long(offset, (sim.long(sim.A5 + offset) + sim.A5) & 0xffffffff)
    sim.call(5, 0x0004, struct.pack('>h', start_room))
    sim.call(4, 0x66ae)
    sim.call(2, 0x5cf4)
    sim.write_word(-0x5056, 10)
    sim.cpu.mem_write(sim.A5 + KID, bytes(sim.cpu.mem_read(sim.A5 - 0x5056, 62)))
    sim.write_word(-0x4fc2, start_room)
    sim.call(3, 0x1ab0)
    sim.call(6, 0x2b7e)
    sim.call(5, 0x638a)
    sim.credit_lines = []  # enables the pen/rect traps
    return sim.long(sim.A5 - 0x5014)


class Snapshot:
    def __init__(self, sim):
        self.memory = bytes(sim.cpu.mem_read(0, 0x1000000))
        self.context = sim.cpu.context_save()
        self.pool, self.handles = sim.pool, dict(sim.handles)

    def restore(self, sim):
        sim.cpu.mem_write(0, self.memory)
        sim.cpu.context_restore(self.context)
        sim.pool, sim.handles = self.pool, dict(self.handles)
        sim.events.clear()


def bank_records(sim, level_address, native_room):
    start = level_address + 0x20e6 + native_room * 0xc0
    count = sim.word(start) & 0xffff
    return [struct.unpack('>19h', sim.cpu.mem_read(start + 2 + 38 * i, 38)) for i in range(count)]


def append_record(sim, level_address, native_room, words):
    start = level_address + 0x20e6 + native_room * 0xc0
    count = sim.word(start) & 0xffff
    if count >= 5:
        return False
    words = list(words)
    words[7] = count  # the record's slot
    sim.cpu.mem_write(start + 2 + 38 * count, struct.pack('>19h', *words))
    sim.cpu.mem_write(start, struct.pack('>H', count + 1))
    return True


def place_kid(sim, native_room, row, x, facing):
    for index, value in ((1, facing), (2, x), (3, 106 + 120 * row), (5, STAND['pose']), (7, row),
                         (9, 0), (10, 0), (11, native_room), (18, STAND['cursor']),
                         (19, STAND['sequence']), (20, STAND['sequence'])):
        sim.put(KID, index, value)
    sim.write_word(-0x4fc2, native_room)
    sim.write_word(-0x4fc4, native_room)
    sim.call(3, 0x1ab0)
    sim.call(6, 0x2b7e)


def opponents(sim, level_address, native_room):
    count = len(bank_records(sim, level_address, native_room))
    slots = [struct.unpack('>31h', sim.cpu.mem_read(sim.A5 + SLOTS + 62 * i, 62)) for i in range(count)]
    return [dict(slot=i, actor=s[4], pose=s[5], facing=s[1], x=s[2], y=s[3]) for i, s in enumerate(slots)]


def port_frame(art, kid_frames, before, kid_pose):
    """The production rule on the native opponents of the room left."""
    actors = [SimpleNamespace(state=SimpleNamespace(actor_type=o['actor'], action=o['pose']))
              for o in before]
    record = CombatEncounter._last_loaded_opponent_frame(SimpleNamespace(guard_art=art), actors)
    if record is None:
        record = kid_frames[kid_pose]
    return record.offset_x, record.aux


def judge(events):
    """Split one frame's events at InitOpps and check the loaded-frame writers."""
    names = [event[0] for event in events]
    first = names.index('initopps')
    phase, loads = None, []
    for index, event in enumerate(events[:first]):
        if event[0] in ('prince_step', 'opponent_pass'):
            phase = event[0]
        elif event[0] in ('prince_done', 'pass_done'):
            phase = 'after_' + phase
        elif event[0] == 'load':
            loads.append((index, phase))
    if not loads:
        return dict(error='no load before InitOpps')
    position, phase = loads[-1]
    last = events[position]
    foreign = [e for e in events[position + 1:first]
               if e[0] == 'write' and not 0x42a8e <= e[1] <= 0x42bac]
    settles = [e for e in events[first:] if e[0] == 'settle']
    end = events.index(settles[0]) if settles else len(events)
    between = [e for e in events[first:end] if e[0] in ('write', 'load')]
    return dict(source='prince' if last[2] == KID_SLOT else 'opponent', phase=phase,
                site=SITES.get(last[1], f'{last[1] >> 16}:{(last[1] & 0xffff) - 4:04x}'),
                slot=last[2], actor=last[3], pose=last[4],
                foreign=[(f'{e[1]:#x}', e[2]) for e in foreign],
                between=[(e[0], f'{e[1]:#x}') for e in between],
                cache=events[first][5], settles=[(e[5], e[6]) for e in settles],
                kid_pose=next((e[4] for e in reversed(events[:first])
                               if e[0] == 'load' and e[2] == KID_SLOT), None))


def run_case(sim, snapshot, level_address, number, native_room, row, x, facing, extra, art, kid_frames):
    snapshot.restore(sim)
    if extra is not None and not append_record(sim, level_address, native_room, extra):
        return None
    # The recorded controller is absolute: right 0x1514, left 0x4514.
    stream = sim.long(sim.handles[('RECG', 900, None)])
    sim.cpu.mem_write(stream + 12, struct.pack('>H', RIGHT if facing == 0 else LEFT))
    place_kid(sim, native_room, row, x, facing)
    for index in range(48):
        before = opponents(sim, level_address, sim.word(sim.A5 - 0x4fc2))
        room = sim.word(sim.A5 - 0x4fc2)
        sim.events.clear()
        sim.write_word(-0x4fee, 1)
        sim.write_word(-0x349a, index)
        sim.call(2, 0x68c0)
        sim.failure = None
        try:
            sim.call(2, 0x6224)
        except Exception as error:  # reported, never counted as a crossing
            pc = sim.cpu.reg_read(sim.pc)
            sim.failure = sim.failure or f'{error} at {pc >> 16}:{pc & 0xffff:04x}'
        if sim.failure:
            return dict(level=number, start=(native_room, row, x, facing), frame=index,
                        failure=sim.failure, room=room, extra=extra)
        if not any(event[0] == 'initopps' for event in sim.events):
            continue
        result = judge(sim.events)
        if 'error' in result:
            return dict(level=number, start=(native_room, row, x, facing), frame=index,
                        failure=result['error'], room=room, extra=extra)
        kid_pose = result['kid_pose']
        result.update(level=number, left=room, entered=sim.word(sim.A5 - 0x4fc2), frame=index,
                      start=(native_room, row, x, facing), opponents=before,
                      port=port_frame(art, kid_frames, before, kid_pose))
        return result
    return dict(level=number, start=(native_room, row, x, facing), crossing=None)


def run_probe(source, *, rooms=None, distances=EDGE_DISTANCES, levels=LEVELS):
    forks = Path(source) / 'resource_forks'
    program = (forks / 'Prince of Persia 2.bin').read_bytes()
    banks = {name: (forks / f'{name}.rsrc.bin').read_bytes()
             for name in ('Prince', 'Kid', 'Skeleton', 'Caverns')}
    skeleton = parse_resource_fork(banks['Skeleton'])
    kid = parse_resource_fork(banks['Kid'])
    art = SimpleNamespace(frames=parse_frame_records(skeleton['FRAM'][750]['data']))
    kid_frames = parse_frame_records(kid['FRAM'][25001]['data'])
    counts, sources, port, examples = Counter(), Counter(), Counter(), []
    digest = hashlib.sha256()
    traps, failures = Counter(), []
    heaps, heap_examples, phases = Counter(), [], Counter()
    settler = NativeSettle(parse_resource_fork(program))
    prince = parse_resource_fork(banks['Prince'])
    original = {number: prince['LEVL'][1999 + number]['data'] for number in levels}
    for number in levels:
        sim = NativeCrossing(program, banks)
        level_address = start_level(sim, number)
        snapshot = Snapshot(sim)
        level = bytes(sim.cpu.mem_read(level_address, 0x2200))
        records = [words for room in range(1, 33) for words in bank_records(sim, level_address, room)]
        for native_room in range(1, 33):
            if rooms is not None and (number, native_room) not in rooms:
                continue
            print(f'level {number} room {native_room}: {dict(counts)}', file=sys.stderr, flush=True)
            left, right = struct.unpack_from('>2H', level, 0x2080 + (native_room - 1) * 8)
            for side, facing, neighbour in (('left', -1, left), ('right', 0, right)):
                if not neighbour:
                    continue
                for extra in (None, *records):
                    for row in range(3):
                        for distance in distances:
                            x = 207 + distance if side == 'left' else 717 - distance
                            result = run_case(sim, snapshot, level_address, number, native_room,
                                              row, x, facing, extra, art, kid_frames)
                            if result is None:
                                counts['full_room_skipped'] += 1
                                continue
                            counts['cases'] += 1
                            if 'failure' in result:
                                counts['native_failures'] += 1
                                failures.append(result)
                                continue
                            if result.get('crossing', 1) is None:
                                counts['no_crossing'] += 1
                                continue
                            if 'error' in result:
                                raise AssertionError(result)
                            counts['crossings'] += 1
                            counts['with_settle'] += bool(result['settles'])
                            sources[f"{result['source']} {result['phase']} {result['site']}"] += 1
                            if result['foreign'] or result['between']:
                                raise AssertionError(('foreign frame writer', result))
                            for cached, _record in result['settles']:
                                if cached != result['cache']:
                                    raise AssertionError(('settle cache changed', result))
                            native = result['cache'][2], result['cache'][4]
                            agree = native == tuple(result['port'])
                            kind = 'agree' if agree else classify(result)
                            port[kind] += 1
                            phases[f"{kind} | {result['phase']} {result['site']}"] += 1
                            for cached, words in result['settles']:
                                # The original 4:198a again, with the port's frame words.
                                slot = words[7]
                                address = 0x20e6 + result['entered'] * 0xc0 + 2 + slot * 38
                                outcomes = [native_settle(settler, original[number], result['entered'], slot,
                                                          address, list(words), frame)
                                            for frame in ((cached[2], cached[4]), tuple(result['port']))]
                                heaps['same' if outcomes[0] == outcomes[1] else 'different'] += 1
                                if outcomes[0] != outcomes[1] and len(heap_examples) < 30:
                                    heap_examples.append(dict(case=result, native=outcomes[0],
                                                              port=outcomes[1]))
                            group = f"{kind} | {result['phase']} {result['site']}"
                            if not agree or result['phase'] != 'opponent_pass' or 'opponent 2:' not in result['site']:
                                if sum(e['group'] == group for e in examples) < 5:
                                    examples.append(dict(result, group=group))
                            digest.update(json.dumps([result['level'], result['left'], result['entered'],
                                                      result['cache']]).encode())
        traps.update(sim.traps)
    return dict(counts=dict(counts), sources=dict(sources), port=dict(port), examples=examples,
                failures=failures, heap_settles=dict(heaps), heap_examples=heap_examples,
                port_by_source=dict(phases),
                traps=dict(traps), executable_sha256=hashlib.sha256(program).hexdigest(),
                outputs_sha256=digest.hexdigest(), exclusions=__doc__)


def classify(result):
    opponents = result['opponents']
    if result['source'] == 'prince':
        return 'native_prince_port_opponent' if opponents else 'prince_pose'
    if not opponents:
        return 'native_opponent_port_prince'
    if result['slot'] != opponents[-1]['slot']:
        return 'different_slot'
    if opponents[-1]['pose'] != result['pose']:
        return 'pose_advanced_in_frame'
    return 'same_pose_other'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--level', type=int, action='append', choices=LEVELS)
    args = parser.parse_args()
    result = run_probe(args.source, levels=tuple(args.level or LEVELS))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(counts=result['counts'], sources=result['sources'], port=result['port'],
                          heap_settles=result['heap_settles'])))


if __name__ == '__main__':
    main()
