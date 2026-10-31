"""One input bank through native hanging, release and climbing.

The climb (SEQS 10 -> 235) is mode 1 except pose 149, which is mode 5:
GenCtrl's gate (6:0576-059c) clears every direction there, so taps made
earlier in the climb are discarded and keys still held are fresh requests
at the next sample, admitted at the standing gate after 119.
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
        # Up/descent entries have the already recovered action consumption.
        # A takeoff Up still held at catch is an inherited hold, not a fresh
        # released climb tap. Releasing it during grip must cancel that hold.
        direction = (() if sequence == 15 and not self.up_held
                     else ('down',) if sequence == 68 else ('up',))
        self.directional_input = self.directional_input.consume(*direction, clear=True)
        if sequence == 15 and getattr(self, 'fall_pending_up', False):
            # Catch 4:37ca, SEQS 15 (mode 3) and 9/210 (mode 2) clear
            # nothing: an Up pressed at the fall's mode-3 poses is still
            # pending and climbs once the grip delay ends, even if released.
            self.directional_input = replace(self.directional_input, up=-1)
        self.fall_pending_up = False
        self.waiting_step_direction = 0

    def consume_ledge_input(self, action):
        self.waiting_controls_available()
        self.sample_waiting_controls()
        self.directional_input = (self.directional_input.consume('up', clear=True, modifier=1)
                                  if action == 'climb' else self.directional_input.consume('down', clear=True))
        self.modifier_input = self.directional_input.modifier

    def latch_fall_key(self, key, pressed):
        """Fall poses 102-105 are mode 3: GenCtrl has no branch for them and
        only modes 4/5 reach ClearControls (6:0576-059c), so a fresh Up stays
        pending until the first mode-4 frame or a catch. The port keeps no
        bank in the air; Up is the only latch the hang gate reads."""
        motion = getattr(self, 'terrain_motion', None)
        if (key == 'up' and pressed and not self.up_held and motion is not None
                and motion.falling and self.sequence_state.animation_state == 3):
            self.fall_pending_up = True

    def waiting_key(self, key, pressed):
        if not getattr(self, 'native_ledge', False) or not self.waiting_controls_available():
            return super().waiting_key(key, pressed)
        if key not in ('up', 'down', 'shift', 'ctrl'):
            return False
        setattr(self, key + '_held', pressed)
        self.sample_waiting_controls()
        if key == 'up':
            self.jump_started_for_press = pressed
        elif key == 'down' and not pressed:
            self.down_sheathe_consumed = False
        return True

    def waiting_horizontal(self, direction, pressed):
        if not getattr(self, 'native_ledge', False):
            return super().waiting_horizontal(direction, pressed)
        self.sample_waiting_controls()
        return False

    def update_waiting_controls(self, *, repeat=True):
        if getattr(self, 'native_ledge', False):
            if self.waiting_controls_available():
                self.sample_waiting_controls()
                state = self.sequence_state
                if self.ledge_climbing and state.cursor > 0 and state.animation_state in (4, 5, 9):
                    self.directional_input = self.directional_input.clear_directions()
            return False
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

    def clear_waiting_controls(self):
        super().clear_waiting_controls()
        self.fall_pending_up = False

    def retire_waiting_controls(self):
        super().retire_waiting_controls()
        motion = getattr(self, 'terrain_motion', None)
        if not (motion is not None and motion.falling and self.sequence_state.animation_state == 3):
            # A mode-4 free-fall or mode-5 landing frame clears the latch.
            self.fall_pending_up = False
