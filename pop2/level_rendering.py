"""Per-level scenery caches, separate from gameplay and the window host."""

from pop2.render_opening import (
    ROOF_DECORATIONS, build_opening_room, draw_harbor, rooftop_scene_data,
)


class LevelRenderer:
    def __init__(self, level):
        if level.kind != 5 and level.number != 2:
            raise ValueError(f"Level {level.number} scenery is not implemented (environment {level.kind})")
        self.level = level
        self.rooms = {}
        self.beach = None
        self.room(level.start_room)

    def room(self, room_id):
        if not 0 <= room_id < 32:
            raise ValueError("Invalid scenery room")
        if room_id not in self.rooms:
            if self.level.kind == 1:
                if room_id != self.level.start_room:
                    raise ValueError("Only the level 2 entrance is implemented")
                from pop2.desert import BeachScene
                from pop2.render_opening import load_resource_file

                self.beach = BeachScene.read(load_resource_file("Desert.rsrc"), room_id)
                self.rooms[room_id] = self.beach.room
            else:
                self.rooms[room_id] = build_opening_room(include_curtain=False, room_id=room_id,
                                                        level_resource_id=self.level.resource_id)
        return self.rooms[room_id]

    def animated_layer(self, frame, room_id, harbor, front=False, frame_number=0):
        if self.beach is not None:
            return frame if front else self.beach.draw(frame, frame_number)
        if harbor is None:
            return frame
        return draw_harbor(frame, room_id, harbor, front=front,
                           level_resource_id=self.level.resource_id)

    def supported_rooms(self):
        if self.level.kind == 1:
            return [self.level.start_room]
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
            return {"1": self.level.start_room}
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
