# Level 13 after the checkpoint: visual comparison with the original

Started 2026-11-27 from the user's captures of the original and the port
(level 13 after the only checkpoint, native room 32 tile 19). Native rooms are
one-based. The second half is rooms 32, 2, 28, 13, 15, 29 and 4 (the altar).

## 1. The bottom strip of rooms without a lower link

The user's capture of room 29 shows wall bricks in rows 340-365 behind the
gargoyles; the port showed whatever the previous room had left there.

- RedrawCellFast 3:1c64 calls GetLeftAry 5:0b50 once, then per row GetAboveAry
  5:026a and GetBelowAry 5:03bc, and per cell GetCells 5:0a4c before the
  drawers. GetBelowAry asks GetObject 5:0470 for the row below with default
  kind 0 (5:0426); for the bottom row that is the lower room's row 0
  (a5-0x4fba, -0x4fb4). The leftmost entry's default is 20 only when the lower
  room exists (5:03ee-03f8).
- GetObject 5:053e-05b4, room 0: the caller's kind, foreground 0 and
  background 9 in the temple (5:056c), 0 in the caverns, ruins and rooftops,
  `(column & 1) << 8 | 9` elsewhere.
- The temple draws a kind-0 cell below the bottom row as back wall 3509 at
  Y 460, clipped to 340-365.

`recover_room` supplied these inputs from Python with `LevelMap.tile`, whose
missing-room cell is GetBlock's collision default (wall 20): nothing was drawn
in the strip. It now runs the native readers in RedrawCellFast's order, and
PieceRightId 5:08c4 is no longer stubbed (an early lookup with the same wall
default). Exports carry `cell_readers: 1`; `run_game` asks an older temple
export for a reimport ("needs the native bottom strip").

Check: every room of levels 3-14 drawn cell by cell equals the native
whole-room traversal 3:1c64 (`_native_scene`), commands and pixels, except
level 13 room 4, which that audit cannot draw (its CUST flame needs Kid.rsrc).
Changed pixels against the previous export: level 11 rooms 11 and 30 and
level 13 rooms 2, 15, 23, 26, 28, 29 and 32 (8,575-12,275 px each, the strip).
Other changed rooms and the loose-floor variants of levels 3, 7-13 differ
only in commands that draw no different pixel. The ruins exports hide their
crevices on purpose (`hide_crevices`), so they never equal 3:1c64 there.

## 2. The flash when the shadow takes the flame

The original turns the whole room white, the death message included; the port
kept every black pixel, a one-bit outline of the scene, and wrote the message
in yellow after the flash.

SetPaletteToColorIdx 3:4fbc sets palette entries 1-254 to the colour and
leaves 0 (white) and 255 (black). No SHAP of Temple, Final, Kid, Prince,
Birdhead, Guard, Skeleton, Head, Jinnee or FlameSword uses index 255, so every
black pixel inside the room is another entry and takes the colour. The flash
now fills the room area except pure white, and the death message (also inks
1-254) is flashed before it is drawn. The black around the room stays.
