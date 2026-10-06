# Development History

Notes from the rooftop prototype's earlier iterations. Setup commands and
external workspace references below describe those revisions; use
[README.md](../README.md) for the current standalone setup.

## Earlier Setup

Run `python scene_prototype.py` from this directory. The local extracted assets
in `assets/` are required; `python extract_assets.py` recreates them from the
local `pop2.hfs` image when needed.

The default scene includes both opening-room guards, the initial guard and
the reinforcement generated from the left, plus the first rooftop room
transitions and terrain checks. After the opening encounter, continue left
to the next screen. Life, visited enemies and reinforcement counts persist
when returning to a room. Use
`python scene_prototype.py --no-guard` for the previous isolated animation test.
That isolated mode retains its old opening-room boundaries.
Use `python scene_prototype.py --peaceful` for terrain testing without guards;
unlike `--no-guard`, this keeps the real rooftop collisions and room links.

## Prototype controls

- The room starts with the original window escape: airborne exit, broken
  glass, curtain, landing and recovery. F5 replays it from any movement or
  combat state, including after changing rooms or falling. Input cannot interrupt the opening; held arrows are read when
  control returns. There is no intro movie or opening audio yet.
- Left/Right: plays the original run start (`SEQS:1`, `200`), continues through
  the run cycle (`SEQS:201-202`), and uses the native stopping animation
  (`SEQS:13`) after release at run poses 7/11, as in GenCtrl (6:11e4).
  It no longer waits for the entire run cycle. A tap still completes each natural phase.
  A fresh forward press within 27 pixels of an ordinary solid barrier uses
  the original short-step rule automatically, without holding Shift.
- Shift + Left/Right: use the original `DoStepFwd` distance-to-sequence rule.
  Terrain mode uses the native supporting-foot/barrier distance, with four
  pixels reserved before selecting a step. Clear floor returns distance 42,
  giving `SEQS:40` plus a two-pixel pre-offset (38 pixels total). Near a gap,
  shorter source sequences stop at the native edge, not the scenery tile edge.
  Another attempt plays the original stationary edge probe (`SEQS:44`);
  releasing and repeating the arrow deliberately steps beyond it (`SEQS:42`).
  Holding Shift and an arrow repeats ordinary steps, but cannot silently
  advance past the warning. Loose-floor/plate warning branches are decoded;
  falling tiles and gate triggers themselves are not implemented yet.
  Confirming the gap warning still causes a fall, but leaving below the
  viewport cannot incorrectly switch to a horizontally linked screen.
  Ordinary falls also use the native foot/floor alignment before their first
  pose. Overlapping flat facade pieces stay in front while a falling body
  crosses their floor row; shaded side artwork retains its separate back rule.
- Opposite direction while standing: play the original in-place turn
  (`SEQS:5`). If the direction stays held, the original controller jumps
  from turn action `48` into the run transition (`SEQS:43`), then starts
  running. A queued reversal can start after turn action `50`, without
  showing actions `51`, `52`, or idle. A queued forward jump can likewise
  start from turn actions `50`-`52`, skipping the remaining turn poses.
  Releasing the direction without another command lets the full turn finish
  at idle. Standing turn mode 7 bypasses the native barrier test, so changing
  sprite width cannot insert a wall bump or move the Prince away from it.
- Opposite direction while running: enter the original drift (`SEQS:6`) from
  run actions `4`-`14`. Its 13 poses (`53`-`65`) finish before the Prince
  changes facing and resumes the run cycle (`SEQS:202`).
- Up: vertical jump (`SEQS:28`). Up plus the facing direction: forward jump
  (`SEQS:3`); Up plus the opposite direction: turn (`SEQS:5`), or drift
  (`SEQS:6`) during a run. A second Up command after the turn's first pose
  can still queue a forward jump. Holding Up repeats a grounded jump directly
  after landing, without an idle pose. Up during an established forward run
  selects the running jump (`SEQS:4`) from run actions `7`-`14`. Holding Up and
  that direction repeats the running jump after each landing. Releasing and
  pressing Up again during the arc buffers one more running jump, even if
  that second press is released before landing. A single tap does not repeat.
  Up plus a direction during the first three run-start poses still selects the
  standing jump.
- Down: play the original lower animation (`SEQS:26`), hold its low pose
  (`SEQS:117`), and rise on release (`SEQS:49`). A tap still completes the
  lower and rise phases. Down plus the facing direction takes a crouched step
  (`SEQS:79`); holding the direction repeats complete steps, while a tap
  completes just one. A step requested during descent waits until the low pose.
  During a run, Down enters the lower animation directly from run actions
  `4`-`14`, without the normal stopping sequence.
- Down at a real ledge behind the Prince backs down with native `SEQS:68`.
  Face the building rather than the gap. Hold Shift to retain the grip;
  releasing Shift uses the native floor/wall-aware return (`SEQS:11`) or
  free fall (`SEQS:23`). Up climbs with `SEQS:10`/`235`
  and takes priority over Shift release; Shift is not required to climb.
  Up beneath a reachable upper ledge selects `SEQS:24`. A falling jump with
  Shift can catch a real edge using `SEQS:15`, subject to the original
  height, velocity and tile checks. A newly caught edge has a 12-tick grip
  delay before climbing. Over empty space, native hold sequence `210` sets
  release mode 11 at its end. Against an ordinary wall, the controller enters
  `SEQS:25`: poses `92, 93, 93, 92, 92, 91`, then a stationary hold at 91.
  Its mode-6 guard prevents restarting that settling animation each tick.
  There is no guessed two-second timeout. Climbing/descending
  updates the actual tile row, not only the sprite's drawing position.
  The old isolated `--no-guard` scene retains its experimental ledge path.
- Ctrl draws the sword (`SEQS:55`); another Ctrl attacks (`SEQS:75`, `203`-`205`).
  Drawing toward a rooftop gap/solid wall and automatically turning toward an enemy use
  the native pre-animation position adjustments, so drawing/turning after the
  opening no longer pushes the Prince off the roof.
  Up blocks (`SEQS:62`, `206`), and Down sheathes with the native short
  sequence `93` while a living enemy is loaded in the room/side rooms;
  otherwise it uses the longer `92`. A Ctrl press
  buffered during a block branches from action `150` into the original
  block-to-attack sequence (`SEQS:66`, action `162`), then continues with attack
  actions `152`-`157`. It does not insert guard or normal attack action `151`.
  Sword sprites use the original `Prince`
  SHAP resources, `CTBL:1005` colors, and the `Kid` AFRM attachment positions.
  Color index 250 has no entry in that CTBL and uses a capture-based estimate
  for the few source pixels that contain it.
- Left/Right with the sword drawn: advance in the facing direction (`SEQS:56`)
  or retreat in the opposite direction (`SEQS:57`), keeping the same facing.
  A tap completes one step; holding repeats steps. Advance uses actions
  `163, 164, 165, 158` and moves 18 pixels; retreat uses `160, 157, 158` and
  moves 16 pixels backwards. Both hold each pose for 100 ms. Another step
  starts after the guard pose, as in the original controller. One command
  can be buffered during a step. An attack can branch from final advance
  action `165` or retreat action `157`; a block can branch from `165`.
- Escape: pause. Any key or mouse click resumes; the resuming key is consumed
  until release, so it does not also move or attack. F2 opens the developer
  menu instead. The original `NFNT:23331` font draws `Game Paused`
  in the native HUD. Both actors and world timers stop; repeated key events
  cannot toggle pause repeatedly. Close the window using its Windows close button.
- Alt+Enter: toggle fullscreen; restore the previous normal/maximized window.
  Window resizing and fullscreen retain the 512x384 aspect ratio, with
  nearest-neighbor scaling and black margins where needed. The mouse cursor
  is hidden over the fullscreen game, visible in the developer menu and
  restored when returning to a window.
- F2: toggle the in-game developer menu over a dimmed, paused scene. Choose
  a supported level-1 screen and start at its entry position.
  Screen numbers follow the route from the opening (1), not internal room
  IDs: the building climb is screen 5. The right-hand secret is a separate
  entry. Teleporting resets guards, health and pending inputs. Other levels
  are not playable/selectable yet. Mouse, Tab/Shift+Tab and arrows navigate;
  Left/Right moves between the side-by-side `Go to screen` / `Resume` buttons.
  Enter/Space activates the focused control. Escape cancels an open screen
  dropdown first, then closes the menu. F2 closes it directly.
  `Peaceful (no guards)` hides and suspends NPCs, their contact/damage and
  their health meter, without disabling terrain. It takes effect immediately;
  `Resume` retains the current position and `Go to screen` starts the selected
  screen. Closing restores the pause state from before the menu was opened.
  Turning it off restores the retained guards. The choice persists through
  screen selection and F5, but is not saved after closing the program.

The pressed keys are sampled on every animation frame, following the original
`ReadKeyboard` priority: Up wins over Down, and Left wins over Right when both
are held. A newly pressed arrow still shows its first pose immediately.

New commands do not replace a protected movement animation that is already
playing. The port keeps at most one buffered command, but native controller
resets can discard it before the next transition. This is not an unconditional
queue of every key press. Up plus a horizontal arrow is one jump command;
pressing either key first produces the same buffered jump. A
running reversal begins at the next eligible run pose; other running commands
wait for the cycle boundary. A new command replaces the one buffered command,
so key mashing does not create a long backlog. If the stop animation has already begun, a queued arrow
branches after stop action `50`, without showing actions `51`, `52`, or the
idle pose `15`: the same direction resumes running, while the opposite one
starts a standing turn. Holding the arrow through that turn starts a run in
that direction at action `48`; releasing it during the turn cancels that
follow-up run.

The animation clock targets 12 fps for movement (about 83 ms per pose) and
10 fps in sword mode (100 ms per pose), matching the original timer's five/six
Macintosh ticks. The first draw pose still uses the movement interval, and the
first sheathing pose still uses the combat interval; later poses use the new
mode's interval. Following poses use fixed deadlines to
avoid rounding drift. A short arrow tap follows the source game's exact chain:
acceleration actions `1` to `8`, stopping actions `53` to `56` and `49` to `52`,
then idle action `15`. The full Shift step uses actions `121` to `132`; shorter
steps select their action lists from the original `SEQS` resources.

The running jump uses the original takeoff, arc, and landing poses (`SEQS:4`,
actions `34`-`44`). `DoRunJump` also aligns takeoff against the next two tiles
and rejects a jump requested too late; it does not extend the 225-pixel arc.
`GenCtrl` clears directional controls on pose `44` (6:074a-0760,
4:3e3a). A direction, jump or crouch request released during the arc is
therefore discarded there. The next running control pass reads the remaining
held keys, with backward input taking priority over Up (6:1216-1248).
Holding both horizontal arrows retains ReadKeyboard's Left priority; a
reversal cannot interrupt the arc or become a standing jump after landing.
The default mode now checks supporting feet and floor flags
from FRAM, applies gravity over gaps, and preserves a run or jump through
supported horizontal room transitions. Landing selects the source soft,
hard or fatal sequence from fall speed. The already-tested animation arcs on
flat ground are not replaced by new physics.

This is an initial rooftop collision subset, not the complete level engine.
Ordinary rooftop grabs, climbing, NPC falls and supported cross-room pursuit
are implemented. Full ceiling collision, special tiles, level completion
and sound remain unimplemented. See
[COLLISION_RECOVERY.md](COLLISION_RECOVERY.md) for source references and limits,
and [BEHAVIOR_MAP.md](BEHAVIOR_MAP.md) for subsystem ownership and recovery gaps.
[RECOVERY_INDEX.md](RECOVERY_INDEX.md) tracks individual branch coverage and
pending work; [RECOVERY_CATALOG.csv](RECOVERY_CATALOG.csv) indexes the known
named routines without claiming their logic is completely recovered.

## Data and implementation notes

Level 1 is resource `LEVL:2000`, uses the Rooftops graphics, and starts in room
4 at tile 2. Run `python render_opening.py` to render the room and a contact
sheet of the extracted player sprites into `rendered/`.

The opening room is rebuilt from the resources on startup, not loaded from an
old flattened PNG. Rooftop SHAPs are decoded once and reused when building
other rooms; obtaining a screen label or F2 list does not render any rooms.
Scenery and foreground remain separate. Each actor has a
floor-dependent foreground mask: the palace parapet hides the lower legs on
its own floor. Airborne bodies retain intersecting flat foreground pieces
until they clear them, even when physics has already advanced the floor row.
The sloping ledge uses the native 17-22-pixel foreground strip, rather than
covering characters with its entire 51-pixel scenery shape.
The near facade's foreground SHAPs also cover a right-facing catch, including
the upper parapet while hanging below its floor. The body stays behind the
building, as in the Macintosh comparison, rather than being drawn over its
front. The shaded side remains background, so a left-facing catch is visible.
During a climb, the upper roof's near face and ledge remain in front even
before SEQS:10 advances the physical floor row at pose 141. The shaded side
remains behind the actor. Mode 1 indexes the drawn rectangle as in IndexChar;
other modes retain the supporting-foot index. Broad overlap-only climb
masks from earlier attempts have been removed.
This is a rooftop drawing subset, not the full native ClipChar/drawing pipeline.
The October 5 r2 update also handles inward wall movement from an already
overlapping landing pose, so releasing an upper-ledge jump cannot enable
Shift steps into the solid building junction. Ordinary guards use EnGarde's
ready-pose front/behind cell checks before voluntarily advancing or retreating.
These AI checks use the anchor column loaded by DoOppInput; fall physics still
uses the current FRAM supporting foot. Guards can still tumble from combat
damage and genuinely unsupported terrain.

The October 5 r3 update restores all eleven native rooftop decoration IDs
and their original offsets/drawing passes, including pieces attached to empty
cells. Missing corner/cornice shapes had cut off the right-hand buildings.
Foreground corner pieces retain their row ownership during catches/climbs;
back-pass pieces do not become an opaque actor mask.
Grounded sword collisions now distinguish front bump 64 from rear bump 65.
The selected response pose is checked too, so a wider pose cannot undo the
wall correction. Interrupted sheathing clears its host-side command lock;
retreating/sheathing at the screen-5 junction can no longer leave controls
frozen. Near-wall forward taps use the native automatic short-step branch.
Guard drawing now supplies each actor's actual pose/bounds/FRAM record to
foreground masking. Exact screen-5 corpse visibility remains a reference
comparison to finish, not a reason to change the source floor height or hide
all dead actors.

The October 5 r4 update addresses the remaining climb clipping in the
`screen 3 comparison.mp4` and `screen 4 comparison.mp4` recordings. After the
pose-141 floor transition, the right-facing actor could lose its near-facade
mask and show hands/legs over the parapet. The overlapping flat foreground
now remains in front throughout poses 135-148, in both ascent and descent.
This is a directional rooftop mask correction, not a new collision boundary
or animation change. The shaded-side ledge rules and native half-redraw
fallback remain separate. Real scene tests check foreground pixels for every
climb pose in rooms 2/0 (screens 3/4), plus descent and a second climb.

The October 5 r5 update covers the earlier jump-to-catch transition in
`screen 3.mp4` and `screen 4.mp4`. Fall poses 102-106 lost the upper parapet
and corner mask as soon as physics advanced the supporting row, exposing
the body before the catch. Intersecting flat foreground SHAPs now remain in
front during airborne modes 3/4, including falls that do not catch. Sloping
side strips keep their existing behind-actor rule. No positions, sequences,
or animation deadlines changed. Real key-handler tests cover both buildings,
three takeoff positions, early/late Shift and no Shift, from takeoff through
catch/climb or an uncaught fall.

The October 5 r6 update corrects the supported hold's missing settling
animation, shown in `Desktop 2026.10.05 - 19.20.25.22.mp4`. GenCtrl at
6:1926 bypasses the ordinary IsWall branch while animation mode is 6,
letting SEQS:25 reach its terminal hold at pose 91. Previously the port
restarted at 92 every tick. Descent/climb sequences and global timing are
unchanged. The left-facing gate branch remains a separate repeated selection;
ship/other special-level exceptions are not covered by this correction.
Tests verify all six settling poses, the stable hold, both catch directions,
release/climb priority and the existing foreground regressions.

The October 5 r7 update fixes a fresh Up buffered during a running jump,
shown in `Desktop 2026.10.05 - 21.54.36.25.mp4`. The command now retains its
running context while SEQS:4 finishes; it dispatches on the next legal
run pose (GenCtrl 6:1230 / DoRunJump 6:1c14), instead of waiting for a full
run cycle and starting a standing forward jump. Tests cover every arc pose,
both directions, short/held second presses, and actual rooftop physics.
The existing held-Up repeat, source poses, takeoff checks and timing are unchanged.

The October 5 r8 update corrects the wall-edge conversions shown in
`Desktop 2026.10.05 - 22.09.22.26.mp4`. GetColDetData (4:53b8-53ca) tests
strict overlap: a body touching the wall's exclusive right edge must not
trigger a bump. GetBarrDistFromFace (4:65d8) likewise measures a right-facing
body using its exclusive right edge. The incorrect extra pixel interrupted
short steps at their wider poses and selected SEQS:47, pushing the Prince
back before he could finish. Tests cover clearances 5-26 in both directions,
touch versus penetration, repeated screen-5 taps and the existing collision
regressions. The recorded Macintosh short step and the port both finish at
X=233; a deliberate bump from that position still settles at X=245, as in
the recording. These are validation coordinates, not hardcoded wall targets.
Source sequences, clocks and scenery are unchanged.

The October 5 r9 update separates standing crouch (SEQS:50, 16 pixels of
source displacement) from running crouch (SEQS:26, 26 pixels). StairClimbing
6:0f4e calls 6:1068's ordinary fallback 50; running GenCtrl 6:125a selects 26.
Using 26 for both made the standing crouch collide too soon near the
screen-5 wall in `Desktop 2026.10.05 - 22.27.53.32.mp4`. GenCtrl 6:06b4/099a
also handles input on the first displayed pose 109, without waiting for
another low frame or the end of the SEQS resource. The port now follows
that gate for release and the next crouched step. Tests cover the native
offsets in both directions, run versus standing selection, low-pose input,
and real wall/crouch/recovery physics. Genuine crouch/rise wall bumps are
retained; this does not disable collisions or change the animation clocks.

The October 5 r10 update addresses the four wall interactions recorded in
`Desktop 2026.10.05 - 22.53.59.36.mp4`. CheckBarr's mode-7 exclusion (4:4e46)
preserves the whole standing turn; repeated reversals do not accumulate a
collision offset. CheckCollide1 (4:551a/5586) ignores rear barriers while
grounded and unarmed. PutSwordAway (6:2594) clears sword mode before its
first pose, retaining the host animation lock until completion. Drawing
toward a solid wall now reserves the same native 56-pixel clearance as the
gap branch, before SEQS:55 starts. GenCtrl's release helper (6:1a84-1b7c)
checks the current and behind tiles, applies its facing-relative offset,
and selects floor return 11 versus free fall 23. The controller no longer
consumes a release pose before the normal animation tick.
Tests use actual key handlers, original resource pose/offset chains, both
draw directions, six consecutive wall turns and full post-retreat sheathing.
Special-level release branches and the complete native collision buffers
remain unported. Source animation resources and timing are unchanged.

The October 5 r11 update fixes the extra partial jump after a wall bump in
`Desktop 2026.10.05 - 23.31.49.40.mp4`. Wall contact still cancels the active
jump, automatic repetition and buffered command, but no longer clears the
already-consumed Up press. Clearing that flag made Up release enqueue a
second jump through the short-tap fallback, or retried it while Up was held.
A fresh press remains usable after recovery. This is a host input-state fix,
not a new animation or a complete translation of native input consumption.
Tests cover both wall directions, both chord orders and early/late/held Up.
Original collision sequences, their positions and timing are unchanged.

The October 6 r12 update translates ordinary `DoOppTumbleSeq` selection:
in addition to forced edge/room cases, a room's generation-point packed LIFE
bit `0x80` enables `Rnd(3)` versus the registered dead-NPC count, with a
same-cell settled-corpse fallback and native facing/tile vetoes. A fatal
strike can therefore select `185` away from an edge. Mode 9 uses original
poses 213-218, SEQS offsets and +6/capped-63 gravity, bypassing roof barriers,
floor landing and room cuts (FrameAdv 2:65ee-6664). Its row follows absolute
Y; it freezes offscreen at 730 rather than becoming a floating flat corpse.
Ordinary mode-9 roof clipping is bypassed (4:4210-422c); the special 16/19
draw cap remains outside the supported scenery subset. Flat deaths retain
85/213, with the native slot-parity variant 195/228 for odd NPC slots; this
is deterministic, not an extra RNG roll. No blanket corpse-hiding rule was
added. Exact flat-corpse screen-5 pixels still require a matched Mac capture.
Regression tests cover the selection branches, both corpse variants, the
complete tumble trajectory, offscreen settling and the native 33-pixel stop
displacement at both supporting-foot gates. Player movement is unchanged.

The October 6 r13 update replaces the separate Windows developer dialog with
a native-viewport overlay. It uses the original bitmap font, nearest-neighbor
presentation, a darkened scene, screen dropdown and peaceful checkbox. Menu
input is intercepted before gameplay bindings, with viewport-relative mouse
coordinates and a visible cursor in fullscreen. Opening pauses both actors;
closing restores the previous pause state without an input/timer backlog.
Outside the menu, any key/click now resumes Escape pause without consuming
that key as gameplay. This is port QoL, not a recovered original menu. Guard
death rules, movement, artwork and animation clocks are unchanged from r12.
The active window title includes `r13`.

The original DATA row anchors are `125, 245, 365` (five pixels below the
tile grid), while CODE:4 `0x31fa` puts the Prince's floor at `row * 120 + 106`:
`226` for this rooftop. These are separate coordinate rules.
Character drawing also follows `AddMid` at CODE:3 `0x0302`-`0x030c`:
the bottom pixel is inclusive, so sprite top is `bottom Y - height + 1`.
Scenery still uses `anchor Y - height` without the extra pixel.

CODE:23 `DrawRoofBackWall` supplies the missing sky fill behind transparent
wall pieces. The curtain follows `DrawRoofGlass` and its original
frame/offset tables. The room's
`510x365` clip is centered in the emulator's `512x384` display; the bottom band
is reserved for the future HUD. All scaling remains nearest-neighbor.

The opening scene, tiles, sprites, animation sequences, and frame-to-sprite
mapping come from the local Macintosh resources. Kid SHAP sprites face
left, so the prototype uses facing `0` for left and `1` for right. The opening
exit starts facing right. The original
`SEQS:5` animation toggles the facing. The running drift in `SEQS:6` keeps the
old facing through action `65`, then toggles it before `SEQS:202`.

The window escape is isolated in `pop2/opening_animation.py`. Main CODE:2
`0x5d56`-`0x5ed8` supplies its tile-based X adjustment, nine pre-advances of
`SEQS:4`, Y reset, and first displayed action `43`. The transition consumes
jump action `44` and fall setup action `102` before displaying `103`, as in
`first screen.mp4`. `SEQS:21` then enters `SEQS:12`; the velocity opcode sets
8 pixels of horizontal speed and 15 of vertical speed. CODE:4 `0x341a` and
`0x3464` add six pixels of gravity per falling tick. The rooftop landing uses
`SEQS:17`, followed by the unheld crouch's `SEQS:49` recovery. These are the
opening's specific controller transitions, not a complete port of StartFall
or the terrain engine. Control returns at action `15`, X=411, bottom Y=226.

The curtain uses CODE:23 `AnimRoofGlass`/`DrawRoofGlass`, DATA/A5 `cd00` and
`cd1e`, and `SHAP:3588-3596`. The broken glass uses the original composite
sprites `SHAP:3597-3608` and the `(Y, X)` table at DATA/A5 `cd42`. The glass
mob advances once before the first room draw, so its first displayed index is
1 and its final index is 11. Neither effect uses generated particles or new
artwork. All three timelines remain on the movement clock of 12 fps.

The input priorities are from `PoP2-Mac-Code-Recovery/code/02.asm`,
`ReadKeyboard` at CODE:2 offset `0x55d2`. The step calculation is from
`PoP2-Mac-Code-Recovery/code/06.asm`, `DoStepFwd` at CODE:6 offset `0x1276`:
reserve 4 pixels, choose `SEQS:42` for 42 or more pixels, otherwise use
`SEQS:28 + floor(distance / 3)` and apply the remainder directly to X.
The default mode supplies clearance from linked rooftop tiles. This is still
a simplified clearance scan, not the complete native barrier-distance routine.
The early run transition during a standing turn comes from `GenCtrl` at CODE:6
offset `0x1014`, which switches to `SEQS:43` at action `48` when forward input
is held. The same pose handler also applies to the long sword sheath, allowing
a held forward run to resume before actions `49`-`52` without changing the
earlier sheathing poses or the movement/combat clocks.
The running reversal follows `GenCtrl` at offset `0x11e4`, which selects
`SEQS:6` for opposite input during run actions `4`-`14`. The stopping sequence
`SEQS:13` is selected when horizontal input has dropped to zero, so a queued
opposite direction takes priority over an earlier key-release request.
The same run handler selects `SEQS:26` for Down after the run-stop and
opposite-direction checks; if horizontal input has just been released at
action `7` or `11`, it stops first.
Once stopping has started, `GenCtrl` routes actions `50`-`52` through the
normal input path at CODE:6 offset `0x0c32`. Opposite input calls the turn
routine at `0x10e4` and switches to `SEQS:5`; forward input calls `0x11a0`
and starts `SEQS:1`. Neither path needs to wait for the stop to reach idle.

The sequence interpreter currently handles the operations needed by the tested
movement paths, including sequence transitions, facing changes, horizontal and
vertical offsets, animation state, and the callback used by the opening run.
Unknown operations stop execution instead of being silently ignored. The
Macintosh executable remains the behavioral reference; the Apple II source
archive is not source for this version.

The frame cadence comes from `ResetFrameVars` at CODE:2 offset `0x68c8`:
the sword-mode flag selects six ticks, otherwise five. Both the original sword
reference video and the side-by-side attack recording show the same seven
attack poses; the former holds each pose for approximately 100 ms.

The block-to-attack rule comes from CODE:6 offsets `0x27e8`-`0x2808`:
an attack requested at action `150` or `161` selects `SEQS:66` instead of
the normal attack `SEQS:75`. The prototype consumes the buffered attack on
the next combat tick, before `SEQS:206` applies its return-to-guard offset.
The resource's own offsets preserve the position through the combination.
The three combinations in `Desktop 2026.10.02 - 12.40.23.17.mp4` confirm
the pose order `169, 150, 162, 152, 153, 154, 155, 156, 157, 158`, at roughly
100 ms per pose. A late attack, after returning to guard, remains a normal
attack. Enemy contact and parry interactions are implemented for the first
ordinary guard, as described below.

Sword movement follows `DoAdvance` at CODE:6 offset `0x1dda` and `DoRetreat`
at `0x1d6e`. For the Prince (actor types 0/1), these routines select `SEQS:56`
and `SEQS:57` only from guard actions `158`, `170`, or `171`. Each resource
supplies its own horizontal offsets. The isolated steps and repeated movement
in `Desktop 2026.10.02 - 13.09.36.22.mp4` show those same pose lists and
approximately 100 ms intervals. Attack transitions at the last step pose
come from CODE:6 `0x279a`-`0x27fe`; the forward-step block transition comes
from `0x2844`-`0x2870`. Releasing a direction finishes the current step,
and changing directions queues a step without turning the Prince.

## First Room Combat

This is a first playable encounter, not a finished translation of every AI or
terrain branch. The October 2 reference recording
`Desktop 2026.10.02 - 15.21.50.26.mp4` is the visual comparison reference.
The later `Desktop 2026.10.02 - 21.05.38.06.mp4` supplies the comparison
for automatic sword turns and hit bursts.
`Desktop 2026.10.02 - 21.34.57.12.mp4` shows unarmed-hit recovery and the
fatal vertical-jump hit.

- The guard generator comes from `LEVL:2000`, room 4, at offset `0x23e8`.
  It supplies row 1, scene X=149 (native X=356), facing right, skill 0, `SEQS:77`, and one
  life. `SetOppMaxLifePts` at CODE:6 `0x2b44` reads its maximum life field.
- The second guard comes from the room's separate generation point at
  `0x3a9e`, not a copy of the initial spawn or a new invented death timer.
  CODE:6 `CheckOppGenPts`/`IsTimeToGenOpp` count five eligible frames, skip
  every third world frame, then consume this point's one reinforcement.
  The Prince must be more than two columns from the entry; a living guard
  between that entry and the Prince can prevent generation. This normally
  means the second follows the first guard's defeat, but death is not the
  actual sole trigger. A pursuing guard approaching from a visited room also
  counts in this corridor, even before ownership transfers at the screen cut.
  This prevents a duplicate reinforcement ahead of an incoming pursuer; it
  is not an invented global one-guard limit.
- It enters from scene X=-102, facing right, with profile 0 and one life.
  Its original `SEQS:84`/`208` provide the run startup and cycle; the native
  odd-pose/distance checks select braking sequence `101`, then draw `90`.
  The incoming unarmed controller still runs when the Prince leaves its
  eligible current/alternate floor or dies: it brakes with `101` and returns to standing `77`/action `166`,
  rather than freezing its decisions while its running animation continues.
  Offscreen entry is allowed without clamping it instantly to the screen edge.
  Each NPC retains its own animation, life, profile and contact state. The
  first corpse remains in the room and can be hidden by the foreground.
- The closest living guard on each side can engage; additional guards on
  the same side wait. The supported flat-rooftop branches use the original
  waiting/spacing gates, including the last explicitly selected NPC sequence
  rather than its internal run-loop sequence. The active combat target and
  enemy health meter switch to a living guard when the old target dies.
- The guard uses `Guard.rsrc`, `CTBL/FRAM/AFRM:750` and the original sword
  attachments. Its action-to-frame mapping follows CODE:4 `0x2b0e`.
- Drawing/advancing/attacking use the NPC sequences `90`, `86`, and `58`,
  rather than reusing the Prince's corresponding sequences. A reversal plays
  `SEQS:60`; an in-progress step is not interrupted by an instantaneous flip.
- Ordinary-guard pursuit, close retreat, attack and defence use the recovered
  distance checks and DATA skill tables from `EnGarde`, `OpponentClose`,
  Defence and Strike (CODE:4 `0x098c`, `0x111a`, `0x1204`, `0x12c6`). Skill 0
  has zero autonomous block/counter chance. The original DATA/ZERO startup
  expansion now supplies the correctly associated tables; pursuit is 255/256,
  ordinary armed-target attack is 75/256, not the earlier swapped values.
  See [AI_RECOVERY.md](AI_RECOVERY.md) for the extraction and remaining limits.
- Facing-relative distance uses CODE:4 `0x49ee`, including the 21-pixel
  opposing-facing correction. It is not a generic sprite-box collision.
  Strike ranges follow CODE:6 `0x5b38`, including unarmed and rear-hit cases.
- Contact is checked only on the native attack poses: `153`/`154` can be
  parried, and `154` deals damage. A defence at `150`/`161`, opposing facing,
  and distance 61-99 selects the attacker's original blocked sequence `69`
  and defender pose `161` (CODE:6 `0x5978`-`0x5ab0`). A queued Ctrl can then
  use the existing block-to-attack sequence `66`. Counterattack preparation
  pose `162` is not a block, despite its visibly raised sword.
- Native hurt/death sequences `74`, `94`, `183`, `85`, and `213` replace
  input while hurt or dead. Each ordinary hit removes one life, with only one
  damage event per swing. If both swords would deal damage in the same cycle,
  `CheckStab` clears the Prince's pending wound before hurting the guard
  (CODE:6 `0x50ec`-`0x50f6`), so there are no traded hits. An enemy strike still
  hits when the Prince's strike misses. A flat corpse uses action `185`, or
  `228` for an odd NPC slot. DoOppTumbleSeq can instead select `SEQS:185` with
  original poses 213-218, either through the forced terrain cases or the
  generation-point/death-bank/random branch above. This mode-9 actor falls
  in front of the rooftop, not onto its lower floor or back into combat.
- A normal hit arms the previously unarmed Prince immediately, without an
  extra draw animation: CODE:6 `0x53f8`-`0x5406` sets the sword flag. The hurt
  sequence returns to `227` in combat mode, not to an invented unarmed idle.
  The scene and encounter retain the same sword state through recovery.
- `CheckStab` at CODE:6 `0x523e`-`0x5268` applies lethal damage during native
  sequences `10`, `16`, `28`, and `14`; `28` is the tested vertical jump.
  Only a valid contact at the damage pose triggers this rule. It is not a
  blanket rule for airborne sprites or an Up key queued for later. Horizontal
  jumps and the landing sequence retain ordinary damage. Hurt/death resets
  the vertical anchor and fall velocity (`0x5478`-`0x547e`).
- With a drawn sword, the Prince turns toward the engaged first-room guard
  when the guard is behind him. CODE:6 `0x2166`/`0x2770` select `SEQS:127`,
  including its own facing change, poses and offsets, then `245`/`227`.
  The original control-state and -15-pixel distance checks protect unavailable
  animation phases and close overlaps. The turn retains one buffered command.
- Successful hits, including fatal hits, draw the original Kid shape index
  `218` (`SHAP:25220`) for the first hurt/death pose only. CODE:3 `0x07dc`
  and `0x0ba4` supply the trigger and body-relative offsets for each fighter.
  Repainting does not restart or consume the effect; misses and parries do
  not produce blood. Foreground scenery still occludes the effect.
- Health uses the original Kid shape indices `297`-`300`, with three red
  bottles for the Prince and one blue bottle for this guard. Positions follow
  `DrawKidMeter`/`DrawOppMeter` at CODE:3 `0x4902`/`0x4a8e` in the native HUD.
  At one remaining life, the first red bottle alternates full/empty on the
  world-frame parity, following CODE:2 `0x5442`-`0x546c`. Healing or death
  ends the blinking; redraws and key events do not advance its phase.
- F5 resets all fighters, lives, reinforcement point, opening, held/buffered commands and the AI
  clock. Key callbacks cannot advance the guard faster than the animation
  clock. Movement remains 12 fps; sword mode uses the existing 10 fps clock.

The opening and ledge hold/climb are protected from combat
contact; ordinary jumps use the source vertical-distance check. Falling also
locks out new player commands and combat contact. Grounded guard movement
uses the rooftop physics rather than clamping X to one room. Pursuers can
transfer between visited horizontal rooms and jump the supported gaps with
the original NPC sequence 100. Automatic sword handling outside these
tested damage/turn paths, combat sound and full AI parity still need their own source-guided
implementation/comparison. No generated replacement artwork is used.

Unarmed contact with a grounded opposing guard uses FrameAdv 2:6c64-6daa.
Its actor-type-1 exclusion must not be confused with animation mode 1, which
is used by ordinary jumps. The port also sweeps the displacement of jump
sequences 3/4 through the native distance interval: a 49-pixel jump step must
not skip contact between sampled frames. It uses the existing bump sequences
46/47 and offsets, not a new jump arc or a blanket restriction on every NPC.
The sweep is a port collision safeguard, not a claim of exact native frame ordering.

## Recovered Enemy Profiles

`assets/enemy_profiles.json` preserves all 12 skill profiles, all 86 initial
enemy generators and the separate reinforcement points in `LEVL:2000`-`2013`,
including raw words, native entry positions and initial actor-type overrides.
Regenerate it from the preserved, unmodified resources:

```powershell
python tools/extract_pop2_enemy_profiles.py
```

Run that command from the workspace root, not the prototype directory.
The runtime uses this extracted data directly for AI probabilities and hit
pauses; the standalone prototype does not need the original program fork.
QuickDraw-style random rolls have the original inclusive 0-255 range.

The ordinary first-room controller separates `EnGarde` decisions from
`GenCtrl` command gates. It preserves the native defence/strike roll order,
attack-over-block input priority, final-step attack transitions, close-block
versus retreat distance checks, anticipating attacks against approaching runs
and jumps, and the attack/parry/hit/sheathing pauses. Repeated key events do
not advance those timers. The first-room reinforcement and ordinary
same-floor target/spacing branches are implemented. Initial guards and
reinforcement points are loaded per visited room, retaining their state on
return. Special enemies, full terrain/alert logic, gates and remaining cross-room controller branches
still need separate work; this is not full multi-guard parity for every map.

Initial guard word +0x14 and reinforcement flags determine jump eligibility.
AutoCtrl's poses 192/196 examine the gap, and DoRunJump supplies the original
13-pixel anchor look-ahead and 75-pixel NPC takeoff reserve. The 11 jump poses
202-212 retain their original displacement and timing. Pursuing guards keep
their identity, health, skill and palette across screen changes; an offscreen
reinforcement must enter its spawn room before a room cut is permitted.
Only visited horizontal rooms and already engaged pursuers are simulated;
this is not the complete original inactive-world or special-enemy engine.

Verification: `python -m unittest discover` includes the existing movement
regressions plus native guard rendering, range boundaries, parries, simultaneous
hit priority, native automatic sword turns and impact rendering, unarmed-hit combat
recovery, vulnerable-sequence lethal hits, health/death,
key-repeat timing, reinforcement eligibility/countdowns, offscreen entry,
per-NPC state, F5 reset and complete input-driven
opening/defence/counterattack/two-guard-defeat/room-exit scenarios. Terrain
regressions cover native room links, supporting-foot offsets, floor flags,
gravity, landing damage, wall sweeps, gap jumps, room revisits and unchanged
flat-ground animation arcs. Scene tests exercise the actual Tk renderer,
including falling-body pixels at the roof corner, continued simulation after
the secret-room jump, and reinforcement braking through a player fall/death.
`tests/test_rooftop_pursuit.py` adds full NPC jump chains in both directions,
two- and three-tile gaps, takeoff alignment, persistent multi-screen pursuit,
entry ownership, low-life blinking, supporting-foot wall correction during
a fall, the ordinary NPC's fatal landing threshold, incoming-pursuer generation
blocking and fatal edge tumbles. Wall-supported holds, free-air grip expiry,
Up-only climbs and conditional ledge masks have separate regressions.

The October 4 recordings `Desktop 2026.10.04 - 00.23.45.21.mp4` and
`Desktop 2026.10.04 - 00.26.07.22.mp4` provide port/reference comparisons;
`goofy.mp4` adds a return-route regression.
Static junction artwork matches the reference; it is not replaced with a
new floor or wall to disguise actor-control problems. CODE:23 `0x0614`-`0x06c6`
also supplies the Prince's conditional ledge-overlap predicate for climbing,
falling and specified hang poses. The mask renderer remains a subset of the
original drawing engine, not a guarantee of pixel parity in every scene.

The right-facing gap catch no longer loses its body behind the next facade.
Foreground masks retain native tile ownership and use `IndexChar`'s supporting
foot/behind-cell selection with `DrawForeImg`'s two foreground cells. Ordinary
floor pieces also occlude all overlapping actor pixels, following the full
rectangle marking in MarkPeelForeBufs/MarkBufsForRect; limiting them to two
cells exposed the extended combat foot through the next parapet. Scenery,
sprite artwork and animation timing are unchanged. Tests
check the caught body's pixels, stationary scenery and both facing indices.
The climb's partial floor redraw also uses the original ten `ComputeHalfRect`
rectangles, avoiding a full-parapet overlay across the torso at poses 135-144.
Reinforcement blocking now also counts neighboring living entry actors
before pursuit begins, preventing a duplicate while returning between
screens. Death releases that block through the existing generator rules.

The October 4 22:54 recording adds regressions for combat-foot occlusion,
stationary wall-supported hanging, and jumps through engaged guards.
The earlier hold interpretation incorrectly reselected SEQS:25 on every tick,
retaining 92. The October 5 r6 review recovered GenCtrl's mode-6 bypass at
6:1926: ordinary wall support plays its six settling poses once and holds 91.
Both-facing scene tests cover stationary NPC contact and contact with the live AI.

The October 5 00:35 comparison distinguishes the large building's shaded
side from a physical gap. At the screen-5 junction, Collide's solid-floor
branch uses SEQS:47/46 rather than the empty/high GroundBump (45). Running
against the wall no longer produces a temporary drop through the floor.
Wall sweeps now compare the previous and current body rectangles, so a
changing sprite cannot bypass the wall even if its anchor barely moves.
Tests follow 80 held-run ticks, Up-only climbing after the bump, and actual
head/arm/body pixels during the climb. Existing guard-contact and combat-foot
regressions remain in the full suite. The updated window title ends in
`(2026-10-05)` to distinguish it from a stale running copy.
