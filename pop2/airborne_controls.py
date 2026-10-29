"""Carry the directional bank through SEQS3/4, including their native resets.

Airborne callbacks only sample. GenCtrl's pose26/44 clear runs at the simulation
boundary, and the existing grounded selector handles the eventual return.
"""

from dataclasses import replace

from pop2.mac_input import DirectionalInput
from pop2.running_controls import RunningControls


AIRBORNE_INPUT_SEQUENCES = frozenset((3, 4))


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
        self.directional_input = (self.directional_input.consume('up', clear=True) if sequence == 4
                                  else self.directional_input.consume(forward, 'up'))
        self.waiting_step_direction = 0
        self.airborne_vertical_followup = False
        self.run_repeat_up = False
        self.pending_action = None

    def waiting_key(self, key, pressed):
        if (self.sequence_state.sequence_id not in AIRBORNE_INPUT_SEQUENCES
                or not self.waiting_controls_available()):
            return super().waiting_key(key, pressed)
        fresh = key == 'up' and pressed and not self.up_held
        cancel_repeat = key == 'up' and not pressed and getattr(self, 'run_repeat_up', False)
        handled = super().waiting_key(key, pressed)
        self.sample_waiting_controls()
        if fresh:
            self.jump_started_for_press = True
            self.run_repeat_up = False
            self.airborne_vertical_followup = not self.horizontal_input
            # Preserve the existing rapid identical-jump filter. It consumes
            # this tap only, without erasing another directional request.
            from pop2.scene_prototype import BufferedCommand
            command = BufferedCommand('jump', self.horizontal_input,
                                      running=self.sequence_state.sequence_id == 4
                                      and bool(self.horizontal_input))
            if (getattr(self, 'queue_grace_remaining_ms', 0) > 0
                    and command == getattr(self, 'queue_grace_command', None)):
                self.directional_input = self.directional_input.consume('up')
        elif cancel_repeat:
            # A held takeoff key re-read after a native clear is automatic
            # repeat, not a new tap. Retain the port's release cancellation.
            self.directional_input = replace(self.directional_input, up=0)
            self.run_repeat_up = False
        if key == 'up' and not pressed:
            self.airborne_vertical_followup = False
        return handled

    def waiting_horizontal(self, direction, pressed):
        if self.sequence_state.sequence_id not in AIRBORNE_INPUT_SEQUENCES:
            return super().waiting_horizontal(direction, pressed)
        self.sample_waiting_controls()
        if not pressed and not self.horizontal_input and self.up_held:
            self.airborne_vertical_followup = True
            self.directional_input = replace(self.directional_input, up=-1)
            self.jump_started_for_press = True
        self.run_stop_requested = self.run_active and self.horizontal_input != self.run_direction
        return False

    def import_airborne_command(self):
        command = self.pending_action
        if command is not None and command.kind in ('horizontal', 'jump', 'crouch', 'crawl'):
            self.latch_waiting_command(command)
            if command.kind == 'jump' and not command.direction:
                self.airborne_vertical_followup = self.up_held
            self.pending_action = None

    def latch_waiting_command(self, command):
        super().latch_waiting_command(command)
        if (self.sequence_state.sequence_id in AIRBORNE_INPUT_SEQUENCES
                and command.kind == 'jump' and not command.direction and self.up_held):
            self.airborne_vertical_followup = True

    def update_waiting_controls(self, *, repeat=True):
        if self.sequence_state.sequence_id in AIRBORNE_INPUT_SEQUENCES:
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
        self.import_airborne_command()
        if state.cursor > 0 and state.action in (26, 44):
            # GenCtrl6:074a-0760 -> ClearControls4:3e3a. Ctrl/Shift survives.
            self.directional_input = self.directional_input.clear_directions()
            self.jump_started_for_press = self.up_held
            self.run_repeat_up = self.up_held and self.jump_repeat_armed

    def clear_waiting_controls(self):
        super().clear_waiting_controls()
        self.airborne_vertical_followup = False

    def retire_waiting_controls(self):
        super().retire_waiting_controls()
        if self.sequence_state.sequence_id not in AIRBORNE_INPUT_SEQUENCES:
            self.airborne_vertical_followup = False
