# Macintosh level 12: route from the player's video

Reviewed 2026-11-14, against main `b6a7c31`. This is a textual walkthrough of
the supplied successful Macintosh recording, for an agent that cannot watch
video. It supplies a route to reproduce in the port; **a complete port replay
has not been performed**. No gameplay code was changed for this handoff.

## Read this first

The recording resolves two important limitations of the earlier
[temple route audit](temple-route-audit.md):

1. **Room 16 is not an obligatory starting detour.** From room 8, climb to
   the top floor, jump to dislodge the loose floor above, and climb through
   the resulting hole into room 1. The video does this at 00:06-00:19.
   The old assertion that hole 8:21 is the only way out is contradicted by
   this Macintosh run.
2. **The room-9 guard is part of the gate puzzle.** The player gets behind
   him, then fights towards the right edge of the left platform. The guard
   falls and his corpse remains beside the statue on the lower floor at
   00:44. This is consistent with the proposed corpse on plate 9:24 holding
   gate 5:2. The player subsequently traverses the three northern gates
   without racing back from that plate. A peaceful search omits this actor.

The successful order is: prepare the northern passage, pass its gates,
descend past the flaming sword, step on the exit plate in room 14 from above,
then return west through rooms 16, 6, 17 and 10 to the room-9/room-8 platforms
and the exit in room 7. **The genie and rooms 18/23/24 are not visited.**

## Coordinates and evidence limits

Rooms here are **native one-based**. In `room:cell`, cell is **zero-based
0-29**, with rows 0-9 / 10-19 / 20-29. Subtract one from a room number for
port state. Left/right refer to the screen. Top/middle/bottom refer to the
three physical floors, not decorative ledges or the supporting-foot anchor.

Source: the player's `Macintosh Level 12 converted.mp4`, 280.433 seconds,
1422 x 1070, 60 fps. SHA-256:
`040f55d78e9b03a006c08e4fb1963ce00ef595ebf6978e34231836911c010997`.
The capture begins in room 19 and shows entry into the open room-7 stairway
at about 04:22. It ends during the exit hold; it does not show level 13.
The original video and its private path are not committed.

The whole capture was reviewed with two-second contact sheets, followed by
one-second samples of 00:16-00:28, 00:38-00:58, 01:50-02:32 and
03:44-04:04, and half-second samples of 00:28-00:39. These are approximate
capture timestamps, not a key recording or native frame deadlines. No claim
is made about exact button durations, attack/parry inputs, hidden actor
state, or independently measured audio timing.

Room identities were matched to scenery and preserved LEVL:2011 links.
A whole-capture comparison against the 26 rendered room backgrounds also
checked the two-second samples (excluding the final fade); room labels were
then reviewed visually. This is identification using port-rendered original
artwork, not proof of equivalent gameplay.
Plate destinations below were read with the existing port decoder from the
imported resource. That is a useful correlation, **not an independent native
decoder check or a new CPU probe**. No new CODE semantics were recovered.

Local ignored evidence is under `rendered/level12-video-reference/` in the
primary worktree: `sheet-01.jpg` through `sheet-07.jpg`,
`detail-sheet-16.jpg`, `detail-28-39.jpg`, `detail-sheet-38.jpg`,
`detail-sheet-110.jpg`, `detail-sheet-134.jpg`, `detail-sheet-224.jpg`,
`room-atlas.jpg` and `route-overview.jpg`. The overview has selected frames
with room/action labels; Claude can inspect still images even without video.
The atlas is rendered port scenery used for identification, not a native
screenshot or proof of pixel equivalence.

## Walkthrough, in capture order

| Time | Native rooms | Action and visible result |
| --- | --- | --- |
| 00:00-00:06 | 19 -> 8 | Leave the entrance to the left along the bottom floor. In room 8, stop at the right-hand climbing shaft. |
| 00:06-00:18 | 8 | Climb from the bottom floor to the middle ledge and then the top floor near column 6. Jump upwards underneath loose 1:26. Rubble appears below; the ceiling passage becomes usable. |
| 00:18-00:23 | 8 -> 1 -> 3 | Climb through the hole into room 1's bottom passage. Move right, jumping its gap, into the bottom-left part of room 3. |
| 00:23-00:27 | 3 -> 19 -> 3 -> 1 | Dislodge loose 3:20 at the left edge of the shaft. The player briefly hangs into room 19 below; rubble is visible at its bottom-left plate by 00:25. Climb back and return left into room 1. The plate/gate correlation is 19:20 -> 3:2, preparing the later top-floor crossing. |
| 00:27-00:34 | 1 -> 8 -> 9 -> 5 | Return down into room 8, go left along its top floor and emerge on room 9's top-right platform, opposite the birdhead on the left platform. Jump up into room 5's bottom passage. |
| 00:34-00:38 | 5 -> 9 | Traverse room 5's bottom passage and descend through its left loose-floor area onto room 9's left platform, behind the guard. This detour changes the side of the fight. Do not replace it with killing the guard on his starting tile. |
| 00:38-00:44 | 9 | Manoeuvre until the Prince is left of the guard, then fight towards the right edge of this left platform. The guard goes over the edge and lands dead on the bottom floor beside the statue. The video shows the fall and corpse, but does not distinguish an HP kill from a fatal fall as the cause of death. |
| 00:44-00:55 | 9 -> 5 | Leave the corpse in place. Climb into room 5 at the left. Cross its lower passage to the right, jump beneath loose 5:18, then climb onto the right middle ledge. Its falling slab lands at plate 5:28; this opens 5:0. |
| 00:55-01:04 | 5 -> 9 -> 5 | Return down/left through room 9's upper-left platform. Rubble is now visible on plate 9:0, consistent with loose 5:20 falling onto it; this opens 2:9. Climb room 5's left bottom and middle ledges, then jump across to the right upper platform. |
| 01:04-01:14 | 5 -> 4 -> 5 | Climb from room 5's right upper platform into room 4's bottom-right recess. Climb one more ledge and dislodge loose 4:17. At 01:12-01:14 rubble is visible on 4:27; it holds 5:1 open. Return down into room 5. |
| 01:14-01:20 | 5 -> 2 | From the top-right platform, jump left across the shaft to the three gates at 5:0-2. Go through them to room 2, entering at the upper right, then drop to the statue's middle platform. This is after the guard/corpse and all three slab preparations. |
| 01:20-01:28 | 2 | Drink the flask on the middle-left platform, then return to the right-hand ledge. This is the ordinary flask at 2:11, not the genie. The middle platform's loose 2:12 leads to the lower plate 2:22, which opens 1:3. |
| 01:28-01:40 | 2 -> 10 -> 9 | Descend into room 10, move right along its bottom passage to room 9, pass the corpse, and climb room 9's right-hand ledges to the top-right platform. |
| 01:40-01:55 | 9 -> 5 -> 1 | Climb through room 5's lower-right, middle-right and top-right ledges, then go right into room 1's top passage. Run through its gates; plate 1:5 opens 1:9. The first crossing of room 1 was along the bottom; this crossing is along the top. |
| 01:55-02:02 | 1 -> 3 | Enter room 3 at the top-left. Advance onto/dislodge loose 3:3, drop from the right edge and catch the middle-right shelf beside gate 3:18. Climb back to the short top-right lip on the left side of gate 3:8. |
| 02:02-02:15 | 3 -> 21 | Jump vertically from that lip to catch the bottom shelf of room 21 above. Pull up and move left across its bottom passage, dislodging loose 21:27. This is a short upward detour, not the route through room 11. |
| 02:15-02:31 | 21 -> 3 -> 11 | Lower back to room 3's top-right platform. Approach the gate area, then drop outside the right edge, catch the middle shelf and move right through gate 3:18 east into room 11. The video contains repeated positioning jumps here; it supplies no exact minimal input macro or offscreen gate-state trace. |
| 02:31-02:39 | 11 -> 7 | Descend into room 7 and approach the sword lying on the top platform. The sword wakes and follows the Prince as he runs right. The capture does not show a sustained sword fight or prove that this encounter must be won. |
| 02:39-02:49 | 7 -> 12 | Continue right to room 12, lower/catch its middle platform, pull up, then lower to the bottom-left passage. Run **left** back towards room 7, rather than east through 12:21. |
| 02:49-02:52 | 12 -> 7 -> 14 -> 22 | Cross room 7's bottom-right gap and drop onto room 14's **top-right** ledge. Step across plate **14:8**, which opens exit **7:23**. Continue right into room 22. This upper-floor visit is the exit-opening step; the later bottom-floor fights are the return journey. |
| 02:52-03:02 | 22 -> 14 | Drop from room 22's upper-left ledge to its bottom floor (a flask is visible), then run **left** to room 14. Crawl under its swinging blade. A birdhead approaches from the left. |
| 03:02-03:18 | 14 | Fight and kill that guard on the bottom floor. At 03:16 the corpse lies beneath/near the blade. This corpse is distinct from the room-9 gate-puzzle corpse. |
| 03:18-03:28 | 14 -> 15 -> 16 | Continue **left** through room 15 into room 16's lower-right passage. Pass its lower gate and leave to the left. This is the westbound return route; do not reverse toward the eastern genie branch. |
| 03:28-03:44 | 16 -> 6 | Crawl under room 6's right blade and fight its birdhead. Kill him, then crawl left past the other blade. The room-6 fight happens late in this run, after the room-9 puzzle and the exit plate. |
| 03:44-03:48 | 6 -> 17 | Enter room 17's bottom-right recess, where a flask is visible. Move left of gate 17:26 and begin climbing the stacked ledges at column 6. No genie release is seen. |
| 03:48-04:00 | 17 | Climb from the bottom to the middle and top shelves. Dislodge loose 10:25 above the top shelf; rubble appears below at 17:25. Climb through this ceiling opening. |
| 04:00-04:04 | 17 -> 10 -> 9 | Pull up into room 10's bottom passage, then run right to room 9. This is a continuous geographical return from the west. The similar shafts in rooms 17/18 and statues in rooms 10/24 must not be confused. |
| 04:04-04:18 | 9 -> 8 -> 19 | Pass the existing room-9 corpse, climb the right ledges, run across room 8's top floor and lower into its right shaft to the bottom. Continue right into room 19. |
| 04:18-04:22 | 19 -> 7 | Run right along room 19's bottom passage to room 7. Enter its now-open stairway at 7:23. The exit-entry animation completes and the view holds until the video ends. |

## Why the genie search was a distraction for this route

The old `LEVEL_12_GENIE` trace is still useful partial port evidence, but it
solves a branch this successful recording does not take. The visible drink at
01:20-01:28 is the ordinary flask in room 2. The later shaft with three ledges
is room **17**, reached to the west of room 6, not room 18. The statue passage
at 04:00 is room **10**, directly above room 17, not room 24.

The exit opens from **14:8** as the Prince arrives from above at about 02:50.
He then returns west via the two blades in room 6 and the ceiling exit from
room 17. There is no need to insert room 23's genie into this walkthrough.
The recording shows the room-9 corpse still in place on both returns.

## Mechanism checklist for a port replay

These destinations were checked in LEVL:2011 with `PressurePlates.link`:

| Preparation | Destination | Evidence to preserve when replaying |
| --- | --- | --- |
| Loose 1:26 from below | Hole from room 8 to room 1 | Early climb works without entering room 16. |
| Loose 3:20 falls to plate 19:20 | Gate 3:2 | Rubble at the bottom-left of room 19 by 00:25. |
| Guard lands at/beside plate 9:24 | Gate 5:2 | Corpse remains while the Prince climbs away; verify actual native-ALIVE, pose and supporting-foot eligibility in the port. |
| Loose 5:18 onto plate 5:28 | Gate 5:0 | Rubble visible by 00:55. |
| Loose 5:20 onto plate 9:0 | Gate 2:9 | Rubble on room 9's upper-left platform by 00:56. |
| Loose 4:17 onto plate 4:27 | Gate 5:1 | Rubble visible by 01:12; avoids a momentary press. |
| Plate 2:22 | Gate 1:3 | Correlation from resource; exact contact is not shown in a dedicated close-up. |
| Plate 1:5 | Gate 1:9 | Crossed on the later top-floor run. |
| Plate 14:8 | Exit 7:23 | Crossed on the short top-right ledge at about 02:50, before the bottom-floor return. |
| Loose 10:25 onto plate 17:25 | Closes gate 17:26 | Rubble visible by 03:56; the hole also provides the upward route to room 10. |

## Port replay, 2026-11-14

The port finishes the level along this route. `LEVEL_12_VIDEO` in
`tests/test_temple_routes.py` is 109 macros of
`tools/audit_temple_routes.py`. They are real keys from a fresh level load,
with opponents on from the start and no supplied corpse, gate or slab. The
replay enters the open room-7 stairway after 4,512 frames.

The one supplied value is the Prince's life. The recording's bar shows twelve
flasks on arrival from level 11, while a level loaded on its own starts with
three. `replay(..., life=12)` sets both his life and his maximum. With three,
the flaming sword kills him.

Fights use three macros that react to the screen as a player would:

- `strike` is the room-9 guard met on landing, a fixed series of stabs.
- `swordduel` parries the flaming sword: up at its wind-up pose 152, forward
  while it rests.
- `duel`/`duelfar` fight the guards in rooms 14 and 6: parry at pose 152, stab
  in reach, step closer otherwise.

They are key policies, not state edits.

### What the replay confirms

- **The start:** plate 19:24 opens gate 8:29. A running leap left clears the
  closing plate 19:23.
- **Room 8:** a jump at room 8's top floor (facing right, beside the gap)
  knocks loose 1:26 down to 8:26, and the Prince climbs up into room 1.
- **The four slabs:** 3:20 lands on 19:20, 5:18 on 5:28, 5:20 on 9:0 and 2:12
  on 2:22. Each holds its gate for good: 3:2, 5:0, 2:9 and 1:3 (timer 31,
  gate at 255).
- **Gate 5:2:** the room-9 guard, fought from the left as he turns on the
  landing Prince, falls off the right edge of his platform and dies on plate
  9:24. His body holds gate 5:2 for good. The hypothesis is confirmed in the
  port. When the same guard is killed on his platform instead, the gate stays
  shut.
- **The sword and the exit:** the flaming sword wakes as the Prince lands on
  room 7's top floor. Parried six times, it drops for 480 frames. Plate 14:8
  then opens door 7:23 to 79, its open position, and the door stays open
  until the end.
- **The way back:** the room-14 guard comes in from room 15 after the Prince
  crawls under its blade. The room-6 guard is fought after crawling under the
  right blade. The climb in room 17 goes up through 10:25 into room 10, then
  on through 9, 8 and 19 to the stairway.

### Where it differs from the video

These differences come from the keys, not from a known rule difference:

- Loose 3:20 is dropped from beside it by three jumps (its third shake), not
  by hanging into room 19.
- Room 3 is crossed to room 11 through gate 3:18 (opened by plate 3:0), with
  no detour to room 21. Loose 21:27 is not needed.
- In the video the Prince runs east with the sword behind him. In the port he
  lands eight pixels to its left, it pushes him back towards the edge, and
  fleeing failed in every tried timing. Parrying it down is the port route.
  Where the port's landing differs from the native one is not measured.
- Gate 5:1 is passed while open, from plate 4:27; the slab of 4:17 is not
  kept on it.
- No exact native timings, audio or hidden state are compared. This is a
  playable-route check, not native equivalence of the fights.

## Next bounded work for Claude

*Done on 2026-11-14 for the port (above). Still open: where the native
Prince lands beside the flaming sword, and the native timing of the three
fights. The original task text follows.*

Reproduce the early room-8 ceiling escape and the northern guard/slab puzzle
from a fresh level load with opponents enabled throughout. Record actual
keys and resulting room/row/position/plate/gate state at the milestones above.
Do not supply the corpse or pre-open gates in a claimed complete replay.
The video makes the gate-5:2 hypothesis actionable, but is not a regression
test of the port's death/press scheduling.

Then reproduce the room-3 -> 21 -> 3 -> 11 descent, the escape past the
flaming sword, the landing on 14:8, and the westbound return through
16 -> 6 -> 17 -> 10 -> 9 -> 8 -> 19 -> 7. Keep earlier `LEVEL_12_GATES` /
`LEVEL_12_GENIE` results labelled partial until one uninterrupted fresh-load
replay reaches and enters exit 7:23. Do not force the search to visit the
genie or require the room-6 fight before the room-9 guard puzzle.

Existing native leads remain CheckPress/PushPlate, including CODE 5:252e
for dead-actor plate handling, and the genie endpoints in its dedicated
research note. This review adds visual evidence, not newly executed native
callers/endpoints. No game, emulator, live user window, saves, settings or
original resources were operated or modified. Documentation validation:
room/link correlation, timestamp review and `git diff --check`; no gameplay
suite or native CPU probe was run for this document.
