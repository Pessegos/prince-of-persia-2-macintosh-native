"""Execute the original Falling caller's vertical Catch window, with Catch supplied."""
import argparse
import hashlib
import json
from pathlib import Path

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules


class NativeFallingWindow(NativeRules):
    RANGES = {6: ((0x00a6, 0x0156),)}
    SUPPLIED = {(4, 0x37ca): 'catch'}


def run_probe(source):
    path = Path(source) / 'resource_forks' / 'Prince of Persia 2.bin'
    executable = path.read_bytes()
    machine = NativeFallingWindow(parse_resource_fork(executable))
    cases = []
    # The caller's successful and rejected branches both reach 6:0156.
    # No floor reader, animation, room cut or Catch geometry executes here.
    for row in range(4):
        for y in (-49, -48, -30, 0, 2, 3, 4):
            machine.reset(bytes(0x49ca))
            for offset, value in ((-0x4fa0, 1), (-0x504e, 0),
                                  (-0x5050, row * 120 + 106 + y),
                                  (-0x5048, row), (-0x5042, 33)):
                machine.put_word(offset, value)
            machine.call(6, 0x00a6, stop=(6, 0x0156))
            actual = bool(machine.services['catch'])
            if actual != (-48 <= y < 3):
                raise AssertionError((row, y, actual))
            cases.append(dict(row=row, relative_y=y, catch=actual))
    return dict(cases=cases, comparisons=len(cases), mismatches=0,
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                supplied=['Actor row/Y/type0, velocity33, already-set scream flag',
                          'Catch4:37ca is an inert counting endpoint'],
                exclusions=['Catch geometry/side effects, floor checks after6:0156',
                            'Animation, room cuts, full FrameAdv and keyboard timing'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f"{result['comparisons']} native window cases; zero mismatches")


if __name__ == '__main__':
    main()
