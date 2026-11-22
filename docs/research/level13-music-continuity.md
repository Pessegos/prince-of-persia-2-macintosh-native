# Level 13 music from the checkpoint to the altar

The Macintosh checkpoint recording contains Temple3C near 0.2 s and
Temple3D near 25.0 s. KillBird comes in near 43.3 s. Chasm replaces it on
entry to native room 2 near 47.3 s, and Temple3D starts near 57.7 s. The
room 2 excerpt independently places Chasm at 2.25 s and Temple3D at 12.7 s.
These times are approximate spectral matches to cues 234, 235, 189 and 292.
The two playthroughs take different routes through combat and use random
tracks, so comparison uses foreground cue identity and admission conditions.

`FrameAdv` (2:67da–67e6) flushes requested sounds first, then calls
`PlayAmbient` with the six-byte record at A5−0x3738. `UpdateAmbient`
(5:571c) stores a requested foreground cue and sets the group to −1.
`PlayAmbient` (5:4f92) restores the working Prince from the saved record
and calls 5:550c before evaluating `SpecialMusic` or any cell group.

| Input while a song plays | Native rule |
| --- | --- |
| Room or supporting cell changes during exploration | Keep the current exploration cue. Select the new cell group on the next admission. |
| `OppToFight` becomes true over exploration | Admit a combat cue immediately (5:557e–55cc). |
| `OppToFight` becomes false over combat | Check `GetOppGenPtOnRow` (6:3d28, called at 5:560a) using the saved supporting column. Keep the track with an active point on the Prince's row. Also keep group 2 if an NPC in the displayed bank has the same row, nonzero +0x18 and ALIVE < 7 (5:5636–56be). The port carries the ordinary guard's cue flag and death count. |
| Level 13 script or `SpecialMusic` cue plays | Group −1 keeps ordinary ambience from replacing it. `AddSong` still takes precedence, including the inscription's entry over KillBird. |
| Current cue ends | Select again, including when a reinforcement is still waiting. Group holds apply to active playback. |

`SpecialMusic` uses cue 253 (Approach) in native rooms 4 and 29 when
admitted. In room 4, saved Prince type 1 and HP greater than two take
precedence with cue 252. The explicit altar/death/merge script requests
retain their own triggers. CUST 4025 calls 10:27a6 on entry to the room 2
inscription, and requests 292 when the saved supporting column is at least
nine. The room 2 excerpt shows that the guard can engage during Chasm
without replacing it.

## Checks

`python -m tools.probe_temple_ambient --source ../PoP2-Mac-Code-Recovery`
executes the original CODE on LEVL 2012 (bank 2, level 13). The 268
fixtures vary cue status, guard alert, row, ALIVE and +0x18, room, generation
points, Prince type and HP. The probe also executes the inscription's
`AddSong` and audio flush before testing combat admission. It supplies
saved Prince/ordinary guard records, sound status/start services and
`Rnd(…) = 0`. Scope is cue admission and record writes. Macintosh Sound
Manager playback timing, full `FrameAdv` and guard movement are outside
the probe.

Hidden-scene regressions exercise the checkpoint's actual generation point,
the guard's pending cue, the transition to KillBird, and the level 13 room
themes with a controlled playback clock. The inscription test crosses the
room link with imported SDL audio and checks the one-shot Chasm request
from the right while KillBird is active. The new checkpoint and room-theme
regressions both fail on the prior implementation.
