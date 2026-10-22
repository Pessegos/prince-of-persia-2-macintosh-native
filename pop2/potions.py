"""Original flask animation and ordinary healing-potion collection rules."""

from dataclasses import dataclass, field
import random

from pop2.terrain import character_column, floor_contact_x, floor_edge_distance


DRINKABLE = (1, 2, 3, 5)
# 2:5a26 starts a 228-update slow fall (a5-0x4fa6, decremented at 2:6c5e).
FLOAT_UPDATES = 228


def potion_kind(foreground):
    return (foreground >> 5) & 7


SWORD_TILE = 22
ITEM_TILES = (10, SWORD_TILE)


def pickup_target(terrain, motion, state, record):
    contact = floor_contact_x(state.target_x, state.facing, record)
    column = character_column(contact)
    current = terrain.tile(motion.room, column, motion.row)
    target = current if current.kind in ITEM_TILES else terrain.tile(
        motion.room, column + (1 if state.facing else -1), motion.row)
    # PickItUp 6:1576-1596 takes every flask; types 4 and 6 (flip and
    # 4:46b2) are not modelled yet and stay on the floor. 6:14ce-1574
    # takes a sword item (tile 22) the same way.
    if (target.room is None or target.kind not in ITEM_TILES
            or target.kind == 10 and potion_kind(target.foreground) not in DRINKABLE):
        return None
    distance = floor_edge_distance(contact, state.facing)
    same = current.kind in ITEM_TILES
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
    fatal: bool = False
    float_timer: int = 0

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

    def take_sword(self, tile):
        # 6:152c-1574: SEQS 91, the cell becomes floor (S04_406C) and the
        # sword type is the item's foreground & 3.
        self.tiles[tile.room, tile.row * 10 + tile.column] = 1, tile.foreground & 0x0f00
        self.picking = None
        return tile.foreground & 3

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
            elif self.held_kind == 3:
                # 4:466c -> 2:5a26: slow fall for 228 updates and song 111.
                self.float_timer = FLOAT_UPDATES
                self.songs.append(111)
                continue
            elif self.held_kind == 5:
                # 4:4678-46b0: DecLifePts(1) and sound 12; a fatal sip selects
                # SEQS:71 with death method 3, which the host applies.
                actor.life = max(0, actor.life - 1)
                state.sound_events.append(12)
                self.fatal = actor.life == 0
                continue
            else:
                continue
            self.songs.append(24)


    @property
    def floating(self):
        return self.float_timer > 0

    def advance_float(self):
        # 2:6c58-6c5e: one count per frame until zero.
        if self.float_timer:
            self.float_timer -= 1
