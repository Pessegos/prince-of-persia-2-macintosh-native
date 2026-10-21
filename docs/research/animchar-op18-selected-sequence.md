# AnimChar Opcode -18 Clears The Selected Sequence

Research note, 2026-10-21, `claude/ai-research`.

**Implemented in `a33dec9`, with the user's authorization while Codex was
unavailable; integrated into `main` alongside the level-four playtest.**
- `-18` now sets `selected_sequence_id = 0`. The extra `sequence_mode` clear
  is kept because it is inert.
- `save_game.py` accepts a selected ID of 0.
- Three regressions fail on the previous code: the runtime link case, the
  skeleton second shake, and the save round trip.
- Rerunning the native probe gives 0 selected-ID mismatches in 3,438 frames.
- **Consequence found by the full suite (`143d972`).** The port hid the sunk
  Prince (pose 185 after `-18`) only through its selected-27 sand clip. The
  original hides him because `-21 7` makes IsCharNonViewable (`4:4724`)
  true, so ClipChar (`4:4152`) skips the character. `composite_actor` now
  skips actors whose `sequence_mode` is 4, 5, 6, 7, 10 or 12. In ordinary
  play only `SEQS:27` sets one of these values. The environment-5 dead-pose
  branch of IsCharNonViewable (`4:474c-477c`) was already implemented in
  `render_opening.py` (`actor_mask`).
- The quicksand test now expects the native state: selected 0, pose 185,
  mode 7. A rendered check (local, not committed) shows the sand without
  the corpse.

It started from a limit of the Prince target patch: the SwordCtrl gate
excludes sequences 27 and 110 (`proposed-prince-target-layers.md`).

## Recovered rule

AnimChar dispatches opcodes `-25..-1` through the table at `4:2c70`
(`jmp 2c6e(pc, d1)`, index = opcode + 25). Known handlers confirm the
decoding: `-2` flips the facing word (`4:2ca2`), `-7` writes the mode
`+0x10` (`4:2cc6`), and `-1` writes the current ID `+0x26` (`4:2e54-2ec2`).

| Opcode | Handler | Native effect | Port (`sequence_runtime.py`) |
| --- | --- | --- | --- |
| -18 | `4:2d7e-2d84` | `clr.w` the selected ID `+0x28` (a5-0x502e) | sets `sequence_mode = 0`, keeps `selected_sequence_id` |
| -21 | `4:2f8a-2f96` | writes the operand to `+0x34` (a5-0x5022) | sets `sequence_mode` |

JumpSeq `6:002c-0032` writes both `+0x26` and `+0x28`; a `-1` link writes
only `+0x26`. So after `-18` the selected ID stays 0 until the next JumpSeq,
including across a following `-1` link. The port's `source_sequence_id`
models `+0x28` (JumpSeq comment in `sequence_runtime.py`, `terrain.py`,
EnGarde in `combat.py`), but it keeps the old ID.

## Executed check

Local probe `rendered/seqs_selected_id_native_probe_v1.py` (ignored by Git)
runs original AnimChar `4:2c0c` once from every frame boundary of every
`SEQS` resource. It runs for actor types 0 and 2, with the selected ID equal
to the sequence and `+0x34` preset to 99. It then compares the result with
one `SequenceRuntime.next_frame()`.

- **Endpoints:** those of the existing hold probe, namely the `SEQS` handle
  lookup at `4:3098`, the `HLock`/`HUnlock`/`HGetState` traps and the
  NativeLoose sound and LEVL stubs.
- **Not compared:** frames where either side raises. That is 18 native and 36
  port frames; the port does not implement `-24` (for example `SEQS:230/232`).

| Result | Frames |
| --- | --- |
| Compared | 3,438 |
| Pose mismatches | 0 |
| Frames that execute `-18` | 40 |
| Selected-ID mismatches | 40, all on `-18` frames; native value always 0 |
| `+0x34` mismatches | 38, all on `-18` frames (the port clears its mode; native keeps 99) |
| Y mismatches | 78, at `-19` SetCharFloor, which the port delegates to terrain (sampled, not fully classified) |

The 20 sequences with `-18` are 14, 27, 28, 68, 78, 88, 100, 112, 137, 138,
139, 140, 152, 156, 172, 173, 229, 235, 238 and 242.

## Port consumers that see the stale ID

Only consumers that test an ID from that list can change.

| Port consumer | Native reader | After `-18` | Observable effect |
| --- | --- | --- | --- |
| Skeleton shake `skeleton.py` `try_wake` (`!= 112`) | `4:15c6`: JumpSeq(112) when `+0x28` is not 112 | 112 → `-18` → 119 | **Yes.** In the port, a second shake consumes the shake and the timer but plays no animation and no sound 61; native restarts 112 (reproducer below). |
| Stone gate `terrain.py` `stone_gate_blocks` (68) | `4:5b42` | 68 → 210 → 11 | Gate exemption lasts through 210/11 in the port; native ends it at `-18`. Not reproduced. |
| Wall correction `terrain.py` (70, 78) | not located | 78 → 2 | Correction stays skipped while standing in 2. Not reproduced. |
| Desert sand clip/draw, stone delay (27) | `18:0526`, `18:0a82` | pose 185 loop | Native drops the 27 tests during the final sink loop. Rendering/timer only. Not reproduced. |
| Opponent height capture `opponent_records.py` (100, 186) | UpdateOppInfo | 100 → 208 run | The port captures a height that restore ignores, because restore tests the saved current ID. No effect found. |
| Skeleton rise (88) | `4:16c0` | 88 → 227 | The 227 poses are below 179. No effect found. |

The GenCtrl `6:058c-059a` 27/110 gate also reads `+0x28`. For the Prince:
- StartFall `4:4ca8-4cb2` clears sword 1 before the desert JumpSeq(27)
  (`4:4da2-4dce`). The port mirrors this in `scene_prototype.py`.
- The only JumpSeq(110) is DoOppRunJump `4:0826`. It is reached from
  `6:501a` in a type-dispatched controller (`4:165c`, jump table entry
  337) that has no direct caller.

The SwordCtrl 27/110 exclusion is therefore not reachable with sword 1 for
an ordinary Prince [I]. This closes that limit of the target patch for the
ordinary Prince; the dispatcher table remains undecoded.

### Skeleton reproducer (port only)

`stationary_bones(shakes=2)` from `tests/test_skeletons.py`, ticked 60 frames:

- frame 0 plays 112 (sound 61);
- frames 6-19 hold 119 with the selected ID still 112;
- at frame 20 the shake count drops from 1 to 0 and the timer is rerolled
  (37), yet the actor stays in 119 at pose 206 with no sound;
- the rise (88, sound 60) starts at frame 58.

Native, with `+0x28 = 0`, takes the JumpSeq(112) at `4:15ce` on that frame.

## Second observation: one native word, two port fields

Native `+0x34` (a5-0x5022) is a single word. The port splits it in two:
- `sequence_mode` is written by `-21`, by `-18` and by the scene
  (`scene_prototype.py`). Its readers test for 3, 4 and 11.
- `special_flag` is read for 13 (OppToFight `6:23b2`, guard brake) and for
  4/5 (UpdateOppInfo, skeleton). Only attract playback writes it (record word
  26). In gameplay it stays 0.

The only `-21 13` is in `SEQS:232`, which uses the unimplemented `-24`, and
no SEQS writes 4 or 5. The split is therefore latent, not a demonstrated
defect. The native non-AnimChar writers of `+0x34` (`2:5e82`, `3:07fa`,
`4:1e94`, `6:1916`, `6:29cc`, `6:2cc2`, `6:2e7a`) were not audited.

### Writers of `+0x34` in the ordinary segments (2, 3, 4, 6) [D]

| Writer | Value | Port |
| --- | --- | --- |
| Prince init `2:5e82` (level start and rebirth) | 0 | — |
| ResetFrameVars `2:68f0-6906`, saved Prince | clears 8, except in current sequence 52 with `+0x24` = 0 | — |
| Opponent1 `3:07e4-07fa` | clears 8 | — |
| TriggerJinnee `4:1e94` | from `d4` | — |
| DoJumpHigh `6:1906-1916` | 0 when releasing: modifier 0, or value 11 | `scene_prototype.py` sets `sequence_mode = 0` on release |
| CrushChar `6:29ca` | 8 | — |
| Side-room load `6:2cc2`; GenerateOpponent `6:3c48` | 0 | — |
| `6:2e7a` (type 11, pose 264) | 6 | — |
| AnimChar `-21` | operand | `sequence_mode` |

Segments 7-10 (special levels) also write it and were not reviewed.

Following `-1` links from every `-21` with a non-zero operand:
- values 1, 2 and 3 are rewritten to 0 by the same sequence before any
  `-18`;
- 7, 12 and 13 end in a hold;
- 11 (`SEQS:210`) links through 11 to 2 without a `-18`.

So no link chain carries a non-zero `+0x34` into a `-18`. Only a later
JumpSeq could do so, which needs 11 to survive the hang. That happens only
when the climb is taken in the two frames after `-21 11`, and the port
already resets `sequence_mode` when a hang starts. The port's extra clear of
`sequence_mode` at `-18` is therefore inert in ordinary play [I]. Removing it
is optional.

## Proposed change (needs coordination)

`sequence_runtime.py` is a shared interface.
- **Proposal:** `-18` sets `selected_sequence_id = 0`.
- **Save validation:** `save_game.py` currently rejects a selected ID that is
  not a `SEQS` resource. It must accept 0 without changing the format.
- **`sequence_mode`:** the extra clear at `-18` is inert (audit above).
  Removing it is optional and can be a separate commit.
- **Regressions:**
  - a runtime test that `-18` yields selected 0 across a following `-1`
    link;
  - the second skeleton shake replaying 112 with sound 61;
  - a save round trip with selected 0.
