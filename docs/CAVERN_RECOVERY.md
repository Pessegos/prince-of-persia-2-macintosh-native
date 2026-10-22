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
retains the existing filename `caverns_entry.json`, now version 14:

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

Import reuses one bounded recovery machine, restoring its initial working RAM
and CPU registers for each draw while retaining compiled CODE. Relocated A5
jump-table stubs let Unicorn execute internal calls directly. Only modeled
primitive entries invoke Python; unsupported instructions still fail and each
native call retains its instruction budget.

The ten climbing poses use the original DATA rectangles at A5-4b46.
ComputeHalfRect (3:3690-36fc) varies their top/right bounds while retaining the
same left/bottom edges. The widest native pose supplies the narrower recrops;
its kind-6 bottom extension is preserved. Pose 141 still executes separately
because DrawCaveLoose (8:25fa) has a special branch for it. Unrecognized table
geometry or a changed branch signature falls back to executing all ten poses.
Loose-floor combinations, gate states, ordering and original clip values are
unchanged. Fresh-import tests compare the complete scenery, recorded demo,
intro, ending and enemy-profile exports against the installed reference.

These optimizations do not change the export format or require existing
installations to reimport. On the local Python 3.10 test machine, complete GUI
import fell from about 365 seconds to 124 seconds, then to about 28 seconds
with the same HFS image and identical exported data. These are local
measurements, not fixed import-time guarantees for other PCs.

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
the Prince on accessible standing terrain from LEVL rather than using a
table of room-specific coordinates.

### Safe Developer Entries

Some ordinary floor markers belong to sealed rock pockets, not the playable
route. F3's level-three selector groups local non-wall space and checks for a
real room-link opening before choosing a standing tile. Vertical connections
require air or a loose floor in the upper cell, rather than passing through
solid floor. Low closed gates and lava/spike obstacles do not connect regions.
This is a developer-placement heuristic, not a gameplay pathfinder or a change
to Macintosh collision rules.

The selector prefers ordinary stable floor near the center. If all such floor
is sealed, it can use stable decorated terrain, including the flask/torch
platform in Room 32. It does not spawn on buttons, loose floors or hazards.
Room 21 retains the previously requested lower-floor preference. Original
sealed-pocket placements change in Rooms 3, 12, 15, 19, 28, 31 and 32.
Live gate/loose-floor state is read without resetting or mutating the world;
explicit-coordinate warps and level-1/2 entries remain unchanged.

Tests cover sealed components, blocked room links, closed/open gates, loose
floor openings, stable fallback tiles and deterministic read-only selection.
Resource-backed checks audit all 32 destinations, idle stability and actual
cautious-step movement after warping. The entrance keeps its normal level
entry sequence rather than using the preview-placement heuristic.

## Retained Scenery And Whole-Level Audit

The transparent pockets at the left edge of wall SHAP:3546 are not missing
exported pieces. DoCleanCut (2:606e-60c2) builds and paints a new room without
first erasing the scenery buffer. Draw mode 16 skips zero pixels, whereas mode
0 copies black as well (17:5ae6-5b1a). Unpainted pockets can therefore show
scenery from more than one room ago. A fresh black-backed preview is not a
path-independent reference for those pixels.

The user's Room 28 Macintosh capture matches a retained-scenery replay of
Rooms 26 -> 27 -> 28. Its middle pocket retains the original SHAP:3502 texture;
the upper pocket also retains part of Room 26's torch artwork. This explains
why matching only the room's exported commands left black gaps in the port.
It does not establish that this dependency was intentional artwork design.

`CavernRoom.retained_mask` records pixels untouched by both scenery layers.
`LevelRenderer.enter_room` fills only those pixels from the previous scenery
snapshot. Ordinary room lookups and immutable art caches do not advance that
history. The live snapshot includes animated scenery before drawing actors,
menus or HUD. Within the same room, gate/floor variants keep the entry underlay
instead of accumulating previous variant frames. Revisits use the newly
preceding scene, not the room's first cached appearance. No room-specific
texture placement, collision change or resource reimport is required.

To repeat the static audit with the original executable resource fork:

```powershell
python -m tools.audit_caverns --program "path\to\Prince of Persia 2.bin"
```

The reference executes original CODE:3 1c64 as one whole-room traversal,
including native GetCells/neighbor preparation and upper-border handling.
It is separate from the optimized exporter's Python cell traversal. The
audit checks admitted command order, IDs, coordinates, clips, transfer modes
and libraries against the installed export, then compares static compositions
and retained scenery on every directed LEVL room link.

The current original resources match all 3,586 commands in 32 rooms and all
86 directed cuts, with zero differing static pixels in the checked scope.
Eleven rooms have some unpainted scenery pixels; retention is a general rule,
not a Room 28 patch. Results and native/port/diff PNGs are written to
`rendered/cavern-background-audit/`, with source hashes for reproducibility.

Scope limits: the audit shares the SHAP decoder and modeled drawing primitives
with import; it is not an independent Macintosh rasterizer. Actor sprites
(including skeletons), flask rectangles, animated torches, live lava/its
intentional overhaul and HUD are excluded from pixel comparison. Dynamic
gate/floor states have separate tests; this audit does not certify every
animation frame or gameplay state. The supplied Room 28 capture additionally
checks the real-rendered retained pockets along the recorded approach.

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

HitFloor (6:02aa-02b8/0326-0344) has a separate lava entry: landing on tile
23/24 calls GetLavaInfoHnd before ordinary impact damage or landing alignment.
It bypasses CheckLavaBoil's pose, surface-height and horizontal admission
limits, preserving airborne mode 3/4 for the death variant. Native execution
confirmed this dispatch in 120 cases across both halves of all five pools,
both facings and six incoming velocities. The Prince host queues that contact
for the same frame's lava update, without advancing the death animation early.
This prevents maximum-speed falls from selecting flat impact death (SEQS:22)
and leaving a corpse on the pool. Regression tests cover all five pools in
both facings, a continuous Room 3 -> 10 fall and the eventual retry prompt.

GetLavaInfoHnd (8:34a6-358e) selects SEQS:116 and cue 70 for the Prince.
Airborne modes 3/4 use drawing sequence 0. Grounded entry uses sequence 1;
Rnd(3)==0 additionally retains it for a longer continuation in which the
Prince re-emerges. Rnd(3) includes 0-3, so this branch has probability 1/4,
not a separate emulator-dependent animation. Facing sets the native mirror
flag. Non-Prince actors use drawing sequence 2, SEQS:115 and cue 69; the
level-three skeleton host now uses these tables and suppresses its ordinary
sprite while the pool draws its sinking body.

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
retaining the irregular silhouette, perimeter crust and shallow rock cut faces.
The protruding interior dark-red strip on the right was replaced by liquid
using 17 palette-index changes, plus the single brown pixel left isolated within
that strip. The neighboring rock and all other pixels stay
unchanged. The masks are derived from this artwork, so those pixels also admit
the original effect frames without any sequence edits or per-position exceptions.
The eight right-edge pixels briefly tried in dark crust were restored to their
previous lava colors. The neighboring brown rock pixel and the cleared isolated
pixel are unchanged.
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
because it is more opaque than the original cover. Native bubble records,
counts and sequences are unchanged. Enhanced mode adds five native pixels to
the bubble drawing X coordinates and subtracts one from Y to place them inside
the recessed surface. Native event coordinates and bubble state are unchanged; the surface,
character-death drawings, splashes, mirror flags and all collision positions
retain their original anchors. Reference mode has no displacement.
A pixel regression test
confirms that the filled surface no longer erases a rear bubble.

Enhanced effects have separate surface and raised passes. The six native
sequences reuse 26 scheduled SHAPs; the native tables do not assign physical
surface/air classifications. Examining their artwork shows flat ripple frames,
attached bubbles, and burst frames that combine raised bodies with contact
waves at the bottom. `LAVA_AIR_ROWS` supplies port-authored upper seed bands.
Four-connected opaque pixels carry the entire raised body into the air pass,
including its lower rows, while separately drawn contact rings remain on the
surface. A hard horizontal split previously put 6-12 body pixels from each of
five native splash frames into the surface pass, visibly slicing them where
the pool mask met rock. Connected-body selection removes that artificial cut
without inventing frames, interpolating movement or changing the native cadence.
The split preserves each source pixel exactly once;
it is a presentation adaptation to the new cavity, not a recovered native rule.

Ripples, attached bubbles and the contact-wave parts of splashes are clipped
against the bright-liquid pixels of the approved surface, excluding rock and
dark-red crust around every side, including the rear perimeter. Raised drops
and burst bodies are drawn after the solid contours without the liquid mask,
so they can rise above the pool or pass in front of the rear rim. Near-side
rock is restored after raised effects too, preventing the final small-particle
frame from spilling two pixels onto the front perimeter. The remaining
inset rock contours remain in front of these raised effects: an additional mask
selects opaque non-liquid pixels between liquid above and below in each column.
Restoring only those pixels after the air pass prevents the small particles
from flashing across the left inset stone or the small rock faces on the right.
This presentation choice leaves every other raised pixel and source frame intact.
No source shape, event timing or bubble count is changed. This offset
is presentation-only; it moves the earlier six-pixel-right placement one pixel
left and one pixel up.

Before raised effects, enhanced mode restores solid contours. A cached mask protects
rock below each column's first molten pixel: both the near-side floor and the
inset stone that separates upper and lower liquid along the left contour.
Dark-red crust, where present, is restored only where bright liquid occurs both
above and below it, without hiding bubbles that rise in front of the rear rim.
The removed interior strip is now liquid and is not included in these masks.
The brighter orange shades count as liquid as well.
The saved pixels
come from the frame immediately after painting the static pool, so transparent
parts of the overlay retain the existing room floor as well. This also retains
the existing occlusion of character-death drawings and their contact splashes.
Raised bubble effects are then drawn, followed by restoration of the near-side
rock and remaining inset contours. Native reference mode has neither the custom
artwork nor the split or additional masks.
Tests compare 100 boiling frames and both facings of all three Prince death
branches for every pool and visible camera-border copy. Focused checks admit
all three flat-ripple frames at every scheduled ripple position without a
changed pixel outside liquid, and verify raised-splash pixels outside the protected rock intact.
This retains the game's palette and bubble artwork without the cover's
rock-cut gaps.
Death body/splash triples and mirror flags remain unchanged. Surface edits
stay in the original pool bounds; raised effects retain their native extents
at the shifted bubble anchor. Contact geometry, fatal Y,
retry behavior and the 1/4 grounded-death continuation probability are intact.

## Clean Level Map

`python -m tools.render_cavern_map` writes the local, actor-free
`rendered/level3-clean-map.png` (5610 x 2160). All 32 rooms are placed from
their original links on a 510 x 360 world grid, with no room numbers or
HUD bands between rooms. The current animated scenery pipeline supplies
torches, enhanced lava and potion artwork at a deterministic snapshot.
Retained background pixels come from an already rendered predecessor on
a valid route, not an unrelated previous room. `--labels` remains available
for diagnostics. The PNG is a local export, not redistributed game artwork.

## Skeleton Encounters

Level-three skeleton artwork and encounters are now enabled. The three
combat rooms retain their individual skill/life records; the other two
skeleton records remain inert bones. Awakening, shaking, collapse and
regeneration have their own controller rather than ordinary-guard startup.
The native data, routines, tested scope and remaining bank-lifecycle limits
are recorded in [AI_RECOVERY.md](AI_RECOVERY.md#level-three-skeletons).

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

The pressure-plate controller below supplies the current gate phase.
GateBarrToStandUp (4:5baa-5c56) now keeps a crouched Prince below a partially
open gate. It tests the original directional anchor band for phases 1-183,
not a fixed standing-height threshold; crawling away remains possible.

CheckGateForKid (4:60e4-61ec) tests current/behind/ahead tiles and overlap in
both consecutive collision buffers. Contact from below requests SEQS:50 on
the next update. If the low pose no longer fits a partially closed cavern
gate, CrushedByGate (6:2ac8) selects SEQS:118 and removes 100 life. A fully
closed gate or drawn sword uses the original nearest-side ejection instead.
Dead actors, selected descent 68 and an already selected crush are exempt.

ATMGate (5:41c8-425e) and CaveMoveSquishingGate (8:3a58-3b32) also track the
nearby player's selected crush sequence, including horizontal room neighbors.
Slow closing follows pose 264 at one unit/update; without the sequence-mode
signal it sets position 56 for 265, then stops at 52 for 266 and stops sound 17.
The normal SEQS:118 path sets mode 3 on its last pose 264. The next gate
update takes CaveMoveSquishingGate's earlier branch (8:3ab2-3ad4), jumps to
position 48, queues cues 20 then 18 and deactivates the gate. Poses 265/266
then flatten the body beneath the final slam without reopening to 56. This
restores the closer Macintosh stop and the visible stone/body impact using
the original sprites, rather than substituting or scaling DOS artwork.
Fast closures reaching the floor
stop at position 56 when the crushing player is nearby rather than at zero.

CaveMoveSquishingGate also has a narrower linear-cell contact test than
ATMGate's initial crush proximity: the supporting foot must occupy the gate
cell or its predecessor, rebased across horizontal room links. A foot in
the following cell must not apply the slow-pose corrections. Original
instruction execution matched 480 additional complete ATMGate updates,
including both closing phases, the mode-3 slam, pose controls and near misses.
Real Room 23 tests verify both facings, the 264/mode-3 -> 265 -> 266 timing,
the final position 48, death/retry and one additional cue-20 playback at impact.

Original execution matched 1,920 contact-selection/displacement/death cases,
4,096 crouch-rise checks and 576 gate-controller updates with and without crush poses. The contact
diagnostic supplies the overlap masks and intercepts sequence/damage calls;
it does not claim to execute the entire native movement loop. Integrated
tests cover jumping under a partial gate, crouch-rise clearance, the full
264/265/266 death, stopped gate and restart readiness.

### DOS-Inspired Crush Presentation

The subsequent DOS recording requested a deliberate visual change, beyond
Macintosh parity: sustained pressure instead of a nearly instantaneous pose
change, with the stone visibly bearing down on the torso. GateCrush uses the
approved drawing-only brake/slam/rebound profile, timed from the first native
SEQS:118 kneeling pose 264. It does not wait for mode 3 or restart its clock
when that mode arrives; the native controller may already have registered
death before the first kneel.

The drawing milestones are measured in elapsed milliseconds, independently
of the 12 Hz gameplay updates:

| Elapsed ms | Drawn gate phase | Displayed Mac pose | Original sprite height |
| --- | --- | --- | --- |
| 0 | 88 | 264 | 35 |
| 300 | 84 | 264 | 35 |
| 460 | 80 | 264 | 35 |
| 640 | 12 | 265 | 22 |
| 720 | 32 | 265 | 22 |
| 800 | 28 | 265 | 22 |
| 840 onward | 28 | 266 | 17 |

The slam stops short of a fully closed gate, rebounds briefly and settles.
Poses 265/266 retain their approved forward offsets of 4/6 pixels and floor
offsets of -2/-1 pixels. All three sprites keep their original dimensions:
the earlier progressive body shrinking has been removed. This is a
DOS-inspired presentation using Macintosh artwork, not a frame-exact
translation of the DOS actor or controller. No original artwork, sequence
resources or collision records are changed.

The native controller still finishes at phase 48 (56 for fast closures),
with unchanged damage, audio arbitration and retry rules. Only the scenery
signature and displayed corpse use the presentation state. The overlapping
gate stays in front of the full-size body in both facings even when its foot
anchor has moved beyond the ordinary column admission. Repainting cannot
advance the animation. Dedicated presentation callbacks schedule the visual
milestones without advancing movement, collision, life, world ticks or audio;
normal gameplay updates continue animating the torch. Pause freezes the
presentation clock, F3/restart clears it, and reopening the gate releases
only its drawing override, retaining the original-size death pose. The time
available to escape is still decided by the native controller.

Tests cover elapsed-time boundaries, the first-kneel start, full sprite
heights, pixel overlap/foreground in both facings, the stable resting pose,
unmodified native gate values, presentation-only callbacks, pause, F3 and
restart. Actual gameplay scheduling and rendering also matched all 132
post-kneel samples of the approved preview in each facing, excluding the
torch region that the old preview had frozen. New Room 17 exports use the
live gameplay path throughout, verify continued torch animation after the
slam, and preserve the previously approved media as separate files.

### Grabbing And Climbing Beside A Gate

The later Room 23 recordings exposed two missing selectors. IsLedge
(4:3fa4-3fc0) rejects a left-facing falling catch when the destination is
tile 4 with phase zero. A nonzero opening can be caught; facing right is
not vetoed by this branch. DoJumpUp deliberately supplies phase 184 for a
gate (6:1620-162a), so its upward approach must not inherit the falling
catch restriction. The portable catch now respects that distinction.

The climb selector at 6:19d4-1a50 inspects the supporting tile ABOVE the
actor. A cavern gate below quarter-phase 30 (phase 120) blocks a left-facing
climb; the right-facing threshold is quarter-phase 12 (phase 48). It selects
SEQS:73, not ordinary SEQS:10: poses 135/136/137/137/138/138/138/138/137/136/135
recede into SEQS:11. The gate never becomes a walkable landing on the wrong
side. Sufficiently open gates retain the complete ordinary climb. Actor 1
and the native environment/facing exceptions remain in the selector.

CheckGateInFore (3:2722-2762/2860) also peels the moving stone over actors
on the same physical row, in the gate's own or preceding foot column,
except hanging modes 2/6. CavernRoom now retains a positioned SHAP:3563
alpha mask from the current gate-phase commands for this actor-specific
foreground. The existing fixed frame, wall masks and collision-height
formula are unchanged. This prevents the turban/body from painting over
the moving stone at tight opening clearances, without hiding hanging poses.
NPC-bank and special crushing redraw paths are not a complete translation.

The gate mask is keyed by the stone's actual tile, not the cell that
requested its repaint. DrawCaveGateMovable (8:1f40) places SHAP:3563 one
column right of that tile; its command's source row can differ from the
repaint row too. Multiple repaint callers share that positioned mask. This
keeps the left neighbor's gate and a gate from the room below behind the
Prince in room 4, without removing the real foreground stone in rooms
17/23. Static scenery and gate movement/collision rules are unchanged.

Ordinary opponents and the Prince also follow IndexChar (4:4558),
IndexCell1 (4:2a38) and DrawObjs (3:39d6), rather than always painting the
Prince last. Offscreen bucket 30 precedes bottom-up, left-to-right visible
cells. SortObjTable/CompareObj (3:3b62/3bec) assigns their ordinary object
kinds the same priority 127, then orders by shape bottom and draw anchor.
The inert skeleton pile's FRAM offset adds ten to its shape bottom, so
its bones correctly cover the Prince's feet when they share a cell.
Original instruction execution matched 512 ordinary actor pairs. Regression
tests cover room 4's background gates, bones and foreground pillar, plus
cell ordering and the offscreen bucket. Other special object priorities
are outside this character-only ordering helper.

Original instruction execution confirmed 6,144 climb selections, 512 gate
catch admissions and 80 foreground-admission cases. Real-terrain tests replay
Room 23's run jump, an initially shut gate, a gate that closes after a valid
grab, the complete failed climb/fall and the successful climb. Pixel checks
cover the moving stone over an overlapping actor in both facings. This
extends the focused gate audit, not a claim of complete movement-loop parity.

CheckSquishedFingers (5:153c-15a2) supplies the original cue 29 when a gate
finishes closing over a hanging Prince's hand. It requires the same room,
animation mode 2 or 6, and a supporting-foot linear cell equal to the gate
cell plus 10 or 11. Facing and a request to climb are not conditions; the
routine does not damage the actor. ATMGate calls it after StopGate on slow
closure (cues 18, 29), and before cue 20 on an ordinary fast closure (29, 20).
The separate fast-close crush stop at position 56 does not call it. Once
closed, the gate leaves the active list, so holding the ledge cannot repeat
the voice. Original instruction execution matched 9,600 room/mode/cell
comparisons, including room-edge linear cells. A real Room 23 running-jump
catch verifies both closure speeds through the audio backend, one voice,
continued hanging and unchanged life. StopGate's separate mode-2 pose
selection is not included in this sound-only recovery.

### Standing Turns Beside Gates

The room-4 reference is not a position-invariant round trip. Standing
Backward (6:10e4, specifically 10f6-1154) measures the supporting foot's
distance to its cell edge. When the ahead tile is a blocking cavern gate,
it reserves eleven pixels by moving backward before selecting SEQS:5.
For example, a left-facing anchor at 29 moves to 32 first, then the
ordinary turn finishes at 41; turning back finishes at 32. Repeating the
turns does not keep shifting the Prince. Open gates need no adjustment.
This is the cavern branch, not the separate six-pixel rule for other
environments or the special level-8 branch.

CheckBarr (4:4e46/4fce) also bypasses ordinary collision-buffer updates in
turning mode 7. CheckGateForKid (4:613c-6164) consequently uses the previous
pair of contact masks, not the turning arm's new rectangle. The port keeps
that pair of gate-contact rectangles during the turn. Contact that already
existed can still force a crouch as the gate closes; merely extending an
arm into a neighboring gate cannot interrupt the turn. History is scoped
to room and physical row, saved with the terrain motion, and defaults to
empty when loading older version-1 saves.

Original instruction execution matched 600 standing-turn offset cases in
both facings and confirmed preserved mode-7 mask values 0/15/240/255.
Tests cover the small initial offset, repeated real-input turns in room 4,
no spurious crouch or cumulative drift, closure over an existing contact,
context changes, save round trips and older saves without contact history.

### Closing Gates And Released Runs

CheckBarr (4:4f8a-4fb4) raises a side-collision index only when the relevant
mask nibble changes from clear to set. A body already overlapping the stone
must not receive another lateral bump just because a new pose grows wider
or the gate becomes low enough to touch it. The cavern gate sweep now uses
these edge transitions; ordinary wall recovery is unchanged. CheckGateForKid
still owns the existing crouch, crush and fully-closed/sword ejection rules.
Its two contact samples are captured before Collide displaces or reloads the
actor, with the previous sample retained independently of the corrected pose.
The current body height remains the input to the gate-clearance predicate.

This also fixes braking through the Room 10 -> 14 gate: the next room's
reverse plate closes the stone behind the Prince. Previously, the widening
stop pose caused a wall bump that pulled him back into Room 10 at X=477.
The released run now stays in Room 14 and completes the native crouch/rise
instead. No artificial held direction, altered stop sequence or input
priority override is needed. Original CheckBarr execution confirmed the
entry/retained-overlap distinction from both sides. Regressions cover both
approaches, a moving low body crushed rather than ejected, pre-collision
contact samples, and several release positions across that room transition.

Gate impact cue 20 has a presentation-only delay of 11/60 seconds, matching
the requested eleven frames at 60 fps. Playback prefixes 8,800 silent stereo
frames at 48 kHz to the already loaded sample; the original impact PCM is
otherwise unchanged. SDL's sample clock handles the delay, including pause,
stop and reset, without quantizing it to gameplay updates or adding a late
callback after restart. The outgoing gate-movement loop uses the existing
short PCM release rather than an abrupt cut into this silent lead-in.
Other effects, native gate movement/damage/escape rules and the approved
crush drawing milestones are unchanged; retry still follows the original
effect-completion rule. No resource reimport is required. SDL tests verify
the exact prefix, unchanged PCM, release transition and cancellation.

## Pressure Plates And Stone Gates

All 27 level-three buttons are reverse plates (tile 34). Their low foreground
byte indexes the original LEVL link table at 0x1680: 256 ten-byte records of
five signed words (one-based target room, cell, timer, previous, next).
Next index -3 ends a chain; room -2 marks an unused link. Sixteen buttons
control nine stone gates (tile 4); the remaining buttons target projectile
traps (33) or exit doors (17). Room 24's second plate controls two gates across
rooms 24 and 23. These are data links, not inferred proximity or room overrides.

CheckPress (5:127e), PushPlate (5:240c) and Trigger (5:1c4c) supply supporting-foot
contact, FRAM/pose admission, cue 27 and the five-update release timer. PushPlate
writes depression bit 0x2000 only after traversing the links. Holding a plate
refreshes its timer without repeatedly clicking; stepping away rearms it.
Actor-death and debris contacts can set timer 31 for permanent pressure.
Debris uses the separate impact predicate when opening a gate permanently.

TriggerGateWithRevPlate (8:2c38) distinguishes fresh from held pressure.
The ordinary gate opens by four phase units per update, reaching 237 after
46 updates. It waits by decrementing one, changes to closing at 183, then
closes by four. A single initial press completes the cycle after 146 updates.
Held pressure refreshes the open position. A fresh press during its open/closing
states caps the position at 184 and requests fast closing: 124, 44, 0 on the
next three updates. Holding that now-depressed plate cannot immediately reopen
the gate. Native AnimGate (5:41aa) supplies cues 17/18/20 and the DATA speed
tables; plate release is the native loop at 5:2554.

Playback keeps the native cue requests and priority arbitration, but avoids a
hard waveform cut when movement cue 17 is replaced by stop cue 18. The stop
starts immediately while a separate channel releases the remaining movement.
An SDL_mixer channel effect applies a 12 ms raised-cosine envelope sample by
sample, carrying its position across mixer buffers. This replaces the former
80 ms channel-volume fade, whose per-buffer gain steps could leave a brief buzz.
It uses the audio sample clock, not an estimate of the play position from game
timing. The silent channel expires after 80 ms. This is a playback-only de-click
improvement, not a recovered Macintosh rule. Pause freezes the release; mute,
reset and replacement stop it. Other cues and the imported samples are unchanged.
The callback only processes SDL's temporary channel buffer, never shared sound
data, and remains owned until playback stops before mixer shutdown.
See [SDL_mixer channel effects](https://wiki.libsdl.org/SDL2_mixer/Mix_RegisterEffect).

Movement cue 17 now repeats on SDL's audio clock instead of waiting for the
next game update after each roughly 1.045-second sample. A 12 ms raised-cosine
overlap joins the end to the beginning in a private, in-memory loop; its start
is rotated near zero without inserting a fade on every repetition. Imported
WAVs are not rewritten. Repeated movement requests renew a playback deadline
equal to the original sample duration, so a missing stop request cannot leave
an infinite sound. Priorities and controller timing are unchanged; cue 18 keeps
the sample-accurate release above, including across a loop boundary. Pause,
mute, replacement and level reset continue to operate on the same channels.

Version 12 binds affected logical cells to original drawing commands, including
fragments emitted from neighboring rooms/cells and the lower room's first row.
DrawCaveGateMovable (8:1f40)
moves SHAPs 3563/3562 by two pixels per quarter phase, clamped at 46, and retains
the native top/bottom clips. Pressed plates change SHAP 3554 to 3555, including
DrawHalf's separate front-only climb repaint. Runtime
rebuilds their actor masks along with the room, retaining loose-floor variants
but discarding obsolete gate-height images. Terrain collision reads the same
current foreground byte. Pause freezes these controllers; room changes retain
them and restarting creates fresh state.

Direct execution of the original controller routines matched 17,280 portable
updates across all 16 gate buttons (single, held and repeated presses), including
ordered cues, timers, active states and foreground words. CheckPress also matched
1,944 plate-contact cases across pose/mode/height, actor, selected sequence and
alive/dead combinations. Original full-room drawing matched all 636 tested
command lists: every visible gate at all 47 visual heights and every visible
plate in both states. Another 504 native comparisons checked simultaneous
gate/plate changes, floor repaint and all ten climb repaint poses at two gate
heights. The diagnostic supplies
redraw bookkeeping and ordinary actor/impact context; it tests these routines,
not the entire native scheduler, crushing or the complete route. Integrated
tests cover actual held-run pressure, blocked/open passage, bounded scenery
caching, pause and restart. Resource-free controller tests also run on CI.

The common pressure/link base, exit opening and projectile traps below are
integrated. Native shared capacity/order
between all animated objects and special actor interactions remain incomplete.

## Exit Buttons And Entry

The two exit links are Room 13/cell 28 -> Room 13/cell 16 and Room 30/cell 8 ->
Room 30/cell 25 (zero-based cells). TriggerObject (5:1f18-1f8a) starts state 1
only when the exit's low foreground byte is zero. Further held or rearmed
presses do not reverse or restart it. ATMExit (5:161c-168c) adds one per update,
stops at 79 and retains the upper foreground flags. Cue 17 accompanies movement
and cue 18 the final update. TriggerObject also requests AddSong(297), the
original OpenDoor MIDI, subject to PrinceSndOn. Import now prepares it with the
original instrument bank; the host uses the music bus, not the effect bus.

Version 13 adds SHAP 3566 drawing bindings for both exits. DrawCaveExitMovable
(8:1c58) clamps at 79, moves its bottom by one pixel per phase and clips its
top to max(row*120+1, sprite top). These bindings compose with loose-floor and
pressure states. The entrance's separate FirstFrame/CloseExit export is unchanged.

The ordinary Up branch (6:0e36) excludes the starting room and non-Prince actors,
then checks the current supporting-foot cell, the cell behind, and the one
ahead for tile 17. Only a low byte >=79 admits entry. The helper at 6:0f58
aligns scene X to 51*exit_column-3, faces left and selects the original SEQS:70.
Controls remain locked while it runs; pause still freezes it. ClipChar's
4:416a-420c exit branch takes effect below row*120+82, using cavern DATA's
rectangle (17, 0, 364, 71), with the right-half column selected from tile 16/17.
The portable actor layer applies its top/right limits before compositing.

Native comparisons matched 1,080 exit-controller updates across both linked
buttons (single, held, repeated), including ordered effects, song requests,
foreground flags and timers. Admission/alignment matched 576 native cases.
All 80 drawing heights and sampled floor/ten-pose climb repaints matched 226
native command lists. Another 320 ClipChar cases matched top/right limits;
that diagnostic supplies equivalent OffsetRect/SectRect platform bookkeeping.
Integrated tests cover the music bus, pause, offscreen persistence, entry,
completion and restart. Visual checks include the supplied Room 30 recording.

SEQS:70's native -16 event now reaches the existing completion host. Level 4
is not implemented: this deliberately stops at Level 3 Complete rather than
loading an unsupported level or replaying the level-one boat cinematic. It
does not claim the complete native next-level music/story/save pipeline.

## Projectile Trap Buttons

The reference `button trap.mp4` shows Room 16's two mid-row shooters, cells 12
and 16, linked from plates 13 and 17 (zero-based cells). Level 3 has nine such
links in Rooms 4, 5, 9, 13, 16, 21, 22 and 28. They use the same pressure/link
controller as the gates and exits, not room-specific triggers.

TriggerObject (5:1f8c) rejects an already depressed plate. TriggerDart
(5:49b6-4aec) also requires shooter foreground `&7 == 0`, adds its animated
object, loads mouth phase 1 immediately and requests sound 65. Its controller
(8:2dea) advances through 2/3/4/5/6, then clears the low three bits and removes
the animation. The plate must be released and the shooter idle to fire again;
holding the plate does not repeat shots. Decoration bits remain intact.

The new type-2 MOB starts at `(51*column+40, 120*row+95)` with constant velocity
`(+27,-19)`. MobDart (8:2f98) has no gravity. Crossing a column checks IsWall or
the native gate-clearance test; crossing `Y <= 120*row+5` checks the row above
for solid floor. Impact requests 67 and marks velocity -3; the next update
removes it. Crossing the viewport's right/top bounds can rebase from the
visible left/lower neighbor into the current room. Otherwise the object is
retired, with impact sound only if that outbound room link is absent. It does
not chase every linked room indefinitely.

CheckDartHit (8:2e82) uses an exclusive 9x7 rectangle at X+13/Y-7 and a separate
swept test. Crouch poses 108-112 are exempt only in selected SEQS:79. Its active
MOB indexing renumbers after a consumed projectile; the portable loop retains
that behavior. A nonfatal hit requests 29/66 for the Prince (59/66 for an
ordinary NPC), displays the existing damage burst, and deducts one life without
interrupting movement or drawing the sword. Multiple darts in the same update
do not stack their one-life wound. Dead actors can consume a projectile without
another damage reaction.

The fatal helper (8:3138-31e0) uses supporting-foot distance and the cell behind
to select supported death (ordinary SEQS:85; Prince wall-jump poses use 98) or
SEQS:18 at a ledge, with the original facing-relative displacement and floor-row
increment. That last branch must keep the common falling/camera physics alive
until landing. The helper's final Prince death-song method is 0.
Special-actor death selection and the complete shared pending-damage arbitration
with unrelated hazards remain outside this ordinary-actor implementation.

DrawCaveDart (8:1aba) supplies mouth SHAPs 3591/3593/3592/3591. Export version
14 binds those slots to each logical shooter and recomputes their different
dimension-dependent clips. DrawObj (3:4032) passes one-based shape 94 to AddMid.
Its stored slot is zero-based 93, but Caverns SHPL:3500 starts at resource
3501, so DrawMidItem (3:3144-3152) resolves SHAP:3594, the orange/yellow 5x5
projectile. The earlier portable 3593 selection was off by one and displayed
the dark 5x3 mouth image instead. The inclusive bottom anchor, flight physics
and damage rules are unchanged. No custom replacement artwork is used.

Native execution matched 3,240 controller/projectile updates across all nine
buttons, with single presses, holding, release/repress and rapid attempts.
Another 315 comparisons cover whole-room, floor-repaint and climb-repaint
command lists at all seven phases. CheckDartHit matched 14,280 rectangle/swept
and crouch cases. The diagnostic executes the native controllers and replaces
unsupported 68020 address arithmetic with equivalent LEVL reads; it supplies
QuickDraw rectangle intersection and stubs redraw bookkeeping and the hit
reaction while testing contact. These are focused comparisons, not a claim of
complete native scheduler or special-actor parity.

Integrated tests run through both Room 16 buttons and one-life/fatal contact,
including ledge-fall completion, continued run animation, pause and restart.
The supplied video and a frame-by-frame port render were inspected for the
mouth/stone/burst presentation. Resource-free rules run on CI; tests needing
the original artwork are skipped there. The shared finite MOB/TROB bank across
all debris, traps and other objects remains separate recovery work.

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
This remains the separate entry-closure controller; button-driven exit opening
is described above.

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

Projectile/special-actor drawing modes and
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
Special actors remain separate recovery work. Pressure-plate impacts now feed
the controller described above; this older debris comparison did not test them.

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

### Collapsing Floors During Climb

CheckFloor (4:35ba-3682) uses FRAM bit 0x40 during the late climb poses,
not just after their link back to idle. The portable protected-ledge path
now performs that same floor test while still bypassing ordinary free-fall
movement and barrier bumps. StartFall also clears the portable climb/hang
locks so the existing Shift/Catch controller can take over on later frames.
The original RoofClimbingIntoShip exception (23:12ba), called at 4:3638,
still exempts selected SEQS:59 in the ship room of environment 5; the moving
ship is not represented by a supporting LEVL floor tile.

In room 24, the loose floor disappears between poses 145 and 146. Previously
the protected climb continued through pose 119, shifted X by another 12 pixels,
and missed the next ledge. It now enters the fall at X=253, catches at X=219
with Shift, and settles at X=223 before climbing the surviving platform.
Without Shift it falls normally. No room-specific catch tolerance was added.

Executing the original CheckFloor matched 120 combinations of pose, floor
kind, facing and room used by the resource-free regression. That diagnostic
intercepts StartFall at entry: it verifies floor-test dispatch, not the whole
native fall/catch simulation. Integrated resource-backed tests cover the
room-24 collapse, Shift catch, subsequent climb, no-Shift fall and an unchanged
solid-platform climb. The two user recordings were also compared visually.

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
floor classifications,
crushers, special potion types from later levels, special draw modes and
skeleton enemies still require semantic recovery and integrated tests.
The ordinary-guard decoder does not reinterpret skeleton spawn records; the
preview encounter host omits those actors until their implementation exists.

The entry-door phases and flask rooms have received focused visual checks;
the complete route and all special drawing modes are not yet validated.
The flask-library defect exposed by the user's Macintosh recording is fixed.
Static row masks still do not implement the complete native actor-clipping
pipeline. See [Route audit](LEVEL3_ROUTE_AUDIT.md) for reference moments and
the remaining recovery order. Room coverage alone is not visual fidelity.

## Normal And Mega Potions

LEVL:2002 contains five type-1 healing flasks (Rooms 7, 9, 12, 26 and 32)
and two type-2 capacity upgrades (Rooms 10 and 20). Type comes from foreground
bits 5-7, independently of the rock decoration and particle phase.

The old flask palette relocation incorrectly added 224 to the stored indices
1-15. Original RemapCTBL (17:6a78), called by LoadFlaskSet (3:5614), assigns
224-238 in order instead. The portable palette now does the same, removing
the missing-color magenta and correcting the flask and particle colors.
DrawFlask (3:46fc, misleadingly named GetFlaskBubbleColor in the symbol index)
uses Prince SHAPs 3001/3002 and two monochrome layers from 3003-3022. The
second half is mirrored; phases 10-13 and 24-27 emit no particles. The native
28-update cycle and TriggerFlask's inclusive Rnd(26)+1 initialization are
retained. Static scenery and floor/climb repaints omit these dynamic items.
The live flask bodies and particles are drawn in the front animation pass,
after the Prince and hit effects, rather than underneath the actor. A pixel
regression covers all seven flasks, both facings and active/quiet phases in
both halves of the cycle; collection also removes them from this front pass.

TryPickUp/PickItUp (6:1350/13d0) select the current or forward flask, align the
standing/crouched Prince, then select SEQS 50/78. RemoveObj (4:406c) replaces
the flask with floor 1 while retaining foreground bits 0x0f00. AFRM attachment
type 3 uses Prince's flask bank, not the sword bank. SEQS 78's -14 operation
with operand 2 precedes the sip; ordinary healing waits for the later operand
1 after the held pose. DoPickupEffect (4:45dc) adds one life for type 1, or
adds one maximum life (capped at 12) and heals fully for type 2, requesting
AddSong(24). The original drinking effect 23 and MIDI 24 are prepared at import.
Restart restores entry capacity rather than permitting repeated collection
of the same upgrade (2:61f2 and SetKidDefaults 2:5d82).

PickItUp (6:1576-1596) takes a flask of any type: RemoveObj (4:406c) stores
the type (foreground bits 5-7), and DoPickupEffect dispatches on it:
- types 1 and 2 behave as described above;
- type 5, the harmful flask, calls DecLifePts(1) and plays sound 12
  (4:4678-46b0). A fatal sip selects SEQS:71 with death method 3.
  Level 4 has type-5 flasks in rooms 14 and 29, and the port now drinks them.
- type 3, the float flask (level-four room 6, above a fatal shaft), sets
  the global a5-0x4fa6 timer to 228 and plays song 111 (4:466c, 2:5a26). The
  timer counts down once per frame (2:6c58-6c5e). While it runs:
  - Move (4:342c-3444) gives every faller +2 gravity with a cap of 8;
  - 4:34b2-34ca halves the floating Prince's horizontal step;
  - StartFall (4:4db4) selects SEQS:228;
  - AnimChar `-10` (4:2e42-2e54) acts as a link, so SEQS:7/45 continue in
    228/229;
  - CheckPress (5:129a) ignores plates under the Prince.

  - CheckBarr (4:50b2-514e): with no barrier hit, a floating body whose top
    is more than 8 pixels into the row above, under a non-space cell (anchor
    column), steps back 6 pixels, stops drifting and restarts SEQS:229. The
    body height uses the port's collision bounds (native a5-0x3560) [I].
- types 4 (flip, 2:59f6) and 6 come in later levels. They are not modelled
  yet and stay on the floor rather than being consumed without their effect.

**Room 14 heap.** The level data puts room 14's dormant skeleton on the
cell of its harmful flask (cell 15); level 8 room 25 is similar. On the
Macintosh the heap is not drawn there.

SkelAddOpponent (4:19f0-1a54) moves a heap with open space on its left
(behind a right-facing heap, ahead of a left-facing one) to the right, until
its foot is 54 pixels from that cell's left edge.
- The port now applies this when it creates a heap. Only room 14 in levels
  3-4 is affected.
- The native routine measures with the frame record already loaded (a5
  globals 0x520e/0x520a). When opponents are created on room entry, that is
  the Prince's current frame [I], so the port uses it too. With a standing
  Prince the heap moves 31 pixels and ends partly behind the pillar, as in
  an emulator image; that image fitted best about 9 pixels further right,
  which depends on the Prince's pose at entry.

Native execution matched 644 pickup admission/alignment/sequence/removal
cases, 128 particle-controller states and 150 life/capacity/song effects.
All 28 phases of each of the seven original flasks matched the native drawing
routine pixel for pixel (196 full-room flask layers). Integrated tests cover
both approaches to every flask, full/injured health, original effect timing,
held attachments, pause, removal and restart with inherited entry capacity.

Shift pickup requests are consumed only when the standing/low-pose handler
can inspect a flask, not merely because Shift was sampled during a fall or
protected animation. Holding a newly pressed Shift through the Room 18 -> 20
drop therefore drinks the mega potion directly from landing pose 109, before
the rise. Releasing Shift before the landing cancels this held request; it is
not an indefinitely latched pickup command. Running/jumping still cannot
collect a flask in mid-animation, and health effects retain their sip timing.

GenCtrl (6:0c50/0a0c) and PickItUp (6:1466-1482) distinguish a pending Shift
from a consumed one and explicitly reject the crouch of hard-fall SEQS:20.
The ordinary SEQS:17 landing is allowed; hard-fall recovery must finish first.
Original execution confirmed 30 crouched-pickup cases across selected
sequences 17/20/26/50/117, both facings and modifier values -1/0/1. Integrated
tests cover the real ledge drop, direct 109 -> 191 transition, cancellation
and the protected recovery exception. No new save fields or asset import
are needed.

Run-stop pickup uses GenCtrl's standing dispatcher at poses 50-52
(6:05fe-0618), rather than waiting for SEQS:13 to return to idle. The earlier
skid poses still finish normally; wall-bump SEQS:47 and protected hard-fall
recovery are not made interruptible by their similar poses.

As a requested port QoL extension, a Shift press after releasing run also
queues a one-shot pickup attempt through that stop, even if Shift is released
before the next tick. An idle pickup tap receives the same treatment. This
does not latch the Shift modifier itself: native modifier sampling otherwise
cancels an unconsumed Shift on release (4:3f08-3f42). The attempt is restricted
to the same room, row and facing and expires at the first eligible pose if
no flask is reachable. New movement/commands, falling, drawing the sword,
clearing controls and F3 placement cancel it. It is transient controller
state, not a save-game field. Integrated Room 10 tests cover both approaches,
two run-release poses, taps at several points through braking, held Shift,
idle taps, cancellation and unchanged sip-effect timing.

Later-level types are identified, not implemented by this level-three work:
type 3 starts slow fall (2:5a26), type 4 toggles vertical screen inversion
(2:59f6), type 5 wounds or cures inversion if active, and type 6 selects the
special SEQS 111 branch. LEVL:2011 (level 12) contains the type-6 flask in
Room 23. These require their own later-level actor/story integration; they
are not silently treated as healing flasks.

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

## Wall Spikes

The three LEVL:2002 type-2 wall traps are in Rooms 11/14/21, cells 22/20/24.
CheckSpikes (5:3c42) uses the physical row, supporting-foot column minus one,
Y >= row*120+35, facing, body width and sword mode. CheckSpikeHit (5:3af8)
checks the current and preceding column, Y >= row*120+56, the native left
body edge and pose exemptions. MobSpikes (5:3fa4) makes only outward phases
1 and 2 lethal. Cautious-step poses 121-132 and idle pose 15 are exempt;
the extended hold is not a recurring damage zone.

TriggerSpikes (5:40a0) starts at phase 1. The phase controller (5:3fda)
advances to 2 with cue 282, then 143; it counts down through 129 before
retracting through 4/5/6/0 with cue 284. Nearby actors renew the hold to 143,
not the outward attack. An impalement latches 240, selects Prince SEQS 51
or 54 according to facing, aligns to tile X+90, turns left, requests cue 281
and death method 4. The original two death resources finish at poses 242/243.
Ordinary supported NPCs use SEQS 188/189; skeleton mechanics remain separate.

InitCaveSpikes (8:2c18) binds DATA banks 70/73/72/71/70/69/74 and
76/79/78/77/76/75/80 to DrawObjSpikes (5:3e12). Original SHAPs and DATA
offsets are drawn behind and in front of actors, including the blood bank.
No new asset export or import is required. Offscreen live MOBs clear their
foreground phase; blood survives room changes and is reset by level restart.

GetBarrCode (4:52bc) uses extended type-3 spike clearance only when c944 is
set inside DoStepFwd (6:1280-1336). Physical wall collision must use ordinary
type 4; using type 3 there stopped a run before it could trigger the trap.
The distance query also defaults to c944 clear. Only an actual cautious
step enables it; GenCtrl's fresh run-start query (6:11a0) must not. At idle
X=115 to the right of a retracted trap, native clearance is 39 for run
startup, versus 17 inside DoStepFwd. Applying the latter to the former
incorrectly selected SEQS:32 without Shift, granting cautious-step immunity
and eventually replacing the attack with a wall bump. The user's recordings
and new close-start regressions at all three traps cover this case separately
from the earlier long-run tests.

Native execution matched 23400 supplied-body-bound trigger/contact/Prince
death-alignment cases across the three traps, all 256 phase-controller
inputs, and 18 back/front drawing-command cases. Resource-backed tests cover
running and cautious approaches at all three traps, both Prince death
sequences, pause and restart. Pure tests run on CI without game resources.
Temple-specific behavior, skeleton interactions and a unified shared MOB
bank are not claimed by this cavern implementation.
