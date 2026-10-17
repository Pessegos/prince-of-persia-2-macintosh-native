"""Render the Macintosh level-three map from LEVL links and recovered scenery."""

from collections import deque
from pathlib import Path
import argparse
import random

from PIL import Image, ImageDraw

from pop2.cavern_state import CavernState
from pop2.level_data import LevelDefinition
from pop2.level_rendering import LevelRenderer
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


def render_map(output=OUTPUT_DIR / 'level3-clean-map.png', labels=False):
    level = LevelDefinition.read(load_resource_file('Prince.rsrc'), 3)
    terrain = LevelMap(level.data)
    positions = room_positions(terrain)
    renderer = LevelRenderer(level, preload_room=False)
    world = CavernState()
    world.configure_entry(renderer.cavern_program.get('entry_exit'))
    world.configure_lava(renderer.cavern_program.get('lava'))
    world.potions.configure(terrain)
    seed = random.getstate()
    try:
        random.seed(17)
        world.configure_torches(renderer.cavern_program.get('torches', {}))
    finally:
        random.setstate(seed)
    left = min(x for x, _y in positions.values())
    top = min(y for _x, y in positions.values())
    width = max(x for x, _y in positions.values()) - left + 1
    height = max(y for _x, y in positions.values()) - top + 1
    # A room spans three 120-pixel physical rows. The remaining viewport
    # pixels are overdraw/HUD, not another band in the level's world grid.
    image = Image.new('RGB', (width * 510, height * 360), 'black')
    draw = ImageDraw.Draw(image)
    scenery = {}
    for room, (x, y) in positions.items():
        x, y = (x - left) * 510, (y - top) * 360
        art = renderer.room(room, world)
        frame = art.background.copy()
        parent = next((previous for previous in scenery
                       if room in (terrain.neighbor(previous, direction)
                                   for direction in ('left', 'right', 'up', 'down'))), None)
        if parent is not None and art.retained_mask is not None:
            frame.paste(scenery[parent], (0, 0), art.retained_mask)
        frame = renderer.animated_layer(frame, room, None, caverns=world)
        frame = Image.alpha_composite(frame, art.foreground)
        scenery[room] = frame.copy()
        frame = renderer.animated_layer(frame, room, None, front=True, caverns=world)
        image.paste(frame.crop((0, 0, 510, 360)).convert('RGB'), (x, y))
        if labels:
            draw.text((x + 8, y + 345), f'Room {room + 1}', fill='white')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT_DIR / 'level3-clean-map.png')
    parser.add_argument('--labels', action='store_true')
    args = parser.parse_args()
    print(render_map(args.output, labels=args.labels))


if __name__ == '__main__':
    main()
