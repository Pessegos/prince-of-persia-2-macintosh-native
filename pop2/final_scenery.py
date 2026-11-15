"""Level 14's moving scenery: room 3's serpents, room 6's crystal glints
and the gargoyle faces of rooms 7 and 8 (CODE 9).

Each object is a trob (AnimTrobs 5:0c38) whose state is its cell's
foreground word (a5-0x4818, written back by AnimTrob 5:0e24). The drawing
hooks move a CUST record of the room and call DrawCustomRoomImg 3:2438.
Rooms are the port's zero-based ones; the native rooms are one higher.
"""

from dataclasses import dataclass

SERPENT_ROOM, FACE_ROOM, CRYSTAL_ROOM, GARGOYLE_ROOMS = 2, 3, 5, (6, 7)
# The kinds whose cells KeepTime 2:5170 makes trobs with their own word.
TROB_KINDS = {SERPENT_ROOM: 40, FACE_ROOM: 31}
ACTIVE, TROB = 0x800, 0x1000
# a5-0x29a6 and a5-0x299a, contiguous: an 'a' index past its six entries
# reads on into the 'b' table (DrawFinlSpider 9:1d28-1d3c).
SERPENT_FRAMES = (0, 1, 2, 3, 2, 1, 4, 5, 6, 7, 6, 5)
SERPENT_B = 6
SERPENT_RECORD = 3
# Room 4's face (trob type 31, 9:1b3a/1ba4): a5-0x29ae, record - 3.
FACE_FRAMES = (0, 1, 1, 0)
FACE_RECORD = 3
FACE_FIRST = 12
# AnimFinlCrystal/DrawFinlCrystal: a5-0x2986 (frame -> record - 8),
# a5-0x297c ((dy, dx) per crystal) and a5-0x2958 (the drawing pass).
CRYSTAL_FRAMES = (0, 1, 2, 3, 0)
CRYSTAL_RECORD = 8
CRYSTAL_OFFSETS = ((83, 472), (167, 59), (165, 130), (191, 201), (177, 317),
                   (189, 355), (283, 1), (285, 211), (296, 403))
CRYSTAL_PASSES = (1, 0, 0, 0, 0, 1, 1, 1, 1)
CRYSTAL_LIMIT = 9
CRYSTAL_LAST_FRAME = 5
# AnimFinlGargoyle/DrawFinlGargoyle: a5-0x2946 (frame -> record - 2),
# a5-0x2938 ((bottom, x) per gargoyle) and a5-0x2928 (the pass).
GARGOYLE_FRAMES = (2, 1, 2, 3, 1, 2, 0)
GARGOYLE_RECORD = 2
GARGOYLE_POSITIONS = ((147, 172), (205, 216), (274, 97), (274, 320))
GARGOYLE_PASSES = (0, 0, 0, 1)
GARGOYLE_LAST_FRAME = 7
# 9:1d84: the gargoyle index counter a5-0x2874 starts at 0 in native room
# 7 and at 2 in room 8.
GARGOYLE_FIRST = {6: 0, 7: 2}


@dataclass(frozen=True)
class SceneryImage:
    """DrawCustomRoomImg(record, pass) with the record moved to (x, bottom)
    or by (dx, dy) from its own place."""
    record: int
    draw_pass: int
    dx: int = 0
    dy: int = 0
    x: int | None = None
    bottom: int | None = None


def _timer(word, shift, mask):
    return (word & mask) >> shift


def serpent_step(word, rng, paused=False):
    """AnimFinlSpider 9:1bf0. Bits 0-2 are the frame and bits 3-10 a timer.
    With the timer at zero the frame advances to 5, which sets the timer to
    Rnd(60) + 30. An expired timer draws Rnd(5) + 1 again and sets frame 7
    (9:1c66-1c74), so the timer never returns to zero. a5-0x5002 (`paused`)
    instead restarts the long wait."""
    timer = _timer(word, 3, 0x7f8)
    if timer == 0:
        frame = word & 7
        if frame == 5:
            timer = rng.randrange(61) + 30
        else:
            frame += 1
        word = (word & 0xfff8) | frame
    else:
        timer -= 1
        if timer <= 0:
            if not paused:
                timer = rng.randrange(6) + 1
                word |= 7
            else:
                timer = rng.randrange(61) + 30
    return (word & 0xf807) | ((timer << 3) & 0xffff)


def serpent_images(word):
    """DrawFinlSpider 9:1cba, in pass 11: the two serpents' records."""
    if not word & 0x7f8:
        first = second = 0
    elif word & ACTIVE:
        first, second = 0, word & 7
    else:
        first, second = word & 7, 0
    return (SceneryImage(SERPENT_FRAMES[first] + SERPENT_RECORD, 11),
            SceneryImage(SERPENT_FRAMES[SERPENT_B + second] + SERPENT_RECORD, 11))


def face_step(word):
    """9:1b3a: the word counts up; at 16 in its low five bits the trob ends
    with the word cleared (None)."""
    word = (word + 1) & 0xffff
    return None if (word & 31) - FACE_FIRST >= len(FACE_FRAMES) else word


def face_images(word):
    """9:1ba4, in pass 11: counts 12-15 draw records 3, 4, 4 and 3."""
    count = (word & 31) - FACE_FIRST
    if not 0 <= count < len(FACE_FRAMES):
        return ()
    return (SceneryImage(FACE_FRAMES[count] + FACE_RECORD, 11),)


def _glint_step(word, rng, last_frame, paused, objects):
    """The shared body of AnimFinlCrystal 9:1e46-1f36 and AnimFinlGargoyle
    9:2122-2208: bits 4-10 count frames while ACTIVE, else the wait."""
    value = _timer(word, 4, 0x7f0)
    word &= 0xf80f
    if word & ACTIVE:
        if value + 1 <= last_frame:
            word |= (value + 1) << 4
        else:
            word = (word | (rng.randrange(41) + 40) << 4) & ~ACTIVE
    elif value - 1 > 0:
        word |= (value - 1) << 4
    elif not paused or not objects:
        word |= ACTIVE
    else:
        word |= (rng.randrange(41) + 40) << 4
    return word | TROB


def crystal_step(word, rng, paused=False, objects=1):
    """AnimFinlCrystal 9:1e30: frames 1-5, then a wait of Rnd(40) + 40."""
    return _glint_step(word, rng, CRYSTAL_LAST_FRAME, paused, objects)


def gargoyle_step(word, room, rng, paused=False, objects=1):
    """AnimFinlGargoyle 9:20dc: frames 1-7. Gargoyles 0-1 belong to native
    room 7, 2-3 to room 8; any other pairing ends the trob (None)."""
    index = word & 15
    if not (index < 2 and room == 6 or index >= 2 and room == 7):
        return None
    return _glint_step(word, rng, GARGOYLE_LAST_FRAME, paused, objects)


def _frame(word):
    if not word & ACTIVE:
        return None
    frame = _timer(word, 4, 0x7f0) - 1
    return frame if frame >= 0 else None


def crystal_image(word):
    """DrawFinlCrystal 9:1f5e, in pass 1: record 8 + a5-0x2986[frame - 1],
    moved by the crystal's offset, in the crystal's own pass."""
    frame, index = _frame(word), word & 15
    if frame is None or index >= len(CRYSTAL_OFFSETS) or frame >= len(CRYSTAL_FRAMES):
        return None
    dy, dx = CRYSTAL_OFFSETS[index]
    return SceneryImage(CRYSTAL_FRAMES[frame] + CRYSTAL_RECORD, CRYSTAL_PASSES[index], dx=dx, dy=dy)


def gargoyle_image(word):
    """DrawFinlGargoyle 9:2238, in pass 1: record 2 (gargoyle 0) or 6 (the
    others) + a5-0x2946[frame - 1] at the gargoyle's place and pass."""
    frame, index = _frame(word), word & 15
    if frame is None or index >= len(GARGOYLE_POSITIONS) or frame >= len(GARGOYLE_FRAMES):
        return None
    bottom, x = GARGOYLE_POSITIONS[index]
    record = GARGOYLE_FRAMES[frame] + GARGOYLE_RECORD + (4 if index else 0)
    return SceneryImage(record, GARGOYLE_PASSES[index], x=x, bottom=bottom)


def scenery_images(room, word):
    """The images a trob's word draws in its room."""
    if room == SERPENT_ROOM:
        return serpent_images(word)
    if room == FACE_ROOM:
        return face_images(word)
    image = (crystal_image(word) if room == CRYSTAL_ROOM else
             gargoyle_image(word) if room in GARGOYLE_ROOMS else None)
    return () if image is None else (image,)


def invalidates(room, before, after):
    """Whether the AnimTrob call from `before` asked for its rectangle to be
    redrawn (5:19f8). The screen keeps the last drawn image otherwise: a
    crystal's or gargoyle's final frame, the face's last blink image and
    the serpents' pose stay until the room is drawn again."""
    if room == SERPENT_ROOM:
        return not before & 0x7f8
    if room == FACE_ROOM:
        return after is not None and (after & 31) >= FACE_FIRST
    last = CRYSTAL_LAST_FRAME if room == CRYSTAL_ROOM else GARGOYLE_LAST_FRAME
    return after is not None and bool(before & ACTIVE) and _timer(before, 4, 0x7f0) + 1 <= last


def step(room, word, rng):
    """One AnimTrob call: (the new word, or None when the trob ends, and
    whether its rectangle is redrawn)."""
    if room == SERPENT_ROOM:
        after = serpent_step(word, rng)
    elif room == FACE_ROOM:
        after = face_step(word)
    elif room == CRYSTAL_ROOM:
        after = crystal_step(word, rng)
    else:
        after = gargoyle_step(word, room, rng)
    return after, invalidates(room, word, after)


def trigger(index, rng):
    """TriggerFinlCrystal 9:2068 / TriggerFinlGargoyle 9:233a: the index,
    a wait of Rnd(40) and the trob flag."""
    return index | (rng.randrange(41) << 4) | TROB


def enter_room(room, cells, rng):
    """KeepTime 2:4fd0's scan of a room (cells 0-29): the words its moving
    scenery starts with. `cells` maps cells to (kind, current word). The
    serpent and the face keep their words; crystals and gargoyles are set
    up again (crystals stop at nine, 9:2070; gargoyles count on from
    9:1d84's start)."""
    words = {}
    index = GARGOYLE_FIRST.get(room, 0)
    for cell in range(30):
        kind, word = cells.get(cell, (0, 0))
        if room in TROB_KINDS:
            if kind == TROB_KINDS[room]:
                words[cell] = word
        elif not word & TROB or room != CRYSTAL_ROOM and room not in GARGOYLE_ROOMS:
            continue
        elif room == CRYSTAL_ROOM and index >= CRYSTAL_LIMIT:
            continue
        else:
            words[cell] = trigger(index, rng)
            index += 1
    return words
