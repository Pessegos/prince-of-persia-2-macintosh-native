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
-0x5086, X -0x5090, pose -0x508a, room -0x507e, native ALIVE -0x5078 (negative
while alive, then a death counter; Codex: recovery notes), life points
-0x5076, selected SEQS -0x506c, armed -0x507a (+0x1a; tested == 1 below).

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
   already 166, if Y is within 30 of its cell's vertical middle (7:17c8),
   JumpSeq 166 (hover).
4. dc == 0 and dr == 1, and moving `seen` is admitted: JumpSeq 143 if the
   head is below the Prince's row (row > Prince row) else 144.
5. `seen == 4` (same cell): unless dc|dr == 0 or already 166, Y
   within 30 of the cell's middle (7:17c8) -> JumpSeq 166.
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
166: if ChompAgain (7:0494) says to bite again: while the Prince is alive
(native ALIVE `-0x5078 < 0`) increment `info[2]` and JumpSeq 150 (from
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

If the Prince's native ALIVE `-0x5078 >= 6` (dead for a
while): HeadGetPeaceful. Otherwise, unless
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

7:161c needs more than one record in the room and every record (this
one included) neither fleeing (mode 2) nor a serpent (kind 8). Then
Rnd(skill / 3 + 1) must be 0 (skill = record +6). Facing right needs
column >= 3; facing left needs column + 3 <= 10. It scans behind the head
(toward column -1 facing right, 10 facing left) for barriers (4:52bc;
kinds 2/7/12/20/25, a gate only while 4:5b0e says it blocks). A clear
path stops one column short of the edge; a barrier stops two columns
before it and must still be at least 3 columns away. Success sets armed
0, state 1, record mode 2, destination (that column, row), +0x22 = -1,
+0x24 = 0, and unbanks the head.

## Serpents 7:1824

Sequences: 170 slither (loop), 171 into the hole (holds pose 264), 172 out
of a floor hole (then 170), 173 strike, 174 death, 175 coiled (poses
278/279), 176 rear up into the coil, 177 uncoil (then 170), 168 rest
(pose 230).

Cell predicates (3:4da6-4f30): IsWall = 2/7/20/25/43, IsSpace =
0/9/27/47/49, IsFloor = neither. Below, `passable(c)` means IsFloor with
an open gate (a gate needs foreground bit 0x80; `fg & 0xb8 > 0x38` is that
bit) or a type-7 cell with bit 0x80 (an uncovered crevice). "Ahead" is
4:39fc(1), the cell in front; "here" is 4:35a6.

The wrapper 7:1824 runs for negative ALIVE with a record. Record word
+0x1c < 0 (active): when 7:1dc6 holds, strike (7:187e), otherwise
7:1b52. Otherwise 7:19fe (waiting). 7:1dc6: not SEQS 171, alert state
(-0x5024, from the ordinary alert routine 2:6ee4) >= 2, and facing the
Prince (facing right with column <= his, or left with column >= his).

Strike 7:187e, with `d` = 4:49ee:

- 31 <= d <= 71: strike on poses 278/279, or during SEQS 176 while the
  Prince's pose is 1-14 or 49-56. Otherwise, outside SEQS 176/173 and
  with 20 <= d <= 60: JumpSeq 176 and sound 128.
- Else, during SEQS 176: strike when the Prince's pose is 1-14 or 49-56
  and 31 < d < 79, or 135-149 and 31 < d < 71. On poses 278/279 with d <
  31 or d > 77 and `passable(ahead)`: JumpSeq 177.
- Strike (unless already SEQS 173): X = AddCharX(d - 58), JumpSeq 173.

Inactive 7:1b52:

- The Prince not alive: JumpSeq 176 unless already there or coiled.
- SEQS 171/172 or special flag 9: see the hole step below.
- `here`'s foreground high nibble (& 0xf00) is 15 (a hole) and the signed
  remainder of (X - 229) / 51 is 16..28: X = AddCharX(22 - r), negated
  facing left and less 2 facing right; JumpSeq 171.
- SEQS 176/168 or coiled: JumpSeq 177 when `passable(ahead)`.
- Otherwise, with ahead not passable: an IsWall ahead of type 7 -> 168; a
  wall facing right -> special flag 9; a wall facing left on pose 254 or
  238 -> 168. Not a wall (space or a closed gate) and 4:3a92 < 25 -> 168.
- Hole step: with special flag 9, IsWall here and 4:3a92 < 12, pose
  264 and JumpSeq 168. On pose 264: special flag 6 and the record timer
  +0x1c = 6 if the alert state is 2, else Rnd(60) + 36.

Waiting 7:19fe: count +0x1c down; at zero set it to -1 and choose a
facing. The Prince in the same room and row strictly between the floor
edges 5:2198 (directions -1 and 1): face left if he is at a lower column;
otherwise face right unless `here` is a wall other than an uncovered
crevice (then left). The Prince elsewhere: reverse the facing. Then a
non-wall or uncovered `here` -> JumpSeq 172; a wall -> JumpSeq 170 with
X = AddCharX(61). Special flag 0.

SnakeUpdateOppInfo 7:1e04 (from the record save 6:342a): in SEQS 171 or
with special flag 9, special flag 6 and the timer Rnd(60) + 36. Otherwise
with `passable(ahead)` and SEQS 176/168/170, the stored facing becomes
NOT facing and the stored X AddCharX(-51).

## Combat: TestStrike, CheckStab And Death

Heads and serpents use the ordinary combat pipeline. TestStrike's
per-striker check (6:5896) and CheckStab (6:5092/51f2) carry the special
cases below; "striker" is the working actor, "defender" the cached one.

Contact (6:5896). The striker must be armed (+1) and in the defender's
row. The vertical limit (|Y difference| < 15) is waived when either side
is a head. IsStrikingPos 6:5d60: heads on poses 165-167 or 181; a serpent
only in SEQS 173 on pose 274 or 280. The defender must be alive, not type
1 or 10, not already marked 8 and not in SEQS 110. `d` = 4:49ee (facing
distance). Block window: heads 0..55, type 10 24..70, others 61..99.

- Parry: facing differs, `d` in the window, the defender is not a head or
  serpent, the striker is not a serpent, and the defender's pose is 161 or
  150. The defender's pose becomes 161. A head striker is banked and the
  parry timer a5-0x369e = 4; then HeadHit 7:08fa (below) picks its
  sequence. So blocking a head hurts the head.
- Otherwise the strike lands (defender mark 10) when IsTheStrikePos 6:5e42
  holds and `d` is inside GetCharStrikeRanges 6:5b38. Heads never satisfy
  IsTheStrikePos (pose 154 is outside their striking poses): a head bites
  instead whenever its special flag is 1 (SEQS opcode -21 1 on poses 167
  and 181) while the parry timer is 0.
- Strike ranges for the Prince: against a head 32..92; against a serpent
  only from SEQS 96 when the serpent's special flag is not 6 and its SEQS
  is not 171: 62..126 facing the same way, -11..79 otherwise. Sword type
  2 (a5-0x500a) lowers the upper limit by 10. A serpent striking the
  Prince needs his Y >= row * 120 + 96 and uses 8..52 (same facing) or
  -32..6. Serpent IsTheStrikePos is pose 280.

CheckStab finds the Prince's striker by pose: a head counts only on pose
167 or 181 (6:51ae-51b6), others through IsTheStrikePos. Then (6:51f2):

- Struck head: damage 1 with sword type 2, otherwise 2; SEQS 153 if it
  survives. Before the damage, if its life exceeds the damage,
  IsAbleToFleeInRoom runs. Hit sound 130.
- Struck serpent, or the Prince struck by a serpent: damage 100. A
  surviving serpent keeps its sequence. Serpent hit sound 127.
- The Prince struck by a head: damage 1, no hit sound. The base reaction
  is 74 (facing differs) or 94 (same facing). Unarmed, unless his frame
  has flag 0x40 or his pose is 191-205, the reaction becomes 45; poses
  102-106 also give 45. On poses 246-261 he is pushed 25 pixels toward
  open floor. Any reaction other than 45 arms him.

Death 6:5562. A head turns to face away from the Prince (facing = NOT the
Prince's), life 0, JumpSeq 154 (falls and ends with -17, removal) and
SetTensionLevel(1, -1). A serpent JumpSeq 174. The Prince killed by a
serpent: SEQS 97 (98 on poses 246-261), sound 126, death method 17. Killed
by a head: SEQS 85 (98 with sound 133 on poses 246-261), death method 6
and SetTensionLevel(1, 5). The tension amount a5-0x36a0 is ChompAgain's
`wounds`: each death to a head makes the heads let go sooner.

HeadHit 7:08fa (the symbol table calls it HeadClearInDir): DecLifePts(1);
dead -> 154; else sound 131, IsAbleToFleeInRoom and 153. Both paths call
SetTensionLevel(1, -1).

SEQS opcode -17 (4:48f8) removes the actor: unbank it, facing 86 (the
removed marker), clear -0x5046, ALIVE and life, reselect the Prince's
opponent if it was this slot, room 0. Opcode -22 `n a b` jumps to `a`
when Rnd(n) != 0, else to `b` (17:6e06 is the inclusive Rnd).

Drawing (3:0b32-0b9c): with special flag 1 a head is drawn by
AlignHeadOnKidNeck 7:0006, which also sets its working X.

## Runtime Groundwork

`pop2/ruins_actors.py` (not wired into the game yet) parses the set-5
records (kind +0x18 through a5-0x5280: 5 -> head 7, 6 -> head 8, 8 ->
serpent 11), HeadAddOpponent's starting state, the Head FRAM index (type 8
+43 below pose 182) and ChompAgain's bounds. Per level: six 6
(4 heads, 2 serpents), seven 14 (8 heads, 6 serpents), eight 24 (19 heads,
5 serpents), nine 12 (6 heads, 6 serpents).

## Controllers In Play

`pop2/ruins_ai.py` translates the head wrapper and leaves (sight, movement
admission, idle, angry, peaceful, attack, focus, locked, done, go-to,
flee, flee check), the serpent routines above, MoveChar's flight for heads
(Y += vy with GetRow, X += AddCharX(vx)) and the combat rules above.
SequenceRuntime gained opcodes -9 (additive velocity), -17 (removal, as an
event) and -22 (random JumpSeq); -19 sets a head's -33 floor height.

CombatEncounter owns a `RuinsCreatures` for opponent sets 5/6, separate
from the ordinary guard bank: it loads a room's records on entry (heads
restart at rest, as HeadAddOpponent does), runs control, AnimChar and
flight each world frame (decrementing the shared AutoCtrl timers per
actor), then TestStrike/CheckStab against the Prince. The scene draws them
with Head.rsrc (type 8's +43 frame offset via `actor_frame_index`), drains
their sounds and passes the sword type. Events carry their own sound (0 for
the silent bite and parry).

DoStrike 6:2780-2816: from the en-garde poses 157/158/170/171/165 the
Prince's strike is SEQS 96 when his opponent is a serpent (6:27d0-27da),
otherwise 75 (an armed NPC of type 10 uses 109, others 58; poses 150/161
riposte with 66). The port selects 96 when the nearest living ruins actor
(6:36f2) is a serpent. The opponent meter shows the banked head
(HeadGetAngry 7:0fc6-0fea, a5-0x505a) while it lives in the Prince's room.

Port approximations: the wall contact (an armed head inside a wall or
closed gate cell is pushed back 22 pixels instead of the full CheckBarrier
4:62b0 distances); the column read live from the pose instead of the value
cached at LoadFrame; an actor whose supporting column leaves 0..9 moves to
the neighbouring room's list (the original cut 2:6680-6700 is not
translated); IsSoundPlaying is not consulted; the kill song 137 plays at
death rather than when native ALIVE reaches 6. Rebirth checkpoints (and so
saves, which keep the checkpoint) carry the ruins actors: killed heads and
serpents stay dead, the living restart at rest on entry.

## Native Comparison Of The Runtime

`tools/probe_ruins_runtime.py` runs the original code in the Unicorn
harness (Codex's level7 machines) and the game's own `pop2/ruins_ai.py`
on the same supplied states, then compares every working field, the
record words, sounds, random draws and the Prince's target:

```powershell
python -m tools.probe_ruins_runtime --source PATH_TO_RECOVERY --output rendered/ruins-runtime-probe.json
python -m tools.probe_ruins_runtime --source PATH_TO_RECOVERY --output rendered/ruins-serpent-probe.json --serpents
python -m tools.probe_ruins_runtime --source PATH_TO_RECOVERY --output rendered/ruins-stab-probe.json --stab
```

| Run | Original | Cases | Mismatches |
| --- | --- | --- | --- |
| Heads | wrapper 7:1324 and every leaf it reaches | 20,000 | 0 |
| Serpents | 7:1824 with 1dc6/187e/19fe/1b52 | 20,000 | 0 |
| Struck head/serpent | CheckStab 6:51f2, DecLifePts, flee check, death 6:5562, SetTensionLevel | 20,000 | 0 |

States are randomized (seeded) over the actual level-seven head and serpent
slots, every record mode, the relevant poses and selected sequences, Prince
positions, life and native ALIVE. The heads run reaches SEQS 131-144, 147,
150-152, 156, 159, 160, 162, 163 and 166 and sounds 131/134/136; serpents
reach 168, 170, 172, 173, 176 and 177 (not 171: no hole cell was drawn).
Supplied endpoints: Rnd (the same seeded draws on both sides), AddSound and
AddSong (recorded), IsSoundPlaying (0), 6:3946 (a supplied flag), shape
bounds (body height 30), DrawOppMeter, AnimChar and the nearest-opponent
choice in the death branch. The serpent wrapper is called after LoadFrame,
as the opponent pipeline does (2:6512); the original serpent leaves read
the loaded frame.

The probes found and fixed three port errors: GoToDest reads the column
remainder left by the last GetCharCol (a5-0x481c), not a fresh one; the
opponent distance 4:49ee is 999 when the Prince has no life (the port used
the guards' version); and the Prince's target, not a ruins-only bank, is
what HeadGetAngry fills (a5-0x505a is the cached Prince's +0x3a).
DecLifePts queues damage in a5-0x5034; the port applies it at once.

Not compared yet: the Prince struck by a head or serpent (CheckStab with the
Prince's frame flags), TestStrike's ranges, AnimChar of the head sequences,
flight, the wall contact and the per-frame scheduling.

## Still Open

Neck alignment while biting (AlignHeadOnKidNeck needs the drawn Prince
object index), the development map, the original cut between rooms, and
native comparisons of the Prince's side of CheckStab, TestStrike's ranges,
AnimChar of the head sequences, flight and per-frame scheduling.
