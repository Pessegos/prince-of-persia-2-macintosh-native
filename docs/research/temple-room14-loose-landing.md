# Temple room 14: short-jump contact and falling slab

Status: 2026-11-14. User supplied `Macintosh room 14.mp4` and
`Port room 14.mp4`, then clarified three differences: masking on contact,
the slab's fall, and its impact on the guard. Both clips were inspected
through the contact, lower-room cut and guard impact, including frame sheets
around each stage. Start times and inputs differ, so timestamps alone do not
establish corresponding simulation frames.

## Original spawn, rather than a masking exception

AnimLoose CODE5:44b2-44ca selects MOB0 only for environment3 (caverns).
Other environments select MOB3. CODE5:4516-4522 sets bottom Y to
`(row+1)*120+5`; CODE5:4546-4564 adds18 and calls ClearCaveBelowFloor8:39b8
only in environment3. DrawObjLoose3:412c-41ae independently chooses temple
pieces28/29 and ruins14/18. These are recovered branches, not artwork edits.

The port tested specifically for ruins, accidentally creating temple MOB0
at Y383 for a bottom-row slab instead of MOB3 at Y365. Its logical rectangle
was87x43 instead of91x31, and it also cleared decoration below the slab as
though this were a cavern. `LooseFloors.advance_tiles` now applies the original
environment3-only condition. Caverns retain their former spawn; ruins retain
MOB3/Y+5 and stop receiving the cave-only decoration clear.

This fixes the18px gap at the first detached frame. At the room border, the
existing offscreen-actor compositor can now draw the slab over the Prince's
trousers at the correct height. No new actor-mask rule is needed. The previous
[full-raster neighbour repaint](falling-floor-neighbour-occlusion.md) remains
as a drawing safeguard; the template's native MOB3 logical width91 already
contains its90px lip. Save format and explicit saved MOB types are unchanged.

## Guard contact

The user-approved temple guard/body sweep remains an intentional horizontal
exception: it can hit a guard whose advancing foot has left the slab's column.
Its caller now also requires the ordinary native head-height gate,
`slabY > floor_y(row)+current_y-57` (ContactChar5:3642). Previously the sweep
could bypass that height and kill a guard before the ordinary contact plane.
This preserves the requested fatal outcome when the slab actually reaches him.
It does not restore every native mode exemption or claim complete guard parity.

## Checks and bounded replay

`tools.probe_loose_spawn` executes original AnimLoose through the AddMob call
boundary for all123 original loose-cell anchors in levels3-13 and four supplied
velocities:492 native/port comparisons, zero mismatches. Original level and
environment headers are checked. Supplied no-op endpoints: MakeSpace5:2606,
foreground writeback44d8-44f8 (including its arithmetic), and the cave-only
clear8:39b8. AddMob allocation, subsequent movement, dirty drawing and full
FrameAdv are excluded. These stubs do not choose spawn Y or type.

A further54 ContactChar5:3642 cases check ordinary guard head-boundary rejection
and admission, both facings, all rows and three relative heights. The actor
bank/FRAM foot record is supplied synthetically using the existing probe's
bank-loader endpoint. Original contact instructions execute; AI, native ALIVE
scheduling and the intentional host body-sweep exception are outside this slice.

The hidden real-key regression starts at level10 native room14 row1 X120,
Up then Right, releases Up after tick2 and Right after tick9. These are supplied
reproduction inputs, not recovered keys from the video. The normal SEQS3 jump
and SEQS18 fall reach pose106/Y6 at tick16. At tick17 the slab is MOB3/Y365,
its visible floor covers the trouser region, and no downstairs decoration is
cleared. Its later Y values are47,102,165,228 after crossing into native room13.
At Y165 the guard remains alive; at228 he is crushed, then the slab becomes
rubble on the following tick. Opponents and real AI are enabled.

Separate negative controls restoring either the former spawn or the ungated
body-sweep caller each fail that regression once without errors. Asset-free
unit checks cover all three rows/environments2/3/4 and the decoration boundary.
The earlier room8 regression now expects native temple MOB3/Y245, with its
three-pixel repaint control retained. Clips, stage sheets, replay JSON and
native reports are ignored under `rendered/room14-loose-landing`.

Focused validation:93 tests pass without skips in40.595s, covering this replay,
loose floors, room8 masking, temple playtests and routes, and actor layering.
Dependency, Ruff F/E9, recovery-catalogue and whitespace checks pass.
