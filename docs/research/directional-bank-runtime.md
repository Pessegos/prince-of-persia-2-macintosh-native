# Directional-bank runtime migration

The input research is now used by a production `DirectionalInput` bank in
`pop2/mac_input.py`. The first stage replaces deferred input during
standing turns and cautious steps, including the ordinary ready gate at their
end. The second stage extends ownership through grounded running; the third
carries the same bank through ordinary/running jumps3/4 and grounded return.
The fourth extends it through vertical14/28 and landing11, described in
[vertical input handoff](vertical-input-handoff.md).
This does **not** replace input across every controller yet.

## Ownership

`pop2/waiting_controls.py` owns those pending directions. Left, Right, Up and
Down are separate latches. Horizontal latches stay in keyboard coordinates;
vertical keys retain the host's existing upside-down mapping before sampling.
The migrated driver does not apply that inversion a second time. Shift/Ctrl are sampled
with the recovered modifier normalization. Facing is applied when choosing
an action, rather than stored as a permanent turn/run/jump classification in
the key callback. Released pending taps persist; consumed holds clear on
release. No pending-input expiry was added.

| Context | Current owner |
| --- | --- |
| Standing turn entered through the scene, cautious step, their subsequent ordinary ready/idle gate | Production directional bank |
| Run start 1, cycles 200/201/202, drift 6, running turn 43 and brake 13 | Production directional bank through `RunningControls` |
| Ordinary forward jump3, running jump4 and their grounded return | Same production bank through `AirborneControls` |
| Vertical jump14/28, landing11 and the early67-69 Forward gate | Same production bank through `AirborneControls` |
| Other airborne, low/prone, ledge and armed controllers | Existing host policies, pending later migrations |
| Host pause/focus/menu/restart boundaries | Existing held-key rules and explicit reset |

While the bank owns input, physical callbacks and internal directional
buffer producers write it directly. They do not also enqueue an executable
`BufferedCommand`. Old scripted/test requests can be imported once at the
ready boundary and removed from the legacy slot. The legacy turn/stop ready
dispatchers are bypassed while this owner is active.

Entering another controller family retires the bank. Physics/combat can
select sequences directly, so retirement also runs after world phases and
on fall/wall/gate/death events. A pending vertical wall-climb request can
cross a grounded wall interruption into the existing host climb policy.
Focus/modal clearing drops both representations. Sequence 43 is a running
turn, not a cautious step despite lying between step resource IDs.
After selecting a non-idle sequence, the controller waits for its first pose
to load. JumpSeq resets the cursor while leaving the old displayed action
in place; consulting that old ready pose again could otherwise replace a
new step with a run before it had even started. A regression rejects that
double dispatch, including repeated controller calls at cursor zero.
The existing initial forward-chord window remains an explicit exception:
fresh Up can combine with the arrow that just selected an automatic
near-wall step, before its first pose. It cannot turn a plain Shift release
into another run. The real-terrain wall-bump regression checks that this
chord starts once and cannot replay after collision.

This is an explicit family boundary, not proof of native bank continuity
through the still-unmigrated families. That continuity and their consumption
sites remain part of the next stages. In particular, this change does not
claim the native pending B/D lifecycle during an entire forward-jump arc.

## Action choice and deliberate host policies

Standing/turn selection follows the recovered priorities at pose 15,
50-52 and the pose-48 run continuation. The sampler distinguishes pending
(-1), inactive (0) and consumed (+1), rather than using a last-command slot.
Turn clears directions and consumes Backward; step consumes Forward and
modifier without clearing unrelated pending directions. Existing terrain
and action functions still perform the movement and animation.

The original Up dispatch at 6:0e7a tests active Forward before choosing
forward jump versus DoJumpUp. DoJumpUp clears directions and consumes Up at
6:1608-160c; ordinary Down/crouch entry and horizontal action effects reuse
the earlier action/low-input recovery. Special terrain admission and full
FrameAdv ordering are not newly certified by this migration.

Existing host choices remain explicit:

- Held Shift steps repeat after the preceding step finishes.
- The existing rapid-step repeat filter remains; it does not expire pending
  directions or replace a different pending request.
- The 35ms resting chord window remains.
- An opposite jump chord turns once; its continuously held Up does not create
  another jump after that turn. Release permits a new chord.
- A fulfilled command at the existing ready/idle presentation seam can act
  before drawing an intermediate idle frame.

These policies are scene regressions, not claimed Macintosh bank rules.
Armed repeat tolerance, pause/retry holds and wall-climb behavior remain
outside the new standing sampler's native-parity claim.

## Observable differences and tests

Up and Down taps during a step now both remain pending, regardless of their
arrival order. The ready controller chooses Up before Down. The later Down
tap no longer replaces Up simply because it arrived last.
An isolated before/after execution of the checked pre-migration scene confirms
the visible difference in both facings: Up then Down selected crouch 50/107,
while Down then Up selected vertical jump 28/67. Both orders now select 28/67.
This is a demonstrated port difference, not an inference from queue metadata.

A consumed Forward that is released during a step/turn becomes zero. A
pending Up can therefore produce a vertical jump at the ready gate, instead
of using the horizontal direction captured earlier in a queued command.
Conversely, a newly pressed Forward remains pending after release and can
still combine with Up for the forward jump. Modifier changes are also read
at the accepting gate. Former animation tests that asserted an immutable
queued chord now assert the bank and these resulting poses; the native
sampler and standing/Up-dispatch rules explain the changed expectations.

`tests/test_directional_input.py` checks production sampling and ready routing
against the independent research models. `tests/test_waiting_controls.py`
checks scene-level conflicting inputs, live modifiers, internal producers,
clearing, physics bypasses and first-pose admission.
Existing animation/input, terrain, potion and window-control tests check the
surrounding behavior. Asset-free CI runs the production-bank matrices; local
asset-backed suites exercise the actual scenes.

`tools/probe_waiting_controls.py` additionally compares production functions
directly with the original instructions:

| Comparison | Matching cases |
| --- | ---: |
| Sample all 405 banks against all 27 raw combinations | 10,935 |
| Direction clearing | 405 |
| Facing/inversion remapping | 1,620 |
| Standing/turn selection, modes and sword availability | 29,160 |
| Up's forward/vertical choice with non-exit cells | 405 |
| DoJumpUp's consumption prefix before terrain lookup | 405 |
| **Total** | **42,930** |

There are zero mismatches. Action/geometry bodies remain supplied sinks in
the routing matrix, exactly as in `probe_input_routes`; this does not prove
full scene/animation/FrameAdv behavior or the host repeat policies.
The separate Up comparison executes 6:0e36-0e8c with non-exit cells, then
checks the actual 6:1600-1610 prefix stopping before geometry at 4:3ff8.
It confirms the branch and bank consumption behind the changed jump tests,
without claiming the remaining ledge/vertical-jump admission is recovered.

```powershell
.venv\Scripts\python.exe -m tools.probe_waiting_controls --source ..\PoP2-Mac-Code-Recovery --output rendered\native-waiting-controls.json
```

Output digest: `454233e270a2c64ebb433ca109198547c8d0f7d9b1c826b327f614c0db75d28a`.
Executable digest: `ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.

## Second stage: grounded running

`pop2/running_controls.py` extends the same bank through the run family.
The old grounded reversal, jump, crouch and stop dispatchers are removed
from the frame path. Two compatibility methods used by scene tests delegate
to the bank; they contain no independent queue logic. Physical callbacks
sample directions and the simulation gate chooses the action. Scripted
legacy requests can be imported once, as in the first stage.

`running_input_request` follows native GenCtrl 6:15b6-15e8 and 11e4-1274:

- Startup poses 1-3 need fresh Forward and fresh Up for the forward jump.
- Run poses 4-14 choose braking first when both horizontal latches are zero
  at pose 7/11, then active Backward, then fresh Up, then fresh Down.
  Active but consumed Up also blocks the Down branch.
- Common run exit consumes fresh Forward. Braking, reversal and crouching
  clear directions and mark their respective latch consumed.
- Drift poses 53-65 retain pending directions until an accepting pose.
  Remapping uses the current facing, including the drift's direction flip.

DoRunJump (6:1c14) still checks pose 7-14 and the existing geometry admission.
Rejecting a jump preserves pending Up. In this second stage an accepted jump
retired the grounded bank on entry to sequence4 and grounded return seeded
it again. The third stage below replaces that boundary with continuous bank
ownership and native takeoff consumption.

Existing host tolerances remain explicit and tested:

- The initial pose-1 forward chord window, and the opposite startup chord
  which turns from the original start position.
- Releasing the horizontal half of a chord, or requesting Up after release,
  can brake before the existing vertical wall alignment/climb. This is a
  bank Up plus a vertical-followup flag, not another executable command slot.
- A continuously held jump key can repeat after landing; releasing that
  automatic repeat cancels it. A genuine new Up tap remains pending when
  geometry rejects takeoff, even after release.
- Ctrl does not interrupt running or skip braking. Its released request
  cannot become a later sword draw. A fresh Ctrl also retains the existing
  cancellation of a pending potion pickup, including while the bank owns
  a run/brake. No stop-and-draw QoL was restored.

The previous test that braked at a synthetic cycle-end pose 14 now checks
that it waits until 7/11, matching the recovered native gate. Tests formerly
inspecting a queued command now inspect the bank for migrated contexts;
their full movement, facing, wall-climb and animation expectations remain.
The test exposing the prior startup-frame guard remains in place.

A before/after execution against the checked pre-migration scene also
confirms a visible priority difference in both facings. During a drift,
released Up then Down taps used to enter crouch 26/107, while the reverse
order entered running jump 4/34. Both orders now enter 4/34. Both directions
remain pending until the accepting gate chooses Up first; Down no longer
replaces it merely by arriving later. This is an observed scene result,
not an inference from different queue metadata.

`tests/test_running_controls.py` compares production routing with the
independent research model and exercises actual scene dispatch/rejection.
`tools/probe_running_controls.py` additionally executes original GenCtrl
against the production selector: 10,935 ordinary/startup/drift cases and
2,025 protected-clear cases, all matching. Action and geometry calls are
supplied sinks in that routing matrix. Earlier native action/traces probes
remain the evidence for action-body consumption; this tool does not claim
animation/physics/FrameAdv parity or native equivalence for host tolerances.

```powershell
.venv\Scripts\python.exe -m tools.probe_running_controls --source ..\PoP2-Mac-Code-Recovery --output rendered\native-running-controls.json
```

Output digest: `226500f57e6f0add94a1498100e5e89a9a3acc2e53add05b7e8f605fba4a7470`.
Original executable digest is unchanged. The remaining controller migrations,
ordinary vertical/pickup admission and full update ordering remain separate
work; do not restart the already completed bank/action audits.

## Third stage: ordinary and running jump arcs

`pop2/airborne_controls.py` keeps the existing bank alive through SEQS3/4.
Takeoff follows the already recovered action bodies: forward jump6:15ea
consumes Forward/Up while preserving other directions and the modifier;
accepted running jump6:1c14 clears directions and consumes Up. A rejected
running jump still leaves pending Up intact. These are the same operations
as the independent [action model](input-action-consumption.md), not a new
recovery of those routines.

Airborne physical callbacks sample the bank without dispatching. At the
simulation boundary GenCtrl6:074a-0760 clears its four directional latches
at displayed poses26/44, preserving the modifier. That clear does not run
on every event callback, nor against a just-selected arc's previous displayed
pose. The grounded selector receives this same bank after the SEQS link.
The old SEQS3 directional pending-slot reset and running-jump slot/reset
flag are removed. Scripted directional requests entering an owned arc are
imported once; callbacks do not also populate `pending_action`.

The [handoff diagnostic](airborne-handoff-audit.md) now has zero host priority
differences in its eight actual platform cases. Early released taps still
clear at26. Late Up/Down taps now choose Up in both orders and facings.
When Forward stays held after an ordinary jump and Up is released, the
grounded gate can select Run directly instead of displaying a transient idle
frame. The prior animation test waited forever for that idle; it now checks
the full16..33 arc and immediate Run1 with a bounded loop. This follows
the existing sampler and ready-gate rules, not an added landing shortcut.

Preserved port policies are explicit:

- Automatic held-jump repetition can be cancelled by releasing Up. A fresh
  late tap remains distinct from that automatic repeat.
- Releasing horizontal while Up remains held can request vertical wall
  alignment/climb. A policy flag accompanies the same Up latch; it is not
  a second executable directional queue. Physics snapshots that intent
  before retiring the bank on a wall/fall interruption.
- Rapid identical-jump filtering and the startup chord windows remain.
- Upside-down physical key mapping occurs once before the bank. Ctrl does
  not interrupt the arc or brake, and released Ctrl cannot draw later.
- Pause preserves ordinary held-key semantics; menu/focus/restart clears
  discard the bank and followup flags. Fall/death/ledge/armed interruptions
  retire ownership rather than replaying the interrupted takeoff.

`tests/test_airborne_controls.py` rejects the old priority/slot behavior on
real scenery and checks takeoff consumption, modifier-preserving resets,
inverted late taps, automatic-repeat cancellation and modal reset. Existing
animation/input/wall-climb tests now inspect bank metadata in migrated arcs;
their movement/pose/facing and successful-climb expectations remain, except
for the direct grounded Run described above. Vertical jump28/14 was outside
this third stage; the fourth stage linked above now migrates it. Wall recovery,
low/prone, ledge and armed controllers remain separate.

### Stage validation

- The six new airborne tests plus the existing running/input/animation tests:
  173 tests passed. The actual wall-climb tests passed in both facings and
  with horizontal release during pause.
- Full discovery with `POP2_SHARED_DESKTOP=1`: 3,236 tests in540.382s,
  ten explicit skips and one old assertion expecting `pending_action` in
  the inverted-jump regression. Its fixture was updated to supply a real
  takeoff key/release before the fresh press and compare the directional
  banks instead. All nine playtest regressions then passed in2.696s.
  Production code did not change during/after that full run; no second full
  import was needed for the fixture-only correction. The full run's sole
  failure is recorded here rather than reported as a green discovery run.
- Ruff F/E9, dependency check, recovery catalog and whitespace checks pass.
  The native/host handoff diagnostic retains the exclusions recorded above.

The obsolete running-jump-clear flag remains accepted by the version-one save
decoder for compatibility only. It is no longer produced/read by the runtime.
Current progress saves reset input on load rather than persisting a live bank;
the format and entry/checkpoint semantics are unchanged. No original assets
were modified, no live game/emulator was operated, and the physical-focus
tests remain for an exclusive-desktop session.
