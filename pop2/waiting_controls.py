"""Directional-bank ownership while turning/stepping and at their ready gate.

Other controller families retain their existing host policies during migration.
The bank stays in keyboard coordinates; facing is applied only at dispatch.
"""

from dataclasses import replace

from pop2.control_mapping import IDLE_SEQUENCE, RUN_STOP_SEQUENCE, STANDING_TURN_SEQUENCE
from pop2.mac_input import DirectionalInput, read_keyboard, standing_input_request


class WaitingControls:
    @staticmethod
    def waiting_sequence(sequence):
        return sequence in (IDLE_SEQUENCE, STANDING_TURN_SEQUENCE, RUN_STOP_SEQUENCE, 44) or 29 <= sequence <= 42

    def ensure_run_stop_controls(self):
        """Own a brake that began without a bank (a scripted SEQS 13 start).

        Its poses 50-52 reach GenCtrl's standing gate (6:05fe-0618), so the
        presses there are bank requests. Keys already held count as consumed;
        call this before a key callback changes the held state.
        """
        if (getattr(self, 'directional_input', None) is not None
                or self.sequence_state.sequence_id != RUN_STOP_SEQUENCE):
            return
        frame = read_keyboard(self.held_directions, self.up_held, self.down_held, self.shift_held)
        bank = DirectionalInput().sample(frame.horizontal, frame.vertical)
        held = [name for name, word in zip(('left', 'right', 'up', 'down'), bank.words()) if word]
        modifier = 1 if self.shift_held else 2 if self.ctrl_held else None
        self.directional_input = bank.consume(*held, modifier=modifier)
        self.waiting_step_direction = 0
        if not self.waiting_controls_available():
            self.directional_input = None

    def waiting_controls_available(self):
        self.ensure_run_stop_controls()
        state = self.sequence_state
        motion = getattr(self, 'terrain_motion', None)
        return (getattr(self, 'directional_input', None) is not None
                and self.waiting_sequence(state.sequence_id)
                and not self.sword_drawn and not self.sword_sheathing
                and not self.ledge_hanging and not self.native_ledge
                and not self._combat_controls_locked() and not self._opening_active()
                and not (motion is not None and (motion.falling or motion.sinking or motion.dead)))

    def begin_waiting_controls(self, direction, *, turning=False):
        owned = self.waiting_controls_available()
        bank = self.directional_input if owned else DirectionalInput()
        frame = self.sample_keyboard()
        bank = bank.sample(frame.horizontal, frame.vertical,
                           -1 if self.shift_held else -2 if self.ctrl_held else 0)
        # DoTurn clears all directions and consumes Backward. DoStepFwd
        # consumes Forward/modifier without clearing other pending directions.
        self.directional_input = bank.consume('right' if direction > 0 else 'left',
                                               clear=turning, modifier=None if turning else 1)
        self.waiting_step_direction = 0 if turning else direction
        if turning:
            # Retained host chord policy: an opposite jump chord turns once;
            # holding its Up does not create an additional jump after the turn.
            self.waiting_suppressed_up = self.up_held
        self.pending_action = None

    def sample_waiting_controls(self):
        frame = self.sample_keyboard()
        if not self.up_held:
            self.waiting_suppressed_up = False
        vertical = frame.vertical
        if vertical == -1 and getattr(self, 'waiting_suppressed_up', False):
            vertical = 0
        self.directional_input = self.directional_input.sample(
            frame.horizontal, vertical, -1 if self.shift_held else -2 if self.ctrl_held else 0)
        self.modifier_input = self.directional_input.modifier

    def waiting_key(self, key, pressed):
        if key not in ('up', 'down', 'shift', 'ctrl') or not self.waiting_controls_available():
            return False
        previous = getattr(self, key + '_held')
        release_suppressed_up = key == 'up' and not pressed and getattr(self, 'waiting_suppressed_up', False)
        setattr(self, key + '_held', pressed)
        if key == 'ctrl' and pressed and not previous:
            self.pending_potion_pickup = None
        if key == 'up' and not pressed:
            self.jump_started_for_press = False
        elif (key == 'up' and pressed and not previous
              and self.sequence_state.sequence_id == STANDING_TURN_SEQUENCE
              and self.sequence_state.action == 45 and self.horizontal_input):
            self.waiting_suppressed_up = True
        if key == 'down' and not pressed:
            self.down_sheathe_consumed = False
        if key == 'shift' and pressed and not previous:
            self.queue_potion_pickup()
        if key in ('shift', 'down'):
            self.update_ledge_test_state()
        if release_suppressed_up:
            self.sample_waiting_controls()
            return True
        if (key == 'up' and pressed and not previous and self._is_resting()
                and not self.horizontal_input):
            # Keep the existing host chord window at rest/ready poses.
            self.sample_waiting_controls()
            self.root.after(35, self.start_jump_if_needed)
            return True
        self.update_waiting_controls()
        return True

    def waiting_horizontal(self, direction, pressed):
        self.sample_waiting_controls()
        command = getattr(self, 'queue_grace_command', None)
        if (pressed and getattr(self, 'waiting_step_direction', 0) and self.shift_held
                and getattr(self, 'queue_grace_remaining_ms', 0) > 0
                and command is not None and command.kind == 'horizontal'
                and command.mode == 'step' and command.direction == direction):
            # Existing rapid-step repeat policy; other pending directions stay.
            self.directional_input = self.directional_input.consume('right' if direction > 0 else 'left')
        return self.update_waiting_controls()

    def latch_waiting_command(self, command):
        """Bridge an internal directional producer without creating a second slot."""
        self.sample_waiting_controls()
        changes = {}
        if command.direction:
            changes['right' if command.direction > 0 else 'left'] = -1
        if command.kind == 'jump':
            changes['up'] = -1
        elif command.kind == 'crouch':
            changes['down'] = -1
        self.directional_input = replace(self.directional_input, **changes)

    def update_waiting_controls(self, *, repeat=True):
        if not self.waiting_controls_available():
            return False
        from pop2.scene_prototype import BufferedCommand

        self.sample_waiting_controls()
        state = self.sequence_state
        direction = getattr(self, 'waiting_step_direction', 0)
        if (repeat and state.sequence_id == IDLE_SEQUENCE and direction and self.shift_held
                and self.horizontal_input == direction
                and not any(value < 0 for value in self.directional_input.words()[:4])):
            # Retained held-step repeat, only after the previous step ends.
            self.directional_input = replace(self.directional_input,
                                             **{'right' if direction > 0 else 'left': -1})
        # Import a scripted/test request at this boundary once. Actual key
        # callbacks use the bank directly and never write the old slot here.
        queued = self.pending_action
        if queued is not None:
            if queued.kind not in ('horizontal', 'jump', 'crouch', 'crawl'):
                return False
            self.latch_waiting_command(queued)
            self.pending_action = None
        state = self.sequence_state
        facing = bool(state.facing)
        relative = self.directional_input.remap(facing_right=facing)
        if state.cursor == 0 and state.sequence_id != IDLE_SEQUENCE:
            # JumpSeq leaves the previous displayed action in place. Do not
            # run its ready gate again before loading the selected first pose.
            # Preserve the host's initial forward chord window when an arrow
            # selected an automatic near-wall step before Up arrived.
            early_chord = (getattr(self, 'waiting_step_direction', 0)
                           and not self.shift_held and relative.up < 0 and relative.left
                           and (state.action == 15 or 50 <= state.action <= 52))
            if not early_chord:
                return False
        relative, request = standing_input_request(
            relative, state.action, mode=state.animation_state,
            sequence=state.sequence_id, sword=not self.sword_lost())
        self.directional_input = relative.remap(facing_right=facing)
        if getattr(self, 'waiting_suppressed_up', False) and self.up_held:
            return False
        if request is None:
            return False
        direction = 1 if facing else -1
        if request in ('turn', 'run'):
            relative = relative.consume('right' if request == 'turn' else 'left', clear=True)
        elif request == 'step':
            relative = relative.consume('left', modifier=1)
        elif request == 'forward_jump' or request == 'up' and relative.left:
            relative = relative.consume('left', 'up')
        elif request == 'up':
            relative = relative.consume('up', clear=True)
        elif request == 'down':
            relative = relative.consume('down', clear=True)
        self.directional_input = relative.remap(facing_right=facing)
        self.modifier_input = relative.modifier
        if request == 'turn_run':
            self.start_running_turn(direction)
        elif request in ('turn', 'step', 'run'):
            self.dispatch_horizontal_action(BufferedCommand(
                'horizontal', -direction if request == 'turn' else direction, request))
        elif request in ('up', 'forward_jump'):
            self.jump_started_for_press = True
            self.dispatch_jump(BufferedCommand('jump', direction if relative.left else 0))
        elif request == 'down':
            if not (self.start_native_descent() or
                    self.down_held and self.shift_held and self._try_start_ledge_hang()):
                self.start_crouch_lower()
        elif request == 'draw':
            self.start_sword_action('sword_draw')
        return True

    def clear_waiting_controls(self):
        self.directional_input = None
        self.waiting_step_direction = 0
        self.waiting_suppressed_up = False

    def retire_waiting_controls(self):
        # Physics/combat can select a sequence directly, bypassing start_sequence.
        # An interrupted step must not resurrect its bank after a later landing.
        if getattr(self, 'directional_input', None) is not None and not self.waiting_controls_available():
            self.clear_waiting_controls()
