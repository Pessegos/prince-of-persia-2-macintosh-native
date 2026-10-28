"""Independent input-consumption model at supplied ordinary terrain boundaries."""

from dataclasses import dataclass

from tools.reference_input_bank import InputBank


def word(value):
    return (value + 32768) % 65536 - 32768


@dataclass(frozen=True)
class ActionResult:
    bank: InputBank
    sequence: int | None
    x: int
    warning: int
    accepted: bool | None = None


def forward_jump(bank, *, x=400, warning=1):
    # 6:15ea sets F/U, without clearing B/D or the modifier.
    return ActionResult(bank.consume('left', 'up'), 3, x, warning)


def step(bank, *, distance=51, barrier=0, tile_kind=1, warning=1,
         x=400, facing_right=True):
    remaining = word(distance - 4)
    sequence = 42
    bank = bank.consume('left', modifier=1)
    if remaining > 0:
        warning = 1
        if remaining < 42:
            sequence = None if remaining < 3 else 28 + remaining // 3
            remainder = remaining % 3
            x = word(x + (remainder if facing_right else -remainder))
    elif warning and (barrier != 1 or tile_kind in (12, 13)):
        warning, sequence = 0, 44
    return ActionResult(bank, sequence, x, warning)


def run(bank, *, distance=51, barrier=0, tile_kind=1, warning=1,
        x=400, facing_right=True):
    result = ActionResult(bank, 1, x, warning)
    if barrier == 1 and distance < 27:
        result = (step(bank, distance=distance, barrier=barrier, tile_kind=tile_kind,
                       warning=warning, x=x, facing_right=facing_right)
                  if bank.left < 0 else ActionResult(bank, None, x, warning))
    return ActionResult(result.bank.consume('left', clear=True), result.sequence,
                        result.x, result.warning)


def turn(bank, *, ahead_kind=1, wall=False, wall_distance=51,
         x=400, facing_right=True, **_ignored):
    # Supplied level5/environment3, type0 and sequence !=71.
    if ahead_kind == 4 and wall and wall_distance < 11:
        delta = word(wall_distance - 11)
        x = word(x + (delta if facing_right else -delta))
    return ActionResult(bank.consume('right', clear=True), 5, x, 1)


def running_jump(bank, *, pose=7, sequence=4, cells=(True, True), gap_distance=0,
                 x=400, facing_right=True, warning=1):
    legal = ((sequence == 4 and 7 <= (pose & 65535) <= 14)
             or (sequence == 100 and pose in (192, 196)))
    if not legal:
        return ActionResult(bank, None, x, warning, False)
    count = 0
    for supported in cells:
        if not supported:
            break
        count += 1
        if count == 2:
            return ActionResult(bank.consume('up', clear=True), sequence, x, warning, True)
    delta = word(gap_distance + count * 51 - (48 if sequence == 4 else 75))
    if not -31 <= delta < 15:
        if delta < 0 and sequence == 4:
            return ActionResult(bank, None, x, warning, False)
        delta = -13
    adjustment = word(delta + 13)
    x = word(x + (adjustment if facing_right else -adjustment))
    return ActionResult(bank.consume('up', clear=True), sequence, x, warning, True)
