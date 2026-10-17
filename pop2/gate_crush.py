"""DOS-inspired crush presentation over the unchanged Macintosh death rules."""

from dataclasses import dataclass, replace


# Original Mac poses, pixel heights, forward displacement and floor offset.
CRUSH_POSES = ((264, 35, 0, 0), (264, 29, 0, 0), (265, 22, 4, -2),
               (265, 18, 4, -1), (266, 12, 6, -1), (266, 14, 6, -1),
               (266, 12, 6, -1))


@dataclass
class GateCrush:
    key: tuple | None = None
    room: int = -1
    frame: int = 0
    start_phase: int = 48
    x: int = 0
    y: int = 0
    gate_released: bool = False

    def reset(self):
        self.key = None
        self.frame = 0
        self.gate_released = False

    def advance(self, terrain, motion, state, record, plates):
        if motion is None or state.source_sequence_id != 118:
            self.reset()
            return
        if self.key is None:
            if state.action != 264 or state.sequence_mode != 3:
                return
            gate = terrain.nearby_gate(motion.room, motion.row, state, record)
            if gate is None:
                return
            tile, _column = gate
            self.key = tile.room, tile.row * 10 + tile.column
            self.room = motion.room
            self.x, self.y = state.target_x, state.current_y
            self.start_phase = max(28, min(tile.foreground & 255, 183))
            self.frame = 0
        elif motion.room != self.room:
            self.reset()
            return
        else:
            self.frame = min(self.frame + 1, len(CRUSH_POSES) - 1)
        if plates.active.get(self.key) in (2, 3):
            self.gate_released = True

    def gate_phase(self, key):
        if self.key is None or key != self.key or self.gate_released:
            return None
        if self.frame == 5:
            return 32
        weight = (4, 3, 2, 1, 0, 0, 0)[self.frame]
        return (28 + (self.start_phase - 28) * weight // 4) & ~3

    def actor(self, state):
        if self.key is None or state.source_sequence_id != 118:
            return state, None
        action, height, dx, dy = CRUSH_POSES[self.frame]
        x = self.x + dx * (1 if state.facing else -1)
        return replace(state, action=action, target_x=x, current_x=x,
                       current_y=self.y + dy), height
