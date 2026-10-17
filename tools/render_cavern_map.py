"""Render the Macintosh level-three map from LEVL links and recovered scenery."""

from pathlib import Path
import argparse

from PIL import Image, ImageDraw

from pop2.development_map import clean_room_frames, map_enemies, room_positions
from pop2.level_data import LevelDefinition
from pop2.level_rendering import LevelRenderer
from pop2.paths import OUTPUT_DIR
from pop2.render_opening import load_resource_file
from pop2.terrain import LevelMap


def render_map(output=None, labels=False, enemies=False):
    level = LevelDefinition.read(load_resource_file('Prince.rsrc'), 3)
    terrain = LevelMap(level.data)
    positions = room_positions(terrain)
    renderer = LevelRenderer(level, preload_room=False)
    left = min(x for x, _y in positions.values())
    top = min(y for _x, y in positions.values())
    width = max(x for x, _y in positions.values()) - left + 1
    height = max(y for _x, y in positions.values()) - top + 1
    # A room spans three 120-pixel physical rows. The remaining viewport
    # pixels are overdraw/HUD, not another band in the level's world grid.
    image = Image.new('RGB', (width * 510, height * 360), 'black')
    draw = ImageDraw.Draw(image)
    actors = map_enemies(level, positions) if enemies else None
    for room, frame in clean_room_frames(renderer, terrain, positions, actors):
        x, y = positions[room]
        x, y = (x - left) * 510, (y - top) * 360
        image.paste(frame, (x, y))
        if labels:
            draw.text((x + 8, y + 345), f'Room {room + 1}', fill='white')
    output = Path(output) if output is not None else OUTPUT_DIR / (
        'level3-map-with-enemies.png' if enemies else 'level3-clean-map.png')
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--labels', action='store_true')
    parser.add_argument('--enemies', action='store_true')
    args = parser.parse_args()
    print(render_map(args.output, labels=args.labels, enemies=args.enemies))


if __name__ == '__main__':
    main()
