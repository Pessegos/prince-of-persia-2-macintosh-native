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
retains the existing filename `caverns_entry.json`, now version 11:

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

Version 10 recovers the upper border's separate drawing context from
RedrawCellFast (3:1cb6-1cda): select the upper room, make the current room its
lower neighbor, load the last-row neighbor arrays, then draw at row -1.
GetCells (5:0a4c-0aa2) and GetObject (5:053e-055c) use scenery floor 1 with
zero foreground/background when that upper room is absent. GetBlock's wall 20
is correct for collision but was not the border drawing default. Version 9
consequently pasted SHAP:3537 across the top five rows of unlinked rooms,
including Room 5. Native GetCells/neighbor-array execution now supplies the
border records, producing floor pieces 3525/3523 instead. Physics and LEVL
links are unchanged; the correction applies to every room and exported variant.

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

Older exports request an asset reimport: version 10 lacks the live lava tables;
version 9 lacks the native upper-border
context, version 5 lacks per-command draw-cell
metadata, version 4 lacks the full-room repaint mode, version 3 lacks the
corrected cell drawing and live torches, version 2 lacks flask library identity,
and version 1 supplies only the entrance. F3 can preview each room, placing
the Prince on a basic floor tile from LEVL rather than using per-room positions.

## Lava

The Macintosh/port lava recordings show native Room 6's bottom-row pool.
The port previously drew only SHAP:3614: a continuous static lava fill.
DrawCaveLava (8:221e-24ba) also paints SHAP:3615, whose opaque rock pixels
cut into that fill, with animated bubbles behind and in front of the cover.
Reconstructing those layers with the original resources reproduces the
fragmented appearance in the Macintosh recording. It is not evidence of an
emulator fault; whether the original artists intended that appearance cannot
be established from the rendering code alone.

Version 11 imports the original DATA bubble sequences, 22 scheduled events,
death drawing triples and PIEC offsets. AnimLava (8:31fe-33ee) cycles through
phases 0-22, retaining active bubbles on reset. Bubble marker -2 moves that
bubble to the front pass and advances past the marker. The portable state
matched 6,000 native updates across all three initial phase seeds and the
Prince's death branches; drawing command order/coordinates/mirror flags
matched another 216 native frames in both facings.

CheckLavaBoil (8:33fc-348c) tests the supporting-foot column, not the sprite's
anchor or bounding box. Tiles 23/24 use foot-X limits `51*column +43/+36`,
FRAM flag 0x40, and absolute Y strictly greater than `120*row +76`.
Native execution matched 3,420 contact cases. The predicate is shared by all
five pools in the level, including camera-border copies; no room-specific
death rectangle is introduced. Normal jumps above the surface remain safe.

GetLavaInfoHnd (8:34a6-358e) selects SEQS:116 and cue 70 for the Prince.
Airborne modes 3/4 use drawing sequence 0. Grounded entry uses sequence 1;
Rnd(3)==0 additionally retains it for a longer continuation in which the
Prince re-emerges. Rnd(3) includes 0-3, so this branch has probability 1/4,
not a separate emulator-dependent animation. Facing sets the native mirror
flag. Non-Prince actors use drawing sequence 2, SEQS:115 and cue 69; those
tables are recovered but skeleton gameplay is not yet integrated.

Cue 68 occurs at the native sequence limit. DrawKid/DrawChar
(3:089e/09ea) suppress the ordinary actor sprite for death cause 5, letting
the lava draw the body instead. SEQS:116's -11 operand 1 separately selects
death music via SetKidDeathMethod (4:3196); death cause 5 and music selector 1
must not be conflated. The existing dead-pose retry/prompt mechanism resumes
after the original sequence reaches pose 185. Tests cover boiling without
input, fatal contact, safe height, rare continuation, layer order and retry.

### Port Visual QoL

Gameplay enables enhanced lava through `CavernState.configure_lava`.
The original `LavaPool` mode remains the default reference for native-rule
comparisons; `enhanced=False` also selects it when configuring a cavern.
This is an explicit presentation deviation, not another recovered Mac rule.

At the ordinary cycle boundary, enhanced mode wraps and processes phase zero
in the same update instead of freezing all active bubbles for one update.
Individual bubble frames still advance at the game cadence. Character-death
phases, including the phase-three reset, limits, sounds and Rnd(3) branch,
are unchanged. All five visible pools were checked for 100 consecutive frames
without a repeated image; the native pause remains covered by reference tests.

For presentation, enhanced mode substitutes a shallow recessed pool for the
SHAP:3615 rock-cut cover. `pop2/lava_recess.json` contains the new artwork as
sparse rows of cavern-palette indices, with transparent pixels outside the edit.
It was adapted from the user-approved visual concept at the native pixel grid,
retaining the irregular silhouette, dark-red crust and shallow rock cut faces.
It is port artwork, not an extracted or recovered Macintosh feature. The file
does not include an original resource fork, palette or surrounding room image.
No concept generator, external reference file or new asset import is needed at
runtime. The imported cavern palette supplies every opaque pixel's color.

The 140 x 33 overlay retains the original bottom anchor; its opaque region
stays inside the old 140 x 30 pool bounds. The original base supplies the
untouched exterior floor. One cached surface serves all five pools and their
camera-border copies, without room-specific coordinates. Nearest-neighbor
presentation retains the native square pixels. Original bitmaps are unchanged.

The filled surface is drawn
BEFORE both bubble passes; keeping it between those passes hides rear bubbles
because it is more opaque than the original cover. Rear/front bubble order,
counts, positions and sequences are unchanged. A pixel regression test
confirms that the filled surface no longer erases a rear bubble.
After animation, enhanced mode restores only the near-side floor. A cached
mask selects rows below each column's last molten pixel, including the dark-red
crust as molten and recognizing the brighter orange shades. The saved pixels
come from the frame immediately after painting the static pool, so transparent
parts of the overlay retain the existing room floor as well. The liquid,
back rim and rising bubbles remain unobscured. This prevents bubbles and death
splashes from repainting the rock in front of the recessed cavity without
editing the approved artwork. Native reference mode has no additional pass.
Tests compare 100 boiling frames and both facings of all three Prince death
branches for every pool and visible camera-border copy: only this floor mask
can differ from the previous uncut rendering.
This retains the game's palette and bubble artwork without the cover's
rock-cut gaps.
Death body/splash triples and mirror flags remain unchanged; only the pool
surface behind them differs. Pixel checks
confine the change to the original pool bounds. Contact geometry, fatal Y,
retry behavior and the 1/4 grounded-death continuation probability are intact.

## Stone Gate Collisions

The supplied Macintosh/port door recordings show Room 17, row 2/column 7.
The port treated tile 4 as floor in cavern wall collision, allowing the Prince
to run or step through the closed stone gate.

GetBarrCode (4:531c-532c) maps tile 4 in environment 3 to barrier type 5.
GetLeftBarr/GetRightBarr (4:541a/547c) use the original DATA offsets 18/0,
giving scene X planes `51*column + 40` and `51*column + 72`. The Room 17 gate
therefore occupies X 397-429 for collision; no room-specific wall is added.

Gate admission (4:5b0e-5ba2) reads the low foreground byte in quarter-phase
steps. It blocks when `2*(phase >> 2) + 11 < clipped_body_height + 13`.
The body height comes from GetCharEdges' viewport-clipped rectangle, not a
fixed standing height or a universal phase-104 threshold. Actor 1 and selected
SEQS:68 bypass this test; actor types 7/8 add 46/33 to the tested height.
CheckCollide's actor-11 exemption also applies to the collision sweep.

The portable predicate is shared by the cavern collision sweep and
GetBarrDistances' cautious-step subset. Existing bump selection handles a
blocked run; ordinary wall behavior, other environments and room links are
unchanged. Native execution matched 12,288 gate-admission cases and both
Room 17 barrier planes. Tests cover closed/open/partial phases, low versus
standing poses, selected-sequence exceptions, both facings, all nine native
level-three gates and running/Shift-walking at the recorded gate.

This implements collision with the current gate phase. Gate buttons, timed
opening/closing, and GateBarrToStandUp's separate crouch-rise controller are
not recovered by this change.

## Flasks And Entry Door

The health bottles in the bottom strip are a separate Kid.rsrc HUD library.
DrawKidMeter (3:4914, 4984-49d4) uses X = 3 + 12*index, Y = 368;
DrawOppMeter (3:4c08-4c30) uses X = 495 - 12*index. These are coordinates
inside the visible 510-pixel game. The host centers that image at X = 1 in a
512-pixel composition buffer, then display/F8 crop it back to 510 pixels.
HealthArtwork formerly drew directly at the native X in the larger buffer,
shifting both meters one pixel left after cropping. Both now include the
room origin. Icon shapes, spacing, palette and last-life blinking are unchanged.

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

### Loose Floors

LEVL:2002 contains 15 kind-11 tiles. The entrance shows one at row 0, column 7
and another through its upper-room link (room 32, row 2, column 8). The same
controller handles every tile, including tiles outside the currently drawn room.

CheckPress (5:127e-13d6) uses the supporting foot column, FRAM bit 0x40,
animation mode and an eleven-pixel floor-height tolerance. Catch pose 79 and
climbing poses have separate above-floor checks. BreakLoose (5:2710) preserves
an existing phase instead of restarting it on repeated contact. AnimLoose
(5:446a) advances twelve collapse phases, or four warning phases after a distant
shake. ShakeEm (5:2876) handles nearby actors and the third repeated shake;
SEQS operations -13/-12 request the current/upper row respectively. The
dispatch table at 4:2c70 maps -19 to SetCharFloor (4:2f72), not a shake.
The first implementation misidentified those operations and wrongly shook
the floor on completing SEQS:235; the corrected runtime preserves floor
alignment without emitting a shake.
Executing native AnimChar for -12/-13/-19 in all three rows confirms the
shake-request mapping. CheckAlert consumes the last request once per update,
not a queue of shakes; later operations replace earlier ones.

FrameAdv (2:622c) moves existing debris before advancing loose tiles. MakeRubble
(5:2b10) adds eight units of velocity below speed 60, crosses downward room links
with a 365-unit physical cut, and uses the original impact classifications and
sound cues 28/26. A falling actor strikes a loose floor with its own velocity;
Falling (6:01ee) halves that velocity and retains the airborne state. Crushed
(6:28f0) supplies the ordinary Prince's one-life damage and SEQS:52 recovery.
Special actors and pressure-plate/gate responses remain separate recovery work.

DrawMob (5:3128-32e0) also marks the next column's floor for repaint at the
object's bottom row and, when different, its top row. ComputeMobRect uses
height 43, width 87 and bottom Y+1. The portable renderer now applies the
exported DrawFloorBuf commands inside that rectangle after drawing debris,
restoring ordinary foreground over the repainted pixels. This prevents the
first two falling poses from crossing the neighboring solid floor. Native
execution matched the selected repaint cells for 4,530 column/Y combinations.

Version 9 exports native drawing variants for shaken/removed floors and their
landing cells, including DrawHalf/DrawFloorBuf repaint commands and all entry
closure phases. AnimLoose's ClearCaveBelowFloor (8:39b8) also removes the native
decoration flags below the detached floor. DrawObjCaveLoose (8:2bb4) supplies
SHAP 3557 and 3604 at the original anchors; debris is painted before actors and
foreground. These changes reuse the original room drawing routines, not a
rectangle painted over the hole. Restart restores the tiles; pause freezes them.

Portable debris phases, positions, full terrain/foreground state and ordered
sounds matched 3,150 native updates (all 15 floors, initial velocities 0/1/40,
70 updates each). CheckPress matched 3,840 pose/mode/facing/height combinations.
The diagnostic supplies drawing bookkeeping, stubs skeleton/plate responses and
the actor-hit loop, and substitutes an equivalent LEVL read for one unsupported
68020 addressing block. Thus it validates those controllers, not the missing
gate/plate mechanisms or complete collision parity. The user's entrance video
was also checked visually for the shaking strip, opening and falling stone.

### Sword-Wall Contact

The shared actor collision bounds now include the native attachment extension.
GetCharEdges (4:5cbc) calls 4:5e6e: when sword mode is 1 and the actor is not
type 7/8, a nonzero AFRM attachment extends the facing edge by `max(0, X - 3)`.
The drawing rectangle stays unchanged; this width belongs to barrier detection,
not foreground clipping, floor contact or the sword's visual bounding box.
Executing the original size routine agrees with the portable extension for
all 110 Kid AFRM entries, both facings and actor types 0/2/7/8 (880 cases).

In the entry room's lower corridor, the ready pose has AFRM X = 22. Its extra
19 pixels contact the right wall after SEQS:55. CheckCollide1 (4:5586-55ee)
and Collide (4:589e-5a54) correct X by -4, select SEQS:64 and request sound 10.
That resource's -10/+6 steps finish at X = 81, rather than the old X = 89.
The Macintosh comparison shows the same short recoil and final pose. The rule
is shared with ordinary guards and other environments, without room overrides.

This is the scenery foundation, not a completed playable level. Original room
transitions and the common movement runtime are available. Cavern-specific
floor classifications, gate and plate controllers, spikes,
crushers, potion behavior and colors, special draw modes and
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
not certify all hazards, object interactions or completion of level 3.
`tests/test_loose_floors.py` covers pressure, warnings, detachment, forced falls,
room-link traversal, impacts, decoration changes, ordinary crushing, dynamic
floor/climb repainting, pause and restart. Its imported-resource cases are
skipped on CI; the pure controller cases run without proprietary game files.
