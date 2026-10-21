# Prince Target Across An Ordinary Guard Death

Research note, 2026-10-21, `claude/ai-research`. Completes the audit of the
original writers of the Prince target field (`+0x3a`) that do not come from
selection or contact. See also `prince-turn-flag-and-rear-target.md` and
`teststrike-prince-target-writes.md`. No gameplay code changed. Labels:
**[D]** direct reading, **[X]** executed in a local native probe, **[I]**
inference, **[?]** open.

## Original writers [D]

- **NPC control prefix** `4:3d24-3d6c`, which runs for each slot in the NPC loop
  after the Prince's frame:
  - native ALIVE < 0 with HP 0 registers the death: ALIVE becomes 0
    (`4:3d64-3d6c`);
  - ALIVE 0..5 with the word `+0x18` set counts ALIVE up (`4:3d48-3d5a`);
  - ALIVE ≥ 6 calls `5:4bb8` and clears the Prince target to -1 when it still
    points at this NPC (`4:3d32-3d46`).
- **GenCtrl dead branch** `6:056c → 6:0762-077c`, which runs for a registered
  NPC. When the Prince target equals this NPC, it is replaced by
  `GetOppIdxClosestToKid(1)` and stored even if the result is -1.
- [D] The bank copy of the dying NPC keeps ALIVE -1 until SaveShad at the end
  of its loop iteration. The selector called in that same iteration can
  therefore choose the dying NPC again.

## Executed lifecycle [X]

Local probe `death_target_lifecycle_native_probe_v1.py` (not published).

**Native fixture:** resident guards in room 1 of the level-1 LEVL, Prince at
X=250 with both facings and sword drawn. At the start, the cached guard C has
just reached HP 0 with ALIVE -1, as after TestStrike and CheckStab.

**Each native frame:** memory is carried between frames and only target-relevant
original code runs, in this order:

1. LoadKid `4:4b02`;
2. GenCtrl → SwordCtrl selection, stopping at `6:2206`;
3. a supplied copy of the working Prince back to the saved record;
4. for each slot: LoadShad, the NPC control prefix (stopping before AutoCtrl
   at `4:3d70`, with `5:4bb8` stubbed to return), the GenCtrl dead branch for
   registered NPCs (stopping at `6:0780`), then SaveShad.

Living NPC AutoCtrl/GenCtrl, AnimChar, contact and cadence are not executed.

**Port side:** each tick registers deaths through `choose_guard_action()` (dead
guards only) and refreshes the target as the end of `resolve_contacts()` does.
The comparison is between the native SwordCtrl effective target and the port
target at the start of the matching tick.

**Scenarios:** 20 scenarios of 9 frames each. They vary the death flag `+0x18`
(0/1), whether C is the nearest guard, a nearer guard ahead, a nearer guard
behind with the Prince's facing, no other guard, and C in slot 1.

| Frame | Original | Port |
| --- | --- | --- |
| 1 | SwordCtrl rejects C (HP 0) but can reselect C, whose bank ALIVE is still -1. The GenCtrl dead branch after registration can pick C again. | Refreshes after the hit and also selects C when C is nearest, because `native_alive` is still true. |
| 2 onwards | The nearest native-ALIVE guard. With no other guard, -1 is stored and slot 0 is the effective target. | The same guard, or slot 0. |

**Result: 0 effective-target differences in 180 frames.** The ALIVE ≥ 6 clear
and the death counter never changed the effective target in these fixtures.
They only update a field that SwordCtrl has already replaced.

## Consequence

The port's HP-based rejection together with its `native_alive` selector gives
the same effective Prince target as the original death writers. This holds for
these ordinary resident fixtures. Any future persistent-target change
(proposed in the companion notes) should keep this rule and the corpse-target
regression unchanged.

## Open [?]

- Who sets the NPC word `+0x18` in ordinary deaths (writers include
  `4:59d8` and `6:2db6`), and what `5:4bb8` does for a dead type-2 actor
  (it dispatches through an undecoded jump table by actor type).
- Removal adjustment `2:66e8-672e` after RemoveOppFromRoom is not executed. The
  port holds object references, so index shifting is structurally absent; the
  reselection when the removed slot was the target is not compared.
- Side-room imports, skeletons and special actors are outside this audit.
