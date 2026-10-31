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

    def waiting_key(self, key, pressed):
        running = self.sequence_state.sequence_id in RUN_INPUT_SEQUENCES and self.waiting_controls_available()
        if not running:
            return super().waiting_key(key, pressed)
        fresh = key == 'up' and pressed and not self.up_held
        self.running_key_callback = True
        try:
            handled = super().waiting_key(key, pressed)
        finally:
            self.running_key_callback = False
        if fresh:
            self.jump_started_for_press = True
            self.try_startup_jump_chord()
        return handled

    def waiting_horizontal(self, direction, pressed):
        running = self.sequence_state.sequence_id in RUN_INPUT_SEQUENCES
        if not running:
            return super().waiting_horizontal(direction, pressed)
        # A release creates no request (4:3e84): an Up still pending meets
        # GenCtrl's running gate as it is, a consumed held Up stays consumed.
        self.sample_waiting_controls()
        self.run_stop_requested = self.horizontal_input != self.run_direction
        return False

    def request_running_jump(self):
        self.jump_started_for_press = True
        self.sample_waiting_controls()
        self.directional_input = replace(self.directional_input, up=-1)
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
        # 6:11e4-1274: with no arrow a pending Up takes off as a running jump
        # at any pose but 7/11, where the brake clears it (a held Up is then
        # fresh at the brake's standing gate).
        relative, request = running_input_request(
            relative, state.action, mode=state.animation_state, sequence=state.sequence_id)
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

