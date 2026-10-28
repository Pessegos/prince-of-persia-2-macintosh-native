"""Bounded original player input wrapper around recovered controller families."""

from dataclasses import dataclass

from tools.reference_input_actions import ActionResult, word
from tools.reference_input_traces import sampled_tick


@dataclass(frozen=True)
class PlayerInputResult:
    action: ActionResult
    countdown: int
    record_status: int


def player_input_tick(saved_bank, axes, pose, *, gate_matches=True, room=1,
                      sequence=201, countdown=0, record_status=0x1234, **context):
    # 4:3cda-3cfc gates raw directions only; the modifier is untouched.
    if not gate_matches or not room or sequence == 59:
        axes = 0, 0, axes[2]
    result = sampled_tick(saved_bank, axes, pose, sequence=sequence, **context)
    return PlayerInputResult(result, word(countdown - 1) if countdown else 0,
                             record_status & 65535)
