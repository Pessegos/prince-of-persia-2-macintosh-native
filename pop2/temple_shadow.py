"""Level thirteen's shadow: the Prince's double that takes the sacred flame.

A Prince who dies on native room 4's row 1 right of the flame (X > 375),
after the death message, rises as a type-1 actor (10:2b32). Its AutoCtrl
(10:2850) runs left, jumps the chasm, takes the flame (SEQS 232, mode 13),
jumps back and lies down on the body; the merge (10:27d8) revives the
Prince. See docs/research/temple-altar.md.
"""

from dataclasses import dataclass

from pop2.sequence_runtime import SequenceState
from pop2.terrain import TerrainMotion

SHADOW_TYPE = 1
RISE_SEQUENCE = 231
RISE_SONG = 254
TAKE_FLAME_SEQUENCE = 232
TURN_SONG = 251
CATCH_SEQUENCE, CLIMB_SEQUENCE = 15, 10
# SEQS 15 -> 9 -> 210 hang and SEQS 10 -> 235 climb: no free-fall physics.
LEDGE_SEQUENCES = (15, 9, 210, 10, 235)
MERGE_SONG = 252
# -5022 / -509e: the mode SEQS 232 leaves the shadow (and the merge the Kid).
IMBUED_MODE = 13
# 10:2b00: the burned Kid (SEQS 230) never rises.
BURNED_MODE = 12
# AddCharObj copies the draw mode 0x30 (-5020): the shadow's colours are
# palette entries 48-63, which hold Kid CTBL 2000 (4:1fea, 2:4b58), and
# CTBL 4077 once it holds the flame (10:2a10, PoPSetPalette(4077, 48)).
SHADOW_PALETTE = 2000
FLAME_PALETTE = 4077


@dataclass
class TempleShadow:
    state: SequenceState
    motion: TerrainMotion
    # -503e: DoStepFwd's warning flag (+0x18), copied from the Kid.
    cautious: bool = False
    palette: int = SHADOW_PALETTE


def shadow_rises(row, x, action, mode, altar):
    """10:2af0-2b0e for the saved Kid: pose 185 at native X > 375 on row 1,
    not burned (mode 12), with a5-0x4fd4 = 1 (KeepTime's death message)."""
    return row == 1 and x > 375 and action == 185 and mode != BURNED_MODE and altar == 1


def auto_ctrl(state, column, kid_x, kid_facing, step, run_jump):
    """10:2850 for the shadow (port facing: 1 right, 0 left).

    ``column`` is the foot column word (-504a); ``kid_x``/``kid_facing`` the
    saved Kid (-50ce/-50d0). ``step(arg)`` runs DoStepFwd 6:1276 and returns
    the selected SEQS; ``run_jump()`` runs DoRunJump(4). Returns (sequence
    or None, event or None): the caller selects the sequence (JumpSeq 6:0006)
    and acts on 'turn' (AddSong 251), 'catch', 'hang', 'flare', 'palette'
    and 'merge'."""
    pose, imbued = state.action, state.sequence_mode == IMBUED_MODE
    if pose == 15:
        if not state.facing:
            if column >= 6:
                if imbued:
                    return 71, None
                if column >= 8:
                    return 1, None
                return (3 if step(0) == 44 else None), None
            if not imbued and state.selected_sequence_id != TAKE_FLAME_SEQUENCE:
                return TAKE_FLAME_SEQUENCE, None
            return 5, 'turn'
        if not imbued:
            return 5, None
        if column >= 6:
            # 10:28e2-293e: walk to 10 pixels before the body, plus 12 more
            # (a5-0x4b94: -1 right, +1 left) when both face the same way.
            native = state.target_x + 207
            d = kid_x - (native - 10)
            same = kid_facing == state.facing
            if same:
                d += (-1 if state.facing else 1) * 12
            if d > 4:
                step(d)
                return None, None
            add_char_x(state, d)
            return (71 if same else 5), None
        return (247 if step(0) == 44 else None), None
    if (1 <= pose <= 14 or 49 <= pose <= 56) and column >= 6:
        run_jump()
        return None, None
    if 103 <= pose <= 106:
        # Catch 4:37ca with -3480 = -1 (Up held): a short jump grips the ledge.
        return None, 'catch'
    if pose == 91:
        # DoJumpHang 6:1b7e, else the climb 6:1998 (mode 13 lifts Y by 2).
        return None, 'hang'
    if pose == 154:
        return None, 'flare'
    if pose == 153 and imbued:
        return None, 'palette'
    if imbued and pose == 185:
        return None, 'merge'
    if pose == 44:
        add_char_x(state, -12)
        return 13, None
    return None, None


def flame_shape(frame):
    """SetupShadowFlame 4:2650-265c: SHAP 4102 + the frame counter
    (a5-0x349a, 2:6754) modulo 9."""
    return 4102 + frame % 9


def add_char_x(state, distance):
    """AddCharX 4:2bae: native facing -1 (left) negates the distance."""
    state.target_x += distance if state.facing else -distance
    state.current_x = state.target_x
