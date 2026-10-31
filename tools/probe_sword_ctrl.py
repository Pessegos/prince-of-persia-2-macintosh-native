"""Execute the original SwordCtrl 6:2164-2390 routing around OnAlert.

SwordCtrl decides each armed frame whether the Prince turns toward his
opponent (6:2638), reads his request (OnAlert 6:24bc), sheathes directly
(PutSwordAway 6:2592) or takes the voluntary turn (Shift + Backward,
6:22f2-2366). Those four bodies are sinks here; the services it consults
are supplied (below), so this proves the routing, not the bodies.
"""

import argparse
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_input_routes import NativeInputRoutes
from tools.reference_armed_input import sword_ctrl
from tools.reference_input_bank import InputBank


class NativeSwordCtrl(NativeInputRoutes):
    RANGES = {**NativeInputRoutes.RANGES,
              6: NativeInputRoutes.RANGES[6] + ((0x2164, 0x2390),)}
    SUPPLIED = {**NativeInputRoutes.SUPPLIED,
                (6, 0x24bc): 'alert', (6, 0x2638): 'turn', (6, 0x2592): 'sheathe',
                (6, 0x36f2): 'target', (4, 0x3312): 'set_target', (4, 0x35a6): 'cell',
                (4, 0x49ee): 'distance', (8, 0x02ae): 'bridge'}
    results = {}

    def dispatch(self, cpu, address, size, user):
        name = self.SUPPLIED.get(divmod(address - self.CODE_BASE, 0x10000))
        if address != self.stop_at and name in ('alert', 'turn', 'sheathe'):
            stack = cpu.reg_read(self.registers['a7'])
            caller = struct.unpack('>I', cpu.mem_read(stack, 4))[0] - self.CODE_BASE
            # The voluntary turn is the call returning to 6:2336.
            self.events.append((('voluntary',) if caller == 0x62336 else (name,), caller))
        super().dispatch(cpu, address, size, user)
        if address == self.stop_at or name is None:
            return
        if name in self.results:
            cpu.reg_write(self.registers['d0'], self.results[name] & 0xffff)


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    path = directory / 'Prince of Persia 2.bin'
    raw = path.read_bytes()
    program = parse_resource_fork(raw)
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2004]['data']
    assert struct.unpack_from('>H', level, 0x218a)[0] == 5
    machine = NativeSwordCtrl(program)
    digest, count = hashlib.sha256(), 0
    banks = [InputBank(0, right, 0, down, modifier) for right in (-1, 0, 1) for down in (-1, 0)
             for modifier in (-2, -1, 0, 1)]
    for (bank, mode, cell, alert, distance, opponent, actor, automatic, room, row, bridge,
         engage, wounded) in product(
            banks, (1, 2), (0, 11, 15), (0, 1, 2, 3), (-40, -16, -15, -1, 0, 100, 330, 331),
            (0, 6, 7), (0, 11), (0, 1), (1, 7, 10, 12), (0, 1), (0, 1), (0, 1), (False, True)):
        machine.fixture(level, bank, 158, mode=mode, sword=1)
        machine.put_word(-0x501c, 0)
        machine.put_word(-0x508c, opponent)
        machine.put_word(-0x504e, actor)
        machine.put_word(-0x5010, automatic)
        machine.put_word(-0x5040, room)
        machine.put_word(-0x5048, row)
        machine.put_word(-0x3130, bridge)
        machine.put_word(-0x5062, alert)
        machine.put_word(-0x5034, -3 if wounded else 0)
        machine.results = {'cell': cell, 'distance': distance, 'bridge': engage, 'target': 0}
        machine.call(6, 0x2166)
        # The hook can report one sink call twice: keep one per call site.
        calls = [event for event in machine.events if len(event) == 2 and isinstance(event[1], int)]
        events = tuple(call[0] for index, call in enumerate(calls)
                       if not index or call != calls[index - 1])
        actual = events, machine.bank(), machine.word(-0x5010)
        expected = sword_ctrl(bank, mode=mode, cell=cell, alert=alert, distance=distance,
                              opponent_type=opponent, actor_type=actor, automatic=automatic,
                              level=5, room=room, row=row, bridge=bridge, wounded=wounded,
                              bridge_test=bool(engage))
        if actual != expected:
            raise AssertionError((bank, mode, cell, alert, distance, opponent, actor, automatic, room,
                                  row, bridge, engage, wounded, actual, expected))
        digest.update(repr(actual).encode())
        count += 1
    if path.read_bytes() != raw:
        raise AssertionError('Read-only original changed')
    return dict(cases=count, mismatches=0, result_sha256=digest.hexdigest(),
                executable_sha256=hashlib.sha256(raw).hexdigest(),
                supplied=['Prince (character 10), life 3, pose 158, LEVL2004 header (level 5),'
                          ' opponent alert word a5-0x5062 0-3',
                          'Turn 6:2638, OnAlert 6:24bc and PutSwordAway 6:2592 are sinks;'
                          ' 4:35a6 (current cell kind), 4:49ee (distance), 6:36f2/4:3312 (target)'
                          ' and the level-five bridge test 8:02ae (0/1, rooms 1/7/10/12, rows 0/1)'
                          ' are supplied; tools/probe_bridge_engage.py executes 8:02ae itself'],
                exclusions=['Action bodies, opponent geometry and target choice',
                            'Other characters (6:2206 onward is common, 6:2166-2204 Prince-only)'])


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
