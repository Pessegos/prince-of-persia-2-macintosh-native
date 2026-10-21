# Prince Turn Flag And Cached Rear Target

Research note, 2026-10-21, `claude/ai-research`. Continues the SwordCtrl
target-cache and conditional turn-decision findings in `AI_RECOVERY.md`
("Hurt Recovery And Facing"). No gameplay code changed. Addresses are original
CODE `segment:offset`; `a5-0xNNNN` names A5-relative globals. Local probes need
private original data and are not part of the public checkout.

Labels: **[D]** direct reading of original instructions; **[X]** executed in a
local native probe; **[I]** inference from direct evidence; **[?]** open.

## Turn flag `a5-0x5010`

- [D] A5-relative writers are only `2:5e5c` (writes 1) and `6:2344-2350`
  (toggles 1/0). An address-of search over all segments found no `lea`/`pea`
  base whose copy covers `a5-0x5010`. ResumeGame's `_BlockMove` (`2:1156`)
  targets the heap buffer held in `a5-0x5018`, not the A5 globals. Register
  indirect stores through other computed pointers were not exhaustively
  audited [?].
- [D] `2:5e5c` ends the Prince level setup `2:5cf4`, whose only caller is
  RestartGame `2:5c16`. RestartGame returns before setup only when its level
  argument is 0, -1 or above 14, or when `a5-0x4fd0` is non-zero
  (`2:5af2-5b12`, `2:5b76-5b7e`). Both level-load paths (`2:5bb8` LoadLevel,
  `2:5bce` LoadLevelMinimum) join at `2:5bd4` and reach `2:5c16` without
  further branches. ResetGame `2:4546-457c` invokes it for the requested level.
- [D] The rebirth path in PlayerCtrl (`4:3bcc-3bee`) calls the Prince
  initializer `2:5e66` directly; that routine does not write the flag.
- [D] The static A5 image value is 0, so the flag is 1 only after a setup run.
- [D] The toggle branch `6:22f2-2362` requires the Prince (ID 10), the "back"
  latch `a5-0x3486` newly pressed and button latch `a5-0x3480` at -1 or 1.
  It then selects the turn routine (`6:2332`), clears direction latches
  (`4:3e3a`), toggles the flag and stores the nearest candidate on the new side.
- [I] Latch meaning: ReadKeyboard (`2:5614-56c0`) maps up/down to `a5-0x3496`,
  left/right to `a5-0x3498`, and the button word `a5-0x3494 = -1` to KeyMap
  key 56 (Shift) or key 65; `-2` to key 59 (Control) or key 82. `4:3d96`
  mirrors the horizontal latches by facing before GenCtrl, so `a5-0x3486` is
  "back" inside GenCtrl.

**Inference:** in ordinary play the automatic SwordCtrl turn at `6:22a6` is
enabled after each RestartGame, and each voluntary back+Shift sword turn
toggles it. A death/rebirth does not reset it.

**Port:** the port has no voluntary sword turn; back with the sword drawn is a
retreat (`scene_prototype.py` `queue_sword_step`). It therefore never reaches
the native flag-0 state, and its automatic turn behaves as if the flag were 1.
A port voluntary turn would be a feature addition, not part of this note.

## Life-meter delta gate `+0x22`

SwordCtrl `6:2212-2230` exits unless `|working +0x22| < HP`.

- [D] `+0x22` is a pending life-meter change, not only damage. DecLifePts
  (`4:352e-3586`) stores negative values. The max-life potion helper
  (`2:53f8-5428`) stores `max - HP`. ChangeMeters (`2:54d6-55c0`) applies
  `HP = clamp(HP + delta, 0, max)` to the Prince record and each bank slot.
- [D] ResetFrameVars (`2:68c0`, called from FrameAdv `2:6106` when
  `a5-0x4fee != 0`) clears the Prince record's delta at `2:68ec`. Other writers
  of the saved Prince delta are RestartGame `2:5c0c` and the death path
  `4:3bcc`.
- [I] The Prince frame copies that record at `2:62ea` before SwordCtrl, and no
  life change runs between them. In ordinary frames the gate therefore sees 0
  and passes. A supplied non-zero value makes the native code exit while the
  port could still turn, but that state is not expected in ordinary Prince
  frames.

## Sources of a cached rear target [X]

A local probe (`sword_turn_reachability_native_probe_v1.py`) runs one original
GenCtrl → SwordCtrl call per step. It carries only the native Prince target
field (`+0x3a`) between steps. Positions, HP (ALIVE = HP > 0), alert, Prince
mode, meter delta and turn flag are supplied per step. AnimChar, NPC control,
contact and cadence are not executed. The port side keeps one encounter and
evaluates `refresh_target()` then `choose_player_turn()`. Both facings were
tested.

- **S1, kill ahead, then B approaches.** Guard C is ahead and cached, A is 50
  px behind with the Prince's facing (alert 2), and B is 90 px ahead.
  - Step 1: C reaches HP 0 while the Prince is in mode 2. Native SwordCtrl
    still selects (Part A showed selection also runs in modes 2/3) and stores
    the nearest live candidate A. The port also picks A.
  - Step 2: B moves to 30 px ahead (mode 3). Native keeps A. The port
    reselects B because A shares the Prince's facing.
  - Step 3: back in mode 0, native reaches the turn routine `6:26b8` (distance
    -50). The port has B ahead and does not turn.
- **S1 control, B stays farther than A.** Both keep A and both turn.
- **S2, rear A at alert 1.** A becomes cached while at alert 1, and the native
  alert gate `6:2248` prevents the turn. B then approaches, so the port
  switches to B. When A reaches alert 2, native turns toward A and the port
  does not.
- **Single cached rear target** (no B to mask gates):

  | Gate | Native | Port |
  | --- | --- | --- |
  | flag 1 | turns | turns |
  | flag 0 | does not turn | turns |
  | alert 1 | does not turn | does not turn |
  | mode 2 | does not turn | does not turn |
  | delta = HP | does not turn | turns |

  The two differences correspond to the flag-0 state, which the port cannot
  reach, and the delta state, which is inert in ordinary frames.

**Conclusion:** the D1 difference follows from ordinary-looking supplied
transitions. A rear target becomes cached while the Prince is mid-strike or
the rear guard is not yet engaged, and a nearer guard then approaches. Whether
gameplay produces these exact transitions frame by frame is not executed [?].

## Not established / next

- The `6:26b8` floor checks, position adjustment and JumpSeq(127) are not
  executed; the visible turn remains a decision-level claim.
- A full frame trace (AnimChar, NPC control, TestStrike/CheckStab, cadence)
  of the S1 sequence is not done.
- Other writers of the Prince target (TestStrike `6:5a06/5a48`, GenCtrl dead-NPC
  reselection `6:0762-077c`, ALIVE ≥ 6 clear `4:3d32-3d46`, removal adjust
  `2:66e8-672e`) have not been exercised.
- **Proposed port change, not implemented.** Keep a persistent Prince target
  cache with the SwordCtrl rule: keep while HP > 0 and the index is in the
  bank, otherwise use the nearest native-ALIVE candidate. Keep the Main
  facing-based frame Opp as a separate temporary choice. This needs
  coordination on `combat.py` and an integration regression that rejects the
  current reselection and preserves the zero-HP corpse-target behaviour.
