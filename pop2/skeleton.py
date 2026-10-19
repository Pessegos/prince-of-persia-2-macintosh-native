"""Level-three skeleton activation and collapse, CODE:4 14c6-1b86."""

from dataclasses import dataclass

from pop2.opponent_generation import EMPTY_TILES, WALL_TILES, OBSTACLE_TILES
from pop2.terrain import floor_y, stone_gate_blocks


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
        if (self.marker == -1 or self.timer or actor.alive or not player.alive
                or player.state.actor_type != 0 or actor.state.special_flag == 5
                or player.state.animation_state in (3, 4, 5)
                or actor.room != player.room or actor.row != player.row):
            return False
        own = encounter._supporting_column(actor)
        other = encounter._supporting_column(player)
        if abs(own - other) > 4:
            return False
        terrain = getattr(encounter, 'terrain', None)
        if terrain is not None:
            for column in range(min(own, other), max(own, other) + 1):
                tile = terrain.tile(actor.room, column, actor.row)
                if tile.kind in EMPTY_TILES | WALL_TILES | OBSTACLE_TILES | {23}:
                    return False
                if tile.kind == 4:
                    art = getattr(encounter, 'guard_art', None)
                    # Retain the old conservative clearance for art-free callers.
                    bounds = (art.bounds(actor.state, floor_y(actor.row))
                              if art is not None else (0, 0, 0, 57))
                    if stone_gate_blocks(tile.foreground, bounds, actor.state):
                        return False
        return True

    def control(self, encounter, actor):
        if not actor.alive:
            if self.timer > 0:
                self.timer -= 1
            return True
        # Skeleton AutoCtrl 4:169e-16ba applies to rising actors too.
        if (not encounter.player.alive
                and getattr(encounter, 'player_death_counter', -1) >= 5):
            self.collapse(actor, encounter=encounter)
            return True
        if actor.state.source_sequence_id == 88 and actor.state.action >= 179:
            if actor.state.action == 182:
                facing = int(actor.state.target_x < encounter.player.state.target_x)
                if actor.state.facing != facing:
                    actor.state.facing = facing
                    actor.state.target_x += 16 if facing else -16
                    actor.state.current_x = actor.state.target_x
            return True
        return False

    def try_wake(self, encounter, actor):
        from pop2.combat import select_sequence

        # FrameAdv 2:624a runs proximity before alert/control and the normal
        # AnimChar. Even an unfinished shake can react once its timer is zero.
        if self.phase not in ('dormant', 'collapsing') or not self.can_wake(encounter, actor):
            return False
        if self.shakes:
            self.shakes -= 1
            self.timer = 15 + encounter.rng.randrange(31)
            if actor.state.source_sequence_id != 112:
                select_sequence(actor, 112)
            actor.runtime.next_frame()
        else:
            select_sequence(actor, 88)
            actor.runtime.next_frame()
            self.phase = 'rising'
            self.victory_pending = False
            actor.life = actor.max_life
            actor.sword_drawn = True
            actor.targetable = True
            actor.death_registered = False
            actor.alert_mode = 3
            encounter.player.state.callback_flag = 0
            encounter.attack_pause = 0
            if actor.terrain_motion is not None:
                actor.terrain_motion.dead = False
        return True

    def after_frame(self, actor):
        if self.phase == 'rising' and actor.state.sequence_id == 227:
            self.phase = 'active'
        elif self.phase == 'collapsing' and actor.state.sequence_id == 119:
            self.phase = 'dormant'

    def shake(self, actor):
        from pop2.combat import select_sequence

        # ShakeBones 4:1900-1946 does not reset recovery or remaining shakes.
        if self.marker != 0 or actor.state.action != 206 or actor.state.special_flag == 5:
            return False
        select_sequence(actor, 112)
        return True

    def collapse(self, actor, landing=False, *, encounter=None, column=None):
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
        if not landing and actor.state.facing and encounter is not None:
            # Collapse 4:1744-176e keeps a right-facing heap on its ledge.
            column = encounter._supporting_column(actor) if column is None else column
            if encounter._guard_tile(actor, column - 1).kind in EMPTY_TILES:
                distance = encounter._guard_front_edge_distance(actor)
                if distance >= -3:
                    actor.state.target_x += distance + 3
                    actor.state.current_x = actor.state.target_x
