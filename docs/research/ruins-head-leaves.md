# Ruins Head Controller Leaves

Read from the original CODE 7 (2026-10-24), continuing Codex's
[level-seven preparation](level7-preparation.md) notes (initialization,
frame loading, routing, idle, movement admission, sequence selection,
recovery, neck alignment). Those notes have native probes; the routines
below are translated by reading only (no probe yet). Addresses are
CODE:offset. Nothing here is wired into the runtime.

## Names

Working actor (the head being controlled, A5 offsets): X -0x5052, Y
-0x5050, facing -0x5054 (0 right, -1 left), column -0x504a, row -0x5048,
room -0x5040, pose -0x504c, selected SEQS -0x502e, native ALIVE -0x503a,
armed -0x503c, special flag -0x5022, head state -0x5024 (3 angry, 1 flee,
0 peaceful), slot -0x5056.

Cached opponent (the Prince, copied by 4:3272): column -0x5088, row
-0x5086, X -0x5090, pose -0x508a, room -0x507e, life -0x5078, life gate
-0x5076, selected SEQS -0x506c, -0x507a (tested == 1 below).

Record pointer `info` = generator record + 0x1c: `info[0]` mode (0 idle,
1 attack, 2 flee, 3 locked), `info[2]` destination column (locked: bite
count), `info[4]` destination row, `info[6]` timer/flag, `info[8]` flee
sound flag.

Sequence IDs (decimal): 131-133 drift left, 134-136 drift right, 137 up,
138 down, 139 calm (HeadGetPeaceful), 140 angry, 142 turn, 143 up, 144
down, 145 dying, 147 swoop, 150/151 bite, 152 shaken off, 155 locked bob,
156-160 flee/recover, 162/163, 164 hurt, 165/166 hover. Poses: 150 idle,
159/165/166/173 hover, 166/167 locked.

## Wrapper 7:1324 (Codex: routing)

`target_ok` = cached `-0x5076` nonzero and not (opponent SEQS 70 with pose
0 or >= 223). Mode 0: angry (7:0f88) when `target_ok`, pose in 150/165/
166/159/173 and CharCanSeeOpp != -1, else idle (7:1268). Mode 1: attack
(7:064c) if `target_ok` else done (7:0b16). Mode 2: flee (7:0cae). Mode 3:
locked (7:1164) if `target_ok` else done.

## HeadGetAngry 7:0f88

`info = [1, prince column... ]`: mode 1, destination (Prince column, row),
timer 1. JumpSeq 140; StopChar (4:34e2); face the Prince (7:0c5e); state
3; armed 1. If no opponent is banked (-0x505a == -1), bank this one
(4:4a46, 3:4a8e, 4:4ac0) and record its slot. AddSound 131.

## HeadGetPeaceful 7:1012

Mode 0, armed 0, StopChar, JumpSeq 139, column = GetCharCol(GetFCharX),
X = column anchor + 47 (`a5-0x4b88[column] + 47`), SetCharFloor, state 0.

## Face The Prince 7:0c5e

If the head's column < the Prince's and it faces left (-1): X =
AddCharX(-12) (relative to the old facing), facing = 0 (right),
StopChar. If its column >= the Prince's and it faces right (0): X =
AddCharX(-12), facing = -1, StopChar.

## HeadAttackProg 7:064c

Returns at once while the selected SEQS is 140, 152, 156 or 162. While it
is 147-151 (swoop/bite), run HeadFocusOnNeck (7:0e8c). Otherwise only on
poses 150, 165, 166, 159 or 173:

1. `seen = CharCanSeeOpp()`. If -1: if `info[6]` was set, clear it and
   restore the destination to the Prince's cell; then HeadGoToDest
   (7:107a). Done.
2. `info[6] = 1`; `dc = |column - Prince column|`, `dr = |row - Prince
   row|`.
3. Same row and dc < 2: direction toward the Prince (1 if X < Prince X,
   else 0). If dc == 0 or movement in that direction is admitted
   (7:0936): JumpSeq 147 (swoop) unless already. Otherwise, unless
   already 166, if ChompAgain-style random test 7:17c8(Y, 30) passes,
   JumpSeq 166 (hover).
4. dc == 0 and dr == 1, and moving `seen` is admitted: JumpSeq 143 if the
   head is below the Prince's row (row > Prince row) else 144.
5. `seen == 4` (same cell): unless dc|dr == 0 or already 166, random
   7:17c8(Y, 30) -> JumpSeq 166.
6. Otherwise destination = Prince cell. For `seen` 2 or 3 (vertical)
   that is not admitted, use the horizontal direction toward the Prince
   instead. If that direction is admitted: 3 -> 143, 2 -> 144, horizontal
   -> 142 (turn) after facing the Prince (7:0c5e) and SetCharFloor unless
   already 142 and within 12 px of the Prince's X. If not admitted:
   StopChar and JumpSeq 166.

## CharCanSeeOpp 7:00f8

Returns 4 when head and Prince share a cell. Otherwise it walks a
Bresenham line on a half-cell grid (each cell is 2x2: the head's
half-column is +1 when its foot X remainder within the cell exceeds 25,
the Prince's likewise; the Prince's half-row is `2 * row + 1`) through
ReadCell (4:27ee) of the head's room, failing on cells for which 3:4ef2
(not space) or 3:4eb2 (wall) holds. If the line is clear and 6:3946
holds, the result is the direction to move: 2/3 (down/up) when the rows
differ, otherwise 1 (right) or 0 (left); without 6:3946 it is 4. A
blocked line returns -1.

## HeadFocusOnNeck 7:0e8c

Only for SEQS 147, 144, 143. Window: if `-0x507a == 1`, 0..60, else
5..68, on `d = 4:49ee()` (horizontal offset to the Prince's neck). In
the Prince's row with `d` inside the window: StopChar, JumpSeq 150 + Rnd(1)
(bite 150 or 151), `info[0] = 3` (locked), `info[2] = 1` (bite count).
Otherwise (threshold -16 or -11): during 147 with `d` below it, StopChar
and JumpSeq 156; out of the Prince's row JumpSeq 142. When `d - 101 <=
window end` in the Prince's row and not SEQS 144: AddSound 134.

## HeadLockedProg 7:1164 (bite)

At SEQS 150 on pose 167 (or with special flag 1), or at SEQS 151 on pose
166: if ChompAgain (7:0494) says to bite again: when the Prince's life
`-0x5078 < 0` (no life left) increment `info[2]` and JumpSeq 150 (from
151) or 151 (from 150); else, when the opponent record's +6 is >= 11,
JumpSeq 165 (let go). If ChompAgain says stop: JumpSeq 152 (shaken off),
X = AddCharX(-12) and `released`. After a release, or in SEQS 158/157/155:
`info[0] = 1` (attack) with the destination at the Prince's cell.

## ChompAgain 7:0494

`level = 2` if a5-0x36a0 > 30, `1` if > 20, else `0`. With the record
skill `s` (generator word +6), lower = table a5-0x2cd2[s] - level,
upper = a5-0x2cba[s] - level. Bite count `info[2]` < lower: bite again;
>= upper: stop; otherwise Rnd(1).

## HeadDoneAttackingKid 7:0b16

If the Prince's life `-0x5078 >= 6`: HeadGetPeaceful. Otherwise, unless
already 166: SetCharFloor and JumpSeq 166. Special flag 0.

## HeadGoToDest 7:107a

Already at the destination cell: HeadGetPeaceful. Different row: try
vertical movement, direction 2 with SEQS 144 when the destination row is
below (greater), else direction 3 with SEQS 143, and JumpSeq it if
admitted. Then, if still not
moving and the column differs, try horizontal (1 if destination column >
column, else 0). Blocked horizontally: moving right succeeds anyway when
the actor's -0x481c < 25, left when it is > 25 (a middle-of-cell test);
then JumpSeq 142 (turn) unless already. If nothing admitted:
HeadGetPeaceful. Returns whether it moved.

## HeadEnemyCollide 7:0b6e

Called from the actor collision routine at 4:647c with the distance to a
barrier (4:6562 measures it in the head's row), not from sword combat.
Unless special flag 1, with that distance `d` in `min..4` and `d >=
-width`: X = AddCharX(-22 - d) (pushed out of the wall). If native ALIVE
< 0 and not SEQS 153: return 157 (bounce). Else, unless SEQS 164: on
poses <= 191 return 164 and snap X to the column anchor + 22 (+51 facing
left); on later poses JumpSeq 145 (dying). Then DecLifePts(100) for the
head (4:34f2): a dead head that hits a wall is finished. Returns -1 when
there is no contact.

DoStrike (6:2638) gives the head family its own strike: unless already
SEQS 156 or 166, or locked on (IsHeadLockedOn 7:16b8), JumpSeq 156.

## Flee 7:0cae / 7:0c5e

SEQS 153: nothing (until special flag 2 clears -0x5024 and JumpSeq 159).
SEQS 159: once back in the destination column and X is within the
middle window (tolerance 3): if in the Prince's row within 2 columns,
HeadGetAngry; otherwise JumpSeq 160 and `info[6]` = a5-0x2ca2[skill]
(rest frames). Other sequences: in the Prince's row within 2 columns with
a living target, HeadGetAngry; else count `info[6]` down; at zero, with a
living, visible target, HeadGetAngry and JumpSeq 162, otherwise
HeadGetPeaceful and JumpSeq 163. The first flee frame requests song 136
unless sound 131 is playing (`info[8]`).

## IsAbleToFleeInRoom 7:1454

Needs another head in the room that is not fleeing (7:161c: more than one
record and not every other one in mode 2 or kind 8) and Rnd(room count /
3) == 0. Facing right needs column >= 3; facing left needs column + 3 <=
10. It scans away from the Prince over barriers (4:52bc, gates by
4:5b0e); with a clear path to the room edge, or a stop at least 3 columns
away, it sets armed 0, state 1, record mode 2, destination (that column,
row), +0x22 = -1, +0x24 = 0 and unbanks the head.

## Serpents (7:1824, partly read)

SnakeComeOutOfHole runs for negative ALIVE. Record mode < 0: if 7:1dc6
holds, 7:187e (strike when the Prince is 31..71 pixels away, or during
his poses 1-14/49-56/135-149, JumpSeq 173 with X adjusted by `d - 58`;
otherwise SEQS 176 with sound 128 at 20..60 pixels; poses 278/279 retract
with SEQS 177 when the cell in front is a wall or an uncovered crevice).
Else SnakeGoIntoHole 7:1b52. Record mode > 0: 7:19fe counts it down and
then turns the serpent toward the Prince when he is in its row between
the floor edges 5:2198 (directions -1/1), choosing SEQS 170 (out, X +61)
or 172 (in). Not translated further yet: 7:1b52 onward, 7:1dc6,
SnakeUpdateOppInfo 7:1ed6.

## Runtime Groundwork

`pop2/ruins_actors.py` (not wired into the game yet) parses the set-5
records (kind +0x18 through a5-0x5280: 5 -> head 7, 6 -> head 8, 8 ->
serpent 11), HeadAddOpponent's starting state, the Head FRAM index (type 8
+43 below pose 182) and ChompAgain's bounds. Per level: six 6
(4 heads, 2 serpents), seven 14 (8 heads, 6 serpents), eight 24 (19 heads,
5 serpents), nine 12 (6 heads, 6 serpents).

## Still Open

The Prince's side (bite damage per chomp, the bitten sequences 150-155 of
the Kid, shaking a head off), what calls HeadEnemyCollide (sword
contact), head death and removal, the remaining serpent routines and
drawing (Codex: neck alignment). Every value above needs a native probe
before runtime use.
