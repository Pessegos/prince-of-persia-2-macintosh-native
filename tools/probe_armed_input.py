"""Execute original OnAlert request arbitration; actions are supplied sinks."""

import argparse
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_input_routes import NativeInputRoutes
from tools.probe_level7_rules import NativeRules
from tools.reference_armed_input import on_alert
from tools.reference_input_bank import InputBank


class NativeArmedInput(NativeInputRoutes):
    RANGES = {**NativeInputRoutes.RANGES,
              6: NativeInputRoutes.RANGES[6] + ((0x24bc, 0x2584),)}
    SUPPLIED = {**NativeInputRoutes.SUPPLIED,
                (7, 0x1266): 'special', (6, 0x2780): 'attack',
                (6, 0x2592): 'sheathe', (6, 0x282a): 'block',
                (6, 0x1dda): 'advance', (6, 0x1d6e): 'retreat',
                (4, 0x2bae): 'recoil_x'}

    def dispatch(self, cpu, address, size, user):
        name = self.SUPPLIED.get(divmod(address - self.CODE_BASE, 0x10000))
        if address != self.stop_at and name in (
                'special', 'attack', 'sheathe', 'block', 'advance', 'retreat', 'recoil_x'):
            event = (name,)
            if name == 'recoil_x':
                stack = cpu.reg_read(self.registers['a7'])
                event += (struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0],)
            self.events.append(event)
            return NativeRules.dispatch(self, cpu, address, size, user)
        return super().dispatch(cpu, address, size, user)


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    path = directory / 'Prince of Persia 2.bin'
    raw = path.read_bytes()
    program = parse_resource_fork(raw)
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2004]['data']
    assert struct.unpack_from('>H', level, 0x218a)[0] == 5
    machine = NativeArmedInput(program)
    digest, count = hashlib.sha256(), 0
    for axes, modifier, pose, actor in product(
            product((-1, 0, 1), repeat=4), (-2, -1, 0, 1, 2),
            (15, 150, 151, 157, 158, 161, 165, 167, 168, 169, 170, 171), (0, 1, 7, 8)):
        bank = InputBank(*axes, modifier)
        machine.fixture(level, bank, pose, sword=1)
        machine.put_word(-0x504e, actor)
        machine.call(6, 0x24bc)
        request = on_alert(bank, pose, actor)
        expected = ((('sequence', 57),) + ((('recoil_x', -9),) if actor == 0 else ()) if request == 'recoil'
                    else ((request,),) if request else ())
        if (machine.bank(), tuple(machine.events)) != (bank, expected):
            raise AssertionError((bank, pose, actor, machine.bank(), machine.events, expected))
        # Recoil's native signed X argument and selected sequence are observed,
        # while both action endpoints remain supplied.
        if request == 'recoil' and actor == 0 and machine.word(-0x5052) != 0:
            raise AssertionError('Recoil endpoint return was not stored')
        digest.update(repr((bank, pose, actor, machine.events)).encode())
        count += 1
    if path.read_bytes() != raw:
        raise AssertionError('Read-only original changed')
    return dict(cases=count, mismatches=0, result_sha256=digest.hexdigest(),
                executable_sha256=hashlib.sha256(raw).hexdigest(),
                supplied=['Input words, pose, actor type and level header',
                          'Action bodies and recoil X service are sinks returning zero'],
                exclusions=['No outer SwordCtrl/target/automatic or voluntary turn routing',
                            'No action admission/consumption, terrain, animation or FrameAdv parity',
                            'No OS keyboard, buffering lifetime or host repeat equivalence'])


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
