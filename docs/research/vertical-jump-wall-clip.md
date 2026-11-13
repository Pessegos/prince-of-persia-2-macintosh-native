# Vertical jump pushed through a rear wall (2026-11-13)

The supplied12.437-second port recording shows level12 room3: climb the
upper-right platform, move against its right wall, face left and jump up.
The Prince crosses into room11. No live game/emulator was operated.

## Reproduction and correction

A hidden real scene reproduces it from room3/row0, sceneX470, facing left,
with the original closed gate phase. The standing position is supplied;
keyboard Up, animation, collisions, floor checks and room cuts run normally.
When the vertical pose widens, the front gate's correction moves X to501.
The wall-response pose50 is now inside the rear wall; align_wall moves the
foot farther to531. The next horizontal cut enters room11, where another
wall alignment displaces him again.

The port's existing swept collision safeguard now also checks the proposed
forced translation of the PREVIOUS body against solid walls on either side.
If a wider pose cannot fit between the gate and rear wall, it still plays the
ordinary SEQS47 bump, with its displacement limited by that wall. Checking
only solid walls here avoids treating the same overlapping gate as a second
opposing constraint. Gates, rocks and scythes retain their ordinary initial
collision admission. No position clamp for a named room is introduced.

This is a deliberate host collision safeguard (A), not a recovered native
rule or a claim that the complete original Collide/Catch scheduler was run.
The native response sequence already used by the port is retained. There is
no supplied Macintosh recording of this particular action and no new CPU
probe. Prior native evidence for barrier masks and responses remains bounded
as described in COLLISION_RECOVERY.md.

## Other locations

The same pre-fix teleport/solid-wall traversal reproduced at these supplied
wall-adjacent positions, with initial level mechanism phases:

| Level | Native room | Row | Scene X | Pre-fix rooms reached |
| --- | --- | --- | --- | --- |
| 10 | 9 | top | 368 | 9,13 |
| 10 | 9 | bottom | 368 | 9,13 |
| 12 | 3 | top | 470 | 3,11 |
| 12 | 16 | middle | 470 | 16,15 |
| 12 | 17 | top | 368 | 17,16,6 |
| 12 | 17 | middle | 368 | 17,16,6 |

`tools.audit_vertical_jump_walls` examines levels1-14, all32 stored room slots,
three rows and both wall sides. It supplies supported idle placements touching
a wall and tests the13 vertical pose shapes at standingY. This is an envelope
of possible collision geometry, not proof of campaign reachability.

The488 standing fixtures/6,344 pose fixtures produce seven candidates. Each
candidate is replayed with real Up input in a fresh peaceful hidden scene.
The six temple positions above invoke the safeguard and stay in their room.
The level8 room17 middle-row candidate never invokes it in the actual jump:
its substantial normal movement is unchanged before/after, so it is not
reported as another confirmed wall clip. Moving gates, all intermediate
positions and other animation families are not exhaustively searched.

## Checks

`tests.test_vertical_jump_walls` rejects the old behavior at all six actual
temple positions, checks that an open gate still allows the jump, and tests
opposed gate/wall collisions in both directions without imported assets.
The latter supplies the response pose only; collision, floor and cut logic
run normally. The actual-level cases supply the initial standing placement;
climbing to it and the preceding wall/turn keys are not replayed.

```powershell
.venv\Scripts\python.exe -m tools.audit_vertical_jump_walls --output rendered\vertical-jump-audit.json
.venv\Scripts\python.exe -m unittest -q tests.test_vertical_jump_walls
```

The audit creates a temporary user-data directory before importing game paths.
Videos, reviewed contact sheets and JSON reports stay ignored locally.
