"""Original ruins exit admission, head meter shapes and multi-actor selection."""

import argparse
import hashlib
from itertools import product
import json
from pathlib import Path
import random
import struct
from types import SimpleNamespace

from pop2.combat_art import HealthArtwork
from pop2.mac_resources import parse_resource_fork
from pop2.opponent_selection import nearest_opponent
from pop2.pressure_plates import can_trigger_exit
from pop2.rebirth import Checkpoint
from tools.probe_level7_rules import NativeRules


class NativeExit(NativeRules):
    RANGES = {5: ((0x1ec8, 0x1fe6),)}
    SUPPLIED = {}

    def reset(self, level):
        super().reset(level)
        self.allowed = False

    def dispatch(self, cpu, address, size, user):
        if address == self.address(5, 0x1f40):
            self.allowed = self.reached = True
            cpu.emu_stop()
            return
        super().dispatch(cpu, address, size, user)


class NativeMeter(NativeRules):
    RANGES = {3: ((0x4a8e, 0x4cc2),), 4: ((0x4ac0, 0x4af4),)}
    SUPPLIED = {(17, 0x4cf4): 'port save supplied'}
    PORT = NativeRules.END + 0x20

    def reset(self, level):
        super().reset(level)
        self.draws = []
        self.cpu.mem_write(self.A5 - 0x1f64, struct.pack('>I', self.PORT))

    def dispatch(self, cpu, address, size, user):
        if address == self.PORT or address == self.address(17, 0x67f4):
            stack = cpu.reg_read(self.registers['a7'])
            if address == self.PORT:
                self.services['port rectangle supplied'] += 1
            else:
                self.draws.append(struct.unpack('>4h', cpu.mem_read(stack + 8, 8)))
                self.services['shape draw recorded, not rasterized'] += 1
            cpu.reg_write(self.registers['a7'], stack + 4)
            cpu.reg_write(self.registers['pc'], struct.unpack('>I', cpu.mem_read(stack, 4))[0])
            return
        if address == self.address(3, 0x4c06):
            # EraseRect Pascal trap: discard its pointer argument, no pixels.
            self.services['EraseRect supplied'] += 1
            cpu.reg_write(self.registers['a7'], cpu.reg_read(self.registers['a7']) + 4)
            cpu.reg_write(self.registers['pc'], address + 2)
            return
        super().dispatch(cpu, address, size, user)


class NativeSelection(NativeRules):
    RANGES = {6: ((0x3642, 0x36de), (0x36f2, 0x3970))}
    SUPPLIED = {}


class NativeCheckpoint(NativeRules):
    RANGES = {2: ((0x6b46, 0x6c1c),)}
    SUPPLIED = {}

    def reset(self, level):
        super().reset(level)
        self.allowed = False

    def dispatch(self, cpu, address, size, user):
        if address == self.address(2, 0x6bb6):
            self.allowed = self.reached = True
            cpu.emu_stop()
            return
        super().dispatch(cpu, address, size, user)


def actor(x, y, kind=8, mode=1, living=True, life=4):
    return SimpleNamespace(state=SimpleNamespace(target_x=x, current_y=y - 106, actor_type=kind),
                           row=0, room=0, alive=life > 0, native_alive=None, skeleton=None,
                           ruins=SimpleNamespace(mode=mode, dead_frames=-1 if living else 0,
                                                 removed=False))


def run_probe(source, cases=5000):
    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(executable)
    level = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())['LEVL'][2007]['data']
    exits = NativeExit(program)
    exit_cases = 0
    for number, entry, room, sword in product((6, 7, 8, 9, 13), (1, 16, 32),
                                              (1, 9, 16, 32), (-1, 0, 1, 2, 3)):
        supplied = bytearray(level)
        struct.pack_into('>H', supplied, 0x218a, number)
        struct.pack_into('>H', supplied, 0x2198, entry)
        exits.reset(supplied)
        exits.put_word(-0x500a, sword)
        exits.call(5, 0x1ec8, (17, room, 15, 5))
        expected = can_trigger_exit(supplied, room - 1, sword)
        if exits.allowed != expected or exits.services:
            raise AssertionError(('exit', number, entry, room, sword, exits.allowed, expected))
        exit_cases += 1

    checkpoint = NativeCheckpoint(program)
    checkpoint_cases = 0
    for number, room, sword in product((6, 7, 8, 9), (1, 9, 16, 32), (-1, 0, 1, 2, 3)):
        supplied = bytearray(level)
        struct.pack_into('>H', supplied, 0x218a, number)
        checkpoint.reset(supplied)
        for offset, value in ((-0x50bc, room), (-0x50c2, 1), (-0x50b6, -1),
                              (-0x50b0, 0), (-0x50b4, 100), (-0x50ca, 0), (-0x500a, sword)):
            checkpoint.put_word(offset, value)
        checkpoint.call(2, 0x6b46)
        point = Checkpoint(1, room - 1, 25)
        expected = point.matches(room - 1, 2, point.x + 4, 1, True, number, sword)
        if checkpoint.allowed != expected or checkpoint.services:
            raise AssertionError(('checkpoint', number, room, sword, checkpoint.allowed, expected))
        checkpoint_cases += 1

    meter = NativeMeter(program)
    meter_cases = 0
    for kind, life in product((2, 4, 6, 7, 8), range(1, 13)):
        meter.reset(level)
        meter.put_word(-0x4fc2, 1)
        meter.put_word(-0x4fcc, 0)
        meter.put_word(-0x4aa0, -1)
        meter.put_word(-0x5208 + 8, kind)
        meter.put_word(-0x5208 + 0x16, 1)
        meter.put_word(-0x5208 + 0xe, 0)
        meter.call(3, 0x4a8e, (0, life), stop=(3, 0x4c64))
        art = HealthArtwork.__new__(HealthArtwork)
        art.icons = {index: index for index in range(297, 301)}
        draws = []
        viewport = SimpleNamespace(paste=lambda icon, xy, mask: draws.append((icon, xy[0] - 1, xy[1], 16)))
        opponent = SimpleNamespace(life=life, state=SimpleNamespace(actor_type=kind))
        encounter = SimpleNamespace(player=SimpleNamespace(life=3, max_life=3),
                                    world_frame=0, health_opponent=lambda: opponent)
        art.draw(viewport, encounter)
        if meter.draws != draws[3:]:
            raise AssertionError(('meter', kind, life, meter.draws, draws[3:]))
        meter_cases += 1

    selection = NativeSelection(program)
    rng = random.Random(0x8001)
    selected_cases = side_cases = 0
    for case in range(cases):
        supplied = bytearray(level)
        count = rng.randrange(1, 6)
        struct.pack_into('>H', supplied, 0x20e6 + 0xc0, count)
        selection.reset(supplied)
        px, py = rng.choice((100, 200, 250, 300, 400)), rng.choice((73, 106, 193, 226, 346))
        player = actor(px, py, 0)
        selection.put_word(-0x50d2 + 4, px + 207)
        selection.put_word(-0x50d2 + 6, py)
        selection.put_word(-0x50d2 + 0x16, 1)
        selection.put_word(-0x4fc2, 1)
        actors = []
        for slot in range(count):
            x, y = rng.choice((px, -120, 80, 150, 200, 250, 350, 450, 530, 650)), rng.choice((73, 106, 193, 226, 346))
            kind, mode = rng.choice((7, 8, 11)), rng.randrange(4)
            living, life = rng.choice((True, True, False)), rng.randrange(9)
            other = actor(x, y, kind, mode, living, life)
            actors.append(other)
            base = -0x5208 + slot * 62
            for offset, value in ((0, slot), (4, x + 207), (6, y), (8, kind),
                                  (0x16, 1), (0x1c, -1 if living else 0), (0x1e, life)):
                selection.put_word(base + offset, value)
            selection.cpu.mem_write(selection.LEVEL + 0x20e6 + 0xc0 + 2 + slot * 38 + 0x1c,
                                    struct.pack('>h', mode))
        for native_side, port_side in ((1, None), (-1, -1), (0, 1)):
            selected = selection.call(6, 0x36f2, (native_side,))
            selected = -1 if selected == 65535 else selected
            target = nearest_opponent(player, actors, port_side)
            expected = next((slot for slot, other in enumerate(actors) if other is target), -1)
            if selected != expected or selection.services:
                raise AssertionError(('selection', case, native_side, px, py,
                                      [(a.state.target_x, a.state.current_y + 106, a.state.actor_type,
                                        a.ruins.mode, a.ruins.dead_frames, a.alive) for a in actors],
                                      selected, expected))
            selected_cases += 1
        for slot, other in enumerate(actors):
            selection.put_word(-0x5052, other.state.target_x + 207)
            selection.put_word(-0x5056, slot)
            result = selection.call(6, 0x3946)
            side = -1 if px >= other.state.target_x else 1
            expected = nearest_opponent(player, actors, side) is other
            if result != int(expected) or selection.services:
                raise AssertionError(('waiting', case, slot, result, expected))
            side_cases += 1
    return dict(exit_cases=exit_cases, checkpoint_admission_cases=checkpoint_cases, meter_cases=meter_cases,
                selection_cases=selected_cases, waiting_cases=side_cases, mismatches=0,
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                supplied=['Controlled LEVL header and actor/record fields',
                          'HUD port save/rectangle and EraseRect supplied without drawing',
                          'HUD shape draw calls recorded without rasterization'],
                scope='Actual TriggerObject admission stops before exit phase/sound; '
                      'checkpoint admission stops before matching/saving a checkpoint record; '
                      'DrawOppMeter positive HP shape/position loop stops before final port/copy; '
                      'GetOppIdxClosestToKid and nearest-on-side execute fully with no services. '
                      'Excludes full AI/frame order, bank target-cache lifecycle, pixel rasterization '
                      'and complete level8 route.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cases', type=int, default=5000)
    args = parser.parse_args()
    report = run_probe(args.source, args.cases)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='ascii')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
