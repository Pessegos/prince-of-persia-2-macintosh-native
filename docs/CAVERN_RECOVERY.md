# Cavern Recovery

## Original Layout

Level 3 is LEVL:2002, environment kind 3. Its 32 rooms form a connected, flat
layout through the original left/right/up/down links. The entry remains native
room 1, row 1, X 226, with SEQS:5 selected by SetKidDefaults (2:5e34).
No room links or geometry are copied from the DOS maps.

`python -m tools.render_cavern_map` writes `rendered/level3-macintosh-map.png`
from these links and the recovered scenery. Labels use one-based resource room
numbers, not an assumed linear gameplay route. The map includes every room,
including side paths outside the shortest route.

## Scenery Export

During import, `tools.extract_caverns` executes CODE:3/8 drawing routines against
the original LEVL, Caverns PIEC and SHAP resources. It records background passes
0/5 and foreground pass 1 for every tile of every room. The portable export
retains the existing filename `caverns_entry.json`, now version 6:

```text
rooms[zero_based_room] = [layer, shape_id, x, bottom, draw_mode, row, clip_rect, library, draw_column, draw_row][]
clip_rect = [top, left, bottom, right]
library = 4 (Caverns) or 1 (Prince flasks)
```

The export captures native clip rectangles, including the SectRect calls at
8:1752/1ca4/1f86 and EmptyRect at 8:20a6 used by gate drawing. Runtime clips
both sprite pixels and actor-occlusion masks to those rectangles. Resources and
decoded shapes are cached across room changes. No Macintosh executable is
retained or executed by the game itself.

The exporter follows DoCleanCut (2:608c-6096): set A5-4832 to 1 before building
a complete room. GetCells (5:0abe-0ac8) then copies the full-room clip instead
of ComputeClipRect's dirty-cell bounds. The drawing routines still intersect
their own gate/piece clips. It follows the bottom-up cell order and
upper-room border from RedrawCellFast (3:1c64-1d38), restores BF midpoint fields
after admission, and retains background-record rectangle unions. DumpTable
(3:2c1e-2c68) paints back walls before floor/pillar bodies.

Version 4 incorrectly built a complete room in incremental cell-redraw mode.
Its cell clips prevented the exit-right piece from repainting the threshold
over the exit-left floor. Full repaint restores the four-row strip at the
door's base, while retaining the right floor in front of it. Comparison with
the user's Macintosh capture at native resolution finds no unmarked scenery
differences in the entrance, excluding the independently animated torch and
the Prince. This is a native repaint-mode correction for every room, not an
entrance-only overlay or changed sprite.

The former PieceRightId stub (5:08c4, column advance at 0904) incorrectly returned
the current tile. DrawCaveWall (8:1852-1876) consequently skipped shadows behind
pillars. Correct neighbor lookup restores the missing pieces from PIEC without
adding room-specific artwork or positions. The entry-room columns, platform
joins and ceiling border have been compared visually with the Macintosh route.

Older exports request an asset reimport: version 5 lacks per-command draw-cell
metadata, version 4 lacks the full-room repaint mode, version 3 lacks the
corrected cell drawing and live torches, version 2 lacks flask library identity,
and version 1 supplies only the entrance. F3 can preview each room, placing
the Prince on a basic floor tile from LEVL rather than using per-room positions.

## Flasks And Entry Door

Flask BF items now retain library 1 and use Prince.rsrc SHPL:3000 / SHAP:3001-3033,
not Caverns rock shapes. LoadFlaskSet (3:5614, 5630-5658) relocates CTBL:3000
to palette index 224. Monochrome masks use the descriptor's ink color and the
whole-bitmap RLE in hGetNShapeItem (17:5f78-5fa0), distinct from color row RLE.
Executing that native loop independently agrees with the portable decoder for
all 18 compressed monochrome flask shapes. This fixes the wrong shape library
and mask decoding. The user subsequently identified incorrect flask colors;
palette fidelity remains open, as do collection, animation and health upgrades.

FirstFrame (2:5f36-5f90) finds the first exit-right tile (kind 17) in the starting
room. CloseExit (5:25aa) starts phase 79/state 4; ATMExit (5:15bc) subtracts the
state-indexed A5 table at -45fc. The imported entry phases are 79 -> 47 -> 0,
with effect 20 on underflow, not a video-derived delay. A separate execution of
ATMExit verified both updates, preservation of upper foreground flags and the
final cue. Each phase's scenery is drawn by the native routines during import
and stored under `entry_exit`; runtime only advances portable session state.
Restart restores the initial phase. The two portal tiles are not pressure plates.
This is entry closure only, not a general exit-opening controller.

The rooftop waterline previously clipped actors in cavern Rooms 16 and 19
because their room IDs matched the docks. Composition now requires environment
5, as in ClipChar (4:4218-4228). Cavern actors retain their lower pixels.

Version 6 retains each command's drawing cell. Runtime uses the actor's bounds
to select cell foreground masks; older exports fall back to intersected-row
masks. MarkPeelForeBufs (3:0428) and MarkBufsForRect (5:19f8) explain dirty-cell
selection, not the complete character clip. The first two clipping revisions
tested that selection in isolation and missed the user's climb defect. In the
affected rectangle the cell-mask revision produces the same alpha as the
previous row-mask revision; it cannot remove the exposed turban by itself.

Composition now also implements the ordinary cavern branch of ClipChar
(4:4230-43de). GetCharEdges (4:5cbc-5e52) supplies drawn columns and top row;
IsSpace determines whether both edges are behind terrain. Right-facing hangs
and stationary poses 79/81 have separate tile-check exceptions. Except for
physical row zero, clipping requires the drawn bottom below `row * 120 + 5`
and the top coordinate strictly greater than that boundary minus 28. Tumbling
and actor types 7/8 bypass this branch. This changes drawing only, not movement
or collisions.

The original M68K GetCharEdges and ClipChar were executed for 61,440 cases:
all 32 level-three rooms, both facings, three rows, ten pose/mode pairs,
eight X positions and four top-edge offsets. The portable clip top matched
every case. Shape-size lookup and initial QuickDraw rectangle construction
were supplied from the same inclusive sprite bounds; terrain lookup, column
calculation and ClipChar itself ran natively. For the recorded entrance climb,
pose 136 has bounds `(106, 218, 125, 302)` and native clip top 245. The new
rendering regression checks that this upper slice contains scenery only.
Pose 137 is not clipped by that branch, so this is not a blanket hide-during-
climb workaround.

This verifies the ordinary top-clip branch, not complete frame parity. The
user's subsequent recording showed a separate defect at pose 137: red pixels
were still visible through the near floor at Y 231-236. Comparing equal poses
(Mac approximately 2.95 seconds, port approximately 2.25 seconds) established
that ClipChar alone was insufficient.

Version 7 executes native DrawHalf (3:3480-35a8) and ComputeHalfRect for every
pose 135-144 in all 32 rooms. The resulting shapes, colors, positions and
QuickDraw clips are exported separately under `climb_redraw`; static scenery
is unchanged. QuickFloor (2:69b6-69e2) selects only a right-facing climb's drawn
left column and top row, even after SEQS changes its physical floor row.
For pose 137, entry cell (2, 1) emits SHAP 3525 at (104, 245), with native
clip (top 229, left 104, bottom 240, right 128). Those floor pixels are painted
over the actor, followed by ordinary foreground inside that rectangle, as in
RedrawCell (3:1eb8-1f30). This preserves pillars instead of painting the floor
strip over them. Both the pixel-leak regression and the foreground-order test
fail when their respective drawing steps are omitted.

Version 8 adds the ordinary-character QuickFloor/DrawFloorBuf path, exposed
by the next upper platform in the user's second comparison. Before the catch,
pose 79 has bounds (304, 102, 333, 191). ClipChar is disabled because the
drawn left edge is over air; DrawFloorBuf must still repaint the solid floor
in drawn cell (6, 0). The native command is SHAP 3528 at (315, 125), clipped
to (top 100, left 315, bottom 125, right 357). Omitting it exposes the turban
through the rock for one pose.

The extractor now executes DrawFloorBuf (3:371c-39c4) with dirty-cell clips
for every room. Runtime applies QuickFloor's ordinary-character selection
(2:69e6-6ac4) to jumping, falling, wall-hanging, cross-row mode 5 and poses
79/81. It clips the emitted floor pixels to the actor's native visible
rectangle, then restores ordinary foreground over that repaint. Right-facing
poses 135-144 retain the separate DrawHalf path. No room-specific movement
or position workaround is involved. Executing native QuickFloor over 1,440
pose/mode/facing/bounds combinations produced the same selected floor cells;
the integrated upper-platform test fails without the repaint. The first
entrance-climb regression remains covered as well.

Special entry/exit rectangles, projectile/special-actor drawing modes and
full dirty-buffer persistence remain separate recovery work. The two aligned
video defects are addressed; complete level-three frame parity is not claimed.

## Torch Animation

Version 4 records visible flame fragments separately under `torches[room]`,
including native draw commands and the originating room/cell. Static previews
retain their exported flame; gameplay caches scenery without that flame and
paints the current frame before actors and foreground. The nine SHAPs are
3581-3589, selected by DrawCaveTorch (8:2ae8-2b90) at the PIEC position. Torches
with foreground bit 0x10 retain the unlit shape and are not animated.

TriggerTorch (5:1ffa-2088) initializes Rnd(8), inclusive. ATM Torch (5:1446-1498)
advances visible torches through CaveGetTorchFrame (8:3b4e-3b78): choose 0-8;
if it equals the previous frame, increment and wrap at 9. A diagnostic executed
the original routine for all 81 previous/random pairs and agrees with the
portable selection. This reproduces the selection policy, not the original
machine's random seed. Session state preserves upper foreground flags and
updates each logical torch once per simulation tick, even when its pixels are
split across several cell clips. Pause freezes the animation without rebuilding
room scenery. Restart reinitializes it.

## Current Boundary

This is the scenery foundation, not a completed playable level. Original room
transitions and the common movement runtime are available. Cavern-specific
floor classifications, gate and plate controllers, loose floors, spikes,
crushers, lava, potion behavior and colors, special draw modes and
skeleton enemies still require semantic recovery and integrated tests.
The ordinary-guard decoder does not reinterpret skeleton spawn records; the
preview encounter host omits those actors until their implementation exists.

The entry-door phases and flask rooms have received focused visual checks;
the complete route and all special drawing modes are not yet validated.
The flask-library defect exposed by the user's Macintosh recording is fixed.
Static row masks still do not implement the complete native actor-clipping
pipeline. See [Route audit](LEVEL3_ROUTE_AUDIT.md) for reference moments and
the remaining recovery order. Room coverage alone is not visual fidelity.

`tests/test_caverns.py` checks clip pixels and masks, all 32 exports, every
original map link, the generated map, F3 room placements, flask libraries and
mask decoding, entry closure/restart, cross-environment water clipping,
missing pillar shadows, upper-border records, clean-cut setup, threshold overlap
through every closing phase and torch selection/pause. These checks do
not certify hazards, object interactions or completion of level 3.
