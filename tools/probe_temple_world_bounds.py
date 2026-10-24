"""Connect actual Kid drawing/collision bounds to native world and rock queries."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_sequence_selection import signed_word
from tools.probe_temple_controller_geometry import MOB_BANK, geometry_player_reference
from tools.probe_temple_frame_progression import NativeTempleFrameProgression, frame_callback
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_hanging_control import LATCHES
from tools.probe_temple_kid_frames import verify_frames
from tools.probe_temple_plate_release import initial_state
from tools.probe_temple_player_control import AXES, SAVED_LATCHES, PlayerInputs
from tools.probe_temple_slide_rock_update import actor_word
from tools.probe_temple_sprite_bounds import (
    BOUNDS_RANGES, BOUND_WORDS, CELL_WORDS, DEFAULT_RECT, SCREEN_RECT,
    bind_bounds, bounds_reference, bounds_service, drawing_reference, shape_sizes,
)
from tools.probe_temple_world_prince import EDGE_DESTINATIONS, world_reference


def sprite_callback(sizes):
    def load(actor, state):
        drawn = drawing_reference(actor, state['frame_metadata'], state['drawing'])
        bounded = bounds_reference(actor, state['frame_metadata'], drawn, sizes, state['bounds'],
                                   state['edge_cells'], state['division_remainder'])
        bounds = bounded['bounds']
        return dict(actor=bounded['actor'], updates=dict(drawing=drawn, bounds=bounds, edge_cells=bounded['cells'],
                    division_remainder=bounded['remainder'], frame_width=bounds[3] - bounds[4],
                    current_edges=(bounds[6], bounds[5], bounds[2], bounds[1]),
                    bound_events=state['bound_events'] + bounded['services']))
    return load


class NativeTempleWorldBounds(NativeTempleFrameProgression):
    RANGES = {s: NativeTempleFrameProgression.RANGES.get(s, ()) + BOUNDS_RANGES.get(s, ())
              for s in NativeTempleFrameProgression.RANGES.keys() | BOUNDS_RANGES.keys()}
    ENDPOINTS = {key: name for key, name in NativeTempleFrameProgression.ENDPOINTS.items()
                 if key not in ((3, 0x0ac8), (4, 0x5cbc))}

    def __init__(self, program, sequences, frames, attachments, sizes):
        super().__init__(program, sequences, frames, attachments)
        self.sizes, self.shape_available, self.bound_events = sizes, True, []

    def reset(self, level):
        super().reset(level)
        bind_bounds(self)
        self.bound_events = []

    def dispatch(self, cpu, address, size, user):
        if bounds_service(self, cpu, address):
            return
        if address in (self.address(3, 0x0ac8), self.address(4, 0x5cbc)):
            self.events.append(('sword' if address == self.address(3, 0x0ac8) else 'edges',))
        super().dispatch(cpu, address, size, user)

    def snapshot(self, size):
        return dict(super().snapshot(size), drawing=bytes(self.cpu.mem_read(self.A5 - 0x34c6, 20)),
                    bounds=tuple(self.word(o) for o in BOUND_WORDS), edge_cells=tuple(self.word(o) for o in CELL_WORDS),
                    current_edges=tuple(self.word(o) for o in (-0x3560, -0x3562, -0x3568, -0x356a)),
                    bound_events=list(self.bound_events))


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    resources = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    kid = parse_resource_fork((directory / 'Kid.rsrc.bin').read_bytes())
    frames, attachments, sizes = kid['FRAM'][25001]['data'], kid['AFRM'][25001]['data'], shape_sizes(kid)
    raw = {n: resources['SEQS'][n]['data'] for n in (2, 9, 10, 11, 23, 25, 47, 73, 99, 210)}
    sequences = {n: struct.unpack('>' + str(len(data) // 2) + 'h', data) for n, data in raw.items()}
    machine = NativeTempleWorldBounds(parse_resource_fork(executable), raw, frames, attachments, sizes)
    loader, sprite = frame_callback(frames, attachments), sprite_callback(sizes)
    counts, outcomes, widths, initial_widths, digest = Counter(), Counter(), Counter(), Counter(), hashlib.sha256()
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
    for (number, original, room, cell), (position, phase), facing, raw_axes, pose, offset, occupied in product(
            inventory, ((3, 1), (12, 1), (120, 4)), (-1, 0), ((0, 0, -1), (0, -1, -1), (0, 0, 0)),
            (89, 91), (0, 25, 50), (False, True)):
        row, column = divmod(cell, 10)
        level = bytearray(original)
        struct.pack_into('>H', level, 0x780 + (room - 1) * 120 + cell * 4, position)
        inputs = PlayerInputs(raw_axes=raw_axes)
        actor = bytearray(actor_fixture(room, row + 1, column, facing, 2))
        for field, value in ((4, 230 + column * 51 + offset), (6, row * 120 + 110), (10, pose), (18, 0), (20, 0),
                (24, -1), (26, 0), (28, -1), (30, 3), (34, 0), (36, 2 if pose == 89 else 3),
                (38, 210 if pose == 89 else 9), (40, 9), (52, 0), (58, -1)):
            put_actor(actor, field, value)
        bank = ((column * 51 + (50 if column else 70), 116, room, 0, -2, 6, row, 459),) if occupied else ()
        storage = bytearray((i * 19 + 7) % 256 for i in range(512))
        if bank:
            struct.pack_into('>8h', storage, 16, *bank[0])
        bounds = (389, 229, 227, 418, 400, 103, 101)
        state = dict(initial_state(level, ((cell, room, phase, 4),)), prince=bytes(actor), working=bytes(range(62)),
                     countdown=-2, saved_edges=(211, 223, 227, 229), exit_flag=1234, view=room, result=-2,
                     cooldown=0, input_latches=(0, 0, 0, 0, 0), working_latches=(31, 37, 41, 43, 47),
                     raw_axes=(53, 59, 61), cell_cache=struct.pack('>6h', 0, 0, 0, 0, -32768, -32768),
                     division_remainder=61, frame_width=18, mob_records=bank, mob_storage=bytes(storage),
                     frame_metadata=bytes(range(18)), bounds=bounds, edge_cells=(137, 139, 149, 151),
                     drawing=struct.pack('>10h', -1, 53, 59, -1, 2, 61, 67, 71, 73, 79),
                     current_edges=(bounds[6], bounds[5], bounds[2], bounds[1]), bound_events=[])
        machine.reset(level)
        machine.inputs = inputs
        for destination, data in ((-0x5056, state['working']), (-0x50d2, state['prince']), (-0x448e, state['trob_storage']),
                (-0x4818, state['os']), (-0x43ee, struct.pack('>4h', *state['scratch'])), (-0x34b0, state['cell_cache']),
                (-0x44a6, scratch), (-0x521a, state['frame_metadata']), (-0x34c6, state['drawing'])):
            machine.cpu.mem_write(machine.A5 + destination, data)
        machine.cpu.mem_write(MOB_BANK - 16, state['mob_storage'])
        machine.cpu.mem_write(machine.A5 - 0x43a4, b'\0' * 4)
        for destinations, values in ((SAVED_LATCHES, state['input_latches']), (LATCHES, state['working_latches']),
                (AXES, state['raw_axes']), (EDGE_DESTINATIONS, state['saved_edges']), (BOUND_WORDS, bounds),
                (CELL_WORDS, state['edge_cells'])):
            for destination, value in zip(destinations, values):
                machine.put_word(destination, value)
        for destination, value in ((-0x43e6, 1), (-0x4fc2, room), (-0x5008, -2), (-0x4490, len(bank)),
                (-0x439e, 192), (-0x4f96, 0), (-0x4fee, 1), (-0x4fac, 0), (-0x4f90, 0),
                (-0x4fce, 1), (-0x4faa, 1234), (-0x4fa6, 0), (-0x5200, 0), (-0x4fa8, 0), (-0x4ffe, 0),
                (-0x4f92, number), (-0x4fd2, number), (-0x43b6, 0), (-0x481c, 61)):
            machine.put_word(destination, value)
        expected = world_reference(state, sequences, inputs, geometry_player_reference, loader, sprite)
        returned = signed_word(machine.call(2, 0x6224))
        actual = dict(machine.snapshot(len(level)), result=returned)
        names = set(machine.ENDPOINTS.values()) | {'sample_input'}
        services = Counter({'sound': 'gate_sound', 'redraw': 'gate_redraw', 'audio': 'audio_request'}.get(e[0], e[0])
                           for e in expected['events'] if e[0] in names | {'sound', 'redraw', 'audio'})
        if (actual != expected or machine.services != services
                or bytes(machine.cpu.mem_read(machine.A5 - 0x44a6, 22)) != scratch or machine.word(-0x439e) != 192
                or bytes(machine.cpu.mem_read(machine.A5 - 0x196c, 8)) != struct.pack('>4h', *DEFAULT_RECT)
                or bytes(machine.cpu.mem_read(machine.A5 - 0x4fec, 8)) != struct.pack('>4h', *SCREEN_RECT)):
            raise AssertionError(dict(fixture=(number, room, cell, position, phase, facing, raw_axes, pose, offset, occupied),
                                      differences={k: (actual[k], expected[k]) for k in expected if actual[k] != expected[k]},
                                      services=(machine.services, services)))
        machine.verify_sequences()
        verify_frames(machine)
        counts['occupied' if occupied else 'empty'] += 1
        outcomes[f'source{actor_word(expected["working"], 40)}'] += 1
        outcomes['rock_left_clips'] += sum(e == ('clip_left',) for e in expected['events'])
        widths[expected['frame_width']] += 1
        initial_widths[sizes[struct.unpack_from('>h', frames, pose * 10)[0]][0] + 1] += 1

        def fixed_width_controller(actor, sequences, inputs, context):
            return geometry_player_reference(actor, sequences, inputs, dict(context, frame_width=18))

        legacy = world_reference(state, sequences, inputs, fixed_width_controller, loader, sprite)
        outcomes['fixed18_selection_changes'] += actor_word(legacy['prince'], 40) != actor_word(expected['prince'], 40)
        digest.update(expected['level'] + expected['prince'] + expected['working'] + expected['mob_storage']
                      + expected['trob_storage'] + expected['drawing'] + expected['frame_metadata'] + expected['cell_cache'])
        digest.update(json.dumps([expected['bounds'], expected['edge_cells'], expected['saved_edges'],
                                  expected['events'], expected['bound_events'], expected['division_remainder']]).encode('ascii'))
    return dict(comparisons=sum(counts.values()), mismatches=0, cases=dict(counts), outcomes=dict(outcomes),
                widths=dict(widths), initial_widths=dict(initial_widths),
                outputs_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(executable).hexdigest(),
                supplied_services={f'{s}:{o:04x}': name for (s, o), name in machine.ENDPOINTS.items()},
                other_supplied=['2:55d2 sampled axes', '17:673a dimensions from original Kid SHAP headers',
                                'SectRect: explicit screen intersection; prepared frame/sequence/library handles',
                                'Audio/redraw/handle services inherited from the prior world/PlayerCtrl probes'],
                scope='Actual world/Prince/PlayerCtrl plus LoadFrame/SetupSword/GetCharEdges and real cell/rock queries. '
                      'Width, actor visible rectangle and saved edges now derived from actual Kid frames, not fixed18. '
                      'Original41 gate anchors with empty or one supplied static rock. Initial anchors/input samples '
                      'and remaining contact/floor/hazard/opponent/external services supplied. Not full FrameAdv, '
                      'physical reachability, rendering, persistent full-world physics or playable temple.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = run_probe(args.source)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='ascii')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
