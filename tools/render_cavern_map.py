"""Render the Macintosh level-three map from LEVL links and recovered scenery."""

from collections import deque
from pathlib import Path
import argparse

from PIL import Image, ImageDraw

from pop2.caverns import cavern_room
from pop2.level_data import LevelDefinition
from pop2.paths import OUTPUT_DIR
from pop2.render_opening import load_resource_file
from pop2.terrain import LevelMap


def room_positions(terrain):
    positions = {terrain.start_room: (0, 0)}
    pending = deque(positions)
    occupied = {(0, 0): terrain.start_room}
    offsets = {'left': (-1, 0), 'right': (1, 0), 'up': (0, -1), 'down': (0, 1)}
    while pending:
        room = pending.popleft()
        x, y = positions[room]
        for direction, (dx, dy) in offsets.items():
            neighbor = terrain.neighbor(room, direction)
            if neighbor is None:
                continue
            target = x + dx, y + dy
            if neighbor in positions:
                if positions[neighbor] != target:
                    raise ValueError('Room links do not form a flat map')
                continue
            if target in occupied:
                raise ValueError('Two rooms occupy the same map position')
            positions[neighbor] = target
            occupied[target] = neighbor
            pending.append(neighbor)
    return positions


def render_map(output=OUTPUT_DIR / 'level3-macintosh-map.png'):
    level = LevelDefinition.read(load_resource_file('Prince.rsrc'), 3)
    positions = room_positions(LevelMap(level.data))
    left = min(x for x, _y in positions.values())
    top = min(y for _x, y in positions.values())
    width = max(x for x, _y in positions.values()) - left + 1
    height = max(y for _x, y in positions.values()) - top + 1
    image = Image.new('RGB', (width * 510, height * 384), 'black')
    draw = ImageDraw.Draw(image)
    for room, (x, y) in positions.items():
        x, y = (x - left) * 510, (y - top) * 384
        art = cavern_room(room)
        image.paste(Image.alpha_composite(art.background, art.foreground).convert('RGB'), (x, y))
        draw.text((x + 8, y + 370), f'Room {room + 1}', fill='white')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT_DIR / 'level3-macintosh-map.png')
    args = parser.parse_args()
    print(render_map(args.output))


if __name__ == '__main__':
    main()
