"""Independent low/prone input controller at explicit terrain/pickup boundaries."""

from dataclasses import dataclass, replace

from tools.reference_input_actions import word
from tools.reference_input_bank import InputBank


@dataclass(frozen=True)
class LowContext:
    pose: int = 109
    mode: int = 1
    sequence: int = 117
    selected: int = 117
    cursor: int = 4
    level: int = 5
    environment: int = 3
    room: int = 1
    x: int = 400
    facing_right: bool = True
    warning: int = 1
    column: int = 4
    ahead_column: int = 4
    here_kind: int = 1
    ahead_kind: int = 1
    behind_kind: int = 1
    left_kind: int = 1
    foreground: int = 0
    distance: int = 51
    gate_blocked: bool = False
    scythe_blocked: bool = False
    scythes_enabled: bool = False
    pickup: bool = False
    missing_sequences: tuple = ()


@dataclass(frozen=True)
class LowResult:
    bank: InputBank
    x: int
    warning: int
    sequence: int
    selected: int
    cursor: int
    requests: tuple = ()
    pickup_checked: bool = False
    revealed: bool = False
    carpet: bool = False


def select(state, context, sequence):
    changes = dict(requests=state.requests + (sequence,))
    if sequence not in context.missing_sequences:
        changes.update(sequence=sequence, selected=sequence, cursor=0)
    return replace(state, **changes)


def crouched(state, context):
    c = context
    if c.level == 5 and c.room == 3 and c.selected not in (17, 20) and 18 in (c.here_kind, c.left_kind):
        return replace(state, carpet=True)
    if c.selected != 111:
        state = replace(state, pickup_checked=True)
    if c.selected == 111 or c.pickup:
        return replace(state, bank=state.bank.consume(clear=True, modifier=1))
    bank, sequence = state.bank, None
    if not bank.down:
        blocked = c.gate_blocked or c.scythes_enabled and c.scythe_blocked
        sequence = (79 if bank.left < 0 else None) if blocked else 49
    elif bank.left < 0:
        bank = bank.consume('left', clear=True)
        low = c.ahead_kind in (12, 13) or c.ahead_kind == 7 and c.foreground & 3 != 3
        sequence = 125 if low else 79
        if low:
            left = 207 + 51 * c.ahead_column
            if c.facing_right and c.x - left > 10:
                state = replace(state, x=word(left + 10))
            elif not c.facing_right and c.x - (left + 51) < 34:
                state = replace(state, x=word(left + 51 + 34))
    if bank.down:
        bank = bank.consume('down', clear=True)
    state = replace(state, bank=bank)
    return select(state, c, sequence) if sequence is not None else state


def crouch_entry(bank, context):
    """6:1068 ordinary type0 entry; Down's no-gap path reaches the same body."""
    c = context
    state = LowResult(bank, c.x, c.warning, c.sequence, c.selected, c.cursor)
    if c.environment == 4 and c.ahead_kind in (12, 13) and c.distance < 8:
        delta = word(c.distance - 8)
        state = replace(state, x=word(state.x + delta * (1 if c.facing_right else -1)))
    state = select(state, c, 50)
    return replace(state, bank=bank.consume('down', clear=True))


def prone(state, context):
    c = context
    if not 246 <= c.pose <= 261:
        return state
    low = (7, 12, 13)
    if not any(kind in low for kind in (c.here_kind, c.ahead_kind, c.behind_kind)) and c.selected != 124:
        return select(state, c, 124)
    if c.pose != 251:
        return replace(state, bank=state.bank.clear_directions())
    if state.bank.up and c.here_kind != 7:
        if c.behind_kind == 7:
            left = 207 + 51 * c.column
            clearance = (word(word(c.x - left) - 58) if c.facing_right else
                         word(-14 - word(c.x - (left + 51))))
        elif c.behind_kind in (12, 13):
            clearance = -51 if c.scythe_blocked else 51
        else:
            clearance = 51
        if clearance >= 0:
            state = select(state, c, 124)
            state = replace(state, bank=state.bank.consume('up', clear=True))
            if clearance < 9:
                state = replace(state, x=word(state.x + (9 - clearance) * (1 if c.facing_right else -1)))
    if state.selected != 124:
        sequence = 122 if state.bank.left < 0 else 123 if state.bank.right < 0 else None
        if sequence is not None:
            state = replace(state, bank=state.bank.clear_directions())
            state = select(state, c, sequence)
    if not state.bank.left and not state.warning:
        state = replace(state, warning=1)
    return state


def low_control(bank, context, *, controller=True):
    """GenCtrl gates, then 6:099a or 07ee. Pose/mode are supplied context."""
    c = context
    state = LowResult(bank, c.x, c.warning, c.sequence, c.selected, c.cursor)
    if controller and (c.mode in (4, 5, 9) or c.selected in (27, 110)):
        return replace(state, bank=bank.clear_directions())
    if c.pose == 109:
        return crouched(replace(state, revealed=c.environment == 4), c)
    if 246 <= c.pose <= 263:
        state = replace(state, revealed=c.environment == 4 and c.pose <= 261)
        return prone(state, c)
    if 110 <= c.pose <= 119:
        return state
    raise NotImplementedError('This model covers only low/prone and rise control gates')


def sampled_low_tick(saved_bank, axes, context, *, gate_matches=True):
    """Saved-player wrapper composition; poses/terrain are supplied, not advanced."""
    c = context
    if not gate_matches or not c.room or c.selected == 59:
        axes = 0, 0, axes[2]
    relative = saved_bank.sample(*axes).remap(facing_right=c.facing_right)
    result = low_control(relative, c)
    return replace(result, bank=result.bank.remap(facing_right=c.facing_right))
