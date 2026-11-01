# Level 13's Altar: the Sacred Flame and the Shadow

Status: 2026-11-01. Static reading of CODE 2/3/4/5/6/10 (two call sites sit in
unmapped regions and were disassembled from the CODE bytes). The burn, the
flare and the shadow are ported (`pop2/temple_altar.py`,
`pop2/temple_shadow.py`, `pop2/caverns.py`, the Temple environment,
`tests/test_temple_altar.py`). No native probe yet. Native rooms are
one-based.

## Where it runs

- The environment hook table a5-0x46f8 (FrameAdv 2:7124, after the Kid and
  the opponents) holds 10:27ba for environment 2. It calls 10:2a62 when the
  Kid's room a5-0x4fc2 is 4 and the level is 13.
- AutoCtrl 6:4e90 dispatches on actor type through a jump table at
  6:4ed0 (unmapped in the listing): type 1 (the shadow) goes to 6:4f44,
  which calls 10:2850 in native room 4 of level 13 only; elsewhere a type-1
  actor gets no AutoCtrl.
- AnimTrob 5:0cd6 dispatches on the TROB's tile kind through 5:0d0e
  (unmapped); tile 43, the flame cell (room 4, cell 11, foreground 0), runs
  10:2cc2. AnimTrob runs before the Kid (2:6230), so a flare written by the
  hook is first drawn one frame later with a5-0x2b7c[5].

## The flame (10:2cc2, DrawTempSacredFlame 10:2d5a)

The counter is the flame cell's foreground word (a5-0x4818 inside AnimTrob).
Without bit 0x80 it runs 0..11, drawn as CUST 4075 record counter + 2. With
bit 0x80 (a flare) it counts its low four bits down; at 0x80 it returns to 0
(record 2). DrawTempSacredFlame draws a5-0x2b7c[counter & 0x7f] =
14, 14, 15, 16, 16, 14 for indices 0-5, with pass 1 (the ordinary frames use
pass 11; the port draws both in one layer). Two places write the flare 0x85
into level + 0x914 (room 4, cell 11): the burn (10:2ab4) and the shadow's
pose 154 (10:29f8).

## The Kid at the altar (10:2a62)

Read from the saved Kid (a5-0x50d2): row 1 and selected SEQS other than 230:

| Native X | Effect |
| --- | --- |
| <= 347 | JumpSeq(230) (no AnimChar), X = 335, DecLifePts(100), AddSound(249), SetKidDeathMethod(16) (AddKidDeathSong: a5-0x4396[16] = 250), flare 0x85 |
| <= 375 | AddSong(253) unless PrinceSndOn(253) |
| otherwise | the shadow (next section) when pose 185, mode (+0x34) != 12 and a5-0x4fd4 = 1 |

SEQS 230: mode 0, opcode -24 (palette flash) to colour 225, poses 50/51,
restore, the burning poses 306-315 (SetupOpponent 3:0852/3:0a76 draw
SetupFlame 10:2fbe over poses 306-318, not ported), mode 12, pose 185 held.
Mode 12 excludes the burned Kid from the shadow.

Opcode -24 (AnimChar 4:2fb0): flag 1 fills palette entries 1-254 with the
colour of an index (SetPaletteToColorIdx 3:4fbc; 225 becomes 209 in
environment 6), flag 0 restores the game palette (3:4f30). In level 13 index
225 is white (Kid CTBL 4077 at 224-239). The port's frames hold colours: it
keeps pure black and white pixels and fills the rest.

## The shadow

Level 13 room 4 row 1: floor at columns 0-2 (the flame at column 1, tile 43),
a gap at columns 3-5 (room 4 is a chasm room, 6:4cd2), floor at 6-9 and one
birdhead (cell 16, X 560). The Kid cannot reach the flame alive: X <= 347
burns him for good.

1. Death message: KeepTime 2:6838-685e sets a5-0x4fd4 = 1 when the death
   message (a5-0x4fcc = 600, set by 4:3c96) is shown with the Kid in room 4
   of level 13. While a5-0x4fd4 = -1 the message timer stops (2:682c).
2. Rise (10:2af0-2b2e -> 2b32): a dead Kid at pose 185, X > 375, row 1, mode
   != 12: the working Kid becomes a new opponent record in room 4 (count
   +1, 6:3642): type 1 (`+0x12 = 1` in the record), the Kid's cell, X and
   facing; actor kind 1, life 1, ALIVE -1, draw mode +0x36 = 0x30,
   SetCharFloor, Y - 1, JumpSeq(231) (rise), AnimChar, AddSong(254).
   a5-0x4fd4 = -1.
3. AutoCtrl 10:2850 (working actor = the shadow; mode = +0x34):
   - pose 15, facing left: column >= 6: mode 13 -> SEQS 71 (lie down),
     else column >= 8 -> SEQS 1 (run), else DoStepFwd(0), and SEQS 44 ->
     SEQS 3 (standing jump). Column < 6: not mode 13 and not SEQS 232 ->
     SEQS 232 (take the flame), else SEQS 5 (turn) + AddSong(251).
   - pose 15, facing right: not mode 13 -> SEQS 5. Mode 13, column >= 6:
     d = Kid X - (X - 10), plus a5-0x4b94[facing] * 12 when both face the
     same way; d > 4 -> DoStepFwd(d), else AddCharX(d) and SEQS 71 (same
     facing) or 5. Column < 6: DoStepFwd(0), and SEQS 44 -> SEQS 247 (a
     longer standing jump).
   - running poses 1-14/49-56 at column >= 6: DoRunJump(4).
   - poses 103-106: a5-0x3480 = -1, 4:37ca. Pose 91: DoJumpHang, else
     6:1998; mode 13 lifts Y by 2.
   - pose 154: flare 0x85. Pose 153 in mode 13: PoPSetPalette(4077, 48).
   - pose 44: SEQS 13, AddCharX(-12).
   - pose 185 in mode 13: merge (10:27d8).
   SEQS 232 (poses 235, 153, 154, flash 225, mode 13, 153, 15) gives the
   shadow mode 13 at the flame. SEQS 71 -> 213 lays it down to pose 185.
4. Merge 10:27d8: the Kid is reloaded, JumpSeq(231), ALIVE -1, full life,
   the death message cleared (a5-0x4fcc/-4fca = 0), DrawKidMeter, Kid mode
   13, unarmed; LoadShad, 4:48f8 (the shadow removed), AddSong(252).
5. IsShadowImbued 4:2590 tests the working actor: mode 13 (or environment
   6 with life > 2). SetupOpponent (3:0852 in environment 6, 3:0a4c for any
   kind-1 actor) calls SetupShadowFlame 4:2630, which draws SHAP 4102 +
   (a5-0x349a % 9) with palette base 224 (a5-0x2b70; CTBL 4077, loaded by
   10:2edc at the level start) over the imbued shadow: AddFCharX centres it
   on the image and MakeFlameFCharClipRect 10:2f1e aligns the bottoms. The
   flame burns over the shadow on its way back, not over the Kid.

Colours: AddCharObj copies the draw mode 0x30 (+0x36) into the object; it is
the palette base 48. 10:2edc loads CTBL 2000 there (2001 when the Kid's mode
is 13), 4:1fea and 2:4b58 likewise, and pose 153 in mode 13 replaces it with
CTBL 4077 (PoPSetPalette 3:508a). Kid.rsrc holds CTBL 2000 (dark blues),
2001 and 4077; the Kid images use indices 1-16, so the port decodes the
shadow's images with those tables.

## In the port

The Temple environment runs the shadow before the altar hook: AutoCtrl
(`auto_ctrl`), AnimChar, then the Kid's terrain rules with the Kid's frames
(`RooftopPhysics`, no room cuts, hang/climb sequences protected).
DoStepFwd uses `step_boundary`/`plan_cautious_step` (arg 0) or
`StepBoundary(d)`; DoRunJump(4) uses `run_jump_offset` with the Prince's
reserve 48. The catch at poses 103-106 uses `catch_ledge`/`align_catch`
(JumpSeq 15 and its first pose); at pose 91 the AnimChar preview (DoJumpHang)
decides the climb (SEQS 10; 6:1998 skips the gate test for kind 1).

From a death at native X 600 the port's shadow steps to the chasm edge,
takes the standing jump (SEQS 3, about 146 pixels for a 153-pixel gap),
falls short, catches the altar's ledge, swings (SEQS 210) and climbs, takes
the flame (flare, white flash, CTBL 4077), turns (song 251), jumps back with
SEQS 247 (about 197 pixels), walks to the body, turns, lies down and merges
(about 130 frames). The state is saved: `CavernState.altar` (a5-0x4fd4) and
`CavernState.shadow`; every level start clears them (2:5bfe).

Exclusions: the facing-right climb's 4:5cbc/5:19f8 calls (10:29d2), the
-3480/-3484 inputs DoStepFwd sets, and 10:2036's failed climb (SEQS 73).
The shadow's footsteps join the Kid's sounds. The port's SEQS -18 also
clears the mode (native 4:2d7e clears only +0x28), so a later climb by the
revived Kid (SEQS 235) leaves mode 13.

## Open

- SetupFlame 10:2fbe over the burning poses 306-318.
- What ends level 13 after the merge (CheckPlayNIS(13, 14): NIS 3), and the
  mode-13 Kid in level 14 (2001 at palette base 48, environment 6).
- A native probe of AutoCtrl 10:2850 and the rise/merge.
