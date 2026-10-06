from dataclasses import dataclass


@dataclass(frozen=True)
class KeyboardFrame:
    horizontal: int
    vertical: int
    shift: bool


@dataclass(frozen=True)
class StepPlan:
    sequence_id: int | None
    pre_offset: int


@dataclass(frozen=True)
class StepBoundary:
    clearance: int
    barrier_type: int = 0
    tile_kind: int = 1


def plan_cautious_step(boundary, cautious):
    # DoStepFwd (6:12fc-1324): a warning clears afc2; the next attempt
    # deliberately takes SEQS:42. Solid barriers do not get this warning.
    step = plan_step(boundary.clearance)
    if step is not None:
        return step, True
    warn = cautious and (boundary.barrier_type != 1 or boundary.tile_kind in (12, 13))
    return StepPlan(44 if warn else 42, 0), False if warn else cautious


def read_keyboard(held_directions, up_held, down_held, shift_held):
    # CODE:2 ReadKeyboard checks Up before Down and Left before Right.
    horizontal = -1 if -1 in held_directions else (1 if 1 in held_directions else 0)
    vertical = -1 if up_held else (1 if down_held else 0)
    return KeyboardFrame(horizontal, vertical, shift_held)


def plan_step(clearance):
    # CODE:6 DoStepFwd at 0x1276: reserve four pixels, then use SEQS:29-42.
    available = clearance - 4
    if available <= 0:
        return None
    if available >= 42:
        return StepPlan(42, 0)
    sequence_id = 28 + available // 3 if available >= 3 else None
    return StepPlan(sequence_id, available % 3)
