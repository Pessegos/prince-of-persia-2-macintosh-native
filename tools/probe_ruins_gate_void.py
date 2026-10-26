"""Execute bounded original gate predicates and Cut's unlinked down rebase.

Working actor/body fields are supplied, not sprite setup. No predicate or Cut
helper is stubbed. The Cut probe stops before the reverse-link/redraw tail.
Full FrameAdv, collision-buffer admission and audio playback are excluded.
"""

import argparse
import json
from pathlib import Path

from pop2.mac_resources import parse_resource_fork
from pop2.sequence_runtime import SequenceState
from pop2.terrain import character_row, stone_gate_blocks
from tools.probe_level7_rules import NativeRules


class Geometry(NativeRules):
    RANGES = {
        4: ((0x3afa, 0x3b24), (0x52bc, 0x5358), (0x5b0e, 0x5ba8)),
        6: ((0x4864, 0x4908),),
    }
    SUPPLIED = {}


def run_probe(source):
    forks = Path(source) / 'resource_forks'
    program = parse_resource_fork((forks / 'Prince of Persia 2.bin').read_bytes())
    levels = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())['LEVL']
    machine = Geometry(program)
    predicates = barriers = cuts = 0
    for number in (3, 6):
        level = levels[1999 + number]['data']
        for height in (34, 74):
            for actor in (0, 1):
                for selected in (2, 68):
                    for phase in range(256):
                        machine.reset(level)
                        for offset, value in ((-0x34ae, phase), (-0x504e, actor),
                                              (-0x502e, selected), (-0x502c, 20),
                                              (-0x5028, 20 + height)):
                            machine.put_word(offset, value)
                        state = SequenceState(selected, actor_type=actor)
                        actual = machine.call(4, 0x5b0e)
                        expected = stone_gate_blocks(phase, (0, 20, 30, 19 + height), state)
                        if actual != expected:
                            raise AssertionError((number, height, actor, selected, phase, actual))
                        predicates += 1
        machine.reset(level)
        machine.put_word(-0x4fc2, 1)
        actual = machine.call(4, 0x52bc, (4,))
        if actual != (5 if number == 3 else 1):
            raise AssertionError('Environment-specific gate barrier type differs')
        barriers += 1
    for number, room in ((6, 27), (5, 9)):
        level = levels[1999 + number]['data']
        for y in range(440, 1101, 30):
            machine.reset(level)
            machine.put_word(-0x5040, room)
            machine.put_word(-0x5050, y)
            machine.call(6, 0x4864, (3,), stop=(6, 0x4908))
            if (machine.word(-0x5040), machine.word(-0x5050), machine.word(-0x5048)) != (
                    0, y - 360, character_row(y - 360)):
                raise AssertionError('Unlinked Cut did not enter native room zero with Y - 360')
            cuts += 1
    return dict(gate_predicates=predicates, gate_barriers=barriers, room_zero_cuts=cuts,
                scope=__doc__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_probe(args.source), indent=2))


if __name__ == '__main__':
    main()
