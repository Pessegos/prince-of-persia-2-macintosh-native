"""Level 14's room themes: the CUST room hooks and FinlWatchOpps (CODE 9).

Rooms here are the port's zero-based ones; the comments give the native
rooms (one higher).
"""

SPIDER, CHESS, CRYSTAL, ESCHER = 268, 267, 269, 262
SPIDER_ROOM, CHESS_ROOMS, CRYSTAL_ROOM = 2, (3, 4), 5
# Native room 8 sets a5-0x4ff2 (reset when the level starts, 2:6e74);
# native room 7 plays Escher only once it is set.
LOWER_ESCHER_ROOM, UPPER_ESCHER_ROOM = 6, 7


def entry_song(room, escher_seen, playing, bank_count):
    """The song a room's enter hook asks for, or None: 9:1a90 (native
    rooms 3-5) and 9:1d84 (6-8). `playing(cue)` is PrinceSndOn 5:52c8;
    `bank_count(room)` the room's opponent count (LEVL 0x20e6 + room *
    0xc0)."""
    if room == SPIDER_ROOM:
        return SPIDER                                   # 9:1b20-1b32
    if room == CHESS_ROOMS[0]:
        return CHESS          # 9:1ab4-1ada; the hook then waits on sound 30500
    if room == LOWER_ESCHER_ROOM:
        return ESCHER if escher_seen else None          # 9:1dbe-1dda
    if room == UPPER_ESCHER_ROOM:                       # 9:1dea-1e1a
        return ESCHER if not playing(ESCHER) and bank_count(UPPER_ESCHER_ROOM) else None
    if room == CRYSTAL_ROOM:
        return CRYSTAL                                  # 9:1e22, the hook's other room
    return None


def watch_song(room, escher_seen, bank_count):
    """FinlWatchOpps 9:068c-06f8, once no song plays: (the room's theme or
    None, the new a5-0x4ff2 flag, a song to stop or None)."""
    if room == SPIDER_ROOM:
        return SPIDER, escher_seen, None
    if room in CHESS_ROOMS:
        return CHESS, escher_seen, None
    if room == CRYSTAL_ROOM:
        # 9:06bc-06e4: with the false Princes gone, Crystal is stopped.
        if bank_count(CRYSTAL_ROOM):
            return CRYSTAL, escher_seen, None
        return None, escher_seen, CRYSTAL
    if room == UPPER_ESCHER_ROOM:
        return ESCHER, True, None                       # 9:06e6-06f2
    if room == LOWER_ESCHER_ROOM:
        return (ESCHER if escher_seen else None), escher_seen, None   # 9:06ec-06f2
    return None, escher_seen, None
