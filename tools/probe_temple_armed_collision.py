"""Bounded armed4:589e with real rock lookup, strike predicate and animation.

Type0 incoming actor/contact side, cached tile, static MOB records and frame
width are supplied. Actual5:21f6/10:20fe rock lookup,6:5d60, movement, JumpSeq,
AnimChar and Kid reload execute. Resource/handle services and sound10 playback
are explicit endpoints. No physical admission, moving rock update or full frame.
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
from tools.probe_temple_air_collision import NativeTempleAirCollision
from tools.probe_temple_controller_geometry import left_edge_reference, MOB_BANK
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_ground_bump import NativeTempleGroundBump, bump_clip_reference
from tools.probe_temple_kid_frames import kid_frame_reference
from tools.probe_temple_slide_rock_update import actor_word


def armed_collision_reference(actor, side, level, bank, cache, sequences, frames, attachments,
                              *, available=True, width=40, remainder=79,
                              metadata=bytes(range(18)), mark=73):
    if (len(actor) != 62 or actor_word(actor, 8) != 0 or actor_word(actor, 26) != 1
            or actor_word(actor, 2) not in (-1, 0) or side not in (-1, 0)):
        raise ValueError('Expected a complete armed type0 actor and native side')
    working, events = bytearray(actor), [('align',)]
    put_actor(working, 6, actor_word(actor, 14)*120+106)

    def move(dx):
        put_actor(working, 4, actor_word(working, 4)+(dx if actor_word(working, 2) == 0 else -dx))

    def result(load=False, changed_mark=mark):
        if load:
            loaded = kid_frame_reference(bytes(working), frames, attachments)
            return dict(actor=loaded['actor'], metadata=loaded['metadata'], remainder=loaded['remainder'],
                        mark=changed_mark, events=events+[('frame',)])
        return dict(actor=bytes(working), metadata=metadata, remainder=remainder, mark=changed_mark, events=events)

    if actor_word(actor, 20) >= 50:
        move(-17)
        return result(True)
    put_actor(working, 20, 0)
    if actor_word(actor, 28) == 0:
        return result()
    room, row = actor_word(actor, 22), actor_word(actor, 14)
    events.append(('rock_query', room, row))
    rock_edge = 0
    if struct.unpack_from('>h', level, 0x2186)[0] == 2:
        events.append(('rock_edge', 0, room, row))
        record = next((r for r in bank if r[5] == 6 and r[3] != -1 and r[2] == room and r[6] == row), None)
        if record is not None:
            rock_edge = signed_word(record[0]+279)
            if rock_edge and actor_word(working, 4) < rock_edge:
                events.append(('rock_edge', -1, room, row))
                left = left_edge_reference(level, record, actor_word(actor, 2), width)
                rock_edge, remainder = left['edge'], left['remainder']
    if side == actor_word(actor, 2):
        if actor_word(actor, 38) == 55 and actor_word(actor, 10) == 207:
            move(17)
        move(6)
        selected = 65
    else:
        selected = 64
        pose = actor_word(actor, 10)
        events.append(('strike', 0, pose))
        if pose in (153, 154, 244, 245):
            if cache[0] == 4 and cache[1] & 255 > 60:
                selected = -1
            else:
                move(25)
    if rock_edge and actor_word(working, 4) < rock_edge:
        selected = 93
        put_actor(working, 26, 0)
    if selected == -1:
        return result()
    events.append(('resource', selected))
    if available:
        for offset, value in ((36, 0), (38, selected), (40, selected)):
            put_actor(working, offset, value)
    clip = bump_clip_reference(bytes(working), sequences)
    working = bytearray(clip['actor'])
    events.extend(clip['events'])
    output = result(True, mark if selected == 64 else 1)
    if selected == 64 and actor_word(working, 40) != 56:
        output['events'].append(('sound', 10))
    return output


class NativeTempleArmedCollision(NativeTempleAirCollision):
    RANGES = dict(NativeTempleAirCollision.RANGES)
    RANGES[3] = ((0x4ef2, 0x4f24),)
    RANGES[4] += ((0x591a, 0x59b4), (0x322a, 0x3262))
    RANGES[5] += ((0x21f6, 0x2224), (0x293c, 0x2996))
    RANGES[6] += ((0x5d60, 0x5e2e),)
    RANGES[10] = ((0x20fe, 0x213a), (0x180e, 0x18f2), (0x1a9e, 0x1aea))

    def dispatch(self, cpu, address, size, user):
        stack = cpu.reg_read(self.registers['a7'])
        if address in (self.address(17, 0x330e), self.address(4, 0x3098)):
            if address == self.address(17, 0x330e):
                kind, number = struct.unpack('>4sh', cpu.mem_read(stack+4, 6))
                if kind != b'SEQS' or number not in (64, 65, 93):
                    raise AssertionError('Unexpected armed reaction resource')
                self.events.append(('resource', number))
                exists = self.available
            else:
                number = struct.unpack('>h', cpu.mem_read(stack+4, 2))[0]
                self.events.append(('sequence', number))
                exists = True
            self.return_value(self.sequences[number][0] if exists else 0)
            return
        if address == self.address(5, 0x4d84):
            self.events.append(('sound', struct.unpack('>h', cpu.mem_read(stack+4, 2))[0]))
            self.return_value(0)
            return
        if address == self.address(4, 0x31fa):
            self.events.append(('align',))
        elif address == self.address(5, 0x21f6):
            self.events.append(('rock_query', *struct.unpack('>2h', cpu.mem_read(stack+4, 4))))
        elif address == self.address(10, 0x180e):
            self.events.append(('rock_edge', *struct.unpack('>3h', cpu.mem_read(stack+4, 6))))
        elif address == self.address(6, 0x5d60):
            self.events.append(('strike', *struct.unpack('>2h', cpu.mem_read(stack+4, 4))))
        NativeTempleGroundBump.dispatch(self, cpu, address, size, user)


def run_probe(source):
    forks = Path(source)/'resource_forks'
    executable = (forks/'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(executable)
    prince = parse_resource_fork((forks/'Prince.rsrc.bin').read_bytes())
    kid = parse_resource_fork((forks/'Kid.rsrc.bin').read_bytes())
    raw = {n: prince['SEQS'][n]['data'] for n in (2, 55, 64, 65, 93)}
    sequences = {n: struct.unpack('>'+str(len(d)//2)+'h', d) for n, d in raw.items()}
    frames = kid['FRAM'][25001]['data']
    counts, outcomes, digest = Counter(), Counter(), hashlib.sha256()
    for attachment_id in (25001, 25201):
        attachments = kid['AFRM'][attachment_id]['data']
        machine = NativeTempleArmedCollision(program, raw, frames, attachments)

        def check(label, *, pose=153, facing=0, side=-1, vy=49, alive=-1, available=True,
                  hp=3, pending=0, active=2, selected=2, gate=60, tile=4, x=460, bank=(), width=40, env=2):
            level = bytearray(prince['LEVL'][2009]['data'])
            struct.pack_into('>h', level, 0x2186, env)
            actor = bytearray(actor_fixture(1, 1, 4, facing, 0))
            for offset, value in ((4, x), (6, 180), (8, 0), (10, pose), (18, 5), (20, vy),
                    (24, 17), (26, 1), (28, alive), (30, hp), (34, pending), (36, 0), (38, active), (40, selected)):
                put_actor(actor, offset, value)
            actor = bytes(actor)
            cache = (tile, signed_word(gate), 14, 1, 4, 1)
            expected = armed_collision_reference(actor, side, level, bank, cache, sequences, frames, attachments,
                                                 available=available, width=width)
            machine.reset(level)
            machine.available = available
            storage = bytearray((i*19+7)%256 for i in range(512))
            for i, record in enumerate(bank):
                struct.pack_into('>8h', storage, 16+i*16, *record)
            machine.cpu.mem_write(MOB_BANK-16, bytes(storage))
            machine.cpu.mem_write(machine.A5-0x4496, struct.pack('>I', MOB_BANK))
            machine.put_word(-0x4490, len(bank))
            machine.cpu.mem_write(machine.A5-0x5056, actor)
            machine.cpu.mem_write(machine.A5-0x50d2, bytes(range(62)))
            machine.cpu.mem_write(machine.A5-0x448e, bytes(range(160)))
            machine.cpu.mem_write(machine.A5-0x34b0, struct.pack('>6h', *cache))
            machine.cpu.mem_write(machine.A5-0x521a, bytes(range(18)))
            for offset, value in ((-0x481c, 79), (-0x4f9e, 73), (-0x3564, 400), (-0x3566, 400+width)):
                machine.put_word(offset, value)
            before = bytearray(machine.cpu.mem_read(machine.A5-len(machine.data), len(machine.data)))
            machine.call(4, 0x589e, (side,))
            before[len(machine.data)-0x5056:len(machine.data)-0x5056+62] = expected['actor']
            before[len(machine.data)-0x521a:len(machine.data)-0x521a+18] = expected['metadata']
            for offset, name in ((-0x481c, 'remainder'), (-0x4f9e, 'mark')):
                struct.pack_into('>h', before, len(machine.data)+offset, expected[name])
            after = bytes(machine.cpu.mem_read(machine.A5-len(machine.data), len(machine.data)))
            if (after != before or machine.events != expected['events'] or machine.services
                    or machine.level_bytes(len(level)) != level
                    or bytes(machine.cpu.mem_read(MOB_BANK-16,512)) != storage):
                raise AssertionError(dict(label=label, attachment=attachment_id, pose=pose, facing=facing, side=side,
                    gate=gate, bank=bank, expected=expected, events=machine.events,
                    changed=[(hex(i-len(machine.data)),a,b) for i,(a,b) in enumerate(zip(before,after)) if a!=b]))
            machine.verify_resources()
            counts[f'{attachment_id}:{label}'] += 1
            outcomes[str(expected['events'][-1:])] += 1
            digest.update(expected['actor']+expected['metadata']+struct.pack('>2h',expected['remainder'],expected['mark']))
            digest.update(json.dumps(expected['events']).encode('ascii'))

        for pose, facing, side, available, vy in product(range(352), (-1,0), (-1,0), (False,True), (49,50)):
            check('all_poses',pose=pose,facing=facing,side=side,available=available,vy=vy)
        for pose, gate, tile, facing in product((152,153,154,155,243,244,245,246), (59,60,61,184,255,0x813d), (1,4), (-1,0)):
            check('strike_gate_edges',pose=pose,gate=gate,tile=tile,facing=facing,side=~facing)
        for active, pose, side, facing, selected, available in product((2,55), (206,207,208), (-1,0), (-1,0), (2,56), (False,True)):
            check('active_source',active=active,pose=pose,side=side,facing=facing,selected=selected,available=available)
        for alive, hp, pending, vy, facing in product((0,-1), (0,3), (-3,0), (-1,49,50), (-1,0)):
            check('life_velocity',alive=alive,hp=hp,pending=pending,vy=vy,facing=facing)
        for rockx, x, facing, side, width, env in product((102,153,255), (250,460,600), (-1,0), (-1,0), (0,40), (2,3)):
            bank=((rockx,236,1,0,-2,6,1,459),)
            check('static_rocks',x=x,facing=facing,side=side,width=width,env=env,bank=bank)
        for bank in ((), ((153,236,1,-1,-2,6,1,459),), ((153,236,1,0,-2,5,1,459),),
                     ((153,236,2,0,-2,6,1,459),), ((153,236,1,0,-2,6,0,459),),
                     ((102,236,1,0,-2,6,1,459),(255,236,1,0,-2,6,1,459))):
            check('bank_filter',bank=bank,x=300)
        for x,facing,side,vy in product((-32768,22,460,32767),(-1,0),(-1,0),(49,50)):
            check('signed_x',x=x,facing=facing,side=side,vy=vy)
        for x,facing in product((370,371,372),(-1,0)):
            check('rock_equality',x=x,facing=facing,side=~facing,gate=61,
                  bank=((153,236,1,0,-2,6,1,459),))
    return dict(comparisons=dict(counts), mismatches=0, outcomes=dict(outcomes),
                executable_sha256=hashlib.sha256(executable).hexdigest(), outputs_sha256=digest.hexdigest(),scope=__doc__)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=run_probe(args.source)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
