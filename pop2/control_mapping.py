IDLE_SEQUENCE = 2
RUN_START_SEQUENCE = 1
SHIFT_STEP_SEQUENCE = 42
RUN_STOP_SEQUENCE = 13
RUN_CYCLE_SEQUENCE = 201
STANDING_TURN_SEQUENCE = 5
RUNNING_DRIFT_SEQUENCE = 6
RUNNING_TURN_SEQUENCE = 43
JUMP_FORWARD_SEQUENCE = 3
JUMP_VERTICAL_SEQUENCE = 28
RUN_JUMP_SEQUENCE = 4
CROUCH_LOWER_SEQUENCE = 26
CROUCH_STANDING_LOWER_SEQUENCE = 50
CROUCH_HOLD_SEQUENCE = 117
CROUCH_STEP_SEQUENCE = 79
CROUCH_RISE_SEQUENCE = 49
LEDGE_APPROACH_SEQUENCE = 7
LEDGE_FALL_SEQUENCE = 214
LEDGE_HANG_SEQUENCE = 12
LEDGE_CLIMB_SEQUENCE = 46
SWORD_DRAW_SEQUENCE = 55
SWORD_ADVANCE_SEQUENCE = 56
SWORD_RETREAT_SEQUENCE = 57
SWORD_GUARD_SEQUENCE = 227
SWORD_ATTACK_SEQUENCE = 75
SWORD_BLOCK_SEQUENCE = 62
SWORD_BLOCK_ATTACK_SEQUENCE = 66
SWORD_SHEATHE_SEQUENCE = 92


def facing_for_direction(direction):
    """Map screen direction to the original Kid sprite orientation."""
    if direction not in (-1, 1):
        raise ValueError("Direction must be -1 (left) or 1 (right)")
    return 0 if direction < 0 else 1


def movement_sequence_for_key(
    direction, facing, running=False, shift_pressed=False
):
    """Select a source SEQS resource for an immediate horizontal key press."""
    if direction not in (-1, 1):
        raise ValueError("Direction must be -1 (left) or 1 (right)")
    if facing not in (0, 1):
        raise ValueError("Facing must be 0 (left) or 1 (right)")

    requested_facing = facing_for_direction(direction)
    if shift_pressed:
        return SHIFT_STEP_SEQUENCE
    if running and requested_facing != facing:
        return RUNNING_DRIFT_SEQUENCE
    return RUN_CYCLE_SEQUENCE if running else RUN_START_SEQUENCE


def jump_sequence_for_input(horizontal_direction, facing, running=False):
    """Select a jump after opposite-direction input has been resolved as a turn."""
    if horizontal_direction not in (-1, 0, 1):
        raise ValueError("Horizontal direction must be -1, 0, or 1")
    if facing not in (0, 1):
        raise ValueError("Facing must be 0 (left) or 1 (right)")
    if horizontal_direction and facing_for_direction(horizontal_direction) != facing:
        raise ValueError("Opposite-direction input must turn before jumping")
    if running and horizontal_direction:
        return RUN_JUMP_SEQUENCE
    if horizontal_direction == 0:
        return JUMP_VERTICAL_SEQUENCE
    return JUMP_FORWARD_SEQUENCE
