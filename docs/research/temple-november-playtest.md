# Temple Playtest, 2026-11-06

Five reports from the user's playtest of levels 10-13. Evidence is the
Macintosh disassembly and the port's real scene; no native run was done.
Tests: `tests/test_temple_playtest.py`.

| Report | Cause | Status |
| --- | --- | --- |
| Rotating tiles open only on a jump | CheckTrapDoor 10:2540 was missing | Recovered |
| The Prince could grab while falling through one | `catch_ledge` lacked IsLedge's temple rule | Recovered |
| Loose 14:25 did not kill guard 13 | Debris was only tested against the Prince's bank | Recovered |
| A second birdhead's body stood up | Set 0's corpse used for set 7 | Recovered |
| "This screen has no supported entry" | The temple used the rooftops' column 9 rule | Port tool |
| Wall spikes invisible | The caverns' banks drawn in the temple | Recovered |

## Trap doors (tile 26)

FrameAdv calls CheckTrapDoor 10:2540 every frame in the temple, for the Kid
(2:63e6) and for each opponent (2:6642). With FRAM bit 0x40 set, Y exactly on
the row's floor and an actor other than the shadow (type 1), it reads the
supporting cell. Tile 26 with low foreground bits clear goes straight to the
constructor 10:25e8, at phase 1. So anyone who walks or runs onto a closed door
opens it, including a guard. TriggerTrapDoor 10:25aa, from ShakeEm 5:28c8 and
Falling 6:0210, is the second way in, for a door away from the actor's column
or struck from above.

The first reading of this report was wrong: it searched for callers of 10:25aa
and read CheckPress, and concluded the original had no such rule. The user
insisted it did. A search for pc-relative calls of 10:25e8 found 10:25a2.
`TrapDoors.check` is the recovered rule, not a port exception.

The fall is native too. IsLedge 4:3f58-3f6e refuses a temple space with
bit 0x80, and an open door is space 0x81. `jump_up_ledge` had that rule;
Catch 4:393e, which also calls IsLedge, did not. `catch_ledge` now refuses it,
so the Prince falls past the door's neighbours with Shift held.

The routes of levels 11 and 12 had used the catch this rule removes. Both were
searched again and replay from a fresh load (`temple-route-audit.md`). The
level 12 route holds the same three gates; it remains unfinished.

## Debris and sleeping guards

MakeRubble 5:3576 tests the loaded bank when the debris is in the Prince's
room, and otherwise the saved records (5:3602-362c): ContactOppInfo 5:377e,
then CrushOppInfo 6:29fa. The port did this only for the ruins, so debris
falling into a room the Prince had not entered passed through its guard.

`CombatEncounter.crush_offscreen` now does it for sets 0 and 7. CrushOppInfo
6:2aa2 writes SEQS 22 at cursor 0 and life 0, so the guard plays his death when
the room is entered, and GuardRoomRecord already restores that. Set 2 only
clears the skeleton's +0x1c word (6:2a8c-2a9c) and is left out.

Loose 14:25 and guard 13 are the reported case. Rooms load on demand in the
port, so the first debris in a room loads its records.

## Corpses

GetOppDeadSeq's table 4:00ac is keyed by the opponent set (0x21a4):

| Set | Corpse by bank slot |
| --- | --- |
| 7 (temple) | slot % 5: none, 191, 192, 193, 194 (poses 252-255) |
| 0, environment not 6 | slot % 2: none, 195 (pose 228) |
| others | none |

The port used set 0's rule everywhere. Pose 228 in Birdhead.rsrc is an upright
frame, so a birdhead in an odd slot stood up. Set 2 now also keeps pose 185, as
the table says. Live deaths and room reloads share `corpse_sequence`.

## Development warps

The temple fell through to the rooftops' branch, which needs floor in column 9.
It now uses `room_entry`, as the caverns and the palace do. Every room warps,
in all four levels. Eight are shafts with no floor to stand on (10: 6, 30, 31;
11: 11, 14; 12: 13; 13: 14, 15), so the Prince arrives in the air and falls.

## Wall spikes

10:1296 is the temple's InitCaveSpikes: pieces from 104, its own offset table
(DATA a5-0x2b18, -0x2b08, -0x2af8). TriggerSpikes 5:40d6-411e places the MOB
at column*51+66, row*120+105 outside the caverns (63 and 106). The port drew
the caverns' pieces, which in Temple.rsrc are scenery shapes. The rendered
phases show spikes leaving the wall, and the blood bank at 240.

In the temple, CheckSpikeHit's exemptions are lifted beside a sliding rock
(5:3bc0-3bd4). All three lead there: the body past the reach (5:3b82), too high
(5:3ba8), and the poses 15 and 121-132 (5:3bb8, 5:3bbe). Skeletons, mice,
sequence 85 and dead poses return earlier and stay exempt, and the spike must
still be in a lethal phase.

SlideRockNearSpikes 10:1fa8 asks SlideRockInCell (margin 25) about the next
cell, then about `ReadCell`'s cached column plus two. That cache was moved by
the first query, so the columns are +1 and +3 and +2 is never asked. The
routine restores the cache afterwards. It reads like a slip, and it is the
original's behaviour.

`tools/probe_temple_spike_rock.py` runs 10:1fa8 for all 15 wall-spike cells of
levels 10-13 with a rock in the room or up to two rooms left or right (19,032
cases), and CheckSpikeHit on one cell with no rock, a rock near and a rock far,
across poses, heights, armed, facing, edges, phases and actor types (7,560
cases): 0 mismatches with real ReadCell, GetSlideRockX, IsDeadPos and MobSpikes.
Changing +3 to +2 in the port gives 440 mismatches at a coarser sweep. The
impalement and the MOB lookup are sinks, and the rock and the edges are supplied.
The port still stops at the first spike of the two columns where the native
loop goes on; that matters only for two adjacent lethal spikes.

No temple spike cell has a rock cell in its row except level 12's room 10 (spike
at 9, rock at 0), so few rooms will show this in play.

## Falling grip, room 14 to 13 (2026-11-09)

The user's paired videos show loose 14:25 falling while the Prince hangs in
room 13. The Macintosh lets him fall; the port kept its protected ledge
controller after the supporting tile disappeared. GenCtrl 6:196a-1990 checks
the cell above the actual supporting foot and calls release 6:1a84 for space,
after the input and wall branches. `update_native_ledge` now includes that
check in the temple. Climb input retains its native priority. Evidence here
is the supplied video and static CODE reading, not a new native CPU probe.

The user explicitly requested a lethal slab impact on the guard, although the
Macintosh video leaves him alive. Releasing the Prince earlier makes the guard
advance: mode 5 exempts him from Crushed 6:28f0, and the advance's supporting
foot can move to column 6 while his body remains under the slab in column 5.
Live ordinary temple guards now additionally use swept slab/body contact and
fatal SEQS 22. This is an **approved port exception**, scoped to environment 2,
actor type 2; it preserves the ordinary death/persistence path. The Prince,
special actors and other environments retain their existing contact rules.

The regression starts at the last falling frame before the 14-to-13 camera
cut, then runs the real Catch, held Shift, loose-floor lifecycle, active guard
and landing. It rejects the prior hanging-in-air behavior and requires the
guard's death. A permanent-floor control retains its grip; body-contact controls
exclude dead actors, other rooms/rows and a body outside the slab's width.

Verification: `python -m unittest -q tests.test_temple_playtest
tests.test_ledge_controls tests.test_loose_floors`: **73 OK, no skips** (14.385s),
with `POP2_SHARED_DESKTOP=1`. Dependencies, Ruff F/E9, recovery catalogue and
whitespace checks pass. No global/import suite, emulator or user's game window
was operated. The recordings and extracted comparison frames remain local.

## Guard landing reaction and wall-spike fall (2026-11-09)

The next paired videos show a standing jump from room 14 landing behind the
room-13 birdhead, then the guard being pushed off the right edge. Two missing
inputs explain the differences:

- HitFloor **6:048a-0492** sets movement/noise word **a5-0x4f9e** for an audible
  Prince landing. AutoCtrl **4:053a** uses it to turn toward a landing behind
  the guard. The port played the landing sound but omitted this signal.
  Temple landings now set `callback_flag`; the existing close-behind draw and
  selected-sheathing veto in the guard controller are preserved.
- **Superseded diagnosis; see the follow-up below.** The initial patch passed
  the AFRM sword extension into AlignFalling **4:4b54/4ba8**, based on its calls
  to GetSwordLength **4:5e6e**. That made the supplied recoil hit the spikes
  without widening trap ranges or changing falling velocity, but overlooked
  the caller's earlier clearing of armed. The follow-up removes this adjustment.

Both initial integrations were restricted to environment 2. Evidence is static original
CODE reading, the supplied recordings and real FRAM/AFRM scene regressions;
no new native CPU probe or full-frame equivalence is claimed. The tests reject
both previous behaviors. The guard recoil is supplied (SEQS 104), with only
his next AI decision suppressed while the actual fall and spikes run.

The user also reported the Prince landing beside the spikes, then confirmed
that he died on retry. A normal running-Prince regression passes with God Mode
off; no change to his invulnerability policy was needed. The fixed turn and
impalement were inspected in the local `rendered/temple-guard-turn-spikes/fixed.png`.

Focused check: `tests.test_temple_playtest tests.test_wall_spikes
tests.test_enemy_ai tests.test_guard_deaths`: **143 run, OK, 1 skipped** (12.570s).
The optional original-profile comparison requires `POP2_RESEARCH_DIR`, which
was unset. Dependencies, Ruff F/E9, recovery catalogue and whitespace checks
pass. No global/import suite or user's game/emulator window was operated.

## Follow-up: a sword hit still sent the guard past the spikes (2026-11-09)

The user's post-update recording exposed a gap in the supplied-recoil test:
it covered SEQS 104 with subsequent AI suppressed, while a nonfatal sword hit
uses SEQS 183. Supplying that hit at room 13's right edge, then running normal
AI and physics, reproduced the surviving guard beside the spikes.

StartFall **4:4ca8-4cb2** clears armed **a5-0x503c** before AlignFalling
**4:4d90**. GetSwordLength **4:5e74-5e7a** consequently returns zero here.
The previous sword-extent adjustment omitted that ordering and compensated
for the symptom in one recoil case; it has been removed. The actual missing
input was the guard's armed flag: the Prince's scene already clears it on a
fall event, but the guard's terrain-event consumer did not. Temple guards now
clear it too, before environmental spike checks. CheckSpikes **5:3c42** then
uses its existing unarmed approach threshold, and CheckSpikeHit impales the
guard normally. Landing retains its existing rearming behavior. Other
environments' guard event handling is unchanged.

The new regression supplies one nonfatal `_hurt` endpoint (not the player's
full input/strike collision), requires SEQS 183 and an unarmed live fall, and
continues with normal AI through death SEQS 188/189 and spike foreground 240.
It fails on the prior update. The earlier recoil, standing-jump turn, normal
running-Prince death, slab/grip and related terrain/trap regressions pass.
Evidence is the supplied recording, static original CODE ordering and the
real hidden scene; no new native CPU probe or full-frame equivalence claim.

Focused verification: `tests.test_temple_playtest tests.test_wall_spikes
tests.test_guard_deaths tests.test_terrain`: **197 OK, no skips** (38.631s),
with `POP2_SHARED_DESKTOP=1`. Dependencies, Ruff F/E9, recovery catalogue and
whitespace checks pass. No global/import suite or user's game/emulator was
operated. Next bounded check is any further playtest report with its actual
combat transition; this fix does not claim complete temple parity.
