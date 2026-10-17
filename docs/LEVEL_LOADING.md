# Level Loading

Gameplay is still written in Python. Level loading and world state no longer
require the Tk window, and scenery caches belong to the selected level.

## Ownership

- `pop2/level_data.py`: immutable level identity, environment, starting room,
  tile, facing, opponent type and checkpoint records from LEVL.
- `pop2/game_session.py`: shared animation resources and a level's runtime,
  terrain, combat, opening controller, harbor, death and checkpoint state.
  Restarting or placing the player does not create a window or play audio.
- `pop2/level_rendering.py`: lazy room images, supported scenery and screen
  labels. Metadata and the F3 tools panel do not build room images. Open map
  requests a private stitched map lazily, once per selected level; other levels
  are not pre-rendered at startup. See [F3 Level Map](DEVELOPMENT_MAP.md).
- `pop2/scene_prototype.py`: keyboard controllers, frame ordering, audio,
  composition and the connection to `pop2/window_controls.py`.

The existing controllers access the session's mutable world through explicit
properties. Animation resources are shared, but each session has its own actor
state, combat world, death counter and checkpoint. Changing levels also replaces
the sprite caches and palettes; a restart keeps the current level. New Game
returns to level 1. A destination is prepared before replacing the running
session, so unsupported scenery does not discard the current game.

This is an incremental separation, not a complete headless gameplay engine.
Input dispatch and simulation scheduling still live in the scene host. The
window remains Tk; pygame/SDL still supplies audio.

## Original Data

Level numbers 1-14 select LEVL resources 2000-2013. The loader checks the
resource's own level number, start coordinates and room links before use.

`SetKidDefaults`, CODE:2 5cf4-5ed8, reads:

| Offset | Field |
| --- | --- |
| 2186 | Environment kind |
| 218a | Level number |
| 2198 | One-based starting room |
| 219a | Starting tile: row * 10 + column |
| 219c | Facing word, complemented before storing in the actor |
| 21a4 | Opponent type; -1 means no opponents |
| 39a6 | Two room/tile checkpoint pairs |

The ordinary starting X is column * 51 + 22. The rooftop window branch
(environment 5, native room 4) instead applies -8, selects SEQS:4 and advances
nine frames before the first display. Its lower landing floor is tracked
separately from the initial absolute Y, as before this separation.

The next branch, 2:5dba-5dca, selects SEQS:124 for environment 1. Level 2's
resource places the Prince in native room 2, tile 15, facing right, and declares
no opponents. Its arrival chain uses poses 256-263, then idle pose 15. The host
runs the entire arrival sequence before enabling ordinary controls and physics.

Ordinary guard creation now inherits the selected environment for initial,
visited-room and generated guards. A room with no guards is valid. Special
opponent types with nonempty spawn tables still fail explicitly in the ordinary
guard decoder. The encounter host omits these unrecovered actors for scenery
previews rather than creating substitute guards.

## Current Boundary

Rooftop scenery and the level-2 shore are implemented. The beach reads
Desert.rsrc's original CUST/SHAP records, including the floating planks' animation.
The stone controller is owned by the session and resets with the level.
The cavern entry-door controller is likewise session-owned; import supplies
its native closure phases and sound cues, and restart restores its initial state.
Visible cavern torches share session-owned phases across their cell fragments;
their changing flame is composed separately from cached scenery.
The opening cave exit loads level 3, preserving the player's health capacity.
All 32 rooms use drawing commands recovered at import time from CODE:3
and CODE:8. The level-3 entry uses SEQS:5 (SetKidDefaults, 2:5e34).
The original links are followed between these rooms, and F3 offers a floor-based
preview placement in each room. Beyond entry-door closure, interactive cavern
objects and skeletons remain unsupported. See [Cavern recovery](CAVERN_RECOVERY.md)
for the current boundary.

SEQS opcode -16 marks completion in the session, independently of the harbor
watcher. The host continues the ship animation while the original end song
plays, then starts NIS 9 and loads level 2. See [Level transitions](LEVEL_TRANSITION.md).

`tests/test_game_session.py` includes synthetic, asset-free tests for metadata,
state ownership and resets, plus optional original-resource tests for all
fourteen level headers, the level-2 entry sequence, guard environments and
unchanged rooftop scenery. Existing integrated tests still cover the level-1
route, checkpoint retry, ship boarding and the attract cycle.
