# Macintosh final-run video reference

Reviewed 2026-11-11 against main `708e490`. This is observation and a bounded
native-code correlation, not a claim that the final level is implemented.

Before extending the mechanics below, fix the subsequently reported early
room-2 trigger and post-NIS room-4 freeze. The
[Claude handoff](final-level-claude-handoff.md) records those blockers and the
new manual/strategy context.

## Capture and limits

The player supplied a 209.016-second Macintosh recording, 1422 x 1070 at
60 frames per second, covering the level-13 exit through the beginning of
the return to the intro. SHA-256:
`b9958ca42dbabf53e9f6eb94d3064d671ff94f888861fedda133e24602716926`.
The video, its private path and the score-table names are not published.
Review frames/contact sheets are local ignored artifacts under
`rendered/final-video-reference/`.

The overview was sampled every three seconds; the tower descent, copies,
final pursuit and score-table exit were then inspected every half second.
Times below are approximate capture positions, generally within half a
second. They are reference points, not recovered game deadlines. Key input
is not recorded, and audio cue timing was not independently compared.
Room labels follow the preserved LEVL links and matching artwork; the shared
8/10 backdrop cannot by itself identify a room-index change.

## Observed route

| Capture time | Visible event | Consequence for the integration |
| --- | --- | --- |
| 00:00-00:17 | Prince leaves level 13 through the final doorway; the temple view remains during the exit hold. | Retain the real completion dispatch and music wait before NIS 3. |
| 00:17-00:38 | Horse flight from the temple to the tower; the horse becomes the golden rooftop figure. | This is the existing NIS 3 recovery, followed by playable tower entry. |
| 00:38-00:43 | Prince moves to the right roof edge and lowers himself down. | Native room 1 is playable, with room 2 below it. |
| 00:43-00:45 | Tower side view; Prince climbs into the window. | The room-2 spatial gate must follow the descent/window entry. |
| 00:45.5-00:55 | Bedroom scene: Princess in bed, real Prince at the left, false Prince at the right casting the spell; fade. | Confirms the recovered NIS 5 scene's role. The bedroom is scripted presentation. |
| 00:56-01:05 | Prince arrives in the chess view, crosses its second screen and reaches the crystals. | Main route is native rooms 4 -> 5 -> 6. The 3/9 tree branch is not visited in this run. |
| 01:05-01:24 | Four purple false Princes; sword approaches/attacks are followed by dissolves, then the final idle figure disappears remotely. | Recover the special copy controller and removal cadence rather than treating these as ordinary guards. |
| 01:24-01:34 | Prince climbs back up the crystals and leaves above. | Room 6 -> 7 is a normal upward route. |
| 01:34-01:44 | Palace left view; Prince climbs to its upper route and moves right. | The expected LEVL route is 7 -> 8. |
| 01:44-01:52 | Purple false Prince stands at the upper right, then retreats down the palace while the player remains above. | The final actor has a movement controller; its presence is observed after the copy sequence. |
| 01:52-02:08 | Blue flaming Prince separates from the body, which stays prone on the upper platform. The blue figure pursues the false Prince through both palace views. | Controlled soul and abandoned body must have separate actor/state ownership. |
| 02:08-02:12 | Both return to the right palace view; blue figure fires a visible projectile across the top; false Prince ignites. | Fireball creation, travel, collision and defeat are required for the final attack. |
| 02:12.5-02:20.5 | Return to the bedroom: a blue burning figure at the left, real red Prince at the right; the burning figure vanishes. | There is a victory bedroom presentation before the illustrated epilogue. |
| 02:20.5-03:18 | Princess and mouse, reunion, horse flight, then the crystal-ball observer. | This is the final epilogue to recover, separate from the port's voyage scene. |
| 03:18.5-03:27 | Hall of Fame, name entry and confirmation, then fade. | Completion includes score entry/persistence before restarting the presentation loop. |
| 03:28-03:29 | The initial story frame/border starts fading in. | The recording captures the beginning of the intro return; it ends before the subsequent intro content. |

## Copy-room observations

At 01:05 there are four false Princes: upper left, upper right, centre and
bottom. The first dissolves around 01:09.5, following a sword approach/attack.
The upper-right figure is gone by 01:15. The bottom figure disappears around
01:22.5-01:23, after another attack. The centre figure then dissolves around
01:23.5 and is absent at 01:24, while the player is still on the bottom ledge.
It is not attacked directly in that final interval.

This fits the code-reading boundary at CODE 9:1574-1594: after computing the
bank count, a remaining count of one selects SEQS 240 if that actor is not
already shimmering and the saved Prince's death counter is negative. It is
not yet a full CPU comparison of that controller. Sword pose, frame flags,
animation state, facing and distance gates follow at 9:1598-16a4. A visible
sword swing followed by a dissolve does not prove that ordinary HP damage
killed the figure. The controller must determine that distinction.

The capture independently confirms that the four are Jaffar's false Princes:
their magenta/purple appearance differs from the red player. Native typing,
SEQS 2, Kid frames and CTBL 25008 are already recovered separately in
[the preparation ledger](final-level-preparation.md#room-6-copy-appearance-2026-11-11).

## Soul, body and final hit

At 01:52 the blue form appears at the player's position; by 01:52.5 the
physical body is visibly prone beneath it. That body remains on the upper
platform while the blue form moves through the two palace views. The false
Prince climbs, hangs, drops and retreats along the architecture. This is
more than an opponent palette change or a normal sword fight.

At approximately 02:10.5 a blue projectile appears in front of the blue
Prince; it crosses the upper platform at 02:11 and reaches the false Prince
around 02:11.5. The target is blue flame by 02:12. Relevant native boundaries
are CODE 9 `ATMFireball` 9:23a8, its actor-6 collision routine 9:24ee, and
the drawing/lifetime helpers near 9:2674-2868. Those routines still need
input/output probes and runtime integration. The recording does not expose
the key combination, projectile admission rules or all possible miss cases.

The initial spell, victory bedroom scene, and the player's previously
reported defeat/laughter scene must be tracked separately. This successful
run contains no player-death example, so it does not verify that defeat
variant or its timing. The relationship between the victory bedroom actors,
native room 11 and the subsequent NIS call remains to be traced end to end.

The right palace view is reached after the copies disappear. This run does
not visit it before solving that sequence, so it does not prove the proposed
conditional reveal or establish that room 10 is an alternate encounter state.
Keep the distinct LEVL room IDs and investigate the scripted actor transfer.

## Final epilogue and Hall of Fame

The existing `ending.json` name is misleading for this task. Its importer
`extract_ending` executes CODE 15:0cf2, NIS 9, for the level-1 -> level-2
voyage. `ScenePrototype.start_ending` labels it `Voyage`, and `finish_ending`
loads level 2. It must not be wired to level-14 victory.

The native generic NIS dispatcher maps NIS 11 at 15:00fa to 15:3c76. That
coordinator opens the Happy resource record at a5-0x26b0 (15:3c80-3c88).
The Happy callback/dialog routines at 15:411a and 15:44b0 are further
recovery targets. Happy.rsrc also supplies the initial NIS 5 spell, so the
resource filename alone does not identify either scene.

CODE 2:4596-45de supplies a separate final completion boundary. With nonzero
remaining minutes and a next-level value greater than 14, it writes the
sentinel -2, calls PlayNIS(11), then HallOfFameDialog 2:1f2c with the minutes
word at a5-0x4fce. If the dialog preserves the sentinel, it clears the next
level to zero; a supplied replacement next level is retained. It then resets
the tree stage at a5-0x27d2 to -1. KeepTime 2:520e-5220 decrements the same
minutes word, so the observed score of 20 is remaining minutes, not elapsed
completion time. Ranking, ties and validation of names still need their own
recovery.

`python -m tools.probe_final_completion` executed 12 original CPU cases:
next levels 15/16, remaining minutes 0/20/60, and a supplied Hall-of-Fame
choice that either preserves the sentinel or requests level 1. Calls and
caller state agree. PlayNIS and HallOfFameDialog are supplied endpoints;
their scene, UI, file I/O and the outer intro/restart loop are excluded.
The zero-minute cases admit no final NIS/Hall calls in this bounded branch.

## Bounded implementation order

1. Recover/probe room-6 controller 9:1526, pose/distance gates, SEQS 240
   rendering/removal and the last-copy handoff. Include the facing draw at
   6:39a2-39c8 without losing native random-state cadence.
2. Recover 9:16fe and the position table/path routines for the final
   false Prince in palace rooms 7/8. Resolve its transfer separately from
   the pre-existing static records shown by developer teleport.
3. Recover the controlled blue form, retained physical body, transformation
   admission, life accounting, fireball and actor-6 collision.
4. Recover the victory bedroom presentation and NIS 11 as a new final
   epilogue program, keeping the existing voyage program intact.
5. Implement Hall-of-Fame entry/confirmation/persistence and the return to
   the intro, using the port's integrated UI and the recovered game rules.
6. Recover the player-death/laughter variant and compare the full sequence
   against another native trace; the successful recording cannot cover it.

No gameplay behavior was changed from the video alone. This milestone adds
the reference timeline, corrects the epilogue target and supplies the bounded
completion probe. Native probe, Ruff, recovery catalogue and diff checks
are the relevant validation; no desktop-exclusive test or live emulator was used.
