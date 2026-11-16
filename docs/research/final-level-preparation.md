# Level 14: Inventory

Status: 2026-11-11. The level-13 completion path through NIS 3, all 11 static rooms, entry
placement and saving are integrated. The final battle and ending are not.

The two playtest blockers of 2026-11-11 (NIS 5 on the room-2 outside
landing, and the freeze after the room-4 sword draw) are fixed; see
[the 2026-11-14 section](#room-2-window-gate-and-armed-reset-2026-11-14).
[The Claude handoff](final-level-claude-handoff.md) also records the
manual's shadow/fireball rules and the optional room-3 potion recovery route.

The player's complete Macintosh run is now indexed in
[the video reference](final-level-video-reference.md). It confirms the copy
sequence, separate blue form/body, projectile victory, bedroom aftermath,
final epilogue and Hall of Fame. The final epilogue is NIS 11 (15:3c76);
the existing `ending.json` is the level-1 voyage and must not be reused for it.
The bounded final completion caller now has 12 original CPU checks with
PlayNIS and HallOfFameDialog supplied. The port now plays NIS 11 from the
original coordinator, then the Hall of Fame takes the remaining minutes and
the introduction restarts (see "NIS 11 and the Hall of Fame" below).
Names in the inventory below come from preserved symbols.

## The level

`LEVL` 2013: level 14, environment 6, 11 rooms, 18,890 bytes. The only tiles seen
in the rooms' lower rows are 0, 1, 10, 20 and 40. Rooms 7 and 8 take the wall
rules already noted in `opponent-barriers.md`, and rooms 1 and 2 are named in
`gate-barrier-distances.md`. `GetUndefineCellId`'s environment 6 branch is already
ported.

`Final.rsrc` holds 66 SHAP, 9 CUST (4000-4250), 4 CTBL (3500-3503), PIEC and
SHPL 3500. `tools/extract_assets.py` now exports its rooms as
`final_level14.json` during import.

## What the level depends on

Mode 13 carries over from level 13: SEQS -18 clears only the selected ID, so the
Prince arrives with the flame. IsShadowImbued 4:2590 is true for mode 13, or in
environment 6 with life above 2. SetupOpponent draws through 3:0852 there, and the
Kid's colours are CTBL 2001 at palette base 48, not 2000
([altar notes](temple-altar.md)).

## CODE 9, by the symbols

| Group | Routines | Lines |
| --- | --- | --- |
| Opponents | FinlCheckDeadOpp 9:00e2, FinlCheckGenOpp 9:0202, FinlGenerateOpp 9:02a6, FinlWatchOpps 9:0654 | 545 |
| Jaffar's path | JaffarSetToNextPos 9:09ca, SetToPrevPos, GoToPos and GoToPos0-3, HoneInOnExactPos, UpdateOppInfo 9:185a, ShadowInRange 9:1954 | 1,340 |
| The end | AllOtherJaffarsShimmerAway 9:090e | 56 |
| Scenery | AnimFinlSpider, AnimFinlCrystal, TriggerFinlCrystal, AnimFinlGargoyle, TriggerFinlGargoyle and their Draw routines | 560 |
| Fireballs | ATMFireball 9:23a8, DrawObjFireball, GetFireballImg | 175 |
| Environment hooks | 9:24ee (from FrameAdv 2:6654, the actors' check), 9:2674 (barrier for type 1), 9:27a0 (AutoCtrl's type table) | 215 |

FinlWatchOpps calls five CODE 2 routines, palette and song routines and
4:2442, so it looks like the battle's controller and the ending.

## Milestone order

1. Export rooms and connect NIS 3 to the native entry. Done for static
   scenery and placement; the mode-13 palette still needs visual comparison.
2. Read FinlCheckGenOpp and FinlGenerateOpp and spawn Jaffar's copies.
   The initial room-3 records are integrated below; the path is still open.
3. Recover the path (9:09ca-14b6), which is the largest part, then the
   final victory and ending.

Scenery can go in any order. The crystals and gargoyles have Trigger routines, so
plates or events reach them.

## First integration findings (2026-11-10)

- `SetKidDefaults` 2:5d10 copies LEVL 2013's native start room 1 into
  a5-0x5040. At 2:5e10-5e32, native level 14 with that start room selects
  SEQS 2 and overrides X to native 498 (port X 291). Other level-14 start
  rooms fall through to SEQS 5 at 2:5e34. `LevelDefinition` now models
  those entry values. `Temple.finish_exit` now follows NIS 3 into this entry
  when the imported scenery is available. It keeps mode 13 and max life.
- The environment-6 tile drawer table at a5-0x4aea has entries for tiles
  0, 1, 10, 20, 31, 40, 41 and 42. The nonzero level-14 entries route to
  CODE 9 (or CODE 3 for tile 10). The existing export harness draws all 11
  real rooms from the preserved code and Final.rsrc. Room 1 also calls
  CODE 9:1a4c from DrawCustomRoomImgs 3:2324. That routine fills the whole
  drawing rect with palette index 64 through PoPFillRect 17:6dd6, with
  SaveCurrentWorld and RestoreOriginalWorld around it. The exporter records
  that fill directly; the local result is a blue sky behind the tower.
- The importer stores the Final resource and export together. Existing
  imports need reimporting for a portable installation; a local
  `final_level14.json` can also be generated from the preserved Macintosh
  image. Without it, NIS 3 still ends safely at the level-13 complete state.
  Development navigation lists level 14 only when its rooms are available.
- An isolated real-resource export produced the 32 room slots (11 linked
  rooms), with the room-1 fill recorded once. All 11 linked rooms rendered
  in the port, and a hidden scene entered level 14, stayed alive for 25
  updates and preserved mode 13. A save/read round trip kept level, room,
  mode and X. Focused tests cover the original entry header, import file set,
  NIS callback, static renderer, handoff and save path.
- The CODE 9 enemy controller, final scenery animation, room palette changes,
  flame's full presentation, victory, credits/ending and a native full-frame
  comparison remain open. The native drawing harness supplies only the
  specified rectangle fill endpoint; it is not an independent pixel check.

## Jaffar generation block (2026-11-10)

The preserved `LEVL` 2013 is environment 6, opponent set 0, with an empty
opponent bank at native room 3 (`+0x2326`). `FinlWatchOpps` 9:0654 calls
9:0874, which checks the current native room is 3 and the environment is 6,
then supplies that bank's count to `FinlCheckGenOpp` 9:0202. The room-3 count
at `+0x2326` is increased by the record constructor 9:03c8. Source inputs
at a5-0x51e0 and a5-0x51fa are the **first active opponent's** selected
sequence and row (+0x28 and +0x0e from a5-0x5208); a5-0x50c4 is the
Prince's row. They must not be read as Prince sequence/facing.

- At count 0, row 1 is chosen if the Prince is on row 2; otherwise row 2.
  At count 1, selected `SEQS 238` blocks another birth. Otherwise row 2 is
  chosen when the first opponent is on row 1, row 1 otherwise. A match
  between that row and the Prince's row blocks birth. Next, `Rnd(20) == 0`
  admits it: `Rnd` is inclusive, so this is **1/21**. Count 2 stops
  further births.
- The column is 4 on row 1 and 2 on row 2, plus 4 when `Rnd(1)` is
  nonzero. The constructor 9:03c8 increments the room-3 count, calls
  `GetOppInfoIdx(3, old_count)` 6:3642 and writes cell `FirstInRow(row) +
  column` (14/18 or 22/26), native X a5-0x4b88[column] (411/615 or
  309/513), facing right below column 5, skill 5 and life `Rnd(2) + 3`
  (3-5), then starts `SEQS 238`. (This bullet was corrected on
  2026-11-15; an earlier reading swapped row and column and described
  cells 21-82 as path rows.) When the first palette-bank slot is empty,
  9:042a-043e and 6:40f6 assign variant 3; Guard.rsrc CTBL 752 gives
  Jaffar's red and white outfit. Its frame 233 resolves to SHAP 782. The
  port stores these as marked type-2 room-3 opponents and persists them
  through room visits and saves.
- Despite its preserved name, `FinlGenerateOpp` 9:02a6 is called from
  `DrawBFItem` 3:2cc8-2d16. It scans 38-byte background/foreground item
  records and chooses which entries to draw (including `0x1025..0x1028`,
  `0x1051..0x1058` and `0x6310`). It does **not** allocate the Jaffar
  opponent records. Its moving scenery remains a separate block.

`python -m tools.probe_final_jaffar_generation` executed 216 combinations
of count, first-opponent sequence/row, Prince row and supplied random results
against the original CODE 9:0202, with no differences. The probe supplies
only `Rnd` 17:6e06 and 9:03c8 as a record-constructor endpoint; it verifies
the call arguments but excludes the native constructor's writes, resource
loading, sound and drawing. The original LEVL and Guard SHAP/FRAM/CTBL are
checked separately by `tests.test_final_jaffars`. Port tests also reject an
immediate second birth during `SEQS 238`, a third birth, loss on room exit
and loss on save. They do not establish full frame cadence or pixel parity.

**Superseded (2026-11-15):** the "column" and "row" in this block are
swapped. See "The room-3 copies and their flasks" below: the copies stand on
rows 1/2 of room 3 and are ordinary guards; there are no path rows 4-8.

## Level-14 handoff and developer warp follow-up (2026-11-10)

The level-13 completion fallback was reachable when an older installation had
not imported `tower.json`, `TowerNIS.rsrc`, `Final.rsrc` and
`final_level14.json`. The launcher's required-file check now requests reimport
before play, and checks the final scenery header, room set and pressure-plate
schema. If files disappear during play, the exit names the missing level-14
files instead of reporting level 13 as the end. No Macintosh behavior is
inferred from this installation guard.

The level-14 F3 menu listed all linked rooms, but its generic room-entry branch
required solid tile 1 in the rightmost column. Rooms 2, 6, 8 and 10 have usable
floor elsewhere. Final-level warps now use the existing room-entry search and
reject room 9, which has no standing tile in its LEVL room data. A hidden Tk
regression runs NIS 3 from level 13 to level 14 and another chooses level 14
through the developer menu, then enters these sparse rooms and advances frames.
The source worktree's imported assets pass the installation check. This does
not establish which build or import the player used for the reported freeze;
the external Mini vMac launcher seen running during investigation is not this
port.

Focused shared-desktop verification: `python -m unittest -q tests.test_run_game
tests.test_temple_arrival tests.test_development_menu tests.test_final_jaffars
tests.test_opponent_generation` passed 151 tests. Dependency, Ruff, recovery
catalogue and `git diff --check` checks passed. Full discovery was interrupted
without a result after memory rose to about 15 GB in the shared desktop; the
focused result does not imply full-suite success. The next bounded gameplay
task remains the Jaffar position path and subsequent battle controller.

## F3 level-selection freeze follow-up (2026-11-10)

The reported freeze occurs on selecting level 14 in the developer map, before
pressing Go. A clean `build_development_map(LEVL 2013)` raised
`IndexError: FRAM action 148 is out of range`: the preview read raw room-11
`SEQS 197` (action 297), and room-6 `SEQS 2` (action 15), from zero-cursor
opponent records and tried to draw them with Guard FRAM 750. The live room-entry
path restores those records through `GuardRoomRecord.restore`, selecting
`SEQS 77` (action 166) for a living zero-cursor guard. The preview now applies
that same restoration for environment 6 before drawing its static actors.
This fixes a port preview path; it does not recover new CODE 9 battle behavior.

A regression checks all six original static records in rooms 6, 10 and 11,
their restored pose, the 11-room map, and the actual level-13 to level-14
dropdown click followed by menu redraw. The old preview path fails before
completing that redraw. The separate background map warmup can now build the
same level, so both cached and uncached menu selection work.

Focused shared-desktop run: `python -m unittest -q tests.test_development_map
tests.test_development_menu tests.test_temple_arrival tests.test_final_jaffars
tests.test_run_game` passed 160 tests. A cold temporary cache warmup wrote
`level-14.zip` and read back all 11 rooms. Dependencies, Ruff, recovery
catalogue and diff checks passed. Full discovery was not repeated after the
previous memory-limited run; physical desktop tests remained excluded.

## Level-13 completion and final-map layout (2026-11-11)

The previously tested NIS 3 handoff began by calling `Temple.finish_exit`
directly. Actual level-13 completion emits `SEQS -16`, but
`ScenePrototype.advance_level_events` did not create a `LevelExit` for 13;
`level_complete` then stopped scheduling with no NIS 3 callback. The dispatch
now includes 13. `GetEndSong` 5:4e0c-4e3e selects song 187 (`LvTemple`) for
environment 2, so the temple exit waits for that song before calling
`Temple.finish_exit` and playing NIS 3. A hidden-scene regression starts at
the real `-16` event, sees song 187 and the flight, and reaches native room 1
of level 14 with mode 13. Audio hardware timing remains unprobed.

The initial F3 map placed room 1 right of room 11 and room 2 above room 1.
The player corrected that reading: room 1 is above room 2, which is above
room 4; room 11 is a cutscene setting and is omitted from the F3 room picker.
This is a presentation exception. Original LEVL 2013 still links native room
1 down to 2, 1 up to 3 and 11 down to 4; live links and entry are unchanged.

The player supplied labelled Macintosh screenshots for rooms 3/9, 4, 5, 6,
7 and 8/10. These show the two shared views and the scenery's intended colours;
they do not establish the puzzle or opponent triggers. The original export has
no own CUST draw commands for room 9 and only a foreground SHAP 3001 for room
10. Their F3/live static scenery now uses the room-3 and room-8 backdrops,
respectively, with room 10's extra item. This is a screenshot-backed retained
view, not a native frame trace of the redraw sequence.

## Visual correction and cutscene routing (2026-11-11)

The port had applied Final CTBL 3500 to every room. In the preserved CODE 9,
9:1a90-1a9c loads CTBL 3501 at palette entry 64; 9:1d84-1d92 loads CTBL
3502 there; 9:00c6-00d2 loads CTBL 3503. The player's original screenshots
and a four-table render grid of the imported Macintosh shapes independently
identify 3501 for the tree/chess rooms 3-5 and 9, and 3502 for crystals/palace
rooms 6-8 and 10. The room-11 cutscene backdrop uses 3503. Room 1-2 retain
3500. A static renderer regression checks pixels from the tree, chess,
crystals and palace, plus the retained backdrops for 9 and 10. This fixes the
large colour mismatch; moving scenery, actors and cutscene animation still
need native-frame comparison.

The initial spell route has a concrete code gate: `FinlWatchOpps` 9:0654
calls 9:0760, whose 9:0764-0784 branch tests the current room word
a5-0x50bc in the saved Prince record for native room 2, a right-side drawing bound at a5-0x3566 no
greater than 486 (computed at 4:5d5a-5d6a),
and the saved Prince animation state a5-0x50c2 different from 4, then calls PlayNIS(5)
through 9:071a. The rest of 9:071a-075e resets the Prince through 9:05d2;
9:05fc-0622 chooses native room 4, row 1 and column 5. The CODE 15
dispatcher 15:07c8 maps NIS 5 to 15:0880, which opens `Happy.rsrc` from the
original A5 file record at -0x26b0. Despite that file name, its ANI callback
is `TransFuncJaffarMagic` 15:09fa. NIS 4 opens `Title.rsrc` and NIS 6 opens
`ThroneNIS.rsrc`; neither is this room-2 spell. The exact sprite/clip rectangle
that satisfies this spatial gate and a native end-to-end transition still need
tracing.
`GenCtrl` 6:0780-07a0 has a separate environment-6 branch that calls
9:0062; that routine puts the character in native room 11, at column 6,
row 2 and SEQS 71. The branch depends on the original actor state, and the
following death presentation needs a native execution trace. Thus room 11
remains an original resource and script destination, but is not a walkable
choice in the F3 overview. The player's account of an initial and a death
variant is consistent with these separate gates; their complete sequence
and the Jaffar laughter are still to be verified.

The player's proposed room-6 clone riddle and a Jaffar who appears only in
room 8/10 after that riddle remain hypotheses. CODE 9's path/state machine,
opponent visuals, transitions, full fight, animations and ending are open.
The preserved LEVL opponent banks give a useful boundary: native room 6 has
four raw-kind-3 records (actor type 6), native room 8 has none, room 10 has one
raw-kind-0 guard (actor type 2), and room 11 has one raw-kind-3 scripted actor.
The room-6 figures are Jaffar's false Princes, as the player clarified; they
use the Kid frame bank with CTBL 25008, distinct from the real Prince's
environment palette 25006. Their bank and initial sequence are now recovered
below; their riddle and controller remain open. Different LEVL tile and
opponent records show that the
shared views 3/9 and 8/10 are distinct logical rooms despite their repeated
backdrops. Room 10's one static record does not by itself establish when
Jaffar is revealed or how the room-6 riddle is solved.

The duplicated views should retain their separate room IDs. In original LEVL
2013, native room 3 links right to 9, up to 4 and down to 1; room 9 links left
to 3 and up to 5. Room 3 has standing tiles in its bottom row, while room 9's
three rows contain only a kind-20 column at the left edge and empty cells
elsewhere. Room 8 links left to 7 and up to 10; room 10 links down to 8. Room
8 has bottom-row platforms; room 10's two lower tile rows are empty and it
has one static opponent record where room 8 has none. Their shared backdrops
are a drawing reuse, not duplicate collision/transition states. A map overview
may group them visually, but teleport and simulation must still address each
room separately.

The first actor-art audit treated all set-0 records as type 2 and therefore
followed the wrong `LoadFrame` jump-table entry. A first presentation patch
substituted Kid pose 166 with the real Prince's red palette. The subsequent
native trace below corrects both assumptions: raw kind 3 is preserved before
the actor-table lookup, and actor 6 uses Kid pose 15 with the false-Prince
palette at initial room entry.

## Jaffar spell resource recovery (2026-11-11)

`tools.extract_intro.recover_final_spell` executes the preserved CODE 15
coordinator 15:0880 with the `Happy.rsrc` file-open endpoint supplied, then
executes `TransFuncJaffarMagic` 15:09fa for the 79 original SCRP animation
frames. It expands the ANI/SCRP sequence to 766 portable draw, timing, fade,
brightness and sound operations. The native coordinator selects CTBL 31001
at palette entry 70 and stores it for the callback fade; the isolated callback
probe's uninitialized palette pointer is replaced by that selected CTBL.
`extract_assets` now imports `Happy.rsrc` and writes `final_spell.json` and
its audio during the user's normal resource import. The original-resource
regression checks the expanded operation count, palette fade, sound IDs
31030/31031, and that `IntroAssets` decodes every referenced SHAP. The probe
supplies CODE 16 animation playback, Resource Manager open/close, shape
decoding and sound endpoints; it does not prove Macintosh pixel or
audio-device parity. The separate `pop2.hfs` check generated the scene JSON
and three sound files in a temporary folder. This checks import against the
preserved disk without writing its source resources.

## Room-2 spell gameplay gate (2026-11-11)

`tools.probe_final_spell_gate` executed 27 combinations of saved Prince room,
right sprite bound and saved animation state against original CODE 9:0760,
agreeing at the inclusive 486 threshold. It supplies only the saved-to-current
Prince record copy 4:4b02 and the full PlayNIS/reset continuation 9:071a; those endpoints are
excluded from the admission claim. `Final.frame_start` now snapshots the
pre-control Prince room/bound/animation for the next environment phase, so a
room-1-to-2 crossing first enters room 2 and plays the NIS on the following
frame. The port uses its decoded Prince sprite right edge for the native
`GetCharEdges` 4:5cbc bound; that equivalence is a geometry inference, not a
native frame comparison. The exit places the Prince in port room index 3
(native room 4), row 1, initial X 277 (native 484), and selects SEQS 55;
its first animation frame advances to X 283/action 207. A hidden scene test
plays the complete imported scene and checks room, sequence, mode and retained
life. The launcher now requires `Happy.rsrc` and `final_spell.json`, so an old
installation asks for a resource reimport before level-14 play.

The native reset services called by 9:071a-075e have not been executed as an
end-to-end CPU trace. The port keeps existing life/capacity and sequence mode
through the scene and uses its room placement helper to reset controls. These
state choices need comparison with a Macintosh capture. Next: compare
original and port scene frames and trace the final actor sprite bank. The room-11
death variant, copy puzzle, complete fight and ending remain separate work.

The original CODE 9 gate probe passed 27/27 cases. The hidden scene and import
tests passed 142/142; frame-phase, save, combat and generation tests passed
175/175. Dependency, Ruff, catalogue and diff checks passed. Shared-desktop
full discovery was attempted but stopped without a test verdict after memory
rose above 10 GB and free RAM fell near 2 GB, matching the earlier runaway
Tk-heavy run. Exclusive-desktop tests were not run while the user's desktop
remained in use. The focused tests are passes; the interrupted discovery is
not counted as a pass.

## Room-6 copy appearance (2026-11-11)

The player's Macintosh room-6 capture places four false-Prince figures at
the four saved opponent positions in native LEVL 2013: cells 25, 3, 7 and 14
with native X 509, 407, 611 and 458. All four have raw kind 3 at record +0x18.
`InitOpps` 6:2bca-2bfe preserves raw kinds 1/3/9/10 instead of replacing them
with the level's set 0; the original DATA table at a5-0x5280 maps index 3 to
actor type 6. At zero cursor, 6:2d64-2d88 selects `SEQS 2` for this type,
except that the room-11 record keeps `SEQS 197`. Their first Kid poses are
15 and 297 respectively. The room-10 raw-kind-0 actor follows the ordinary
type-2 branch and starts `SEQS 77`/pose 166.

`LoadFrame` 4:2a8e's actor-6 jump entry goes to 4:2ad6, loading FRAM and AFRM
through the Kid handles at a5-0x3472 and -0x3476. Pose indices are direct;
the type-2 `pose - 149` remap does not apply. `InitOpps` calls 6:3972;
its actor-6 branch 6:3986-39a0 loads `Kid CTBL 25008` at palette 32,
giving the false Princes their magenta shirts and purple turbans. Room setup
9:1da2-1daa selects the same table. The real Prince remains on CTBL 25006.

`tools.probe_final_clone_frames` executes the original selector, zero-cursor
sequence branch, frame/attachment copy and palette calls for all six static
records in rooms 6/10/11. All six agree. It supplies CheckLoadedOppSet,
room-11 sound, palette and Rnd endpoints, plus resident resource handles and pose
inputs. It compares raw FRAM/AFRM bytes, without the port's frame decoder.
Resource loading, AnimChar, full room entry, AI and combat are excluded.

The port preserves actor type 6 through room-record restore and snapshots,
and uses the Kid frames and false-Prince palette in gameplay and F3. Existing
snapshots without the newly added visual marker remain loadable. A snapshot
from the earlier visual-only patch migrates its marked type-2 copy to type 6.
These scripted copies currently advance their animation without ordinary
guard AI or terrain control; the CODE 9 riddle/path controller, later actions,
combat and room-11 death presentation remain to be integrated. The original
room-10 guard is not treated as one of the room-6 copies. The native actor-6
palette service also randomizes room-6 facing with `Rnd(1) - 1` at
6:39a2-39c8. The port currently retains the record's facing; recover the
controller and its random-state cadence before adding this draw.

The next bounded controller trace is now identified: `AutoCtrl`
6:4eb6-4f02 dispatches actor 6 through 6:4efe to 9:08e8, which selects
9:1526 in the final room 6 and 9:16fe elsewhere. The fatal-hit branch at
6:56a6-56ae calls `AllOtherJaffarsShimmerAway` 9:090e for an actor-6 target;
that routine selects SEQS 240 for other idle type-6 figures. Recover its
saved-Prince pose/distance gates, bank removal and animation timing before
connecting the riddle. This does not yet establish a room-10 reveal trigger.

Validation: six native selector/frame-bank cases and 249 focused port tests
passed. Full discovery ran all 4,101 discovered cases in separate module
processes to avoid the earlier Tk memory accumulation: 4,090 passed, 10 skipped,
and one failed. The failure is the existing
`test_cave_ambience.MenuTests.test_every_row_stays_inside_the_panel`
(row bottom 371 exceeds panel bottom 357), reproduced unchanged on published
main 7c5e98c. Exclusive-desktop tests remained skipped in shared mode.
Dependency, Ruff, recovery catalogue and diff checks passed. The reviewed
hidden gameplay image shows a red player and four purple false Princes.

## Room-2 audio freeze repair (2026-11-11)

The player's room-1 descent and room-2 teleport both reproduced an exception
in the real animation loop when audio was enabled: `AudioEngine.play_intro`
could not find cue `scene-0-31030`. The local installation had the scene JSON
and WAVs but lacked all three final-spell registrations in `audio/manifest.json`.
The Tk callback raised before it could schedule another animation tick, leaving
the game stopped. The earlier silent hidden-scene test did not exercise this.

The local audio registrations and files were rebuilt from the preserved disk
in a temporary directory, then only those three entries were merged into each
worktree's ignored manifest. `run_game.missing_assets` now checks the audio
of the final spell, tower, throne and temple programs along with other story
scenes, so an incomplete installation requests reimport before gameplay.
An installation regression rejects the precise missing-manifest case. A hidden
full animation-loop test with the real AudioEngine and supplied playback checks
both the downward room crossing and teleport, completes NIS 5 and reaches native
room 4. A separate real mixer check with SDL's dummy audio device also completed.
No live player window, shared save/settings or original resource was changed.

Focused shared-desktop checks: 185 tests passed across temple arrival,
developer map/menu, level ending, music transition and installation. Dependency,
Ruff, recovery catalogue and diff checks passed. Full discovery was not repeated
because the prior shared-desktop run grew to about 15 GB without finishing.

## Room-2 window gate and armed reset (2026-11-14)

Both reported blockers reproduced with real keys from the native entry in a
hidden scene: step to the roof edge, turn, climb down and drop.

- **Early spell.** `GetCharEdges` 4:5cbc stores a5-0x3566 at 4:5d5a-5d6a
  as left + width, where left already includes `X + 0xcf`: the edge is in
  working X (drawing X + 207) and exclusive. `Final.frame_start` passed the
  port's inclusive drawing column instead, so 486 admitted every room-2
  position. The landing on the outer sill now gives native edge 534 and
  plays no scene; the first step left reaches 481 and plays NIS 5 on the
  next frame, with the Prince hidden in the window as in the video at
  00:44-00:44.5. The edge comes from the existing collision bounds, which
  add 4:5e6e's sword extension.
- **Freeze in room 4.** After NIS 5 the reset 9:05d2 selects SEQS 55
  (9:05e2), sets a5-0x503c = 1 (sword drawn, 9:05ec) and calls
  `AddSound(14)` (9:05f6). The port selected SEQS 55 without the sword flag.
  SEQS 55 ends in the en-garde hold (pose 171), which only the armed
  controls leave, so no key did anything. `finish_spell` now sets the flag
  and queues sound 14. Advance, sheathe and run respond afterwards.

Also read but not changed: 9:05d6 sets the Kid draw mode a5-0x5020 to 16;
9:064a clears the Up-held catch flag a5-0x3480; 9:0758 writes -1 to
a5-0x5000. The port already draws the Prince with CTBL 25006 in level 14,
which matches the red Prince of the video after the spell.

`tests.test_final_spell_flow` now plays that real-key route with an
`AudioEngine` over mocked playback. It checks the landing and the window
step, the NIS 5 audio, room 4, and then advance, sheathe and run. Two direct
regressions cover the native edge and the armed reset. The previous code
fails all three (three failures, no errors). A separate run with SDL's dummy
audio device and the real mixer completed the same route with no Tk
callback exception. The route keys are supplied; they are not the video's
recorded input.

## Room-6 false-Prince controller (2026-11-14)

`pop2/final_tower.py` translates 9:1526, the AutoCtrl branch for type-6
figures in native room 6, and `CombatEncounter` now runs it for actor
type 6 in environment 6 instead of the generic scripted advance.

- **Shimmer of the last figure.** 9:1568-1594 counts the room bank (less
  one when the Prince is the shadow, type 1). With one figure left, a
  selected sequence other than 240 and the saved Prince alive
  (a5-0x50b6 < 0), it selects SEQS 240: nine idle frames, sound 270, then
  SEQS 196. The branch then falls through to the pose tests, so a
  shimmering idle figure can still strike.
- **Strike.** In pose 15 the figure strikes only when the Prince is alive,
  not in SEQS 44/6, type 0, in an exposed pose (FRAM +8 flag 0x40 or poses
  191-205) and not in animation state 3/4. With CharDistance 4:49ee:
  same facing 24 < d-15 < 71; behind it (d < 0) 24 < -15-d < 71 with a
  turn; facing a landing Prince (pose 145) 24 < d-15 < 78. The strike
  moves 15 px (AddCharX 4:2bae), draws the sword and selects SEQS 75.
- **After the strike.** Pose 171 sheathes (sword off, SEQS 92); pose 52
  after the Prince's death laughs (SEQS 197, sound 261); pose 109 rises
  (SEQS 49).
- **Fatal hits.** CheckStab 6:52b8-52ca deals 100 points when either side
  is type 6. The kill routine 6:5562 gives a type-6 victim SEQS 196
  (sound 260, poses 301-305, then `-17` removal). When a type-6 figure
  kills the Prince, 6:56a6 calls `AllOtherJaffarsShimmerAway` 9:090e:
  every other idle figure of the bank selects SEQS 240. The death method
  table at 6:570e gives 17 for a type-6 killer.
- **Transfer.** `RemoveChar` 4:48f8 removes a figure; in room 6 with
  SEQS 240 and the Prince alive it calls 9:19fa, which sets column 17,
  X 1132, row -3, path index 0 and SEQS 2. In the port the figure enters
  native room 8 at native X 622 (1132 - 510), row 0, facing left, marked
  `final_path` for the path controller.

The path controller that then drives this figure is described in the next
section. The room-6 random facing draw 6:39a2 is ported (2026-11-15): every
entry into native room 6 runs CheckSideRoomsForVisibleOpps 6:2b7e (PrepCut
2:5394, after KeepTime), whose 6:3972 call draws `Rnd(1) - 1` for each
actor-6 record in bank order; `Combat.enter_room` does this after the
records are restored. The port draws them before the crystals' triggers of
the same entry (the original draws them after); both use the game's Rnd.

`tests.test_final_tower` covers the decision windows without the scene,
then in a hidden level-14 scene: three hits dissolve three figures and the
last shimmers into room 8; a figure that kills the Prince stays while the
others shimmer; a crouching Prince ahead of a figure is struck and the
figure laughs. The earlier port played SEQS 2 without control, so these
scene checks fail on it. No native CPU probe of 9:1526 is claimed yet.

## Palace path controller (2026-11-14)

`pop2/final_path.py` translates 9:16fe and its helpers for the figure that
9:19fa moved to native room 8. The figure keeps actor type 6 and the Kid's
frames. It runs the Kid's own control routines, so it climbs, hangs, drops
and run-jumps like the Prince.

- **Decision (9:16fe).** The opponent record holds +0x1c mode (1 fleeing,
  2 closing in), +0x1e target position and +0x20 last position reached;
  all three are zero in LEVL. Against the ordinary Prince (type 0): if his
  armed word (+0x1a, -0x507a; corrected 2026-11-16, it is not ALIVE) is 1,
  a drawn sword, and the figure is within 91 px (and not in poses 207-210
  or 158), the Kid takes SEQS 241 with AddSong 264 and armed becomes -1:
  the sword is taken. Otherwise, on the figure's row while a5-0x5004 >= 4
  (his turn count, 4:1fb2), it flees if his life is above 2 or he is in
  SEQS 242. Otherwise it closes in only if armed is -1 (no sword). Against the shadow (type 1) it
  flees while his life is above 2 or he casts, and closes in otherwise.
  SEQS 230 in mode 12 (burnt) increments a5-0x4f92.
- **Positions.** DATA a5-0x2a06 gives four 22-byte entries (global column,
  row, facing, arrival X1..X2 in the target room's coordinates, then the
  ShadowInRange 9:1954 zones). In order: upper right of room 8, lower
  right of room 8, lower left of room 7, upper left of room 7. Fleeing
  (9:0b28) moves away from the side where the Prince stands. Closing in
  (9:0a42) moves the other way. On arrival with the Prince in range
  (9:0ba6), 9:09ca turns to face him or selects SEQS 242.
- **Spell.** Pose 281 of SEQS 242 plays sound 289. At pose 282, with the
  Prince still in range, 9:14c8 selects SEQS 244 for the figure. The
  Prince gets SEQS 71, sound 12, 100 points of damage and death method 17.
  In range (9:0ba6) means the same row and the Prince's life above zero.
  The pose tests at 9:0bee-0c2c read -0x504c, the Char record: the
  figure's own pose must be exposed (FRAM 0x40, or 191-205) and must not
  be the crouch (109). A crouching Prince is still struck. On the upper floor the figure must be at
  global column <= 6 or >= 13. On the middle floor both must be on the same
  side of column 13.
- **Routes (9:0d28).** 0ed2/107c/11fe/136e choose the Kid routine from the
  position, the row and the pose: forward 6:11a0, standing jump 6:15ea,
  DoJumpUp 6:1600, climb 6:1998, release 6:1a84, DoRunJump(4) 6:1c14,
  StairClimbing 6:0e8e (lower over the edge), DoStepFwd 6:1276. They also
  select SEQS 5 (turn), 13 (stop) and 49 (rise). HoneIn 9:0dac steps into
  the X window and sets the last position reached.
- **Away from the palace.** JaffarUpdateOppInfo 9:185a puts a travelling
  figure at its target (X1 + 10, the position's facing, SEQS 2). The port
  applies this while the Prince is outside native rooms 7/8.

HitFloor 6:036a-0374 lands types 1 and 6 in SEQS 17 (crouch) instead of
the armed SEQS 63; the port's landing rule now follows that. The type-6
figure's footsteps (`-15 1`) are played like the Kid's.

Port choices, not recovered behaviour: the Kid routines reuse the Prince's
terrain helpers (ledge, step, run-jump and release tests) with the figure's
foot column. CutOpponent 6:424c -> UpdateOppInfo 6:30b0 moves a record
that leaves the Prince's room to the other room's bank and drops it from
the active list, so out of view the figure keeps the move it was in and
resumes when the Prince comes (6:42fc-430a). The port lets only a burning
figure (SEQS 230) finish out of view, so the victory still arrives. The
video supports the view rule: the Prince crosses room 7's upper floor
unharmed while the figure stands in room 8. The relocation's call site is assumed, not traced.
The turn count (a5-0x5004) and the shadow are now ported (next section),
so the figure flees from a strong shadow.

`tests.test_final_path` covers decisions with a recording Kid. In a hidden
scene it checks four cases: standing on the figure's floor is fatal
(method 17); the figure waits in room 8 while the Prince is in room 7; a
Prince below sends it through room 7's upper floor and down its ledge
toward position 2; and relocation away from the palace. No native CPU
probe of 9:16fe is claimed yet.

## Route playthrough fixes (2026-11-15)

Playing native room 1 to Jaffar in a hidden scene found six faults. Each
has a regression in `tests.test_final_route` or `tests.test_final_path`
that fails on the earlier port.

- **Room 3 right exit (CutChar 6:4c50-4c6c).** In environment 6 native
  room 3 refuses its right exit, so the Prince bumps against the wall
  column and never reaches room 9. The port had let him walk into room 9.
- **False Princes' strike range (6:5b38).** For a type-6 defender the
  Kid's window is (16, 86) facing each other and (16, 79) facing the same
  way (6:5bd2-5c06); a type-6 attacker gets (16, 79) (6:5cd4-5cec). The
  ordinary (61, 99) left all four room-6 figures out of reach. Not ported:
  with sword type -0x500a == 2 (levels 7-8) the Kid's high bound is 10
  lower.
- **Flasks.** The palace flasks are library-1 front commands left out of
  the static room. `animated_layer` now draws them on the front pass in
  environment 6, and `Final.level_events` consumes potion events, so
  drinking heals (`advance_potions`, shared with the caverns).
- **Jaffar's in-range pose** reads his own record, as above.
- **Jaffar out of view** freezes in his move, as above, instead of running
  on through room 7.
- **Casting at rest.** After the eight turns the waiting controls own the
  Ctrl bank, and their Ctrl branch drew the sword. It now calls the same
  DoKidEngarde 6:1f4c-1f72 cast as the standing gate.

Played in the hidden scene: room 6 (climb, kill the left figure from 76 px,
run-jump, kill the right one, descend, kill the bottom one, the last
shimmers away), the climb through rooms 7/8, the eight turns (12 -> 4 life
with the body's fall), the chase across both views, and a cast on
Jaffar's row that burns him (SEQS 230 to pose 185) and returns to the
introduction.

Resolved 2026-11-16: standing in range on Jaffar's floor killed before
four turns were possible (SEQS 242 reaches pose 282 in 11 frames; four
standing turns take about 15). The missed gate is 9:17ec-17fc: closing in,
and so the cast, needs the Prince's armed word at -1. The port read ALIVE
(+0x1c) where 9:16fe reads +0x1a, so it cast at every living Prince. A
Prince who keeps his sword, sheathed or drawn out of reach, can stand on
his floor and turn; a drawn sword within 91 px is taken first (SEQS 241),
and only then does he cast. This also explains the video (he stands at the
upper right while the Prince is on his floor, then flees) and the guide's
"the final Jaffar resists the sword". The scene now also drops the drawn
sword when it is taken (a `disarm` combat event); before, the scene's
sword flag re-armed the Kid on the next frame. `tests.test_final_path`
rejects the ALIVE reading (decisions and three hidden-scene cases).

## Shadow form and magic fire (2026-11-14)

`pop2/final_magic.py` holds the rules. `Final` in `pop2/environments.py`
runs them in the scene. Native facing word 0 is the port's facing 1.

- **Turns (4:1fb2).** The standing turn calls it at 6:1184, before
  JumpSeq(5). This happens in environments 2 and 6, but not in native
  rooms 1/2 of level 14.
  - A type-0 Kid already in SEQS 5 adds one to a5-0x5004; otherwise the
    count becomes 1.
  - On the fourth turn, palette 2000 + IsShadowImbued is loaded at 48.
  - From the fourth turn on, each turn plays sound 288 and costs one point
    (DecLifePts(1)) and one unit of capacity. A fatal point gives SEQS 71
    with death method 17.
  - On the eighth turn, the 4:2046 test reads the life from before this
    turn's pending point. Above 4, LeaveBody runs and the Kid becomes type
    1 (draw mode 0x30, SEQS 2, sound 260, song 290). Otherwise he takes
    SEQS 71 and 100 points.
  - 6:1188 skips the turn after SEQS 71.
- **Flashes (4:2174).** GenCtrl runs this before the turn decision.
  - Pose 15 clears the count.
  - Poses 45-52 with a count of 4 or more select draw mode 0x30 when
    4:250a says so.
  - Any other sequence clears the count and restores the palette.
- **The body (4:2206, 6:0bcc).** LeaveBody shifts the Kid 25 px away from
  an empty cell, first behind him, then ahead. It then leaves a type-0
  record with his position, facing and life, running SEQS 71 (179, then
  SEQS 213 to 185). While the body falls through poses other than
  179/183/185, every frame costs the Prince a point and a unit of
  capacity. From 12 life this gives 7 at the change and 4 after the fall,
  as in the video.
- **Lying down and rejoining.** The shadow's Down (6:1068 -> 4:1f1e) acts
  within 51 px of the body (4:24b2 distance: 6 more when both face the
  same way):
  - A shadow facing away from the body turns and moves 6 px.
  - X then becomes X - (d - sign * 7), and the shadow takes SEQS 71.
  - At pose 185 within 2 px, 6:0b5a -> 4:25ce removes the body and gives
    type 0, draw mode 0 and SEQS 231.
  - A dead shadow goes back into the dead body (4:2338).
- **Cast (9:2674, from DoKidEngarde 6:1f4c).** This needs the type-1 Kid
  in native rooms 7/8 of environment 6.
  - With life above 2, a barrier closer than 35 moves him back by
    AddCharX(d - 35). Then SEQS 242, DecLifePts(2) and AddSong 265.
  - Otherwise nothing happens, and no sword is drawn either way.
  - Poses 272-281 play sound 258 (9:2868). Pose 281 throws (9:2880): X is
    AddCharX(43) - 207, Y is the Kid's Y - 55, the room is his, and the
    speed is +-12.
- **Flight (ATM 9:27a0, 9:25e4).**
  - The speed changes by 3 a frame while below 25, reaching 27.
  - In room 0 the fire ends.
  - The wall test reads the cell at X - 22 + image width, or at
    X - 22 - width when flying left. The width is a5-0x44e4, from the last
    drawing. A negative X steps one column left.
  - At a wall the fire aligns to the cell, bursts (state 8), plays 259
    and stops song 265.
  - Flying frames cycle through four images, with sound 258. A burst shows
    frames 0-3 and ends.
  - When the fire ends with the Prince's life at 2 or less, palette 2000
    returns.
  - The drawing (9:23a8) moves the fire into a side room as it crosses the
    edge. It uses SHAP 4115-4118 in flight and 4119-4122 for the burst, in
    CTBL 2001, centred on its point.
- **Burning Jaffar (9:24ee).** For a living type-6 record not in SEQS 230:
  - The fire must be on his row and not bursting.
  - The span [x + speed - 17, x + speed + 17] must overlap his edges, ±510
    between the palace rooms.
  - Then the fire bursts at his edge, he takes DecLifePts(100) and SEQS
    230 (AnimChar at once), and sound 289 plays.
  - SEQS 230 ends in mode 12 at pose 185. 9:16fe then increments a5-0x4f92
    to 15, and CODE 2:4596 starts NIS 11 and the Hall of Fame.

Port choices:
- The port's controller runs only in view, so the burnt Jaffar is also
  read directly by `Final.level_events`.
- The victory plays NIS 11 and the Hall of Fame, then the introduction
  (see the next section).
- The lie-down's native Y - 1 is left out to keep the Kid on his floor.
- The shadow's fall off the bottom of the screen (4:3780) is not
  separately ported.
- The flame behind the shadow reuses the temple's SetupShadowFlame
  drawing (4:2630) while his life is above 2.

`tests.test_final_magic` checks the following:
- the flash table, body distance, fire acceleration, wall bursts and the
  hit span;
- in hidden scenes, eight turns from 12 life leave the body and end at 4;
- a weak Prince (8 life) collapses on the eighth turn with method 17;
- lying down on the body rejoins it;
- a dead shadow returns to the dead body;
- from room 7, the fire burns Jaffar in room 8 and the game returns to the
  introduction;
- with 2 life the shadow cannot cast and draws no sword.

No native CPU probe is claimed.

### NIS 11 and the Hall of Fame (ported 2026-11-15)

**NIS 11 (HappyEnding 15:3c76).** `tools.extract_intro.recover_happy` runs
the coordinator with Happy.rsrc open (a5-0x26b0, resource offset 1000000):

- 15:44e2, the victory bedroom, runs inline. It uses palette 0x7919 and
  SHAP 0x7a47, then ANI 0x7918 with flags 0x0e and callback
  TransFuncSetCTABframe1 15:09c0, which sets brightness (0x51, 100) at
  frame 1.
- SetForeColor 17:0eae and the PaintRect trap after it become a `fill`.
- The epilogue ANI 30004 (286 frames, callback HappyFunc 15:411a) is
  recovered one frame at a time into a table (`happy_frames` in
  `happy.json`). Each frame's callback runs with persistent state
  a5-0x2340/-0x2342/-0x2344 and sound status a5-0x1f7c/-0x1f6e; the
  sound-ensure call at 15:448c is left out. The player then applies the
  rules of HappyFunc that depend on time:
  - frames 131..141 with song cue 102 or later (a5-0x1f6e, set by
    PoPAudioCallBack 16:2054) move the remaining frames on to 142, once;
  - from frame 3, whenever no digitized sound plays (a5-0x1f7c), one
    frame passes and HappyDialog 15:44b0 starts the next line: voice
    30004 + line and text 30000 entry line + 4, for five lines, then the
    panel is cleared;
  - past frame 182, once song 30020 has ended, the callback returns -1 and
    the animation ends.
- HappyDialog draws its panel through NISTextDraw (a5-0x27de) on the
  picture under it, in colours (8, 255), (6, 253), (5, 254).
- SetNISCTAB flags 0x2000/0x4000 blend the current or target table with the
  third table (palette flag 0x1000) as (a * p + b * (100 - p)) / 100.

Timeline in the port: bedroom 0-6 s, song 30010 from 8.35 s, the three
narrative panels, the epilogue from 32.1 s, voices and dialog 32.7-46.1 s,
fade 46.6 s, the observer from 50.6 s, done at 64.7 s once song 30020 ends.
This matches the user's Macintosh capture (circle on black about 50 s,
observer dimmed about 62 s, scene about 64.7 s). In that timeline the 286
frames run out before song 30020 ends, so the -1 path is checked only with
a shortened song in the test.

**Hall of Fame (CODE 2).** `pop2/hall_of_fame.py` and the `hall` menu page:

- HOFAddPlayer 2:260c: at most five 30-byte entries (Pascal name, word
  minutes); a new score goes before the first entry it equals or beats; a
  full table drops its last entry and a lower score still takes fifth
  place.
- GetHallOfFameName 2:2220: '<', '>' and NUL are refused and names stay
  below 24 characters; Return asks whether this is the name to insert
  (2:235e-237e); an empty name is not written (2:254c-2560, 2:1f88).
- After the name is saved the table stays up for 900 ticks or a click
  (2:1fa4-1fd8). ShowHallOfFame 2:28c2 (Alt+H) shows the table.
- CODE 2:4596-45c2: only with minutes left does the victory play NIS 11 and
  the Hall of Fame; the next level becomes 0 and the presentation restarts.

Port choices:
- The table is JSON beside the saves (`hall_of_fame.json`), not the
  Macintosh Hall of Fame file (2:29de, creator 'PRNc').
- The page uses the port's menu style; its look awaits the user's review.
  Escape leaves the victory row unnamed, as an empty name does. An empty
  table shows "No names yet" (ShowHallOfFame shows nothing then).
- ShowHallOfFame's song cue 180 and the native pixel-width limit on the
  name are not ported.
- The introduction is started under the Hall page and runs once it closes.
- `happy.json` is optional at launch; without it the victory goes straight
  to the Hall of Fame. A reimport writes it.

`tests.test_happy_ending` checks the recovered program, the dialog order and
the -1 end, the table rules, the page and the victory flow through real key
events. No native CPU probe of HappyFunc's timing rules is claimed.

### The defeat variant (ported 2026-11-15)

GenCtrl 6:0560 sends a dead actor (ALIVE a5-0x503a >= 0) to 6:0762. At
6:0780-07a0 a dead type-0 Kid in environment 6 with ALIVE > 6 calls 9:0062:

- 9:0066-0074: nothing happens when he is already in native room 11
  (a5-0x5040) or when no rebirth point exists (a5-0x5018 is zero).
  SaveRebirthPtStatus 2:1674 allocates that bank at a checkpoint;
  SetRebirthPtInitials 2:179e frees it at level start. Level 14's only
  checkpoint (LEVL 0x39a6) is native room 4, cell 14.
- 9:0076-00a4: the target room a5-0x4fc4 (the view follows, 2:5344) and
  the Kid's room become 11; column 6 gives X a5-0x4b88[6] = 513 (scene
  306); row 2 gives Y 2 * 120 + 112 = 352.
- 9:00a8-00be: SEQS 71 (pose 179, then SEQS 213 to the dead pose 185) and
  AnimChar five times.

Room 11 is the princess's bedroom. Entering it restores its one record, a
type-6 figure (the false Prince's frames and CTBL 25008) at zero cursor.
InitOpps 6:2d64-2d86 keeps its SEQS 197 (poses 297-300, then standing) and
calls AddSound(0x105): the laugh, sound 261. The two sound routines are
AddSong 5:4d58 and AddSound 5:4d84; 6:2d82 is the latter.

The port runs this in `Final.defeat` from the environment's GenCtrl hook,
after the death counter: the scene moves to port room 10 without the audio
reset of a developer warp, so the death song continues. The retry restores
the checkpoint as usual. Without a checkpoint the body stays where he fell.
A dead shadow (type 1) takes 6:07a2 -> 4:2338 instead (already ported).

Exclusions:
- AutoCtrl sends type-6 figures outside room 6 to the palace path
  controller 9:16fe. In room 11 the port only plays the figure's sequence.
  With the Prince dead and fewer than four turns counted, 9:16fe neither
  flees nor closes in; the flee branch for four or more turns on the same
  row is not run in room 11.
- No native CPU probe and no Macintosh capture of this death is available.

`tests.test_final_magic.DefeatSceneTests` checks, in hidden level-14
scenes: the move on the first frame after ALIVE 6, room 10 row 2 near X 306
in the dead pose, the laughing figure and one sound 261, a death without a
checkpoint staying in place, and the retry at the checkpoint. Without the
change three of the four fail.

### The room-3 copies and their flasks (ported 2026-11-15)

**Correction.** The generation block above read 9:0202's two pushed
values the wrong way round. 9:0202 pushes d6 and then d3, so the
constructor's first argument `$8(a6)` is d3 and its second `$a(a6)` is d6.
9:03c8 uses the first as the **column** (X from a5-0x4b88, the facing,
-0x504a) and the second as the **row** (FirstInRow, -0x5048 and +0x20).
So d6, the value compared with the Prince's row, is the copy's row (1 or
2), and d3 (2 or 4, plus 4 from `Rnd(1)`) is its column. There are no path
rows 4-8: a copy stands on room 3's row 1 at column 4 or 8 (cells 14/18,
native X 411/615) or row 2 at column 2 or 6 (cells 22/26, X 309/513). It
is born on the row the Prince is not on. Columns below 5 face right
(9:040c-0420). Life is `Rnd(2) + 3`, so 3, 4 or 5 (the old port drew
only 3 or 4). The constructor also arms the cue word (-0x503e = 1), sets
ALIVE -1 and calls AddSound(0xf3), sound 243, as SEQS 238 starts.

**Control.** The copies are ordinary type-2 guards: AutoCtrl 6:4e90's
table sends type 2 to 6:4f04 -> 6:4f60, the ordinary guard controller,
with skill 5. The port no longer parks them in their sequence: they
alert, draw and fight like the other guards.

**Death (FinlCheckDeadOpp 9:00e2).** GenCtrl 6:0762 sends a dead type-2
actor in native room 3 of environment 6 to 9:00e2 (6:07b8-07d6). PlayerCtrl
4:3d24 still counts ALIVE 0..6 while the cue word is set and then plays the
opponent's death song as usual (4:3d32).

- At ALIVE 6: ReadCell(room, column, row) 4:27ee, then `Rnd(2)` is always
  drawn. With a nonzero draw, a floor cell (kind 1), fewer than four
  animated objects (a5-0x43e6) and a cell (`row * 10 + column`) outside
  22-24, room 3's tile becomes 10 and its foreground `(draw << 5) |
  0x4000`: 1 a healing flask, 2 a life enhancement. TriggerFlask 5:1ce8
  starts the bubbling at `Rnd(26) + 1` and 5:18f0 redraws the cell. ALIVE
  becomes 7.
- 9:01d4-01e2: once the cue word is clear and ALIVE > 6, ALIVE goes up by
  one per call.
- At ALIVE 96, unless +0x28 is already 239: SEQS 239 (poses 242-254), sound
  243, the target (a5-0x5098) reset when it was this copy. The sequence's
  -17 is RemoveChar 4:48f8, which takes the record out of the room-3 bank,
  so FinlCheckGenOpp can bring another copy: the respawning opponents the
  strategy guide describes.

Port: `final_jaffars.dead_copy_step` is the routine; combat runs it from
the dead-guard path with `death_song_frames` as ALIVE up to 6 and
`final_alive` after it, queues the flask in `final_drops`, and removes the
copy on SEQS 239's -17. `Final.place_drops` writes it into the flasks'
state (tile and phase), and `cavern_flask_instances` gives such a flask the
same front command as the imported ones (shape 3001, X `column * 51 + 29`,
bottom `row * 120 + 110`), so it is drawn, bubbles and can be drunk.

Evidence:
- `python -m tools.probe_final_jaffar_record`: 144 original cases run
  9:0202 and 9:03c8 with FirstInRow 4:322a and GetOppInfoIdx 6:3642
  native; Rnd, the palette-bank helpers 6:40f6/41dc, 4:31fa, 4:34e2,
  SetSeq, 4:2c0c, AddSound and 4:4a46 are supplied and only record their
  arguments. The room-3 count, the record's cell, X, facing, skill,
  palette slot, index, life words and row, the character words and the
  target agree. A model that always faces left is rejected.
- `python -m tools.probe_final_dead_copy`: 1684 original cases of 9:00e2
  with ReadCell, FirstInRow and the room loader 5:0004 native and Rnd,
  TriggerFlask, the redraw, SetSeq and AddSound supplied. ALIVE, the
  level's tile and foreground bytes, the supplied calls and the target
  agree. Dropping the 22-24 exclusion, allowing four objects or moving
  the shimmer to 97 is each rejected.
- `python -m tools.probe_final_jaffar_generation` (216 cases) now
  compares the constructor's arguments as (column, row).
- `tests.test_final_jaffars` and `tests.test_final_copies` (hidden level-14
  scenes): the copy on row 1 at cell 14, a copy that draws and wounds a
  Prince on its row, the life-enhancement flask on its cell at ALIVE 6,
  drawn in the front layer, SEQS 239 on the 97th frame after the death,
  removal 13 frames later and a new copy, and drinking the flask
  (maximum life 4 -> 5).

Exclusions:
- a5-0x43e6 is the trob count of the room on screen (capacity 20,
  5:20bc). KeepTime 2:4fd0 adds one per flask, per cell of kinds
  28/29/31/40/43 and, in native rooms 6-8, per crystal/gargoyle cell
  (foreground 0x1000). Room 3's spider is kind 40, so with it three flasks
  already refuse a fourth. The port counts these cells in the Prince's
  room; the neighbouring rooms' edge cells that KeepTime also scans are
  left out (room 3 has none of those kinds).
- A copy that dies outside native room 3 keeps the ordinary body (6:07b8
  requires room 3); the port does not let copies follow the Prince out of
  room 3 (it has no exit they can walk through: CutChar refuses the right
  edge and the other links are vertical).
- No Macintosh capture of this room is available (the user's winning
  video skips it), so the fight's timing and the pixels of SEQS 238/239
  are unchecked against the original.

## Moving scenery: fangs, face, crystals and gargoyles (ported 2026-11-15)

Every moving object is a trob (AnimTrobs 5:0c38). AnimTrob 5:0cd6 loads
the trob's room (5:0004) and its cell's foreground word into a5-0x4818
(5:29a8), dispatches on the type through the table in the unmapped gap at
5:0d0e, and writes the word back (5:0e24). The drawing hooks read the same
word from the cell's draw record (a5-0x4f8c + 0x14), move a CUST record of
the room and call DrawCustomRoomImg 3:2438(record, pass). All tables are in
the A5 data.

- **Room 3, the spider's fangs** (kind 40, cell 23; CUST 4050).
  AnimFinlSpider 9:1bf0: bits 0-2 a frame, bits 3-10 a timer. With the
  timer at 0 the frame advances to 5 and the rectangle a5-0x298e is
  redrawn; at frame 5 the timer becomes `Rnd(60) + 30`. When the timer
  runs out, 9:1c66-1c74 draws `Rnd(5) + 1` and sets frame 7 (a5-0x5002,
  zero in play, would restart the long wait instead). The timer therefore
  never returns to 0: the fangs move once. DrawFinlSpider 9:1cba (pass
  11) draws a5-0x29a6[a] + 3 and a5-0x299a[b] + 3; with the timer at 0
  both are the rest pose, so frames 1-4 are never shown, and frame 5
  shows the right fang's record 4. The frame-7 word reads a5-0x29a6[7],
  past the six-entry table, which is a5-0x299a[1]: records 8 and 7, both
  left-fang images. That change is not redrawn (no 5:19f8 call), so it
  appears when the room is drawn again: from the second visit on, the
  right fang is missing. Running the native renderer (`recover_room`)
  over the words 0x0, 0x2d, 0xf and 0x80d confirms the records drawn for
  cells 23 and 24 (column 4 draws from the same word).
  **Port exception (the user's choice, 2026-11-15):** an index past the
  first table draws the left fang at rest, so both fangs stay on every
  visit. `spider_images(word, native=True)` keeps the original reading,
  which the probe checks.
- **Room 4, Jaffar's face** (kind 31, cell 1; CUST 4075). 9:1b3a counts
  the word up by one per frame. Counts 12-15 are redrawn and 9:1ba4 (pass
  11) draws records a5-0x29ae[count - 12] + 3: 3, 4, 4 and 3, a wink. At
  16 the trob ends with the word cleared and no redraw, so the half-closed
  eye stays until the room is drawn again. It happens on each entry.
- **Room 6, crystal glints** (CUST 4125). Cells with foreground 0x1000 get
  TriggerFinlCrystal 9:2068 from KeepTime 2:5182-51a8 at room entry:
  index from a5-0x2872 (reset by the room hook 9:1d84; nine at most),
  wait `Rnd(40)`, the trob flag, AddTrob type 41. AnimFinlCrystal
  9:1e30: bits 4-10 a wait, or frames while 0x800 is set. An ended wait
  activates; frames 1-5 are redrawn; frame 6 starts a wait of `Rnd(40) +
  40` without a redraw, so the last image (record 8, the smallest glint)
  stays drawn. DrawFinlCrystal 9:1f5e (pass 1) draws record
  a5-0x2986[frame - 1] + 8 moved by a5-0x297c[index] (dy, dx) in pass
  a5-0x2958[index].
- **Rooms 7 and 8, gargoyle faces** (CUST 4150, 4175). TriggerFinlGargoyle
  9:233a: index from a5-0x2874, which 9:1d84 starts at 0 in room 7 and 2
  in room 8, AddTrob type 42. AnimFinlGargoyle 9:20dc is the crystal
  logic with frames 1-7; an index outside its room's pair ends the trob.
  DrawFinlGargoyle 9:2238 (pass 1) draws record a5-0x2946[frame - 1] + 2,
  plus 4 for every gargoyle but the first, at a5-0x2938[index] (bottom,
  x) in pass a5-0x2928[index], then puts the record back at 0, 0, pass 11.

Port: `pop2/final_scenery.py` holds the routines and tables.
`Final.advance_scenery` sets up a newly entered room (KeepTime's scan;
the fangs' and face's words carry over, crystals and gargoyles are
triggered again) and steps the room's trobs in cell order with the game's
Rnd, after the room-3 drops. `CavernState.final_scenery` keeps the words
and `final_scenery_drawn` the word each image was last drawn from: it
changes on a redraw request or on entering the room, which gives the
original's lingering images. `draw_final_scenery` draws pass-0/11 images
in the back layer and pass-1 images in the front layer. The static room 3
no longer contains the exported rest pose (SHAP 4053-4060).

Evidence:
- `python -m tools.probe_final_scenery`: 2326 original cases run the face
  routines, AnimFinlSpider, DrawFinlSpider, the crystal and gargoyle
  routines and both triggers in Unicorn over the original A5 data and the
  room's original CUST record. Rnd, the redraw call 5:19f8,
  DrawCustomRoomImg (with the record's bottom, X and pass at the call),
  AddTrob and the OffsetRect trap are supplied. Words, Rnd arguments,
  redraw requests, drawn records and positions, trob ends and counters
  agree. States the routines never produce are left out: an active frame
  past the last one, gargoyle indexes above 3 and active-fang frames 6-7.
- `tests.test_final_scenery`: the fangs' single movement and the
  never-zero timer (a model that animates again is rejected), the frame-7
  images, the wink, crystal and gargoyle cycles and records, room-entry
  triggers, and in hidden level-14 scenes the fangs drawn from their word
  (absent from the static room), the frame-7 word shown only after
  re-entry, room 6's glints, and a save round trip.

Exclusions:
- In the original, an actor moving over these cells redraws them from
  the current word, so a lingering image can change in patches before
  the room is drawn again. The port redraws only on the trob's own
  request or on room entry. DrawFinlSpider's raised clip top for cell 23
  is not needed with full-room drawing.
- KeepTime also scans the neighbouring rooms' edge cells; a crystal or
  gargoyle cell there would get a trob (and Rnd draws) in the original.
  The port sets up only the room on screen.
- 9:1d84 also asks for songs (269 in room 6; 262 in rooms 7 and 8 under
  conditions); see the room themes section below.
- No Macintosh capture of these rooms is available to compare pixels.

## The mental rooms' themes (ported 2026-11-15)

Environment 6 has no ambient bank (bank 6 is empty), so before this the
final level was silent apart from effects, and the audio import did not
render any of its songs. CODE 9 plays four room themes:

- The CUST enter hooks: 9:1a90 (native rooms 3-5) adds Spider (268) in
  room 3 and ChessRm (267) in room 4, then waits on sound 30500
  (WaitSndId 16:270e); 9:1d84 (rooms 6-8) adds Crystal (269) in room 6,
  Escher (262) in room 7 when a5-0x4ff2 is set, and Escher in room 8 when
  it is not already playing and room 8's bank holds an opponent (LEVL
  0x26e6 = 0x20e6 + 8 * 0xc0).
- FinlWatchOpps 9:0654, every frame, when the music is on (a5-0x3738), the
  current song (a5-0x4398) has ended (PrinceSndOn 5:52c8), the Prince is
  alive (a5-0x50b6 < 0) and no level change is pending: through the jump
  table at 9:06aa (in an unmapped gap; decoded with capstone) room 3 asks
  for Spider, rooms 4 and 5 for ChessRm, room 6 for Crystal while its bank
  holds opponents (LEVL 0x2566, the false Princes; otherwise Crystal is
  stopped with PrinceResetSnd 5:5252), room 8 sets a5-0x4ff2 and asks for
  Escher, and room 7 asks for Escher once a5-0x4ff2 is set. 9:06fc-0714
  adds the song unless it already plays. a5-0x4ff2 is cleared when an
  environment-6 level starts (2:6e74).

Port: `pop2/final_music.py` (`entry_song`, `watch_song`) and
`Final.ambient_audio`; the themes are ambient songs, so the port's music
switch silences them. `CavernState.final_escher` is a5-0x4ff2. The audio
import now renders `FINAL_SONGS`: 262-265 and 267-270 and Shadow (290),
which also gives sound to the shadow form, the spell (265) and the body's
dissolve (264) that were already requested. Happy1 (266, a .gmf song)
renders silent and is left out. An older import has no files for these
and stays silent until the game is imported again.

Evidence: static reading of the hooks and of 9:0654-0716 including the
decoded table; `tests.test_final_music` checks both tables (a reading
that swaps rooms 7 and 8 is rejected) and, in hidden level-14 scenes,
each room's requests, the Escher flag, no new theme while a song plays
and nothing with the music off. No native CPU probe and no capture.

Which rooms run each hook: LoadCustomRoomData 3:1378 loads CUST 3975 +
native room * 25 and, with a record, takes the enter hook through
3:18aa (table a5-0x4c2e by CUST kind, 3:13ec-13f8). The
expanded DATA gives kinds 25-27 (rooms 3-5) the 9:1a90 entry, kinds 28-30
(rooms 6-8) 9:1d84, kind 23 (room 1) 9:1a4c and kind 9 (room 11) 9:00c6 (the
CTBL 3503 hook). Rooms 9 and 10 have no CUST resource, so no hook runs there
and room 10 gets no Crystal.

Exclusion: ChessRm starts after the room-4
wait below, about two seconds later than the Macintosh, whose hook adds it
before waiting.

### The spell's last sound and room 4's wait (2026-11-15)

From frame 51 `TransFuncJaffarMagic` checks sound 10055 (SoundIdOn
16:25b0): once it has ended and a5-0x245a is clear (cleared at 15:0918),
it starts 30500 with StartSndId 16:2396 and sets the flag (15:0ae4-0b0c).
The extractor reported SoundIdOn as playing and emitted the throne scene's
"restart when ended" operation, so the port replayed 10055 and never played
30500. The scene now has a `sound_after` operation. Room 4's enter hook
(9:1ab4-1b06) sets the room palettes, adds ChessRm, erases the screen and
calls WaitSndId(30500, 1) 16:270e; the scene's black last frame is held by
a closing `wait_sound` (30500, 1) tagged `code: 9`. In the scene's own
timeline 30500 starts at 8.6 s and ends at 11.5 s, after the scene's 9.5 s.

Evidence: static reading; `tests.test_final_spell` rejects the old
operation and checks the follow sound plays once and holds the end. A
re-import writes the corrected scene and its 30500 entry.

## Saves and the retry (2026-11-16)

A save keeps the rebirth snapshot only (`docs/SAVE_GAME.md`), never the
battle's live state. Two faults sat in that snapshot:

- The palace figure's `PathInfo` was not a saved record. A checkpoint first
  reached after the figure ran (the Prince can leave room 4 right of cell
  14 and come back) made every later save fail. It is saved now.
- The checkpoint copied `final_magic` with the world, so a retry kept the
  turns made before it. SetKidDefaults 2:5cf4 clears a5-0x5004 at 2:5e56 at
  every level start and rebirth; the checkpoint no longer keeps the magic.

`tests.test_save_records` rejects both, with the temple's genie and the
older cavern saves fixed in the same change.

## Native probe of the palace controller 9:16fe (2026-11-16)

`python -m tools.probe_final_path` runs the original 9:16fe with all of its
own CODE 9 callees (0a42, 0b28, 09ca, 0ba6, 0cac/0cec, the routes 0d28,
0ed2, 107c, 11fe, 136e, HoneIn 0dac, the kill 14c8, ShadowInRange 1954)
and CharDistance 4:49ee, over the original DATA tables. Supplied, each
recording its arguments: the record lookup 6:3642, SetSeq 6:0006, AddSound,
AddSong, the record swaps 4:4a46/4b02/4ac0/335a, DecLifePts 4:34f2, the
death method 4:3196, the Kid routines 6:11a0, 15ea, 1600, 1998, 1a84, 1c14,
0e8e, 1276 and AddCharX 4:2bae. The FRAM flag table is synthetic and shared
by both sides. 6,000 seeded cases (40% closing in on a Prince without a
sword, 15% at the spell's poses 281/282, 15% fleeing) compare the calls in
order, the record's +0x1c/+0x1e/+0x20 and a5-0x4f92: no differences after
one fix. Every route call kind is reached.

The fix: CharDistance returns 999 when the opponent's life is exactly 0
(4:49f0) or his facing word is 0x56 (4:4a0a). The port measured a dead
Prince's distance, so a drawn sword at 0 life could still be taken.

`tests.test_probe_final_path` runs 1,500 cases and rejects two wrong
models (CharDistance without the life gate; a range test that ignores the
floors' columns). Not covered: the Kid routines' own effects, AnimChar,
the caller 9:08e8 and its scheduling.

## Native probe of room 6's controller 9:1526 (2026-11-16)

`python -m tools.probe_final_copies` runs the original 9:1526 and
CharDistance 4:49ee over LEVL 2013, rewriting room 6's bank count per
case. Supplied: SetSeq 6:0006, AddSound 5:4d84 and AddCharX 4:2bae (X + 15
along the facing). The FRAM flags are synthetic and shared. The port reads
one Prince view for the opponent record and the saved Prince, so the probe
writes both from it; a frame in which they differ is excluded. 6,000 cases
(40% strike candidates) compare the calls, the facing word (the turn) and
the armed word: no differences. The shimmer (240), the strike (75, 15 px),
the sheathe (92), the laugh (197 with 261), the rise (49) and the turn are
all reached. `tests.test_probe_final_path` also rejects a distance measured
in the port's facing instead of the native word.

## Native probe of the turn rules (2026-11-16)

`python -m tools.probe_final_magic` runs three original routines over LEVL
2013 (environment 6, level 14):

- 4:250a, the turn flash (with the division helper 19:4bd0): every pose
  0-399 and count 0-15, 6,400 cases, against `turn_flash`.
- 4:2174, GenCtrl's per-frame count, now `final_magic.count_turn_frame`
  (moved out of `Final.controls`): 2,400 cases of pose, selected SEQS,
  count and native room. The palette restore 3:5f1c is supplied and
  recorded; it runs exactly where the port clears its flash outside
  standing. Where 4:2174 leaves the draw mode alone (pose 15) the port
  also clears its flash flag; that presentation is not compared.
- 4:1fb2, the standing turn, with DecLifePts 4:34f2 and IsShadowImbued
  4:2590 run natively, against `Final.standing_turn` on a minimal scene:
  1,152 cases of life 1-8, capacity 8/12, shadow, SEQS 5 or not, mode 13
  and count 0-8. Supplied and recorded: PoPSetPalette 3:508a, SetSeq,
  4:3196, LeaveBody 4:2206, AddSound and AddSong; the port's kill and
  body-leaving are recorded too. The room gate 6:116c and the port's
  same-frame order (`fresh_turn`) are outside the routine.

One difference was fixed: a fatal DecLifePts(1) on the eighth turn. The
original still runs 4:203e, whose low-life branch kills again and clears
the count; the port returned with the count at 8. Life plus pending damage
and capacity agree in every case, as do the palette (2000 + imbued at the
fourth turn), sound 288 and the shadow's SEQS 2, sound 260 and song 290.
`tests.test_final_magic` and `tests.test_probe_final_path` reject the old
return and a transform threshold of 3.
