# Prince Target On Character Removal

Research note, 2026-10-21, `claude/ai-research`. No runtime code changed.
It closes the open writer "removal adjust `2:66e8-672e`" listed in
`proposed-prince-target-layers.md`.

Labels: **[D]** direct reading; **[X]** executed in a local native probe;
**[I]** inference.

## RemoveChar `4:48f8-4970` [D]

1. RemoveChar marks the working character for removal:
   - facing word `+0x2` = 86 (`0x56`);
   - mode and ALIVE `+0x1c` = 0;
   - HP `+0x1e` = 0.

   The entry at `4:4924` also sets the room to 0.
2. If the character's ID is not 0 and it is the Prince's target (a5-0x5098),
   the target becomes GetOppIdxClosestToKid(1). A removed slot 0 is not
   reselected here.

### Callers

- AnimChar opcode `-17` (`4:2f68`, table index 8). It ends `SEQS:145`, 154,
  196 and 239. The only JumpSeq(154) found is in CheckCheatKeys (`2:4c96`).
  JumpSeq(145) is in CODE 7 and JumpSeq(239) in CODE 9, both special-level
  segments. No JumpSeq(196) was found.
- TriggerJinnee `4:1d76`, CutToKidRoom `4:23e4`, `4:25f0` (shadow merge
  after IsShadowImbued), IsBrgGateOpen `8:038e` and CODE 10 `283e`.

None of these is an ordinary guard fight in levels 1-3 [I]. The port does not
implement `-17`, and `SequenceRuntime` raises on it. It does not select these
sequences either. It does treat 154/196 as terminal records at room save
(`opponent_records.py`).

## FrameAdv removal loop `2:66dc-673e` [D]

For each bank slot whose facing word is 86:
1. LoadShad (`4:4ac0`), then RemoveOppFromRoom (`6:3462`), which compacts
   the bank.
2. A Prince target above the removed slot is decremented.
3. A target equal to the removed slot becomes
   GetOppIdxClosestToKid(working facing word). Because the loaded removed
   record carries the marker, the argument is always 86.

## GetOppIdxClosestToKid side argument [X]

Local probe `rendered/closest_side_arg_native_probe_v1.py` (ignored by Git)
calls `6:36f2` directly. Each layout has one guard left and one right of the
Prince, in the same room and row, both native-ALIVE. It covers 3 layouts and
both Prince facings (24 calls). The result does not depend on the Prince's
facing.

| Argument | Result |
| --- | --- |
| 1 | Nearest on either side |
| 0 (right-facing word) | Right-side guard only |
| -1 (left-facing word) | Left-side guard only |
| 86 (removal marker) | None (-1) |

So the argument is an absolute side given as a facing word, not "ahead" of
the Prince. This confirms the voluntary turn's `~facing` argument
(`voluntary-sword-turn.md`): it selects the side the Prince is turning
toward.

The removal loop's reselection therefore always stores -1, "no target". On
the next frame, SwordCtrl (armed) or Main (otherwise) picks the nearest
guard by its own rule.

## Port comparison

`refresh_target()` replaces a target that has left the active bank with the
nearest native-ALIVE guard on either side. This matches RemoveChar's
GetOppIdxClosestToKid(1) for IDs other than 0. For slot 0, or after the loop's
-1, the native target is empty for one frame before SwordCtrl or Main fills
it. The port fills it at once. The nearest-guard result is the same; only the
frame on which it is stored differs [I]. Given the callers above, no ordinary
level-1-3 difference is expected. No change is proposed.
