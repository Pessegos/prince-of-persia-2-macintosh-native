# A slamming gate pushed the runner back and blocked room 3

The user's level-12 room-3 port recording shows the Prince climbing onto the
middle platform, running right onto the closing plate, then being thrown back
to the left of the gate. The gate shuts and the route becomes blocked.

Follow-up: the SEQS 1 correction below did not cover a short tap's stopping
sequence. [Passage history](gate-passage-history.md) supersedes that limited
scope and checks the shared ruins/temple gate path, preserving cold recovery.

## Reproduction and correction

Supply a supported start at port room 2, row 1, X444, facing right, with gate
cell 18 fully raised at foreground 184. Use Shift+Down to descend, then Up
to climb back. The Prince finishes at X445. Run right through the open gate.
At X502, pose 8, the real plate in cell 19 triggers the gate's fast closure.
On the following update it reaches foreground 124 while pose 9 advances to
X516. The old generic overlap recovery pulls him back to X447 and selects
bump sequence 47. Subsequent frames leave him behind the closed gate.

At that moment, the previous body's horizontal bounds are 461..512 and the
new bounds are 477..522. The gate's type-1 front plane is X470. Both poses
already extend across that plane: this is not a fresh front crossing.

The temple's unarmed Prince's ordinary run (selected SEQS 1) now uses actual
edge crossing for gate-side collisions, as the existing cavern-gate and
vertical-jump paths do.
A closing gate behind his trailing arm cannot create a new front bump.
The corrected run stays at X516/pose 9, crosses the real right room link to
port room 10 (native room 11), and leaves the closed gate behind him.
The plate and gate retain their original activation and closing timing.

Real front crossings still block in both directions. Solid-wall recovery,
ruins and other-sequence overlap recovery, armed/NPC rules, gate contact/crouching,
crushing, and the approved drawing/ledge improvements are retained.
No asset, animation, input, save or settings changes are required.

## Original evidence

CheckBarr `CODE 4:4f7c-4fb4` compares the current and preceding side bits;
CheckCollide1 `4:54da` (including the facing checks at `551a`/`5586`)
does not turn an unarmed rear overlap into a front collision. This rule
is not specific to the jump sequences corrected in the earlier report.

`tools.probe_temple_gate_passage` executes original LoadFrame `4:2a72`,
SetupSword `3:0ac8`, GetCharEdges `4:5cbc`, warm CheckBarr `4:4e34` and
CheckCollide1 `4:54da`. It uses actual Kid FRAM/AFRM/SHAP headers and the
original level-12 room-3 gate/header. Nine standing/running snapshots follow
the real rightward port replay; reflected snapshots supply the other facing.
The last snapshot changes the supplied gate foreground from 184 to each of
0/24/60/124/180/184 while retaining warm collision banks.

There are 108 native snapshots and 96 port comparisons, with zero differences.
Two additional front-crossing controls (four native samples) still request
Collide with the displacement independently produced by the port's gate plane.
The probe verifies the retained frame resources and level bytes and records
input/output hashes in its ignored report.

The actor poses, X positions, live foreground snapshots, room globals and
empty MOB/zero float state are supplied. Shape sizes come from original SHAP
headers; SectRect uses supplied arithmetic and Collide is a recorded no-op.
Native running/plate controllers, contact/crushing, response animation,
nonempty rocks, physical support, pixels and complete FrameAdv are outside
this CPU comparison. The real port replay separately covers the complete
descent/climb/run/plate/slam/room-cut interaction.

## Regression and handoff

`tests.test_temple_gate_passage` checks both-facing overlap and genuine front
crossing, then the complete hidden scene reproduction. Restoring the previous
tile correction fails three cases/subcases without errors, including the
actual route. The old vertical-jump test's expectation of ordinary temple
overlap recovery was inconsistent with this original running evidence: it
now asserts no false front collision for temple running and preserves its
old positive recovery assertion under the separate ruins environment.

The first full-suite run exposed a separate dependence in the level-12 genie
route: SEQS 43 after a catch in room 24 still relies on the port's existing
overlap recovery. A broad change for every unarmed sequence let it cross a
closed gate after the room/grip transition and fall. The original baseline
passes that route. The fix is therefore bounded to the established ordinary
run SEQS 1, alongside the already-approved jump cases; it preserves that
catch recovery. The native probe does not establish bank initialization or
contact recovery across such a room/grip transition.

```powershell
$env:POP2_SHARED_DESKTOP = '1'
.venv\Scripts\python.exe -m unittest -q tests.test_temple_gate_passage tests.test_vertical_jump_walls tests.test_terrain tests.test_stone_gates tests.test_gate_clearance tests.test_temple_playtest
.venv\Scripts\python.exe -m tools.probe_temple_gate_passage --source ..\PoP2-Mac-Code-Recovery --output rendered\room3-gate-block\native.json
```

The final whole shared-desktop run completed in isolated interpreters to
bound cached scene/artwork memory: 250 modules, 4,173 cases, ten explicit
skips, zero failures (455 seconds). Audio and frame-cost modules ran serially.
The skips are nine exclusive-desktop cases and one unavailable native enemy
profile. The earlier broad implementation's full run had the genie-route
failure described above; it is not counted as a passing run. The final focused
passage/jump/route group also passes all 15 tests, without skips. Dependency,
Ruff (`F,E9`), recovery-catalogue and whitespace checks pass.
No live game window, user data or original resources were modified.

This establishes the reported room-3 passage, not an entrance-to-exit audit
or complete equivalence of every moving-gate/actor interaction.
