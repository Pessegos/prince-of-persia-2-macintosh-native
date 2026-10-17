"""Level-three skeleton activation and collapse, CODE:4 14c6-1b86."""

from dataclasses import dataclass

from pop2.opponent_generation import character_column, EMPTY_TILES, WALL_TILES


@dataclass
class Skeleton:
    marker: int
    timer: int
    shakes: int
    phase: str = 'dormant'
    victory_pending: bool = False

    @classmethod
    def from_spawn(cls, spawn):
        words = spawn.skeleton_words
        shakes = (spawn.skill + 1) & 1 if spawn.skill else 3
        return cls(words[14], words[14], shakes)

    def initialize(self, actor):
        from pop2.combat import select_sequence

        active = self.marker == 1
        self.phase = 'active' if active else 'dormant'
        actor.life = actor.max_life if active else 0
        actor.sword_drawn = active
        actor.targetable = active
        select_sequence(actor, 63 if active else 112 if self.marker == 0 else 119)
        actor.runtime.next_frame()

    def can_wake(self, encounter, actor):
        player = encounter.player
        if (self.marker == -1 or not player.alive or player.state.animation_state in (3, 4, 5)
                or actor.room != player.room or actor.row != player.row):
            return False
        own = character_column(actor.state.target_x)
        other = character_column(player.state.target_x)
        if abs(own - other) > 4:
            return False
        terrain = getattr(encounter, 'terrain', None)
        if terrain is not None:
            for column in range(min(own, other), max(own, other) + 1):
                tile = terrain.tile(actor.room, column, actor.row)
                if tile.kind in EMPTY_TILES or tile.kind in WALL_TILES:
                    return False
                if tile.kind == 4 and tile.foreground & 255 < 120:
                    return False
        return True

    def control(self, encounter, actor):
        from pop2.combat import select_sequence

        if self.phase == 'active':
            return False
        if self.timer > 0:
            self.timer -= 1
        if self.phase in ('rising', 'collapsing'):
            return True
        actor.targetable = False
        if not self.can_wake(encounter, actor):
            return True
        if self.timer or actor.state.sequence_id != 119:
            return True
        if self.shakes:
            self.shakes -= 1
            self.timer = 15 + encounter.rng.randrange(31)
            select_sequence(actor, 112)
        else:
            self.phase = 'rising'
            self.victory_pending = False
            actor.life = actor.max_life
            actor.sword_drawn = True
            actor.targetable = True
            actor.death_registered = False
            if actor.terrain_motion is not None:
                actor.terrain_motion.dead = False
            select_sequence(actor, 88)
        return True

    def after_frame(self, actor):
        if self.phase == 'rising' and actor.state.sequence_id == 227:
            self.phase = 'active'
        elif self.phase == 'collapsing' and actor.state.sequence_id == 119:
            self.phase = 'dormant'

    def collapse(self, actor, landing=False):
        from pop2.combat import select_sequence

        # Skeleton death selects 120, cue 61 and a 120-update recovery timer.
        actor.life = 0
        actor.sword_drawn = False
        actor.targetable = False
        actor.recovering = False
        self.phase = 'collapsing'
        self.victory_pending = True
        self.timer = 120
        self.shakes = (actor.skill + 1) & 1 if actor.skill else 3
        actor.state.current_y = actor.state.vertical_velocity = 0
        actor.state.sound_events.append(61)
        select_sequence(actor, 112 if landing else 120)
