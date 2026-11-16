"""CODE 9's path controller for the final Jaffar in the palace (9:16fe).

After the room-6 figures, the last one (9:19fa) runs this AutoCtrl in
native rooms 7 and 8 of environment 6. It moves between four saved
positions (the DATA table at a5-0x2a06) with the Kid's own control
routines, flees while the Prince is strong, and otherwise closes in and
casts SEQS 242, whose pose 282 kills a Prince in range (9:14c8).

Everything here uses native values: rooms are one-based, X includes the
207-pixel origin and facing is the native word (0 right, -1 left).
Columns are "global": room 8 adds 10 to its foot column (9:0ed2 etc.).
"""

from dataclasses import dataclass

from pop2.final_tower import prince_exposed

LEFT_ROOM, RIGHT_ROOM = 7, 8
ROOM_WIDTH = 510


@dataclass(frozen=True)
class Position:
    """One 22-byte entry of a5-0x2a06."""
    column: int
    row: int
    facing: int
    x1: int
    x2: int
    rows: tuple        # +0x0a/+0x0c: the Prince's row for side -1 / +1
    min_columns: tuple  # +0x0e/+0x10
    max_columns: tuple  # +0x12/+0x14


POSITIONS = (
    Position(17, 0, -1, 616, 637, (1, 0), (15, 1), (18, 18)),
    Position(14, 2, -1, 427, 472, (2, 1), (0, 14), (18, 18)),
    Position(5, 2, 0, 484, 523, (1, 2), (2, 0), (9, 18)),
    Position(6, 0, 0, 571, 586, (0, 1), (1, 6), (18, 10)),
)
# a5-0x4b88 + 2 * column: native X of a column's left edge.
COLUMN_X = {column: 207 + 51 * column for column in range(-4, 16)}
# a5-0x4b98 indexed by the facing word: +1 right, -1 left.
FACING_SIGN = {0: 1, -1: -1}

TURN, STOP, RISE = 5, 13, 49
SPELL_SEQUENCE = 242
SPELL_SOUND_POSE, SPELL_STRIKE_POSE = 281, 282
SPELL_SOUND = 289
KILL_SEQUENCE = 244
DISSOLVE_PRINCE_SEQUENCE = 241
DISSOLVE_SONG = 264
BURN_SEQUENCE, BURNED_MODE = 230, 12
HANG_POSE, CROUCH_POSE = 91, 109
RUN_POSES = (7, 11)
# Jump-to-hang, hanging, climbing and lowering sequences: the Kid's hang
# has no free-fall physics.
LEDGE_SEQUENCES = (24, 16, 15, 9, 210, 25, 10, 235, 68)


@dataclass
class PathInfo:
    """Opponent record +0x1c..+0x20: 1 fleeing, 2 closing in; the target
    position and the last position reached."""
    mode: int = 0
    pos: int = 0
    prev: int = 0


@dataclass(frozen=True)
class Figure:
    """The fields of a character record (a5-0x5056 or the opponent
    a5-0x5094) that this controller reads."""
    pose: int
    selected: int
    facing: int
    x: int
    column: int
    row: int
    room: int
    life: int = 0
    # +0x1a, the armed word (a5-0x503c for the Kid): 1 sword drawn, 0
    # sheathed, -1 no sword (2:5eaa-5eba). 9:16fe reads it as -0x507a;
    # ALIVE is +0x1c and plays no part here.
    armed: int = 0
    actor_type: int = 0
    mode: int = 0
    turns: int = 0


def global_column(figure):
    return figure.column + (10 if figure.room == RIGHT_ROOM else 0)


def distance(jaffar, prince):
    """CharDistance 4:49ee: 999 unless the opponent has life (4:49f0, life
    exactly 0 fails) and shares the room and row; 4:4a0a also gives 999 for
    an opponent facing word of 0x56."""
    if (prince.life == 0 or jaffar.room != prince.room or jaffar.row != prince.row
            or prince.facing == 0x56):
        return 999
    value = prince.x - jaffar.x
    if jaffar.facing:
        value = -value
    if value >= 0 and jaffar.facing != prince.facing:
        value += 21
    return value


def prince_in_range(jaffar, prince, frames):
    """9:0ba6: may the spell reach the Prince?

    The pose tests at 9:0bee-0c2c read -0x504c, the Char record's pose:
    Jaffar's own. He must stand in a FRAM 0x40 pose (or 191-205) and not
    crouch (109); the Prince's own pose does not matter here."""
    if (prince.life <= 0 or prince.room not in (LEFT_ROOM, RIGHT_ROOM)
            or prince.selected == DISSOLVE_PRINCE_SEQUENCE or jaffar.row != prince.row
            or not prince_exposed(jaffar.pose, frames) or jaffar.pose == CROUCH_POSE):
        return False
    column = global_column(jaffar)
    if jaffar.row == 0:
        return column <= 6 or column >= 13
    if jaffar.row == 1:
        other = global_column(prince)
        return other <= 12 if column <= 12 else other >= 14
    return jaffar.row == 2


def prince_near(position, side, prince):
    """ShadowInRange 9:1954: the Prince is in the position's side zone."""
    index = 0 if side < 0 else 1
    if POSITIONS[position].rows[index] != prince.row:
        return False
    column = prince.column + (10 if prince.room == RIGHT_ROOM else 0)
    return (POSITIONS[position].min_columns[index] <= column
            <= POSITIONS[position].max_columns[index])


class Controller:
    """One AutoCtrl call. ``kid`` supplies the Kid routines on the Jaffar's
    record: select(seq) (JumpSeq 6:0006), forward() 6:11a0, stand_jump()
    6:15ea, jump_up() 6:1600, climb() 6:1998, release() 6:1a84,
    run_jump() 6:1c14(4), descend() 6:0e8e, step(n) 6:1276 and
    add_x(n) 4:2bae (returns the new X)."""

    def __init__(self, jaffar, prince, info, frames, kid):
        self.jaffar, self.prince, self.info = jaffar, prince, info
        self.frames, self.kid = frames, kid
        self.events = []

    def run(self):
        """9:16fe. Returns the events for the caller: 'kill' (9:14c8),
        'dissolve' (the Prince's SEQS 241), 'sound' and 'hit'."""
        jaffar, prince, info = self.jaffar, self.prince, self.info
        flee = info.mode == 1 and info.pos != info.prev
        close = False
        if prince.actor_type == 0:
            if prince.armed == 1 and not (207 <= jaffar.pose <= 210) and jaffar.pose != 158:
                if abs(distance(jaffar, prince)) < 91:
                    # 9:177e-17bc: a drawn sword within 91 pixels is taken:
                    # the Kid's SEQS 241, song 264 and armed -1.
                    self.events.append(('dissolve', DISSOLVE_PRINCE_SEQUENCE, DISSOLVE_SONG))
            elif prince.row == jaffar.row and prince.turns >= 4:
                flee = prince.life > 2 or prince.selected == SPELL_SEQUENCE
            else:
                # 9:17ec-17fc: he closes in (and casts) only on a Prince
                # without a sword.
                close = prince.armed == -1
        else:
            strong = prince.life > 2 or prince.selected == SPELL_SEQUENCE
            flee, close = strong, not strong
        if jaffar.selected == BURN_SEQUENCE and jaffar.mode == BURNED_MODE:
            self.events.append(('hit',))
        if flee:
            self.flee()
        elif close:
            self.close_in()
        return self.events

    # 9:0b28
    def flee(self):
        info = self.info
        info.mode = 1
        if info.pos == info.prev:
            if prince_near(info.pos, -1, self.prince):
                info.pos = (info.pos - 1) % 4
            elif prince_near(info.pos, 1, self.prince):
                info.pos = (info.pos + 1) % 4
        if info.pos != info.prev:
            self.go_to_position()

    # 9:0a42
    def close_in(self):
        jaffar, prince, info = self.jaffar, self.prince, self.info
        info.mode = 2
        if jaffar.selected == SPELL_SEQUENCE:
            if jaffar.pose == SPELL_SOUND_POSE:
                self.events.append(('sound', SPELL_SOUND))
            elif jaffar.pose == SPELL_STRIKE_POSE and prince_in_range(jaffar, prince, self.frames):
                self.kill()
            return
        if info.pos == info.prev:
            if prince.row == jaffar.row and prince_in_range(jaffar, prince, self.frames):
                self.face_and_cast()
            elif prince.selected != DISSOLVE_PRINCE_SEQUENCE:
                if prince_near(info.pos, -1, prince):
                    info.pos = (info.pos + 1) % 4
                else:
                    info.pos = (info.pos - 1) % 4
        if info.pos != info.prev and prince.life > 0:
            if jaffar.row == 1 and prince_in_range(jaffar, prince, self.frames):
                self.face_and_cast()
            else:
                self.go_to_position()

    # 9:09ca
    def face_and_cast(self):
        jaffar = self.jaffar
        sequence = None
        if jaffar.pose == 15:
            if self.prince.x < jaffar.x:
                sequence = TURN if jaffar.facing != -1 else SPELL_SEQUENCE
            else:
                sequence = TURN if jaffar.facing != 0 else SPELL_SEQUENCE
        elif 1 <= jaffar.pose <= 14 or 49 <= jaffar.pose <= 56:
            if jaffar.selected not in (STOP, TURN):
                sequence = STOP
        if sequence is not None:
            self.kid.select(sequence)

    # 9:14c8
    def kill(self):
        self.kid.select(KILL_SEQUENCE)
        self.events.append(('kill',))

    # 9:0d28
    def go_to_position(self):
        route = (self.route_0, self.route_1, self.route_2, self.route_3)[self.info.pos]
        sequence = route()
        if sequence is not None:
            self.kid.select(sequence)

    # 9:0dac
    def hone_in(self):
        jaffar, info, kid = self.jaffar, self.info, self.kid
        if jaffar.pose != 15:
            return None
        if info.mode == 2 and prince_in_range(jaffar, self.prince, self.frames):
            self.face_and_cast()
            return None
        target = POSITIONS[info.pos]
        x = jaffar.x
        if jaffar.facing != target.facing:
            x += FACING_SIGN[target.facing] * 10
        if target.column < 10:
            if jaffar.room == RIGHT_ROOM:
                x += ROOM_WIDTH
        elif jaffar.room == LEFT_ROOM:
            x -= ROOM_WIDTH
        if x < target.x1:
            if jaffar.facing == 0:
                kid.step(target.x1 - x + 4)
                return None
            return TURN
        if x > target.x2:
            if jaffar.facing == -1:
                kid.step(x - target.x1 + 4)
                return None
            return TURN
        if jaffar.facing != target.facing:
            return TURN
        info.prev = info.pos
        return None

    def _row_one_climb(self, column):
        # The shared row-1 branches of 9:0fea-1052 (toward position 0).
        jaffar, kid = self.jaffar, self.kid
        if jaffar.pose == 15:
            if jaffar.facing == 0:
                if column < 17:
                    kid.forward()
                    return None
                return TURN
            if column < 17:
                return TURN
            kid.jump_up()
            return None
        if column >= 17 and jaffar.pose in RUN_POSES:
            return STOP
        if jaffar.pose == HANG_POSE:
            kid.climb()
        elif jaffar.pose == CROUCH_POSE:
            return RISE
        return None

    def _row_one_descent(self):
        # 9:10e6-1132 and 12ee-1330: drop from the ledge, walk left.
        jaffar, kid = self.jaffar, self.kid
        if 87 <= jaffar.pose <= 91:
            kid.release()
        elif jaffar.pose == 15:
            if jaffar.facing == -1:
                kid.forward()
            else:
                return TURN
        elif jaffar.pose == CROUCH_POSE:
            return RISE
        return None

    # 9:0ed2: to the upper right of room 8.
    def route_0(self):
        jaffar, kid, target = self.jaffar, self.kid, POSITIONS[0]
        column = global_column(jaffar)
        if self.info.prev == 3:
            if jaffar.pose == 15:
                if column == 6:
                    kid.stand_jump()
                elif column > 7 and target.column - 1 > column:
                    kid.forward()
                else:
                    return self.hone_in()
            elif jaffar.pose in RUN_POSES:
                if 5 <= column <= 6 or 10 <= column <= 11:
                    kid.run_jump()
                elif target.column - 1 <= column:
                    return STOP
            return None
        if jaffar.row == 2:
            if jaffar.pose == 15:
                if jaffar.facing == 0:
                    kid.jump_up()
                    return None
                return TURN
            if jaffar.pose == HANG_POSE:
                kid.climb()
            return None
        if jaffar.row == 1:
            return self._row_one_climb(column)
        return self.hone_in()

    # 9:107c: to the lower right of room 8.
    def route_1(self):
        jaffar, kid, info = self.jaffar, self.kid, self.info
        if info.prev < info.pos:
            if jaffar.row == 0:
                if jaffar.facing == 0 and jaffar.selected != TURN:
                    return TURN
                if jaffar.pose == 15:
                    kid.descend()
                return None
            if jaffar.row == 1:
                return self._row_one_descent()
            if jaffar.row == 2:
                if jaffar.pose == CROUCH_POSE:
                    return RISE
                return self.hone_in()
            return None
        column = global_column(jaffar)
        if column <= POSITIONS[2].column and jaffar.pose == 15:
            kid.forward()
            return None
        if 6 <= column <= 7 and jaffar.x >= COLUMN_X[7]:
            kid.run_jump()
            return None
        if column <= 10:
            return None
        if POSITIONS[1].column - 1 <= column and jaffar.pose in RUN_POSES:
            return STOP
        return self.hone_in()

    # 9:11fe: to the lower left of room 7.
    def route_2(self):
        jaffar, kid, info = self.jaffar, self.kid, self.info
        if info.prev < info.pos:
            column = global_column(jaffar)
            if column + 1 >= POSITIONS[1].column and jaffar.pose == 15:
                kid.forward()
                return None
            if (column >= 11 and COLUMN_X[2] + 57 > jaffar.x and jaffar.selected != 4
                    and jaffar.pose in RUN_POSES):
                kid.add_x(3)
                kid.run_jump()
                return None
            if column <= 6 and jaffar.pose in RUN_POSES:
                return STOP
            return self.hone_in()
        if jaffar.row == 0:
            if jaffar.pose == 15:
                if jaffar.facing == 0:
                    return TURN
                kid.descend()
            return None
        if jaffar.row == 1:
            return self._row_one_descent()
        if jaffar.row == 2:
            if jaffar.pose == CROUCH_POSE:
                return RISE
            return self.hone_in()
        return None

    # 9:136e: to the upper left of room 7.
    def route_3(self):
        jaffar, kid, info, target = self.jaffar, self.kid, self.info, POSITIONS[3]
        column = global_column(jaffar)
        if info.prev == 0:
            if jaffar.pose == 15:
                if column > 10:
                    kid.forward()
                elif column <= target.column:
                    return self.hone_in()
            elif jaffar.pose in RUN_POSES:
                if column <= target.column:
                    return STOP
                if 14 <= column <= 15 or 9 <= column <= 10:
                    kid.run_jump()
            return None
        if jaffar.row == 2:
            if jaffar.pose == 15:
                kid.jump_up()
            elif jaffar.pose == HANG_POSE:
                kid.climb()
            return None
        if jaffar.row == 1:
            if jaffar.pose == 15:
                if jaffar.facing == 0:
                    if column == 6:
                        kid.step(51)
                        return None
                    return TURN
                kid.jump_up()
            elif jaffar.pose == HANG_POSE:
                kid.climb()
            elif jaffar.pose == CROUCH_POSE:
                return RISE
            return None
        return self.hone_in()
