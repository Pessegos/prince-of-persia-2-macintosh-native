# Temple sliding rocks in CheckBarr

A sliding rock is a barrier by two routes. Its crush reaction (10:16f6, 10:1b04)
acts on the rock's side of the frame. This note covers the other route: the
faces the rock adds to the Kid's own collision banks, which were the last gap in
[the temple's wall collision](temple-implementation-plan.md).

## The rule

CheckBarr 4:4e34 asks three things of a level with the rock flag (byte 0x2191):

- **4:4e6e-4e86.** With a rock on the actor's room and row
  (GetSlideRockOnRoomRow 10:1a9e, the first live type-6 record) and sequence
  mode 4, the actor gets no banks at all. This is the crushed Kid of 10:1c04.
- **4:4fce-5096.** Animation state 7 skips the sweeps and the contact scan, but
  with that rock it still rebuilds history and adds the rock.
- **4:4f18-4f62.** After the sweeps, GetSlideRockDetData 10:190c runs for the
  current, lower and upper rows, in that order.

GetSlideRockDetData works with the two faces in native X:

| Face | X | Condition | Bits set in that column |
| --- | --- | --- | --- |
| Left | rock X + 218 | face < body right | low nibble |
| Right | rock X + 279 | face > body left | high nibble |

The column's tag becomes the rock's room, so the contact scan treats a rock
column as it treats a wall. Only the actor's room counts: a rock in a linked
room is no barrier until 10:1d5c moves its record across.

A travelling rock would report a false contact each time a face entered a new
column. So when a face's column differs from the column 2 pixels to its right,
and the rock's control is not 100 and it is on the actor's row, the old
column's history bits move to the new column. If the old column has no current
bit left, its history bit is cleared.

CheckCollide1 4:54da then treats the column as usual: states 2 and 6 and poses
135-144 decide nothing, the left face decides before the right, and unarmed the
side behind the body is free. CheckCollide 4:5654 reads the cell under the face
and can still admit the body (tile 10, an open crevice, an open gate, a
retracted scythe). A barrier in that cell gives the edge. Otherwise
GetSlideRockBarrDist 10:180e gives the rock's face, the left one raised to a
wall or gate cell's boundary one column behind it.

Collide 4:5738 needs no new rule. Its bump and the disarm beside a rock were
already ported.

## The port

The port has no persistent banks, so it does not store the masks. `wall_correction`
compares body edges between frames instead, which gives the same answer because
a contact is exactly a body edge newly past a face:

- `SlideRocks.contact` finds the crossing. Last frame's faces lay 2 pixels to
  the right unless the rock's control is 0 or 100.
- `LevelMap.rock_correction` applies the state, pose, facing and cell rules.
- `wall_correction` combines the result with the tile correction: the left
  faces decide before the right, and within a side the smallest column wins.

## Evidence

`tools/probe_temple_rock_overlay.py` runs original CheckBarr and CheckCollide1
for two connected frames from cold banks at all 12 tile-25 cells, with a real
record in the MOB bank. GetSlideRockOnRoomRow, GetSlideRockDetData,
GetSlideRockBarrDist, the three sweeps, history and the contact scan execute
natively. The working actor, body edges and height, MOB records and each frame's
rock X are supplied. Collide 4:5738 is a recorded no-op boundary, and float
timer 0 excludes 4:50da.

With `--x-step 120 --offset-step 18`: 11,344 two-frame traces plus 198 row and
mode controls, 0 mismatches. The second frames gave 274 left-face and 180
right-face responses. A further 944 traces left the bank domain (see
Exclusions) and are not comparisons. Executable SHA256
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`,
compared-output SHA256
`b73e46cf922967e86a56722988717f8b943581ef01e6e658309ccf7c274982f2`.

`tools/audit_temple_rock_collision.py` then compares those native-checked
references with production `wall_correction` in pure Python, over rock positions,
control 2 and 100, seven steps, 16 offsets around each face, both facings, armed
and unarmed. With a 13-pixel rock step:

- 180,792 clean starts: 0 differences.
- 255,040 overlapping starts: 71,769 differences. These start inside a barrier
  (usually the rock's own tile-25 home cell), where the native finds no new
  contact and the port's deliberate inward-stop recovery still acts. This is
  the existing exception from `tools/audit_temple_collision.py`, not a rock
  rule.

`tests/test_slide_rocks.py` covers the faces, the free side, room and row
scoping, dead rocks, skipped states, the column priority and a random walk
against the references (asset-free).

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_rock_overlay --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_rock_overlay_v1.json --x-step 120 --offset-step 18
.venv\Scripts\python.exe -m tools.audit_temple_rock_collision --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_rock_audit.json --x-step 13
.venv\Scripts\python.exe -m unittest -q tests.test_slide_rocks
```

## Exclusions

- Opponents. The port's opponents skip `wall_correction` in `RooftopPhysics`, so
  a rock is no barrier to them. The native gives them the same banks through
  EnemyCollide, which is unrecovered for rocks.
- History across a row change is not modelled separately. The port compares
  the same body edges against the current row's rock.
- Faces near the room's edges: GetSlideRockDetData's history transfer runs
  without a range check, so column -1 writes the body-height word and column 10
  writes the first current mask. The probe counts these apart and the port does
  not reproduce them.
- No full FrameAdv or Collide response is run with a rock in these traces.

## Cross-room following of running opponents

The older notes list this as open. Reading it again, nothing is left to port.

- FrameAdv 2:6550-65da is translated by `CombatEncounter._physics_admitted`.
- A native opponent has no horizontal Cut. CutOpponent 6:424c acts only at
  Y >= 730, and a runner past the X window stops moving while it stays in its
  bank. CutAllOpponents 6:4476-4626 carries it when the Kid changes room.
- `opponent_follows_cut` carries the same running poses (186-201 with a nonzero
  movement flag, 202-212 with flag 1) for actor types 2 and 4. The temple's
  birdheads are type 2. `tests/test_guard_rooms.py` and `tests/test_skeletons.py`
  cover the rule.

The port moves an opponent past the room edge into the neighbour's list, but
`bank_room` keeps it active, so the difference is bookkeeping. No native
multi-room chase has been run, so this is a static reading, not an equivalence
claim.
