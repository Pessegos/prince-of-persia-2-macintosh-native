"""One input bank through native hanging, release and protected climbing.

The input gate is native. Retaining complete tapped commands during the
protected climb is an existing port tolerance, kept in this same bank.
"""

from dataclasses import replace

from pop2.airborne_controls import AirborneControls
from pop2.mac_input import DirectionalInput, ledge_input_request


class LedgeControls(AirborneControls):
    def waiting_sequence(self, sequence):
        return getattr(self, 'native_ledge', False) or super().waiting_sequence(sequence)

    def waiting_controls_available(self):
        if not getattr(self, 'native_ledge', False):
            return super().waiting_controls_available()
        motion = getattr(self, 'terrain_motion', None)
        if (self.sword_drawn or self.sword_sheathing or self._combat_controls_locked()
                or self._opening_active()
                or motion is not None and (motion.dead or motion.falling or motion.sinking)):
            return False
        if getattr(self, 'directional_input', None) is None:
            self.directional_input = DirectionalInput()
            self.sample_waiting_controls()
            if self.ledge_climbing:
                self.directional_input = self.directional_input.consume('up', clear=True, modifier=1)
            elif self.up_held:
                # Physics can clear the bank on the same tick as a catch
                # beside a wall/gate. Re-adopt held Up as consumed, so its
                # release still cancels the inherited takeoff hold.
                self.directional_input = self.directional_input.consume('up')
        return True

    def begin_ledge_controls(self, sequence):
        if getattr(self, 'directional_input', None) is None:
            self.directional_input = DirectionalInput()
        self.waiting_suppressed_up = False
        self.sample_waiting_controls()
        # Entry keeps the existing port's discard of pre-catch commands.
        # Up/descent entries have the already recovered action consumption.
        # A takeoff Up still held at catch is an inherited hold, not a fresh
        # released climb tap. Releasing it during grip must cancel that hold.
        direction = (() if sequence == 15 and not self.up_held
                     else ('down',) if sequence == 68 else ('up',))
        self.directional_input = self.directional_input.consume(*direction, clear=True)
        self.waiting_step_direction = self.ledge_jump_chord_direction = 0

    def consume_ledge_input(self, action):
        self.waiting_controls_available()
        self.sample_waiting_controls()
        self.directional_input = (self.directional_input.consume('up', clear=True, modifier=1)
                                  if action == 'climb' else self.directional_input.consume('down', clear=True))
        self.modifier_input = self.directional_input.modifier
        self.ledge_jump_chord_direction = 0

    def waiting_key(self, key, pressed):
        if not getattr(self, 'native_ledge', False) or not self.waiting_controls_available():
            if key == 'up' and not pressed and getattr(self, 'ledge_auto_repeat', False):
                self.directional_input = replace(self.directional_input, up=0)
                self.ledge_auto_repeat = self.ledge_repeat_after_tick = False
            return super().waiting_key(key, pressed)
        if key not in ('up', 'down', 'shift', 'ctrl'):
            return False
        fresh = pressed and not getattr(self, key + '_held')
        setattr(self, key + '_held', pressed)
        self.sample_waiting_controls()
        if key == 'up':
            self.jump_started_for_press = pressed
            if fresh and self.ledge_climbing and self.horizontal_input:
                self.ledge_jump_chord_direction = self.horizontal_input
        elif key == 'down' and not pressed:
            self.down_sheathe_consumed = False
        return True

    def waiting_horizontal(self, direction, pressed):
        if not getattr(self, 'native_ledge', False):
            return super().waiting_horizontal(direction, pressed)
        self.sample_waiting_controls()
        if pressed and self.ledge_climbing and self.up_held:
            # Retained protected-climb chord tolerance, including a complete
            # released tap. Holding only Forward at completion instead runs.
            self.directional_input = replace(self.directional_input, up=-1)
            self.ledge_jump_chord_direction = self.horizontal_input
        return False

    def latch_waiting_command(self, command):
        super().latch_waiting_command(command)
        if (getattr(self, 'native_ledge', False) and self.ledge_climbing
                and command.kind == 'jump' and command.direction):
            self.ledge_jump_chord_direction = command.direction

    def update_waiting_controls(self, *, repeat=True):
        if getattr(self, 'native_ledge', False):
            if self.waiting_controls_available():
                self.sample_waiting_controls()
            return False
        if getattr(self, 'ledge_repeat_after_tick', False):
            return False
        if getattr(self, 'ledge_auto_repeat', False):
            if not self.up_held:
                self.directional_input = replace(self.directional_input, up=0)
            self.ledge_auto_repeat = False
        return super().update_waiting_controls(repeat=repeat)

    def native_ledge_request(self):
        if not self.waiting_controls_available():
            return None
        self.sample_waiting_controls()
        player = getattr(getattr(self, 'combat', None), 'player', None)
        alive = (True if player is None else player.alive if player.native_alive is None else player.native_alive)
        return ledge_input_request(self.directional_input, grip=self.ledge_grip_delay,
                                   alive=alive, sequence_mode=self.sequence_state.sequence_mode)

    def finish_native_ledge_controls(self):
        self.waiting_controls_available()
        self.sample_waiting_controls()
        chord = getattr(self, 'ledge_jump_chord_direction', 0)
        if chord and self.horizontal_input == chord and not self.up_held:
            self.directional_input = replace(self.directional_input, up=0)
        elif self.up_held and self.directional_input.up >= 0:
            # Keep the existing host's completion pose before automatic held
            # repetition. Fresh tapped requests still dispatch at completion.
            self.ledge_auto_repeat = self.ledge_repeat_after_tick = True
        if self.shift_held and self.directional_input.remap(facing_right=bool(self.sequence_state.facing)).right < 0:
            # Retained Shift+Backward policy: complete one turn, without a
            # run at48 from the modifier consumed by the preceding climb.
            self.directional_input = replace(self.directional_input, modifier=-1)
        self.ledge_jump_chord_direction = 0

    def clear_waiting_controls(self):
        super().clear_waiting_controls()
        self.ledge_jump_chord_direction = 0
        self.ledge_auto_repeat = self.ledge_repeat_after_tick = False

    def retire_waiting_controls(self):
        super().retire_waiting_controls()
        if getattr(self, 'ledge_repeat_after_tick', False):
            if self.directional_input is not None and self.up_held:
                self.directional_input = replace(self.directional_input, up=-1)
            self.ledge_repeat_after_tick = False
