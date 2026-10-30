"""Extend directional-bank ownership through grounded running controllers."""

from dataclasses import replace

from pop2.control_mapping import RUN_START_SEQUENCE, RUN_STOP_SEQUENCE
from pop2.mac_input import DirectionalInput, read_keyboard, running_input_request
from pop2.waiting_controls import WaitingControls


RUN_INPUT_SEQUENCES = frozenset((1, 6, 43, 200, 201, 202))


class RunningControls(WaitingControls):
    @staticmethod
    def waiting_sequence(sequence):
        return sequence in RUN_INPUT_SEQUENCES or WaitingControls.waiting_sequence(sequence)

    def waiting_controls_available(self):
        state = self.sequence_state
        if (getattr(self, 'directional_input', None) is None and state.sequence_id in RUN_INPUT_SEQUENCES
                and not self.sword_drawn and not self.sword_sheathing
                and not self.ledge_hanging and not self.native_ledge
                and not self._combat_controls_locked() and not self._opening_active()):
            motion = getattr(self, 'terrain_motion', None)
            if motion is None or not (motion.falling or motion.sinking or motion.dead):
                frame = read_keyboard(self.held_directions, self.up_held, self.down_held, self.shift_held)
                bank = DirectionalInput().sample(frame.horizontal, frame.vertical,
                                                 -1 if self.shift_held else -2 if self.ctrl_held else 0)
                if frame.horizontal == (1 if state.facing else -1):
                    bank = bank.consume('right' if state.facing else 'left')
                self.directional_input = bank
                self.waiting_step_direction = 0
        return super().waiting_controls_available()

    def begin_running_controls(self, direction):
        bank = self.directional_input if self.waiting_controls_available() else DirectionalInput()
        frame = self.sample_keyboard()
        bank = bank.sample(frame.horizontal, frame.vertical,
                           -1 if self.shift_held else -2 if self.ctrl_held else 0)
        self.directional_input = bank.consume('right' if direction > 0 else 'left', clear=True)
        self.waiting_step_direction = 0
        self.run_vertical_followup = False

    def waiting_key(self, key, pressed):
        running = self.sequence_state.sequence_id in RUN_INPUT_SEQUENCES and self.waiting_controls_available()
        if not running:
            return super().waiting_key(key, pressed)
        fresh = key == 'up' and pressed and not self.up_held
        cancel_repeat = key == 'up' and not pressed and getattr(self, 'run_repeat_up', False)
        if fresh:
            self.run_repeat_up = False
        self.running_key_callback = True
        try:
            handled = super().waiting_key(key, pressed)
        finally:
            self.running_key_callback = False
        if fresh:
            self.jump_started_for_press = True
            self.run_vertical_followup = not self.horizontal_input
            self.try_startup_jump_chord()
        elif cancel_repeat:
            # A continuously held takeoff key is an automatic repeat, not a
            # new tap. Keep the host's cancellation when it is released.
            self.directional_input = replace(self.directional_input, up=0)
            self.run_repeat_up = False
        return handled

    def waiting_horizontal(self, direction, pressed):
        running = self.sequence_state.sequence_id in RUN_INPUT_SEQUENCES
        if not running:
            return super().waiting_horizontal(direction, pressed)
        self.sample_waiting_controls()
        if not pressed and not self.horizontal_input and self.up_held:
            # Existing host tolerance: release the horizontal half of a held
            # chord to request vertical alignment/climb after the brake.
            self.run_vertical_followup = True
            self.directional_input = replace(self.directional_input, up=-1)
            self.jump_started_for_press = True
        self.run_stop_requested = self.horizontal_input != self.run_direction
        return False

    def request_running_jump(self):
        self.jump_started_for_press = True
        self.sample_waiting_controls()
        self.directional_input = replace(self.directional_input, up=-1)
        self.run_vertical_followup = not self.horizontal_input
        self.try_startup_jump_chord()

    def try_startup_jump_chord(self):
        state = self.sequence_state
        direction = 1 if state.facing else -1
        if (state.sequence_id == RUN_START_SEQUENCE and 1 <= state.action <= 3 and state.cursor > 0
                and self.horizontal_input == -direction and self.directional_input.up < 0):
            from pop2.scene_prototype import BufferedCommand
            self.dispatch_jump(BufferedCommand('jump', -direction))
        elif (state.sequence_id == RUN_START_SEQUENCE and state.action == 1 and state.cursor > 0
              and self.horizontal_input == direction and self.directional_input.up < 0):
            # Deliberate host chord tolerance, narrower than a startup rewind:
            # native 15b6 otherwise requires *fresh* Forward as well as Up.
            self.directional_input = replace(self.directional_input,
                                             **{'right' if direction > 0 else 'left': -1})
            self.update_waiting_controls()

    def update_waiting_controls(self, *, repeat=True):
        state = self.sequence_state
        if state.sequence_id not in RUN_INPUT_SEQUENCES:
            self.run_vertical_followup = False
            return super().update_waiting_controls(repeat=repeat)
        if not self.waiting_controls_available():
            return False
        self.sample_waiting_controls()
        if getattr(self, 'running_key_callback', False):
            return False
        if state.cursor == 0:
            return False
        facing = bool(state.facing)
        relative = self.directional_input.remap(facing_right=facing)
        vertical = getattr(self, 'run_vertical_followup', False) and not relative.left and not relative.right
        if vertical and 4 <= state.action <= 14 and state.action not in (7, 11):
            return False
        relative, request = running_input_request(
            relative, state.action, mode=state.animation_state, sequence=state.sequence_id)
        if vertical and request == 'brake':
            relative = replace(relative, up=-1)
        self.directional_input = relative.remap(facing_right=facing)
        self.modifier_input = relative.modifier
        if request is None:
            return False
        from pop2.scene_prototype import BufferedCommand
        direction = 1 if facing else -1
        if request == 'brake':
            self.run_active = self.run_stop_requested = False
            self.run_direction = 0
            self.start_sequence(RUN_STOP_SEQUENCE)
        elif request == 'reverse':
            self.start_running_drift(-direction)
            self.run_stop_requested = self.horizontal_input != -direction
        elif request in ('forward_jump', 'running_jump'):
            return self.dispatch_jump(BufferedCommand('jump', direction, running=request == 'running_jump'))
        elif request == 'running_crouch':
            self.start_crouch_lower()
        return True

    def clear_waiting_controls(self):
        super().clear_waiting_controls()
        self.run_vertical_followup = False
        self.run_repeat_up = False
