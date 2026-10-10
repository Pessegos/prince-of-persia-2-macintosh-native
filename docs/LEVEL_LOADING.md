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
  labels. Room images are built only when requested, not when opening F2.
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
opponent types still fail explicitly rather than creating ordinary guards.

## Current Boundary

Rooftop scenery and the level-2 entrance are implemented. The beach reads
Desert.rsrc's original CUST/SHAP records, including the floating planks' animation.
The remaining island scenery, environmental controllers and music scheduling
still need recovery. Unsupported room transitions retain the current room.
Other environments' start controllers also remain explicitly unsupported.

SEQS opcode -16 marks completion in the session, independently of the harbor
watcher. The host continues the ship animation while the original end song
plays, then starts NIS 9 and loads level 2. See [Level transitions](LEVEL_TRANSITION.md).

`tests/test_game_session.py` includes synthetic, asset-free tests for metadata,
state ownership and resets, plus optional original-resource tests for all
fourteen level headers, the level-2 entry sequence, guard environments and
unchanged rooftop scenery. Existing integrated tests still cover the level-1
route, checkpoint retry, ship boarding and the attract cycle.
