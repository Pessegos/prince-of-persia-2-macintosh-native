"""DOS-inspired crush presentation over the unchanged Macintosh death rules."""

from dataclasses import dataclass, replace


# Milliseconds from the first native kneeling pose. These are drawing times;
# the original controller still decides when escape ends and death occurs.
SLAM_AT_MS = 640
GATE_TRACK = ((0, 88), (300, 84), (460, 80), (SLAM_AT_MS, 12), (720, 32), (800, 28))
# Time, pose, original height, forward displacement and floor offset.
CRUSH_POSES = ((0, 264, 35, 0, 0), (SLAM_AT_MS, 265, 22, 4, -2), (840, 266, 17, 6, -1))
VISUAL_TIMES = tuple(sorted({time for time, _phase in GATE_TRACK}
                            | {pose[0] for pose in CRUSH_POSES}))


@dataclass
class GateCrush:
    key: tuple | None = None
    room: int = -1
    elapsed_ms: float = 0
    last_updated_at: float | None = None
    x: int = 0
    y: int = 0
    gate_released: bool = False
    life_before_crush: int | None = None

    def reset(self):
        self.key = None
        self.elapsed_ms = 0
        self.last_updated_at = None
        self.gate_released = False
        self.life_before_crush = None

    def begin(self, life):
        self.reset()
        self.life_before_crush = life if life > 0 else None

    def display_life(self, state, life):
        if (life == 0 and state.source_sequence_id == 118
                and self.life_before_crush is not None and self.elapsed_ms < SLAM_AT_MS):
            return self.life_before_crush
        return life

    def advance(self, terrain, motion, state, record, plates, now=None):
        if motion is None or state.source_sequence_id != 118:
            self.reset()
            return
        if self.key is None:
            if state.action != 264:
                return
            gate = terrain.nearby_gate(motion.room, motion.row, state, record)
            if gate is None:
                return
            tile, _column = gate
            self.key = tile.room, tile.row * 10 + tile.column
            self.room = motion.room
            self.x, self.y = state.target_x, state.current_y
            self.elapsed_ms = 0
            self.last_updated_at = now
        elif motion.room != self.room:
            self.reset()
            return
        else:
            if now is not None:
                self.update(now)
        if plates.active.get(self.key) in (2, 3):
            self.gate_released = True

    def update(self, now):
        if self.key is None:
            return
        if self.last_updated_at is not None:
            self.elapsed_ms = round(self.elapsed_ms + max(0, now - self.last_updated_at) * 1000, 6)
        self.last_updated_at = now

    def next_delay_ms(self):
        if self.key is None:
            return None
        return next((time - self.elapsed_ms for time in VISUAL_TIMES
                     if time > self.elapsed_ms), None)

    def gate_phase(self, key):
        if self.key is None or key != self.key or self.gate_released:
            return None
        return next(phase for time, phase in reversed(GATE_TRACK) if time <= self.elapsed_ms)

    def actor(self, state):
        if self.key is None or state.source_sequence_id != 118:
            return state, None
        _time, action, height, dx, dy = next(
            pose for pose in reversed(CRUSH_POSES) if pose[0] <= self.elapsed_ms)
        x = self.x + dx * (1 if state.facing else -1)
        return replace(state, action=action, target_x=x, current_x=x,
                       current_y=self.y + dy), height
