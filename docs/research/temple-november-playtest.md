# Temple Playtest, 2026-11-06

Five reports from the user's playtest of levels 10-13. Evidence is the
Macintosh disassembly and the port's real scene; no native run was done.
Tests: `tests/test_temple_playtest.py`.

| Report | Cause | Status |
| --- | --- | --- |
| Rotating tiles open only on a jump | No native path; see below | Port exception, at the user's request |
| The Prince could grab while falling through one | `catch_ledge` lacked IsLedge's temple rule | Recovered |
| Loose 14:25 did not kill guard 13 | Debris was only tested against the Prince's bank | Recovered |
| A second birdhead's body stood up | Set 0's corpse used for set 7 | Recovered |
| "This screen has no supported entry" | The temple used the rooftops' column 9 rule | Port tool |
| Wall spikes invisible | The caverns' banks drawn in the temple | Recovered |

## Trap doors (tile 26)

TriggerTrapDoor 10:25aa has two callers, confirmed by a byte search of every
CODE resource (`4e ad 0e 5a`): ShakeEm 5:28c8 and Falling 6:0210. CheckPress
5:13ac-13b6 dispatches kinds 11 and 15, not 26, so in the original a walk
across a closed door does nothing. What opens one is a landing (SEQS 11, 17,
20, 22, 46, 63), a fall onto it, a debris impact, and a foot test (SEQS 44),
each in the door's row.

The user wants a step to open it too, so `TrapDoors.step` does this for the
Prince only, on the frames CheckPress would admit, and not while he hangs from
or climbs a door's edge. **This is a deliberate port exception, not recovered
behavior.** A door in the actor's own column starts at phase 1.

The fall needed no exception. IsLedge 4:3f58-3f6e refuses a temple space with
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

Not done: in the temple, MobSpikes' pose exemption is lifted beside a sliding
rock (5:3bc0-3bd4, SlideRockNearSpikes 10:1fa8).
