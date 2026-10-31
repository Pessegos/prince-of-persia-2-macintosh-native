"""Directional-bank ownership while the sword is drawn.

OnAlert 6:24bc selects a request from the five native words; the action
bodies (DoStrike 6:2780, DoBlock 6:282a, PutSwordAway 6:2592, DoAdvance
6:1dda, DoRetreat 6:1d6e) either refuse it, leaving every word pending, or
accept it and consume (`consume_armed_request`). The bank stays in keyboard
coordinates and is remapped with the facing at dispatch, so a turn between
the press and the guard pose changes Forward/Backward as in the original.

Ctrl follows the native modifier word: releasing it before an admitting
pose cancels the strike (4:3f38 writes 0), so a double tap swings once
unless the second press is still held at the next gate
(tools/probe_attack_taps.py). See docs/research/armed-input-priority.md.
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
            return None
        bank = self.armed_input_bank()
        frame = self.sample_keyboard()
        self.armed_input = bank.sample(frame.horizontal, frame.vertical, self.armed_raw_modifier())
        return self.armed_input

    def armed_relative_input(self):
        bank = self.sample_armed_controls()
        if bank is None:
            return None
        return bank.remap(facing_right=bool(self.sequence_state.facing))

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
        self.latch_armed_attack()
        return self.dispatch_armed_at_guard('sword_attack')

    def latch_armed_attack(self):
        """A fresh Ctrl word (-2), as the sample of a new press writes it.
        It stays pending only while Ctrl is held."""
        bank = self.sample_armed_controls()
        if bank is not None:
            self.armed_input = replace(bank, modifier=-2)

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
            self.modifier_input = 2

    def sheathe_unengaged(self):
        """SwordCtrl 6:2368-2386: with no engaged opponent within reach, a
        pending Down calls PutSwordAway directly, at any mode-0/1 pose and
        ahead of a pending attack; OnAlert's guard-pose gate does not apply."""
        combat = getattr(self, 'combat', None)
        if combat is not None and combat.player_distance_routed():
            return False
        relative = self.armed_relative_input()
        if relative is None or relative.down >= 0:
            return False
        if not self.start_sword_action('sword_sheathe'):
            return False
        self.accept_armed_request('sword_sheathe')
        return True

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
