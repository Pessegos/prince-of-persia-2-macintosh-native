"""Ordinary type-2 room records, separate from live animation state."""

from dataclasses import dataclass

from pop2.sequence_runtime import SequenceState
from pop2.terrain import TerrainMotion, floor_y


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

    def restore(self, actor, slot):
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
        dead = state.action in (185, 228)
        if dead:
            actor.life = 0
            if state.action == 185 and state.level_kind != 6 and slot % 2:
                state.select(195)
                actor.selected_sequence = 195
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
    return state.special_flag in (4, 5) or state.source_sequence_id in (154, 196)
