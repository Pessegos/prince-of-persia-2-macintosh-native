"""Original flask animation and ordinary healing-potion collection rules."""

from dataclasses import dataclass, field
import random

from pop2.terrain import character_column, floor_contact_x, floor_edge_distance


def potion_kind(foreground):
    return (foreground >> 5) & 7


def pickup_target(terrain, motion, state, record):
    contact = floor_contact_x(state.target_x, state.facing, record)
    column = character_column(contact)
    current = terrain.tile(motion.room, column, motion.row)
    target = current if current.kind == 10 else terrain.tile(
        motion.room, column + (1 if state.facing else -1), motion.row)
    if target.room is None or target.kind != 10 or potion_kind(target.foreground) not in (1, 2):
        return None
    distance = floor_edge_distance(contact, state.facing)
    same = current.kind == 10
    if state.action == 109:
        delta = (distance - 6 if not same and distance < 36 else 0) if state.facing else (
            distance + (0 if same else 51) - 34)
    else:
        delta = distance - (37 if state.facing else 26) if same else (
            distance + (1 if state.facing else 24))
    return target, delta * (1 if state.facing else -1)


@dataclass
class Potions:
    phases: dict = field(default_factory=dict)
    tiles: dict = field(default_factory=dict)
    picking: tuple | None = None
    drinking: bool = False
    held_kind: int = 0
    starting_max_life: int | None = None
    effect_pending: bool = False
    shift_was_held: bool = False
    songs: list = field(default_factory=list)

    def configure(self, terrain, rng=None):
        rng = rng or random
        for room in range(32):
            for cell in range(30):
                tile = terrain.tile(room, cell % 10, cell // 10)
                if tile.kind == 10:
                    self.phases.setdefault((room, cell),
                        (tile.foreground & 0xffe0) | rng.randint(1, 27))

    def advance(self, visible):
        # TriggerFlask 5:1ce8 / flask controller 5:13ec: a 28-update cycle.
        for key in set(visible):
            if key in self.phases and key not in self.tiles:
                value = self.phases[key]
                self.phases[key] = (value & 0xffe0) | ((value & 31) + 1) % 28

    def take(self, tile):
        key = tile.room, tile.row * 10 + tile.column
        self.tiles[key] = 1, tile.foreground & 0x0f00
        self.picking = None
        self.held_kind = potion_kind(tile.foreground)
        self.drinking = self.effect_pending = True

    def consume_events(self, state, actor):
        events = [event for event in state.sequence_events if event[0] == -14]
        for event in events:
            state.sequence_events.remove(event)
            if event != (-14, (1,)) or not self.effect_pending:
                continue
            self.effect_pending = False
            if not actor.alive:
                continue
            if self.starting_max_life is None:
                self.starting_max_life = actor.max_life
            # DoPickupEffect 4:45dc; life upgrade 2:53f8 is capped at 12.
            if self.held_kind == 2:
                actor.max_life = min(12, actor.max_life + 1)
                actor.life = actor.max_life
            elif self.held_kind == 1:
                actor.life = min(actor.max_life, actor.life + 1)
            else:
                continue
            self.songs.append(24)
