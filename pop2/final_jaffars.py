"""CODE 9's initial Jaffar-copy records in the final tower."""

from dataclasses import dataclass


@dataclass(frozen=True)
class JaffarSpawn:
    cell: int
    column: int
    row: int
    life: int


def next_jaffar_spawn(count, first_sequence, first_row, player_row, rng):
    """FinlCheckGenOpp 9:0202, followed by the record writes at 9:03c8.

    The record's cell is a final-path position; rows 4, 6 and 8 are not
    ordinary room cells. The caller owns the original room-3 bank count.
    """
    if count == 0:
        column = 1 if player_row == 2 else 2
    elif count == 1:
        # a5-0x51e0 and -0x51fa are +0x28/+0x0e in the first opponent.
        if first_sequence == 238:
            return None
        column = 2 if first_row == 1 else 1
        # Rnd(20) 17:6e06 is inclusive: zero occurs once in 21 draws.
        if column == player_row or rng.randrange(21) != 0:
            return None
    else:
        return None
    row = (4 if column == 1 else 2) + (4 if rng.randrange(2) else 0)
    return JaffarSpawn(row * 10 + column, column, row, rng.randrange(2) + 3)
