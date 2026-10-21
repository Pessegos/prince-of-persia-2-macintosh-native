# Voluntary Sword Turn (Back + Shift)

Research note, 2026-10-21, `claude/ai-research`. No runtime code changed.
It continues `prince-turn-flag-and-rear-target.md`, which located the toggle
branch, and specifies the missing port feature.

Labels: **[D]** direct reading; **[X]** executed in a local native probe;
**[I]** inference.

## Original branch `6:22f2-2366` [D]

The branch is inside SwordCtrl, after the automatic part `6:2252-22f0`, and it
runs on the same frame even when that part has already called OnAlert or the
turn.

1. **Gates:**
   - the actor is the Prince (ID 10);
   - the Backward latch `cb7a` (a5-0x3486) is fresh (negative);
   - the modifier latch `cb80` (a5-0x3480) is -1 or 1, which is Shift, fresh
     or held; Ctrl is -2/2;
   - not in level 5, room 10 (native) with a5-0x3130 > 0, the same exception
     as the turn routine `6:26d2`.

   The outer SwordCtrl gates still apply: native ALIVE, sword 1, mode below
   2 and not 4/5/9, sequence not 27/110, and the meter delta below the HP.
2. **Turn:** turn dispatch `6:2638`. For actor types 0/1 this is the Prince
   turn routine `6:26b8`, the same floor checks and JumpSeq(127) as the
   automatic turn the port already implements.
3. **Latches:** the modifier becomes 2 (consumed). ClearControls `4:3e3a`
   zeroes the four directions and Backward becomes 1 (consumed).
4. **Flag:** a5-0x5010 toggles (0 → 1, otherwise → 0). A value of 0 disables
   the automatic turn at `6:22a6`.
5. **Target:** the target `+0x3a` (a5-0x501c) receives
   GetOppIdxClosestToKid(`~facing`), the nearest native-ALIVE candidate on
   the side the Prince is turning toward. The write is unconditional, so it
   is -1 when there is none.

Otherwise (`6:2368`), if no automatic action was taken, a fresh Down goes to
the sheath branch `6:2592` and anything else goes to OnAlert `6:24bc`. Inside
OnAlert, a retreat requires modifier 0 (`INPUT_RECOVERY.md`). Shift + Back
therefore never retreats in the original.

## Executed check [X]

Local probe `rendered/voluntary_sword_turn_native_probe_v1.py` (ignored by
Git) runs one GenCtrl `6:0560` call per case:
- 180 cases: both facings, three layouts, Backward 0/-1/1, modifier
  -2/-1/0/1/2 and flag 0/1;
- the layouts are a guard ahead within reach, ahead plus a guard behind, and
  only a far guard behind.

Supplied endpoints:
- `6:26b8`, `6:24bc`, `6:2592` and JumpSeq `6:0006` are recorded returns;
- the room check `8:02ae` returns 0;
- ClearControls and GetOppIdxClosestToKid run natively;
- AnimChar and the floor checks of `6:26b8` are not executed.

Results:
- **Fresh Back with Shift (24/24):** the turn is called, the flag toggles,
  Backward becomes 1 and the modifier 2.
- **Same frame as the automatic part:** OnAlert runs first and then the
  turn when the guard is in reach. When the automatic turn already ran
  (rear guard, flag 1), the turn is called twice, and the flag still toggles
  to 0.
- **Target after the turn:**
  - ahead plus rear guard: the rear slot;
  - only a guard ahead: -1;
  - only a far rear guard: that slot.
- **Every other case (156):** no flag change. With flag 0, the far rear guard
  gets OnAlert instead of the automatic turn.

## Consequences for the port

- **Shift + Back:** the port retreats (`queue_sword_step`); the original
  turns. The port retreat also ignores the modifier-zero rule.
- **Automatic turn:** the port never reaches flag 0, so it is always on.
  In the original, each voluntary turn switches it on or off. The flag
  returns to 1 only at level setup (`2:5e5c`), not on death or rebirth
  [D, earlier note].
- **Target:** the voluntary turn overwrites the target with the candidate on
  the new side, or with none.

## Proposed feature (needs coordination)

This needs `pop2/scene_prototype.py` (the input) and `pop2/combat.py`. The
scene file is reserved for the level-four work.

- **Input:** with the sword drawn, a fresh Back while Shift is held requests
  the voluntary turn instead of the retreat. A Back with any modifier does
  not retreat.
- **`CombatEncounter`:**
  - an `auto_turn` flag, set at level setup and toggled by the voluntary
    turn;
  - `choose_player_turn` returns `False` when the flag is off;
  - the voluntary turn reuses `PLAYER_COMBAT_TURN_SEQUENCE` and
    `combat_turn_offset`;
  - it sets `target_cache` to the nearest native-ALIVE guard on the new side,
    or `None`.
- **Save:** saving the flag would add a field. Keeping the save format
  unchanged means the flag resets to 1 on load, which is a deliberate
  approximation to record. Whether a native resume keeps the flag is not
  established; ResumeGame's copy does not cover it [D, earlier note].
- **Regressions:**
  - Shift + Back turns and does not retreat;
  - the automatic turn is off after one voluntary turn and on after two;
  - the target becomes the rear guard, or `None`;
  - a Back without Shift still retreats.
- **Open question for the user:** the native toggle can surprise a player who
  did not know the automatic turn was switched off. Implementing it is the
  faithful choice; keeping the automatic turn always on would be a recorded
  port exception.
