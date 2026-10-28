"""Execute original action consumption with explicit terrain/animation boundaries."""

import argparse
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_input_routes import NativeInputRoutes
from tools.probe_level7_rules import NativeRules
from tools.reference_input_bank import InputBank
from tools.reference_input_actions import forward_jump, run, running_jump, step, turn


class NativeInputActions(NativeInputRoutes):
    RANGES = {4: NativeInputRoutes.RANGES[4] + ((0x2bae, 0x2bcc),),
              6: NativeInputRoutes.RANGES[6] + ((0x10e4, 0x1340), (0x15ea, 0x15fe),
                                               (0x1c14, 0x1d5e))}
    SUPPLIED = {key: value for key, value in NativeInputRoutes.SUPPLIED.items()
                if value not in ('turn', 'step', 'forward_jump', 'run', 'run_jump')}
    SUPPLIED.update({(4, 0x5eae): 'distance', (4, 0x3a92): 'wall_distance',
                     (4, 0x39fc): 'ahead_kind', (4, 0x5b0e): 'wall',
                     (4, 0x3ad6): 'column', (4, 0x27ee): 'read_ahead',
                     (6, 0x5eca): 'support', (4, 0x3aa0): 'gap_distance'})
    TERRAIN_SERVICES = {'distance', 'wall_distance', 'ahead_kind', 'wall',
                        'column', 'read_ahead', 'support', 'gap_distance'}

    def dispatch(self, cpu, address, size, user):
        segment, offset = divmod(address - self.CODE_BASE, 0x10000)
        service = self.SUPPLIED.get((segment, offset))
        if service in self.TERRAIN_SERVICES and address != self.stop_at:
            if service == 'column':
                value = 4
            elif service == 'read_ahead':
                cells = self.terrain.get('cells', (True, True))
                value = int(cells[self.reads])
                self.reads += 1
            elif service == 'support':
                stack = cpu.reg_read(self.registers['a7'])
                value = struct.unpack('>H', cpu.mem_read(stack + 4, 2))[0]
            else:
                value = self.terrain.get(service, {'distance': 51, 'wall_distance': 51,
                                                   'ahead_kind': 1}.get(service, 0))
            NativeRules.dispatch(self, cpu, address, size, user)
            cpu.reg_write(self.registers['d0'], int(value) & 65535)
            return
        super().dispatch(cpu, address, size, user)

    def action_fixture(self, level, bank, terrain, facing_right=True, warning=1,
                       pose=15, x=400):
        self.fixture(level, bank, pose)
        self.terrain, self.reads = terrain, 0
        for field, value in ((-0x5054, 0 if facing_right else -1), (-0x5052, x),
                             (-0x503e, warning), (-0x3576, terrain.get('barrier', 0)),
                             (-0x34b0, terrain.get('tile_kind', 1)), (-0x36bc, 0)):
            self.put_word(field, value)


ACTIONS = {'forward_jump': (0x15ea, forward_jump), 'step': (0x1276, step),
           'run': (0x11a0, run), 'turn': (0x10e4, turn),
           'running_jump': (0x1c14, running_jump)}


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    raw = (directory / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(raw)
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2004]['data']
    assert struct.unpack_from('>HH', level, 0x2186)[0] == 3
    assert struct.unpack_from('>H', level, 0x218a)[0] == 5
    machine = NativeInputActions(program)
    counts, digest = {}, hashlib.sha256()
    banks = [InputBank(*directions, modifier) for directions in product((-1, 0, 1), repeat=4)
             for modifier in (-2, -1, 0, 1, 2)]

    def check(name, bank, *, facing_right=True, warning=1, pose=15, x=400, **terrain):
        offset, reference = ACTIONS[name]
        machine.action_fixture(level, bank, terrain, facing_right, warning, pose, x)
        if name == 'running_jump':
            args = (terrain.get('sequence', 4),)
            expected = reference(bank, pose=pose, x=x, warning=warning,
                                 facing_right=facing_right, **terrain)
        elif name == 'step':
            args = (0,)
            expected = reference(bank, x=x, warning=warning, facing_right=facing_right, **terrain)
        else:
            args = ()
            expected = reference(bank, x=x, warning=warning,
                                 **({'facing_right': facing_right} if name != 'forward_jump' else {}),
                                 **terrain)
        result = machine.call(6, offset, args)
        events = (('sequence', expected.sequence),) if expected.sequence is not None else ()
        actual = (machine.bank(), tuple(machine.events), machine.word(-0x5052),
                  machine.word(-0x503e), machine.word(-0x36bc))
        wanted = (expected.bank, events, expected.x, expected.warning, 0)
        if actual != wanted or expected.accepted is not None and result != int(expected.accepted):
            raise AssertionError((name, bank, terrain, facing_right, warning, pose, x,
                                  actual, wanted, result, expected.accepted))
        counts[name] = counts.get(name, 0) + 1
        digest.update(repr((actual, expected.accepted)).encode())
        return expected

    for bank, facing in product(banks, (False, True)):
        for name in ACTIONS:
            check(name, bank, facing_right=facing, pose=7)
        check('run', bank, facing_right=facing, barrier=1, distance=4)
        check('running_jump', bank, facing_right=facing, pose=6)
        check('running_jump', bank, facing_right=facing, pose=7, cells=(False, False))
    boundary_banks = (InputBank(), InputBank(-1, -1, -1, -1, -2), InputBank(1, 0, 1, -1, -1))
    for bank, facing, warning, barrier, kind, distance in product(
            boundary_banks, (False, True), (0, 1), (0, 1), (1, 12, 13),
            (-32768, -1, 0, 1, 4, 5, 6, 7, 26, 27, 45, 46, 32767)):
        for name in ('run', 'step'):
            check(name, bank, facing_right=facing, warning=warning,
                  barrier=barrier, tile_kind=kind, distance=distance)
    for bank, facing, kind, wall, distance in product(
            boundary_banks, (False, True), (1, 4), (False, True), (-1, 0, 6, 10, 11, 12)):
        check('turn', bank, facing_right=facing, ahead_kind=kind, wall=wall, wall_distance=distance)
    for bank, facing, sequence, pose, cells, gap in product(
            boundary_banks, (False, True), (4, 100), (6, 7, 14, 15, 192, 196),
            ((False, False), (True, False), (True, True)),
            (-32768, -1, 0, 16, 17, 18, 44, 45, 46, 62, 63, 64, 32767)):
        check('running_jump', bank, facing_right=facing, sequence=sequence,
              pose=pose, cells=cells, gap_distance=gap)
    return dict(cases=counts, total=sum(counts.values()), mismatches=0,
                outputs_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(raw).hexdigest(),
                supplied=['Level5/environment3, living type0 Prince, pose and latches',
                          'Barrier/distance/wall/cell/support/column/gap-distance services',
                          'JumpSeq request sink: animation and automatic pose advancement excluded'],
                actual=['Action bodies, latch consumption, relative X arithmetic and ClearControls'],
                exclusions='No full geometry, animation, other environments/actors, player wrapper or FrameAdv')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
