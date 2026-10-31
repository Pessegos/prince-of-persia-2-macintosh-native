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
