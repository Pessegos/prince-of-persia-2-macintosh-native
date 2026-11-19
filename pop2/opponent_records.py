"""Saved type-2/type-6 room records, separate from live animation state."""

from dataclasses import dataclass

from pop2.sequence_runtime import SequenceState
from pop2.terrain import TerrainMotion, floor_y


# IsDeadPos 4:47a0-48de: pose 185 for every actor; type 2
# adds 228 in set 0 (4:4846-485c) and 248 and 251-256 in any other set
# (4:4864-4896: the temple's birdhead corpses, SEQS 191-194, are 252-255);
# type 10 213, type 4 206/207 and type 11 273.
_TYPE_2_SET_0_DEAD = frozenset((185, 228))
_TYPE_2_OTHER_DEAD = frozenset((185, 248, 251, 252, 253, 254, 255, 256))
PRINCE_DEAD_POSES = frozenset((185, 242, 243, 266, 271))
_OTHER_DEAD = {0: PRINCE_DEAD_POSES, 10: frozenset((185, 213)), 4: frozenset((185, 206, 207)),
               11: frozenset((185, 273))}


def is_dead_pose(actor_type, opponent_set, pose):
    """IsDeadPos 4:47a0, excluding the Prince's level-five mode-10 exception."""
    if actor_type == 2:
        return pose in (_TYPE_2_SET_0_DEAD if opponent_set == 0 else _TYPE_2_OTHER_DEAD)
    return pose in _OTHER_DEAD.get(actor_type, (185,))


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


LAUGH_SEQUENCE, LAUGH_SOUND = 197, 261


def fresh_sequence(actor_type, sequence):
    """InitOpps 6:2d64-2d9e for a record at zero cursor (type 10 aside):
    a type-6 figure starts in SEQS 2, except the room-11 Jaffar, who keeps
    SEQS 197 and laughs (AddSound(0x105)); other types keep SEQS 22 or take
    77. Returns (sequence, sound or None)."""
    if actor_type == 6:
        if sequence == LAUGH_SEQUENCE:
            return sequence, LAUGH_SOUND
        return 2, None
    return (sequence if sequence == 22 else 77), None


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
    def capture(cls, actor, *, restart_living, cell=None, update_height=True, opponent_set=0):
        state = actor.state
        previous = actor.guard_record
        native_alive = actor.life > 0 if actor.native_alive is None else actor.native_alive
        restart = restart_living and native_alive
        # UpdateOppInfo leaves the old resource header intact when it clears
        # a living cursor. The header still controls InitOpps' height branch.
        sequence = previous.sequence if restart and previous is not None else state.sequence_id
        height = previous.height if previous is not None else 0
        # SetSpecialOppInfo 6:33bc (update_height: UpdateOppInfo 3164 and
        # TransferOppInfo 338e, not the Cut copy 3186): a type 2 in SEQS
        # 100/186 (selected ID) saves its height; otherwise, in set 7, the
        # record takes the current ID even for a restarted cursor and a zero
        # height (33e8-3402).
        if update_height and state.source_sequence_id in (100, 186):
            height = floor_y(actor.row) + state.current_y
        elif update_height and opponent_set == 7 and state.actor_type == 2:
            sequence, height = state.sequence_id, 0
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
                              current_y=initial_y, facing=state.facing, actor_type=state.actor_type,
                              level_kind=state.level_kind, callback_counter=state.callback_counter)
        state.__dict__.update(fresh.__dict__)
        laugh = None
        if self.cursor:
            sequence = self.sequence
        else:
            sequence, laugh = fresh_sequence(state.actor_type, self.sequence)
        state.select(sequence)
        state.cursor = self.cursor
        actor.selected_sequence = sequence
        actor.life = self.life if self.cursor else actor.max_life
        actor.sword_drawn = self.armed if self.cursor else False
        actor.alert_mode = 0
        actor.recovering = actor.contact_consumed = False
        actor.runtime.next_frame()
        dead = is_dead_pose(state.actor_type, opponent_set, state.action)
        if dead:
            actor.life = 0
            corpse = corpse_sequence(opponent_set, state.level_kind, slot)
            if state.action == 185 and corpse is not None:
                state.select(corpse)
                actor.selected_sequence = corpse
                actor.runtime.next_frame()
        actor.native_alive = not dead
        actor.death_registered = dead
        # InitOpps 6:2e18-2e20 restores settled corpses with ALIVE 7 and
        # clears the pending cue. The port's counter saturates at six.
        actor.death_song_frames, actor.death_song_pending = (6 if dead else -1), False
        if laugh is not None:
            # 6:2d7e: the room-11 Jaffar laughs as the room is entered.
            state.sound_events.append(laugh)
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
