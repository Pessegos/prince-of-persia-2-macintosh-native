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
of this fixed-to-MOB transition; it remains a bounded importer follow-up
(done 2026-11-16: the temple export keeps phase 3's image, `shake_pairs`).
No shake table, imported artwork or resource data is changed by this fix.

Validation for this origin correction:246 focused tests pass without skips
in90.983s (room14/slab/cavern/opening/loose/ledge/actor/temple/gate/bridge).
Dependency, Ruff F/E9, recovery-catalogue and whitespace checks pass. No new
full-discovery run is claimed for this drawing-only coordinate change.

## Deliberate port improvement: first-contact leg reveal (2026-11-15)

**Superseded admission:** the source18 standing-jump exception in this and
the next section was based on the wrong reproduction. It is withdrawn;
the confirmed video-frame correction below applies only to running source21.

After accepting the native match, the user requested a visual exception for
the supplied short-jump impact frame: show the Prince's whole lower leg and
boot in front of the loose tile, then resume its existing masking on the
following frame. This is an approved port improvement, not recovered native
behaviour; the original can show the same cut.

The room14 real-key reproduction at start X145 selects SEQS18, pose106,
mode4. At tick16 the actor has relative Y6 in row2 and the struck type11
floor is still attached at collapse phase11. QuickFloor's complete floor
repaint cuts across the trousers and boot. The compositor now omits only
that supporting cell's floor repaint in this state, verified through the
supporting-foot coordinate and its active forced-collapse controller.
The exception applies to this temple short-jump contact, independently of
room number. Other environments, actors, sequences and contact heights keep
their previous drawing. Warning shakes and ordinary floors are excluded.

Stationary statue/plinth masking still happens before the actor is painted;
neighbouring floors still repaint. Tick17's MOB3 at Y365 retains the accepted
inclusive raster origin, foreground protection and trouser masking. No actor,
motion, tile controller, slab or guard timing is changed, and no persistent
state or input is introduced.

The regression compares all23 frames of the supplied-input reproduction
against the previous painter at the same game state: only tick16 changes.
Its entire image equals the render without floor repaint in that frame,
showing the actual actor artwork; no changed pixel touches stationary
foreground. The test also checks actor/motion/loose-controller state remains
unchanged by drawing. A separate two-floor control verifies that deferring
one cell leaves its neighbour in front. Existing detached-frame/plinth and
guard-contact regressions remain in force. Disabling the exception makes
the new real-route test fail once, without errors. Start and key timing are
supplied test inputs, not a recovery of the video's original keypresses.

The legacy temple-arrival slab fixture also now supplies a transparent
stationary-foreground image and expects the already recovered inclusive
bottom. That fixes its stale fixture/expectation after the earlier painter
changes; it does not change production behaviour or weaken the shape check.
No original resources or imported artwork are modified.

Validation:252 focused renderer/route tests pass without skips in98.233s;
62 temple-arrival/final-level tests pass without skips in24.810s. After adding
the neighbouring-floor control, all five room14 tests pass in3.681s.
Dependency, Ruff F/E9, recovery-catalogue and whitespace checks pass. The
before/fixed contact and both adjacent frames were visually inspected.
No full discovery or native probe rerun is claimed for this visual exception.

## Residual: toe cut by the neighbouring stone base (2026-11-15)

The user's zoom after e24c078 exposed a gap in that implementation and its
X145 test. Deferring QuickFloor reveals the leg at X145, but starts X150 and
X155 put the toe into the statue plinth's independent actor-alpha mask. The
floor-only reference render retained that same mask, so it could not certify
that every boot pixel was visible. The preceding no-foreground-change claim
was specific to X145; it did not cover this residual.

The same first-contact admission now also removes the contacted slab's full
visible contour from the actor mask, before the actor layer is composited.
Existing `platform_contours` provide its actual alpha, including the portion
extending into the next cell: this temple slab is90 pixels wide, whereas its
QuickFloor repaint is clipped to51 pixels. Using only that half repaint as
the mask boundary would still leave the toe cut. No new rectangular mask or
resource/artwork change is introduced. The statue above that contour remains
in front; the lower leg and toe can cover the overlapping base in this one
approved frame. The following detached frame retains normal plinth occlusion.

Two additional real-key23-frame replays at starts X150 and X155 compare with
e24c078's mask order. Only tick16 changes, restoring respectively4 and37 actor
pixels. An independent control disables all actor masks and checks the whole
lower leg/boot against that original sprite image; the upper statue/body
continues to differ from the unmasked control exactly as before. Restoring
the previous mask produces two failing subcases without errors, each at the
leg/boot artwork comparison. A synthetic contour test checks holes, bounds,
unchanged source artwork and unchanged input mask. Earlier X145, neighbour
floor, detached-slab/plinth and guard progression tests are retained.

These are supplied reproduction starts/keys, not recovered video inputs or a
claim of complete native raster equivalence. This remains the user's visual
port exception; actor/controller/physics and the following frame are unchanged.
Ignored same-state enlarged before/fixed crops are under
`rendered/first-loose-contact-leg/residual-before-fixed.png`.

Validation:283 focused renderer/loose/ledge/temple-arrival/final-route tests
pass without skips in108.527s. The final seven room14 tests pass in8.045s,
including both actual toe-overlap starts. Dependencies, Ruff F/E9,
recovery-catalogue and whitespace checks pass. No new full discovery or
native CPU probe run is claimed for this renderer-only follow-up.

## Correction: confirmed video A is a running jump (2026-11-15)

The user still saw no change after both patches, then confirmed the target
using actual video images: A is source frame76 (about1.267s), with straight
trousers/boot in front of the stone; B is the next pose, source frame80
(about1.333s), which must retain its occlusion. The user also confirmed
launching the primary worktree's `run_game.py`, rather than a packaged build.

The failure was the reproduction and its admission guard. The video's
earlier frames show a running leap. A real-key running reproduction, start
X2 in room13/row1, Right held, Up pressed before tick4 and released before
tick5, reaches source21/pose106/mode4/Y6 at tick22, targetX322 and actor
bounds(291,282,324,352). The video's white-trouser silhouette fits pose106
at that same drawn X/Y. Previous supplied standing inputs selected source18,
so the strict source18 guard did nothing to the user's running case. The
passing tests and previous completion reports did not establish a fix for A.
Video keypresses are not recovered; these are supplied inputs matching the
confirmed impact placement, not full pixel/timing equivalence with the clip.

The production correction now changes the guard to source21 **only**, and
withdraws the unrequested source18 change. It reuses the already checked
floor-repaint deferral/full-contour actor mask at the same forced phase11
and Y6, with no further changes to the painter, assets, actor state, motion,
MOB origin, guard timing, gates or AI. A23-frame standing-jump regression
now requires every frame to match the original mask path, including contact.

Three29-frame running-input replays at starts X2/7/12 compare against the
previously published running path: only tick22 changes. For exact A and
nearby X7, the whole lower-leg/boot region matches independent drawing with
all actor masks and floor repaint disabled. At X12, upper trousers genuinely
intersect the statue's foot above the slab contour, so that stone remains
in front; the boot below the real contour must still match its complete
artwork. This is an explicit upper-statue preservation control. At exact A's
tick23, B remains byte-identical to the old path, source21/pose106/Y-92,row3,
and the MOB still starts at Y365/type3. The farther-right route can instead
land on the statue's floor; its following render must likewise stay unchanged.

Restoring e56ada4's actual admission function fails all three running
subcases at the independent artwork check and fails the standing-jump
preservation test: four failures, no errors. Enlarged source-video/before/
corrected A and B were inspected together in
`rendered/first-loose-contact-leg/confirmed-running-comparison.png`.

Validation:283 focused renderer/loose/ledge/temple-arrival/final-route tests
pass without skips in109.699s. Final seven room14 tests pass in7.113s after
adding explicit state/motion/loose-controller immutability checks at the
running contact. Dependencies, Ruff F/E9, recovery-catalogue and whitespace
checks pass. No full discovery/native CPU probe run is claimed for this
source-admission correction; no new painter geometry was added.
