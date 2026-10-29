"""Carry the directional bank through crouch, rise and prone movement."""

from dataclasses import replace

from pop2.control_mapping import LEDGE_CLIMB_SEQUENCE
from pop2.coordinates import column_left
from pop2.crevices import CREVICE_TILE
from pop2.ledge_controls import LedgeControls
from pop2.mac_input import DirectionalInput, low_input_request
from pop2.opponent_generation import character_column


LOW_INPUT_SEQUENCES = frozenset((17, 26, 49, 50, 79, 117, 121, 122, 123, 124, 125))


class LowControls(LedgeControls):
    def waiting_sequence(self, sequence):
        return sequence in LOW_INPUT_SEQUENCES or super().waiting_sequence(sequence)

    def low_controls_available(self):
        state, motion = self.sequence_state, getattr(self, 'terrain_motion', None)
        return (state.sequence_id in LOW_INPUT_SEQUENCES and not self.native_ledge
                and state.source_sequence_id != LEDGE_CLIMB_SEQUENCE
                and not self.ledge_hanging and not self.sword_drawn and not self.sword_sheathing
                and not self._combat_controls_locked() and not self._opening_active()
                and not (motion is not None and (motion.falling or motion.sinking or motion.dead)))

    def waiting_controls_available(self):
        if (self.sequence_state.sequence_id in LOW_INPUT_SEQUENCES
                and self.sequence_state.source_sequence_id == LEDGE_CLIMB_SEQUENCE):
            return False
        if self.low_controls_available():
            if getattr(self, 'directional_input', None) is None:
                self.directional_input = DirectionalInput()
                self.sample_waiting_controls()
            return True
        return super().waiting_controls_available()

    def begin_low_controls(self, sequence):
        # The existing SEQS46 wall/climb recovery links through49 too.
        # Its separate vertical-request tolerance retains the old owner.
        if (self.native_ledge or self.ledge_hanging or self.ledge_climbing
                or self.sequence_state.source_sequence_id == LEDGE_CLIMB_SEQUENCE):
            return
        if getattr(self, 'directional_input', None) is None:
            self.directional_input = DirectionalInput()
        self.sample_waiting_controls()
        self.waiting_step_direction = 0
        self.low_polled_this_tick = False
        if sequence == 79:
            self.low_step_direction = 1 if self.sequence_state.facing else -1
            self.low_inherited_down = self.down_held
        elif sequence in (26, 49, 50):
            self.low_step_direction = 0
            self.low_inherited_down = False
        if sequence in (26, 50):
            # Crouch6:1068/DoRunCrouch: the accepted Down is consumed.
            self.directional_input = self.directional_input.consume('down', clear=True)
            self.pending_action = None

    def waiting_key(self, key, pressed):
        if not self.low_controls_available():
            return super().waiting_key(key, pressed)
        if key not in ('up', 'down', 'shift', 'ctrl'):
            return False
        self.waiting_controls_available()
        fresh = pressed and not getattr(self, key + '_held')
        setattr(self, key + '_held', pressed)
        self.sample_waiting_controls()
        if key == 'down':
            if fresh:
                self.low_inherited_down = False
            elif not pressed and getattr(self, 'low_inherited_down', False):
                # Retained low-step release policy: an inherited Down hold
                # may cancel before109; a new released Down tap stays pending.
                self.directional_input = replace(self.directional_input, down=0)
                self.low_inherited_down = False
        if key == 'up':
            self.jump_started_for_press = pressed
        elif key == 'down' and not pressed:
            self.down_sheathe_consumed = False
        if key == 'ctrl' and fresh:
            self.pending_potion_pickup = None
        if key in ('shift', 'down'):
            self.update_ledge_test_state()
            if not self.low_controls_available():
                return True
        # Match the existing immediate low-step callback; protected resets
        # and all prone dispatch remain at the simulation boundary.
        return True

    def waiting_horizontal(self, direction, pressed):
        if not self.low_controls_available():
            return super().waiting_horizontal(direction, pressed)
        self.waiting_controls_available()
        self.sample_waiting_controls()
        command = getattr(self, 'queue_grace_command', None)
        if (pressed and self.sequence_state.sequence_id == 79
                and getattr(self, 'queue_grace_remaining_ms', 0) > 0
                and command is not None and command.kind == 'crawl' and command.direction == direction):
            # Existing rapid-repeat tolerance, scoped to the same low step.
            self.directional_input = self.directional_input.consume('right' if direction > 0 else 'left')
        return self.update_low_controls(callback=True)

    def update_waiting_controls(self, *, repeat=True):
        if self.low_controls_available():
            if self.in_animation_tick and getattr(self, 'low_polled_this_tick', False):
                return False
            result = self.update_low_controls()
            if self.in_animation_tick:
                self.low_polled_this_tick = True
            return result
        return super().update_waiting_controls(repeat=repeat)

    def prone_geometry(self):
        """Existing crawl-cell/stand-clearance geometry, independent of latches."""
        if getattr(self, 'terrain_motion', None) is None:
            return True, -1
        state = self.sequence_state
        _, own = self.crawl_cell(0)
        _, ahead = self.crawl_cell(1)
        _, behind = self.crawl_cell(-1)
        low = (CREVICE_TILE, 12, 13)
        inside = any(tile.kind in low for tile in (own, ahead, behind))
        if own.kind == CREVICE_TILE:
            return inside, -1
        column = character_column(state.target_x)
        if behind.kind == CREVICE_TILE:
            clearance = (state.target_x - column_left(column) - 58 if state.facing else
                         -14 - (state.target_x - column_left(column + 1)))
        elif behind.kind in (12, 13):
            clearance = -51 if 3 <= behind.foreground & 0x1f <= 15 else 51
        else:
            clearance = 51
        return inside, clearance

    def update_low_controls(self, *, callback=False):
        if not self.low_controls_available():
            return False
        self.waiting_controls_available()
        state = self.sequence_state
        self.sample_waiting_controls()
        command = self.pending_action
        if command is not None:
            if command.kind not in ('horizontal', 'jump', 'crouch', 'crawl'):
                return False
            self.latch_waiting_command(command)
            self.pending_action = None
        if state.cursor == 0:
            return False
        if callback and (state.action != 109 or state.animation_state in (4, 5, 9)):
            return False
        inside, clearance = (self.prone_geometry() if 246 <= state.action <= 261 else (True, -1))
        ahead_low = False
        if state.action == 109 and getattr(self, 'terrain_motion', None) is not None:
            _, ahead = self.crawl_cell(1)
            ahead_low = ahead.kind in (12, 13) or ahead.kind == CREVICE_TILE and ahead.foreground & 3 != 3
        facing = bool(state.facing)
        relative = self.directional_input.remap(facing_right=facing)
        if (state.sequence_id == 117 and state.action == 109 and relative.down and relative.left >= 0
                and self.horizontal_input == getattr(self, 'low_step_direction', 0)
                and self.horizontal_input):
            # Retained held-low-step repeat: start the next complete step at
            #109, without inserting another stationary frame to rearm Forward.
            relative = replace(relative, left=-1)
        relative, sequence = low_input_request(
            relative, state.action,
            mode=state.animation_state, selected=state.selected_sequence_id,
            can_rise=not self.gate_blocks_crouch_rise(), low_ahead=ahead_low,
            inside_low=inside, can_stand_prone=clearance >= 0)
        self.directional_input = relative.remap(facing_right=facing)
        self.modifier_input = relative.modifier
        if sequence is None:
            return False
        if sequence == 125:
            self.start_crawl(down_active=True)
        elif sequence == 79:
            self.start_crouch_step(1 if facing else -1, try_crawl=False)
        elif sequence == 49:
            self.start_crouch_rise()
        else:
            self.start_sequence(sequence)
            if sequence == 124 and inside and 0 <= clearance < 9:
                state.target_x += (9 - clearance) * (1 if facing else -1)
                state.current_x = self.player_x = state.target_x
        return True

    def update_crawl(self):
        return 246 <= self.sequence_state.action <= 261 and self.update_waiting_controls()

    def resume_crouch(self):
        return self.sequence_state.action == 109 and self.update_waiting_controls()

    def clear_waiting_controls(self):
        super().clear_waiting_controls()
        self.low_polled_this_tick = False
        self.low_step_direction = 0
        self.low_inherited_down = False

    def retire_waiting_controls(self):
        super().retire_waiting_controls()
        self.low_polled_this_tick = False
        if self.sequence_state.sequence_id not in LOW_INPUT_SEQUENCES:
            self.low_step_direction = 0
