"""The first room's window escape, not a general terrain/physics engine."""

from render_opening import OPENING_FLOOR_Y, ROOF_GLASS_FRAMES


# CODE:23 ATMGlass/DrawObjGlass, DATA/A5:cd42 (Y, X), SHAP:3597-3608.
GLASS_POSITIONS = (
    (263, 107), (263, 141), (264, 182), (264, 206),
    (264, 209), (258, 207), (359, 149), (377, 180),
    (398, 235), (415, 260), (431, 182), (445, 231),
)


class OpeningEscape:
    def __init__(self, runtime, start_tile):
        self.runtime = runtime
        self.state = runtime.state
        self.tick = 0
        self.phase = "window"
        self.active = True
        state = self.state
        # Main CODE:2 0x5d56-0x5db4: tile anchor +22, opening adjustment -8.
        state.target_x = (start_tile % 10) * 51 + 22 - 8
        state.current_x = state.target_x
        state.current_y = 0
        state.facing = 1
        state.animation_state = 0
        state.horizontal_velocity = 0
        state.vertical_velocity = 0
        state.special_flag = 0
        state.sequence_mode = 0
        state.callback_counter = 0
        state.callback_flag = 0
        state.engine_counter = 0
        state.sequence_events.clear()
        state.sound_events.clear()
        self._jump_sequence(4)
        for _ in range(9):
            runtime.next_frame()
        # SetKidDefaults resets Y/velocity, then advances once: first pose 43.
        state.current_y = (start_tile // 10) * 120 + 106 - OPENING_FLOOR_Y
        runtime.next_frame()
        state.current_x = state.target_x

    @property
    def curtain_frame(self):
        foreground = self.tick + 1
        return ROOF_GLASS_FRAMES[foreground] if foreground < 14 else 8

    @property
    def glass_frame(self):
        # The mob is advanced once after TriggerGlass, before the first draw.
        index = self.tick + 1
        return index if index < len(GLASS_POSITIONS) else None

    def _jump_sequence(self, sequence_id):
        self.state.sequence_id = sequence_id
        self.state.cursor = 0

    def advance(self):
        if not self.active:
            return
        state = self.state
        self.tick += 1
        if self.phase == "window":
            # Finish pose 44; StartFall (CODE:4 0x4cf6) initializes SEQS:21.
            # Its setup pose 102 precedes the first displayed falling pose 103.
            self.runtime.next_frame()
            self._jump_sequence(21)
            self.runtime.next_frame()
            self.phase = "fall"
        elif self.phase == "landing" and state.action == 109:
            # GenCtrl's unheld crouch exits to SEQS:49, not the idle pose.
            self._jump_sequence(49)
            self.phase = "rise"

        self.runtime.next_frame()
        if self.phase == "fall":
            # CODE:4 0x341a/0x3464; normal gravity adds six per falling tick.
            if state.animation_state in (4, 9):
                state.vertical_velocity = min(63, state.vertical_velocity + 6)
                direction = 1 if state.facing else -1
                state.target_x += direction * state.horizontal_velocity
            state.current_y += state.vertical_velocity
            if state.current_y > 0:
                # Falling/HitFloor (CODE:6): floor row 1, speed <50 -> SEQS:17.
                state.current_y = 0
                self._jump_sequence(17)
                self.runtime.next_frame()
                state.horizontal_velocity = 0
                state.vertical_velocity = 0
                self.phase = "landing"
        if self.phase == "rise" and state.sequence_id == 2:
            self.active = False
            self.phase = "done"
        state.current_x = state.target_x
