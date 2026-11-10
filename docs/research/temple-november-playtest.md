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

## Room 2: scythe collision cancelled guard wounds and turns (2026-11-10)

The user reported that level 10's room-2 guard repeatedly stepped away from
the scythe or cancelled a side exchange, unlike the Macintosh. The room has
no initial guard: its real generator produces the birdhead used here. The
blade/handle are cells 27/28 on the bottom row.

The port's swept wall safeguard for NPC states outside EnemyCollide's
admission also treated an extended scythe as a wall. A nonfatal wound
(SEQS 183, animation state 5) became bump 65 and displaced the guard away
from the blade. An automatic turn (60, also state 5) became bump 64 instead,
followed by repeated corrections near the right wall.

Native FrameAdv **2:65f6-65fa** calls EnemyCollide and CheckGateForOpp for the
guard; the Kid's CheckBarr/Collide path is separate. For type 2, EnemyCollide
**4:62e2-62f4** rejects state 5; its admitted path only accepts walls/blocking
gates. The scythe barrier is in CheckCollide **4:5654-5674/5c76**, with its
extended interval at **5:5fa0**. Evidence is static original CODE and real
scene regressions, not a new CPU probe or complete FrameAdv equivalence.

`wall_correction` now omits only the scythe barrier for ordinary type-2 temple
guards. The existing wall/gate safeguard stays; a control confirms that a
wounded guard still bumps against room 2's right wall. The Prince's scythe
barrier and other environments are unchanged. No AI profile, alert scan,
impassable-cell rule or blade reach/timing changed: native IsImpassable
**3:4dfe-4e08** also rejects tiles 12/13 for some voluntary movements.

Both failure regressions reject the previous code. They use the actual room-2
generator and normal subsequent AI, supply nearby combat positions and an
already-raised phase-5 blade, then run its lifecycle through the cut/death
190. The wound case supplies one successful `_hurt` endpoint, not full
input/contact. The exchange case lets normal NPC control select turn 60,
requires its facing change, and keeps only the exposed Prince invulnerable
to observe the guard. No guard decision is suppressed. These bounded checks
do not replay the entire user's fight or certify all native lure behavior.

Focused check: `tests.test_temple_playtest tests.test_scythes
tests.test_enemy_ai tests.test_terrain`: **226 run, OK, 1 skipped** (39.680s),
with `POP2_SHARED_DESKTOP=1`. The optional original-profile comparison needs
`POP2_RESEARCH_DIR`, which was unset. The existing real-key temple Prince
blade-death regression also passes. Dependencies, Ruff F/E9, recovery
catalogue and whitespace checks pass. No full/import suite or user game,
emulator, focus, settings, save or resource operation. Next bounded check is
further room-2 playtesting with the actual input/attack transition.

## Corpse-held gate after leaving room 24 (2026-11-10)

The supplied recording reports a corpse holding room 24's plate while the
gate on the route left of room 29 closes, then reopens on returning to 24.
In level 10 the exact source is cell **24:24**, link **54**, targeting
**32:9** (one-based native rooms, zero-based cells).

The permanent source timer (31) was already implemented, but TriggerGate
still chose temporary phase 2 and open-wait 237. Once the corpse left the
active actor bank, nothing refreshed that wait. Native CheckPress
**5:1388-13aa** tests ALIVE and exempts skeletons from the permanent timer;
TriggerGate **5:1dcc-1dfa/1e1a-1e36** independently selects permanent phase 3
when native ALIVE is nonnegative or the presser's room differs from the
nonzero displayed-room word. An already open gate also needs its active
phase replaced, not only foreground 255.

Pressure now carries both native ALIVE and displayed-room context through
the link traversal. Dead ordinary pressers latch the source timer and gate;
a living off-screen presser latches only the gate. A zero-HP actor whose
native ALIVE remains true still takes the living branch. Existing impact,
reversible-plate, sound and capacity policies are retained. No save fields
were added. A previously saved temporary gate may need one further visit
to its corpse-held plate to receive the corrected trigger.

The real-level regression supplies a room-29 generated guard's carried/dead
endpoint on the actual room-24 plate. It then runs pressure, gate animation
and actor-bank departure for 160 ticks away: timer 31, foreground 255 and
no active gate remain. The old press entry path reproduces closure to 0.
Separate controls cover closed/open gates, native ALIVE versus HP, and a
living off-screen presser. This is static CODE plus scene evidence, not a
new native CPU probe or a replay of the entire chase/death.

## Continuous combat retreat delayed the camera (2026-11-10)

The second clip shows the Prince retreating from room 29 into 24 while the
old room stays visible. With a fresh Backward event every tick, the port can
restart SEQS 57 at its final ready pose 158 indefinitely. Native CutChar
**6:4a26-4a62** excludes that pose, so the port never reaches eligible idle
170 until key repeat stops or a wall interrupts the retreat. The previous
code reproduces the empty old screen and continues far into room 24.

The port now admits only the Prince's completed retreat at pose 158,
selected SEQS 57, animation state 1. **This is an intentional port input
accommodation**, not a recovered native pose exception. It makes the cut
available one frame before the otherwise eligible idle 170, while retaining
the native facing-dependent body/sword thresholds and coordinate rebase.
Incomplete retreat poses, attacks, wounds and NPCs retain their exclusions.
This does not claim exact Macintosh keyboard-repeat or whole-frame parity.

A real-key regression draws the sword, repeats Backward continuously and
requires the 29-to-24 cut within the entry area, rather than at the far wall.
It fails the previous code. Boundary controls require left >= 510 for the
left-facing rightward exit and reject unfinished, wounded, attack and NPC
cases. The paired videos and native CODE were inspected offline.

Combined focused verification: `tests.test_pressure_plates
tests.test_temple_playtest tests.test_terrain tests.test_gate_audio
tests.test_guard_rooms tests.test_throne_gates`: **248 OK, no skips**
(49.265s), with `POP2_SHARED_DESKTOP=1`. Dependencies, Ruff F/E9, catalogue
and whitespace checks pass. No full/import suite, live game/emulator,
physical input/focus, shared settings/saves or original-resource operation.
Next bounded check is live playtesting these two recorded transitions.

## Guard fall scream and victory music (2026-11-10)

The paired Macintosh/port recordings show level 12 room 9's birdhead falling
from the upper platform to the bottom floor. In the port the long-fall cue
30 can be queued on the very frame that also produces impact 7; overlapping
effects then let the entire 1.67-second scream play over the corpse. The
Prince already stopped cue 8 at impact, but ordinary guards had no matching
stop. Falling **6:00d4-00f2** selects cue 30 for type 2; native impact uses
the single-effect arbitration path (**5:4d84**) which mixing does not replace.

Actual guard terrain impacts now request a cue-30 stop before frame audio
is drained, including a breaking-floor impact that continues downward.
Terminated guard falls (including trap deaths) also clear a pending scream
before drain. A cue queued on the impact frame is suppressed as well as an
already playing voice. In-flight falls keep their scream. The imported PCM,
Prince cue 8 and void-fall policy are unchanged.

Victory was a broader omission: ordinary type-2 KillBird dispatch was absent,
including all four temple levels. Existing skeleton/head/flaming-sword paths
were separate. Fresh original bytes at **5:4bde/4c2c** select song **189**;
the actual temple headers use opponent set 7 and their ordinary birdheads
are actor type 2, correcting the old research note's set/type confusion.
PlayerCtrl **4:3d24-3d70** registers death, counts six pending NPC updates,
then dispatches. The common tail **5:4c9e-4cd4** consumes the request even
when another native-ALIVE opponent or an active same-row generator
(**6:3d28/3daa**) suppresses it, and forbids rooftop environment 5.

The port adds a separate ordinary pending-audio flag/count, not a replacement
for HP, registered death or boolean native ALIVE. Living ordinary control,
sword hits and generation arm the supported cue subset. Full recovery of
every shared pending-word writer is excluded. Cold room-record imports
clear it. Two optional/defaulted fields preserve old saves and allow a new
save mid-count to continue exactly once. No resource reimport is needed.
The trap check additionally exposed a pre-existing save validation limit:
scythe SEQS 190 reaches real corpse pose 256, above the old type-2 maximum
254. That bound now includes 255/256, with a regression saving the consumed
victory state and preserving it on read; other actor bounds are unchanged.

Both initial scene regressions fail the old code. The reported-room fixture
supplies one nonfatal strike near the edge, then runs actual AI, FRAM fall,
landing and audio. Additional checks cover already-playing fatal/surviving
landings, in-flight preservation, sword-death endpoints in levels 10-13,
impact/debris and both spike/scythe death endpoints, the exact registration
delay, native ALIVE versus zero HP, reinforcement and column exclusions,
rooftop silence, corpse re-entry and old/new saves. Trap endpoints supply
the registered death state; they are not full input replays for each trap.
Audio uses the real AudioEngine with a timed backend, not a physical-device
capture. Original clips/bytes/headers were inspected offline; no new CPU
probe, full original fight or complete FrameAdv equivalence is claimed.

Focused check: `tests.test_audio tests.test_audio_integration.SceneAudioTests
tests.test_guard_audio tests.test_guard_deaths tests.test_enemy_ai
tests.test_guard_rooms tests.test_save_game.SaveFormatTests
tests.test_temple_playtest`: **268 run, OK, 1 skipped** (30.770s). The optional
original-profile comparison needs `POP2_RESEARCH_DIR`, which was unset.
Four final targeted native-ALIVE/save/flaming-sword/head-song checks pass.
The final SaveFormatTests group is **29 OK, no skips** (0.633s), including
the previously rejected scythe corpse and pending-count continuation.
Dependencies, Ruff F/E9, catalogue and whitespace checks pass. No full/import
suite, live game/emulator, focus, shared settings/saves or resource writes.
Next bounded task is playtesting the room-9 landing and later temple kills.

## Follow-up: guard scream onset (2026-11-10)

The user's v2 recording exposed a gap in the preceding regression: it checked
the impact stop but never required the scream to start before impact. The
room-9 scene now requires both, and that strengthened test fails on 1e051e0.

NPC FrameAdv **2:65da/65de** runs gravity and movement **4:341a/3464**
before CheckFloor **2:65fe -> 5:1202**. Fresh original CODE bytes resolve
its mode-4 table entry to **5:124e -> Falling 6:00a6** (this table/body
is unmapped in the disassembly listing). Falling tests velocity >=59, with
type-2 cue 30 restricted to <=63 (**6:00b4-00f2**). The port tested the
previous velocity before gravity: the actual room-9 fall reached 60 while
still airborne, but requested cue 30 only on the next frame, when the impact
correctly cancelled it. Type-2 audio admission now uses the updated velocity,
so this fall plays cue 30 for the final airborne frame and stops it on impact.

This change concerns cue scheduling. It retains the existing trajectory,
velocity cap, Prince onset and impact stops. It does not newly implement
native Falling's subsequent velocity-64 marker or claim complete FrameAdv
parity. No music or save changes. Checks use the actual hidden scene and
AudioEngine with timed playback, not hardware output. Additional controls
cover a fall reaching the threshold on impact (no late scream), a short fall
(no scream) and already-playing surviving/fatal impacts.

Verification: guard-audio **10 OK**, terrain/scene-audio/cliff checks
**148 OK**, no skips; dependencies, Ruff F/E9, catalogue and whitespace
checks pass. No full/import suite, CPU probe, live game/emulator, focus,
shared settings/saves or original-resource writes. Next bounded check is
playtesting the same room-9 fall after restart.
