"""Ordinary type-2 room records, separate from live animation state."""

from dataclasses import dataclass

from pop2.sequence_runtime import SequenceState
from pop2.terrain import TerrainMotion, floor_y


# IsDeadPos 4:4846-48de for the ordinary corpses, with set 7's four variants.
CORPSE_POSES = frozenset((185, 228, 252, 253, 254, 255))


def corpse_sequence(opponent_set, level_kind, slot):
    """GetOppDeadSeq's table 4:00ac: the corpse of bank slot ``slot``, or None
    to keep pose 185. The temple's birdheads (set 7) have four flat corpses,
    SEQS 191-194; SEQS 195's pose 228 stands in their art."""
    if opponent_set == 7:
        first, count = 191, 5
    elif opponent_set == 0 and level_kind != 6:
        first, count = 195, 2
    else:
        return None
    offset = slot % count
    return first + offset - 1 if offset else None


@dataclass
class GuardRoomRecord:
    sequence: int
    cursor: int
    life: int
    armed: bool
    cell: int | None = None
    height: int = 0
    pending: bool = True

    @classmethod
    def capture(cls, actor, *, restart_living, cell=None, update_height=True):
        state = actor.state
        previous = actor.guard_record
        native_alive = actor.life > 0 if actor.native_alive is None else actor.native_alive
        restart = restart_living and native_alive
        # UpdateOppInfo leaves the old resource header intact when it clears
        # a living cursor. The header still controls InitOpps' height branch.
        sequence = previous.sequence if restart and previous is not None else state.sequence_id
        height = previous.height if previous is not None else 0
        if update_height and state.source_sequence_id in (100, 186):
            height = floor_y(actor.row) + state.current_y
        return cls(sequence, 0 if restart else state.cursor, actor.life,
                   actor.sword_drawn, cell, height)

    def restore(self, actor, slot, opponent_set=0):
        if not self.pending:
            return False
        state = actor.state
        if self.cell is not None:
            actor.row = abs(self.cell) // 10 * (-1 if self.cell < 0 else 1) - int(self.cell < 0)
        initial_y = self.height - floor_y(actor.row) if self.sequence == 100 else 0
        fresh = SequenceState(self.sequence, current_x=state.target_x, target_x=state.target_x,
                              current_y=initial_y, facing=state.facing, actor_type=2,
                              level_kind=state.level_kind, callback_counter=state.callback_counter)
        state.__dict__.update(fresh.__dict__)
        sequence = self.sequence if self.cursor or self.sequence == 22 else 77
        state.select(sequence)
        state.cursor = self.cursor
        actor.selected_sequence = sequence
        actor.life = self.life if self.cursor else actor.max_life
        actor.sword_drawn = self.armed if self.cursor else False
        actor.alert_mode = 0
        actor.recovering = actor.contact_consumed = False
        actor.runtime.next_frame()
        dead = state.action in CORPSE_POSES
        if dead:
            actor.life = 0
            corpse = corpse_sequence(opponent_set, state.level_kind, slot)
            if state.action == 185 and corpse is not None:
                state.select(corpse)
                actor.selected_sequence = corpse
                actor.runtime.next_frame()
        actor.native_alive = not dead
        actor.death_registered = dead
        actor.targetable = actor.life > 0
        state.animation_state = 1
        state.horizontal_velocity = state.vertical_velocity = 0
        state.current_x = state.target_x
        if actor.terrain_motion is not None:
            actor.terrain_motion = TerrainMotion(actor.room, actor.row)
        self.pending = False
        return True


def removed_on_room_save(actor):
    state = actor.state
    return state.sequence_mode in (4, 5) or state.source_sequence_id in (154, 196)
