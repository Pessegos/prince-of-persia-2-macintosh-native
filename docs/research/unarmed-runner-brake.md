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
