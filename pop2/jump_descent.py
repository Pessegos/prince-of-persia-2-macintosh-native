"""A presentation-only terminal jump pose, with ordinary wall occlusion intact."""

from dataclasses import dataclass, replace

from pop2.sequence_runtime import SequenceState
from pop2.terrain import TILE_HEIGHT


@dataclass(frozen=True)
class JumpEnd:
    state: SequenceState
    room: int
    row: int


def capture_jump_end(motion, state):
    # CheckFloor consumes pose44 when StartFall immediately advances SEQS21.
    # Retain its pre-alignment drawing point for this bottom-edge transition.
    if (motion.row != 2 or motion.dead or state.actor_type != 0 or state.level_kind != 3
            or state.source_sequence_id != 4 or state.action != 44):
        return None
    return JumpEnd(replace(state, sound_events=[], sequence_events=[]), motion.room, motion.row)


def descent_drawing(previous, motion, state):
    if (previous is None or not motion.falling or motion.dead
            or motion.room != previous.room or motion.row != previous.row + 1
            or state.source_sequence_id != 21 or state.action != 102):
        return None
    # The simulation has advanced its supporting row. Express the retained
    # drawing in that row's coordinates without moving the physical actor.
    return replace(previous.state,
                   current_y=previous.state.current_y + (previous.row - motion.row) * TILE_HEIGHT)
