from dataclasses import dataclass, replace


@dataclass(frozen=True)
class DirectionalInput:
    """4:3e84: four independent latches in keyboard coordinates, plus modifier."""

    left: int = 0
    right: int = 0
    up: int = 0
    down: int = 0
    modifier: int = 0

    def sample(self, horizontal=0, vertical=0, modifier=0):
        if horizontal not in (-1, 0, 1) or vertical not in (-1, 0, 1):
            raise ValueError('Invalid raw direction')
        if modifier not in (-2, -1, 0):
            raise ValueError('Invalid raw modifier')

        def latch(value, active):
            if value < 0:
                return value
            return (-1 if value == 0 else value) if active else 0

        return DirectionalInput(latch(self.left, horizontal == -1),
                                latch(self.right, horizontal == 1),
                                latch(self.up, vertical == -1),
                                latch(self.down, vertical == 1),
                                -modifier if modifier and self.modifier == -modifier else modifier)

    def clear_directions(self):
        return DirectionalInput(modifier=self.modifier)

    def remap(self, *, facing_right, inverted=False):
        return DirectionalInput(self.right if facing_right else self.left,
                                self.left if facing_right else self.right,
                                self.down if inverted else self.up,
                                self.up if inverted else self.down, self.modifier)

    def consume(self, *directions, modifier=None, clear=False):
        if not set(directions) <= {'left', 'right', 'up', 'down'}:
            raise ValueError('Invalid direction to consume')
        if modifier is not None and modifier not in (1, 2):
            raise ValueError('Invalid consumed modifier')
        changes = {direction: 1 for direction in directions}
        if modifier is not None:
            changes['modifier'] = modifier
        return replace(self.clear_directions() if clear else self, **changes)

    def words(self):
        return self.left, self.right, self.up, self.down, self.modifier


def standing_input_request(bank, pose, *, mode=0, sequence=2, sword=True):
    """GenCtrl standing/turn gates; bank.left/right mean Forward/Backward here."""
    if mode in (4, 5, 9) or sequence in (27, 110):
        return bank.clear_directions(), None
    forward, backward, up, down, modifier = bank.words()
    if 45 <= pose <= 49:
        if pose == 48 and modifier >= 0 and forward and not up and not down:
            return bank, 'turn_run'
        return bank, None
    if pose != 15 and not 50 <= pose <= 52:
        return bank, None
    if sword and modifier == -2 and not any((forward, backward, up, down)):
        return bank.consume(modifier=2, clear=True), 'draw'
    if modifier in (-1, 1):
        if backward < 0:
            return bank, 'turn'
        if up < 0:
            return bank, 'up'
        if down < 0:
            return bank, 'down'
        if forward < 0 and not up and not down:
            return bank, 'step'
        if forward:
            return bank, None
    if forward < 0:
        return bank, 'forward_jump' if up < 0 else 'run'
    if backward < 0:
        return bank, 'turn'
    if up < 0:
        return bank, 'up'
    if down < 0:
        return bank, 'down'
    return bank, 'run' if forward else None


def low_input_request(bank, pose, *, mode=1, selected=117, can_rise=True,
                      low_ahead=False, inside_low=True, can_stand_prone=False):
    """GenCtrl6:0576/099a/07ee at supplied terrain/pickup boundaries.

    Latches are facing-relative. Requests are original sequence IDs; existing
    terrain/action code performs alignment and checks pickup/carpet first.
    """
    if mode in (4, 5, 9) or selected in (27, 110):
        return bank.clear_directions(), None
    if pose == 109:
        if selected == 111:
            return bank.consume(clear=True, modifier=1), None
        if not bank.down:
            return bank, 49 if can_rise else 79 if bank.left < 0 else None
        if bank.left < 0:
            return bank.consume('left', clear=True), 125 if low_ahead else 79
        return bank.consume('down', clear=True), None
    if 246 <= pose <= 261:
        if not inside_low and selected != 124:
            return bank, 124
        if pose != 251:
            return bank.clear_directions(), None
        if bank.up and can_stand_prone:
            return bank.consume('up', clear=True), 124
        if selected != 124:
            sequence = 122 if bank.left < 0 else 123 if bank.right < 0 else None
            if sequence is not None:
                return bank.clear_directions(), sequence
    return bank, None


def ledge_input_request(bank, *, grip=0, alive=True, sequence_mode=0):
    """GenCtrl6:18e0-191e, before the separate terrain/support decisions."""
    if not alive:
        return 'release'
    if grip == 0 and bank.up:
        return 'climb'
    if not bank.modifier or sequence_mode == 11:
        return 'release'
    return None


def vertical_input_request(bank, pose, *, mode=1):
    """GenCtrl6:0576-059c/064c-0660; bank.left is facing-relative Forward."""
    if mode in (4, 5, 9):
        return bank.clear_directions(), None
    # 6:15de accepts active Forward, including a consumed hold. Up need
    # not be pressed again during the first three vertical preparation poses.
    return bank, 'forward_jump' if 67 <= pose <= 69 and bank.left else None


def running_input_request(bank, pose, *, mode=0, sequence=201):
    """GenCtrl 6:15b6 and 11e4-1274; facing-relative bank, geometry deferred."""
    if mode in (4, 5, 9) or sequence in (27, 110):
        return bank.clear_directions(), None
    if 1 <= pose <= 3:
        if bank.left < 0 and bank.up < 0:
            return bank.consume('left', 'up', clear=True), 'forward_jump'
        return bank, None
    if not 4 <= pose <= 14:
        return bank, None
    if not bank.left and not bank.right and pose in (7, 11):
        result, request = bank.consume('left', clear=True), 'brake'
    elif bank.right:
        result, request = bank.consume('right', clear=True), 'reverse'
    elif bank.up:
        result, request = bank, 'running_jump' if bank.up < 0 else None
    elif bank.down < 0:
        result, request = bank.consume('down', clear=True), 'running_crouch'
    else:
        result, request = bank, None
    if result.left < 0:
        result = result.consume('left')
    return result, request


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


def sample_modifier(previous, shift, ctrl):
    """4:3f08-3f42: Shift wins; release cancels; consumed holds stay consumed."""
    raw = -1 if shift else (-2 if ctrl else 0)
    return -raw if raw and previous == -raw else raw


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
