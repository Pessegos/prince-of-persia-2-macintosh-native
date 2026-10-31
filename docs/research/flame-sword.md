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
  108 its advance (13 pixels in pose 171); 90 a 17-pixel glide.

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
| TestStrike 6:5ae6 | parry cue 239 instead of 11 | parry event sound |
| Defence 4:1206 | it never blocks | `decide_guard_intent` |
| 6:1e1c | advance SEQS 108 instead of 86 | `apply_guard_intent` |
| 6:2592/25d4 | instead of sheathing (SEQS 77) it glides (SEQS 90) | Prince-dead branch |
| AnimChar 4:2ca2 (opcode -2) | its turn first moves AddCharX(25) | `SequenceRuntime` |
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
  remaining CheckAlert 70f2 engagement, DoStrike 6:2690 cue 60 gate.
- What the encounter leads to (TriggerJinnee 4:1d64 and the shadow
  functions 4:24b2-2630 are separate).
