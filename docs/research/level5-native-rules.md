# Level Five: Native Rule Index

Research note, 2026-10-22, audited 2026-10-23, `claude/ai-research`.
Level five (LEVL 2004, cavern environment 3, skeleton opponents) is playable
from the level-four exit to the carpet ride into level six. Addresses are
original CODE `segment:offset`; one-based room numbers are native. This is a
rule index, not a claim of full native equivalence.

Labels: **[D]** direct reading; **[I]** inference; **[?]** not yet read.

## Audit checklist (2026-10-23)

Every site in the original CODE that compares the level number (LEVL
`+0x218a`) with 5 was listed by scanning the listings (39 sites, plus the
unmapped-region sites below). Each is accounted for:

| Site | Function | Status |
| --- | --- | --- |
| `2:6e38` | level start (S02_697E) | clears bridge state (S08_3BCE: a5-0x3130, 16 bytes at -0x312e); the port creates a fresh bridge per level load |
| `3:0262`, `3:30b0` | AddMid / DrawMidItem | room 10 layer-4 items take CUST shapes (falling planks); covered by the plank drawing, checked against native redraws |
| `3:0832` | Opponent1 | Prince frame 295 in room 3 draws the ridden carpet (SetupCarpet); implemented |
| `3:4b8a` | DrawOppMeter | **fixed 2026-10-23**: no meter for a skeleton in the bridge rooms (row != 0) |
| `4:04be` | InRange | implemented (no advance away from the bridge end) |
| `4:0a3a`, `4:0aec`, `4:0bdc` | EnGarde | implemented (engage/hold) |
| `4:1036`, `4:106c`, `4:10cc` | GenFight | implemented |
| `4:1128`, `4:11b8` | OpponentClose | implemented |
| `4:1676` | skeleton AutoCtrl | implemented (bridge guard 8:033c) |
| `4:2e68` | AnimChar -1 link | read; no reachable case (only SEQS 60 links to 57) |
| `4:31be` | SetKidDeathMethod | implemented (tension level 3) |
| `4:350e` | DecLifePts | implemented (bridge skeleton immune) |
| `4:3830` | Catch | implemented (+25 reach at tension >= 40) |
| `4:4814` | IsDeadPos | implemented (mode-10 carpet crash counts as dead) |
| `4:4c54` | StartFall | implemented (SEQS 198) |
| `5:2688` | MakeSpace | read: in room 3 an emptied cell gets foreground 0xc000. Only Sitting (8:13e8) uses it there, emptying the carpet's cell 23; not modelled because the ride ends the level or kills the Prince |
| `5:3846` | AddGateSound | implemented (BrgDoor 120) |
| `5:539c` | SpecialMusic | implemented (BrgFight 119 in rooms 7/10/12) |
| `6:09b4` | GenCtrl | implemented (carpet sit) |
| `6:19a0` | DoClimbUp | implemented (SEQS 236, sword lost) |
| `6:22be` | SwordCtrl turn | **fixed 2026-10-23**: an engaging bridge skeleton (8:02ae) does not turn to a Prince more than 15 pixels behind it; otherwise SEQS 60 |
| `6:2318`, `6:26c0` | SwordCtrl / DoTurn | implemented (no Prince turn in room 10 while breaking). DoTurn's room check (6:26b8) is only reached for char types 0/1, so opponents still turn |
| `6:451a` | CutAllOpponents | implemented |
| `6:4cd6`, `6:4d32` | CutChar | implemented (no cut below room 10; chasm to room 0) |
| `8:0190`, `8:01ae` | BridgeGetCharCol | implemented (rooms 7/12 continue room 10's columns) |
| `8:06e0` | plank wobble | read, **not implemented** (see below) |
| `8:0a5e`, `8:0baa` | ATMBrgFloor / TriggerBrgFloorMob | implemented |
| `8:2d78` | TriggerGateWithRevPlate | implemented |
| `8:3b9a` | Caverns frame hook | implemented (BridgeCheckBreak in rooms 10/7/12) |

Other level-dependent tables reviewed for level five: IsTimeForNIS
(`2:00e8`) has no level-five case; CheckPlayNIS selects scene 1 (NISCarpet,
`15:1630` through the NIS 1-6 dispatcher `15:07c8`) when leaving level five.

**Tension persistence (fixed 2026-10-23):** SetTensionLevel's globals
(a5-0x36a2/-0x36a0) are written only by `6:5022` and a debug dialog
(`2:4a5a`). RestartGame (`2:5b66`) reloads the level (LoadLevelMinimum
`3:585a`) and clears only the bridge (`2:6e38`), so tension built up by
fatal falls survives a restart; the next-level opcode -16 (`4:2f5a`) resets
it, except when leaving level six. The port now carries it across restarts.
The heads of levels six/seven also use it (`7:04ea`, `7:092a`), so it will
need to move out of the bridge state for those levels.

**Approximations and gaps that remain:**
- Plank wobble (8:06d8, below) is not drawn and does not move characters by
  one pixel.
- The carpet's red fade of palette entries 45/46 (`8:10ba-119c`).
- Cutscene 1 (NISCarpet) between levels five and six is not shown; the
  port goes straight to level six.
- Unmeasured: the bridge-fight tempo against the original over a whole
  fight (only the individual rules were checked).

No blocking progression defect is known: the route from the level-four exit
through the bridge, room 7's gate and the carpet into level six works, and
the failure paths (chasm fall, carpet crash, saves with bridge state) are
covered by tests in `tests/test_bridge.py` and `tests/test_level5.py`.
Death and restart use the shared rebirth path; no level-five-specific
restart test exists.

## Entry and scenery

- **Entry:** SetKidDefaults `2:5e34` selects ordinary sequence 5 [D].
- **Scenery:** `tools/extract_caverns.py` exports `caverns_level5.json`,
  including room 10's rope bridge and room 3's custom chamber (CUST
  4050/4225), with room 3's bars (pass 11).

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
- DecLifePts `4:34f2-352e`: a skeleton in the bridge rooms (row not 0) takes
  no damage; only the collapse defeats it (implemented).
- CutAllOpponents `6:4510-4540`: bridge-room opponents always follow the
  Prince across a cut (implemented).
- Note: the symbol file's "IsBrgGateOpen" at `8:033c` is the bridge guard;
  the actual gate test is `8:0458`.

**Still open [D, read but not implemented]:**
- `8:06d8`/RedrawBrgFloor `8:0878`: plank wobble. Each bridge cell is a trob
  (TriggerBrgFloor `8:091c` at room entry). While a character's column ±1
  is marked (8:0534/MarkBridgeForCol `8:05cc`; both on the bridge mark all),
  Rnd(3) >= 2 sets the foreground nibble to 1 or 2 for one frame; the cell
  is redrawn with CUST record 3 + nibble (SHAP 4226-4228, bottom +0/+1/+2)
  and a character's Y on a floor pose moves -1/+1 (`8:068c-06be`). Not
  implemented: it needs per-cell redraws of the pre-rendered room.
- (Implemented) BridgeCheckBreak's room-7 side effect (`8:020a-0236`): a
  Prince who still has his sword (a5-0x503c != -1) outside the bridge in
  room 7, column <= 5, with the gate trob in phase 0 or 2, triggers
  TriggerGateWithRevPlate(7, 13).
- (Implemented) DoClimbUp `6:19aa-19c4`: the first climb out of a hang in
  room 10 uses SEQS 236 (poses 319-322 let the sword fall, sound 14) and sets
  a5-0x503c to -1, so Ctrl draws nothing (GenCtrl `6:0c70`). A sword hit
  writes 1 again (`6:53f8-5406`) and rebirth restores 0 (`2:5e66`, the level
  sword type a5-0x500a is still 1). Level 6 starts without a sword
  (`3:6202-6216`).
- (Implemented) StartFall `4:4c4a-4ca4`: in room 10 a Prince holding the
  direction behind him turns back with SEQS 198 (bypassing the pose table).
- (Implemented) Tension level 3: SetKidDeathMethod(3) `4:31b4-31d6` while
  room 10 is on screen adds 5; from 20 an armed right-facing fall uses SEQS
  198, from 40 a left-facing catch reaches 25 pixels further
  (`4:382c-3880`).
- (Implemented) CutChar `6:4d5a-4d66` moves the Prince to room 0: no floor
  of room 11 can stop his fall below the chasm.
- (Implemented) TriggerGateWithRevPlate `8:2d66-2d96`: a bridge skeleton
  (row != 0) cannot open a fully shut reversible gate.

**Rules elsewhere that depend on the bridge state [D]:**
- Prince turn `6:26d2` and voluntary turn `6:2322-2330`: no turn in level 5,
  room 10, while a5-0x3130 > 0.
- AnimChar `-1` link `4:2e64-2ea0`: in level 5, rooms 10/7/12, a char in row
  != 0 linking to 57 from a selected sequence other than 60, in column 9,
  links to 86 instead. Not implemented: only SEQS 60 links to 57, always
  selected by JumpSeq, so no reachable case was found.
- OpponentClose `4:1672-169c`: in level 5, rooms 10/7/12, with the char's row
  word nonzero, wake uses S08_033C (IsBrgGateOpen) instead of the proximity
  test.
- (Implemented) GenFight `4:102c-1054` and similar EnGarde sites: level 5,
  rooms 10/7/12, skip the run-after-the-Prince start.

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
  - After the ride the port plays the cavern end song (32) and loads level
    six (cutscene 1 is not shown).

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
