# Armed request priority

This is the first armed stage after the low/prone bank migration. It recovers
OnAlert's request arbitration and fixes conflicting requests in the existing
armed host buffer. It does **not** migrate armed input to the directional bank.

## Original evidence

`tools/probe_armed_input.py` executes the original CODE6:24bc-2584 in an
isolated M68000 instance. It compares 19,440 cases with the independent
`tools/reference_armed_input.py` model: all combinations of four directional
words -1/0/+1, five modifier words, twelve supplied poses and actor types
0/1/7/8. All cases agree; the original executable remains unchanged.

- Result SHA256: `33045ae1dc901a33f97bf9219a27b97d17e7358d88861776b023ae1ddcac8def`.
- Original executable SHA256: `ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
- The supplied LEVL2004 header is checked before execution.
- Attack, sheathe, block, advance, retreat and special-actor action bodies are
  sinks. JumpSeq and AddCharX are also sinks returning zero. Recoil observes
  the sequence57 request and signed -9 X argument for actor0; actor1 requests
  the sequence without that X adjustment. Input words remain unchanged at
  these **request** boundaries, because consumption belongs to action bodies.
- The probe excludes outer SwordCtrl, opponent/terrain decisions, automatic
  and voluntary turns, action admission/consumption, animation, FrameAdv,
  keyboard sampling and host buffer lifetime. It does not certify combat AI.

OnAlert first delegates types7/8. For ordinary actors, pose161 with a
nonnegative modifier forces recoil before other requests. Otherwise:

1. Fresh Ctrl (-2) requests attack, even at a pose where DoStrike will refuse.
2. Pending Down owns the next branch. Only158/170/171 request sheathing;
   at other poses it blocks fallback to Up or movement.
3. Pending Up requests block.
4. Pending Forward requests advance.
5. Pending Backward requests retreat only with modifier0.

Positive consumed direction words do not request a new action. Shift and a
consumed Ctrl suppress the ordinary Backward branch. Voluntary turns belong
to the enclosing SwordCtrl and remain outside this selector.

## Runtime change and retained policy

`pop2/sword_controls.py:armed_input_request` implements the checked request
selector. `buffered_sword_request` uses its eventual guard158 gate to arbitrate
two existing buffered requests. It must not evaluate the current draw/attack
pose and wrongly discard a command that the port deliberately buffers.

Previously, a later arrow, Up or Down callback replaced a queued strike.
Now conflicting armed requests use the recovered priority, in either order
of arrival. The same arbitration runs before the immediate guard dispatcher
can clear the pending command, and in `buffer_input` for internal producers.

Only the winner stays in the existing host slot. This remains an interim
adapter: it does not preserve all lower-priority independent native latches,
reclassify horizontal requests after a later turn, or replace raw-held sword
step repetition. Those require the next armed bank lifecycle module. No
second executable queue was introduced.

The deliberate rapid-Ctrl attack-start filter runs **before** arbitration:
a discarded rapid attack cannot erase a buffered block. Existing grace,
held movement, draw/attack/counter pose admission, released-Ctrl counter
cancellation, pause, automatic/voluntary turns and sheathing stay separate.
The removed running stop-and-draw QoL is not restored.

## Regression checks

The initial three scene regressions failed in28 subcases before the runtime
fix. The final scene tests check all ordered request pairs in both facings, actual Ctrl and
arrow/Up/Down callbacks during drawing, completed attack/sheath traces, rapid
attack rejection, and a selected-but-not-yet-displayed guard boundary.

An older animation test explicitly expected a later retreat tap to erase a
queued strike. Its expectation now retains the strike and checks the exact
164/165 ->151..158 trace, following the newly checked OnAlert priority.
Existing reversal, step cadence, counter, block and rapid-attack tests retain
their pose and timing assertions.

The asset-free CI selector test compares the production selector against the
same independent model over all19,440 inputs, including the blocked Down
branch and supplied special-actor boundary. Native execution is an explicit
local research command, not part of normal tests or asset import:

```powershell
python -m tools.probe_armed_input --source PATH_TO_RECOVERY --output rendered/armed-input-priority.json
python -m unittest -q tests.test_armed_input tests.test_animation_data tests.test_input_recovery
```

Next: carry the existing five-word bank through admitted armed sequences,
remove the corresponding legacy directional producers and consumers
together, and preserve the documented attack-repeat tolerance explicitly.
The runtime boundaries to replace together are `start_sequence`'s retirement
of the unarmed bank, the sword branches in key callbacks, queued guard return,
counter cancellation/recoil and sheath-to-ground return. Automatic/voluntary
turns must use the facing captured at dispatch; queued horizontal requests
currently have their kind fixed at event time. The present priority adapter
must be retired when that bank becomes the sole armed directional owner.

## Validation of this stage

- Final focused input/animation/catalogue run:173 tests pass; asset-free
  directional/selector CI selection:10 tests pass.
- Full shared-desktop discovery:3,267 tests in553.514s,10 explicit exclusive
  desktop skips and one catalogue consistency failure. The process had
  imported the old review metadata before the catalogue/documentation update
  during that run. The fresh catalogue tests and check pass afterward; no
  production code or test assertion changed during/after full discovery.
  The raw full run is not reported as green, and the importer was not repeated
  for a documentation/module-cache mismatch.
- Ruff F/E9, dependency and whitespace checks pass. Tests use isolated
  temporary data and hidden fixtures; no live game window is operated.
