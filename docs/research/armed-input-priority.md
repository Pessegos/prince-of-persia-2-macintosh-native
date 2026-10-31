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

Retained host policies at the time (removed 2026-10-31, see below): a
fresh Ctrl press was an attack request that survived releasing Ctrl (the
original cancels it, 4:3f38), except before the counter gates; rapid Ctrl
repeats during the first attack poses were discarded and consumed. (The automatic sword turn was then also always enabled; since
2026-10-30 a voluntary turn toggles it as in the original.)

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
current-cell kind 4:35a6, distance 4:49ee, target 6:36f2/4:3312 and
level-five bridge test 8:02ae supplied. 3,538,944 cases (24 bank shapes, two
animation modes, three cell kinds, the opponent alert word a5-0x5062 at
0-3, eight distances, three opponent types, actor types 0/11, both
automatic-turn flags, rooms 1/7/10/12, rows 0/1, the bridge word, the
8:02ae result 0/1 and a fatal pending hit)
match `tools/reference_armed_input.py:sword_ctrl` with zero mismatches.

- Result SHA256: `5c6706d24410f7642fd1c13e19474df5a5c251c8910a897a7ba44283095318c7`
  (2026-10-31; the 442,368-case run before the 8:02ae dimension: `1fcb...9664`).
- Correction (2026-10-30): the first run (110,592 cases, digest
  `8389...a2be`) kept a5-0x5062 at 0 and called 4:35a6 "engagement". 4:35a6
  is CurrentCell (ReadCell 4:27ee of the Prince's room, stored column and
  row), and 6:2248 also admits the distance routing when the opponent copy's
  alert word (+0x32, a5-0x5062) is 2 or more. The model now takes both.

Recovered routing, for a living Prince in animation mode 0/1 without a
fatal pending hit (otherwise nothing runs):

1. Distance routing (6:2236-2274) runs when the Prince's own cell is a
   loose floor (11) or ruins shelf (15), or the opponent is at alert 2 or
   more. There a distance of -15..330 runs OnAlert. An opponent farther
   behind (below -15) selects the automatic turn 6:2638 instead of OnAlert,
   unless the automatic-turn flag a5-0x5010 is 0, the opponent type is 6,
   or (level five, rows 1-2, rooms 7/10/12) the bridge test passes; those
   run OnAlert. Actor type 11 does neither. Farther ahead than 330 falls
   through to step 3.
2. Shift or a consumed Shift (modifier -1/1) with a pending Backward then
   takes the voluntary turn, except in level five's room 10 while a5-0x3130
   (the breaking bridge) is positive: modifier 2, ClearControls, Backward 1,
   the automatic-turn flag toggles, and the target is chosen again. The
   flag starts at 1 (enabled) with each level (2:5e5c). One voluntary turn
   therefore disables the automatic turn until the next voluntary turn or
   level; this is the original's answer to opponents on both sides.
3. Otherwise, when neither step 1 ran OnAlert nor turned: a pending Down
   calls PutSwordAway **directly** (6:2382; no OnAlert pose gate and ahead
   of a pending attack), else OnAlert. PutSwordAway 6:2592 has no pose gate
   of its own: it clears sword mode, ClearControls, Down=1, then SEQS 93
   while OppToFight finds a fighter, else 92.

Port status: the automatic turn's distance rule (-15), its precedence
over OnAlert in the same frame, the flag toggle (since 2026-10-30) and the
room-10 bridge refusal match `combat.choose_player_turn`,
`choose_voluntary_turn` and `resume_combat_turn`.

Step 3 is in production since 2026-10-30
(`combat.player_distance_routed`, `ArmedControls.sheathe_unengaged`): the
cell is the Prince's supporting-foot cell, the alert is the current
target's (`combat.guard`, the effective target the death-target audit
checked), and the distance is `opponent_distance` (999, i.e. beyond reach,
in another room or row). USER-VISIBLE: after a kill, or with the target at
alert 0/1 (another room, sight blocked) or more than 330 ahead, Down
sheathes at the next frame, even mid-strike, mid-step or mid-block, and
wins over a pending attack. An engaged opponent within reach keeps OnAlert's
priority (attack first) and its guard-pose gate. Regressions (fail on the
previous code, 6 subcases): `tests.test_armed_input.UnengagedSheatheTests`.
The port's first-pose wait (cursor 0) is unchanged.

The turn exemptions are in production since 2026-10-31
(`combat.choose_player_turn`): an opponent of working type 6 (raw kind 3,
only in level 14) and, in level five's bridge rooms off row 0, a Prince
for whom 8:02ae says "press forward" run OnAlert instead of the automatic
turn; a loose floor or shelf underfoot admits the turn at alert 0/1 as it
does the rest of the distance routing (`combat._distance_routing`).
Regressions: `tests.test_combat` (`test_auto_turn_skips_an_opponent_of_type_six`,
`test_auto_turn_on_a_loose_floor_or_shelf_needs_no_alert`) and
`tests.test_bridge.BridgeGuardAiTests.test_a_pressing_prince_does_not_turn_to_the_skeleton_behind_him`.
The SwordCtrl probe now supplies 8:02ae's result 0/1 in rooms 1/7/10/12 at
rows 0/1 (3,538,944 cases, 0 mismatches).

### BridgeEngage 8:02ae, and a swapped port rule

`tools/probe_bridge_engage.py` executes 8:02ae with BridgeGetCharCol
8:0188, 8:0424 and IsBrgGateOpen 8:0458; only the trob lookup 5:38a6 is
supplied (none, or phase 0-3 for room 7 cell 13). 1,244,160 cases (rooms
1/7/10/12, columns -1..10, both facings, X differences around 0 and -204,
opponent room/column, sword word 0-2, the trob, tension level/amount)
match `pop2.bridge.bridge_engage` with zero mismatches; the trob lookup is
called with (7, 13) or not at all.

- Result SHA256: `d4932e6c41fbe7b678dab7bc79cda6a9190f5e0d8f1e27b8edd9a463e18d976b`.

Rule: with the facing word -1 (**left**) the character presses from bridge
column 8 on; with 0 (**right**) below column 2, when its opponent is behind
room 7's open gate (opponent bridge column below 2), or against an opponent
with sword word 1 less than 204 pixels ahead, in its own (unadjusted)
column 6 or lower, while the tension is level 2 with at least 20.

Correction: the port's `_bridge_engage` (implemented 2026-10-23 for the
bridge skeleton) had the two facings swapped: right from column 8, left
below 2 or toward the gate, with the Prince *behind* the skeleton. 8:04a2
uses the same word with the port's facing correctly, so the swap was
local. USER-VISIBLE on level five's bridge: the skeleton now presses
forward from its post at the right end (facing left, column 8+) and,
facing right, from the left end or back toward its post when the Prince
hides behind the gate; it no longer presses at the left end while facing
the Prince there. EnGarde, GenFight, OpponentClose, the pursuit gap rule
and the skeleton's SwordCtrl turn all use the corrected rule.

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

## Ctrl taps: the native modifier alone (2026-10-31)

User decision: remove both attack extensions, provided a double tap still
swings once as on the Mac. `tools/probe_attack_taps.py` runs the sample
4:3e84-3f42 and OnAlert 6:24bc with its action bodies frame by frame over
every Ctrl pattern of ten frames starting with a press at the guard pose
(512 patterns, 5,120 frames). Supplied: guard pose 158 and SEQS 75's poses
151..157 after each accepted strike, LEVL2004 header, no opponent pose.
Excluded: outer SwordCtrl routing, FrameAdv, taps shorter than a frame.
Zero mismatches against `reference_swings` and the closed rule: the second
strike starts at the first gate frame (pose 157, then guard) where Ctrl is
held after a release. All 62 patterns whose second tap is released before
the gate swing once. The reason is the modifier update itself: DoStrike
writes 2 (6:280c), the release writes 0 and a later press -2; a release
before the next admitting pose writes 0 again (4:3f38). No pose filter or
consumed latch is needed.

- Result SHA256: `f6571f4d85f4e3d5aa2197f0f1a267b9ac631ff6088a08a49bf5092357d02591`.

Runtime: `armed_attack_requested` and the 151-153/162 filter are removed;
a Ctrl press writes -2 into the armed bank (`latch_armed_attack`, also used
for a press made while paused and still held at resume) and every armed
sample can cancel it. USER-VISIBLE: a Ctrl tap released before the Prince
reaches a striking pose (during a draw, step, turn or the end of a strike)
no longer strikes later; hold Ctrl until the swing starts. A press made
during 151-153 and held to 157 now swings again. The scene regression
replays the 512 patterns in both facings through the key callbacks and
matches the native strike frames; both removed extensions fail it. Tests
that queued a strike with a released tap now hold Ctrl to the gate.
