# Proposed Prince Target Layers (Specification, Not Implemented)

Design note, 2026-10-21, `claude/ai-research`. It summarizes the original
rules established in the companion notes into an implementable port change.
**No code has been changed.** `pop2/combat.py` and save schemas are shared
interfaces, and `pop2/scene_prototype.py` is reserved for the level-four
work, so ownership must be agreed before implementation.

## Original model

| Layer | Original | Stored? | Rule |
| --- | --- | --- | --- |
| Persistent cache | Prince `+0x3a` | yes | See the writers below |
| Frame Opp, Main | `2:62f8-6342` | no | Keep the cache if it is not -1 and its slot's facing differs from the Prince's. No HP, ALIVE or count test. Otherwise use the nearest native-ALIVE guard on both sides, else slot 0. |
| Frame Opp, SwordCtrl | `6:2174-2200` | writes the cache | Runs when the Prince is ALIVE, in mode not 4/5/9, in a sequence other than 27/110, with sword 1. Keep the cache if it is not -1, inside the bank and HP > 0, with no facing test. Otherwise use the nearest native-ALIVE guard and store it if found, else slot 0 without storing. The Opp is reloaded. |

Writers of the persistent cache:

- SwordCtrl reselection `6:21fa`;
- TestStrike hit `6:5a06` and block `6:5a48` (the last contacted slot in bank
  order);
- GenCtrl dead branch `6:0762-077c` and ALIVE ≥ 6 clear `4:3d32-3d46`;
- removal adjustment `2:66e8-672e`;
- voluntary sword turn `6:2362`, which the port lacks;
- level setup `2:5e8c`, which sets -1.

## Port consumers and the layer they should read

| Port consumer | Original reader | Layer |
| --- | --- | --- |
| `choose_player_turn` (automatic sword turn) | SwordCtrl `6:2252-22ea`, after the reload at `6:2200` | SwordCtrl |
| `start_sword_action` fast-block check (target pose 168/153) | DoBlock `6:2844`, reached from SwordCtrl control | SwordCtrl [I] |
| `choose_player_bump` (unarmed overlap) | FrameAdv `2:6c64`. Sword ≠ 1, so SwordCtrl did not run | Main |
| Save target index (`save_game.py`) | Prince record `+0x3a` | Persistent cache |

## Proposed rules

1. **Persistent cache.** Replace the facing condition in `refresh_target()`.
   Keep the cached actor while it is in the active bank and HP > 0. Otherwise
   pick the nearest native-ALIVE guard (`_nearest_guard()`) and keep the old
   value when there is none. The effective fallback is slot 0, as now.
2. **Contact writes.** In `resolve_contacts()`, a Prince hit (action 154 within
   range) or a parry against the Prince sets the cache to that guard, using
   the last contacted guard in active-bank order.
3. **Main frame Opp.** For `choose_player_bump`, compute a temporary target
   that is not stored. Keep the cache when its facing differs from the
   Prince's, even if it is dead; otherwise use the nearest guard, else slot 0.
   A dead Main Opp yields no bump: the port bump already requires
   `guard.alive`, and the original GetDist returns 999 for HP 0.
4. **Keep unchanged:** the HP rejection, native-ALIVE selection and the
   pending-ALIVE behaviour (verified to match in 180 executed death frames),
   active-bank membership and side-room projection.

## Regressions to add (each must fail on the current code)

- **D1 resident:** cached A 60 px behind with the Prince's facing and alert 2;
  B 40 px ahead, opposing. The armed Prince in a ready pose requests the turn
  toward A. Repeat for both facings.
- **S1 sequence:** C ahead is killed while the Prince is mid-strike, so A
  behind becomes the cache. B then approaches nearer than A. On return to a
  ready pose, the Prince turns toward A.
- **Contact write:** cached A out of reach and B hit (or blocking). After
  `resolve_contacts()` the target is B, and with two hits it is the later
  slot.
- **Unarmed bump (Main layer):** a cached dead opposing guard plus a live guard
  overlapping. No bump is produced while the Main Opp is the corpse. This
  needs one more native check before being asserted, see Open.

## Existing regressions that must stay green

- `test_opposing_side_target_is_retained_until_its_control_hit_points_reach_zero`
- `test_pending_zero_hp_candidate_stops_obstructing_selection_after_control_registration`
- `test_target_refresh_discards_stale_actor_and_falls_back_to_slot_zero`
- The carried-guard three-tick death/turn trace, and the existing auto-turn
  tests in `tests/test_combat.py`.

## Open before implementation

- **Main-layer bump:** confirm by executing `2:6c64` with a corpse frame Opp
  and a live overlapping guard. That an unarmed Prince does not bump while the
  Main Opp is the corpse is an inference so far.
- **DoBlock fast-block Opp:** confirm that it reads the Opp reloaded by
  SwordCtrl.
- **Save compatibility:** the save index already exists. The rule change does
  not alter the format.
- **Voluntary sword turn (back + Shift):** a possible separate feature that
  would make the `a5-0x5010` flag reachable in the port.
