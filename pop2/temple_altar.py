"""Level thirteen's altar: the sacred flame in native room 4.

The temple's environment hook (FrameAdv 2:7124 -> a5-0x46f8[2] = 10:27ba)
runs 10:2a62 while the Kid's room (a5-0x4fc2) is native room 4 of level
13. It reads the saved Kid (a5-0x50d2): row +0xe, selected SEQS +0x28,
X +4 (native, with the 207 origin). See docs/research/temple-altar.md.
"""

ALTAR_LEVEL, ALTAR_ROOM = 13, 3  # native room 4
ALTAR_ROW = 1
BURN_SEQUENCE = 230
# 10:2a8c: the burning Kid stands at native X 335.
BURN_X = 335
BURN_SOUND = 249
# SetKidDeathMethod(16): AddKidDeathSong plays a5-0x4396[16] (250).
BURN_DEATH_METHOD = 16
APPROACH_SONG = 253


def altar_event(level_number, room_id, row, x, selected_sequence, approach_song_playing):
    """10:2a62-2aee for the Kid: 'burn' at native X <= 347, 'song' (AddSong
    253 unless PrinceSndOn) at X <= 375, else None. Nothing in another row
    or once SEQS 230 is selected."""
    if ((level_number, room_id) != (ALTAR_LEVEL, ALTAR_ROOM) or row != ALTAR_ROW
            or selected_sequence == BURN_SEQUENCE):
        return None
    if x <= 347:
        return 'burn'
    if x <= 375 and not approach_song_playing:
        return 'song'
    return None
