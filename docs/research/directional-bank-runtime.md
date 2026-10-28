# First directional-bank runtime migration

The input research is now used by a production `DirectionalInput` bank in
`pop2/mac_input.py`. This first migration replaces deferred input during
standing turns and cautious steps, including the ordinary ready gate at their
end. It does **not** enable a complete replacement across every controller.

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
| Run, airborne, low/prone, ledge and armed controllers | Existing host policies, pending later migrations |
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
