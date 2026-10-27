"""Recover4:3982 wall spacing with real point/column/cell and Kid reload.

Incoming actor, frame metadata and caller admission are supplied. Ordinary
temple cells, horizontal/vertical links, IsWall, relative movement, frame reload
and final cell refresh execute. Prepared FRAM/AFRM handles only; no animation,
ShapeBounds, prior Collide correction or complete physical/frame composition.
"""
import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_sequence_selection import signed_word, supporting_column
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_gate_standing import COLD_CACHE, StandingCellReader
from tools.probe_temple_ground_bump import NativeTempleGroundBump
from tools.probe_temple_kid_frames import kid_frame_reference
from tools.probe_temple_slide_rock_geometry import NativeSlideRockGeometry
from tools.probe_temple_slide_rock_update import actor_word


WALLS=frozenset((2,7,20,25))

def spacing_reference(actor, metadata, reader, frames, attachments, *, remainder=79):
    if (len(actor)!=62 or len(metadata)!=18 or actor_word(actor,2) not in (-1,0)
            or actor_word(actor,8) not in (0,11)):
        raise ValueError('Expected a complete type0 actor or the explicitly skipped type11')
    working=bytearray(actor);events=[];adjustment=None;distance=None
    row, room, column=(actor_word(actor,o) for o in (14,22,12))
    special=actor_word(actor,52)
    env=struct.unpack_from('>h',reader.level,0x2186)[0]
    def read_cell(room,column,row):
        tile=reader.read(room,column,row)
        if env!=2 and reader.cache[3]==0:
            raise ValueError('Non-temple undefined-cell fallback is outside this spacing proof')
        return tile
    skip=(special==4 or actor_word(actor,8)==11 or (room==3 and env==6 and column<0))
    if not skip:
        # GetCharPoint uses the prepared current metadata, which need not be
        # the frame selected by a later LoadFrame. Keep these inputs distinct.
        _,remainder=supporting_column(actor_word(actor,4),actor_word(actor,2),metadata[8:])
        distance=signed_word(50-remainder) if actor_word(actor,2)==0 else remainder
        ahead=read_cell(room,column+(-1 if actor_word(actor,2)==-1 else 1),row)
        adjustment=signed_word(distance-51) if distance>=18 or ahead in WALLS else signed_word(distance+18)
        put_actor(working,4,actor_word(actor,4)+(adjustment if actor_word(actor,2)==0 else -adjustment))
        loaded=kid_frame_reference(bytes(working),frames,attachments)
        working=bytearray(loaded['actor']);metadata=loaded['metadata'];remainder=loaded['remainder']
        events.append(('frame',))
    returned=read_cell(actor_word(working,22),actor_word(working,12),actor_word(working,14))
    return dict(actor=bytes(working),metadata=metadata,remainder=remainder,events=events,
                returned=returned&65535,adjustment=adjustment,distance=distance,skip=skip)


class NativeTempleWallSpacing(NativeTempleGroundBump):
    RANGES={s:NativeTempleGroundBump.RANGES.get(s,())+NativeSlideRockGeometry.RANGES.get(s,())
            for s in NativeTempleGroundBump.RANGES.keys()|NativeSlideRockGeometry.RANGES.keys()}
    RANGES[3]+=((0x4ef2,0x4f24),)
    RANGES[4]+=((0x3982,0x3a32),(0x3a92,0x3ac8),(0x35a6,0x35b8))

    def reset(self,level):
        super().reset(level)
        self.reads=[]

    def dispatch(self,cpu,address,size,user):
        if address==self.address(4,0x27ee):
            stack=cpu.reg_read(self.registers['a7'])
            self.reads.append(struct.unpack('>3h',cpu.mem_read(stack+4,6)))
        super().dispatch(cpu,address,size,user)


def run_probe(source):
    forks=Path(source)/'resource_forks'
    executable=(forks/'Prince of Persia 2.bin').read_bytes()
    program=parse_resource_fork(executable)
    prince=parse_resource_fork((forks/'Prince.rsrc.bin').read_bytes())
    kid=parse_resource_fork((forks/'Kid.rsrc.bin').read_bytes())
    frames=kid['FRAM'][25001]['data']
    counts,outcomes,digest=Counter(),Counter(),hashlib.sha256()
    for attachment_id in (25001,25201):
        attachments=kid['AFRM'][attachment_id]['data']
        machine=NativeTempleWallSpacing(program,{},frames,attachments)

        def check(label,level,room,column,row,*,facing=0,x=None,pose=15,special=0,kind=0,
                  warm=False,metadata=None):
            actor=bytearray(actor_fixture(room,row,column,facing,0))
            for off,value in ((4,207+column*51+25 if x is None else x),(8,kind),(10,pose),
                              (26,1),(28,-1),(30,3),(52,special)):
                put_actor(actor,off,value)
            actor=bytes(actor)
            if metadata is None:
                # Type11 is a no-reload exception; its prepared metadata is
                # explicit and never interpreted as a Kid frame by native code.
                if kind==11:
                    metadata=bytes(range(18))
                else:
                    metadata=kid_frame_reference(actor,frames,attachments)['metadata']
            # Cell traversal itself is shared by environment2/6; the reader's
            # temple-only constructor validates a copy, then queries original.
            fixture=bytearray(level);struct.pack_into('>h',fixture,0x2186,2)
            reader=StandingCellReader(fixture,room);reader.level=level
            machine.reset(level)
            machine.put_word(-0x4fc2,room)
            machine.cpu.mem_write(machine.A5-0x5056,actor)
            machine.cpu.mem_write(machine.A5-0x50d2,bytes(range(62)))
            machine.cpu.mem_write(machine.A5-0x448e,bytes(range(160)))
            machine.cpu.mem_write(machine.A5-0x34b0,struct.pack('>6h',*COLD_CACHE))
            machine.cpu.mem_write(machine.A5-0x521a,metadata)
            machine.put_word(-0x481c,79);machine.put_word(-0x4f9e,73)
            if warm:
                reader.read(room,column,row)
                machine.call(4,0x27ee,(room,column,row))
                reader.requests.clear();machine.reads.clear()
            before=bytearray(machine.cpu.mem_read(machine.A5-len(machine.data),len(machine.data)))
            expected=spacing_reference(actor,metadata,reader,frames,attachments)
            actual=machine.call(4,0x3982)
            before[len(machine.data)-0x5056:len(machine.data)-0x5056+62]=expected['actor']
            before[len(machine.data)-0x521a:len(machine.data)-0x521a+18]=expected['metadata']
            struct.pack_into('>h',before,len(machine.data)-0x481c,expected['remainder'])
            struct.pack_into('>6h',before,len(machine.data)-0x34b0,*reader.cache)
            if reader.pointer_room is not None:
                rr=reader.pointer_room
                struct.pack_into('>II',before,len(machine.data)-0x4824,
                                 machine.LEVEL+0x780+(rr-1)*120,machine.LEVEL+(rr-1)*60)
            after=bytes(machine.cpu.mem_read(machine.A5-len(machine.data),len(machine.data)))
            if (actual!=expected['returned'] or after!=before or machine.events!=expected['events']
                    or machine.reads!=reader.requests or machine.services or machine.level_bytes(len(level))!=level):
                raise AssertionError(dict(label=label,attachment=attachment_id,actor=actor.hex(),metadata=metadata.hex(),
                    actual=actual,expected=expected,events=machine.events,reads=machine.reads,expected_reads=reader.requests,
                    changed=[(hex(i-len(machine.data)),a,b) for i,(a,b) in enumerate(zip(before,after)) if a!=b]))
            machine.verify_resources()
            counts[f'{attachment_id}:{label}']+=1
            outcomes[f"skip{expected['skip']}:delta{expected['adjustment']}"]+=1
            digest.update(expected['actor']+expected['metadata']+struct.pack('>Hh6h',actual,expected['remainder'],*reader.cache))
            digest.update(json.dumps(reader.requests).encode('ascii'))

        for number in range(10,14):
            level=prince['LEVL'][1999+number]['data']
            for room,cell in product(range(1,33),range(30)):
                if struct.unpack_from('>h',level,(room-1)*60+cell*2)[0] not in WALLS:continue
                row,column=divmod(cell,10)
                for facing,residual in product((-1,0),(0,17,18,50)):
                    check(f'level{number}_wall_anchors',level,room,column,row,facing=facing,
                          x=207+column*51+residual)
        level=prince['LEVL'][2009]['data']
        for pose,facing,residual,warm in product(range(352),(-1,0),(17,18),(False,True)):
            check('pose_frame_controls',level,1,4,1,pose=pose,facing=facing,x=411+residual,warm=warm)
        for facing,kind,special,warm in product((-1,0),(0,11),(0,4),(False,True)):
            check('skip_controls',level,1,4,1,facing=facing,kind=kind,special=special,warm=warm)
        for env,column,facing,special,(room,row) in product((2,6),(-1,0),(-1,0),(0,4),((3,1),(1,3),(3,3))):
            fixture=bytearray(level);struct.pack_into('>h',fixture,0x2186,env)
            # The shared cell model bounds undefined-cell behavior to the
            # temple. Keep this non-temple exception control in live rooms.
            for linked_room in (1,2,3):
                struct.pack_into('>4h',fixture,0x2080+(linked_room-1)*8,2,2,2,2)
            check('room3_environment',fixture,room,column,row,facing=facing,special=special)
        # Exact18 boundary with deliberately supplied current metadata. Its
        # displacement is independent of the pose reloaded after the move.
        for facing,distance,front_kind in product((-1,0),(17,18,19),(0,1,2,4,7,20,25)):
            fixture=bytearray(level)
            col=4+(-1 if facing==-1 else 1)
            struct.pack_into('>h',fixture,10*2+col*2,front_kind)
            rem=50-distance if facing==0 else distance
            metadata=bytes(8)+struct.pack('>5h',1,0,0,0,0)
            check('distance18_front_tiles',fixture,1,4,1,facing=facing,x=26+8*51+rem,metadata=metadata)
    return dict(comparisons=dict(counts),mismatches=0,outcomes=dict(outcomes),
                executable_sha256=hashlib.sha256(executable).hexdigest(),outputs_sha256=digest.hexdigest(),scope=__doc__)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=run_probe(args.source)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,indent=2))
