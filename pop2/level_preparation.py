"""The next cave level, readied a step at a time while the game waits for frames.

Walking into the caves for the first time (level 2's last screen into level 3)
stalled for about a quarter of a second. The new level's scenery was built three
times over (the start room, then each of the first two frames of its entrance
door) and its first room was read for the ambience, all within the first two
frames. Most of that can be done beforehand, in the spare time of the level
before.

A rehearsal session of the next level is loaded and set up the way bind_level
sets up a real one. Only the drawings and readings of its start room are kept,
each under the exact key the real level asks for. The renderer is handed over
when that very level is loaded with the same entrance. Anything that does not
match is built again then, as it always was.
"""

from pop2.level_rendering import CAVE_KINDS, LevelRenderer, room_kinds

# The entrance door's first frames are drawn on the first frames of a level.
ENTRY_FRAMES_AHEAD = 3


class NextLevel:
    def __init__(self, resources, number, terrain_enabled=True, ruins_entry=1, ambience=lambda: False):
        self.resources, self.number = resources, number
        self.terrain_enabled, self.ruins_entry = terrain_enabled, ruins_entry
        self.ambience = ambience
        self.renderer = None
        self.done = False
        self._steps = self.steps()

    def step(self):
        """One step of readying. Returns whether a step was taken."""
        if self.done:
            return False
        try:
            next(self._steps)
        except StopIteration:
            self.done = True
        return True

    def take(self, number, terrain_enabled, ruins_entry, level):
        """The readied renderer, for this level as it is really loaded, or None."""
        if (self.renderer is None or (number, terrain_enabled, ruins_entry)
                != (self.number, self.terrain_enabled, self.ruins_entry)):
            return None
        renderer, self.renderer, self.done = self.renderer, None, True
        # The same level read again: the session's own definition is the one to keep.
        renderer.level = level
        renderer.cavern_map = None
        return renderer

    def steps(self):
        from pop2.cavern_ambience import AMBIENCE_LEVELS, colours_of, room_air, room_torches
        from pop2.game_session import GameSession

        game = GameSession.load(self.resources, self.number, self.terrain_enabled, ruins_entry=self.ruins_entry)
        if game.level.kind not in CAVE_KINDS or game.caverns is None:
            return
        yield
        # The exports first, then the renderer, which draws the start room once.
        from pop2.caverns import cavern_assets, room_assets

        cavern_assets(self.number)
        yield
        renderer = LevelRenderer(game.level)
        self.renderer = renderer
        yield
        # As bind_level sets up the world before entering the start room.
        caverns, program = game.caverns, renderer.cavern_program
        caverns.configure_level_entry(program, game)
        caverns.configure_torches(program.get('torches', {}))
        caverns.configure_lava(program.get('lava'))
        room = game.room_id
        key = renderer.room_key(room, caverns)
        keys = [key]
        if room == caverns.entry_room and caverns.entry_frames:
            last = min(len(caverns.entry_frames), caverns.entry_frame + ENTRY_FRAMES_AHEAD) - 1
            keys = [(key[0], frame, *key[2:]) for frame in range(caverns.entry_frame, last + 1)]
        for drawn_key in keys:
            renderer.cached_room(drawn_key)
            yield
        if self.number not in AMBIENCE_LEVELS or not self.ambience():
            return
        # The palette's tables, made once for the level.
        colours_of(tuple(sorted(room_assets(self.number, room)[2].items())))
        yield
        # The ambience first reads the room on the first tick, the door a frame on.
        key = keys[min(1, len(keys) - 1)]
        drawn = renderer.cached_room(key)
        raised = None
        if room_torches(program, room):
            raised = renderer.gates_up_of(key, drawn)
            yield
        air = room_air(self.number, room, drawn, game.level_map, raised)
        renderer.ambience_ahead[room] = (key, room_kinds(game.level_map, room)), air
