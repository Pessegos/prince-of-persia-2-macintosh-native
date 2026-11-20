# Level 12 Guard Fall From Room 20 To Room 18

The Macintosh recording shows the birdhead at the bottom of room 18. The port
recording shows it on the intermediate ledge. Room 18 cell 27 is the opener
at row 2, column 7. Its link chain starts at 179 and opens the gates at
room 18 cell 19 and room 12 cell 21.

In the original, CutOpponent 6:42dc-433a leaves an actor in mode 4 in its
current bank while a down link exists. Falling 6:0156-026c tests successive
floor rows in that coordinate system, following the map link for the cells.
Subtracting the 365-pixel cut during the fall delays the intermediate floor
test relative to the birdhead's sideways drift. The port now preserves the
floor-relative height with a 360-pixel rebase during its early room transfer.
It also carries speed 64 after Falling 6:00ee-00f0 queues cue 30. Gravity
4:3446-344e preserves a speed already above the clamp.

HitFloor 6:046a-0478 advances to the corpse pose before CheckPress 5:127e
(called from 2:6602), with the incoming frame's supporting column and FRAM
auxiliary word still loaded. In the X349 fixture the corpse finishes at X400
with cached column 7. Reloading its FRAM changes the supporting column to 6.
The port carries the incoming contact into its plate check on that tick.
Its existing offscreen pressure rule selects permanent gate phase 3, while
the plate itself can release.

The probe supplies a ready, left-facing, two-life birdhead in room 20,
with the attack already admitted by the caller. It uses original LEVL,
Birdhead FRAM/AFRM and SEQS. It executes CheckStab 6:51f2, AnimChar,
Move, LoadFrame, CheckFloor dispatch, CheckPress and Cut. X345, 348 and
349 land on cell 27. Applying Cut at row 3 sends all three to the intermediate
ledge. X350 reaches that ledge in the original schedule as well.

The probe supplies no catch or sliding-rock contact, inert sound stops and
redraw, and in-memory resource handles with inert lock traps. Sound requests
are recorded by the base harness. It supplies the frame call order and omits
AI, full bank transfer/reload, gate animation and rendering. The scene test
supplies the fighters immediately before contact and runs the regular contact,
animation and plate paths. Both linked gates reach 255 and remain there
after the ordinary wait interval with the Prince still in room 20.

```powershell
.venv\Scripts\python.exe -m tools.probe_room18_guard_fall --source ..\PoP2-Mac-Code-Recovery
.venv\Scripts\python.exe -m unittest -q tests.test_temple_playtest
```
