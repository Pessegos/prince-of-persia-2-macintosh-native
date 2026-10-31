# Unarmed runner: obstacle brake and spacing (2026-10-31)

AutoCtrl's running branch 4:057c-07fc runs for an opponent whose pose is odd
in 195-199 or is the last jump pose 212; poses 192/196 of a jump-capable
runner (generation flags a5-0x501e >= 1) go to the jump 4:0834 instead. The
port is `CombatEncounter._choose_unarmed_guard_action` and `_brake_guard`.

## Native order [D]

1. Crowd distance d5 (4:05a4-05f8): GetOppIdxClosestToKid 6:36f2 in the
   opposite facing; itself 127, none 0, else |X - that opponent's X| from the
   bank table a5-0x5204.
2. Kid distance d4 (4:0606-0662): |X - Kid X|; a moving Kid pose (1-14,
   49-56, 34-44) adds 51 when facing the same way, else subtracts 51; a still
   Kid without the sword (a5-0x50b8 != 1) adds 51.
3. Target row: the Kid row a5-0x50c4 equals the opponent row or the
   alternate row (+0x20 of GetOppInfoIdx 6:3642). With it, the cell ahead
   (GetCellsInFront 4:39fc(1)) must be IsAdvancableId 6:5eca.
4. Otherwise (4:0696-06d4): a jump-capable runner whose front edge distance
   (GetFCharX/GetDist1 4:3a92) is at least 39 keeps running when the row is
   the target row and the cell ahead is not a gate; every other case brakes
   with alert 0.
5. On the target row with a free cell ahead (4:06da-07a0): spacing brake
   (alert 2) on the same row unless a same-facing run (second Kid copy
   a5-0x5094, animation state != 7) is at least 102 away; else when crowd
   <= 126 or Kid <= 178. Passing the Kid (column words a5-0x504a against
   a5-0x50c6) brakes with alert 2. A dead Kid or a5-0x509e = 13 brakes with
   alert 0. In an exit-chasing room (IsExitChasingSkel 4:17aa) a Kid within
   127 is lunged at: JumpSeq 87, armed.
6. Braking is JumpSeq 101. From pose 212 the cell behind (GetCellBehind
   4:3a48) must be advancable, else AddCharX(12) (4:07ae-07d6).

## Port before this change

The cells ahead and behind and the passing test used the anchor column
`character_column(target_x)`. Natively all three read the column words,
which LoadFrame 4:2a7c derives from the supporting foot (GetFCharX). With a
frame whose foot is a few pixels off the anchor, the port looked at the
wrong cell: it braked before an obstacle the runner had not reached, ran
into one it had, and missed or invented the pass. The three tests now use
`_supporting_column` for the opponent and the Kid.

## Probe

`tools/probe_unarmed_brake.py` runs 4:057c with its real helpers (ReadCell,
GetUndefineCellId, IsAdvancableId with IsWall/IsImpassable/IsSpace,
GetCellsInFront/Behind, GetFCharX/GetDist1/GetCharCol, IsExitChasingSkel,
AddCharX and the column word 4:2a7c). Supplied: 6:36f2 returns the fixture's
nearest slot (itself, none, or slot 3 with its X in the bank table); 6:3642
returns a record with the alternate row; JumpSeq 6:0006 and 4:0834 are
recorded. Every LEVL 2000-2013 room and row, X -10..509 step 23, both
facings, poses 192/195/196/197/199/200/212, four frame fixtures for the
opponent and the Kid, Kid offsets and poses, flags 0-2, ALIVE, 13, the
same-direction state, crowd variants; plus every gate one cell ahead or
behind across phases (low byte step 13), poses 195/212, flags 0/1:
75,472 cases (50,832 terrain, 24,640 gate), zero mismatches. Result SHA256
`73931d2dede76b5991919ca302612aad605b8d0b82b39e6239f8b706fdbee49d`.
The previous code (anchor columns): 388 terrain mismatches, all from the
column (cells ahead/behind and the pass).

Exclusions: the pose-166 and armed branches of AutoCtrl (4:04fc), the jump
itself (4:0834, DoRunJump), opponents outside the Kid room (the port also
tests the room, natively the processed opponents are the Kid room's bank).

ResumeRun 4:011e (alert 1 keeps running; else JumpSeq 102 for type 4, 84
otherwise, unarmed, alert 0) matches `_resume_guard_run` statically; its
callers (GenFight 4:0df2/0e68/1056, caverns 8:03e8) were not probed here.

```powershell
python -m tools.probe_unarmed_brake --source PATH_TO_RECOVERY --output rendered/unarmed-brake.json
```

## Level-four exit rooms: can a skeleton pass the exit door? (2026-10-31)

Native [D]: the exit door cells (tiles 16/17, room 22 cells 23-24) are
ordinary advancable floor for an opponent (IsAdvancableId 6:5eca: not
IsWall, not IsImpassable 3:4de2, not a space). Nothing in AutoCtrl,
EnemyCollide or CheckGateForOpp stops an opponent at the door; a runner
stops relative to the Kid (spacing <= 178, the pass, the 87 lunge within
127 in the exit-chasing rooms 22, 24-28 of IsExitChasingSkel 4:17aa). The
skeletons sleep in rooms 26-28 (zero-based 25-27); the wake needs the door
fully open (SkelDoneShaking 4:1ae0-1b34) and the Kid in the skeleton's room
to its left, within eight columns on a clear path (OpponentClose 4:1522-1570).

Port (offscreen, withdrawn Tk root, god mode, door forced open): a skeleton
set running left in room 22 from X 480 with the Kid standing at X 230 brakes
at 333 (alert 2, SEQS 101, the 4:057c rule probed above), draws (90) and
fights; it never reaches the door cells while the Kid is there. Rising in
room 26 next to the Kid, it fights him there. No pass through the door was
observed, and the native rules give no reason for one: the door is not a
barrier, the Kid is. Not reproduced: a full native multi-room chase (no
whole-frame native emulation exists here); the cross-room following of
running opponents (FrameAdv 2:6550-65da, item 7 of the plan) remains open.

## The opponent's draw: GenCtrl 4:4996 and DoEngarde 6:1e78 (2026-10-31)

At pose 166 with a draw request (a5-0x3482 < 0) GenCtrl's opponent branch
turns instead when a turn is requested (SEQS 80). Otherwise, when the cell
behind (GetCellBehind 4:3a48, column word) is not IsAdvancableId, AddCharX(8)
moves the body forward; DoEngarde clears the inputs (4:3e3a), arms the
opponent and, for every type but the Kid and the heads, asks
GetBarrDistances 4:5eae: 0 < d < 18 gives AddCharX(d - 18); then SEQS 90.

4:5eae reads its cells through the column word a5-0x504a and its barrier
distances through the character edges, both from before that AddCharX(8),
but its edge distance (GetFCharX/GetDist1) from the moved X. The port used
the anchor column for the cell behind and recomputed everything from the
moved X, so a draw beside a wall could reserve when the original did not.
`CombatEncounter._draw_guard_sword` now takes the column word and the edges
before the step and passes the column to `step_boundary(column=...)`.

`tools/probe_opp_engarde.py` runs 4:4996 + DoEngarde with the whole 4:5eae
(as in probe_kid_engarde), IsAdvancableId and AddCharX; JumpSeq is recorded,
edges/heights are fixtures. Every LEVL 2000-2013 room and row, X -20..529
step 7, both facings, three FRAM fixtures, types 2/4, two heights, a turn
request every 17th case; every gate behind or ahead across phases: 241,290
cases (167,322 terrain, 73,968 gate); 6 mismatches, all in level thirteen's
room 4 row 1 (the temple, not playable: the port reserves where 4:5eae does
not, presumably a temple cell kind step_boundary does not model). Elsewhere
zero. Result SHA256
`a8545f5d9a5173f989b57563e46d9e9dce50b3ec08ce2b470136d06e0e4ecca9`.
Excluded: the decision to request the draw (AutoCtrl 4:04fc).

## Which opponents get physics: FrameAdv 2:6550-65d6 (2026-10-31, static)

After AnimChar (2:6538) the opponent pass runs Move 4:341a/3464, LoadFrame,
the drawing setup, GetCharEdges and, outside animation state 9,
EnemyCollide 4:62b0, CheckGateForOpp 4:5ffc and the hazards 5:1202/127e,
then the environment's own checks, only when:
- native X a5-0x5052 is 54..869 (scene -153..662, in the Kid room's frame)
  and Y a5-0x5050 <= 730 or the opponent's room has a room below; else
- level 11 or 13 with Y < 730; else
- level five, row not 0, rooms 7/10/12 (the bridge rooms); else
- the palace (environment 6), rooms 7-8.
Otherwise AnimChar still moves the opponent, but it neither falls, collides
nor changes room. The port ran the terrain step for every active opponent;
`CombatEncounter._physics_admitted` now gates `_advance_guard_terrain`.
The earlier skip of the whole decision below Y 484 without a room below
(2:64f2-6512) was already modelled. Not probed natively (a pure branch);
`test_frameadv_admits_opponent_physics_only_inside_the_native_x_window`.
