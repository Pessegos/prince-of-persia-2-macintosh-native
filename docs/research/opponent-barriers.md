# Opponent barriers: EnemyCollide, OpponentClose, MobDart (2026-10-31)

The gate collision 4:5b0e (see [gate barrier distances](gate-barrier-distances.md))
has three callers outside the Kid's step, turn and draw: the opponents' wall
contact EnemyCollide 4:62b0 (4:6340/636a), the dormant-opponent proximity
check 4:13a4 (4:1486) and the cavern dart MobDart 8:2f98 (8:30fc).

## EnemyCollide 4:62b0 (opponents)

FrameAdv's opponent pass (2:65da-65fa) runs Move, LoadFrame, the drawing setup
and GetCharEdges, then EnemyCollide and CheckGateForOpp 4:5ffc. The Kid's pass
(2:6392-639e) uses CheckBarr 4:4e34, CheckCollide1 4:54da (Collide 4:5738) and
CheckGateForKid 4:60e4 instead: EnemyCollide is never called for the Kid.

For an ordinary opponent (the heads 7/8 add HeadEnemyCollide 7:0b6e, already
in `RuinsCreatures._wall_contact`):

1. Only in animation state a5-0x5046 = 1 (SEQS -7), with native ALIVE
   (a5-0x503a < 0), the sword drawn (a5-0x503c = 1) and a selected sequence
   other than 58 (6:62e2-631e).
2. The cell is the supporting one (CurrentCell 4:35a6), else the one ahead
   (4:39fc), when IsWall 3:4ef2 (2, 7, 20, 25, 43) holds or it is a gate that
   4:5b0e blocks. CheckCollide 4:5654 then rejects an open crevice for a body
   at most 34 high (4:5ade) and everything for type 11 (the serpent).
3. Both distances: GetBarrDistFromFace 4:6562 and GetBarrDistFromBack 4:6610
   with GetBarrCode 4:52bc (tile 43 has code 0: face -1, back 200). The
   nearer one, at least five pixels out (4:6416-6472).
4. Within [-width, 5): pushed out (AddCharX 4:2bae) and JumpSeq 65; 64 only
   for a gate with a non-negative push, which the sign rules never leave.
   AnimChar and LoadFrame follow (6:653a-6546). No sound is requested.

The cell anchor is the column table a5-0x4b88 (207 + 51 * column) + 22,
rebased by AdjustRoom 4:56e6. ReadCell turns a cell past an edge without a
neighbour into room 0 at the wrapped column (4:26e2-27d6); AdjustRoom then
matches room 0 with the first missing link among left/down-left (-510) and
right/down-right (+510) filled by 3:1ab0. A right-edge cell therefore lands
510 pixels to the left of the room whenever the left or down-left neighbour
is missing, and the opponent meets no barrier there.
`LevelMap.barrier_x` reproduces this; `LevelMap.enemy_collide` is 4:62b0.

### Port before this change

Opponents ran the Kid's swept `wall_correction` and Collide response: pushed
to the barrier edge from any overlap, SEQS 64 (with the sword-contact cue 10)
when pushed back, 65 when pushed forward. `RooftopPhysics.advance` now takes
EnemyCollide for an armed opponent in animation state 1 with native ALIVE
(`_native_alive`): a wall or gate ahead is met with SEQS 65 and no cue, an
overlap under five pixels stands, and the push follows the nearer of the two
distances. Other opponent states (unarmed, falling, recoiling) keep the
port's swept correction: natively they meet no barrier at all, but the
correction prevents walking through walls in port paths whose controller is
not yet native (for example the unarmed running skeleton of 21c5606). That
safeguard is a port exception, not recovered behaviour.

### Native execution

`tools/probe_enemy_collide.py` runs 4:62b0 with ReadCell, CurrentCell/
GetCellsInFront, IsWall, CheckCollide, the crevice and gate collisions,
GetBarrCode, both distance routines, AdjustRoom, AddCharX, the neighbour words
(3:1ab0-1c3c) and the column word (4:2a7c). Supplied: the drawing setup
3:0ac8 and GetCharEdges 4:5cbc (their outputs are fixtures: edges, width,
height, clipped top/bottom), JumpSeq 6:0006 (recorded), AnimChar 4:2c0c and
LoadFrame 4:2a72 (inert).

- Barrier sweep: every cell of kind 2, 4, 7, 10, 12, 20, 25, 43 in LEVL
  2000-2013, X from 60 before to 112 past it in steps of 3, both facings,
  three FRAM dx/flags, five body sizes, types 2/4/5 (and 6/11 in variants),
  every 11th case varying animation state, ALIVE, armed and sequences 58/64/
  216.
- Gate sweep: every gate, desert phases 0-20 or the low byte 0-252 step 9.
- 511,788 cases (413,888 barrier, 97,900 gate): 188,633 responses, all SEQS
  65; zero mismatches. The last 55 (level 13, native room 4, column -1) came
  from `LevelMap.tile` lacking GetUndefineCellId's temple branch (a space
  there, not a wall); see below.
- Result SHA256 (native results only):
  `4e30ed9b6c014fd7c688650edabedb7e2333887b2623ca869f63268972a9d441`.

Excluded: the heads, opponents outside the Kid room, the caution word
a5-0x36bc, and which opponents FrameAdv 2:6550-65da lets reach the call.

```powershell
python -m tools.probe_enemy_collide --source PATH_TO_RECOVERY --output rendered/enemy-collide.json
```

## OpponentClose 4:13a4 (dormant opponents)

4:14c6 (FrameAdv 2:624a) wakes a dormant opponent when 4:13a4 accepts it:
the bank record exists, ALIVE is clear, a5-0x5022 is not 5, the rows match,
a5-0x50ca is clear, a running shake timer defers to IsExitChasingSkel 4:17aa,
the opponent's column lies within the reach (8 in the exit-guarded rooms, 4
on skeleton levels, 5 otherwise), and every cell from the Prince's column to
the opponent's is IsFloor 3:4da6 (not a wall or space), not IsImpassable
3:4de2 (11, 15, 26, 12, 13, 23, 24) unless the opponent is type 10, and not
a gate that 4:5b0e blocks for the opponent's stored body (4:1486).

`skeleton.opponent_path_clear` is that loop; `Skeleton.can_wake` keeps the
other conditions. The port used `stone_gate_blocks` (no desert branch) and
had no type-10 exception; skeletons (type 4) outside the desert see no
change.

`tools/probe_opponent_close.py` runs 4:13a4 with ReadCell, IsFloor/IsSpace/
IsWall/IsImpassable and 4:5b0e; only the bank lookup 6:3642 is supplied (a
zeroed record: no shake timer). Every room/row of LEVL 2000-2013, the
opponent's column -1..10 and the Prince's -2..11, reaches 4/5/8, types 4/10;
every gate with its phases, four column pairs and five bodies (sequence 68,
type 10): 222,412 cases (177,912 terrain, 44,500 gate), zero mismatches.
The former check differed in 1,428 of them (desert gates, type 10). Result
SHA256: `25c7d46dc826ced7e61913cd2d0c082a6435ed6d71c32a54d716752aed5fde1f`.

```powershell
python -m tools.probe_opponent_close --source PATH_TO_RECOVERY --output rendered/opponent-close.json
```

## MobDart 8:2f98 (cavern darts)

Crossing a column, MobDart asks IsWall and, for a gate, 4:5b0e (8:30ec-3102);
reaching row*120+5 it asks IsSpace of the row above. Both columns use DIVS
(truncation toward zero). `Darts.advance` already followed the rest; it now
truncates like DIVS and asks `gate_collides` (the same as
`stone_gate_blocks` in the caverns).

`tools/probe_mob_dart.py` runs one MobDart update with ReadCell, IsSpace,
IsWall, 4:5b0e and the neighbour words; AddSound is recorded. Every room of
the cavern levels (LEVL 2002-2004) as the view room with the dart in it or
in its left/lower neighbour, X 0..530 step 5, four heights per row, dy
-19/-3/-1; every gate with the low byte 0-252 step 9 and four bodies: 133,392
cases (110,424 terrain, 22,968 gate), zero mismatches. Before the change:
1,485 gate cases at negative X (floor division). Result SHA256:
`ff0dc79ba812cab08a71d490c281ecb3f8f4f281779c78ec45eb997053344719`.

Open: the body 4:5b0e reads is whatever character copy the mob animator
leaves in a5-0x5056; the port passes the Prince's. No shipped dart
trajectory reaches a gate cell, so the question has no gameplay effect.

```powershell
python -m tools.probe_mob_dart --source PATH_TO_RECOVERY --output rendered/mob-dart.json
```

## GetUndefineCellId 4:28b6 (cells past a missing link)

ReadCell passes its original column and row to 4:28b6 when a link is
missing; the room tests read the Kid room a5-0x4fc2:

- Rooftops (environment 5): space. Desert and caverns: wall 20.
- Ruins (4): space for the row above a Kid room without an upper link
  (a5-0x4fbc = 0, row -1), outside level six's room 27 and level nine's room
  16; else wall.
- Temple (2): space in level thirteen's rooms 4 and 13 (the chasms), else
  wall.
- Palace (6): wall beside rooms 7-8 above the floor rows (row < 3) and at
  room 3's bottom-row edges (column < 0 or 9, row 2); else space.

`LevelMap.undefined_cell` translates all of it, taking the room the lookup
started from as the Kid room. Before, only the rooftop void and the two ruins
exteriors were air. `tools/probe_cliff_void.py` now covers every level with
the room's real upper link: 19,794 undefined cells, zero mismatches (the old
rule differed in 3,082: 840 ruins top-row cells, 116 in level 13, 2,126 in
level 14). The DoKidEngarde, gate-barrier, standing-turn and Prince-turn
probes reran with their native hashes unchanged; DoKidEngarde's 30 and
EnemyCollide's 55 remaining cases now match.

Player-visible: in the ruins (levels 6-7 here) the cell above a room with no
upper link is now air instead of a wall, as natively.
