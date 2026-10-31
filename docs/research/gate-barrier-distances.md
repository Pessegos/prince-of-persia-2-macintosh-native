# Gate barriers in the step distance (2026-10-31)

GetBarrDistances 4:5eae is the Kid's step/draw/turn distance. It classifies
the supporting cell and the one ahead with GetBarrCode 4:52bc and measures a
barrier with GetBarrDistFromFace 4:6562. For a gate (tile 4), 6562 first calls
the gate collision 4:5b0e and returns -1 (no barrier) unless it blocks.
4:5b0e has no environment table except the desert's:

- **Desert** (LEVL 0x2186 = 1): blocks while the five low foreground bits
  are below 19, whatever the body. 18:067c writes the exit's phase there
  (1-20, one step per frame); TriggerDsrtExit 18:07b6 reads it back.
- **Elsewhere**: actor type 1 and sequence 68 pass; otherwise it compares the
  clipped body height (+46 for type 7, +33 for type 8) with the gate position.

GetBarrCode 4:531c then makes a blocking gate type 5 in the caverns (3),
type 8 at the throne (level eight, Kid room 9) and type 1 elsewhere.
A barrier 51 or more away reports the ordinary clear 42 with reason 2
(4:5fe8 -> 5f78), not its own distance.

## Port before this change

- `step_boundary` ignored the desert exit (no barrier at any phase), so a
  Shift step toward the closed exit took a full step and DrawSword reserved
  nothing.
- It reported a barrier 51 or more away with its own distance and type 2
  (for example 54 or 76) instead of 42, which lengthened a step by one SEQS
  and changed DrawSword's reservation (min(0, d - 56)).
- The throne gate was a barrier whatever its state; 6562 asks 4:5b0e first.
- CheckCollide 4:5688 asks 4:5b0e too, but the port's desert collision used
  `exit_open` (phase 20): the body was held one frame longer than the
  original.
- The runtime desert tile carried a drawing value (0 closed, 104 open)
  instead of the phase. DoRunJump's gate test 6:5eca compares the low byte
  with 104 in every environment, so the open exit stopped obstructing a
  running jump. Natively the phase never reaches 104: the exit always
  obstructs a running jump, open or not (the Prince's late jump is refused,
  an early one is aligned before it). The same holds for the climb test
  (low byte >> 2 < 12 selects the failed climb 73).

## Port now

`LevelMap.gate_collides` is 4:5b0e; `step_boundary`, `combat_turn_offset`
and the desert collision in `wall_correction` all use it. The desert tile's
low five bits are `DesertState.gate`. A barrier at 51 or more returns
`StepBoundary(42, 2)`.

## Native execution

`tools/probe_gate_barriers.py` runs 4:5eae with nothing supplied: CurrentCell,
ReadCell (room links, GetUndefineCellId), GetBarrCode, IsFloor/IsSpace/IsWall,
GetDist1/GetCharCol with DIVS 5:48b0, AdjustRoom 4:56e6, 4:6562/6610 and
4:5b0e. The column word comes from LoadFrame's 4:2a7c.

- Every tile-4 cell of LEVL 2000-2013, the supporting cell on the gate or one
  behind it, both facings, three remainders, three FRAM dx/flags, sequences
  227/68, heights 60/90/120, edges X -/+ 10 or 22, caution 0/1.
- Phases: the desert's 0-20; elsewhere the low byte 0-252 in steps of 9.
- 213,600 cases (desert 2,016; caverns 61,248; ruins 36,192; temple 114,144),
  49,628 barrier results, zero mismatches after the change. Before it:
  703 desert, 1,694 caverns (754 of them the slope reason below), 2,802
  ruins and 26,834 temple mismatches.
- The slope branches 4:5fa2/5fc6 leave the reason word unwritten; the port
  reports 0. 754 cavern cases compare the distance only.
- Result SHA256 (native results only):
  `01b2a552b10c2931a10b944f4d31f846d801f55f2796b2862cbd62651e99db26`.

`tools/probe_prince_turn.py` reran unchanged: 316,128 cases, zero mismatches,
the same result hash.

Excluded: the callers (DoStepFwd 6:1276, DrawSword, GenCtrl), CheckBarr's
collision-bank construction and CheckCollide's response (only its 4:5b0e
decision is shared), and cells other than the gate and the one behind it.
DoRunJump 6:1c50 and the climb test are read statically, not executed.

```powershell
python -m tools.probe_gate_barriers --source PATH_TO_RECOVERY --output rendered/gate-barriers.json
```

## Standing turn (6:10f6-1158)

The standing Backward handler 6:10e4 asks GetCellsInFront 4:39fc for the cell
ahead of the supporting foot. When it is a gate that 4:5b0e blocks, it moves
the Kid back (AddCharX 4:2bae) until GetDist1 4:3a92 leaves a reserve before
SEQS 5 changes facing: 11 pixels in the caverns (LEVL 0x2186 = 3), -100 (that
is, never) when the Kid is in room 9 of level eight, 6 elsewhere. The port
had only the cavern branch: a standing turn at a closed desert exit (below
phase 19), ruins or temple gate kept the Kid up to 6 pixels too close.
`standing_turn_offset` now uses `gate_collides` and the three reserves.

`tools/probe_standing_turn.py` runs 6:10f6-1158 with nothing supplied (same
helpers as above, plus 4:3a92). A terrain sweep over every room/row of LEVL
2000-2013 (X -40..559 step 11, both facings, three FRAM dx/flags) and a gate
sweep (the gate one cell ahead, foot distance 0-12, 20, 40, desert phases 0-20
or the low byte 0-252 step 9, heights 79/30, type 1, sequence 68): 383,490
cases (116,490 terrain, 267,000 gate), zero mismatches. Before the change:
915 desert, 3,899 ruins and 13,341 temple mismatches. Result SHA256:
`0fec63fc2433f96bab3ece739bafa72a2b2fb383128a1340cc0e348b2aadcc39`.

Excluded: the 6:10e4 prologue (3E3A/-503e) and everything from 6:1158 (1FB2,
the SEQS 5 selection).

```powershell
python -m tools.probe_standing_turn --source PATH_TO_RECOVERY --output rendered/standing-turn.json
```

## Drawing the sword (DoKidEngarde 6:1f04)

DoEngarde 6:1e78 calls DoKidEngarde for the Kid (type 0 or 1). It returns
SEQS 55 or -1 (no draw; Ctrl stays consumed, 6:20fc clears a5-0x503c):

1. Refused at poses 246-261, in the desert (LEVL 0x2186 = 1) and in level
   fourteen's native rooms 1-2. Type 1 in the palace rooms 7-8 takes 9:2674.
2. The temple's sliding rock (GetSlideRockX 5:21f6, zero elsewhere) within a
   column measures from the rock instead (6:2020-2070): ahead of the Kid
   the extra is |edge - X| - GetDist 4:3a92 - 6 (-1 before the 6 becomes
   -3); behind him an obstructed draw is refused (6:20ce-20f2). Modelled
   since 2026-10-31; the probe's rock sweep supplies the same edge to both
   (237,900 temple cases, zero mismatches).
3. Facing right with the Kid's own cell (CurrentCell 4:35a6) a gate that
   4:5b0e blocks: the extra is -51.
4. Otherwise the cell ahead (4:39fc) must be an obstruction: not IsFloor
   3:4da6, loose floor (11) or a blocking gate; else the draw needs nothing.
5. Then the cell behind (4:3a48, column -/+ 1 by facing) is tested the same
   way: obstructed there too, or a5-0x5022 = 4 (SEQS -21, the port's
   `sequence_mode`; not the animation state a5-0x5046), refuses.
6. Else GetBarrDistances 4:5eae + extra; below 56 the Kid moves back
   (AddCharX) to 56.

The port reserved 56 only before a gap or wall with a non-gap supporting
cell. It never refused and ignored loose floors and gates ahead, the cell
behind and the right-facing gate cell. `combat_draw_offset` now follows the
rules above and returns None for a refusal; `start_sword_action` then
returns without selecting SEQS 55 (Ctrl already consumed).

`tools/probe_kid_engarde.py` runs 6:1f04 with everything native except the
draw sound 5:4d84 (recorded) and, in the temple, TempGetSlideRockX 10:20fe
(0, no rock). A terrain sweep (every room/row of LEVL 2000-2013, X -40..559
step 9, both facings, three FRAM dx/flags; poses 15/246/261/262, modes
0/2/4) and a gate sweep (the supporting cell is the gate, one behind or one
ahead; desert phases 0-20 or the low byte 0-252 step 9; heights 79/30,
sequence 68, edges -/+ 10 or 22): 262,056 cases (141,906 terrain, 120,150
gate), 127,735 refusals, 32,458 moved, zero mismatches. The last 30 (levels
13-14, a room edge without a neighbour) came from `LevelMap.tile` lacking
GetUndefineCellId's temple and palace branches, translated since
([opponent barriers](opponent-barriers.md)). Before the change: 150,938
mismatches (mostly refusals). Result SHA256:
`f6c15fcde04feb72def317cf583165ea3fec4feada4e999eb8ca4cdac0a02313`.

Excluded: the sliding-rock branch, type 1 and 9:2674, a5-0x503c, DoEngarde
and GenCtrl's admission (`try_draw_sword`).

```powershell
python -m tools.probe_kid_engarde --source PATH_TO_RECOVERY --output rendered/kid-engarde.json
```

## The caution word a5-0x36bc end to end (2026-10-31, static) [D]

`a5_data_references.csv` lists three uses: DoStepFwd 6:1276 sets it to 1 on
entry (6:1280) and clears it on exit (6:1336); GetBarrCode 4:52fe is the
only reader (tile 2 with a foreground low byte below 3 gives code 3 instead
of 4). DoStepFwd reaches GetBarrCode only through GetBarrDistances 4:5eae,
which it calls when its argument is 0 (6:128e-1298). The ordinary callers
GenCtrl 6:0da0 and 6:11c4 pass 0; the other callers are the final battle
(9:0e5e, 0e86, 1474) and the temple (10:288e, 2916, 2944), not ported.
The port asks `step_boundary(..., cautious=True)` only from the scene's step
command, the same path; every other barrier query keeps code 4. Nothing to
change.
