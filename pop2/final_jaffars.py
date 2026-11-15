"""CODE 9's Jaffar copies in native room 3 of the final tower.

FinlCheckGenOpp 9:0202 picks a row and a column and calls the record
constructor 9:03c8, which reads its first argument as the column and its
second as the row. FinlCheckDeadOpp 9:00e2 replaces the ordinary dead-guard
work for these copies: at ALIVE 6 one may leave a flask on its cell, and at
ALIVE 96 the body shimmers away (SEQS 239, whose -17 removes it).
"""

from dataclasses import dataclass

SKILL = 5  # 9:0424
# 9:0438 / 9:01ac-01ba: the appearance and the shimmer, with sound 243.
APPEAR_SEQUENCE, VANISH_SEQUENCE, SHIMMER_SOUND = 238, 239, 243
DROP_ALIVE, VANISH_ALIVE = 6, 96
FLASK_TILE = 10
# 9:011e: fewer than four animated objects (a5-0x43e6).
MAX_OBJECTS = 4
# 9:0136-0140: no flask on cells 22-24.
NO_DROP_CELLS = range(22, 25)


@dataclass(frozen=True)
class JaffarSpawn:
    cell: int
    column: int
    row: int
    life: int

    @property
    def facing_right(self):
        # 9:040c-0420: columns below 5 face right (native 0), others left.
        return self.column < 5

    @property
    def native_x(self):
        # 9:03fa-040c: a5-0x4b88[column], each column 51 pixels from 207.
        return 207 + 51 * self.column


def next_jaffar_spawn(count, first_sequence, first_row, player_row, rng):
    """FinlCheckGenOpp 9:0202, followed by the draws of 9:03c8.

    A copy is born on the row the Prince is not on: column 4 (or 8) on
    row 1, column 2 (or 6) on row 2. The caller owns the room-3 bank count.
    """
    if count == 0:
        row = 1 if player_row == 2 else 2
    elif count == 1:
        # a5-0x51e0 and -0x51fa are +0x28/+0x0e in the first opponent.
        if first_sequence == APPEAR_SEQUENCE:
            return None
        row = 2 if first_row == 1 else 1
        # Rnd(20) 17:6e06 is inclusive: zero occurs once in 21 draws.
        if row == player_row or rng.randrange(21) != 0:
            return None
    else:
        return None
    column = (4 if row == 1 else 2) + (4 if rng.randrange(2) else 0)
    # 9:045a-0466: life Rnd(2) + 3, so 3, 4 or 5.
    life = rng.randrange(3) + 3
    return JaffarSpawn(row * 10 + column, column, row, life)


@dataclass(frozen=True)
class DeadCopyStep:
    alive: int
    drop: int = 0          # flask kind written on the copy's cell
    cell: int = 0
    vanish: bool = False   # SEQS 239 and sound 243 this frame


def dead_copy_step(alive, pending, selected, cell_kind, objects, row, column, rng):
    """FinlCheckDeadOpp 9:00e2 for one GenCtrl call on a dead copy.

    `alive` is the native ALIVE word (a5-0x503a), `pending` the cue word
    a5-0x503e and `selected` the +0x28 sequence. At ALIVE 6 Rnd(2) is drawn
    whatever the cell holds; 1 is a healing flask and 2 a life enhancement.
    """
    drop = cell = 0
    vanish = False
    if alive == DROP_ALIVE:
        roll = rng.randrange(3)
        cell = row * 10 + column
        if (roll and cell_kind == 1 and objects < MAX_OBJECTS
                and cell not in NO_DROP_CELLS):
            drop = roll
        alive += 1
    elif alive >= VANISH_ALIVE and selected != VANISH_SEQUENCE:
        vanish = True
        alive += 1
    # 9:01d4-01e2: with the cue consumed, ALIVE counts on.
    if not pending and alive > DROP_ALIVE:
        alive += 1
    return DeadCopyStep(alive, drop, cell if drop else 0, vanish)


def drop_foreground(kind):
    """9:015e-0162: (kind << 5) | 0x4000."""
    return (kind << 5) | 0x4000
