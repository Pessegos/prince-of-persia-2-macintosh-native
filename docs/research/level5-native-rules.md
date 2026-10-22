# Level Five: Native Rule Index

Research note, 2026-10-22, `claude/ai-research`. This is a plan for enabling
level five (LEVL 2004, cavern environment 3, skeleton opponents), not an
implementation. Addresses are original CODE `segment:offset`; one-based room
numbers are native.

Labels: **[D]** direct reading; **[I]** inference; **[?]** not yet read.

## What already works

- **Entry:** SetKidDefaults `2:5e34` selects ordinary sequence 5 [D].
- **Scenery:** `tools/extract_caverns.py` exports `caverns_level5.json`,
  including room 10's rope bridge and room 3's custom chamber (CUST
  4050/4225). Pass-11 custom pieces are not drawn
  (`docs/LEVEL4_RECOVERY.md`).

## Level-specific tiles

- **Room 10, row 1, columns 1-8:** tile 44, the bridge floor.
- **Room 3:** tile 18 at cell 23 and tile 27 at cell 6 [?].
- **Customized rooms:** 3 and 10 (foreground bits 0xc000).

## The bridge (CODE 8 "Caverns")

Implemented; see `docs/LEVEL4_RECOVERY.md` ("The rope bridge breaks") for
BridgeCheckBreak `8:002e-016c`, the plank mobs (`8:0c1a`, TriggerBrgFloorMob
`8:0ba2`, ATMBrgFloor `8:0976`, DrawObjBrgFloor `8:0b44`) and the native
check of the redraw at each collapse stage.

**Still open [D, read but not implemented]:**
- `8:06d8`/RedrawBrgFloor `8:0878`: the planks under marked columns
  (a5-0x3134, MarkBridgeForCol `8:05cc`) wobble between CUST records 3-5
  (Rnd(3)), adding ±1 to a character's Y (`8:0682-06be`).
- `8:02ae`: opponent predicate for EnGarde/GenFight/DoKidEngarde; facing
  right it is true from bridge column 8; facing left below column 2, at the
  room-7 gate (`8:0424`/`8:0458`, cell 13 state 0 or 2), or when an armed
  character within 204 pixels to its right stands in column <= 6 while
  tension a5-0x36a2 is 2 and a5-0x36a0 >= 20.
- `8:04a2`: InRange/EnGarde predicate on the bridge column (< 3 facing
  right, > 3 facing left).
- IsBrgGateOpen `8:033c`: the removal of a falling (mode 4) opponent is
  implemented for one leaving rooms 7/10/12 downward; the other branches
  (sequence 102/216 handling, the room-7 gate `8:2c38`, DoStrike) are not.
- BridgeCheckBreak's room-7 side effect (`8:020a-0236`): an armed Prince
  outside the bridge, in room 7 column <= 5 with the cell-13 gate state 0
  or 2, triggers TriggerGateWithRevPlate(7, 13).

**Rules elsewhere that depend on the bridge state [D]:**
- Prince turn `6:26d2` and voluntary turn `6:2322-2330`: no turn in level 5,
  room 10, while a5-0x3130 > 0.
- AnimChar `-1` link `4:2e64-2ea0`: in level 5, rooms 10/7/12, a char in row
  != 0 linking to 57 from a selected sequence other than 60, in column 9,
  links to 86 instead.
- OpponentClose `4:1672-169c`: in level 5, rooms 10/7/12, with the char's row
  word nonzero, wake uses S08_033C (IsBrgGateOpen) instead of the proximity
  test.
- GenFight `4:102c-1054` and similar EnGarde sites: level 5, rooms 10/7/12,
  skip the run-after-the-Prince start.

## The finale: carpet and ceiling bars (room 3) [D, partly read]

Room 3 is customized (CUST 4050). Its tile 27 at cell 6 is the ceiling's
cave bars and tile 18 at cell 23 belongs to the flying carpet:
- **Bars (implemented):** RedrawCell `3:1d24-1d2e` adds back pass 11 for a
  loaded CUST room; the export now runs it, which only adds room 3's bars
  (levels 3 and 4 stay byte-identical, room 10 unchanged). DrawCaveBars
  `8:15c0` draws CUST record (foreground & 7) + 1 (SHAP 4051, 4052, 4053,
  4064: closed to open); native redraws of phases 1-3 only change that
  SHAP, so the bars are a pressure-drawing record. Room 3's plate (cell 8,
  link 17) triggers them: TriggerCaveBars `8:1672-16d0` opens fully closed
  bars and closes fully open ones on a fresh press; `8:1508-1576` moves one
  phase per update with sound 282 (opening from 0) or 284 (closing from 3).
  IsCaveBarsOpen `8:157a` tests phase >= 3.
- **Carpet:** SetupCarpet `8:12b6` (from Opponent1 `3:084c`), Sitting
  `8:13a8` (from GenCtrl `6:072a`), DrawCarpet/SaveUnderCarpet/
  DrawObjCarpet/GetCarpetShape (`8:0e48-1264`) with palette cycling
  (ComputeBloodRGB `8:0df6`). Sitting: Prince frame 295 starts the carpet
  and triggers cell (3, 23); while rising, below Y 100 with the bars still
  closed the Prince gets DecLifePts(100) and death method 9 (`8:1486-1498`);
  with them open the carpet stops at Y 39 (mode 10, JumpSeq 129, sound 117).
  `8:14ae-14ec` selects song 115 or 116 by IsCaveBarsOpen.

GenCtrl `6:099a-09fe`: in level 5 room 3, a Prince whose cell or the
cell to its left is tile 18, outside selected sequences 17/20, starts the
carpet (`8:14ae`: JumpSeq 128, X 425, +30 facing right, song 115 if the
bars are open, else 116). The carpet ride and level exit are the next
bounded task.

## Other level-five checks still to read [?]

| Site | Function |
| --- | --- |
| `2:6e38` | CheckAlert |
| `3:0262` | AddMid |
| `3:0832` | Opponent1 |
| `3:30b0` | DrawMidItem |
| `3:4b8a` | DrawOppMeter |
| `4:04be` | InRange (opponent run controller) |
| `4:0a3a`, `4:0aec`, `4:0bdc` | EnGarde |
| `4:1036`, `4:106c`, `4:10cc` | GenFight |
| `4:1128`, `4:11b8` | OpponentClose |
| `4:31be` | SetKidDeathMethod |
| `4:350e`, `4:3830` | DecLifePts |
| `4:4814` | IsDeadPos |
| `4:4c54` | LoadShad |
| `5:2688` | MakeSpace |
| `5:3846` | AddGateSound |
| `5:539c` | SpecialMusic |
| `6:09b4` | GenCtrl |
| `6:19a0` | DoJumpHigh |
| `6:22be`, `6:2318` | DoKidEngarde |
| `6:26c0` | DoStrike |
| `6:451a` | CutAllOpponents |
| `6:4cd6`, `6:4d32` | CutChar |
| `8:2d78` | TriggerGateWithRevPlate |
| `8:3b9a` | CaveGetTorchFrame |

## Suggested order

1. Make level five loadable (F3, entry, importer and launcher behind a
   reimport, saves `1..5`) and route the level-four exit into it.
2. The bridge: the static floor exists; then break state, piece fall
   animation and the characters falling through it.
3. Work through the remaining rows of the table, each with a native probe or
   direct reading and a regression.
