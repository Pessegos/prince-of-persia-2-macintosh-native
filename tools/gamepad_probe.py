"""Show what the game reads from connected controllers, without the game.

    .venv\Scripts\python.exe -m tools.gamepad_probe [--seconds N]

Prints each controller SDL recognises (name and button style) and every
change of the digital inputs the game uses (buttons, triggers and the left
stick past its thresholds), with the original key each one stands for in
play. Useful for checking a controller nobody here owns.
"""

import argparse
import time

from pop2.gamepad import PadReader, SdlGamepads
from pop2.input_bindings import ACTION_BY_NAME, Bindings, pad_name
from pop2.input_routing import PAD_DIRECTIONS


def meaning(name, bindings):
    if name in PAD_DIRECTIONS:
        return PAD_DIRECTIONS[name]
    action = bindings.action_for(name)
    return ACTION_BY_NAME[action].label if action else '-'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--seconds', type=float, default=60.0,
                        help='how long to listen (default 60; Ctrl+C stops sooner)')
    options = parser.parse_args(argv)
    pads = SdlGamepads()
    reader = PadReader()
    bindings = Bindings('controller')
    deadline = time.monotonic() + options.seconds
    while not pads.ready and pads.error is None and time.monotonic() < deadline:
        time.sleep(.01)
    if pads.error is not None:
        print(f'Controller support unavailable: {pads.error}')
        return 1
    print('Listening for controllers. Press buttons; Ctrl+C to stop.')
    known, held = {}, frozenset()
    try:
        while time.monotonic() < deadline:
            snapshot = pads.snapshot
            current = {pad.instance: pad for pad in snapshot}
            for instance, pad in current.items():
                if instance not in known:
                    print(f'+ connected: {pad.name} (style: {pad.style})')
            for instance, pad in known.items():
                if instance not in current:
                    print(f'- disconnected: {pad.name}')
            known = current
            style = snapshot[0].style if snapshot else 'xbox'
            now = reader.inputs(snapshot)
            for name in sorted(now - held):
                print(f'  down  {name:<14} {pad_name(name, style) or name:<9} -> {meaning(name, bindings)}')
            for name in sorted(held - now):
                print(f'  up    {name}')
            held = now
            time.sleep(.01)
    except KeyboardInterrupt:
        pass
    finally:
        pads.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
