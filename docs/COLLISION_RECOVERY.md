# Macintosh Rooftop Collision Recovery

The preserved Macintosh executable and resources are the behavioral reference.
This is the first playable terrain subset, not a complete collision engine.
The earlier animation-only mode and all Mini vMac packs are unchanged.

## Map And Coordinates

`pop2/terrain.py` reads tiles and room links directly from `LEVL:2000`:

- Tile kinds: room * 60, 30 big-endian words per room.
- Foreground/background modifiers: `0x780 + room * 120`.
- Room links: `0x2080 + room * 8`, left/right/up/down; native zero means no link.
- Start room/tile: `0x2198` / `0x219a`.

Native room numbers are one-based; runtime room indices are zero-based.
The opening is native room 4. Its left exit leads to room 2, then 3, then 1.
Tile lookup traverses vertical links before horizontal links, rather than
inventing solid walls at every viewport edge. Room scenery uses the same map
reader, original Rooftops assets and separate foreground layer.

`SetCharFloor`, CODE:4 `0x31fa`, gives row * 120 + 106. `GetRow` at `0x3afa`
uses signed division with truncation toward zero. Tile columns retain the
native `GetCharCol` conversion rather than simple sprite X / 51.

## Implemented Player Rules

- `GetFCharX`, CODE:4 `0x3a72`: the supporting foot is determined by the
  current FRAM offset and its lower six flag bits, with facing applied.
  Testing only the actor anchor makes gap jumps fail at the wrong position.
- `CheckFloor`, CODE:4 `0x35ba`: only FRAM flag `0x40` enables ground testing.
  Airborne jump poses must not fall merely because a gap is underneath them.
  Existing sequence-driven jump offsets remain unchanged on flat ground.
- `StartFall`, CODE:4 `0x4cbe`-`0x4d90`: supported ordinary run/jump/sword
  poses select their corresponding fall sequence and advance the floor row.
  New commands cannot cancel a fall.
- CODE:4 `0x4ca8`-`0x4cb2` clears the drawn-sword flag on fall entry, before
  those pose-specific branches. This lets a retreat off a ledge use the normal
  Shift catch controller; retaining sword mode incorrectly blocked the catch.
- The preparation at CODE:4 `0x4b16` now aligns ordinary falls using the old
  pose's supporting foot and cached column. It checks floor/wall cells ahead,
  behind and above, applies the source 17/34-pixel thresholds, and when needed
  lowers the anchor to the new row's Y=120*row before selecting the fall pose.
  This is the physical preparation, not the rendering/occlusion rule. It is
  not a sprite-wide wall clamp or a special opening-room offset.
- `Move`, CODE:4 `0x341a` / `0x3464`: gravity adds 6 per simulation frame,
  capped at 63; horizontal velocity applies in animation state 4.
- `Falling`, CODE:6 `0x00a6`, and `HitFloor`, `0x0280`: landing is checked
  in states 4/9. Speed below 50 selects soft landing (`17`, or `63` armed);
  50-62 selects hard landing `20` and one life of damage; 63 selects fatal
  landing `22`. Falling beyond absolute Y=730 without a lower room is fatal,
  except in the two harbor water rooms, where RoofWatchOpps owns the death delay.
- `GetLeftBarr` / `GetRightBarr`, CODE:4 `0x541a` / `0x547c`: the full-wall
  case uses the recovered DATA offsets. A swept body check prevents crossing
  the wall between frames, including horizontal drift during a fall. The
  supported low grounded bump uses `46`/`47`; unsupported/high contact uses
  `45`. Armed front/rear contact selects `64`/`65` respectively.
- `CutChar`, CODE:6 `0x4918`: supported horizontal exits use the body's
  facing-dependent visible bounds, not its center. A linked screen change
  rebases X by 510 without restarting the current animation or velocity.
  The native rectangle's right edge is exclusive; the sprite helper's right
  edge is inclusive and is converted before testing. Left-facing left exits
  use left<=-16; right-facing left exits use exclusive right<=-1. Using the
  opposite bounds caused a jump into room 5 to cut back into room 4 on the
  following pose. CODE:6 `0x4a26`-`0x4a62` also excludes poses 110-119,
  135-162, 166-168 and animation state 7 from horizontal cutting.
  Downward coordinate transfer uses a 365-pixel clip and three tile rows.
  Full native vertical viewport-cut timing is not implemented yet.
  Falling exits now include CODE:6 `0x4dac`'s neighbor entry-tile check (pose
  102 uses row-1), and the downward-priority rule at `0x49ce`: at Y>=440 with
  a lower link, or Y>=440+sprite height without one, do not switch sideways
  into another room. A deliberate step after the warning can still fall and
  die in the opening room. Ordinary airborne exits and the right-hand secret
  room remain available; there is no blanket ban on room changes while falling.

Player Shift steps now use the ordinary subset of `GetBarrDistances`, CODE:4
`0x5eae`-`0x5ffa`: inspect the supporting foot's current tile and its immediate
neighbor, with linked-room lookup. Gap/loose/plate distances use `GetFCharDist`
at `0x3a92`; ordinary wall types use the body's barrier distance and the DATA
offsets. Tiles 23/24 keep their native asymmetric current/next-tile distances.
Clear floor returns 42 before `DoStepFwd` reserves four pixels, producing a
38-pixel step (SEQS:40 plus two pixels). The earlier isolated no-guard test
retains its previous 42-pixel step. NPC patrol bounds still use the older scan.

GenCtrl CODE:6 `0x11a0`-`0x11d6` also calls DoStepFwd without Shift: a fresh
forward press with barrier type 1 and distance strictly below 27 selects the
short step rather than run acceleration. Ordinary gaps do not use this branch.
The source Collide tail at 4:`0x64f6`-`0x6532` distinguishes front sword bump
64 from rear bump 65. Selecting 64 for both sides moved a retreating Prince
farther into the wall. After loading the response pose the port also checks
its new body bounds; this second sweep is an explicit safeguard until the
full native collision-buffer/GetCharEdges pipeline is translated.
PutSwordAway (6:2594) clears sword mode before its first pose, while the
Python sheath lock persists until completion. CheckCollide1 (4:551a/5586)
therefore ignores a rear barrier during grounded sheathing, instead of
aborting it as an armed rear bump. Armed contacts still check both sides;
the existing port sweep also keeps both sides during a fall. CheckBarr's
mode-7 exclusion (4:4e46) bypasses the wall sweep for a standing turn.
Changes in sprite width cannot replace that turn with a collision response.

The 23:31 recording exposed a separate host input-state error after wall
contact: clearing jump_started_for_press let releasing the already-used Up
key enqueue another jump through the short-tap fallback. A wall event now
keeps that consumed-press flag until release, while still clearing the
buffer and jump-repeat permission. Fall/death resets are unchanged. Tests
exercise both chord orders, both wall sides, four release timings, a held
chord and a genuinely fresh press after recovery. This lifecycle correction
does not change native collision poses or imply native key consumption is
fully translated.

`DoStepFwd`, CODE:6 `0x12fc`-`0x1324`, supplies the missing caution behavior:
insufficient clearance selects SEQS:44 once and clears the native caution
state. Its poses 121-126, 86 and 116-119 probe the edge and return to the
original X; the next explicit attempt selects SEQS:42 and can fall. Holding
the first press cannot automatically confirm that warning. Solid barriers do
not trigger the probe, except kinds 12/13 as in the native test. The warning
and distance rules are covered for loose/plate kinds, but dynamic floor/gate
events, type-4 gate openness and all special-level barriers remain unported.

At the opening's right gap, the idle supporting foot at actor X=411 gives
distance 21; a short step reaches X=428, leaving distance 4. This is farther
than the former geometric tile-edge stop at X=404. No new floor height offset
was added: the warning's original FRAM records supply their own -1 Y offsets.

Sword drawing and automatic turns also need terrain checks before selecting
their animation. The ordinary gap/solid-wall branch of CODE:6 `0x2072`-`0x2122`
reserves 56 pixels when drawing toward an immediate obstruction, using
`GetBarrDistances`: supporting-foot distance for gaps, body/barrier distance
for solid walls. The turn routine at CODE:6
`0x26dc`-`0x276c` checks the next two tiles, reserves 84 pixels and applies
the original extra allowances for drawing pose 207 and hurt sequence 94.
These facing-relative adjustments happen before `SEQS:55` / `127`; the
resources' poses and offsets are unchanged. Previously, drawing then turning
immediately after the opening moved the Prince off the roof. Neither a
screen-wide clamp nor an exemption from falling is used to fix that case.

GenCtrl's ledge-release helper (6:1a84-1b7c) tests IsLandOnable on the
supporting-foot cell and the cell behind. Ordinary wall/floor combinations
select SEQS:11, with relative offsets -23 (current wall), -12 (floor behind),
+10 (floor underfoot), or zero (both floor). No landing support selects
SEQS:23, retaining the -23 adjustment when the current cell is a wall.
The normal animation tick consumes the first pose exactly once. The empty-
cell DoJumpHang/SEQS:99 variant and other-level exceptions remain pending.
Real-key scene regressions compare turns, drawing, post-retreat sheathing
and wall release against the original resource interpreter; tile decision
boundaries are checked in both facings.
Gate-specific and full wall-distance drawing branches remain unported.

## Actor Occlusion And Reinforcement Control

The old flattened foreground was pasted over every actor regardless of floor.
That erased parts of a sword-retreat fall with the previous row's parapet,
even after the fall preparation moved the Prince into the next row.
`pop2/render_opening.py` now retains each foreground piece's tile row and derives
actor masks from the same/lower rows; `pop2/scene_prototype.py` applies that mask
to each actor, sword and hit effect separately. The scenery image is unchanged.
Grounded actors retain parapet occlusion. Falling actors are not erased by an
upper row's ledge. CODE:23 `DrawRoofLedgeInBack` at `0x05a2` is the recovery
reference for floor-sensitive layering. This mask is a limited rooftop
representation: the full native DrawRoofFloor/ClipChar predicates and all
special-pose overlaps are not yet complete, so it is not certified pixel parity
for every fall, grab or climb.

Normal floor occlusion covers every overlapping floor piece, not just
DrawForeImg's two indexed cells. MarkPeelForeBufs 3:0428 calls
MarkBufsForRect 5:19f8 to mark the actor rectangle's foreground cells.
Restricting a wide attack pose to the supporting foot's two cells exposed
the forward foot through the next parapet. Near facade pieces cover the actor
rectangle; climbing retains its native partial-floor redraw.

DrawRoofDecoration 23:`0x018e`-`0x0242` uses DATA tables at A5 cca8/ccea.
All eleven shape/offset/pass entries are now used, including decoration
modifiers in empty tiles. These supply the previously missing right-hand
cornices/corners. Pass-1 pieces belong to foreground; pass-5 pieces stay in
back. The full conditional redraw pipeline is still incomplete. Guard
bodies now pass their actual state/bounds/FRAM record into per-actor masking,
as the Prince already did. This does not certify exact corpse visibility
at a different death position; see the explicit pending item in
`RECOVERY_INDEX.md`.

The additional DrawRoofFloor helper at CODE:23 `0x0614`-`0x06c6` tests the
Prince's bounding rectangle against the roof-ledge SHAP rectangle. Modes
3/4/6 and actions 91/80/81/136 can suppress that ledge's foreground occlusion;
sequence 68 explicitly vetoes this exception. The renderer translates this
predicate for the Prince and his hit effect only. Actor bounds have inclusive
right/bottom coordinates; the image rectangle is exclusive. The room texture
and the remaining foreground pieces do not change.

The incoming guard's AutoCtrl must run even when no same-floor combat target
is eligible. Previously `choose_guard_action` returned before the unarmed
controller, leaving the run loop active after the Prince fell. CODE:4
`0x0674`-`0x06d0` checks the floor and selects braking sequence 101; the
player-death branch at `0x0766` does the same. The supported controller now
brakes when the player leaves the floor/room or dies and completes the return
to standing sequence 77. Target eligibility remains separate from updating
the NPC's own control state. The later pursuit implementation supplies a
rebased target in a visited neighboring room. A different floor selects braking
unless the guard's generator explicitly permits the player's alternate row.
See `AI_RECOVERY.md` for the supported NPC terrain paths.

## Supporting-Foot Wall Correction

CODE:4 `0x3982` is now translated for ordinary rooftop actors. CheckFloor
calls it when a grounded supporting foot enters a wall. Falling at CODE:6
`0x0156`-`0x0174` calls it before the floor-height comparison, except during
sequence 15. It uses the current foot's edge distance and the facing-neighbor
tile: subtract 51 if the distance is >=18 or the neighbor is a wall,
otherwise add 18, then apply that offset in the facing direction and reload
the supporting tile. Sequence mode 4 and actor type 11 bypass the correction.
The special level-6/room-3 exception is outside this rooftop subset.

Previously a stationary falling actor was never corrected by the swept body
test, and a wall under a grounded foot was treated as support. This missing
rule affected the walls beside the gap in native room 1 (prototype index 0,
the two tan buildings). Both sides now use the per-pose correction rather
than allowing a wall to become a landing floor. Body sweeps also distinguish
GetBarrCode's short-pose type-7 barrier and thin type-2 wall offsets.

## Native Ledge Controller

The default terrain scene now replaces the old experimental hold with these
ordinary native branches:

- StairClimbing, CODE:6 `0x0ece`: an empty tile behind a grounded Prince,
  a real supporting tile and supporting-foot distance >=11 select `SEQS:68`.
  Its pre-offset is `(distance - 38)` in the facing direction. The Prince
  backs down facing the building; Down alone initiates it.
- DoJumpUp, CODE:6 `0x1610`-`0x1bbe`: the upper current tile must be empty,
  and the upper forward tile must be a real floor rather than a wall. The
  `(distance - 21)` alignment selects `SEQS:24`, then 9/210.
- Catch, CODE:4 `0x37ca`-`0x3928`: Shift, vertical velocity <60 and relative
  Y in [-48, 3] permit the original 17-pixel look-behind tile check. A real
  ledge selects 15 and aligns using its first caught pose 80; an empty pair
  of cells can never hold the Prince. The original grip delay is 12 ticks.
- GenCtrl, CODE:6 `0x18e0`-`0x1998`: Up selects 10 after the grip delay,
  before testing Shift release. Otherwise hanging actions 87-99 fall through
  23 when Shift is released or sequence 210 sets mode 11. A wall under the
  supporting foot selects 25 only outside animation mode 6 (6:1926-1938).
  SEQS:25 sets mode 6 itself, so its six poses 92/93/93/92/92/91 finish once
  and -23 holds 91. The earlier every-tick restart at 92 missed this guard.
  A left-facing gate still reselects 25 independently of mode. Ordinary wall
  holds do not expire; free-air grip expiry comes from sequence 210, not a
  guessed number of seconds. Ship/other special-level exceptions remain unported.
  The October 5 19:20 comparison exposed this state-selection error; matched
  climb poses retain the same five-tick cadence. Tests check the entire
  settling action list before asserting the stable hold, including both
  catch directions, so they cannot validate only a wrong stationary pose.
- Sequence row opcodes -3/-4 update the actual terrain row. Native climb
  10/235 reaches the upper floor; descent 68 reaches the lower row. The
  controller protects the approach/climb from unrelated horizontal input.

## Jump Contact With Guards

FrameAdv 2:6c64-6daa supplies the ordinary unarmed bump. The exclusion at
6c96 tests actor type (af b2), not animation mode (af ba). Both standing and
running jumps use animation mode 1 and must still reach the contact check.
The ordinary distance limit is 24; SEQS:4 also accepts distances below 63.
The native opposing-facing correction adds 21 for a target ahead. Responses
retain native SEQS:46/47, immediate first-frame loading and their X offsets.

The port additionally sweeps same-room forward jump displacement through
that native interval. SEQS:3's 49-pixel step can otherwise skip both sampled
contact positions. This is an explicit port safeguard, not a recovered native
swept-NPC routine. Contact stops at the interval before applying the existing
bump response. It does not apply to ordinary running, retreating, armed or
ineligible actors, and it never treats a room-coordinate rebase as movement.
Integration tests cover both jump types/facings with a stationary NPC and
the live guard AI; boundary tests preserve the native exclusions.

The building junction is native room 10 (runtime 9), lower row 1. At X=240,
facing left, Up alone reaches the real upper ledge and climbs to row 0.
The lower join remains a continuous floor after a running wall bump; its
foreground is not treated as a hole. Conditional native rooftop clipping
is still only partially translated, so this is not a claim of every-pixel
rendering parity at every approach pose.

The October 5 00:35 video exposed why an end-state-only junction test was
insufficient. Collide 4:5826-584c distinguishes empty support (GroundBump,
5868, SEQS:45) from a solid-floor response (589e). A low unarmed solid-floor
bump calls SetCharFloor, clears vertical velocity and selects SEQS:46 for
poses 24/25, 40-42 or 102-106; ordinary running uses SEQS:47. The earlier
port always chose 45 and marked a fall, temporarily dropping the Prince
below the continuous lower floor before landing. The regression now checks
every tick of a prolonged wall approach, not just the recovered final pose.
The current body sweep also accepts the actual previous frame's bounds;
translating the new sprite backwards by anchor movement misses collisions
when its width/anchor changes. This remains a port body sweep, not the full
native collision-buffer implementation. Tests cover a changed sprite with
both moving and stationary anchors, and Up-only climb after a wall bump.

The October 5 22:09 screen-5 comparison exposed an exclusive-edge error
in that sweep. GetColDetData (4:53b8-53ca) marks overlap only when the wall's
right edge is greater than the body's left, not equal. Touching that edge
now allows the source short-step poses 124/131 to complete instead of
interrupting them with SEQS:47 and its backward offset. Leftward correction
places the body at the exclusive wall edge without reserving an extra pixel.
GetBarrDistFromFace (4:65d8-65ea) also requires the exclusive body-right edge
for right-facing step clearance; the Pillow last column is converted once.
Real-input regressions cover both directions at clearances 5-26. Recorded
Macintosh poses confirm the screen-5 short-step endpoint X=233 and the
legitimate repeated-tap bump/return endpoints 245/233. No screen-specific
position target or extra step-distance adjustment was introduced.

The October 5 22:27 crouch comparison exposed a different controller error:
the standing Down path, StairClimbing 6:0f4e -> 1068 -> 108a, chooses SEQS:50,
not the running path's 26 (6:125a). Their source displacements are 16 and 26
pixels respectively. At the same screen-5 anchor, 50 reaches pose 109 before
a released crouch rises; 26 hit the wall before that low pose and flashed a
standing bump instead. GenCtrl 6:06b4/099a permits a follow-up on the first
109, so an extra hold frame must not delay release or repeated crouched
steps. Integration tests retain the actual bump when lowering from a fully
blocked position or when the rise itself reaches the wall. No new wall
geometry, collision exemption, frame rate or foreground mask was introduced.

`tests/test_game_ui.py` covers descending, grip expiry, release, upper-floor climb,
an actual gap jump/catch/climb, absence of a catch on flat floor, input
protection, the building junction and the upper generated guard's landing.
It also exercises native pause-font rendering, both frozen actors, AI-clock
resume, aspect-fit scaling, fullscreen state and the in-game development menu.

## State And Testing

The current room's guards and reinforcement points load from the original
level data. Revisits retain their state; screen transitions retain player life,
held input and the current movement sequence. Curtain/glass effects stay in
the opening room and do not replay on return. New Game resets the world and opening.

Initial guards also retain generator word +0x0c (palette variant). The native
palette resource rule, CODE:6 `0x4210`, is CTBL=749+variant: the opening guard
uses 750, while room 5's variant 3 uses 752, with a light turban and red-brown
clothes. Sprite cache keys include the variant, including on revisits.
The missing-room physics sentinel is no longer rendered as a wall. Rooms
without an upper neighbor extend their top-row background through the
five-pixel viewport margin; room 5 no longer gets a spurious wall strip.

`tests/test_terrain.py` covers native coordinates and links, foot offsets, floor
flags, gravity, landing thresholds/damage, wall sweeps, left/right transitions,
room persistence, empty-room combat, gap jumps, reset, and flat-ground
animation regressions. Integration tests use the real hidden Tk renderer,
including opening, both guard defeats, sheathing and continuing to room 2
through input commands rather than teleporting past the encounter. Sword
regressions include pressing only Ctrl after the opening, turns at both sides
of a gap, linked-floor clearance and a buffered attack after the turn.
Fall regressions also check the corner alignment thresholds, first-pose
entry-row exception, the 440+height boundary, continuing both deliberate
step and sword-retreat falls through death without a false room change,
resetting afterwards, and jumping into the secret room.
Further regressions check both facing-dependent viewport boundaries, excluded
poses, continued simulation after entering room 5 without a reverse cut,
actual falling-body pixels in the renderer, and an incoming guard finishing
its brake after a sword-retreat fall and player death.
`tests/test_rooftop_pursuit.py` checks both sides of the two-building gap, including
wall correction before the next floor is reached without any horizontal
velocity, and native NPC jump/transfer/landing behavior.

## Remaining Scope

The player running-jump entry now translates `DoRunJump`, CODE:6
`0x1c50`-`0x1d3a`: anchor look-ahead 13, two forward tile checks, Prince
reserve 48, adjustment range -31 through 14, and late-jump rejection. The
arc is unchanged. Integration coverage crosses both consecutive rooftop
gaps using run/Up inputs and climbs the building after running to its wall.

`DrawRoofFloor`, CODE:23 `0x04c4`-`0x0546`, limits the extended ledge's
foreground strip to 22 pixels, with native room exceptions of 20, 19 and
17. The full slope remains in the scenery. Masks combine alpha by union,
so a transparent ledge cannot erase another foreground piece.

Foreground pieces are retained separately by their native tile column. `IndexChar`,
CODE:4 `0x4558`-`0x45b8`, uses GetCharEdges' drawn bottom/left in mode 1
(4:5dfa/5e10), and the physical row/supporting foot in other modes.
Modes 2/3/4/6 and poses 135-148 then offset one cell behind
(DATA b46a=+1, b46c=-1). The rectangle's column uses 5:48b0, not GetCharCol's
additional supporting-foot offset; a drawn row of -1 maps to 3.
`DrawForeImg`, CODE:3 `0x2598`-`0x26bc`, redraws that cell and its left
neighbor. That index alone is not the whole foreground redraw pipeline:
MarkPeelForeBufs also handles rectangles across the actor. The Prince's body
and impact layer use indexed pieces plus the near facade's foreground wall
SHAPs. Poses 135-144 also use the ten
original `ComputeHalfRect` rectangles from DATA b4ba for partial floor
redraws (`DrawHalf`, CODE:3 `0x3480`), translated by the 51x120 cell origin,
without adding the scenery's five-pixel margin. Neither sprite offsets
nor building textures are moved to conceal the rendering error. Remaining
barrier, actor-order, partial-redraw and special-level branches are incomplete.

The October 5 climb comparison additionally shows the upper roof's near
ledge covering the head and arm at pose 140 while the body stays visible
against the long shaded side. The old mask omitted that ledge until the
physical floor counter advanced, then attempted to compensate by covering
all overlapping pieces. Those overlap-only branches are removed. The
climbed roof stays eligible before the pose-141 row transition, using only
the selected near face and native ledge strip; unrelated upper walls are
not added. The existing pose/mode ledge-behind veto and partial floor strips
remain. Real-render tests assert that opaque sprite head/arm pixels become
scenery pixels, but the pants/foot on the shaded side remain sprite pixels.
Comparison PNGs in the temporary diagnostic directory show the before,
updated render and the same native-video pose; video resampling prevents
claiming exact source-pixel parity from that capture alone.

The five newer October 5 videos disambiguate the perspective: when facing
right and catching the left face of the right-hand tan building (room 0)
or palace (room 2), the original hides the body behind that facade. The old
test claiming that the whole body should remain visible was incorrect and
has been replaced. The facade's foreground SHAP alpha remains eligible
across the actor rectangle, not just the two indexed columns. Hanging poses
80/81 and 87-99 also retain the intersecting upper parapet. The near face
remains eligible for climb poses 135-140 before the floor row changes.
The newer screen-3/4 comparison exposed an error at poses 141-148: relying
on the partial redraw alone leaked hands and legs over the flat near face.
The r4 mask keeps overlapping near-facade floor/corner SHAPs in front for
right-facing climb poses, including the descent's reverse row transition.
Left-facing shaded-side climbing and the standalone half-redraw fallback
retain their separate rules. Actual input-driven ascent/descent/reclimb
tests check every emitted pose in both recorded rooms. Shaded side
artwork is still background. This is a video-verified rooftop approximation
of the foreground pipeline, not a claim that every native draw branch is recovered.

The subsequent `screen 3.mp4` / `screen 4.mp4` recordings isolated a separate
pre-catch failure in airborne poses 102-106. The physics row changes to 2
while the drawn body still intersects row-1 parapet/corner foreground; the
old mask dropped those pieces until caught pose 80. The r5 renderer keeps
intersecting flat foreground SHAPs in front during airborne modes 3/4,
independently of Shift or whether Catch succeeds. This also covers the next
row change in an uncaught fall. RoofLedge side strips retain their existing
overlap/back predicate; background pieces never join the mask. The rule is
geometric and shared between actors, with no room ID, takeoff X, or pose-102
special case. Physics, animation sequences and timing are unchanged.
An input-driven pixel regression failed before this correction and now
covers screens 3/4 at three starting X positions with early/late/no Shift,
checking every frame through climb or death. The native renderer is still
only partly translated: this extension is based on the observed facade
ordering, not a claim of recovering all original clipping branches.

Releasing SEQS:24 before the hold returns to the lower continuous floor,
but its landing/foot alignment can leave a sprite edge overlapping a wall
barrier. The sweep now also rejects further inward motion from that
overlap; movement out remains legal. Four release timings followed by 70
held Shift-step frames each verify the junction stays solid.

Ordinary EnGarde's too-close branch (CODE:4 0x0a82-0x0b1a) runs only at
ready pose 171. An advancable cell in front requests advance, except while
already in retreat sequences 57/104; otherwise an advancable cell behind
permits retreat. No supported cell behind means no voluntary retreat.
DoOppInput (CODE:6 0x2c90-0x2ca0) loads the anchor column before this decision;
LoadFrame (CODE:4 0x2a7c) computes the FRAM foot column later for CheckFloor.
Those columns must not be conflated. Real-resource AI/physics tests keep a
nonattacking player close in front for 240 frames from both gap edges, with
no guard fall. Wounded/parried retreat and native tumble/fall paths remain
unchanged; guards are not made immune to falling by an invisible boundary.

Returning to a neighbor can also expose an offscreen reinforcement before
it has seen the Prince and acquired `pursuing=True`. Generator corridor
checks now count that living actor's projected position as well as active
pursuers, without resetting its ownership, sequence or countdown. Native
side/floor/wall eligibility and death still determine when another guard
may spawn; this is not a global one-guard cap.

F2 exposes traversal-order screens 1-10 and the right-hand secret, with
fixed supported entry positions. It no longer exposes native room IDs,
floor selection or arbitrary X coordinates. Pause centers the original
font's visible ink in the 19-pixel HUD band. The long sheath accepts
buffered or held horizontal input at poses 50-52 (GenCtrl 6:0c32); the
short sheath retains all five poses before locomotion without an idle gap.
For a held forward run, the long sheath also uses the earlier pose-48
transition to SEQS:43 (GenCtrl 6:062c/1014), like the standing turn.

The `mac correct.mp4` / `port bug.mp4` comparison exposed a missing Catch
alignment branch (4:38da-3928). After SEQS:15 loads pose 80, its supporting
foot may cross into the upper floor tile. IsFloor(GetBlock at row-1) then
subtracts 51 from the alignment distance. The third screen's right-facing
standing-jump catch now settles at X=281 rather than X=332, while the
already-tested catches that do not cross that cell boundary are unchanged.
The source's additional left-facing rooftop room-19 adjustment is translated
too. The floor check happens after loading pose 80, not using the earlier
airborne pose or the post-alignment foot.

A buffered vertical jump at a running-cycle boundary must not enter
DoJumpUp using the running frame's foot offset. GenCtrl 6:11e4-1242 routes
running poses through braking or DoRunJump, not DoJumpUp. The host now
brakes before dispatching that queued vertical jump; a grounded wall bump
can replace the brake without losing its pending Up. The one-command host
buffer remains a partial translation, not a native latch implementation.
Regression tests compare the complete climb trajectory and rendered pose
140 against a settled approach across 18 rapid-input timings. No scenery
mask or wall coordinate is changed for this correction.

Ordinary flat deaths now apply the source's post-first-pose alignment
(6:5524-5558 and 6:04aa-055a). A foot already over space moves back 36;
the adjacent empty tile then aligns the corpse to native distance 32.
This applies the native supporting-foot correction; settled-body visibility
is a separate rule below. The r12 ordinary tumble selection also uses
generator LIFE bit 0x80, the registered dead-NPC
bank count/Rnd(3), overlapping settled corpses and facing/tile vetoes.
Mode 9 bypasses roof walls, floor landing and room cuts (2:65ee-6664), follows
the SEQS:185/207 trajectory with native gravity, and freezes at absolute
Y=730. Its ordinary ClipChar bypass is distinct from all ledge/facade masks.
The odd-slot flat corpse variant 195/228 is deterministic. Neither flat
corpse Y nor all corpse visibility is changed to imitate a screenshot.

The SEQS:85 alignment also applies to the Prince with his own frame record.
Settled Prince and guard rooftop corpses follow `IsCharNonViewable`
4:474c-477c, which suppresses dead poses outside native rooms 15/16/19. Death animation poses
remain visible. The former flat-guard visibility exception is removed. See
[REBIRTH_RECOVERY.md](REBIRTH_RECOVERY.md) for the death presentation rules.

Room cuts reuse one decoded rooftop atlas. Screen labels and F2 metadata no
longer build all supported rooms: the first label took about 1.4 seconds
before this change, versus about 2 ms afterwards on the development PC;
building an additional room fell from about 105 ms to about 3.5 ms. These
are local timings, not a hardware-independent performance guarantee.

- The old Shift+Down hold exists only in the isolated `--no-guard` animation
  scene. The terrain scene uses the native ledge controller above. Full
  ceiling/head collision, blocked climb destinations and special-level grab
  exceptions still need recovery and reference-video comparison.
- Full native barrier types, wall-controller branches and sword-expanded
  viewport bounds are not implemented by the initial body/wall check.
  The swept body test is still not equivalent to the native current/previous
  collision buffers; the supporting-foot correction does not replace those.
- Floor-aware foreground masks are not a complete translation of native
  character clipping and conditional rooftop drawing passes.
- Ordinary NPC pursuit, gap jumps and falls are now supported on these
  rooftops, including the supported alternate-row drop. Full inactive-world
  simulation, other vertical pursuit, special actors
  and all native `CutOpponent` lifecycle branches remain out of scope.
- Harbor tiles 47/48, the departure counter, ship catch/climb and water deaths
  are implemented for the end of level 1. The full native moving-obstacle bank
  and conditional pillar redraw pipeline remain incomplete. Boarding emits
  the original level-transition request; the host currently shows completion
  instead of playing the ending movie or loading level 2. Audio is unimplemented.

See [HARBOR_RECOVERY.md](HARBOR_RECOVERY.md) for the source predicates, room
route, rendering scope and integrated harbor regressions.

No replacement artwork or generic physics library changes the recovered
animation sequences. The prototype's 12 fps movement / 10 fps combat cadence
is unchanged.
