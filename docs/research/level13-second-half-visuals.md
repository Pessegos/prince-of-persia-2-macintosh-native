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
whole-room traversal 3:1c64 (`_native_scene`), commands and pixels. Level 13
room 4 needs the (Temple.rsrc, Kid.rsrc) artwork tuple for its CUST flame
(SHAP 4077); with it, its export also equals the native traversal.
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

## 3. The altar plate's click

PushPlate 5:2480-24a2 skips AddSound(27) for a dead Kid's pose 185 and for a
plate in native room 4 of level 13 (a5-0x34aa = 4, LEVL 0x218a = 13): the
hidden plate 4:12 the shadow steps on makes no sound. The port clicked.

## 4. The flare covers the shadow

DrawTempSacredFlame 10:2d5a runs in a cell's pass 11 under the full room clip
(10:2d7e). An ordinary record stays a pass-11 back item, behind the
characters. A flare (counter bit 0x80) draws a5-0x2b7c[counter & 0x7f] with
the CUST record's pass word set to 1 for the call (10:2dbe-2dce): a front
item, dumped after the objects, so the tongue covers the shadow taking the
flame, as the user's capture of the original shows (pose 15 of SEQS 232,
record 16). The port drew every record behind the characters; a flare is now
drawn in `Temple.after_actors`.

Not modelled: whether the original repaints the flare's pixels outside the
ordinary flame when the flare ends (the front item is drawn under the full
clip; what restores those pixels was not traced).

## 5. The temple exit's top

DrawTempExitMovable 10:069a clips the exit SHAP (3583) to row*120-10
(10:06c6-06d2, intersected with the room clip) and lifts it min(phase, 0x4d)
pixels (10:06f6-0708): it stops 77 pixels up, not 79. The port clipped it at
row*120+1, so the closed door lost its top eight rows (native 113 against
121 in room 32), and drew the open door two pixels higher. A per-phase native
comparison (`recover_room`, phases 0-79 of every exit of levels 10-13,
480 cases) now matches the port's commands exactly; the temple's stone gates
(1,968 cases) and the ruins' gates and exits already did. The caverns' gate
3562 differs on purpose (its clean-cut cap, `pressure_drawing_commands`).

## 6. A sword behind the next cell's front pieces

GetCharAttach 4:2a8e copies the frame's attachment record (type, shape, X
and Y offsets) to a5-0x521a (4:2b92-2ba6). For type 1, the sword, 3:0e14
adds it as its own object (AddCharObj 3:0130, kind 3 for the Kid from
3:08aa, 9 for an opponent from 3:09f6) and, unless animation state
a5-0x5046 is 9 (3:0e6c-0e72), marks the cells of its rectangle for a front
redraw (MarkBufsForRect 5:19f8 with MarkFRedraw, 3:0e74-0e80). The flask
(type 3, 3:0e9c-0ee2) is marked the same way, always. The body has its own
setup (3:0ac8 from 3:0d88, marked at 3:0daa-0db6); 3:0ba4-0d18 is the hit
star's. MarkFRedraw 5:48e8
unites each cell's marked rectangles, clipped to the cell. The port masked
the character's layer, sword included, with the front pieces of the cells
of the body's rectangle only: a guard's blade reaching into the next cell
was drawn over that cell's pillar. In room 32 a guard at column 8 facing the
Prince by the checkpoint (column 9) now has the tip of his sword behind the
front of pillar 3540, as the code draws it. `composite_actor` adds the
cells of the sword's rectangle (`GuardArtwork.draw` returns it; the Prince's
comes from his attachment). Not modelled: the sword's own place in the
object sort (the port draws it in its character's layer), the hit star's
and the flame's rectangles (the flame is a separate layer).

## Checked, no difference

- Every exit, gate and plate of levels 10-13, every phase: `recover_room`
  against `pressure_drawing_commands` (section 5).
- Front pieces per dirty cell, levels 10-13 (`tools.probe_foreground_cells`
  at rest, `--pressure`, `--variants`): 98,400 cells, no missing, bleeding
  or extra pixel. Temple candles (`tools.probe_temple_candles`): 128 rooms,
  no mismatch. What hides the Prince in rooms 32, 2, 28, 13, 15, 29 and 4
  (`tools.probe_actor_cover --level 13`): 1,651 frames, none missing or extra
  (moving objects, items and the exit frame are counted apart by design).
- The flask: DrawFlask 3:46fc reads PIEC 3500 +0xd6 and +0x4c0, which are the
  same in Caverns, Ruins, Temple and Final, so the bubble offsets verified on
  level 3 hold in room 29. Its ink choice (3:48a0) and quiet phases match.
- Room 32's bottom strip: every redraw path (DoCleanCut 2:606e -> 3:1a9c ->
  RedrawCellFast 3:1c64, used for cuts and rebirth after PrepCut 2:532c sets
  the room and calls 3:1ab0; the dirty redraw 3:3260) runs GetBelowAry per
  row, and the native code draws dark wall 3509 for all ten columns. The
  lighter columns 0-4 in the user's capture are not explained by the code.
- Doors over guards (pair 9/10): no front piece of an exit cell exists in
  rooms 32 and 28, ClipChar's exit clip (4:416a) is the Kid's only, and the
  exits are back items; nothing in the code draws a door over an opponent.

## Room 29's music

SpecialMusic 5:5388 (called from 5:4ff8 for the room's ambient song) returns
song 253 in level 13 for native rooms 4 and 29 (5:543c-545a); in room 4 a
Kid of actor type 1 with more than 2 HP gets 252 instead (5:53ec-5416). The
port plays the same (`Temple.ambient_audio`). No other level 13 code tests
room 29; its only mechanism is the flask.
