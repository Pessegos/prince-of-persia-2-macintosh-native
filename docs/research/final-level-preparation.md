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
