"""Compare exported cavern scenery with the original whole-room drawing routine."""

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from pop2.caverns import cavern_assets, cavern_command_sprite, clipped_sprite
from pop2.level_data import LevelDefinition
from pop2.level_rendering import LevelRenderer
from pop2.paths import ASSET_DIR, OUTPUT_DIR
from pop2.render_opening import load_resource_file
from pop2.terrain import LevelMap
from tools.extract_caverns import CavernRecovery, recover_room


def replay_scenery(commands, resources, palette, shapes, previous=None):
    """Replay native static transfers without clearing untouched destination pixels."""
    frame = previous.copy() if previous is not None else Image.new('RGBA', (510, 365), 'black')
    for command in commands:
        library = command[7]
        if library == 4 and 3581 <= command[1] <= 3589:
            continue
        clipped = clipped_sprite(cavern_command_sprite(command, resources, palette, shapes), command)
        if clipped is not None:
            sprite, position = clipped
            frame.paste(sprite, position, sprite)
    return frame


def pixel_difference(reference, actual, ignored=()):
    difference = ImageChops.difference(reference.convert('RGB'), actual.convert('RGB'))
    if ignored:
        draw = ImageDraw.Draw(difference)
        for top, left, bottom, right in ignored:
            draw.rectangle((left, top, right - 1, bottom - 1), fill='black')
    red, green, blue = difference.split()
    changed = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    pixels = difference.width * difference.height - changed.histogram()[0]
    return pixels, difference


def audit_caverns(program_path, output=None, *, level_number=3):
    output = output or OUTPUT_DIR / f'level{level_number}-cavern-background-audit'
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    original = Path(program_path).read_bytes()
    artwork = (ASSET_DIR / 'Caverns.rsrc').read_bytes()
    prince = (ASSET_DIR / 'Prince.rsrc').read_bytes()
    level = LevelDefinition.read(load_resource_file('Prince.rsrc'), level_number)
    terrain = LevelMap(level.data)
    export, resources, palette, shapes = cavern_assets(level_number)
    native = {}
    rooms = []
    renderer = LevelRenderer(level, preload_room=False, retouch_caverns=False)
    with CavernRecovery(original, artwork, prince) as machine:
        for room in range(32):
            commands = recover_room(original, artwork, level.data, room, prince,
                                    _machine=machine, _native_scene=True)['commands']
            native[room] = commands
            ignored = [command[6] for command in commands if command[7] == 1]
            expected = replay_scenery(commands, resources, palette, shapes)
            art = renderer.room(room)
            actual = Image.alpha_composite(art.background, art.foreground)
            count, difference = pixel_difference(expected, actual, ignored)
            stem = output / f'room-{room + 1:02d}'
            expected.save(f'{stem}-native.png')
            actual.save(f'{stem}-port.png')
            difference.save(f'{stem}-diff.png')
            rooms.append({'room': room + 1, 'commands': len(commands),
                          'commands_equal': commands == export['rooms'][str(room)],
                          'different_pixels': count,
                          'untouched_pixels': art.retained_mask.histogram()[255]})
    transitions = []
    for source in range(32):
        for side in ('left', 'right', 'up', 'down'):
            target = terrain.neighbor(source, side)
            if target is None:
                continue
            renderer = LevelRenderer(level, preload_room=False, retouch_caverns=False)
            renderer.enter_room(source)
            art = renderer.enter_room(target)
            actual = Image.alpha_composite(art.background, art.foreground)
            before = replay_scenery(native[source], resources, palette, shapes)
            expected = replay_scenery(native[target], resources, palette, shapes, before)
            ignored = [command[6] for room in (source, target)
                       for command in native[room] if command[7] == 1]
            count, _difference = pixel_difference(expected, actual, ignored)
            transitions.append({'source': source + 1, 'target': target + 1,
                                'side': side, 'different_pixels': count})
    passed = (all(room['commands_equal'] and not room['different_pixels'] for room in rooms)
              and all(not cut['different_pixels'] for cut in transitions))
    report = {
        'passed': passed,
        'level': level_number,
        'reference': 'Original CODE 3:1c64 whole-room traversal; native scenery transfers',
        'scope': 'Initial static scenery and all directed LEVL room links, at 510x365',
        'excluded': ['actors (including skeletons)', 'flask rectangles',
                     'animated torches', 'animated lava and intentional overhaul', 'HUD'],
        'limitations': 'Shared SHAP decoder; not an independent Macintosh rasterizer or all dynamic states',
        'source_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in
                          (('program', original), ('Caverns.rsrc', artwork), ('Prince.rsrc', prince))},
        'rooms': rooms,
        'transitions': transitions,
    }
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='ascii')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--program', type=Path, required=True,
                        help='Original Macintosh executable resource fork')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--level', type=int, choices=(3, 4), default=3)
    args = parser.parse_args()
    output = args.output or OUTPUT_DIR / f'level{args.level}-cavern-background-audit'
    report = audit_caverns(args.program, output, level_number=args.level)
    print(f"{'PASS' if report['passed'] else 'FAIL'}: {len(report['rooms'])} rooms, "
          f"{len(report['transitions'])} directed room cuts; report: {output / 'report.json'}")
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
