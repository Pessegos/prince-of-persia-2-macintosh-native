# Remaining host-slot writers (2026-10-30)

Inventory for the next queue/input migration stages, after armed requests
moved to the directional bank (see `armed-input-priority.md`). It lists the
code paths that still **write** `ScenePrototype.pending_action`, the native
rule each one stands in for, and the proposed migration with the regression
that should reject today's behavior. No production behavior changed here,
except the armed Up-release fix noted below.

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

Proposed: let the waiting bank own the recovery: clear its directions in
mode 5 (as 6:059c) and drop the slot write from `start_jump` there. Tests:
a released tap during 212 never jumps; a hold jumps at the first standing
gate; a held Forward is fresh after the recovery (both facings).

## 2. Presses during the run stop (SEQS 13) without a bank

Native: the brake poses 50-52 reach GenCtrl's standing gate (6:05fe-0618),
so these presses are bank requests like at rest.

Port today: `waiting_controls_available` requires an existing bank. When
the run stop starts without one (a scripted start, or a run started through
the legacy path), presses go to the slot and `resume_queued_action_during
_run_stop` dispatches them at 50-52; a released turn or crouch tap waits
there as a host command.

Proposed: create the bank on the first key event in a waiting sequence
(sampling the held keys as consumed, as `begin_waiting_controls` does) so
the waiting family always owns these presses. Remove the run-stop branch of
`resume_queued_action_during_run_stop` together with it; keep the sheathe
stop (SEQS 92 at 50-52) until that family moves. Tests: a turn tapped at
pose 47-49 of the brake turns at 50; a crouch tapped there crouches; with
both, the original priority (backward before down) applies.

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
The SEQS 46 wall/climb tail stays an explicit exception (see
`ledge-input-handoff.md`).

## 4. Releasing Up with the sword drawn (fixed)

`set_key_state('up', False)` called `start_jump` when Up had been held
without starting a jump, for example a press during a hurt (controls locked)
released after the sword was drawn. The queued jump then fired after
sheathing. With the sword drawn Up belongs to the armed bank (DoBlock), so
the release no longer starts or queues a jump. Regression:
`tests.test_armed_input` "releasing up held through a hurt" (fails on the
previous code).

## Consumers still reading the slot

`dispatch_pending_action`, `resume_queued_action_during_run_stop`,
`update_native_input_boundaries` (SEQS 46 tail), `update_fall_recovery_
controls`, the airborne/ledge/low/running families' one-shot imports of
scripted requests, and the ledge-climb completion re-classification. Each
should be removed with its producer above, not separately.
