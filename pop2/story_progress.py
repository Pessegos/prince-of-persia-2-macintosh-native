"""Original inter-level scene selection and the deferred campaign clock."""

from dataclasses import dataclass, field


FRAMES_PER_MINUTE = 719
# KeepTime 2:5308-530e and FrameAdv 2:6834 show a time message this long.
MESSAGE_FRAMES = 24


@dataclass
class StoryProgress:
    minutes: int = 75
    frames_remaining: int = FRAMES_PER_MINUTE
    tree_stage: int = -1
    # KeepTime's a5-0x4fa2 request: 'minutes', 'seconds' or None. It is
    # presentation state only, not part of the saved campaign.
    message_pending: str | None = field(default=None, compare=False)

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
            # 2:5244-526c: every twelfth update of the last minute, replacing
            # the message already on screen.
            if self.minutes == 1 and self.frames_remaining % 12 == 0:
                self.message_pending = 'seconds'
            return False
        self.frames_remaining = FRAMES_PER_MINUTE
        self.minutes -= 1
        # 2:5226-5242: below five minutes, and on every fifth minute.
        if self.minutes and (self.minutes < 5 or self.minutes % 5 == 0):
            self.message_pending = 'minutes'
        return True

    def message_text(self):
        """KeepTime 2:5290-52fe formats against the A5 strings 0x558c-0x55aa."""
        if self.minutes <= 0:
            return 'Time has expired!'
        if self.minutes != 1:
            return f'{self.minutes} Minutes Left'
        seconds = (self.frames_remaining + 1) // 12
        return '1 Second Left' if seconds == 1 else f'{seconds} Seconds Left'
