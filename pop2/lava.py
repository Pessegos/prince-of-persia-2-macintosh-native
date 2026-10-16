"""Cavern lava state recovered from CODE:8, separate from scenery and input."""

from dataclasses import dataclass, field
import random

from pop2.opponent_generation import character_column
from pop2.terrain import character_row, floor_contact_x, floor_y


ENHANCED_BUBBLE_OFFSET_X = 5
ENHANCED_BUBBLE_OFFSET_Y = -1


@dataclass
class LavaPool:
    tables: dict
    flags: int = 0
    bubbles: list = field(default_factory=lambda: [[0] * 6 for _ in range(15)])
    enhanced: bool = False

    @property
    def character_sequence(self):
        # GetLavaCharSeqIdx 8:3648-3672.
        return (self.flags & 0x6000) >> 13 if self.flags & 0x8000 else -1

    def trigger_bubble(self, event):
        # TriggerLavaBubble 8:38e4: reuse the first inactive entry.
        bubble = next((value for value in self.bubbles if not value[0]), None)
        if bubble is not None and self.flags - 1 == event[0]:
            _, sequence, dy, dx, layer = event
            bubble[:] = [1, 0, sequence, dy, dx, layer]

    def initialize(self, cell):
        # TriggerLava/ResetLavaInfo: seed by native cell index modulo 3.
        self.flags = (cell % 3) * 5
        for event in self.tables['events']:
            self.trigger_bubble(event)

    def begin_death(self, mode, facing, actor_type=0, random_value=None):
        # GetLavaInfoHnd 8:34ce-3538. Rnd(3) is inclusive (0..3).
        self.flags = 0x8000
        if actor_type != 0:
            self.flags |= 0x4000
        elif mode not in (3, 4):
            self.flags |= 0x2000
            if (random.randint(0, 3) if random_value is None else random_value) == 0:
                self.flags |= 0x1000
        if not facing:
            self.flags |= 0x0800
        return (116, 70) if actor_type == 0 else (115, 69)

    def advance(self):
        # AnimLava 8:31fe-33ee uses the PREVIOUS phase for tests/events.
        previous, sequence = self.flags & 31, self.character_sequence
        if previous == 22 or sequence >= 0 and previous == 3:
            if previous == 22 and sequence < 0 and self.enhanced:
                # Visual QoL: wrap and process phase zero in this update,
                # rather than holding every bubble for one extra frame.
                self.flags, previous = 0, 0
            else:
                self.flags = (self.flags & 0xf800) | 4 if previous == 3 else 0
                return ()
        self.flags += 1
        if sequence >= 0 and previous < 3:
            return ()
        sounds = ()
        if sequence >= 0:
            limit = self.tables['limits'][sequence]
            if previous >= limit:
                if not self.flags & 0x1000 or previous >= limit + 16:
                    self.flags &= 0x07ff
                if previous == limit:
                    sounds = (68,)
            previous = 0
        for bubble in self.bubbles:
            if not bubble[0]:
                continue
            bubble[1] += 1
            shape = self.tables['bubbles'][bubble[2]][bubble[1]]
            if shape == -1:
                bubble[0] = 0
            elif shape == -2:
                bubble[5] = 1
                bubble[1] += 1
        for event in self.tables['events']:
            if event[0] == previous:
                self.trigger_bubble(event)
        return sounds

    def drawings(self):
        """(Shape, X offset, bottom offset, mirrored) admission order."""
        sequence, phase = self.character_sequence, self.flags & 31
        dx, dy = self.tables['piece_offsets']
        # Keep the native cover/order as the reference. Enhanced lava uses
        # the original continuous surface instead of the rock-cut cover.
        cover = 3614 if self.enhanced else 3615
        records = []
        if sequence >= 0:
            records.append((cover, dx, dy, False))
            shape, x, y = self.tables['characters'][sequence][phase]
            if shape != -1:
                mirrored = bool(self.flags & 0x0800)
                records.append((3500 + shape, x, y, mirrored))
                if phase in (1, 2):
                    shape, x, y = self.tables['splashes'][phase]
                    records.append((3500 + shape, x, y, mirrored))
            if phase < 3:
                return records
        elif self.enhanced:
            # The filled surface is a background, not an occluding cover:
            # painting it between bubble passes would erase rear bubbles.
            records.append((cover, dx, dy, False))
        # DrawCaveLava 8:23c0-24b4 interleaves rear bubbles, the cover,
        # then front bubbles. The cover's rock pixels erase the base fill.
        for layer in range(2):
            for active, frame, kind, y, x, foreground in self.bubbles:
                if active and foreground != layer:
                    shape = 3616 + self.tables['bubbles'][kind][frame]
                    # Presentation-only: leave the native event positions and
                    # all character/splash anchors untouched.
                    draw_x = x + (ENHANCED_BUBBLE_OFFSET_X if self.enhanced else 0)
                    draw_y = y + (ENHANCED_BUBBLE_OFFSET_Y if self.enhanced else 0)
                    records.append((shape, draw_x, draw_y, False))
            if layer == 0 and sequence < 0 and not self.enhanced:
                records.append((cover, dx, dy, False))
        return records


@dataclass
class Lava:
    tables: dict | None = None
    room: int | None = None
    pools: dict = field(default_factory=dict)
    enhanced: bool = False

    def enter_room(self, room, records):
        if self.tables is None or room == self.room:
            return
        self.room = room
        self.pools.clear()
        for record in records:
            key = record['room'], record['cell']
            if key not in self.pools:
                pool = self.pools[key] = LavaPool(self.tables, enhanced=self.enhanced)
                pool.initialize(key[1])

    def advance(self):
        return tuple(cue for pool in self.pools.values() for cue in pool.advance())

    def contact(self, terrain, motion, state, frame, *, landed=False):
        # CheckLavaBoil 8:33fc-348c uses cached actor column/physical row,
        # supporting-foot X, and the FRAM floor-contact flag, not sprite overlap.
        # HitFloor 6:0336 calls GetLavaInfoHnd directly: its lava-tile
        # landing bypasses CheckLavaBoil's surface/pose admission limits.
        if motion.dead or (not landed and not frame.aux & 0x40):
            return None
        y = floor_y(motion.row) + state.current_y
        foot = floor_contact_x(state.target_x, state.facing, frame)
        row, column = character_row(y), character_column(foot)
        tile = terrain.tile(motion.room, column, row)
        if tile.kind not in (23, 24) or (not landed and y <= row * 120 + 76):
            return None
        if not landed and (tile.kind == 23 and foot < column * 51 + 43
                           or tile.kind == 24 and foot > column * 51 + 36):
            return None
        cell = tile.row * 10 + tile.column - int(tile.kind == 24)
        return self.pools.get((tile.room, cell))
