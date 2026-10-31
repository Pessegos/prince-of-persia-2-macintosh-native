"""Carry the directional bank through jump arcs and vertical landing.

Arc callbacks sample; vertical preparation has its early Forward gate.
GenCtrl's pose26/44 and protected-landing clears run at the simulation boundary,
and the existing grounded selector handles the eventual return.
"""


from pop2.mac_input import DirectionalInput, vertical_input_request
from pop2.running_controls import RunningControls


VERTICAL_INPUT_SEQUENCES = frozenset((14, 28, 11))
AIRBORNE_TAKEOFF_SEQUENCES = frozenset((3, 4, 14, 28))
AIRBORNE_INPUT_SEQUENCES = AIRBORNE_TAKEOFF_SEQUENCES | {11}


class AirborneControls(RunningControls):
    @staticmethod
    def waiting_sequence(sequence):
        return sequence in AIRBORNE_INPUT_SEQUENCES or RunningControls.waiting_sequence(sequence)

    def waiting_controls_available(self):
        state = self.sequence_state
        if (getattr(self, 'directional_input', None) is None
                and state.sequence_id in AIRBORNE_INPUT_SEQUENCES):
            # Scripted/dev entries can select an arc without a grounded input
            # controller. Establish ownership only while that arc is admitted.
            self.directional_input = DirectionalInput()
            if not super().waiting_controls_available():
                self.directional_input = None
                return False
            self.sample_waiting_controls()
        return super().waiting_controls_available()

    def begin_airborne_controls(self, sequence):
        if getattr(self, 'directional_input', None) is None:
            self.directional_input = DirectionalInput()
        self.sample_waiting_controls()
        forward = 'right' if self.sequence_state.facing else 'left'
        # DoFwdJump6:15ea consumes Forward/Up; DoRunJump6:1c14 clears
        # directions and consumes Up only after takeoff geometry accepts it.
        # DoJumpUp6:1608-160c has the same clear/consume-Up prefix.
        self.directional_input = (self.directional_input.consume('up', clear=True) if sequence != 3
                                  else self.directional_input.consume(forward, 'up'))
        self.waiting_step_direction = 0

    def waiting_key(self, key, pressed):
        if (self.sequence_state.sequence_id not in AIRBORNE_INPUT_SEQUENCES
                or not self.waiting_controls_available()):
            return super().waiting_key(key, pressed)
        fresh = key == 'up' and pressed and not self.up_held
        handled = super().waiting_key(key, pressed)
        self.sample_waiting_controls()
        if fresh:
            self.jump_started_for_press = True
        return handled

    def waiting_horizontal(self, direction, pressed):
        if self.sequence_state.sequence_id not in AIRBORNE_INPUT_SEQUENCES:
            return super().waiting_horizontal(direction, pressed)
        # A release creates no request (4:3e84); the takeoff consumed Up, and
        # the landing clear (26/44 or the protected modes) makes a held Up fresh.
        self.sample_waiting_controls()
        self.run_stop_requested = self.run_active and self.horizontal_input != self.run_direction
        if self.sequence_state.sequence_id in VERTICAL_INPUT_SEQUENCES:
            return self.update_waiting_controls()
        return False

    def update_waiting_controls(self, *, repeat=True):
        state = self.sequence_state
        if state.sequence_id in VERTICAL_INPUT_SEQUENCES and state.cursor > 0:
            if state.action == 15:
                return super().update_waiting_controls(repeat=repeat)
            if 67 <= state.action <= 69 and self.waiting_controls_available():
                self.sample_waiting_controls()
                relative = self.directional_input.remap(facing_right=bool(state.facing))
                _bank, request = vertical_input_request(relative, state.action, mode=state.animation_state)
                if request == 'forward_jump':
                    from pop2.scene_prototype import BufferedCommand
                    return self.dispatch_jump(BufferedCommand('jump', 1 if state.facing else -1))
        if state.sequence_id in AIRBORNE_INPUT_SEQUENCES:
            # Sampling/reset belongs to update_airborne_controls during the
            # tick, or to the key callback. Do not re-sample held keys here
            # immediately after this tick's ClearControls.
            return False
        return super().update_waiting_controls(repeat=repeat)

    def update_airborne_controls(self):
        state = self.sequence_state
        if state.sequence_id not in AIRBORNE_INPUT_SEQUENCES or not self.waiting_controls_available():
            return
        self.sample_waiting_controls()
        protected_landing = state.sequence_id in VERTICAL_INPUT_SEQUENCES and state.animation_state in (4, 5, 9)
        if state.cursor > 0 and (state.action in (26, 44) or protected_landing):
            # GenCtrl6:074a-0760 (26/44) and0576-059c (protected modes)
            # call ClearControls4:3e3a. Ctrl/Shift survives.
            self.directional_input = self.directional_input.clear_directions()
            self.jump_started_for_press = self.up_held
