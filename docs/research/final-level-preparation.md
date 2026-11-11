# Level 14: Inventory

Status: 2026-11-11. The level-13 completion path through NIS 3, all 11 static rooms, entry
placement and saving are integrated. The final battle and ending are not.
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

- At count 0, column 1 is chosen if the Prince is on row 2; otherwise column
  2. At count 1, selected `SEQS 238` blocks another birth. Otherwise column
  2 is chosen when the first opponent is on row 1, column 1 otherwise. A
  match between that column and the Prince's row blocks birth. Next,
  `Rnd(20) == 0` admits it: `Rnd` is inclusive, so this is **1/21**.
  Count 2 stops further births.
- The constructor 9:03c8 increments the room-3 count and calls
  `GetOppInfoIdx(3, old_count)` 6:3642. `FirstInRow` 4:322a plus the selected
  column writes cell 21/22, 41/42, 61/62 or 81/82; `Rnd(1)` independently
  adds 4 to the base row (2 for column 2, 4 for column 1). Those larger
  values are positions for Jaffar's later vertical path, not regular cells
  to clamp to 0..29. The original X table at a5-0x4b88 gives native X 258
  or 309; the constructor faces left, sets skill 5 and life 3 or 4 from a
  second independent `Rnd(1)`, then starts `SEQS 238`. When the first
  palette-bank slot is empty, 9:042a-043e and 6:40f6 assign variant 3;
  Guard.rsrc CTBL 752 gives Jaffar's red and white outfit. Its frame 233
  resolves to SHAP 782. The port stores these as marked
  type-2 room-3 opponents, keeps their path cell in the room record, starts
  that sequence and persists them through room visits and saves.
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

The path controller beginning at 9:09ca, later copy movement between rooms,
combat, finishing logic, moving scenery and ending remain open. The next
bounded task is to recover Jaffar's position transitions and the mapping of
these extended record cells to visible tower rooms. Until then, copies can
appear in room 3's visible row 2; path rows 4/6/8 are retained but are not
drawn or run through ordinary guard AI.

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
four actor-type-2 records, native room 8 has none, room 10 has one, and room
11 has one. In the player's room-6 screenshot the four opponents look like
copies of the Prince (five figures including the player). The port still
decodes those records with `Guard.rsrc`, producing blue-robed guards; this is
a confirmed visual mismatch. Resource selection, palettes and animation for
these actors need a separate CODE 3/CODE 9 trace before changing the live
combat renderer. Different LEVL tile and opponent records show that the
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

An initial actor-art audit narrows that remaining problem. The port restores
the four room-6 records as actor type 2 with `SEQS 77`/pose 166 and draws the
`Guard.rsrc` frame, yielding blue robes. Decoding the preserved `Kid.rsrc`
`FRAM` 25001 pose 166 with environment-6 `CTBL` 25006 yields the red shirt,
white trousers and blue turban seen on the standing copies in the Macintosh
screenshot. This identifies candidate source artwork, but is not yet a safe
live-renderer substitution: original `LoadFrame` 4:2a8e's actor-type-2
jump-table entry goes to 4:2b0e, which maps pose 166 to opponent frame index
17 (`pose - 149`). The pointer at a5-0x3472 and any final-level override of
the image bank must be traced through room entry and draw setup. A direct use
of Kid frame 166 would match a still image without establishing the
Macintosh's animation and frame selection.

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

Focused shared-desktop checks: 185 tests passed across temple arrival,
developer map/menu, level ending, music transition and installation. Dependency,
Ruff, recovery catalogue and diff checks passed. Full discovery was not repeated
because the prior shared-desktop run grew to about 15 GB without finishing.
