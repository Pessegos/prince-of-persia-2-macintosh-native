# Vertical jump falsely becomes a gate bump (2026-11-13)

The user's paired Macintosh/port recordings confirm that the previous
rear-wall safeguard prevented teleportation but retained a false collision:
the unarmed vertical jump became SEQS47 at pose73. The Macintosh continues
the jump. This supersedes the earlier expectation that a bump was the desired
response at the six temple pinches.

## Cause and bounded correction

CheckBarr4:4f7c-4fb4 first requires matching current/history room tags, then
raises each side candidate only when its low/high overlap nibble changes
from zero to nonzero. CheckCollide1 at 4:54da additionally rejects an unarmed
actor's rear side, with no retry of the other candidate. These are collision
admission rules, before the existing Collide response.

In the supplied room3 replay, X453/facing left, pose72 has sprite edges446..481
and pose73 has445..483. The gate's back boundary is480. Both old and new
left edges already overlap that boundary: there is no new front contact.
The port's ordinary overlap-recovery sweep nevertheless treated the widening
as a crossing and proposed X488. Its emergency wall cap then selected the
bump and ended the jump. Limiting the resulting shove could prevent the
teleport but could not restore the intended animation.

For the unarmed Prince's selected SEQS14/28, temple/ruins gates now use the
same actual-edge crossing admission already used for cavern gates. Widening
under an already-overlapped gate does not create a new collision. A genuine
new crossing still does. Other animation families keep their existing port
overlap-recovery safeguard. Full walls, opponents, gate crushing, collision
capacity and the earlier complete-response rear-wall cap are unchanged.
This is a bounded application of the recovered edge-history rule, not an
integration of the entire native collision-bank scheduler.

The original SEQS14 includes the thirteen-pixel backward move at pose78.
That move and the landing's three-pixel adjustment are expected behavior,
not a room clip. In the actual lower-start replay the pre-jump X453 remains
unchanged through pose77, becomes440 at78 and finishes at437. Subsequent Left
moves to433,429,420,410 in room3; walking farther can leave the real ledge.
The whole jump, including the native top bound at row*120-18, now plays.

## Original-executable check

```powershell
.venv\Scripts\python.exe -m tools.probe_vertical_jump_gate_contact --source ..\PoP2-Mac-Code-Recovery --output rendered\native-vertical-gate-contact.json
.venv\Scripts\python.exe -m unittest -q tests.test_vertical_jump_walls tests.test_temple_collision_decision_reference tests.test_temple_collision_banks_reference tests.test_temple_sprite_bounds_reference
```

The new probe composes original LoadFrame4:2a72, SetupSword3:0ac8,
GetCharEdges4:5cbc, CheckBarr4:4e34 and CheckCollide1 at 4:54da. It uses original
Kid FRAM/AFRM and SHAP header dimensions, with a warm initial standing sample
followed by supplied jump poses67..79 and the original SEQS14 X movement.
It verifies the original sequence prefix and each temple level/environment
header; native facing-1 is the port's facing0/left. The original left-facing
GetCharEdges width+1 is converted to inclusive sprite edges for the port
comparison; no port image decoder supplies the reference geometry.

Across the six actual temple positions and six frozen gate phases
(0,24,60,124,180,184), 504 native samples request no Collide response. All468
post-primer port comparisons retain the supplied X, with zero mismatches.
Two additional native samples and one port comparison form a positive control:
a supplied nine-pixel front approach to the closed gate still requests
Collide(+2,side0). That control clears the rear wall in a synthetic level copy,
not in any original resource file. Frames, level bytes and empty MOB memory
remain unchanged by the jump fixtures.

Supplied boundaries and exclusions:

- Actor pose/X/Y/mode, room slots, frozen phases and initial empty history
  are fixtures. Poses/X are checked against SEQS14, but its AnimChar controller
  and outer FrameAdv are not executed by this probe.
- Shape-size services return preserved SHAP header dimensions; resource
  loading/decompression and pixel rasterization are not executed. SectRect
  is supplied rectangle arithmetic.
- Collide is recorded as a no-op. Its bump/ground response is covered by
  separate existing probes and the real port scene regressions.
- Float timer0 and an empty MOB bank exclude floating-ceiling and nonempty
  rock behavior. The bank/history/three sweeps, gate admission, ReadCell and
  empty-rock queries execute as original instructions.
- No native pixel, arbitrary gate-height, full campaign reachability,
  moving-gate or complete collision-scheduler equivalence is claimed.

With the pre-change tile sweep substituted, the original/port comparison
fails at level10 room9 pose73, and the real room3 regression fails with
68,69,70,71,72,50 instead of the complete jump. These intentional negative
controls reject the previous fix's cancellation.

## Regression expectations

`tests.test_vertical_jump_walls` now requires poses68..79 in order, the native
jump apex, unchanged X before the sequence's own step, and subsequent Left
movement without a room cut. The actual room3 lower climb and all six upper
pinches are retained. The older twelve-pixel movement limit and required
pose50 were incorrect: they rejected SEQS14's own thirteen-pixel move and
codified the cancellation reported by the user. They were replaced by these
stronger original-backed assertions.

The old synthetic opposed-barrier fixture also already overlapped the gate,
so it is now a no-new-contact regression for both facings and SEQS14/28.
The mirrored bump-safety test instead supplies a genuine new front-edge
crossing, still executes SEQS47's16-pixel displacement and requires the
opposing wall to contain it. Ordinary non-jump overlap recovery and the
open-gate jump control remain covered. The36 focused tests above pass.

Before/after offscreen renders confirm that the completed jump emerges at437
and subsequent Left stays in room3. No live game or emulator, original file
writes, user saves/settings, publication or executable build was used.

Final validation: full discovery by246 isolated modules ran4,133 tests with
zero failures and10 explicit skips (nine exclusive-desktop tests and one
original enemy-profile reference without its research configuration). Audio,
frame-cost and other performance checks ran serially after the worker pool.
The36 focused collision/bounds/scene tests also passed. Dependency, Ruff F/E9,
recovery-catalogue and whitespace checks passed. Native probe output includes
executable/Kid/Prince SHA256 values; recordings and generated reports remain
local and ignored.
