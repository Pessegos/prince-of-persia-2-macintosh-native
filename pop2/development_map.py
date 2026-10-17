"""Clean level scenery and spatial room selection for the F3 map."""

from collections import deque
from dataclasses import dataclass, field
import random

from PIL import Image, ImageChops

from pop2.level_rendering import LevelRenderer
from pop2.terrain import LevelMap


ROOM_SIZE = (510, 360)
MAP_SIZE = (464, 194)
DIRECTIONS = {'left': (-1, 0), 'right': (1, 0), 'up': (0, -1), 'down': (0, 1)}


def room_positions(terrain):
    positions = {terrain.start_room: (0, 0)}
    occupied = {(0, 0): terrain.start_room}
    pending = deque(positions)
    while pending:
        room = pending.popleft()
        x, y = positions[room]
        for direction, (dx, dy) in DIRECTIONS.items():
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


def map_enemies(level, positions):
    from pop2.animation_data import sequence_words
    from pop2.combat import Fighter, GuardSpawn
    from pop2.combat_art import GuardArtwork, sword_palette_for_level
    from pop2.render_opening import load_resource_file
    from pop2.sequence_runtime import SequenceRuntime, SequenceState
    from pop2.skeleton import Skeleton

    spawns = {room: GuardSpawn.all_from_level(level.data, room) for room in positions}
    if not any(spawns.values()):
        return None, {}
    prince = load_resource_file('Prince.rsrc')
    sequences = {i: sequence_words(item['data']) for i, item in prince['SEQS'].items()}
    art = GuardArtwork(load_resource_file('Skeleton.rsrc' if level.kind == 3 else 'Guard.rsrc'),
                       prince['SHAP'], int.from_bytes(prince['SHPL'][1000]['data'][:2], 'big'),
                       sword_palette_for_level(prince, level.kind))
    actors = {}
    for room, entries in spawns.items():
        actors[room] = []
        for spawn in entries:
            state = SequenceState(spawn.sequence_id, target_x=spawn.x, current_x=spawn.x,
                                  facing=spawn.facing, actor_type=spawn.actor_type,
                                  level_kind=level.kind)
            actor = Fighter(SequenceRuntime(sequences, state), spawn.life, spawn.life,
                            room, spawn.row, palette_variant=spawn.palette_variant)
            actor.runtime.next_frame()
            if spawn.skeleton_words:
                Skeleton.from_spawn(spawn).initialize(actor)
            actors[room].append(actor)
    return art, actors


def clean_room_frames(renderer, terrain, positions, enemies=None):
    """Use a private world/buffer so browsing cannot alter a running game."""
    from pop2.cavern_state import CavernState
    from pop2.harbor import Harbor

    world = None
    harbor = Harbor() if renderer.level.kind == 5 else None
    if renderer.level.number == 3:
        world = CavernState()
        world.configure_entry(renderer.cavern_program.get('entry_exit'))
        world.configure_lava(renderer.cavern_program.get('lava'))
        # These two controllers use the legacy global RNG during setup.
        seed = random.getstate()
        try:
            random.seed(17)
            world.potions.configure(terrain)
            world.configure_torches(renderer.cavern_program.get('torches', {}))
        finally:
            random.setstate(seed)
    scenery = {}
    for room in positions:
        art = renderer.room(room, world)
        frame = art.background.copy()
        parent = next((previous for previous in scenery
                       if room in (terrain.neighbor(previous, direction)
                                   for direction in DIRECTIONS)), None)
        if parent is not None and getattr(art, 'retained_mask', None) is not None:
            frame.paste(scenery[parent], (0, 0), art.retained_mask)
        frame = renderer.animated_layer(frame, room, harbor, caverns=world)
        frame = Image.alpha_composite(frame, art.foreground)
        scenery[room] = frame.copy()
        if enemies is not None:
            from pop2.combat import guard_frame_index
            from pop2.terrain import floor_y

            artwork, actors = enemies
            for actor in actors.get(room, ()):
                layer = Image.new('RGBA', frame.size)
                artwork.draw(layer, actor.state, floor_y(actor.row), actor.palette_variant)
                bounds = artwork.bounds(actor.state, floor_y(actor.row))
                record = artwork.frames[guard_frame_index(actor.state.action)]
                # Use the current room's actor-aware masks, including the
                # corrected cavern redraw ordering, not a flattened PNG mask.
                mask = art.actor_mask(actor.row, bounds[3], actor.state, bounds, record)
                layer.putalpha(ImageChops.multiply(layer.getchannel('A'), ImageChops.invert(mask)))
                frame = Image.alpha_composite(frame, layer)
                if renderer.level.kind == 3:
                    frame = art.draw_actor_foreground(frame, actor.state, bounds)
        frame = renderer.animated_layer(frame, room, harbor, front=True, caverns=world)
        yield room, frame.crop((0, 0, *ROOM_SIZE)).convert('RGB')


@dataclass(frozen=True)
class DevelopmentMap:
    image: Image.Image
    rooms: dict
    positions: dict
    enemy_rooms: frozenset = frozenset()
    source_frames: dict = field(default_factory=dict, repr=False, compare=False)
    scaled_images: dict = field(default_factory=dict, repr=False, compare=False)

    def transform(self, size):
        scale = min(size[0] / self.image.width, size[1] / self.image.height)
        return scale, ((size[0] - self.image.width * scale) / 2,
                       (size[1] - self.image.height * scale) / 2)

    def detail(self, size):
        if size == self.image.size:
            return self.image
        if size not in self.scaled_images:
            image = Image.new('RGB', size, '#101010')
            scale, (ox, oy) = self.transform(size)
            for label, rect in self.rooms.items():
                left, top, right, bottom = (round(value * scale + offset) for value, offset
                                            in zip(rect, (ox, oy, ox, oy)))
                source = self.source_frames.get(label)
                if source is None:
                    source = self.image.crop(rect)
                image.paste(source.resize((max(1, right - left), max(1, bottom - top)),
                                          Image.Resampling.LANCZOS), (left, top))
            self.scaled_images.clear()
            self.scaled_images[size] = image
        return self.scaled_images[size]

    def hit(self, x, y):
        return next((label for label, (left, top, right, bottom) in self.rooms.items()
                     if left <= x < right and top <= y < bottom), None)

    def move(self, label, direction):
        dx, dy = DIRECTIONS[direction]
        x, y = self.positions[label]
        candidates = [(other, (ox - x) * dx + (oy - y) * dy,
                        abs((ox - x) * dy - (oy - y) * dx))
                      for other, (ox, oy) in self.positions.items()]
        return min((candidate for candidate in candidates if candidate[1] > 0),
                   key=lambda candidate: (candidate[2], candidate[1]),
                   default=(label, 0, 0))[0]


def build_development_map(level, include_enemies=True):
    renderer = LevelRenderer(level, preload_room=False)
    terrain = LevelMap(level.data)
    entries = renderer.screen_entries()
    positions = {room: point for room, point in room_positions(terrain).items()
                 if room in entries.values()}
    if not positions:
        raise ValueError('This level has no supported map rooms')
    left = min(x for x, _y in positions.values())
    top = min(y for _x, y in positions.values())
    columns = max(x for x, _y in positions.values()) - left + 1
    rows = max(y for _x, y in positions.values()) - top + 1
    scale = min(MAP_SIZE[0] / (columns * ROOM_SIZE[0]),
                MAP_SIZE[1] / (rows * ROOM_SIZE[1]))
    width, height = round(columns * ROOM_SIZE[0] * scale), round(rows * ROOM_SIZE[1] * scale)
    origin = (MAP_SIZE[0] - width) // 2, (MAP_SIZE[1] - height) // 2
    image = Image.new('RGB', MAP_SIZE, '#101010')
    rooms, frames, labels = {}, {}, {room: label for label, room in entries.items()}
    enemies = map_enemies(level, positions) if include_enemies else None
    for room, frame in clean_room_frames(renderer, terrain, positions, enemies):
        x, y = positions[room]
        # Shared rounded grid edges prevent one-pixel seams or hit-test gaps.
        x1 = origin[0] + round((x - left) * ROOM_SIZE[0] * scale)
        y1 = origin[1] + round((y - top) * ROOM_SIZE[1] * scale)
        x2 = origin[0] + round((x - left + 1) * ROOM_SIZE[0] * scale)
        y2 = origin[1] + round((y - top + 1) * ROOM_SIZE[1] * scale)
        image.paste(frame.resize((x2 - x1, y2 - y1), Image.Resampling.LANCZOS), (x1, y1))
        rooms[labels[room]] = x1, y1, x2, y2
        frames[labels[room]] = frame
    return DevelopmentMap(image, rooms, {labels[room]: point for room, point in positions.items()},
                          frozenset(labels[room] for room, actors in enemies[1].items() if actors)
                          if enemies is not None else frozenset(), frames)
