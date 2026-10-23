"""Per-level scenery caches, separate from gameplay and the window host."""

from dataclasses import replace

from PIL import Image

from pop2.render_opening import (
    ROOF_DECORATIONS, build_opening_room, draw_harbor, rooftop_scene_data,
)


class LevelRenderer:
    def __init__(self, level, preload_room=True, retouch_caverns=True):
        if level.kind != 5 and level.number not in (2, 3, 4, 5, 6, 7):
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
        if preload_room:
            self.room(level.start_room)

    @property
    def cavern_program(self):
        # Parsed on first use: menus build renderers for every level, and the
        # level-five export alone is about 25 MB of JSON.
        if self.level.kind not in (3, 4):
            return None
        from pop2.caverns import cavern_assets

        return cavern_assets(self.level.number)[0]

    def room(self, room_id, caverns=None):
        if not 0 <= room_id < 32:
            raise ValueError("Invalid scenery room")
        if self.level.kind in (3, 4):
            from pop2.caverns import (
                cavern_pressure_signature,
                cavern_room,
                cavern_scene_signature,
                cavern_scythe_signature,
            )

            if caverns is not None:
                caverns.lava.enter_room(room_id,
                    self.cavern_program.get('lava', {}).get('rooms', {}).get(str(room_id), ()))
            frame = caverns.entry_frame if caverns is not None else 0
            signature = (cavern_scene_signature(self.cavern_program, room_id, caverns)
                         if caverns is not None else '')
            pressure = cavern_pressure_signature(self.cavern_program, room_id, caverns) if caverns else ()
            fallen = caverns.bridge.fallen() if caverns is not None else frozenset()
            wobble = frozenset(caverns.bridge.wobble.items()) if caverns is not None else frozenset()
            scythe = (cavern_scythe_signature(self.cavern_program, room_id, caverns)
                      if caverns is not None else ())
            entry = caverns.entry_room if caverns is not None else self.level.start_room
            key = room_id, frame if room_id == entry else 0, signature, pressure, fallen, scythe, wobble
            if key not in self.cavern_frames:
                # Retain loose-floor variants, not every historical gate
                # height or plank wobble.
                for previous in tuple(self.cavern_frames):
                    if previous[0] == room_id and (previous[3] != pressure or previous[6] or wobble):
                        del self.cavern_frames[previous]
                self.cavern_frames[key] = cavern_room(room_id, entry_frame=key[1], animated=True,
                                                    loose_key=signature, pressure_key=pressure,
                                                    retouched=self.retouch_caverns,
                                                    level_number=self.level.number,
                                                    bridge_fallen=fallen, scythe_patch=scythe,
                                                    bridge_wobble=wobble)
            self.rooms[room_id] = self.cavern_frames[key]
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

    def enter_room(self, room_id, caverns=None):
        room = self.room(room_id, caverns)
        if self.level.kind not in (3, 4):
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
        if self.level.kind in (3, 4):
            # Snapshot before actors/HUD; later drawing must not modify this image.
            self.cavern_scenery = frame.copy()

    def animated_layer(self, frame, room_id, harbor, front=False, frame_number=0, desert=None, caverns=None):
        if self.level.kind in (3, 4) and caverns is not None:
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
            frame = draw_cavern_torches(frame, room_id, caverns, level_number=self.level.number)
            frame = draw_cavern_lava(frame, room_id, caverns, level_number=self.level.number)
            frame = draw_cavern_darts(frame, room_id, caverns, level_number=self.level.number)
            frame = draw_cavern_spikes(frame, room_id, caverns, self.cavern_map,
                                        level_number=self.level.number)
            frame = draw_bridge_planks(frame, room_id, caverns, level_number=self.level.number)
            return draw_cavern_falling(frame, room_id, caverns, self.level.data,
                                       self.room(room_id, caverns), level_number=self.level.number)
        if room_id in self.desert_rooms:
            return self.desert_rooms[room_id].draw(frame, frame_number, desert, front)
        if harbor is None:
            return frame
        return draw_harbor(frame, room_id, harbor, front=front,
                           level_resource_id=self.level.resource_id)

    def supported_rooms(self):
        if self.level.kind == 1:
            return [0, 1, 2]
        if self.level.kind in (3, 4):
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
            return {"1": 1, "2 (Stones)": 0, "Right shore": 2}
        if self.level.kind in (3, 4):
            return {f"Room {room + 1}": room for room in self.supported_rooms()}
        terrain, _shapes, _pieces = rooftop_scene_data(self.level.resource_id)
        available = set(self.supported_rooms())
        route = []
        room = self.level.start_room
        while room in available and room not in route:
            route.append(room)
            left = terrain.neighbor(room, "left")
            room = left if left in available else terrain.neighbor(room, "down")
        entries = {str(index + 1): room for index, room in enumerate(route)}
        secret = terrain.neighbor(self.level.start_room, "right")
        if secret in available and secret not in route:
            entries["Secret (right)"] = secret
        return entries
