"""Connect native type0 frame loading to world control and bounded persistent clips."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_sequence_selection import signed_word
from tools.probe_temple_controller_geometry import MOB_BANK, NativeTempleControllerGeometry, geometry_player_reference
from tools.probe_temple_gate_actor_clip import clip_reference, put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_hanging_control import LATCHES
from tools.probe_temple_kid_frames import FRAME_RANGES, bind_frames, install_frames, kid_frame_reference, verify_frames
from tools.probe_temple_plate_release import initial_state
from tools.probe_temple_player_control import AXES, SAVED_LATCHES, PlayerInputs
from tools.probe_temple_slide_rock_update import actor_word
from tools.probe_temple_world_prince import EDGE_DESTINATIONS, EDGE_SOURCES, world_reference


CONTINUATION = {2: 8, 9: 8, 10: 6, 11: 2, 23: 2, 25: 5, 47: 8, 73: 10, 99: 2}


def frame_callback(frames, attachments):
    def load(actor, _state):
        result = kid_frame_reference(actor, frames, attachments)
        return dict(actor=result['actor'], updates=dict(frame_metadata=result['metadata'], division_remainder=result['remainder']))
    return load


def continue_reference(state, sequences, operation, loader):
    result = dict(state)
    if operation == 'animate':
        clip = clip_reference(state['working'], sequences, vertical=True)
        result.update(working=clip['actor'], events=clip['events'])
    elif operation == 'frame':
        frame = loader(state['working'], state)
        result.update(working=frame['actor'], events=[('frame',)], **frame['updates'])
    else:
        raise ValueError('Only separately scheduled animation and frame continuation are bounded')
    return result


class NativeTempleFrameProgression(NativeTempleControllerGeometry):
    RANGES = {segment: NativeTempleControllerGeometry.RANGES.get(segment, ()) + FRAME_RANGES.get(segment, ())
              for segment in NativeTempleControllerGeometry.RANGES.keys() | FRAME_RANGES.keys()}
    ENDPOINTS = {key: value for key, value in NativeTempleControllerGeometry.ENDPOINTS.items() if key != (4, 0x2a72)}

    def __init__(self, program, sequences, frames, attachments):
        super().__init__(program, sequences)
        install_frames(self, frames, attachments)

    def reset(self, level):
        super().reset(level)
        bind_frames(self)

    def dispatch(self, cpu, address, size, user):
        if address == self.address(4, 0x2a72):
            self.events.append(('frame',))
        super().dispatch(cpu, address, size, user)

    def snapshot(self, size):
        return dict(super().snapshot(size), frame_metadata=bytes(self.cpu.mem_read(self.A5 - 0x521a, 18)))


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    resources = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    kid = parse_resource_fork((directory / 'Kid.rsrc.bin').read_bytes())
    frames, attachments = kid['FRAM'][25001]['data'], kid['AFRM'][25001]['data']
    raw = {n: resources['SEQS'][n]['data'] for n in (2, 9, 10, 11, 23, 25, 47, 73, 99, 210)}
    sequences = {n: struct.unpack('>' + str(len(data) // 2) + 'h', data) for n, data in raw.items()}
    machine = NativeTempleFrameProgression(parse_resource_fork(executable), raw, frames, attachments)
    loader = frame_callback(frames, attachments)
    counts, outcomes, digest = Counter(), Counter(), hashlib.sha256()
    inventory = []
    for number in range(10, 14):
        level = resources['LEVL'][1999 + number]['data']
        if (struct.unpack_from('>3h', level, 0x2186)[::2] != (2, number)
                or struct.unpack_from('>h', level, 0x21a4)[0] != 7):
            raise ValueError('Expected original temple/opponent headers')
        for room, cell in product(range(1, struct.unpack_from('>h', level, 0x2180)[0] + 1), range(30)):
            if struct.unpack_from('>h', level, (room - 1) * 60 + cell * 2)[0] == 4:
                inventory.append((number, level, room, cell))
    if len(inventory) != 41:
        raise ValueError('Expected41 original temple gates')
    scratch = bytearray((i * 7 + 13) % 256 for i in range(22))
    struct.pack_into('>I', scratch, 16, MOB_BANK)
    scratch = bytes(scratch)
    for (number, original, room, cell), (position, phase), facing, raw_axes, offset in product(
            inventory, ((3, 1), (12, 1), (120, 4)), (-1, 0), ((0, 0, -1), (0, -1, -1), (0, 0, 0)), (0, 25, 50)):
        row, column = divmod(cell, 10)
        level = bytearray(original)
        struct.pack_into('>H', level, 0x780 + (room - 1) * 120 + cell * 4, position)
        inputs = PlayerInputs(raw_axes=raw_axes)
        actor = bytearray(actor_fixture(room, row + 1, column, facing, 2))
        for field, value in ((4, 230 + column * 51 + offset), (6, row * 120 + 110), (10, 91), (18, 0), (20, 0),
                (24, -1), (26, 0), (28, -1), (30, 3), (34, 0), (36, 3), (38, 9), (40, 9), (52, 0), (58, -1)):
            put_actor(actor, field, value)
        state = dict(initial_state(level, ((cell, room, phase, 4),)), prince=bytes(actor), working=bytes(range(62)),
                     countdown=-2, saved_edges=(211, 223, 227, 229), exit_flag=1234, view=room, result=-2,
                     cooldown=0, input_latches=(0, 0, 0, 0, 0), working_latches=(31, 37, 41, 43, 47),
                     raw_axes=(53, 59, 61), cell_cache=struct.pack('>6h', 0, 0, 0, 0, -32768, -32768),
                     division_remainder=61, frame_width=18, mob_records=(),
                     mob_storage=bytes((i * 19 + 7) % 256 for i in range(512)), frame_metadata=bytes(range(18)))
        machine.reset(level)
        machine.inputs = inputs
        for destination, data in ((-0x5056, state['working']), (-0x50d2, state['prince']), (-0x448e, state['trob_storage']),
                (-0x4818, state['os']), (-0x43ee, struct.pack('>4h', *state['scratch'])), (-0x34b0, state['cell_cache']),
                (-0x44a6, scratch), (-0x521a, state['frame_metadata'])):
            machine.cpu.mem_write(machine.A5 + destination, data)
        machine.cpu.mem_write(MOB_BANK - 16, state['mob_storage'])
        machine.cpu.mem_write(machine.A5 - 0x43a4, b'\0' * 4)
        for destinations, values in ((SAVED_LATCHES, state['input_latches']), (LATCHES, state['working_latches']),
                (AXES, state['raw_axes']), (EDGE_DESTINATIONS, state['saved_edges']),
                ((-0x3560, -0x3562, -0x3568, -0x356a), EDGE_SOURCES)):
            for destination, value in zip(destinations, values):
                machine.put_word(destination, value)
        for destination, value in ((-0x43e6, 1), (-0x4fc2, room), (-0x5008, -2), (-0x4490, 0),
                (-0x439e, 192), (-0x4f96, 0), (-0x4fee, 1), (-0x4fac, 0), (-0x4f90, 0),
                (-0x4fce, 1), (-0x4faa, 1234), (-0x4fa6, 0), (-0x5200, 0), (-0x4fa8, 0), (-0x4ffe, 0),
                (-0x4f92, number), (-0x4fd2, number), (-0x43b6, 0), (-0x481c, 61), (-0x3564, 400), (-0x3566, 418)):
            machine.put_word(destination, value)

        def compare(label, returned=None):
            actual = dict(machine.snapshot(len(level)), result=state['result'] if returned is None else returned)
            names = set(machine.ENDPOINTS.values()) | {'sample_input'}
            expected_services = Counter({'sound': 'gate_sound', 'redraw': 'gate_redraw', 'audio': 'audio_request'}
                                        .get(e[0], e[0]) for e in state['events']
                                        if e[0] in names | {'sound', 'redraw', 'audio'})
            if (actual != state or machine.services != expected_services
                    or bytes(machine.cpu.mem_read(machine.A5 - 0x44a6, 22)) != scratch or machine.word(-0x439e) != 192):
                raise AssertionError(dict(fixture=(number, room, cell, position, phase, facing, raw_axes, offset), operation=label,
                                          differences={k: (actual[k], state[k]) for k in state if actual[k] != state[k]},
                                          services=(machine.services, expected_services)))
            machine.verify_sequences()
            verify_frames(machine)
            counts[label] += 1
            digest.update(state['level'] + state['prince'] + state['working'] + state['trob_storage'] + state['cell_cache']
                          + state['frame_metadata'] + state['mob_storage'])
            digest.update(json.dumps([state['events'], state['division_remainder'], state['input_latches'], state['result']]).encode('ascii'))

        state = world_reference(state, sequences, inputs, geometry_player_reference, loader)
        compare('world', signed_word(machine.call(2, 0x6224)))
        source = actor_word(state['working'], 40)
        outcomes[f'initial-source{source}'] += 1
        for _step in range(CONTINUATION[source]):
            for operation in ('animate', 'frame'):
                before = state['working']
                machine.events = []
                machine.services.clear()
                state = continue_reference(state, sequences, operation, loader)
                machine.call(4, 0x2c0c if operation == 'animate' else 0x2a72)
                compare(operation)
                if operation == 'frame':
                    outcomes['supporting-column-changed'] += actor_word(before, 12) != actor_word(state['working'], 12)
                else:
                    outcomes['script-row-changed'] += actor_word(before, 14) != actor_word(state['working'], 14)
                    outcomes['script-y-changed'] += actor_word(before, 6) != actor_word(state['working'], 6)
    return dict(cases=dict(counts), traces=counts['world'], comparisons=sum(counts.values()), mismatches=0,
                outcomes=dict(outcomes), continuation=CONTINUATION, outputs_sha256=digest.hexdigest(),
                executable_sha256=hashlib.sha256(executable).hexdigest(), frame_sha256=hashlib.sha256(frames).hexdigest(),
                attachment_sha256=hashlib.sha256(attachments).hexdigest(),
                sequence_sha256={str(n): hashlib.sha256(data).hexdigest() for n, data in raw.items()},
                supplied_services={f'{s}:{o:04x}': name for (s, o), name in machine.ENDPOINTS.items()},
                other_supplied=['2:55d2 sampled axes', '5:3828/0fe6/4d84 cue/redraw/audio',
                                '17:330e/4:3098 prepared sequence handles; state0 handle traps; prepared Kid frame bindings'],
                scope='One actual world/Prince/PlayerCtrl update with real LoadFrame/current/front/above/rock query '
                      'followed by separately scheduled persistent AnimChar/LoadFrame pairs. Original type0 Kid metadata '
                      'and bounded original clips including optional Y/row opcodes. Saved Prince remains the actual first '
                      'world result during continuation; no later actor copy or full world/GenCtrl/physics is implied. '
                      'GetCharEdges/frame width, other contact/hazards and external services supplied; empty MOB bank. '
                      'No physical reachability, full falling/climbing, outer FrameAdv, saves or runtime integration.')


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
