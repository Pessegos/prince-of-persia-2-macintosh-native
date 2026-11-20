# Level 12's Flaming Sword (Actor Type 10)

Status: first port, 2026-10-31. Source reading of CODE 2/3/4/6 with focused
regressions (`tests/test_flame_sword.py`); no native probe yet. Native rooms
are one-based, port rooms zero-based.

## Identity

- Level 12 (opponent set 7) native room 7 holds one initial record: raw kind
  1, X 560, row 0, facing left, skill 11, SEQS 105, life 6.
- 6:2bca keeps raw kinds 1/3/9/10 and DATA a5-0x5280 maps raw 1 to actor
  type 10. CheckLoadedOppSet 3:5278 then loads opponent set 1. The program's
  file list (`:Data:Guard.rsrc`, `:Data:FlameSword.rsrc`, ...) puts
  FlameSword.rsrc second, and its FRAM matches the sequences exactly: every
  FRAM shape is -1 (no body); poses 213-217 (FRAM 64-68, LoadFrame 4:2b0e
  `action - 149` as for type 2) are AFRM pieces 14-18, the sword lying on
  the floor and lifting. The other frames carry hovering flame pieces on the
  ordinary guard poses. It is a sword fighting by itself.
- SEQS 105 holds 213; 106 animates 213-217 (cues 241/239) and links to 227
  (en garde); 107 plays it back down to 105; 103 is the parried push-back;
  108 its advance (13 pixels in pose 171); 109 its strike (218-227: raised,
  tilted, a 21-pixel lunge at 224, back down near the floor); 90 a 17-pixel glide.

## Recovered rules (port)

| Native | Rule | Port |
| --- | --- | --- |
| InitOpps 6:2d16-2d62 | fresh record on a floor (IsFloor of CurrentCell 4:35a6): SEQS 105, not engaged; else SEQS 106, engaged, alert 3, facing the Prince | `FlameSword.initialize` |
| InitOpp 6:2b02-2b10 | SEQS 105 has 0 life points, else the record's maximum | same |
| IsDeadPos 4:489c, 6:2e34-2e4e | pose 213 is its only dead pose; then the record timer is cleared | `FlameSword.settle` |
| FrameAdv 2:6242-624a, 4:14c6 | the skeleton proximity loop also runs for a type-10 bank (slot 0, a5-0x5200) | `wake_skeletons` |
| 4:13a4, 4:1534-1548 | dead, timer 0, same row, Kid type 0 and not in modes 3-5, within 5 columns; the scan needs floor in every cell; impassable cells are allowed for type 10 (4:1478) | `FlameSword.can_wake` |
| 4:15dc-1644 | JumpSeq(106), AnimChar, InitOpp (full life), ALIVE, engaged, alert 3, faces the Prince, becomes his target if he has none | `FlameSword.try_wake` |
| AutoCtrl 4:16e8-1704 | a resting record's timer counts down | `FlameSword.control` |
| TestStrike 6:590a | the Prince's strikes skip a type-10 defender | `resolve_contacts` |
| GetCharStrikeRanges 6:5c58 | its strike reaches -16..61 | `strike_range` |
| TestStrike 6:5962 | the Prince's parry window against it is 24..70 (61..99 otherwise) | `resolve_contacts` |
| TestStrike 6:5a74, FlameSwordDecLifePts 4:1c36 | a parried strike costs one life: SEQS 103, cue 10, SetCharFloor 4:31fa; the last one 4:1c9e: SEQS 107, SetSkelTimer 480, AddSong 238, ALIVE 0 | `FlameSword.parried/fall` |
| DoStrike 6:27bc-27e4 | from 157/158/170/171/165 it strikes with SEQS 109 (poses 218-227), not the guard's SEQS 58 | `apply_guard_intent` (2026-11-20) |
| IsStrikingPos 6:5d9a-5db8, IsTheStrikePos 6:5e4a-5e64 | 223/224 can be parried, the strike lands at 224 (153/154 and 154 for guards) | `striking_poses`, `strike_pose` |
| TestStrike 6:5ab4-5af8 | an unparried strike that misses sounds 239 instead of 11; a parry (Prince at 161) and a hit sound nothing here | scene audio, parry event sound 0 (2026-11-20; it was read as a parry cue) |
| Defence 4:1206 | it never blocks | `decide_guard_intent` |
| 6:1e1c | advance SEQS 108 instead of 86 | `apply_guard_intent` |
| 6:2592/25d4 | instead of sheathing (SEQS 77) it glides (SEQS 90) | Prince-dead branch |
| AnimChar 4:2ca2 (opcode -2) | its turn first moves AddCharX(25) | `SequenceRuntime` |
| Turn admission 6:2690-26a6 | type 10 cannot select SEQS 60 in floor/rise poses 213..217; it may turn once ready | `choose_guard_action` (2026-11-10 follow-up) |
| CheckAlert 2:704c-7068 | gaps, obstacles and closed gates neither limit nor block its alert; walls do | `alert_path_mode(floating=True)` |
| CheckStab 6:5722 | the Prince killed by it gets death method 12 | `_hurt` |
| CheckFloor 4:35ca | it never falls | no terrain physics |
| SetupSword 3:0b1c, 4:1be4 | drawn from the opponent bank (image set 3) at piece = AFRM shape, X +/- (FRAM X + AFRM X), Y + FRAM Y + AFRM Y; pieces 4/19/20 flicker: counter 0 keeps the piece, then 19, 20, 21, 22 | `FlameSwordArtwork`, `FlameSword.present` |
| SetupOpponent 3:0f3e, 4:1cce | while a shown piece is 4/19/20 it bobs: Y <= floor-4 moves Rnd(1)+1, Y >= floor+4 moves Rnd(1)-4, otherwise Rnd(8)-4 | `FlameSword.present` |
| CheckCheatKeys 2:4c4a | the kill cheat sets the timer to 480 and SEQS 107 | host kill command |
| UpdateOppInfo/InitOpps | a living record restarts through the fresh path; a resting one keeps its pose and loses its timer | `store_room/restore_pending` |

CheckPress 5:1294 excludes type 10 from plates; the port gives it no terrain
motion, so the plate, loose-floor, spike and crush hooks skip it.

## Port decisions and approximations

- The port selects the opponent artwork per room (the native has one loaded
  set): frame records follow the Prince's room, but each actor is drawn with
  its own file. The birdheads keep Birdhead.rsrc.
- Without a body shape its barrier collision (CheckBarr/EnemyCollide edges)
  is not recovered; it stays within its room's X extent.
- Its unarmed AutoCtrl paths (after the Prince dies it is not engaged) are
  not recovered: it holds still.
- The flicker/bob run once per frame after the opponents' animation, for
  actors in the Prince's room, standing in for the drawing pass.
- FlameSword.rsrc is a new import: a reimport is needed. Without it the
  sword is not drawn.

## Open

- Native probe of the wake/parry/bob paths; 4:02e0's impassable-cell branch
  (0372), Opponent1 3:09d8, IsCharInKidRoom 6:46a8 (same row only), the
  remaining CheckAlert 70f2 engagement. The turn gate at 6:2690 is now
  implemented (the older note called SEQS 60 a cue).
- What the encounter leads to (TriggerJinnee 4:1d64 and the shadow
  functions 4:24b2-2630 are separate).

## Room-7 playtest follow-up (2026-11-10)

The user's broad bug report prompted a hidden-scene check of level 12,
native room 7. Three concrete defects were reproduced and corrected:

- Crossing behind the sword during SEQS 106 interrupted its rise with a
  combat turn. With pose 214 and the Prince moved from X290 to X430, the
  next port frame switched to SEQS 60. SwordCtrl **6:22e6 -> 2638**, then
  **6:2690-26a6**, rejects the turn for type 10 in poses 213..217. The
  original listing names this routine DoStrike, but this path selects
  SEQS 60; it is a turn request, not sound cue 60. The port now keeps the
  rise and permits the pending side change once pose 171 is reached.
- On the final parry, the sword retained its hover offset all the way to
  rest pose 213. For example Y+7 remained Y+7 after twenty frames. The
  native caller **TestStrike 6:5a74/5a7c -> 4:1c36** takes both surviving
  and final life-loss paths through **4:1c4c-1c56**: AddSound(10), then
  SetCharFloor **4:31fa**, which writes row*120+106. The port only did so
  for surviving parries. Both paths now align to the floor (relative Y0).
- The same final-parry branch omitted sound 10. It now queues the cue as
  on surviving parries, alongside the existing parry/deactivation music.

The wake sequence's brief return to the floor is in the original SEQS 106
data; it is not an AI restart. No change to the authored animation, the
native 25-pixel turn offset, combat ranges, six parries, 480-frame rest
timer or room collision approximation is claimed by these fixes.

The strengthened final-parry test and new turn tests reject the previous
code. Tests include all five blocked poses, a ready-pose turn control and
the actual scene's complete rise after supplying a crossed Prince position.
This is not a physical-input jump replay or full encounter parity.
Verification: flame-sword **18 OK**; combat/enemy-AI/guard-audio **161 run,
OK, 1 skipped** (optional original profile, POP2_RESEARCH_DIR unset).
Dependencies, Ruff F/E9, catalogue and whitespace checks pass. Original CODE
was read offline; no new native CPU probe, full/import suite, hardware
capture, live game/emulator, shared settings/saves or resource write.
These fixes do not close the remaining native-rule gaps listed above.

## Clarified report: rises but does not fight (2026-11-10)

The user clarified that the sword rises (possibly late), then does nothing.
That exact standstill reproduces when the Prince arrives in landing recovery,
rather than as an idle actor already within wake range. The resting sword
gets an NPC control update before it can wake. Generic death registration
correctly clears `Fighter.native_alive`, but the old wake path only restored
HP and `FlameSword.native_alive`. Nearest-opponent selection still saw the
inactive Fighter flag. CheckAlert then downgraded the only sword to waiting
alert 2 instead of engaged alert 3. It finished rising and held indefinitely.

Native wake **4:15f6-160c** calls InitOpp, writes ALIVE=-1, arms the actor
and selects alert 3. There is one native ALIVE word; the port's two stored
representations must agree. `FlameSword` now updates Fighter's flag at wake,
initialization/re-entry and deactivation. Awake control also repairs stale
inactive flags carried by older saves, without a save-format change.
This does not substitute HP for native ALIVE in ordinary guard selection.

The perceived delay is distinct: **4:14d4-14ec** explicitly rejects the
Prince's animation modes 3, 4 and 5 before waking, including landing
recovery. Those native gates and the authored SEQS 106 timing are retained.

Both new regressions fail on ccb48fd. The actual room-7 scene supplies the
Prince's SEQS 20 landing start, then runs recovery, wake, alerts, AI and
contact: the sword must become native-ALIVE/engaged and hurt the Prince.
A supplied inconsistent awake record checks repair within two frames; this
is not an old-file-format or hardware-input replay. The earlier idle-entry
test passed without exercising any resting NPC update and missed this bug.
Verification: flame-sword **20 OK** (3.369s); opponent-selection/alerts/
guard-room/audio **48 OK** (6.957s), no skips. Required dependency, Ruff,
catalogue and whitespace checks pass. No full/import suite, new native CPU
probe, live game/emulator, physical input, shared settings/saves or resource
write. Broader barrier/unarmed/encounter-result recovery remains open.

## Room-7 follow-up: meter, side-room wake and cut (2026-11-19)

The user's port video (parrying the sword east until the forced retreats
carried the Prince into room 12) showed three faults, all reproduced in a
hidden scene from the room-7 start at X 420 facing west:

- **The meter.** The port drew six blue flasks for the sword. DrawOppMeter
  **3:4b64-4b76** loads the selected record and jumps to the clearing tail
  **4c9a** for actors 10, 11 and 0, so the sword never has a meter. The
  user's Macintosh capture of level 12 shows none either.
  `CombatEncounter.health_opponent` now returns no opponent for them.
- **Waking from a side room.** After the sixth parry (SEQS 107, timer 480)
  the next retreat crossed the cut. The sword, still drawn at room 7's edge,
  was stored and restored as a resting record (pose 213 clears its timer,
  as on re-entry), then `wake_skeletons` ran its wake test inside the side
  room view, where the projected Prince is in the sword's room: it rose
  with full life while he stood in room 12, and hovered at room 7's edge
  for good. The wake loop **4:14f0-151e** counts and OpponentClose **13b6**
  reads only the records of the Kid's room (a5-0x4fc2). The flaming sword
  now wakes only when the Prince is in its own room. (The skeleton's wake
  uses the same view; it was not changed here.)

  *2026-11-20 correction:* this rule is a hypothesis, not recovered
  behaviour. The user's Macintosh level-3 run shows a skeleton heap
  rising in native room 15, meter and all, after the Prince has run into
  room 17, which has no records, so the native does wake a side-room
  record and the reading of 14f0-151e above is incomplete. Applying the
  same rule to skeletons broke that video's behaviour and was dropped. The
  sword keeps it because it removes the reported room-12 rise; a
  Macintosh capture of a fallen sword left at room 7's edge while the
  Prince stands in room 12 would settle it.
- **The cut.** Port room changes carried only actors 2 and 4. In
  CutAllOpponents only the running-pose test (**6:44f2-4500**) is limited
  to them; the ALIVE/engaged/direction test (**4582-45fa**) applies to
  every actor, and its helper **463c** adds a type-10 rule (**46a8-46be**):
  the sword follows only on the Kid's row. An awake sword past X 385 (124
  going left) now follows the Prince into room 12 with the life it has
  left; a fallen one stays in room 7. Re-entering room 7 still clears a
  resting timer, so a sword left there rises again when he comes back.

The forced retreat of 25 pixels after each uncountered parry (SEQS 57 and
AddCharX(-9), GenCtrl **6:24da-2506**) and the sword's 20-pixel push-back
(SEQS 103) then 13-pixel advances (SEQS 108) were checked and are native:
six parries move the Prince about three columns.

The route test `test_level_12s_flaming_sword_can_be_passed_as_in_the_video`
depended on the sword staying in room 7. With the cut rule its key policy
(seven back steps, then sheathe) let the sword strike him as he started to
run. The Macintosh capture (02:36-02:40) shows the player back off, parry,
sheathe while the sword is pushed back, and run east with the sword behind
him; its flame then waits at room 12's top-left while he drops to the
middle floor. `swordpass` now backs two (three since 2026-11-20) steps, parries one strike and
sheathes; the Prince reaches room 12 untouched and the sword follows him
there with five lives. This is a key policy, not a timing claim.

Verification: flame-sword 23 OK; the three new regressions fail on the
previous `combat.py`. Combat/AI/selection/temple-route/audio/save suites
429 run, OK, 2 skipped (the optional original-resource export check and
the slow fresh-import test). Original CODE read offline; no new CPU probe,
no live game.

## The strike and the fallen sword at room 12 (2026-11-20)

The user's second Macintosh capture (room 7 to room 12, one minute, 60 fps,
read frame by frame at the game's 12 Hz) shows two things the port lacked.

- **Its strike.** The sword raises its flame upright, tilts it, lunges
  blade first and drops low before it settles; the port's sword struck with
  the guard's SEQS 58, whose poses 151-157 carry other pieces, so this was
  never drawn. DoStrike **6:27bc-27e4** chooses by actor type: 96/75 for
  the Kid and shadow, **109 for type 10**, 58 for the rest. SEQS 109 plays
  poses 218-227 (FlameSword FRAM 69-78, pieces 1, 7, 11, 8, 7, 1, 2, 19, 4,
  10) and moves -6, +9, +3, +9, +6 (a 21-pixel lunge at 224), then back.
  IsStrikingPos **6:5d9a** makes 223/224 parryable and IsTheStrikePos
  **6:5e4a** lands the strike at 224. TestStrike's sound at **5ab4-5af8**
  plays only for a strike that was neither parried nor landed: 239 for the
  sword, 11 for others. The port's parry sound 239 came from misreading
  that branch and is removed; 4:1c4c's cue 10 stays.
- **The fallen sword.** After the sixth parry it lies across room 7's
  right edge (hilt in room 7, blade tip in room 12). The Prince walks into
  room 12; a second later it rises at room 12's left edge and strikes him
  from behind. InitOpps **6:2b7e** first calls CheckSideRoomsForVisibleOpps
  **6:2f4e-308a**: a left neighbour's record with native X > 0x249 (scene
  378), or a right one's below 0x14b (scene 124), is copied into the
  entered room with X -/+ 510 (AddOpp 358e) and deleted from its room
  (3462). The Kid-room wake **4:14f0** (a5-0x4fc2 is the Kid's room) then
  finds it, and its timer was cleared on entry (6:2e34). So the reading of
  14f0 was right; the record moves. The port's `bank_room` view leaves side
  records in their room, which is why the sword once rose there and
  hovered (alert 0 outside the Kid's room), and why the 2026-11-19 rule
  never let it rise. `_take_visible_flame_swords` now moves visible type-10
  records on entry. Ordinary guards and skeletons keep the bank view; the
  same transfer probably explains the level-3 skeleton (P, not changed).

Key policies: `swordduel` presses up at pose 222, advances only when the
sword rests more than 40 pixels away and counters from 161, so the forced
retreats no longer carry the Prince off room 7's west edge; `swordpass`
backs three steps. The duel's other random draws leave the room-14
birdhead duel 9 pixels west, so `LEVEL_12_VIDEO` adds two `nudgeL` after
it. These are replay choices, not timing claims.

Open: the Prince hit in room 7 at X 498 crossed into room 12 and the next
frame stood at X 516 in room 7 (seen in a rejected `swordpass` variant);
not investigated. Static CODE reading, no new CPU probe.
