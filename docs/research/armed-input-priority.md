# Armed request priority

The first stage below recovered OnAlert's request arbitration as an interim
fix of the armed host buffer. The second stage (2026-10-30, "Action-body
consumption and bank ownership") replaced that buffer: the five-word bank is
now the sole owner of armed directional and modifier requests.

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

## Action-body consumption and bank ownership (2026-10-30)

`tools/probe_armed_consumption.py` runs OnAlert 6:24bc **with** its action
bodies DoRetreat 6:1d6e, DoAdvance 6:1dda, DoStrike 6:2780, DoBlock 6:282a
and PutSwordAway 6:2592 and the real ClearControls 4:3e3a. JumpSeq 6:0006
records the sequence. 71,280 cases (all 405 banks, eleven poses, opponent
poses 0/152/153/168, two distances, with and without an opponent) match the
independent `tools/reference_armed_input.py:armed_action`, with zero
mismatches. Supplied: AddCharX 4:2bae, OppToFight 6:2392, distance 4:49ee,
4:2c0c and the sheathe tail 6:25ee; the fixture uses LEVL2004's header,
ALIVE type-0 Prince and the opponent pose a5-0x508a. Excluded: outer
SwordCtrl/turn routing, actor types 1/7/8, terrain, animation, FrameAdv and
DoAdvance's level-five sequence 86 (a5-0x507e/-0x5088 are zero).

- Result SHA256: `a2c02902f7dd65269254384c79f96b7cf781d39857c98ac08cdf4d70200f3a7b`.

Recovered rules:

| Request | Admitting own poses | Sequence | Words after acceptance |
| --- | --- | --- | --- |
| Attack (Ctrl -2) | 150/161 (66), 157/158/165/170/171 (75) | 66/75 | all directions 0, modifier 2 |
| Sheathe (Down) | 158, 170, 171 | 92, 93 with an opponent | directions 0, Down 1 |
| Block (Up) | 158/165/168/170/171 unless the opponent is at 168; 167 | 62; 61 | **Up 1 only** |
| Advance (Forward) | 158, 170, 171 | 56 | directions 0, Forward 1 |
| Retreat (Backward, modifier 0) | 158, 170, 171 | 57 | directions 0, Backward 1 |

A refused request changes no word: a released tap stays pending (-1) and
acts at the next admitting pose. A consumed hold stays 1 (4:3e84), so
**holding an arrow or Up acts once**; release and press again to repeat.
ClearControls writes 0, so a direction still held after a strike, sheathe
or step becomes a fresh request at the next sample; DoBlock alone leaves
the other words pending (Up+Forward blocks, then advances).

Runtime: `pop2/armed_controls.py` samples the bank on armed key events
(presses and releases) and every armed tick, remaps it with the facing at
dispatch, selects with `armed_input_request` and calls the existing
`start_sword_action` admission; only an accepted action consumes
(`consume_armed_request`). The sword keys, guard return, post-frame 158
dispatch, counter (66 at 150/161), forced recoil and voluntary turn now use
it. `buffered_sword_request`, the armed use of `pending_action` and the
raw-held step/block repetition were removed together. The voluntary turn
consumes Backward and the modifier (6:2330-233c). A press at a displayed
guard pose still starts at once when it is the selected request.

Retained host policies, explicit in that module: a fresh Ctrl press is an
attack request that survives releasing Ctrl (the original cancels it,
4:3f38), except that a released Ctrl is still cancelled before the counter
gates; rapid Ctrl repeats during the first attack poses are discarded and
consumed; the automatic sword turn stays enabled.

Changed expectations, each from the rules above: held sword steps and held
Up blocks no longer repeat; a held Up after a counter blocks again at the
guard; a held Forward after a strike advances again. Scripted combat tests
now press each step (`tap_sword_step`). The screen-five kill test states
its turn timing through the mode-5 rule instead of a fixed offset, because
the tapped fight now ends with SEQS 203.

Not covered here: recordings of real key timing and other fighters'
controllers. The outer routing and DoAdvance's level-five sequence follow.

## Outer SwordCtrl routing (2026-10-30)

`tools/probe_sword_ctrl.py` runs the Prince's SwordCtrl 6:2166-2390 with
the turn 6:2638, OnAlert 6:24bc and PutSwordAway 6:2592 as sinks and the
engagement 4:35a6, distance 4:49ee, target 6:36f2/4:3312 and level-five
bridge test 8:02ae supplied. 110,592 cases (24 bank shapes, two animation
modes, three engagement results, eight distances, three opponent types,
actor types 0/11, both automatic-turn flags, rooms 1/10, the bridge word
and a fatal pending hit) match `tools/reference_armed_input.py:sword_ctrl`
with zero mismatches.

- Result SHA256: `838908062cb098cdf83294831cf2ebe28d097a4be8c7229f30b1d2039307a2be`.

Recovered routing, for a living Prince in animation mode 0/1 without a
fatal pending hit (otherwise nothing runs):

1. Engaged (4:35a6 returns 11 or 15): a distance of -15..330 runs OnAlert.
   An opponent farther behind (below -15) selects the automatic turn
   6:2638 instead of OnAlert, unless the automatic-turn flag a5-0x5010 is 0,
   the opponent type is 6, or (level five, rows 1-2, rooms 7/10/12) the
   bridge test passes; those run OnAlert. Actor type 11 does neither.
   Farther ahead than 330 falls through to step 3.
2. Shift or a consumed Shift (modifier -1/1) with a pending Backward then
   takes the voluntary turn, except in level five's room 10 while a5-0x3130
   (the breaking bridge) is positive: modifier 2, ClearControls, Backward 1,
   the automatic-turn flag toggles, and the target is chosen again. The
   flag starts at 1 (enabled) with each level (2:5e5c). One voluntary turn
   therefore disables the automatic turn until the next voluntary turn or
   level; this is the original's answer to opponents on both sides.
3. Otherwise, when neither step 1 ran OnAlert nor turned: a pending Down
   calls PutSwordAway **directly** (no OnAlert pose gate), else OnAlert.

Port status: the automatic turn's distance rule (-15) and its precedence
over OnAlert in the same frame match `combat.choose_player_turn` and
`resume_combat_turn`. Differences, not changed here: the port keeps the
automatic turn always enabled (the approved voluntary-turn exception), it
does not exempt opponent type 6 or the level-five bridge rooms from the
automatic turn, and it sheathes only at guard poses 158/170/171 even when
SwordCtrl would call PutSwordAway directly (step 3 when not engaged).
Engagement 4:35a6 itself is not modelled here.

## DoAdvance's level-five sequence

DoAdvance 6:1e28-1e46 selects SEQS 86 instead of 56 in level five when the
opponent copy (a5-0x5094) is in native room 19 (+0x16) at column 5 (+0xc).
`pop2/sword_controls.py:advance_sequence` implements it for the Prince's
current target (port room 18, supporting column 5).

## Validation of the first stage

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
