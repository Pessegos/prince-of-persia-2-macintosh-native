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

Full shared-desktop discovery on this gameplay change:4,222 tests,
OK with10 skips,822.035s. Exclusive-desktop tests were not run while the
user could be playing. Existing Tk teardown messages and Pillow deprecation
warnings did not produce test failures. This run precedes integration of
the independently published menu-opening work.

## Follow-up: slab over the statue plinth (2026-11-14)

The user's paired stills exposed a residual in the first MOB3 frame: the
slab covered the stationary plinth to its right. The preceding regression's
X120 start checked trouser occlusion but did not make the actor's redraw
rectangle reach far enough into that plinth to catch this error.

`draw_cavern_falling` also runs after an offscreen actor, clipped to that
actor's rectangle. Static foreground has already been composited at this
point. The slab painter repeated the neighbouring floor records, but cell
(6,2), tile8, has no DrawFloorBuf record. Its statue foreground was therefore
left underneath the moving slab. Native drawing treats DrawForeImg3:2598
independently of floor-buffer records (RedrawCell3:1d34/1dd4).

Moving slab pieces now have the stationary foreground's alpha removed from
their own alpha before compositing. This protects the plinth and other
foreground contours even when the floor-record list is empty. It retains
holes and live foreground lighting, without repainting cached static RGB
across the frame. Cached SHAP images are copied before their alpha changes.
Existing floor redraws, actor clipping, MOB3 origin/size, fall/guard timing
and input remain unchanged. This is a bounded host compositor correction;
no new native CPU/full-raster probe is claimed.

Five actual Up/Right replays, starts X125/130/135/140/145, now check the
whole plinth at the first detached frame as well as the existing trouser,
fall and guard tests. A synthetic no-floor-record case checks foreground
holes, live colours, outside pixels and unchanged cached source artwork.
The previous painter fails all five overlap subcases plus that synthetic
case, without errors. The corrected X145 before/fixed view was inspected
against the user's supplied target.

An ignored audit compares all original loose/shelf anchors in levels3-13:
144 anchors,95 rooms,1,641 supplied drawing cases, with actual detached
variants. Stationary occlusion changes1,054 cases at140 anchors. Every changed
pixel restores the finished stationary scenery colour. These include
supplied fall positions that are not naturally reachable through a solid
floor; this is a drawing audit, not140 reproduced campaign bugs. The audit,
negative controls and actual critical-frame view are under
`rendered/slab-stationary-foreground`.

Final follow-up validation:245 focused tests pass without skips in104.916s
(room14, moving slabs, cavern/opening renderer, loose floors, ledges, actor
layering, temple playtests/exits, gate repaint and bridges). Dependency,
Ruff F/E9, recovery-catalogue and whitespace checks pass. No new full-suite
or native-probe run is claimed for this renderer-only follow-up.

## Follow-up: one-pixel shift from fixed tile to moving slab (2026-11-14)

The user noticed the next-frame floor movement and clarified that the still
with three spent lives was Macintosh; the other still was Port. Inspection
of the original clip's left floor edge around frames95-96 (about1.58-1.60s)
shows a slight downward step before the slab leaves the room.

The cause at this contact is the dynamic-image origin. AddImgObj3:0302-030c
stores `top = bottom - image_height + 1`: its bottom coordinate is inclusive.
Static exported room commands use an exclusive bottom. The host had placed
moving slab pieces at `bottom-height`, so the first moving image occupied the
same rows as the former fixed floor. Falling-slab pieces now start one raster
row lower, with their stationary-foreground mask sampled at that same shifted
rectangle. MOB coordinates, velocities, controller phases, fall timing and
the guard contact rule are unchanged. The statue/plinth protection remains.
The shared painter corrects the corresponding origin for caverns and ruins too.

`tools.probe_loose_raster_origin` executes those original instructions for
all six slab SHAPs across cave/ruins/temple resources and eight supplied bottom
coordinates:48 comparisons, zero mismatches. Original level/environment/
controller headers and imported SHAP headers are checked. A6/A3, caller's
bottom, shape height and record allocation are supplied. Image loading,
clipping, pixel decoding and the whole draw loop are excluded. This checks
the native coordinate convention, not complete raster equivalence.

The room14 contact regression now compares the moving floor texture with
the static reference one row above, while retaining the plinth and guard
checks. An asset-free test checks both the new top and inclusive last row.
Restoring the99cf8bc painter fails these two tests without errors. Actual
same-state before/fixed contact views were inspected; ignored evidence is
under `rendered/temple-loose-shake`.

Separate research finding: original temple shake phases include both
3545/3547 and3546/3548 pairs, but legacy temple imports retain only the first
shake state. That affects other attached shake phases and is not the cause
of this fixed-to-MOB transition; it remains a bounded importer follow-up.
No shake table, imported artwork or resource data is changed by this fix.

Validation for this origin correction:246 focused tests pass without skips
in90.983s (room14/slab/cavern/opening/loose/ledge/actor/temple/gate/bridge).
Dependency, Ruff F/E9, recovery-catalogue and whitespace checks pass. No new
full-discovery run is claimed for this drawing-only coordinate change.
