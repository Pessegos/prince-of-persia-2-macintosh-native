# Level 14: Inventory

Status: 2026-11-10. The passage through NIS 3, all 11 static rooms, entry
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
