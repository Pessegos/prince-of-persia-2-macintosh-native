"""Original inter-level scene selection and the deferred campaign clock."""

from dataclasses import dataclass


FRAMES_PER_MINUTE = 719


@dataclass
class StoryProgress:
    minutes: int = 75
    frames_remaining: int = FRAMES_PER_MINUTE
    tree_stage: int = -1

    @property
    def clock_started(self):
        return self.tree_stage >= 0

    @property
    def expired(self):
        return self.clock_started and self.minutes == 0

    def select_scene(self, previous_level, next_level):
        """2:0180-027e after load/copy-protection admission has succeeded."""
        scene = None
        if previous_level and previous_level != next_level and next_level != -1:
            scene = {1: 9, 2: 100, 3: 10, 5: 1, 9: 2, 13: 3}.get(previous_level)
        if scene is not None or previous_level < 4:
            return scene
        if self.tree_stage == -1:
            self.tree_stage = 0
            return 20
        # The native signed division truncates -1/9 to zero at time expiry.
        stage = 7 - max(0, self.minutes - 1) // 9
        if stage > self.tree_stage:
            self.tree_stage = stage
            return 20 + stage
        return None

    def advance_frame(self, player_alive=True):
        """One eligible original 2:51f4 clock update, not one host repaint."""
        if not self.clock_started or not player_alive or self.minutes <= 0:
            return False
        self.frames_remaining -= 1
        if self.frames_remaining:
            return False
        self.frames_remaining = FRAMES_PER_MINUTE
        self.minutes -= 1
        return True
