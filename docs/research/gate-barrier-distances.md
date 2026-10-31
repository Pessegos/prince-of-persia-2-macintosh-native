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
