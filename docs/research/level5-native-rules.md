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

The state lives in a5-0x3130 (0 intact, 1 triggered, 3 collapsing) and the
counter a5-0x3132 [D].

**BridgeCheckBreak `8:0004-016c` [D].**
- It resolves the bridge columns of the Prince and of the opponent
  (BridgeGetCharCol `8:0188`, `8:01e2`/`0252`).
- While both stand on it within three columns of each other, the counter
  rises once per call. At 60, with the Prince in columns 4-6, the opponent in
  columns 5-6 and the Prince's selected sequence not 85, the state becomes
  1. The two must therefore fight on the middle of the bridge long enough.
- Apart, the counter falls by one; with no character on the bridge it falls
  by two.
- From state 3, pieces are triggered (`8:0c1a`) from column 7 downwards, with
  sound 123 and song 121.

**Other bridge routines [?]:** MarkBrgFloorsForChars `8:050e`,
MarkBridgeForCol `8:05cc`, OffsetBrgFloorY/RestoreBrgFloorY
`8:0772`/`081e`, RedrawBrgFloor `8:0878`, TriggerBrgFloor `8:091c`,
ATMBrgFloor `8:0976`, DrawObjBrgFloor `8:0b44`, TriggerBrgFloorMob `8:0ba2`
and IsBrgGateOpen `8:033c`.

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
