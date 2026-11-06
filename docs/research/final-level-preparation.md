# Level 14: Inventory

Status: 2026-11-06. An inventory for planning, not a recovery. Names come from the
preserved symbols. Only the function graph of CODE 9 was read, not its bodies.
Nothing here is ported: `Temple.finish_exit` plays NIS 3 and marks level 13 complete.

## The level

`LEVL` 2013: level 14, environment 6, 11 rooms, 18,890 bytes. The only tiles seen
in the rooms' lower rows are 0, 1, 10, 20 and 40. Rooms 7 and 8 take the wall
rules already noted in `opponent-barriers.md`, and rooms 1 and 2 are named in
`gate-barrier-distances.md`. `GetUndefineCellId`'s environment 6 branch is already
ported.

`Final.rsrc` holds 66 SHAP, 9 CUST (4000-4250), 4 CTBL (3500-3503), PIEC and
SHPL 3500. `tools/extract_assets.py` copies it, for NIS 3 alone so far. No
exporter draws its rooms: level 14 needs an `extract_caverns`-style export first.

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

## A bounded first step

1. Export the rooms and show them through a development warp, with the Prince's
   palette 2001. This needs a reimport and no game rules.
2. Read FinlCheckGenOpp and FinlGenerateOpp and spawn Jaffar's copies.
3. Only then the path (9:09ca-14b6), which is the largest part.

Scenery can go in any order. The crystals and gargoyles have Trigger routines, so
plates or events reach them.
