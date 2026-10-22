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

**Bridge skeleton AI (implemented, cross-checked with dmucli/pop2-port):**
`roof_fight_room` means level 5, rooms 7/10/12, row not 0.
- `8:02ae` engage: facing right, bridge column >= 8; facing left, column < 2,
  or the Prince behind room 7's open gate (`8:0424`: gate trob phase 0/2,
  Prince bridge column < 2), or an armed Prince within 204 pixels to the
  right in column <= 6 with tension level 2 and amount >= 20. An engaging
  skeleton advances (EnGarde `4:0a30-0a7e`, GenFight, OpponentClose
  `4:1128-1154`) and does not back off from a gap (`4:0fb8`).
- `8:04a2` near its end (column < 3 facing right, > 3 facing left): away
  from it the skeleton neither retreats nor advances (EnGarde `4:0ae2`,
  `4:0b0c`, `4:0bfc`; InRange `4:04de`; OpponentClose `4:11d4`) and no
  run is resumed in pursuit.
- `8:033c` bridge guard (from the skeleton AutoCtrl `4:1672-169c`, which
  then skips the death-counter collapse): turns back right (+10) when the
  Prince hides behind the open gate; a right-facing runner brakes (SEQS 101,
  armed, alert 2) at column 9 or a shut gate; with the Prince behind the
  gate it runs (SEQS 102); past column 9 it turns (SEQS 60).
- Tension (SetTensionLevel `6:5022`): a skeleton's hit on the Prince in
  room 10 adds 5 at level 2 (CheckStab `6:5752-5772`); entering room 10
  after the break started clears it (`8:050e`).
- Note: the symbol file's "IsBrgGateOpen" at `8:033c` is the bridge guard;
  the actual gate test is `8:0458`.

**Still open [D, read but not implemented]:**
- `8:06d8`/RedrawBrgFloor `8:0878`: plank wobble (±1 Y).
- BridgeCheckBreak's room-7 side effect (`8:020a-0236`): an armed Prince
  outside the bridge in room 7, column <= 5, with the gate trob in phase 0
  or 2, triggers TriggerGateWithRevPlate(7, 13).
- Climbing up from a hang in room 10 with the sword out uses SEQS 236
  (`6:2bfd8` in dmucli's numbering).

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
- **Carpet (implemented, `pop2/carpet.py`):**
  - GenCtrl at frame 109 (`6:06b4` -> `6:099a`, check `6:09b4-09fe`): in
    level 5 room 3, a crouching Prince whose stored cell or the cell to its
    left is tile 18, outside selected sequences 17/20, sits down (`8:14ae`):
    JumpSeq 128, X 425 (+30 facing right; port 218/248), song 115 with the
    bars open, else 116.
  - SEQS 128: frame 296 four times, then frame 295 rising (-6 moves, 361
    pixels in all), -16 (next level), then SEQS 199 (frame 295 forever).
  - Sitting `8:13a8` (GenCtrl at frame 295, `6:0722`): the first call
    starts the carpet counter. Later, below Y 100 with the bars not open it
    crashes: Y 39, mode 10 (hidden), JumpSeq 129 (-> 199), sound 117. The
    next frames apply DecLifePts(100) and death method 9; IsDeadPos
    (`4:4814-4842`) counts a dead mode-10 Prince in room 3 as a dead pose.
  - Drawing: DrawCarpet `8:0e48` paints the unused carpet (SHAP 25312) at
    X 149, bottom 363; SetupCarpet `8:12b6` paints the ridden carpet at the
    Prince's X/Y plus a5-0x3104 offsets (-30 facing right), shape 25303 +
    a5-0x311a[frame]. Frame `8:11e4`: counter mod 9, then counter mod 6 + 3;
    after a crash min(counter + 8, 10) (SHAP 25318, the underside).
    DrawObjCarpet `8:11a4` counts each drawn frame.
  - **Palette:** CheckCarpetImg `8:0d30` is room 3's CUST enter hook (kind
    0, table a5-0x4c2e; the leave hook `8:0d5c` restores CTBL 3500 and 750).
    It loads CTBL 25303 at entries 32-46 and CTBL 3501 at 64-183, so the
    whole room uses 3501. Entries 16-31 hold the cavern Prince palette (Kid
    CTBL 25003) one bank up. An emulator capture of the room and the unused
    carpet matches pixel for pixel (mean difference below 1 outside the
    Prince). Not reproduced: the red fade of entries 45/46 (`8:10ba-119c`).
  - **Left column:** GetCells' neighbour cache (`5:0bbc-0be2`) marks the left
    room's last column 0xc000 in a CUST room (except rows 1-2 of CUST kind
    0x1f), so its pillar pieces are not drawn; the export harness now does
    the same (this removed the dark patch at the top left of room 3).
  - After the ride the port plays the cavern end song (32) and leaves the
    completed level on screen; level six is not available.

## Rules found in unmapped listing regions [D, not implemented]

The `.asm` listings leave some real code unmapped (e.g. CODE 5 `4198-4681`,
ATMGate). Disassembled with capstone:
- ATMGate `5:4396-43bc` (implemented): in level 5, room 7's gate undoes
  its waiting step (phases 0/1 at position >= 184), so once open it never
  starts closing by itself.
- AddGateSound `5:3828-388e` (implemented): a slam (sound 20) of room 7's
  gate adds BrgDoor (120) unless it plays or the Prince is in room 7 left of
  column 3.
- CutChar `6:4cd2-4d0c` (implemented): falling out of room 10's bottom does
  not cut to room 11; the Prince dies (DecLifePts(100)).
- `6:5752-5772`: in level 5 room 10, SetTensionLevel(2, 5).
- ATMExit `5:15a4-168d`: as the exit finishes opening (position 79) it calls
  ResetSoundItem(0) before sound 18, except in level 13 room 4.

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
