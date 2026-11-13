# Vertical jump pushed through a rear wall (2026-11-13)

The supplied12.437-second port recording shows level12 room3: climb the
upper-right platform, move against its right wall, face left and jump up.
The Prince crosses into room11. No live game/emulator was operated.

The initial fix below was incomplete: a later recording and explicit key
sequence reproduced a stuck body followed by a room cut. See the complete
input replay at the end; its regressions supersede the initial jump-only
coverage claim.

The subsequent paired Macintosh video also showed that retaining a bump
cancelled the real jump. The latest [gate-admission correction](vertical-jump-gate-admission.md)
preserves the complete jump and subsequent movement; the historical bump
expectations below are superseded by that original-backed regression.

## Reproduction and correction

A hidden real scene reproduces it from room3/row0, sceneX470, facing left,
with the original closed gate phase. The standing position is supplied;
keyboard Up, animation, collisions, floor checks and room cuts run normally.
When the vertical pose widens, the front gate's correction moves X to501.
The wall-response pose50 is now inside the rear wall; align_wall moves the
foot farther to531. The next horizontal cut enters room11, where another
wall alignment displaces him again.

For the unarmed Prince's vertical jumps (selected SEQS14/28), the port's
existing swept collision safeguard now also checks the proposed forced
translation of the PREVIOUS body against solid walls on either side.
If a wider pose cannot fit between the gate and rear wall, it still plays the
ordinary SEQS47 bump, with its displacement limited by that wall. Checking
only solid walls here avoids treating the same overlapping gate as a second
opposing constraint. Gates, rocks and scythes retain their ordinary initial
collision admission. No position clamp for a named room is introduced.

The initial broad implementation also checked other collision responses.
Full discovery exposed unwanted changes to short steps, a crawl hold and a
running skeleton's bump selection. The final guard is limited to unarmed
player vertical jumps; the existing response calculations for those other
families are restored. Their three failing regressions pass without changing
any test expectations.

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

Final verification: full discovery by243 isolated modules ran4,119 cases,
with nine desktop exclusions and one original enemy-profile reference check
unconfigured (10 skips). Its initial broad safeguard exposed the three
regressions above; that run is not reported as green. After limiting the
safeguard, all169 cases in the affected level4, ruins reports, game UI and
vertical-wall/temple replay/playtest modules passed. The other full-discovery
modules had passed, including terrain, ceiling, combat, gate and saved-state
coverage. No expectations for the three unrelated regressions were changed.

Dependency, Ruff F/E9, recovery catalogue and whitespace checks pass. The final
port audit again reports488 standing/6,344 pose fixtures and seven candidate
replays, with the six temple pinches contained. The initial focused command
also named a nonexistent test_temple_collision module; its import error is
not counted as a test pass. Full discovery covers the actual collision tests.

No executable was rebuilt, and no physical game/emulator or original native
code probe was run. Further work, if needed, should supply a specific action
outside unarmed SEQS14/28 rather than broadening the correction to every
animation family without independent regression evidence.

## Complete climb, step, turn, jump and movement replay

The user's third clip (10.86 seconds) gives the missing sequence: begin below
the right-hand upper ledge beside the gate, climb, take a short right step
with Shift, turn left, jump vertically, then walk left. This reproduces on
the current port; no stale executable or alternate workspace is assumed.

A hidden scene supplies only the supported lower start, native room3/row1,
X434 facing right. Both gates retain their original closed foreground0.
Up+Shift for30 ticks and5 released ticks runs the actual ascent16->10 and
settles at X444, row0, clearing the ledge flags. Shift+Right3 ticks, release12,
Left1 and release10 settles at X453 facing left. Up3 and release20 reproduces
the faulty jump. The following Left input cuts to room11 immediately.

The first safeguard did run. At vertical pose73, the front gate proposes
X488; the preceding body's solid-wall sweep limits it to455. But selecting
the ordinary bump47 immediately executes its first pose50, whose backward
displacement adds another16, leaving X471. On the subsequent left input,
another collision/bump moves to499, CheckFloor's align_wall carries the foot
to531 and the room cut follows. Checking only the first displacement missed
the response sequence's own movement.

The safeguard now also caps the **complete response** against the same
previous body and solid walls, after sequence selection and the response
pose's secondary collision. Bounds are refreshed before CheckGate/CheckFloor
and room-cut logic consume them. In this replay the bump ends at455; Left
then moves normally to451,447,438,428 while remaining on room3's top ledge.
Walking farther left can still leave the real ledge and fall normally.
The restriction remains unarmed Prince SEQS14/28; short steps, crawling and
NPC collision families are not included. This is a host safeguard (A), with
no new native CPU or full collision-buffer equivalence claim.

`tests.test_vertical_jump_walls` now includes the complete lower-start replay
and the step/turn/jump/follow-up at all six known pinches. It checks that the
supporting foot stays outside solid cells, remains on the original room/row
and actually moves left after recovery. The mirrored synthetic case now
executes the16-pixel response displacement too. Replacing only advance with
the pre-change method yields seven failures across the two new scene tests;
the updated implementation passes. Those negative-control failures are
intentional evidence, not successful tests of the old code.

The original 488-position/6,344-pose audit was also rerun: seven candidates,
with the six temple pinches contained. Its supplied placements and exclusions
remain unchanged; it is not a full campaign/input-state search. Actual full
climb input is replayed in room3, while the other five sites supply a supported
upper-platform start before the step and turn.

A before/after offscreen render of that complete replay confirms room11 after
Left with the old method and room3 with the new one. At the pressed position,
the front column still covers much of the idle sprite. The fix restores
immediate movement out of that position; native pixel/occlusion parity at
the column has not been established and is not claimed here.

A lower-start sweep X428..440 gave eight completed ascents (X433..440), all
settling at444 and passing the complete step/turn/jump/Left replay. The other
five supplied starts did not ascend and are not counted as successful route
checks. Ten consecutive vertical jumps at the pre-jump position followed by
Left also remain in room3. These are bounded port experiments, not exhaustive
timing, gate-phase, saved-campaign or opponent scheduling coverage.

Final checks: full discovery run as246 isolated modules exercised4,132 cases,
with10 explicit skips (nine exclusive-desktop cases and one original enemy-AI
reference without its research configuration). All functional modules passed.
The frame-cost check initially failed during parallel load at level6
(median44.9ms, budget41.7ms); its unchanged assertion passed alone afterwards
(level6 median11.5ms). The raw parallel run is not described as entirely green.
Audio and other performance modules ran serially after the worker pool.
An earlier single-process discovery and a duplicate focused run were stopped
before completion; neither is counted as a completed pass. The five final
wall tests, including the strengthened mirrored displacement, passed too.

Dependency, Ruff F/E9, recovery-catalogue and whitespace checks passed. No
original resources, user saves/settings, executable build or live desktop
input was involved.
