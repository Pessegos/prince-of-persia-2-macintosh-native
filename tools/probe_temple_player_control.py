"""Run real temple PlayerCtrl preparation inside native world/Prince updates."""

import argparse
from collections import Counter
from dataclasses import asdict, dataclass, replace
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_sequence_selection import signed_word
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_hanging_control import HangingInputs, LATCHES, NativeTempleHangingControl, hanging_reference
from tools.probe_temple_plate_release import initial_state
from tools.probe_temple_slide_rock_update import actor_word
from tools.probe_temple_world_prince import (
    CallerInputs, EDGE_DESTINATIONS, EDGE_SOURCES, NativeTempleWorldPrince, world_reference,
)


SAVED_LATCHES = (-0x3492, -0x3490, -0x348e, -0x348c, -0x348a)
AXES = (-0x3498, -0x3496, -0x3494)


@dataclass(frozen=True)
class PlayerInputs(CallerInputs, HangingInputs):
    raw_axes: tuple = (0, 0, -1)
    previous_latches: tuple = (0, 0, 0, 0, 0)
    vertical_flip: int = 0
    matching_context: bool = True


CASES = {
    'hold': PlayerInputs(),
    'climb': PlayerInputs(raw_axes=(0, -1, -1)),
    'climb-cooldown1': PlayerInputs(raw_axes=(0, -1, -1), cooldown=1),
    'climb-cooldown2': PlayerInputs(raw_axes=(0, -1, -1), cooldown=2),
    'released': PlayerInputs(raw_axes=(0, 0, 0)),
    'second-held': PlayerInputs(raw_axes=(0, 0, -2)),
    'consumed-up-held': PlayerInputs(raw_axes=(0, -1, -1), previous_latches=(0, 0, 1, 0, 1)),
    'preserved-fresh': PlayerInputs(raw_axes=(1, 0, 0), previous_latches=(-1, 0, -1, 0, -1)),
    'new-context': PlayerInputs(raw_axes=(-1, -1, -1), matching_context=False),
    'freeze-animation': PlayerInputs(raw_axes=(0, -1, -1), suppress_animation=1),
}


def normalize_latches(previous, axes):
    if len(previous) != 5 or len(axes) != 3:
        raise ValueError('Expected five saved latches and three sampled axes')
    flags = list(previous)
    for index, target in enumerate((-1, 1, -1, 1)):
        if flags[index] >= 0:
            if axes[index // 2] != target:
                flags[index] = 0
            elif flags[index] == 0:
                flags[index] = -1
    held = axes[2]
    flags[4] = (flags[4] if flags[4] == -held else held) if held in (-1, -2) else 0
    return tuple(flags)


def player_reference(actor, sequences, inputs, state):
    if actor_word(actor, 24) >= 0 or actor_word(actor, 30) == 0:
        raise ValueError('This PlayerCtrl composition bounds negative death-counter/nonzero HP only')
    events = [('player_ctrl',), ('prepare_controls',), ('restore_latches',), ('sample_input', inputs.raw_axes)]
    cooldown = signed_word(state['cooldown'] - 1) if state['cooldown'] != 0 else 0
    axes = list(inputs.raw_axes)
    if not inputs.matching_context or actor_word(actor, 22) == 0 or actor_word(actor, 40) == 59:
        axes[:2] = (0, 0)
    events.append(('normalize_latches',))
    flags = list(normalize_latches(state['input_latches'], axes))
    events.append(('orient_controls',))
    horizontal = actor_word(actor, 2) == 0

    def flip_x():
        events.append(('flip_horizontal',))
        axes[0] = signed_word(-axes[0])
        flags[0], flags[1] = flags[1], flags[0]

    def flip_y():
        events.append(('flip_vertical',))
        axes[1] = signed_word(-axes[1])
        flags[2], flags[3] = flags[3], flags[2]

    if horizontal:
        flip_x()
    if inputs.vertical_flip:
        flip_y()
    controls = hanging_reference(actor, sequences, replace(inputs, held=flags[4], up=flags[2], cooldown=cooldown), flags)
    flags[:] = controls['latches']
    events.extend(controls['events'])
    if horizontal:
        flip_x()
    if inputs.vertical_flip:
        flip_y()
    events.extend((('inactive_demo_result',), ('save_latches',)))
    cache = state['cell_cache']
    if controls['foreground'] is not None:
        cache = cache[:2] + struct.pack('>H', controls['foreground']) + cache[4:]
    return dict(actor=controls['actor'], result=-2, events=events,
                updates=dict(cooldown=cooldown, input_latches=tuple(flags), working_latches=tuple(flags),
                             raw_axes=tuple(axes), cell_cache=cache))


class NativeTemplePlayerControl(NativeTempleWorldPrince, NativeTempleHangingControl):
    RANGES = {segment: NativeTempleWorldPrince.RANGES.get(segment, ()) + NativeTempleHangingControl.RANGES.get(segment, ())
              for segment in NativeTempleWorldPrince.RANGES.keys() | NativeTempleHangingControl.RANGES.keys()}
    RANGES[4] += ((0x3b88, 0x3d14), (0x3d96, 0x3f42))
    RANGES[5] += ((0x6072, 0x60be),)
    ENDPOINTS = {key: value for key, value in NativeTempleWorldPrince.ENDPOINTS.items() if key != (4, 0x3b88)}

    def reset(self, level):
        super().reset(level)
        self.inputs = PlayerInputs()

    def dispatch(self, cpu, address, size, user):
        segment, offset = divmod(address - self.CODE_BASE, 0x10000)
        if (segment, offset) == (2, 0x55d2):
            self.events.append(('sample_input', self.inputs.raw_axes))
            self.services['sample_input'] += 1
            for destination, value in zip(AXES, self.inputs.raw_axes):
                self.put_word(destination, value)
            self.return_value(0)
            return
        native = {(4, 0x3b88): 'player_ctrl', (4, 0x3cae): 'prepare_controls',
                  (4, 0x3e60): 'restore_latches', (4, 0x3e84): 'normalize_latches',
                  (4, 0x3d96): 'orient_controls', (4, 0x3dfe): 'flip_horizontal',
                  (4, 0x3e1c): 'flip_vertical', (4, 0x3e50): 'save_latches',
                  (5, 0x6072): 'inactive_demo_result'}
        if (segment, offset) in native:
            self.events.append((native[segment, offset],))
        super().dispatch(cpu, address, size, user)

    def snapshot(self, size):
        return dict(super().snapshot(size), cooldown=self.word(-0x4f96),
                    input_latches=tuple(self.word(offset) for offset in SAVED_LATCHES),
                    working_latches=tuple(self.word(offset) for offset in LATCHES),
                    raw_axes=tuple(self.word(offset) for offset in AXES),
                    cell_cache=bytes(self.cpu.mem_read(self.A5 - 0x34b0, 12)))


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    resources = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    raw = {n: resources['SEQS'][n]['data'] for n in (2, 9, 10, 11, 23, 25, 47, 73, 99, 210)}
    sequences = {n: struct.unpack('>' + str(len(data) // 2) + 'h', data) for n, data in raw.items()}
    machine = NativeTemplePlayerControl(parse_resource_fork(executable), raw)
    counts, outcomes, events, services, digest = Counter(), Counter(), Counter(), Counter(), hashlib.sha256()
    inventory = []
    for number in range(10, 14):
        level = resources['LEVL'][1999 + number]['data']
        if (struct.unpack_from('>3h', level, 0x2186)[::2] != (2, number)
                or struct.unpack_from('>h', level, 0x21a4)[0] != 7):
            raise ValueError('Expected original temple/opponent headers')
        for room in range(1, struct.unpack_from('>h', level, 0x2180)[0] + 1):
            for cell in range(30):
                if struct.unpack_from('>h', level, (room - 1) * 60 + cell * 2)[0] == 4:
                    inventory.append((number, level, room, cell))
    if len(inventory) != 41 or SAVED_LATCHES != (-0x3492, -0x3490, -0x348e, -0x348c, -0x348a):
        raise ValueError('Expected41 gate anchors and the five-word saved latch bank')
    mob = bytes((i * 7 + 13) % 256 for i in range(22))

    def compare(anchor, position, phase, facing, inputs, label, actor_room=None, selected_source=9):
        number, original, room, cell = anchor
        row, column = divmod(cell, 10)
        level = bytearray(original)
        struct.pack_into('>H', level, 0x780 + (room - 1) * 120 + cell * 4, position)
        actor = bytearray(actor_fixture(room if actor_room is None else actor_room, row + 1, column, facing, 2))
        for field, value in ((4, 207 + column * 51), (6, row * 120 + 110), (10, 91), (18, 0), (20, 0),
                              (24, -1), (26, 0), (28, -1), (30, 3), (34, 0),
                              (36, 3), (38, 9), (40, selected_source), (52, inputs.release_word), (58, -1)):
            put_actor(actor, field, value)
        state = dict(initial_state(level, ((cell, room, phase, 4),)),
                     prince=bytes(actor), working=bytes(range(62)), countdown=-2,
                     saved_edges=(211, 223, 227, 229), exit_flag=1234, view=room, result=-2,
                     cooldown=inputs.cooldown, input_latches=inputs.previous_latches,
                     working_latches=(31, 37, 41, 43, 47), raw_axes=(53, 59, 61),
                     cell_cache=struct.pack('>6H', 11, 13, 17, 19, 23, 29))
        machine.reset(level)
        machine.inputs = inputs
        for destination, data in ((-0x5056, state['working']), (-0x50d2, state['prince']),
                                  (-0x448e, state['trob_storage']), (-0x4818, state['os']),
                                  (-0x43ee, struct.pack('>4h', *state['scratch'])),
                                  (-0x34b0, state['cell_cache']), (-0x44a6, mob)):
            machine.cpu.mem_write(machine.A5 + destination, data)
        for destinations, values in ((SAVED_LATCHES, state['input_latches']), (LATCHES, state['working_latches']),
                                     (AXES, state['raw_axes']), (EDGE_DESTINATIONS, state['saved_edges']),
                                     ((-0x3560, -0x3562, -0x3568, -0x356a), EDGE_SOURCES)):
            for destination, value in zip(destinations, values):
                machine.put_word(destination, value)
        for destination, value in ((-0x43e6, 1), (-0x4fc2, room), (-0x5008, -2), (-0x4490, 17),
                (-0x439e, 192), (-0x4f96, inputs.cooldown), (-0x4fee, inputs.live),
                (-0x4fac, inputs.suppress_animation), (-0x4f90, inputs.invulnerable),
                (-0x4fce, inputs.time_left), (-0x4faa, 1234), (-0x4fa6, inputs.floating),
                (-0x5200, 0), (-0x4fa8, inputs.vertical_flip), (-0x4ffe, 0),
                (-0x4f92, number), (-0x4fd2, number if inputs.matching_context else number - 1), (-0x43b6, 0)):
            machine.put_word(destination, value)
        machine.cpu.mem_write(machine.A5 - 0x43a4, b'\0' * 4)
        expected = world_reference(state, sequences, inputs, player_reference)
        returned = signed_word(machine.call(2, 0x6224))
        actual = dict(machine.snapshot(len(level)), result=returned)
        names = set(machine.ENDPOINTS.values()) | {'current_cell', 'front_cell', 'above_cell', 'bars', 'sample_input'}
        expected_services = Counter({'sound': 'gate_sound', 'redraw': 'gate_redraw', 'audio': 'audio_request'}
                                    .get(e[0], e[0]) for e in expected['events']
                                    if e[0] in names | {'sound', 'redraw', 'audio'})
        if (actual != expected or machine.services != expected_services
                or bytes(machine.cpu.mem_read(machine.A5 - 0x44a6, 22)) != mob
                or machine.word(-0x4490) != 17 or machine.word(-0x439e) != 192
                or machine.word(-0x43b6) != 0 or bytes(machine.cpu.mem_read(machine.A5 - 0x43a4, 4)) != b'\0' * 4
                or machine.word(-0x4fa8) != inputs.vertical_flip or machine.word(-0x4ffe) != 0):
            raise AssertionError(dict(anchor=(number, room, cell), inputs=asdict(inputs),
                                      fixture=(label, position, phase, facing, actor_room, selected_source),
                                      differences={k: (actual[k], expected[k]) for k in expected if actual[k] != expected[k]},
                                      services=(machine.services, expected_services)))
        machine.verify_sequences()
        counts[label] += 1
        outcomes[f'source{actor_word(expected["prince"], 40)}_mode{actor_word(expected["prince"], 16)}'] += 1
        events.update(e[0] for e in expected['events'])
        services.update(machine.services)
        digest.update(expected['level'] + expected['prince'] + expected['working'] + expected['trob_storage']
                      + expected['os'] + expected['cell_cache'])
        digest.update(json.dumps([expected['scratch'], expected['events'], expected['input_latches'],
                                  expected['raw_axes'], expected['cooldown'], returned]).encode('ascii'))

    for anchor, (position, phase), facing, vertical_flip, (label, inputs) in product(
            inventory, ((3, 1), (12, 1), (120, 4)), (-1, 0), (0, 1), CASES.items()):
        compare(anchor, position, phase, facing, replace(inputs, vertical_flip=vertical_flip), label)
    for raw_axes, previous, facing, vertical_flip, cooldown in product(
            tuple(product((-1, 0, 1), (-1, 0, 1), (-2, -1, 0))),
            ((0, 0, 0, 0, 0), (1, 1, 1, 1, 1), (-1, -2, -1, -2, -1), (2, 2, 2, 2, 2)),
            (-1, 0), (0, 1), (-1, 0, 1, 2)):
        compare(inventory[0], 12, 1, facing, PlayerInputs(raw_axes=raw_axes, previous_latches=previous,
                vertical_flip=vertical_flip, cooldown=cooldown), 'sampled-latch-controls')
    for current, front, above, bars, facing, raw_axes in product(
            (0, 1, 4, 20), (0, 1, 20), (0, 1, 4), (0, 1), (-1, 0),
            ((0, -1, -1), (0, 0, 0), (0, 0, -1))):
        compare(inventory[0], 3, 1, facing, PlayerInputs(current=current, front=front, above=above, bars=bars,
                raw_axes=raw_axes), 'gate-controller-overrides')
    for raw_axes, matching_context, facing in product(((1, -1, -1), (0, 0, 0)), (False, True), (-1, 0)):
        compare(inventory[0], 12, 1, facing, PlayerInputs(raw_axes=raw_axes, matching_context=matching_context),
                'room0-controller', actor_room=0)
    for facing in (-1, 0):
        compare(inventory[0], 12, 1, facing, PlayerInputs(raw_axes=(1, -1, -1)),
                'source59-direction-reset', selected_source=59)
    return dict(cases=dict(counts), comparisons=sum(counts.values()), mismatches=0,
                outcomes=dict(outcomes), events=dict(events), services=dict(services), outputs_sha256=digest.hexdigest(),
                executable_sha256=hashlib.sha256(executable).hexdigest(), inputs={k: asdict(v) for k, v in CASES.items()},
                sequence_sha256={str(n): hashlib.sha256(data).hexdigest() for n, data in raw.items()},
                level_sha256={str(n): hashlib.sha256(resources['LEVL'][1999 + n]['data']).hexdigest() for n in range(10, 14)},
                supplied_services={f'{s}:{o:04x}': name for (s, o), name in machine.ENDPOINTS.items()},
                other_supplied=['2:55d2 writes sampled raw axes only', '4:35a6/3a48/3ff8 cell kind/above foreground',
                                '10:2036 bars bool', '5:3828/0fe6/4d84 cue/redraw/audio',
                                '17:330e/4:3098 prepared original handles; state0 handle traps'],
                scope='Actual2:6224 world/2:62e6 Prince/4:3b88 PlayerCtrl, latch restore/sample-normalization/'
                      'orientation/cooldown/save, real GenCtrl hanging/climb/release/preview, gate bank, '
                      'AnimChar/gravity and actor save2:6472. One world update per supplied fixture. '
                      'Input polling, cell/bars responses, geometry/contact/hazards, opponents, clock/cut/'
                      'presentation services supplied; inactive demo/null handle only. No physical input, '
                      'outer FrameAdv, death controller, full collision/reachability, saves or runtime integration.')


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
