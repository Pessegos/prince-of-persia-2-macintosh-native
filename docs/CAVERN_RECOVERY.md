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
retains the existing filename `caverns_entry.json`, now version 3:

```text
rooms[zero_based_room] = [layer, shape_id, x, bottom, draw_mode, row, clip_rect, library][]
clip_rect = [top, left, bottom, right]
library = 4 (Caverns) or 1 (Prince flasks)
```

The export captures native clip rectangles, including the SectRect calls at
8:1752/1ca4/1f86 and EmptyRect at 8:20a6 used by gate drawing. Runtime clips
both sprite pixels and actor-occlusion masks to those rectangles. Resources and
decoded shapes are cached across room changes. No Macintosh executable is
retained or executed by the game itself.

Older exports request an asset reimport: version 2 lacks the flask library
identity, and version 1 supplies only the entrance. F2 can preview each room, placing
the Prince on a basic floor tile from LEVL rather than using per-room positions.

## Flasks And Entry Door

Flask BF items now retain library 1 and use Prince.rsrc SHPL:3000 / SHAP:3001-3033,
not Caverns rock shapes. LoadFlaskSet (3:5614, 5630-5658) relocates CTBL:3000
to palette index 224. Monochrome masks use the descriptor's ink color and the
whole-bitmap RLE in hGetNShapeItem (17:5f78-5fa0), distinct from color row RLE.
Executing that native loop independently agrees with the portable decoder for
all 18 compressed monochrome flask shapes. This fixes their appearance, not
collection, animation or health upgrades.

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

## Current Boundary

This is the scenery foundation, not a completed playable level. Original room
transitions and the common movement runtime are available. Cavern-specific
floor classifications, gate and plate controllers, loose floors, spikes,
crushers, lava, potion behavior, special draw modes, animated torches and
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
original map link, the generated map, F2 room placements, flask libraries and
mask decoding, entry closure/restart and cross-environment water clipping. These checks do
not certify hazards, object interactions or completion of level 3.
