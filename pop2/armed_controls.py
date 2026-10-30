"""Directional-bank ownership while the sword is drawn.

OnAlert 6:24bc selects a request from the five native words; the action
bodies (DoStrike 6:2780, DoBlock 6:282a, PutSwordAway 6:2592, DoAdvance
6:1dda, DoRetreat 6:1d6e) either refuse it, leaving every word pending, or
accept it and consume (`consume_armed_request`). The bank stays in keyboard
coordinates and is remapped with the facing at dispatch, so a turn between
the press and the guard pose changes Forward/Backward as in the original.

Host extension, kept explicitly: a fresh Ctrl press is an attack request
that survives releasing Ctrl (the original cancels it, 4:3f38), except at
the counter gates, and rapid repeats during the first attack poses are
discarded. See docs/research/armed-input-priority.md.
"""

from dataclasses import replace

from pop2.mac_input import DirectionalInput
from pop2.sword_controls import armed_input_request, consume_armed_request


class ArmedControls:
    def armed_controls_available(self):
        return self.sword_drawn and not self.sword_sheathing

    def armed_raw_modifier(self):
        return -1 if self.shift_held else -2 if self.ctrl_held else 0

    def armed_input_bank(self):
        bank = getattr(self, 'armed_input', None)
        if bank is None:
            # Drawing (6:0cb6) and DoEngarde (6:1e80) leave the directions
            # cleared (0) and the modifier consumed; a held modifier is not
            # a fresh request.
            bank = DirectionalInput(modifier=-self.armed_raw_modifier())
        return bank

    def sample_armed_controls(self):
        """4:3e84-3f42 on the current keyboard state."""
        if not self.armed_controls_available():
            self.armed_input = None
            self.armed_attack_requested = False
            return None
        bank = self.armed_input_bank()
        frame = self.sample_keyboard()
        self.armed_input = bank.sample(frame.horizontal, frame.vertical, self.armed_raw_modifier())
        return self.armed_input

    def armed_relative_input(self):
        bank = self.sample_armed_controls()
        if bank is None:
            return None
        relative = bank.remap(facing_right=bool(self.sequence_state.facing))
        if getattr(self, 'armed_attack_requested', False):
            relative = replace(relative, modifier=-2)
        return relative

    def armed_request(self):
        """The OnAlert request at the guard gate (158), as 'sword_<kind>'."""
        relative = self.armed_relative_input()
        if relative is None:
            return None
        request = armed_input_request(relative, 158)
        return None if request in (None, 'special', 'recoil') else 'sword_' + request

    def armed_pending(self):
        """The armed request waiting in the bank, as a host command (tests)."""
        from pop2.scene_prototype import BufferedCommand

        request = self.armed_request()
        return None if request is None else BufferedCommand(request)

    def armed_press_ctrl(self):
        from pop2.scene_prototype import SWORD_ATTACK_START_POSES, SWORD_ATTACK_START_SEQUENCES

        bank = self.sample_armed_controls()
        if bank is None:
            return False
        state = self.sequence_state
        if (state.sequence_id in SWORD_ATTACK_START_SEQUENCES
                and state.action in SWORD_ATTACK_START_POSES):
            # Port QoL: a rapid repeat during the first three attack poses
            # does not schedule another swing.
            self.armed_input = replace(bank, modifier=2)
            self.modifier_input = 2
            return False
        self.armed_attack_requested = True
        self.modifier_input = 2
        return self.dispatch_armed_at_guard('sword_attack')

    def dispatch_armed_at_guard(self, kind):
        """A press at a guard pose starts at once when it is the request
        OnAlert selects; otherwise the selected one waits for its gate."""
        from pop2.scene_prototype import SWORD_GUARD_SEQUENCE

        if (self.sequence_state.sequence_id != SWORD_GUARD_SEQUENCE
                or self._combat_controls_locked()):
            return False
        # The guard sequence's poses are all ready poses (158).
        return self.dispatch_armed_request({kind}, pose=158, admit=False)

    def dispatch_armed_request(self, kinds=None, *, pose=None, admit=True):
        """Run the selected action body; consume only what it accepted."""
        relative = self.armed_relative_input()
        if relative is None:
            return False
        request = armed_input_request(relative, self.sequence_state.action if pose is None else pose)
        if request in (None, 'special', 'recoil'):
            return False
        kind = 'sword_' + request
        if kinds is not None and kind not in kinds:
            return False
        if admit and not self.armed_admits(kind) or not self.start_sword_action(kind):
            return False
        self.accept_armed_request(kind)
        return True

    def accept_armed_request(self, kind):
        bank = self.armed_input_bank()
        facing = bool(self.sequence_state.facing)
        relative = consume_armed_request(bank.remap(facing_right=facing), kind[len('sword_'):])
        self.armed_input = relative.remap(facing_right=facing)
        if kind == 'sword_attack':
            self.armed_attack_requested = False
            self.modifier_input = 2

    def armed_admits(self, kind):
        """The port's existing pose admission for each action body."""
        from pop2.scene_prototype import SWORD_GUARD_SEQUENCE, SWORD_STEP_SEQUENCES

        state = self.sequence_state
        if kind == 'sword_attack':
            return (state.sequence_id in SWORD_STEP_SEQUENCES | {SWORD_GUARD_SEQUENCE}
                    and state.action in (157, 158, 170, 171, 165))
        if kind == 'sword_sheathe':
            return state.action in (158, 170, 171)
        if kind == 'sword_block':
            return True
        return (state.sequence_id == SWORD_GUARD_SEQUENCE
                and state.action in (158, 170, 171))

    def consume_voluntary_turn(self, facing_before):
        # SwordCtrl 6:2330-233c: the voluntary turn consumes Backward (as it
        # was before turning) and the modifier (2), clearing other directions.
        relative = self.armed_input_bank().remap(facing_right=facing_before)
        relative = relative.consume('right', modifier=2, clear=True)
        self.armed_input = relative.remap(facing_right=facing_before)
