# Level 13's Altar: the Sacred Flame and the Shadow

Status: 2026-11-05 (the shadow presses plates and rises from a sword death: [route audit](temple-route-audit.md)). Static reading of CODE 2/3/4/5/6/10 (two call sites sit in
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
restore, the burning poses 306-315, mode 12, pose 185 held. SetupOpponent
3:0852 runs SetupFlame 10:2fbe for poses 306-318 before the sword branch: the
pose's AFRM record (a5-0x521a type 4) gives SHAP 4092 + index and its
offsets, drawn at palette base 224 (CTBL 4077). The port draws it as that
attachment.
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
   10:2edc at the level start) with the imbued shadow: AddFCharX centres it on
   the image and MakeFlameFCharClipRect 10:2f1e aligns the bottoms. It is
   object type 14 (AddCharObj 3:0130). GetObjForePriority gives it 200 (a5-0x44e0)
   against the shadow's 127, and SortObjTable 3:3b62 puts the higher priority
   first, so DrawObjs draws it behind the shadow. Only the shadow has it, not
   the Kid.

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
The shadow's footsteps join the Kid's sounds.

## The riddle, and after the flame

Room 2's tapestry reads "He who would steal the sacred flame... must die". The
Prince must die to the birdhead in room 4 and press nothing. The bow and the
door below are the reward, and the user's memory of them is confirmed by the
code. The story guide's account agrees (popuw.com/story/pop2-13.html).

- Opponents bow. AutoCtrl 6:4f8a-5018: an armed opponent runs EnGarde 4:098c
  only while the Kid's mode (a5-0x509e) is not 13. Otherwise, with LEVL byte
  0x2196 set and selected SEQS other than 110, 4:07fe runs: AddCharX(distance -
  68) when GetBarrDistances gives under 68 with type other than 2, then JumpSeq(110).
  SEQS 110 is poses 228, 230-240, held. An unarmed opponent still draws by
  4:04fc, and is then armed and bows. `CombatEncounter._bow_guard`.
- Mode 13 lasts. AnimChar 4:2d7e (opcode -18) clears only the selected ID, so
  the climb's SEQS 235 keeps it. Sequences with opcode -21 still replace it, as
  in the original.
- Level 13's door. Tile 4:12 is a working plate that is drawn as nothing. Its
  kind is 5 and its foreground 0xc0b7, but its image word is 0. Every other
  plate in the level has 9 or 1. DrawTempUpPlate 10:0da8 and DrawTempDownPlate
  10:0c76 draw image 0 as back wall only (10:0004). The Prince cannot reach the
  cell. The shadow steps on it (2:6602) and opens exit 32:12, which stays open.
- The door is silent. TriggerObject 5:1f72-1f7e never adds song 297 on level 13.
  ATMExit 5:162c-1640 and 5:1656-166a skip cues 17 and 18 while the Kid is in
  room 4 of level 13, and with them ResetSoundItem(0). That is the call at
  5:1644, jump-table entry 500 (`$fc2(a5)`, the stub at 16:21fc, body 16:2200).
  It stops the current music and sound items just before cue 18, in every other
  room. The port does not do this at any exit door. These ATMExit bytes are in a
  gap in the listing.
- Native room 13 of level 13: 4:0902-091e lets a running opponent jump any gap
  until the Kid has mode 13. `_choose_guard_jump`.

From room 4, a real run: the birdhead kills the Prince, the shadow fetches the
flame, the door reaches 79, and the same birdhead then draws and kneels.

## Open

- What ends level 13 after the merge (CheckPlayNIS(13, 14): NIS 3), and the
  mode-13 Kid in level 14 (2001 at palette base 48, environment 6).
- A birdhead that draws with the Prince within 27 pixels behind it, next to
  the chasm, can turn into it: SEQS 60 flips the supporting foot across the
  anchor, and CheckFloor drops it. SwordCtrl 6:26a8 selects SEQS 60 with no floor
  test and CheckFloor 4:35ca has no exemption for it, so this reads as original
  behaviour. It has not been run on the original.
- A native probe of the rise, the merge and the whole flight. The decisions are
  checked: `tools/probe_temple_shadow_ctrl.py` runs AutoCtrl 10:2850 over poses,
  facing, column, mode, selected SEQS and the Kid (24,576 cases), and the bow
  6:4ffa, 4:07fe with a supplied distance (288 cases), 0 mismatches. Moving the
  shadow's column 8 test to 9 is caught.

## NIS 3: the flight to the tower

Leaving level 13, `CheckPlayNIS(13, 14)` dispatches (15:07c8) NIS 3 at
15:7226 (unmapped in the listing; disassemble 15:7226 onwards). It loads
TowerNIS.rsrc and uses Horse.rsrc, Prince.rsrc, Kid.rsrc and Final.rsrc
(SHAP 4000/4001, CTBL 3500) through TransFunc9-11 (15:755a, 759e, 75e2).

- The importer (`tools/extract_intro.py` `extract_tower`) writes
  `tower.json`. Callback shape ids are searched in TowerNIS, Horse, then the
  residents. The fade takes the palette that 15:26fc stores only when the
  flags word has bit 0 set.
- PlayTheAnimation without flag 8 but with a fill colour repaints the
  animation bounds every frame (16:13be-13d2). The port emits a `fill`
  operation per frame. Only this scene uses that path.
- `Temple.finish_exit` plays the scene and then marks level 13 complete.
  Level 14 (the Final environment, CODE 9) is not ported.
- Known gap: there are small artifacts at the right edge (x ≈ 507) of the
  flight shots.
