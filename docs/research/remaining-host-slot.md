# Remaining host-slot writers (2026-10-30)

Inventory of the queue/input migration stages after armed requests moved to
the directional bank (see `armed-input-priority.md`). It lists the code paths
that wrote `ScenePrototype.pending_action`, the native rule each one stood in
for, and the migration with the regression that rejects the old behavior.
The slot is now retired (last section); the numbered sections are the record
of how each writer went.

## Method

A census run replaced `pending_action` with a recording property and ran
the input, animation, combat, terrain, level-six and caverns suites
(`tests.test_animation_data`, `test_input_*`, `test_*_controls`,
`test_terrain`, `test_combat`, `test_level6`, `test_caverns`). Writes from
test code (fixtures that assign the slot directly) are excluded. Each row is
the writing call chain, the command, the current sequence and the sword
state. This shows which paths ordinary scene traces still exercise; it is
not proof that no other path exists.

| Writes | Path | Command | Sequence |
| --- | --- | --- | --- |
| 30 | `press_up` -> `start_jump_if_needed` -> `start_jump` -> `buffer_input` | jump | 212, 20 (hard-fall recovery) |
| 4 | `horizontal_key` -> `queue_sampled_horizontal_action` -> `queue_horizontal_action` | turn/run | 13 (run stop), no bank |
| 1 | `set_key_state('down')` -> `buffer_input` | crouch | 13 |
| 4 | `horizontal_key` -> `queue_released_jump_direction` | jump | 46, 47 (climb tail, wall stop) |
| 2 | `set_key_state('up', False)` -> `start_jump` | jump | 227, sword drawn |

## 1. Up during the hard-fall recovery (SEQS 20 -> 212 -> 49)

Native: GenCtrl 6:0576-059c calls ClearControls in animation mode 5 every
frame (the INPUT_RECOVERY "Hard-Fall Recovery Input" section). A tap during
the recovery is discarded. A held Up is 0 after each clear and becomes a
fresh request (-1) at the first sample after mode 5 ends.

Port today: `start_jump` buffers a jump; `update_fall_recovery_controls`
discards it in mode 5 and re-reads the held Up afterwards. The result
matches for these two cases, through two mechanisms.

Done: SEQS 20/212 joined `LOW_INPUT_SEQUENCES` (49 was already there),
so the bank's mode-5 clear covers 108/109 and the key callbacks no longer
reach `start_jump`/`buffer_input`; `update_fall_recovery_controls` is
removed. Regression: `tests.test_input_recovery` "presses belong to the
bank" (Up/Down/Forward/Backward, tap and hold, both facings; the old code
fails all 16 at the slot assertion). A tap leaves the Prince at rest; a
hold selects 28/50/1/6 at the standing gate.

## 2. Presses during the run stop (SEQS 13) without a bank

Native: the brake poses 50-52 reach GenCtrl's standing gate (6:05fe-0618),
so these presses are bank requests like at rest.

Port today: `waiting_controls_available` requires an existing bank. When
the run stop starts without one (a scripted start, or a run started through
the legacy path), presses go to the slot and `resume_queued_action_during
_run_stop` dispatches them at 50-52; a released turn or crouch tap waits
there as a host command.

Done: `WaitingControls.ensure_run_stop_controls` creates the bank for a
SEQS 13 that has none, with the keys already held marked consumed. The key
callbacks call it before they change the held state (so the press itself
stays fresh), and the tick reaches it through `waiting_controls_available`.
The run-stop branch of `resume_queued_action_during_run_stop` is removed;
the sheathe stop (SEQS 92 at 50-52) keeps it until that family moves.

Sheathe (done): `start_sword_action('sword_sheathe')` hands the bank to
`WaitingControls.begin_sheathe_controls` (PutSwordAway 6:2598: ClearControls,
Down=1), and the waiting bank owns SEQS 92/93 and the idle pose after them.
`resume_queued_action_during_run_stop` and the sheath branch of
`resume_run_during_standing_turn` are removed. Raw SEQS 92 sets mode 5 for
pose 50, so taps made during the long sheathe are discarded there and held
keys act at 51 (previously 50, and taps were kept); a pending Forward runs
from pose 48. Regressions: `tests.test_armed_input.SheatheBankTests`.
Regressions in `tests.test_waiting_controls`: Backward/Down taps at 55 and
49, alone and in both orders, turn before crouching and never crouch after
the turn (the old slot kept the last tap: Backward then Down crouched);
keys held into a scripted brake are not requests. Three fixture tests in
`test_animation_data` that started SEQS 13 without a bank now follow the
production timing of a real run's brake: a press at 50 starts the turn or
crouch in the callback, so the next tick shows 46/108, not 45/107.

## 2b. Presses during a scripted standing turn (SEQS 5) without a bank

Native: level entry, restart and the level-six cliff door start SEQS 5
(45-52). The latches are 0 there (4:3e70 at 2:5bdc; ClearControls and a
zero modifier at 7:379a), so a key still held is a fresh request. GenCtrl's
pose-48 gate (6:062c/1014) resumes a pending or held Forward as SEQS 43;
50-52 are the standing gate.

Port before: presses went to the slot (`queue_sampled_horizontal_action`);
`resume_run_during_standing_turn` ran a held Forward at 48 and
`resume_queued_turn_during_standing_turn` dispatched the last tap at 50.

Done: `ensure_run_stop_controls` also creates a zeroed bank for a bankless
SEQS 5, and both resume functions are removed. Regressions in
`tests.test_waiting_controls`: Backward/Down taps in both orders turn and
never crouch (the old slot crouched on Backward-then-Down); a released
Forward tap runs from pose 48 as SEQS 43 (the old slot started SEQS 1 at 50).
The restart chord test now checks the bank instead of the slot.

## Census after the sheathe and scripted-turn stages (2026-10-30)

Same method, 688 tests (animation, armed, recovery, waiting, combat,
terrain, level six, caverns, game UI and every `test_input_*`/`*_controls`
module). Every remaining non-fixture write is in the wall-bump climb
family: SEQS 46 (bump), its rise 49, and 47 (wall stop) or the idle after it.

| Writes | Path | Sequence |
| --- | --- | --- |
| 60 | `advance_terrain` wall event keeps an unfulfilled vertical Up | 47, 46 |
| 50 | `queue_released_jump_direction` | 47, 46, 49, 2 |
| 18 | `press_up` -> `start_jump` -> `buffer_input` | 46, 47, 49 |

These were the retained host wall-climb tolerances (a climb requested before
or during a bump survived later wall contact). No slot writer outside this
family remained in the traced suites.

## 5. Wall bump and wall stop (SEQS 46 -> 49, 47) (done, user approved)

Native: Collide (terrain.py, 4:5826-584c) selects 46 (poses 102, 107-109,
rising through 49: 110-116 mode 5, 117-119 mode 1) or 47 (50-52, all mode
5). GenCtrl's mode-5 gate (6:0576-059c) runs ClearControls every frame
there, so a tap made before or during the bump is discarded, and a key
still held when mode 5 ends is a fresh request at the next sample (4:3e84).
Up alone then climbs (DoJumpUp 6:1600); Up and Forward still held jump
forward again, so holding a jump chord into a wall repeats the jump.

Port before: the wall event kept an unfulfilled vertical slot request
(`advance_terrain`), `queue_released_jump_direction` turned an arrow release
in 46/47 into a jump, and `press_up` buffered into the slot, all excluded from
the low bank by `source_sequence_id == 46` checks. The SEQS 46 tail branch of
`update_native_input_boundaries` discarded only horizontal/crawl requests.

Done: 46 and 47 joined `LOW_INPUT_SEQUENCES`; the source-46 exclusions, the
wall-event snapshot/keep, the 46/47 release producer and
`update_native_input_boundaries` are removed. The port's legacy rooftop climb
(SEQS 46 with `ledge_hanging`, prototype without a level map) keeps its owner.
Changed behaviour: an Up tap during the bump no longer climbs; holding Up and
the arrow into a wall repeats the jump instead of stopping once. As at the
other bank-owned stops, a held key dispatches at the transition to idle, so
a held Forward goes from 52 straight into the next step without showing
pose 15 (the old slot path showed one idle frame). Two scripted tests that
waited for that frame (`test_terrain` sword-draw wall contact, `test_harbor`
complete route) now release or climb at a phase-independent point.
Regressions (fail on the previous code): `tests.test_low_controls` "wall bump
and wall stop belong to the bank" (Up/Down/Forward, tap and hold, 46 and 47),
`tests.test_game_ui` "cavern run jump bump discards an Up tap but climbs on a
held Up" (6 poses) and "wall bump repeats a jump only while its keys stay
held", and the 46/47 cases of `tests.test_input_recovery` "releasing run jump
horizontal". The held-Up wall-climb tests keep their climbs; their slot
assertions now check that no slot is written, and pose 15 left their release
lists because a held chord no longer rests there.

## 3. Releasing the horizontal half of a held Up chord

Port today: `queue_released_jump_direction` turns the release of the arrow
of a held Up+arrow chord into a jump request during runs, jumps (SEQS 3/4)
and the climb tails 46/47.

Native: a release does not create a request (4:3e84). Whether Up is still
pending at the next gate depends on whether the takeoff consumed it: DoRunJump
6:1d48 and DoJumpUp 6:1608 write Up=1, so a held consumed Up is not a new
jump; an Up that was never consumed (pressed during the run but not yet
admitted) is still pending. The port rule therefore approximates the
pending case and over-produces in the consumed case.

Proposed: needs a bounded trace first (no new native probe is required for
the latch rules; the airborne and vertical handoff models cover the gates).
Replace the release producer with the bank's own pending Up. Tests: release
the arrow after an accepted running jump: no second jump; release it while
Up is still pending in the run: standing jump at the brake/standing gate.
The SEQS 46/47 part now belongs to the bank (section 5).

Update (producer census below): `queue_released_jump_direction` is removed.
The same release rule remains a host tolerance inside the running (SEQS 1,
6, 43, 200-202) and jump (3, 4, 14, 28, 11) banks, now one method,
`latch_released_chord`; the native-latch replacement proposed here is still
open.

## 4. Releasing Up with the sword drawn (fixed)

`set_key_state('up', False)` called `start_jump` when Up had been held
without starting a jump, for example a press during a hurt (controls locked)
released after the sword was drawn. The queued jump then fired after
sheathing. With the sword drawn Up belongs to the armed bank (DoBlock), so
the release no longer starts or queues a jump. Regression:
`tests.test_armed_input` "releasing up held through a hurt" (fails on the
previous code).

## Retirement of the slot and its consumers (2026-10-30)

Final census, same method over the whole discovery set (3,291 tests): no
production code wrote the slot; only fixtures did. A static review of the
remaining writers found two that ordinary play reaches but no test pressed
through, both item actions started from a crouch:

| Sequence | Poses | Mode | Old slot behaviour |
| --- | --- | --- | --- |
| 78 (drink) | 191-205 | 1 | last tap ran at pose 15 (Backward then Down crouched) |
| 91 (sword pickup) -> 92 | 229-232, then the long sheathe | 1 (92's pose 50 is 5) | last tap ran after 52 (Up jumped, Down crouched) |

Native: GenCtrl 6:0560-07e0 (static decode) has no branch for these poses:
they are not in IsDeadPos 4:47a0 (185, 242/243, 266, 271 for the Prince) or
179-183, nor in any later range (246-263, 217-226, 272-281, 295, 26/44). With
mode 1 the 6:0576 clear does not run either, so the latches simply wait for
the next gate: pose 15 after the drink (6:05fe, standing priority 6:0db0-0e16),
and the long sheathe's own gates after the pickup (48 resumes a pending
Forward as SEQS 43, 50 is mode 5, 51-52 standing).

Done: `ITEM_SEQUENCES` (78, 91) joined `WaitingControls.waiting_sequence`, so
the bank survives the item action (the pickup's own 6:0b4c clear and modifier
consumption still run first). With no writer left, the slot was removed:
`pending_action`, `dispatch_pending_action`, the airborne/ledge/low/running/
waiting one-shot imports, the run-cycle and landing dispatch calls, the
non-native climb reclassification and the slot retarget in
`queue_sampled_horizontal_action`. `dispatch_jump`'s vertical-Up run brake
now latches the Up into the brake's bank instead. `buffer_input` latches into
the bank where a family owns the pose and otherwise drops the tap; this is a
port approximation for the poses no family owns yet (throne collapse 237 and
wake 231, which run IsDeadPos/wake branches; the prototype rooftop without a
level map). Held keys are still read at rest there.

Regressions (fail on the previous code): `tests.test_potions` "taps during
the drink wait in the bank for the standing gate" (Backward/Down in both
orders and facings turn and never crouch) and `tests.test_level6` "presses
during the pickup meet the long sheathe's gates" (Forward tap runs from 48;
Up/Down taps are discarded at 50; held Backward turns at 51). Fixtures that
assigned the slot now latch through `buffer_input`, and the 198 assertions
that only checked the slot stayed empty were dropped with it. The airborne
and vertical handoff audits no longer record a `pending` field.

## Census of the remaining producers (2026-10-30)

With the slot gone, `buffer_input` was the last generic bridge: the key
callbacks that no bank intercepted still built a command and handed it over,
and it latched into the owning bank or dropped the tap. A census replaced
`buffer_input` and `queue_released_jump_direction` with recorders and ran the
whole discovery set (3,293 tests). Every production call latched into a bank;
none was dropped and none was armed:

| Calls | Path | Sequence/poses | Test |
| --- | --- | --- | --- |
| 6 | paused `horizontal_key` -> `queue_released_jump_direction` | 3 (16, 19, 22) | standing jump keeps held Up for the wall climb |
| 3 | paused `horizontal_key` -> `queue_released_jump_direction` | 4 (34, 39, 40) | run jump keeps held Up when the arrow is released |
| 1 | `start_jump` called directly | 42 (pose 0) | fixture-style call |

All other calls (119, among them every armed one) came from test code. The
unpaused key callbacks never reach the bridge: each bank family intercepts
its keys first (`waiting_key`, `waiting_horizontal`), and where no family owns
the pose the bridge could only drop the tap.

The paused release was a real difference. Pausing, releasing the arrow of a
running Up chord and resuming latched a bare Up without the running bank's
follow-up flag, so the run took off as a running jump (SEQS 4) and met the
wall; the same release without pause brakes (13) and jumps up (14 or 28).
Trace: level 3, native room 21, X 250, facing left, Up pressed at run poses
8-13; old paused runs `[4, 201, 13, 47, 24]` or `[4, 47, 24, 9, 10]`, live
and new paused `[201, 13, 14, 11, 14]` or `[202, 13, 28, 11]`.

Done: the paused branch calls the owning family's `latch_released_chord`
(the rule the running and jump banks already applied on a live release), and
`queue_released_jump_direction` is removed. `buffer_input` becomes
`latch_request` (scripted requests only: `start_jump` from a pose a bank owns,
and fixtures); its queue-grace filter and potion-pickup reset went with it.
The dropping producers are removed: Down pressed outside a crouch, and the
non-resting branches of `queue_sampled_horizontal_action` (jump chord) and
`queue_horizontal_action`. Regression (fails on the previous code):
`tests.test_game_ui` "releasing the arrow of a run chord during pause acts as
without pause" (paused and live traces equal, no SEQS 4; pose 5 is a control
that matched before too).
