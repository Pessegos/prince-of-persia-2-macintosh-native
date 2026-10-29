"""Execute original hanging input gates and climb/release consumption prefixes.

Routing action and terrain endpoints are supplied. Prefix execution stops
before terrain lookup; no native animation or whole FrameAdv is simulated.
"""

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
from tools.reference_ledge_input import climb_input, ledge_request, release_input


class NativeLedgeInput(NativeInputRoutes):
    RANGES = {**NativeInputRoutes.RANGES,
              6: NativeInputRoutes.RANGES[6] + ((0x18e0, 0x19d4), (0x1a84, 0x1a92))}
    SUPPLIED = {**NativeInputRoutes.SUPPLIED, (6, 0x1998): 'climb', (6, 0x1a84): 'release',
                (4, 0x35a6): 'here', (3, 0x4ef2): 'wall', (4, 0x3ff8): 'ahead',
                (3, 0x4eb2): 'gap', (23, 0x132c): 'special'}
    prefix = False

    def dispatch(self, cpu, address, size, user):
        target = divmod(address - self.CODE_BASE, 0x10000)
        name = self.SUPPLIED.get(target)
        if address != self.stop_at and name in ('here', 'wall', 'ahead', 'gap', 'special'):
            return NativeRules.dispatch(self, cpu, address, size, user)
        if address != self.stop_at and name in ('climb', 'release'):
            if self.prefix:
                return  # Execute the actual consumption prefix, not its sink.
            self.events.append((name,))
            NativeRules.dispatch(self, cpu, address, size, user)
            return
        super().dispatch(cpu, address, size, user)


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    path = directory / 'Prince of Persia 2.bin'
    raw = path.read_bytes()
    program = parse_resource_fork(raw)
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2005]['data']
    assert struct.unpack_from('>H', level, 0x2186)[0] == 4
    assert struct.unpack_from('>H', level, 0x218a)[0] == 6
    machine = NativeLedgeInput(program)
    digest, gates, prefixes = hashlib.sha256(), 0, 0
    for up, modifier, grip, alive, mode, facing in product(
            (-1, 0, 1), (-2, -1, 0, 1, 2), (0, 1, 12), (-1, 0), (0, 11), (0, 1)):
        bank = InputBank(-1, 1, up, -1, modifier)
        machine.fixture(level, bank, 91, mode=2, sequence=9)
        for field, value in ((-0x503a, alive), (-0x4f96, grip), (-0x5022, mode),
                             (-0x5054, 0 if facing else -1)):
            machine.put_word(field, value)
        machine.call(6, 0x18e0)
        request = ledge_request(bank, grip=grip, alive=alive, sequence_mode=mode)
        events = ((request,),) if request else ()
        if (machine.bank(), tuple(machine.events)) != (bank, events):
            raise AssertionError((bank, grip, alive, mode, facing, machine.bank(), machine.events, events))
        digest.update(repr((machine.bank(), machine.events)).encode())
        gates += 1
    machine.prefix = True
    for axes, modifier, action in product(product((-1, 0, 1), repeat=4), (-2, -1, 0, 1, 2),
                                          ('climb', 'release')):
        bank = InputBank(*axes, modifier)
        machine.fixture(level, bank, 91, mode=2, sequence=9)
        start, stop = (0x1998, 0x19d4) if action == 'climb' else (0x1a84, 0x1a92)
        machine.call(6, start, stop=(6, stop))
        expected = climb_input(bank) if action == 'climb' else release_input(bank)
        if machine.bank() != expected:
            raise AssertionError((action, bank, machine.bank(), expected))
        digest.update(repr(machine.bank()).encode())
        prefixes += 1
    if path.read_bytes() != raw:
        raise AssertionError('Read-only original changed')
    return dict(gate_cases=gates, prefix_cases=prefixes, mismatches=0,
                result_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(raw).hexdigest(),
                supplied=['Living/dead native ALIVE, bank, grip, mode and facing',
                          'Climb/release actions are sinks during routing',
                          'Ordinary unsupported-cell hold: terrain queries return zero'],
                exclusions=['No support/ledge geometry, animation, FrameAdv or OS input',
                            'Climb/release prefixes stop before their terrain lookup',
                            'No level5 sword-drop, ship, full action-body or complete input parity claim'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
