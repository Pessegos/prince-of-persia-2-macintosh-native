"""Level twelve's flaming sword: actor type 10 drawn from FlameSword.rsrc.

The temple's raw opponent kind 1 (6:2bca, DATA a5-0x5280) is a sword with no
body (every FlameSword FRAM shape is -1). It shares the skeleton's
proximity wake (4:14c6) and timer (SetSkelTimer 4:184a), the ordinary
guard's sequences and AI with about thirty type-10 branches, and is worn
down only by parrying its strikes (6:5a74 -> FlameSwordDecLifePts 4:1c36).
"""

from dataclasses import dataclass

from pop2.opponent_generation import EMPTY_TILES, WALL_TILES, character_column


RAW_KIND = 1
ACTOR_TYPE = 10
REST_SEQUENCE = 105    # lying on the floor, pose 213 (IsDeadPos 4:489c)
RISE_SEQUENCE = 106
FALL_SEQUENCE = 107    # drops back to 105
PUSHED_SEQUENCE = 103  # a parried strike that did not exhaust it
ADVANCE_SEQUENCE = 108  # DoAdvance 6:1e1c instead of SEQS 86
GLIDE_SEQUENCE = 90    # 6:2592/25d4: it cannot sheathe (SEQS 77)
REST_POSE = 213
FALL_TIMER = 480       # 4:1ca8 / cheat kill 2:4c52
WAKE_COLUMNS = 5       # 4:1534-1548, as for every set except the skeletons'
FALL_SONG = 238        # 4:1cb6 AddSong
PUSHED_CUE = 10        # 4:1c4c
PARRY_CUE = 239        # TestStrike 6:5ae6 instead of 11
DEATH_METHOD = 12      # CheckStab 6:5722
# GetCharStrikeRanges 6:5c58: its own strike against the Prince.
STRIKE_RANGE = (-16, 61)
# TestStrike 6:5962: the Prince's parry window against it (61..99 for others).
PARRY_WINDOW = (24, 70)
# 4:1be4/1cce: the hovering pieces that flicker and bob.
HOVER_PIECES = (4, 19, 20)


def standing_on_floor(encounter, actor):
    """InitOpps 6:2d1e: IsFloor 3:4da6 of CurrentCell 4:35a6 (X column)."""
    terrain = getattr(encounter, 'terrain', None)
    if terrain is None:
        return True
    tile = encounter._guard_tile(actor, character_column(actor.state.target_x))
    return tile.kind not in EMPTY_TILES | WALL_TILES


def face_prince(actor, player):
    # 6:2d4e-2d5e / 4:1618-1628: native facing 0 (right) unless X >= the Prince's.
    actor.state.facing = int(actor.state.target_x < player.state.target_x)


@dataclass
class FlameSword:
    # The record's +0x1e timer (SetSkelTimer 4:184a), counted down while down.
    timer: int = 0
    # Native ALIVE (a5-0x503a < 0); HP alone is zero at the rest pose.
    native_alive: bool = False
    # a5-0x501a: 1be4's flicker counter, 0 then -1..-4.
    flicker: int = 0
    # The AFRM piece SetupSword drew this frame (after the flicker).
    piece: int | None = None
    song_pending: bool = False
    # A stored room record: True restarts a living sword, False keeps a
    # resting one; None when nothing is pending.
    room_record: bool | None = None

    def initialize(self, encounter, actor):
        """InitOpps 6:2d16-2d62 for a fresh record, then InitOpp 6:2ae0 and
        the post-AnimChar IsDeadPos test (6:2df4-2e4e)."""
        from pop2.combat import select_sequence

        self.flicker, self.piece = 0, None
        if standing_on_floor(encounter, actor):
            select_sequence(actor, REST_SEQUENCE)
            actor.alert_mode = 0
            actor.sword_drawn = False
        else:
            select_sequence(actor, RISE_SEQUENCE)
            actor.sword_drawn = True
            actor.alert_mode = 3
            face_prince(actor, encounter.player)
        # InitOpp 6:2b08: SEQS 105 has no life points.
        actor.life = 0 if actor.state.sequence_id == REST_SEQUENCE else actor.max_life
        actor.runtime.next_frame()
        self.settle(actor)

    def settle(self, actor):
        # IsDeadPos 4:489c: pose 213 is its only dead pose; 6:2e34-2e4e then
        # clears the record timer (types 4 and 10).
        if actor.state.action == REST_POSE:
            self.native_alive = False
            self.timer = 0
            actor.death_registered = True
            actor.targetable = False
        else:
            self.native_alive = True
            actor.targetable = True

    def store_room(self, actor, *, restart_living):
        # UpdateOppInfo 6:30b0 clears the cursor of a living in-bounds record.
        self.room_record = bool(restart_living and self.native_alive)

    def restore_pending(self, encounter, actor):
        """InitOpps on re-entry: a living record restarts (cursor 0) through
        the fresh-record path; a resting one keeps its pose and loses its
        timer (6:2e34-2e4e)."""
        if self.room_record is None:
            return False
        if self.room_record:
            actor.alert_mode = 0
            actor.recovering = actor.contact_consumed = False
            actor.state.current_y = 0
            self.initialize(encounter, actor)
        else:
            self.settle(actor)
        self.room_record = None
        return True

    def can_wake(self, encounter, actor):
        """OpponentClose 4:13a4 with the type-10 rules of 4:14c6."""
        from pop2.skeleton import opponent_path_clear
        from pop2.terrain import floor_y

        player = encounter.player
        if (self.native_alive or self.timer or not player.alive
                or player.state.actor_type != 0 or actor.state.sequence_mode == 5
                or player.state.animation_state in (3, 4, 5)
                or actor.room != player.room or actor.row != player.row):
            return False
        own = encounter._supporting_column(actor)
        other = encounter._supporting_column(player)
        if abs(own - other) > WAKE_COLUMNS:
            return False
        terrain = getattr(encounter, 'terrain', None)
        if terrain is None:
            return True
        art = getattr(encounter, 'guard_art', None)
        bounds = art.bounds(actor.state, floor_y(actor.row)) if art is not None else (0, 0, 0, 57)
        return opponent_path_clear(terrain, actor.room, actor.row, other, own, bounds, actor.state)

    def try_wake(self, encounter, actor):
        """4:15dc-1644: JumpSeq(106), AnimChar, InitOpp, then ALIVE, engaged,
        alert 3 and facing the Prince; it becomes the Prince's target."""
        from pop2.combat import select_sequence

        if not self.can_wake(encounter, actor):
            return False
        select_sequence(actor, RISE_SEQUENCE)
        actor.runtime.next_frame()
        actor.life = actor.max_life
        self.native_alive = True
        actor.targetable = True
        actor.death_registered = False
        actor.sword_drawn = True
        actor.alert_mode = 3
        actor.recovering = False
        face_prince(actor, encounter.player)
        if getattr(encounter, 'target_cache', None) is None:
            encounter.target_cache = actor
        return True

    def control(self, actor):
        """AutoCtrl 4:165c-1704: a resting sword only counts its timer down."""
        if self.native_alive and actor.alive:
            return False
        # PlayerCtrl 4:3d64-3d6c registers zero HP first, including a record
        # restored mid-fall whose pose left ALIVE set (6:2e52).
        self.native_alive = False
        if self.timer > 0:
            self.timer -= 1
        return True

    def parried(self, actor):
        """FlameSwordDecLifePts 4:1c36: one life per parried strike. The last
        drops it (SEQS 107) for 480 frames with song 238; otherwise SEQS 103,
        cue 10 and SetCharFloor 4:31fa."""
        from pop2.combat import select_sequence

        actor.life = max(0, actor.life - 1)
        if actor.alive:
            select_sequence(actor, PUSHED_SEQUENCE)
            actor.state.sound_events.append(PUSHED_CUE)
            actor.state.current_y = actor.state.vertical_velocity = 0
        else:
            self.fall(actor)
        actor.runtime.next_frame()
        actor.state.current_x = actor.state.target_x

    def fall(self, actor):
        from pop2.combat import select_sequence

        # 4:1c9e-1ccc: ALIVE 0 and a5-0x503e (the record is saved) set.
        select_sequence(actor, FALL_SEQUENCE)
        self.timer = FALL_TIMER
        self.native_alive = False
        self.song_pending = True
        actor.life = 0
        actor.targetable = False
        actor.recovering = False
        actor.death_registered = True

    def present(self, actor, record_piece, rng):
        """SetupSword 3:0b1c/4:1be4 then SetupOpponent's 4:1cce, once per
        drawn frame: the hovering pieces flicker through 19-22, and while one
        of 4/19/20 is shown the sword bobs within 4 pixels of its floor."""
        piece = record_piece
        if piece in HOVER_PIECES:
            if self.flicker:
                piece = 18 - self.flicker
            self.flicker = self.flicker - 1 if self.flicker > -4 else 0
        self.piece = piece
        if piece not in HOVER_PIECES:
            return
        # Rnd(n) is 0..n. Native Y is the floor (row*120 + 106) + current_y.
        y = actor.state.current_y
        if y <= -4:
            step = rng.randrange(2) + 1
        elif y >= 4:
            step = rng.randrange(2) - 4
        else:
            step = rng.randrange(9) - 4
        actor.state.current_y += step
