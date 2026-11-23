"""Per-level scenery caches, separate from gameplay and the window host."""

from dataclasses import replace

from PIL import Image

from pop2.render_opening import (
    ROOF_DECORATIONS, build_opening_room, draw_harbor, rooftop_scene_data,
)


# Environments drawn from the cave exports: caverns, ruins, temple and the tower.
CAVE_KINDS = (2, 3, 4, 6)


def room_kinds(terrain, room_id):
    """The kinds of a room's tiles: all that reading a room for the ambience takes from
    the level map."""
    return tuple(terrain.tile(room_id, column, row).kind for row in range(3) for column in range(10))


class LevelRenderer:
    def __init__(self, level, preload_room=True, retouch_caverns=True):
        if level.kind != 5 and level.number not in (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14):
            raise ValueError(f"Level {level.number} scenery is not implemented (environment {level.kind})")
        self.level = level
        self.retouch_caverns = retouch_caverns
        self.rooms = {}
        self.desert_rooms = {}
        self.cavern_frames = {}
        self.cavern_display = None
        self.cavern_underlay = None
        self.cavern_scenery = None
        self.cavern_map = None
        self.ambience = None
        self.desert_wind = None
        self.ruins_wind = None
        self.horse_star_seen = False
        self.ambience_air = {}
        # Rooms read before the Prince comes in: {room: ((drawing key, tiles), air)}.
        self.ambience_ahead = {}
        self.ambience_reading = None
        self.supported = None
        self.cavern_keys = {}
        if preload_room:
            self.room(level.start_room)

    @property
    def cavern_program(self):
        # Parsed on first use: menus build renderers for every level, and the
        # level-five export alone is about 25 MB of JSON.
        if self.level.kind not in (2, 3, 4, 6):
            return None
        from pop2.caverns import cavern_assets

        return cavern_assets(self.level.number)[0]

    def room(self, room_id, caverns=None):
        if not 0 <= room_id < 32:
            raise ValueError("Invalid scenery room")
        if self.level.kind in (2, 3, 4, 6):
            if caverns is not None:
                caverns.lava.enter_room(room_id,
                    self.cavern_program.get('lava', {}).get('rooms', {}).get(str(room_id), ()))
            key = self.room_key(room_id, caverns)
            self.cavern_keys[room_id] = key
            self.rooms[room_id] = self.cached_room(key)
            return self.rooms[room_id]
        if room_id not in self.rooms:
            if self.level.kind == 1:
                if room_id not in (0, 1, 2):
                    raise ValueError("Outside the desert shore")
                from pop2.desert import DesertScene
                from pop2.render_opening import load_resource_file

                scene = DesertScene.read(load_resource_file("Desert.rsrc"), room_id)
                self.desert_rooms[room_id] = scene
                self.rooms[room_id] = scene.room
            else:
                self.rooms[room_id] = build_opening_room(include_curtain=False, room_id=room_id,
                                                        level_resource_id=self.level.resource_id)
        return self.rooms[room_id]

    def room_key(self, room_id, caverns=None):
        """What a cave room's drawing depends on, as things stand. Only read."""
        from pop2.caverns import (
            cavern_pressure_signature,
            cavern_scene_signature,
            cavern_scythe_signature,
        )

        frame = caverns.entry_frame if caverns is not None else 0
        signature = (cavern_scene_signature(self.cavern_program, room_id, caverns)
                     if caverns is not None else '')
        pressure = cavern_pressure_signature(self.cavern_program, room_id, caverns) if caverns else ()
        fallen = caverns.bridge.fallen() if caverns is not None else frozenset()
        wobble = frozenset(caverns.bridge.wobble.items()) if caverns is not None else frozenset()
        scythe = (cavern_scythe_signature(self.cavern_program, room_id, caverns)
                  if caverns is not None else ())
        entry = caverns.entry_room if caverns is not None else self.level.start_room
        alternate = caverns is not None and caverns.alternate_entry
        redrawn = frozenset(caverns.loose.redrawn) if caverns is not None else frozenset()
        return (room_id, frame if room_id == entry else 0, signature, pressure, fallen, scythe, wobble,
                alternate, redrawn)

    def cached_room(self, key):
        """The cave room drawn for a key, built once."""
        if key not in self.cavern_frames:
            room_id, pressure, wobble = key[0], key[3], key[6]
            # Retain loose-floor variants, not every historical gate
            # height or plank wobble.
            for previous in tuple(self.cavern_frames):
                if previous[0] == room_id and (previous[3] != pressure or previous[6] or wobble):
                    del self.cavern_frames[previous]
            self.cavern_frames[key] = self.built_room(key)
        return self.cavern_frames[key]

    def built_room(self, key):
        from pop2.caverns import cavern_room

        room_id, frame, signature, pressure, fallen, scythe, wobble, alternate, redrawn = key
        return cavern_room(room_id, entry_frame=frame, animated=True, loose_key=signature, pressure_key=pressure,
                           retouched=self.retouch_caverns, level_number=self.level.number,
                           bridge_fallen=fallen, scythe_patch=scythe, bridge_wobble=wobble,
                           alternate_entry=alternate, redrawn=redrawn)

    def room_with_gates_up(self, room_id):
        """The room as it stands now, but with every gate raised."""
        key = self.cavern_keys.get(room_id)
        if key is None:
            return self.rooms[room_id]
        return self.gates_up_of(key, self.rooms[room_id])

    def gates_up_of(self, key, drawn):
        """drawn, the room as drawn for key, with every gate raised."""
        from pop2.caverns import cavern_gates_up

        pressure = cavern_gates_up(self.cavern_program, key[0], key[3])
        return drawn if pressure == key[3] else self.built_room((*key[:3], pressure, *key[4:]))

    def enter_room(self, room_id, caverns=None):
        if caverns is not None and self.cavern_display is not None and self.cavern_display[0] != room_id:
            # Entering a room repaints it whole: no crevice keeps a redraw.
            caverns.loose.redrawn.clear()
        room = self.room(room_id, caverns)
        if self.level.kind not in (2, 3, 4, 6):
            return room
        display = self.cavern_display
        if display is not None and display[0] == room_id and display[1] is room:
            return display[2]
        if display is None or display[0] != room_id:
            # DoCleanCut (2:608c) repaints without erasing the scenery buffer.
            # Only pixels untouched by BOTH new layers retain the previous room.
            self.cavern_underlay = self.cavern_scenery
        if self.cavern_underlay is not None and room.retained_mask is not None:
            background = room.background.copy()
            background.paste(self.cavern_underlay, (0, 0), room.retained_mask)
            resolved = replace(room, background=background)
        else:
            resolved = room
        self.cavern_display = room_id, room, resolved
        self.cavern_scenery = Image.alpha_composite(resolved.background, resolved.foreground)
        return resolved

    def remember_scenery(self, frame):
        if self.level.kind in (2, 3, 4, 6):
            # Snapshot before actors/HUD; later drawing must not modify this image.
            self.cavern_scenery = frame.copy()

    def ambience_kind(self):
        """(how a room is read, the ambience made of what is read) for this level, or
        None: the caves' and the ruins' are different effects."""
        from pop2.cavern_ambience import AMBIENCE_LEVELS, CavernAmbience, room_air
        from pop2.ruins_ambience import RUINS_LEVELS, RuinsAmbience, ruins_air

        if self.level.number in AMBIENCE_LEVELS:
            return room_air, CavernAmbience
        if self.level.number in RUINS_LEVELS:
            return ruins_air, RuinsAmbience
        return None

    def advance_ambience(self, room_id, terrain, footing=None, thuds=(), shakes=()):
        """One game tick of the optional cave or ruins ambience; pixels only."""
        from pop2.ruins_ambience import (
            DESERT_ROOMS, HORSE_ROOM, HORSE_STAR_DELAY_TICKS, RuinsAmbience, horse_shooting_star,
        )

        kind = self.ambience_kind()
        if kind is None:
            self.ambience = None
            return
        room_air, ambience = kind
        if self.level.number == 9 and room_id in DESERT_ROOMS and self.desert_wind is None:
            self.prepare_desert_wind(room_air)
        if self.desert_wind is not None:
            self.desert_wind.advance()
        if self.ambience is None or self.ambience.room != room_id:
            if room_id not in self.ambience_air:
                ahead = self.ambience_ahead.pop(room_id, None)
                if ahead is not None and ahead[0] == (self.cavern_keys.get(room_id), room_kinds(terrain, room_id)):
                    # Read beforehand from this very drawing of the room.
                    self.ambience_air[room_id] = ahead[1]
                else:
                    self.ambience_air[room_id] = room_air(self.level.number, room_id, self.rooms[room_id], terrain,
                                                          lambda: self.room_with_gates_up(room_id))
            self.ambience = ambience(room_id, self.ambience_air[room_id])
            if isinstance(self.ambience, RuinsAmbience) and self.ambience.air.windy:
                self.attach_ruins_wind()
        if self.ruins_wind is not None:
            self.ruins_wind.advance()
        self.ambience.advance(terrain, footing, thuds, shakes)
        # The first tick in the room draws the entry frame.
        if (self.level.number == 9 and room_id == HORSE_ROOM and not self.horse_star_seen
                and self.ambience.tick > HORSE_STAR_DELAY_TICKS):
            self.horse_star_seen = True
            self.ambience.shooter = horse_shooting_star()

    def attach_ruins_wind(self):
        from pop2.ruins_ambience import RuinsWind

        if self.ruins_wind is None:
            self.ruins_wind = RuinsWind()
            self.ruins_wind.prime()
        self.ambience.wind = self.ruins_wind

    def prepare_desert_wind(self, room_air, *, incremental=False):
        """Read the painted desert scenery, then start wind over the whole strip."""
        from pop2.ruins_ambience import DESERT_ROOMS, DesertWind, Dunes

        for room in DESERT_ROOMS:
            if room not in self.ambience_air:
                art = self.rooms.get(room) or self.room(room)
                self.ambience_air[room] = room_air(9, room, art)
                if incremental:
                    return
        self.desert_wind = DesertWind(Dunes.join([self.ambience_air[room].dunes for room in DESERT_ROOMS]))
        self.desert_wind.prime()

    def read_ambience_ahead(self, room_id, caverns, terrain):
        """Read one room next to this one that the ambience has not read yet, while the
        game waits for its next frame, so that walking in does not stall the frame.

        What is read is kept with the drawing and the tiles it was read from: a room
        that has changed by the time the Prince comes in is read again then, as it was
        before there was any reading ahead.
        It goes a step at a time, each call doing one: drawing the room, drawing it
        with its gates up when it has torches, then reading it. Returns whether a step
        was taken."""
        from pop2.cavern_ambience import room_torches

        kind = self.ambience_kind()
        if kind is None or self.level.kind not in CAVE_KINDS:
            return False
        room_air = kind[0]
        if self.level.number == 9 and self.desert_wind is None:
            self.prepare_desert_wind(room_air, incremental=True)
            return True
        reading = self.ambience_reading
        if reading is not None and reading[0] in self.ambience_air:
            reading = None  # The Prince went in first.
        if reading is None:
            reading = self.ambience_reading = self.room_to_read(room_id, caverns, terrain)
            if reading is None:
                return False
        near, seen, steps = reading
        key = seen[0]
        if 'drawn' not in steps:
            steps['drawn'] = self.cached_room(key)
            return True
        if 'raised' not in steps and room_torches(self.cavern_program, near):
            steps['raised'] = self.gates_up_of(key, steps['drawn'])
            return True
        self.ambience_reading = None
        self.ambience_ahead[near] = seen, room_air(self.level.number, near, steps['drawn'], terrain,
                                                   steps.get('raised'))
        return True

    def room_to_read(self, room_id, caverns, terrain):
        """(room, (drawing key, tiles), {}) of a room next door to read ahead, or None."""
        rooms = set(self.supported_rooms_cache())
        for direction in ('left', 'right', 'up', 'down'):
            near = terrain.neighbor(room_id, direction)
            # Once each: a room whose gates keep moving would be read again every frame.
            if near is None or near not in rooms or near in self.ambience_air or near in self.ambience_ahead:
                continue
            # Walking in repaints the room whole, so no crevice keeps a redraw then.
            key = (*self.room_key(near, caverns)[:8], frozenset())
            return near, (key, room_kinds(terrain, near)), {}
        return None

    def supported_rooms_cache(self):
        if self.supported is None:
            self.supported = tuple(self.supported_rooms())
        return self.supported

    def ambient_layer(self, frame, room_id):
        """Drawn after remember_scenery: a room cut keeps the scenery of the
        previous room in places, and must not keep a mote or a drop with it."""
        from pop2.ruins_ambience import OPENING_CLIFF, RuinsAmbience, ruins_air

        if (self.level.number, room_id) == OPENING_CLIFF and self.ambience is None:
            # The first playable frame follows the carpet's painted cliff directly.
            if room_id not in self.ambience_air:
                self.ambience_air[room_id] = ruins_air(self.level.number, room_id, self.rooms[room_id])
            self.ambience = RuinsAmbience(room_id, self.ambience_air[room_id])
            self.attach_ruins_wind()
        if self.ambience is not None and self.ambience.room == room_id:
            self.ambience.see_gates(self.rooms[room_id])
            frame = self.ambience.draw(frame)
        if self.level.number == 9:
            from pop2.ruins_ambience import DESERT_ROOMS, WIDTH

            if room_id in DESERT_ROOMS:
                if self.desert_wind is None:
                    self.prepare_desert_wind(ruins_air)
                origin = DESERT_ROOMS.index(room_id) * WIDTH
                self.desert_wind.put_sand(frame.load(), self.ambience_air[room_id], origin)
        return frame

    def animated_layer(self, frame, room_id, harbor, front=False, frame_number=0, desert=None, caverns=None,
                       falling=None):
        """The room's moving scenery behind (or, with ``front``, over) the characters.

        ``falling``, when a list, receives each falling slab as (MOB type, X,
        bottom, layer): the pixels its drawing changed, which the characters
        it is sorted after (pop2.object_order) are covered with again.
        """
        if self.level.kind == 6 and caverns is not None:
            # The final tower's flasks (native rooms 7, 8 and 10, and room
            # 3's drops) are front commands like the caverns' own; the static
            # room leaves their library-1 commands out.
            # Its moving scenery (pop2.final_scenery) has images in both.
            from pop2.terrain import LevelMap
            from pop2.caverns import draw_cavern_flasks, draw_final_scenery

            if self.cavern_map is None:
                self.cavern_map = LevelMap(self.level.data)
            if not front:
                return draw_final_scenery(frame, room_id, caverns, level_number=self.level.number,
                                          terrain=self.cavern_map)
            frame = draw_cavern_flasks(frame, room_id, caverns, self.cavern_map,
                                       level_number=self.level.number)
            return draw_final_scenery(frame, room_id, caverns, level_number=self.level.number,
                                      front=True, terrain=self.cavern_map)
        if self.level.kind in (2, 3, 4) and caverns is not None:
            from pop2.terrain import LevelMap
            from pop2.caverns import (
                draw_cavern_torches, draw_cavern_falling, draw_cavern_lava, draw_cavern_darts,
                draw_cavern_flasks, draw_cavern_spikes, draw_bridge_planks, draw_sword_items,
            )

            if self.cavern_map is None:
                self.cavern_map = LevelMap(self.level.data)
            if front:
                # Flask bodies and particles belong in front of actors.
                frame = draw_cavern_flasks(frame, room_id, caverns, self.cavern_map,
                                           level_number=self.level.number)
                if self.level.kind == 4:
                    # The sword item is a front-layer command (6:14ce, tile 22).
                    frame = draw_sword_items(frame, room_id, caverns, self.cavern_map,
                                             level_number=self.level.number)
                return draw_cavern_spikes(frame, room_id, caverns, self.cavern_map, front=True,
                                           level_number=self.level.number)
            occlusion = self.room(room_id, caverns).torch_occlusion if self.level.kind == 2 else None
            frame = draw_cavern_torches(frame, room_id, caverns, level_number=self.level.number,
                                       occlusion=occlusion)
            frame = draw_cavern_lava(frame, room_id, caverns, level_number=self.level.number)
            frame = draw_cavern_darts(frame, room_id, caverns, level_number=self.level.number)
            frame = draw_cavern_spikes(frame, room_id, caverns, self.cavern_map,
                                        level_number=self.level.number)
            frame = draw_bridge_planks(frame, room_id, caverns, level_number=self.level.number)
            if falling is None or not caverns.loose.falling:
                return draw_cavern_falling(frame, room_id, caverns, self.level.data,
                                           self.room(room_id, caverns), level_number=self.level.number)
            before, drawn = frame.copy(), []
            frame = draw_cavern_falling(frame, room_id, caverns, self.level.data,
                                        self.room(room_id, caverns), level_number=self.level.number,
                                        drawn=drawn)
            falling.extend(falling_layers(before, frame, drawn))
            return frame
        if room_id in self.desert_rooms:
            return self.desert_rooms[room_id].draw(frame, frame_number, desert, front)
        if harbor is None:
            return frame
        return draw_harbor(frame, room_id, harbor, front=front,
                           level_resource_id=self.level.resource_id)

    def supported_rooms(self):
        if self.level.kind == 1:
            return [0, 1, 2]
        if self.level.kind in (2, 3, 4, 6):
            from pop2.development_map import room_positions
            from pop2.terrain import LevelMap

            return sorted(room_positions(LevelMap(self.level.data)))
        scenery_map, _shapes, _pieces = rooftop_scene_data(self.level.resource_id)
        supported_kinds = {0, 1, 20, 47, 48, 49}
        rooms = []
        for room_id in range(32):
            if not any(scenery_map.tile(room_id, column, row).kind == 1
                       for row in range(3) for column in range(10)):
                continue
            tiles = [scenery_map.tile(room_id, column, row)
                     for row in range(-1, 4) for column in range(-1, 10)]
            if any(tile.room is not None and (tile.kind not in supported_kinds
                   or ((tile.foreground >> 8) & 15) > len(ROOF_DECORATIONS)) for tile in tiles):
                continue
            rooms.append(room_id)
        return rooms

    def screen_entries(self):
        if self.level.kind == 1:
            return {"Room 1": 1, "Room 2": 0, "Room 3": 2}
        if self.level.kind in (2, 3, 4, 6):
            return {f"Room {room + 1}": room for room in self.supported_rooms()
                    if not (self.level.number == 14 and room == 10)}
        terrain, _shapes, _pieces = rooftop_scene_data(self.level.resource_id)
        available = set(self.supported_rooms())
        route = []
        room = self.level.start_room
        while room in available and room not in route:
            route.append(room)
            left = terrain.neighbor(room, "left")
            room = left if left in available else terrain.neighbor(room, "down")
        entries = {f"Room {index + 1}": room for index, room in enumerate(route)}
        secret = terrain.neighbor(self.level.start_room, "right")
        if secret in available and secret not in route:
            entries[f"Room {len(entries) + 1}"] = secret
        return entries


def falling_layers(before, after, drawn):
    """(MOB type, X, bottom, layer) for each drawn slab: ``after``'s pixels
    inside the slab's pieces that its drawing changed, transparent elsewhere."""
    from PIL import Image, ImageChops

    layers = []
    for mob_type, x, y, area in drawn:
        box = (max(0, area[0]), max(0, area[1]), min(after.width, area[2]), min(after.height, area[3]))
        if box[0] >= box[2] or box[1] >= box[3]:
            continue
        changed = ImageChops.difference(before.crop(box), after.crop(box))
        red, green, blue, alpha = changed.split()
        mask = ImageChops.lighter(ImageChops.lighter(red, green), ImageChops.lighter(blue, alpha))
        mask = mask.point(lambda value: 255 if value else 0)
        if mask.getbbox() is None:
            continue
        layer = Image.new('RGBA', after.size)
        layer.paste(after.crop(box), box[:2], mask)
        layers.append((mob_type, x, y, layer))
    return layers
