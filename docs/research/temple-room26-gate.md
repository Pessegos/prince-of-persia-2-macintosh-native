# Level 11 Room 26 Fatal Hit And Gate

The supplied Macintosh capture shows the left-facing birdhead shift west on
the fatal hit before it falls. In the port capture it falls against the right
gate, with its head beyond the visible opening. The level has a close plate
at native room 26 cell 18 (link `0x49`) and an iron gate at cell 19. The
opener at cell 13 (link `0x50`) targets the same gate.

`CheckStab` 6:51f2 enters the floor-death selector at 6:5474. For a
left-facing opponent, 6:55da-5636 checks the tile behind the cached foot,
then the foot tile itself. When either is kind 4, `4:3b30` rebases its column
and the death selector sets X to the gate anchor minus 31. The gate phase is
irrelevant. The regular type-2 death offset at 6:56d6-56e8 and the first pose of
SEQS 85 then place this guard at native X 674 (scene X 467), pose 179. In the
replay the pre-hit X is 688 (scene X 481). The settled pose 185 is at native
X 672 (scene X 465), with the supporting foot still in column 8 on the close
plate. Before the fix the scene X values were 508 and 506.

`CheckPress` 5:127e still depresses the close plate under this corpse.
`TriggerGate` 5:1e5c-1e80 ignores its closing request when `IsDeadPos` 4:47a0
accepts the pose and the native ALIVE word is at least 2. The port now feeds
the existing corpse counter to this check. `InitOpps` 6:2e18-2e20 restores a
settled corpse at ALIVE 7 with the pending cue cleared. The port represents
that as its saturated count of six with no pending cue. Previously the
corpse's close request replaced the opener's phase 2 with phase 4 every
frame, holding the gate at zero and repeatedly requesting iron slam cue 275.

```powershell
.venv\Scripts\python.exe -m tools.probe_room26_gate --source ..\PoP2-Mac-Code-Recovery
.venv\Scripts\python.exe -m unittest -q tests.test_temple_playtest.TemplePlaytestTests.test_room26_fatal_hit_and_gate_reopening tests.test_pressure_plates tests.test_opponent_records
```

The CPU probe runs six hits and twelve pressure cases on LEVL 2010 with
original Birdhead FRAM/AFRM, SEQS and the native cell and coordinate routines.
It supplies the actors, hit entry and active gate record, including one
open-gate phase control. It loads real sequence bytes through a supplied
resource lookup and treats sequence-handle memory traps as inert. Sound and
redraw calls are sinks. The Prince's target lookup 6:36f2 returns -1. The
five post-hit animation steps supply the ALIVE word and call animation,
movement and frame loading directly. They exclude full AI, scheduling,
drawing and audio playback.

The port test positions the fighters after the swap and sends Ctrl through
the scene input. It then places the Prince on cell 13 and ticks the real
plate and gate controllers while the corpse still depresses cell 18. On
`559029b`, both the six-frame position trace and the gate check fail. With
the fix the guard matches the native trace and the gate reaches waiting
position 237 with one opening cue and zero slam requests.
