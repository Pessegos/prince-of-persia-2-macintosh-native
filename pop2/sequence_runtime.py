from dataclasses import dataclass, field


class UnsupportedSequenceOpcode(ValueError):
    def __init__(self, sequence_id, cursor, opcode):
        super().__init__(
            f"SEQS:{sequence_id} opcode {opcode} at word {cursor} is not implemented"
        )
        self.sequence_id = sequence_id
        self.cursor = cursor
        self.opcode = opcode


@dataclass
class SequenceState:
    sequence_id: int
    cursor: int = 0
    action: int = 0
    current_x: int = 0
    target_x: int = 0
    current_y: int = 0
    facing: int = 0
    animation_state: int = 0
    actor_type: int | None = None
    level_kind: int | None = None
    callback_counter: int = 0
    callback_flag: int = 0
    sound_events: list[int] = field(default_factory=list)
    sequence_events: list[tuple[int, tuple[int, ...]]] = field(default_factory=list)
    sequence_mode: int = 0
    special_flag: int = 0
    engine_counter: int = 0
    horizontal_velocity: int = 0
    vertical_velocity: int = 0


@dataclass(frozen=True)
class SequenceFrame:
    sequence_id: int
    action: int
    current_x: int
    target_x: int
    current_y: int
    animation_state: int


class SequenceRuntime:
    """Interpret the SEQS operations needed by the opening-room controls."""

    def __init__(self, sequences, state, max_operations_per_frame=512):
        self.sequences = sequences
        self.state = state
        self.max_operations_per_frame = max_operations_per_frame

    def _next_word(self):
        sequence = self.sequences.get(self.state.sequence_id)
        if sequence is None:
            raise KeyError(f"Missing SEQS resource {self.state.sequence_id}")
        if self.state.cursor >= len(sequence):
            raise ValueError(
                f"SEQS:{self.state.sequence_id} ended without a sequence transition"
            )
        word = sequence[self.state.cursor]
        self.state.cursor += 1
        return word

    def _next_operand(self, opcode, opcode_cursor):
        try:
            return self._next_word()
        except ValueError as error:
            raise ValueError(
                f"SEQS:{self.state.sequence_id} opcode {opcode} at word "
                f"{opcode_cursor} has no operand"
            ) from error

    def next_frame(self):
        for _ in range(self.max_operations_per_frame):
            opcode_cursor = self.state.cursor
            opcode = self._next_word()

            if opcode >= 0:
                self.state.action = opcode
                return SequenceFrame(
                    self.state.sequence_id,
                    opcode,
                    self.state.current_x,
                    self.state.target_x,
                    self.state.current_y,
                    self.state.animation_state,
                )

            if opcode == -1:
                target_sequence = self._next_operand(opcode, opcode_cursor)
                self.state.sequence_id = target_sequence
                self.state.cursor = 0
            elif opcode == -2:
                self.state.facing = 1 - self.state.facing
            elif opcode == -5:
                delta = self._next_operand(opcode, opcode_cursor)
                self.state.target_x += delta if self.state.facing else -delta
            elif opcode == -6:
                self.state.current_y += self._next_operand(opcode, opcode_cursor)
            elif opcode == -7:
                self.state.animation_state = self._next_operand(opcode, opcode_cursor)
            elif opcode == -8:
                first = self._next_operand(opcode, opcode_cursor)
                second = self._next_operand(opcode, opcode_cursor)
                self.state.sequence_events.append((opcode, (first, second)))
                # AnimChar, CODE:4 0x2cec-0x2d4e: additive, capped fall velocity.
                if (
                    first
                    and self.state.horizontal_velocity < 24
                    and self.state.vertical_velocity < 63
                ):
                    self.state.horizontal_velocity = min(
                        24, self.state.horizontal_velocity + first
                    )
                if second and self.state.vertical_velocity < 63:
                    self.state.vertical_velocity = min(
                        63, self.state.vertical_velocity + second
                    )
            elif opcode == -10:
                callback_id = self._next_operand(opcode, opcode_cursor)
                self.state.sequence_events.append((opcode, (callback_id,)))
            elif opcode == -13:
                self.state.special_flag = -1
            elif opcode == -15:
                callback_id = self._next_operand(opcode, opcode_cursor)
                if callback_id == 0:
                    continue
                if 2 <= callback_id <= 301:
                    # AnimCharTap 4:315c-317e forwards ordinary sound IDs.
                    self.state.sound_events.append(callback_id)
                    continue
                if (
                    callback_id != 1
                    or self.state.actor_type not in (0, 2)
                    or self.state.level_kind is None
                ):
                    raise UnsupportedSequenceOpcode(
                        self.state.sequence_id, opcode_cursor, opcode
                    )
                self.state.callback_counter += 1
                if self.state.level_kind != 1:
                    sound_id = 0x126 + (self.state.callback_counter & 1)
                    self.state.sound_events.append(sound_id)
                # AnimCharTap 0x314e sets the movement flag only for the Prince.
                if self.state.actor_type == 0:
                    self.state.callback_flag = 1
            elif opcode == -18:
                self.state.sequence_mode = 0
            elif opcode == -16:
                # AnimChar 4:2f2c requests the next level, after boarding.
                self.state.sequence_events.append((opcode, ()))
            elif opcode == -19:
                self.state.sequence_events.append((opcode, ()))
            elif opcode == -21:
                self.state.sequence_mode = self._next_operand(opcode, opcode_cursor)
            elif opcode == -23:
                self.state.cursor = max(0, self.state.cursor - 1)
                return SequenceFrame(
                    self.state.sequence_id,
                    self.state.action,
                    self.state.current_x,
                    self.state.target_x,
                    self.state.current_y,
                    self.state.animation_state,
                )
            elif opcode == -4:
                self.state.engine_counter += 1
            elif opcode == -3:
                self.state.engine_counter -= 1
            else:
                raise UnsupportedSequenceOpcode(
                    self.state.sequence_id, opcode_cursor, opcode
                )

        raise RuntimeError("SEQS did not yield an animation action in time")
