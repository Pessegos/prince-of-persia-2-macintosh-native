# Macintosh Enemy AI Recovery

This document distinguishes recovered data from implemented behavior. The
Macintosh executable is the reference, not a DOS source reconstruction.

## Original Data

`tools/extract_enemy_profiles.py` expands DATA:0 using ZERO:0 exactly as
the executable startup does at CODE:1 `0x00da`-`0x00ea`. CODE:0 specifies the
22,266-byte below-A5 allocation. Reading the compressed resource as a plain
global array would give incorrect addresses. The exported JSON records the
original resource-fork SHA-256 values, offsets, profiles and generators.

The action tables are selected by their actual CODE:4 references:

| Table | A5 Offset | Routine |
| --- | --- | --- |
| Advance | -0x3638 | OpponentClose, 0x11ee |
| Block | -0x3668 | Defence, 0x12b2 |
| Reblock after parry | -0x3650 | Defence, 0x128e |
| Counter from block | -0x3680 | Strike, 0x135e |
| Ordinary strike | -0x3698 | Strike, 0x1388 |
| Pause after enemy is hit | -0x36ba | CODE:6 0x514a |

Earlier prototype code had advance/strike and counter/reblock assigned to the
wrong tables. The recovered association replaces those constants, not merely
a subjective adjustment to the guard's aggression.

Each probability is `Rnd(255) < threshold`, with 256 possible values. A 255
entry is not a guaranteed action. These are conditional decision probabilities,
not attacks per second, and an accepted roll can still fail the animation gate.

| Profile | Advance | Block | Reblock | Counter | Strike | Hit Pause |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 255 | 0 | 0 | 0 | 75 | 20 |
| 1 | 200 | 150 | 75 | 0 | 100 | 20 |
| 2 | 200 | 150 | 75 | 0 | 75 | 20 |
| 3 | 200 | 200 | 100 | 5 | 75 | 20 |
| 4 | 255 | 200 | 100 | 5 | 75 | 10 |
| 5 | 255 | 255 | 145 | 175 | 50 | 10 |
| 6 | 200 | 200 | 100 | 20 | 100 | 10 |
| 7 | 0 | 250 | 250 | 10 | 220 | 10 |
| 8 | 0 | 0 | 0 | 0 | 0 | 0 |
| 9 | 255 | 255 | 145 | 255 | 60 | 10 |
| 10 | 100 | 255 | 255 | 255 | 40 | 0 |
| 11 | 100 | 255 | 175 | 150 | 60 | 0 |

`QuickDrawRandom` reproduces the valid-seed Mac II ROM algorithm at `0x1d7ec`:
seed * 16807 modulo 2147483647, return the low word, replace 0x8000 with zero.
PoP2's CODE:17 `0x6e06` treats that word as unsigned and reduces it modulo
limit + 1. Apple's contemporary explanation confirms the seed formula in
[develop 21, Macintosh Q&A](https://vintageapple.org/develop/pdf/develop-21_9503_March_1995.pdf).
The prototype does not reproduce all other original consumers of the shared
random stream or its startup seed, so matching one recording's exact fight
is not a valid parity test.

## Per-Enemy Differences

Generators are 38 bytes, with up to five per room. The extraction retains all
19 signed words, not only health and skill. CODE:6 `InitOpps` at
`0x2bd2`-`0x2c0e` can preserve a generator's special kind instead of replacing
it with the level's default; the DATA mapping then supplies its actor type.

- The opening ordinary guard is profile 0 with one life. Room 5 of the same
  level has profile 1 and three lives.
- LEVL:2002 (the third level) includes profiles 0, 2, 3 and 5 for its initial
  skeleton actors. Native room 20 is profile 5, with a stronger block/counter
  profile than rooms 11 and 15. Identifying it as the exact extra-potion route
  still requires tracing that room's map links.
- LEVL:2011 has ordinary actor-type-2 generators and a preserved kind-1,
  actor-type-10 override in native room 7, starting at sequence 105. This is
  evidence of a special opponent, not proof that it is the specific guard
  described in the user's temple puzzle.
- Some raw life fields are 105 and some initial sequences are dormant or
  special. The JSON exposes these literally. They must not all be treated as
  ready, ordinary guards with that many displayed health bottles: awakening,
  resurrection and special initialization can change the state.

## Implemented First-Room Rules

- EnGarde `0x098c`: close/range/far branches; wait for poses 102-117 in
  falling-recovery state 5; anticipating strikes against run poses 7-14
  below distance 150, or jump poses 34-43 below 186.
- InRange `0x0466` and `0x109e`: direct attacks against unarmed/back-facing
  targets; armed, opposed-facing targets use Defence followed by Strike.
  The armed-target upper range boundary is excluded for AI selection even
  though contact damage includes both boundaries.
- OpponentClose `0x111a`: skill 0 ignores the 15-frame advance pause; other
  profiles wait. Pursuit reads its own table, including at distances 99-116.
- Defence `0x1204`: only opponent poses 152/153/162 request a block roll.
  The four-frame parry window chooses the separate reblock table.
- Strike `0x12c6`: no strike roll against poses 169/151. Own block poses
  150/161 select the counter table, not the ordinary strike table.
- GenCtrl/DoStrike `0x24bc`/`0x2780`: attack input takes priority over block.
  Poses 157/158/170/171/165 select NPC sequence 58; 150/161 select 66.
  A failed pose gate does not fall back to a lower-priority block command.
- DoBlock `0x282a`: ordinary NPC defence at distance >=74 retreats; a closer
  opponent at pose 152 allows sequence 246. Own blocked-attack pose 167 can
  select sequence 61. A parried block without a counter retreats via 57.
- DoAdvance/DoRetreat `0x1dda`/`0x1d6e` only start steps at 158/170/171.
- CODE:6 `0x2522`, `0x25ae`, `0x514a`: player attack sets approach pause to 15;
  sheathing sets attack pause to 9; a hit uses the struck enemy's profile
  pause. AutoCtrl `0x4e98` decrements these shared timers on each NPC call,
  not once per world frame.
- Prince strike range at `0x5c18` tests the target's engagement field, not its
  sword flag. The ordinary NPC range branch still tests the Prince's sword.
- Sword contacts at CODE:6 `0x581c`/`0x5856` run NPC-first, then Prince;
  contact marks a pending wound without immediately applying a hurt pose.
  CheckStab `0x50dc` processes wounded NPCs first. At `0x50ec`-`0x50f6`, a
  wounded NPC clears the cached Prince's wound marker (animation state 10
  becomes 1), before the player-damage check at `0x5178`. Thus two successful
  sword contacts in one cycle hurt only the NPC, even when the NPC dies.
  A missed Prince strike does not cancel a successful enemy strike. The
  earlier prototype's explicit traded-hit behavior did not match this rule.

No new animation assets, guessed aggression constants, or output audio filters
are introduced by this change. Opening/movement cadence and player controls
retain their existing tests.

## Prince Held Defence And Late Blocks

PlayerCtrl samples and saves the input bank before GenCtrl consumes it
(`4:3cd2-3d0a`, save/restore `4:3e50/3e60`). Held Up is therefore read on
subsequent control cycles, not only on the Windows key-down event. OnAlert
`6:250c-255e` gives a pending strike priority over Up; it does not make the
whole attack an active block. Successful block/counter and forced-recoil
priority remain unchanged.

Prince DoBlock `6:2844-28e6` accepts poses 158/170/171/168/165. Opponent pose
168 vetoes that ordinary block. Against opponent pose 153, DoBlock calls
AnimChar once immediately, before the frame's normal AnimChar; sequence 62
thus reaches protected pose 150 without showing startup pose 169 first.
Own blocked-attack pose 167 can select sequence 61 directly, without waiting
for idle guard. This is important when held Up follows a strike that the
enemy parries. Sequence 61 keeps its original retreat offsets and poses
159/160/150. Attack poses 152/153/154/162 do not acquire extra immunity.

Executing original OnAlert instructions agrees across 2,116 combinations
(23 own poses, 23 opponent poses, both facings, attack absent/present).
The probe observes JumpSeq selection and the extra AnimChar call, rather
than substituting guessed block timing. Original input save/restore also
confirms that consuming Up during GenCtrl does not erase the next saved
sample. Unit tests cover these block gates, continuous Up/release, recovery
from a parried attack, preserved buffered attacks, and late-block contact
followed by a counter against guards and skeletons in both directions.

The C translation in
[dmucli/pop2-port](https://github.com/dmucli/pop2-port/blob/master/src/game/seg06a_characters1.c)
was reviewed as a secondary cross-reference for OnAlert/DoStrike/DoBlock.
No AI probabilities or external runtime were imported; the Macintosh
opcodes remain the reference. This does not establish full enemy-AI parity.

## Terminal Animation Poses During Reload

AnimChar's opcode -23 (`4:2f00-2f14`) rewinds to one word before the cursor
saved at function entry, then continues interpreting until a pose is read.
It is not simply a return of the actor's cached pose. The previous port
appeared correct during uninterrupted playback because that cache already
contained the terminal frame, but a room reload can start with action zero.
In that case, the held combat resource 227 must yield pose 171 again.

SequenceRuntime now follows the original rewind/read path. Its operation
limit also bounds malformed streams that never yield a pose. The selected
sequence history, offsets, callbacks and normal animation cadence remain
separate; the rewind does not replay earlier movement before the held pose.

An independent original AnimChar probe supplies original SEQS bytes and
observes the actual 68k interpreter, rather than substituting SequenceRuntime.
Across 867 checks, the baseline mismatched 861 times with deliberately stale
pose caches; the correction has no mismatches. Inputs cover terminal holds
across the original resource set, actor types 0/2/4, both facings, four cached
poses and an intervening-mode-operation fixture. Resource lookup and Toolbox
handle locking are supplied endpoints. This validates this opcode path, not
every instruction or external callback in every animation.

Asset-free tests cover fresh/stale cached poses, the entry-cursor distinction,
selected sequence history, repeated holds, movement/callback preservation,
peek isolation and malformed-stream limits. A resource-backed skeleton room
reload confirms a visible pose 171 and retained health rather than action
zero. The preceding InitOpps audits intentionally used the shared SEQS
interpreter; they were not independent proof of this instruction. Local
probe: `rendered/sequence_hold_native_probe_v1.py`.

## Silent Animation Movement Signals

AnimCharTap(0), `4:30e0-30f6/314e-315a`, sets the Prince's global movement
signal just like the end of the footstep callback, but without advancing
the footstep counter or playing sound. Other actor types leave that signal
unchanged. The previous interpreter ignored callback zero entirely. Original
SEQS 11 and 227 use this silent callback; standing guard control already
consumes the signal, so suppressing its producer could miss a native turn.

The silent callback now sets the Prince's flag independently of environment.
It preserves pending sound/sequence events and does not re-fire during a
terminal held pose. Ordinary footstep callback one retains its separate
counter, sound and actor behavior. Seven asset-free regressions and a
resource-optional guard integration cover production, peek isolation and
last-unarmed-record consumption without inventing an audible effect.

Independent original comparisons cover 72 direct AnimCharTap calls and 288
actual AnimChar executions at the callback in original SEQS 11/227, varying
actor type 0/2/4, environment, facing, counter and initial signal. The old
interpreter mismatches 60 of these 360 cases; the correction matches all.
Resource lookup and Toolbox handle locking are supplied endpoints; this
does not independently prove every noise producer or the whole AI scheduler.
Local probe: `rendered/silent_callback_native_probe_v1.py`.

## Close Spacing After Retreats And Turns

EnGarde `4:0a82-0c08` distinguishes the selected sequence at A5 `-0x502e`
from the resource AnimChar currently interprets. A continuation into combat
idle 227 does not erase a selected retreat 57/104 or turn 60. Reading only
the current resource allowed the port to restart an advance after retreating,
repeatedly pass the Prince and turn without reaching attack range.

At ready pose 171, the ordinary too-close branch tries the front cell first,
except after retreat 57/104. It otherwise requests retreat if the rear cell
is advancable. After turn 60, `4:0b1e-0c08` instead prefers retreat when the
rear cell is advancable, the facing-relative distance is positive, and any
of these conditions holds:

- The supporting foot's GetDist1 distance is at most 25 pixels.
- The lower strike bound minus opponent distance is at most 17 pixels.
- The second rear cell is advancable.

Otherwise it tries the front cell. Cell queries use the cached anchor column;
GetDist1 uses the FRAM supporting foot. No new collision barrier or blanket
minimum spacing replaces these decisions. The level-5 bridge exceptions
(LEVL +0x218a == 5, not rooftop environment +0x2186 == 5) and non-flat
terrain branches remain outside this subset.

SwordCtrl `6:2206-220e`, `6:22e6` and DoTurn `6:26a8-26b0` allow an ordinary
guard to select turn 60 in animation modes 0/1, not only at pose 171. Modes
2 and above remain protected; the sequence's own opcode changes facing.
Original SwordCtrl execution confirms this across six poses and four modes.

Direct execution of original EnGarde, strike-range, tile-classifier and
GetDist1 opcodes matched the port in 2,200 close-spacing cases: both facings,
five selected sequences, five distances and 44 opening-room positions.
Map reads were supplied from the same LEVL data. Real-resource regressions
previously made 10-12 turns and no attacks over 240 frames; they now make
one turn and return to repeated in-range attacks. Tests also cover the
25/17 boundaries, rear gaps, zero distance and continuation identity.
Forced parry recoil, wounds and their edge falls retain their own rules.

## Leaving Combat And Climbing Under Attack

The screen-5 comparison exposed a host-only immunity: the scene marked the
Prince untargetable throughout falls, holds and climbs. CheckStrikes
`6:58aa-592c` does not exclude those animation modes. Ordinary sword contact
instead needs the same row, absolute Y difference strictly below 15, a living
target and the native actor/mode exclusions. Direct execution of the original
routine marks a wound during jump, fall, hold and climb poses when those
geometric conditions hold. A high enough jump still avoids a low sword.

The scene now retains only its opening-escape exclusion. Guard decisions can
continue while the Prince attempts a grab; a hit clears the interrupted
ledge/queued-climb state before playing the original hurt or death sequence.
Fatal climb sequence 10 still uses CheckStab's existing fatal-sequence rule.
Tests cover scene-level hits during hold/climb, strict -14/-15 height bounds,
and the original opening and edge-fall regressions. This does not imply that
every climb can be hit or that escaping screen 5 must always be impossible.

EnGarde's far branch `4:0c14-0c66` only enters pursuit at distance >= upper
strike bound +18 and with no attack pause. An opposing run (poses 7-14) or
jump (34-43) requests an anticipating strike below 150/186 respectively;
at or beyond those thresholds it waits, without a chance roll or advance.

Ordinary pursuit `4:0fb8-1098` requests retreat when both front cells are
empty. Otherwise a nonzero movement flag, same-facing moving Prince and
Prince mode !=7 can resume SEQS:84. It does not require two flat, traversable
cells or a guard ready pose before selecting that run: AutoCtrl and collision
handle the upcoming obstacle. Other cases consult OpponentClose's advance
table. The level-5 bridge exceptions remain untranslated and do not apply
to level 1. Original EnGarde/range/tile opcodes agree with the port in 2,016
audited far-branch cases across three rooms, four positions, both facings,
seven Prince poses, flags -1/0/1 and attack pauses 0/1. Probability branches
used a supplied zero roll; this is not a full native RNG/update-order trace.

The NPC hurt lock no longer outlives its native animation gate. EnGarde still
evaluates decisions during recovery; SwordCtrl/ordinary input only accepts
them in modes 0/1. Modes >=2 remain protected. This permits responses at the
interruptible end of recovery without waiting for a resource link to 227.

The opening escape's host contact exclusion must not disable NPC decisions.
EnGarde `4:09e6-0a08` waits at distance >=39 for Prince poses 102-117 in
mode 5, not throughout the window escape. Removing the additional targetable
decision gate lets the first guard approach during the airborne poses while
retaining the scene's opening damage protection. Original opcode probes request
advance for poses 43/103/105/106/109/117/118/15 with their opening modes,
and wait for 107/110/116 in mode 5. Scene tests verify early approach, unchanged
escape geometry and health, and the existing three-hit fatal edge fall.

SetupOpp `3:0994-09ce` draws the damage burst for mode 9 at pose 213 as
well as mode 10. HitArtwork now includes that first SEQS:185 tumble pose;
later tumble poses do not repeat the effect. The burst uses the same actor
clipping context as the body, so the native mode-9 roof bypass also applies
to it. A scene regression resolves a fatal sword contact at distance 120
(one pixel below the ordinary upper bound 121) and compares the complete
render against the original burst pixels in front of the roof.

## Remaining Work

This is not a complete translation of every enemy controller. The default
prototype now loads guards and reinforcement points per visited room, and
grounded NPC clearance reads the current room's tiles. Ordinary falls and
horizontal pursuit are implemented for the supported rooftops. Full
unarmed front/behind obstacle branching, different-floor target selection,
native NPC bank/candidate filtering and full alert acquisition still need
recovery. Unarmed AutoCtrl's obstacle/distance branches (`4:0664-06d4`) are
not fully translated. WaitingEngarde's self-nearest obstacle retreat and the
shared live gate/tile classification are now covered by the audit below.
Level-5 bridge helpers `8:02ae/04a2` are identified, not
implemented; they must not be enabled just because the environment is rooftops.
Ordinary same-floor target selection,
flat-rooftop WaitingEngarde spacing and the first room's reinforcement now
have their own implementation and tests, detailed below.

Level-three skeleton activation/collapse is now implemented separately as
described below. Bird controllers, actor type 10 and the final battle still
need their own translations; recovered generators alone do not implement them.

## Obstacle And Waiting-AI Audit

The secondary C translation in
[dmucli/pop2-port](https://github.com/dmucli/pop2-port/blob/master/src/game/seg04a_characters2.c)
(reviewed local revision `8caa5df`) helps locate EnGarde, WaitingEngarde and
the skeleton controller. Its translated function count is not evidence that
either port is behaviorally complete. The original CODE instructions remain
the authority for these corrections.

- IsAdvancableId (`6:5eca-5f54`) rejects a stone gate only while its low-byte
  opening is below 104, not every tile of kind 4. This AI threshold does not
  replace sprite-height-based physical gate collision. Close spacing, safe
  retreats and NPC jump takeoff now use the live tile and modifier. Ordinary
  guards/skeletons avoid walls, space and impassable tiles, with tile 23's
  original exception. The helper also preserves the classifier's actor-type
  7/8/10 exceptions without implementing those actors' controllers.
- Alert acquisition (`2:7026-7038`) downgrades engagement to mode 1 across
  a gate below the same 104 threshold; it no longer ignores closed gates.
  This threshold applies to gates inside the scanned interval; the right
  endpoint exclusion is documented below. It uses the current LevelMap,
  including removed loose floors, rather than
  looking only at the immutable LEVL tile IDs. The existing first-obstruction
  scan order, wall mode 0 and clear-path nearest/waiting modes are retained.
- WaitingEngarde (`4:0e94-0f0e`) has a branch for an NPC that is itself the
  nearest candidate. At Prince distance <51 it checks one cell ahead,
  otherwise two. An impassable tile, empty cell or gate below 104 requests a
  retreat if the rear cell is advancable. A wall alone does not satisfy this
  particular branch. The port previously returned without evaluating it.
  The original ready-pose gate still decides whether that retreat can start;
  this is not a new random retreat or a blanket edge push.

Direct execution of IsAdvancableId matched 1,020 type/tile/modifier cases.
Executing the self-nearest branch of WaitingEngarde matched 672 combinations
of facing, distance, front/rear tile and gate opening, with only cell lookup
and the self-nearest fixture supplied by the harness. Original OnAlert/DoBlock
instructions also matched the existing NPC attack/block dispatch in 12,696
cases across actor types 2/4, both facings, distances 73/74/90, poses 149-171
on both actors, and attack absent/present with block requested. Those dispatch
rules and all twelve probability profiles were left unchanged.

Regressions cover both movement directions, the 103/104 gate boundary,
modifier flag bits, live cavern gate opening/closing, safe/unsafe rear cells,
the 50/51 look-ahead boundary, dynamic floor changes and attack-pose vetoes.
Existing pursuit, multiple-enemy spacing, skeleton lifecycle, damage, audio,
terrain and player-control tests remain the regression scope. This audit
does not certify untranslated special actors, bridge rules or the complete
room-bank lifecycle. The following audit extends ordinary selection and
unarmed control for the playable rooftop/cavern levels.

### Alert Scan Endpoints

CODE:2 `6fc2-6fce` queries the larger supporting column before scanning.
If that cell is a gate (tile 4), the upper endpoint moves one column left,
regardless of gate opening or which actor is on the right. Equal endpoints
then skip the scan altogether, including when that equality results from
the gate adjustment. Interior and left-endpoint gates retain the original
low-byte 104 threshold; no physical collision rule changes.

In cavern environments only, `7084-709c` also permits obstacle tile 24 when
both cached supporting columns are at or to the right of GetBlock's returned,
room-normalized column. An interior tile 24 is still an obstruction. This
exception does not alter IsObstacle or IsAdvancableId for other callers.
Scanning still stops at the first obstruction from left to right, and a
non-primary enemy still receives waiting mode 2 after a clear scan.

`tests/test_enemy_alerts.py` exercises both actor orders, guards and skeletons,
gate openings/flag bits, adjacent/equal endpoints, every tile at a shared
column, cavern-only behavior, first-obstruction ordering, live terrain,
waiting selection, linked-room normalization and existing actor exclusions.
The nine path tests need no original assets and are included in CI; two
additional combat-integration tests run when imported enemy profiles exist.
The path rule lives in `pop2/enemy_alerts.py`, so CI does not import combat's
asset-backed probability tables merely to validate geometry. A clean
temporary project with no assets runs the path tests and skips only the two
explicitly resource-backed integration checks.

Direct execution of the original alert loop, GetBlock and tile classifiers
found 24 mismatches in a 19,200-case baseline matrix and none after these
corrections. It varies four environments, 50 tile kinds, four modifiers,
both actor orders and a same-column placement for a type-4 enemy. Another
480 comparisons cover ordinary guards and skeletons, adjacent endpoints,
linked-room normalized cells and modifier flag bits. Actor load/save and
nearest-candidate selection are supplied endpoints: these comparisons do
not establish full bank scheduling, supporting-foot derivation or special
actor parity. Local probe: `rendered/alert_native_probe_v1.py` (also accepts
`--boundaries`); original resources and Unicorn are research-only inputs.

## Playable-Level Transition Audit

The scope is ordinary guards in level 1 and skeletons in level 3, not future
special opponents. Decisions were compared by executing original Macintosh
CODE resources in a 68k emulator. The harness supplies actor banks, terrain
queries and random results, then observes native input requests, JumpSeq,
alert modes and displacement. It does not substitute the C translation for
the original decisions. The probability profiles above are unchanged.

- GetOppIdxClosestToKid `6:36f2-3918` compares actual absolute Y distances,
  not equal row IDs. A vertical-distance difference greater than 80 prefers
  the vertically closer actor; less than 80 prefers the horizontally closer
  actor. Exactly 80, and horizontal ties, retain bank order. This also refines
  the enemy meter while the Prince is above or below the opponent. Dead and
  wrong-room candidates remain excluded; side-room coordinate views preserve
  the real actor's identity.
- Unarmed running AutoCtrl `4:057c-07d6` tests the live front cell before
  deciding spacing. A jump-capable runner can continue toward its takeoff
  pose when GetDist1 is at least 39, but not through a low gate. Alternate
  rows bypass same-floor spacing, not the passed-Prince, dead-Prince or
  special-13 checks. Braking at pose 212 adds the native forward 12 pixels
  only when the rear cell is not advancable. The movement bucket includes
  pose 44; the separate anticipating-strike bucket still ends at 43.
- Standing AutoCtrl `4:04fc-057a` and GenCtrl `4:4996-49ec` preserve the
  close-behind draw, engagement-3 turn, selected-sheathing veto and dead-target
  checks. AnimCharTap's existing step/noise flag participates in the decision;
  it is consumed by the last unarmed bank record, including across a rebased
  side-room view, and cleared when a skeleton wakes. Player hurt also sets
  it. DoEngarde retains the unsafe-rear forward-eight correction and the
  18-pixel barrier reserve (`6:1ebe-1eda`).
- DoOppRunJump `4:0834-0974` and DoRunJump `6:1c14-1d58` retain gap width,
  capability rolls, alternate rows and takeoff alignment. The takeoff scan
  allows tile 11 even though ordinary IsAdvancableId rejects it. A committed
  takeoff is not cancelled merely because the Prince died.
- Resume-run helper `4:011e-0150` selects 84 for ordinary guards and 102 for
  skeletons, retaining the alert-mode-1 veto. This does not implement the
  special exit-chasing skeleton controller from later levels.
- Skeleton OpponentClose `4:13a4-14b0` rejects all native impassable tiles,
  including 23, and uses supporting columns. Its gate query uses the current
  body rectangle and the shared physical barrier rule, not a fixed 120
  opening. The game supplies the original skeleton artwork; art-free callers
  retain the former conservative clearance. Shadow, timer, special-5 and
  already-living exclusions are preserved.
- Skeleton control `4:165c-170c` resumes ordinary decisions below rising pose
  179, not only after idle 227. The existing mode/pose gates still prevent an
  invented attack during the rising animation. Collapse `4:170e-17a8` aligns
  a right-facing heap when the cached rear cell is space: GetDist1 >= -3 adds
  GetDist1 + 3 pixels. Left-facing and fall-landing collapses do not receive
  this standing correction. Sword death retains its cached supporting column.

Native differential coverage for this pass:

| Routine | Cases | Observed |
| --- | ---: | --- |
| Closest opponent | 5,000 | Selection, height, bank order, left/right filter |
| Running AutoCtrl | 10,000 | Front/rear tiles, 38/39 edge, spacing, alternate floor, brake/X |
| Gap jump | 3,000 | Both facings, 192/196, map queries, rolls, selected sequence/X |
| Standing AutoCtrl + GenCtrl | 18,432 | Noise, alert, distance, row, life, sheathing, rear floor, clearance |
| Skeleton proximity | 3,000 | 50 tile kinds, ten openings, three body poses, both facings |
| Standing collapse | 40 | Facing, rear tile, signed edge distance and X |
| Rising dispatch | 14 | Every pose in the rising chain before idle |

All 39,486 comparisons agree. Another 40 landing-collapse regressions confirm
that the standing correction is not applied to landing sequence 112. Tracked
tests cover the boundary cases and actual scene flows; the native probes use
locally supplied original resources and are not an asset-free CI requirement.

This is stronger evidence for the tested branches, not a claim that all enemy
AI is now proven identical. Complete CutOpponent/CheckSideRoomsForVisibleOpps
bank scheduling, all noise producers, the shared random stream's other game
consumers and every terrain/contact combination still need differential
coverage. In particular, a matching decision given a supplied barrier query
does not prove every upstream geometry query. Later-level special actors and
bridge/exit exceptions remain outside this playable-level audit.

## Skeleton Lifecycle Scheduling

FrameAdv `2:6224-6258` evaluates skeleton proximity (`4:14c6`) before alert
acquisition and the ordinary NPC control/animation pass. The port previously
combined awakening and the dead timer decrement inside Skeleton.control,
and waited for sequence 119 before allowing a response. It now separates
the proximity pass from AutoCtrl:

- A timer of one prevents awakening in that pass, then becomes zero during
  dead AutoCtrl (`4:16e8-1708`). Proximity can succeed on the following pass.
- SkelDoneShaking (`4:1ab0`) consumes a remaining shake and sets inclusive
  Rnd(30)+15. The same frame's dead AutoCtrl decrements that new timer once.
- Proximity calls AnimChar even when an unfinished shake already has selected
  sequence 112. It does not restart that sequence; neither does it require
  the idle continuation 119 before selecting rising sequence 88.
- A successful rising selection advances once during proximity and once in
  the ordinary animation pass. The first completed frame is pose 207, not
  a newly invented hold at 206. Life, sword, alert 3 and the shared attack/noise
  resets are restored in the proximity phase.
- Living skeletons do not decrement their dead recovery timer. Rising's
  midpoint turn is gated by selected sequence 88, so being hurt during rising
  cannot apply another midpoint turn merely because the hurt pose is 182.
- EnGarde `4:09d4-09de` does not sheath a skeleton's sword when the Prince
  dies. It remains armed until copied death counter five triggers collapse;
  the ordinary human guard's sheathing branch is unchanged.

Executing original proximity, shaking/timer, and skeleton AutoCtrl routines
agrees over 72 complete 320-frame scenarios (23,040 snapshots): skills
0/2/3/5, starting timers 0/1/120, sequences 112/119/120, two random seeds,
leaving/re-entering range, excluded player modes, death counter 4/5 and return.
Snapshots compare selected/current sequence, pose, visible life, timer,
remaining shakes, cues and RNG seed. The harness advances the shared recovered
SEQS interpreter when native code requests AnimChar and supplies flat-floor
geometry; ordinary sword AI and floor physics are isolated. This verifies
the lifecycle schedule, not an independent reimplementation of AnimChar or
all physics/room-bank behavior.

ShakeEm `5:2876-28fe` also calls ShakeBones (`4:1898-197a`). A matching row,
pose 206, marker zero and special flag other than five select 112, without
advancing it immediately or resetting the recovery timer/remaining shakes.
Row notifications now come from both player shake requests and loose-floor
impacts, including rows without any loose tiles. Only the final player shake
request in an update is consumed. The new notification queue is transient
and omitted from saves, retaining compatibility with earlier saved records.
Original ShakeBones agrees in 48 marker/pose/row/special/timer combinations.

CheckSideRoomsForVisibleOpps is the routine at `6:2f4e-308e`, called by the
initialization entry at `6:2b7e`; some recovered symbol labels conflate them.
Its ordinary visibility thresholds are native X >585 in the left neighbor
and X <331 in the right neighbor, or port X >378 / <124. Execution agrees
across 1,824 position/side cases, including the copied +/-510 coordinates.
Cavern room entry now initializes such neighboring skeleton records even
without a previous visit. In particular, entering room 17 directly exposes
room 15's X=381 skeleton to the existing side-room simulation. The same actor
is retained on revisits; this is not a duplicate enemy or a spatial teleport.
This extends initial visibility, not the complete CutAllOpponents/UpdateOppInfo
bank scheduler, which remains a separate fidelity audit.

## Level-Three Skeletons

`pop2/skeleton.py` owns the actor-type-4 lifecycle, separately from the shared
sword decisions in `CombatEncounter`. Import now includes `Skeleton.rsrc`;
its original FRAM/AFRM/SHAP/CTBL resources replace the guard artwork for this
environment. Existing installations without this resource request another
disk-image import rather than drawing guard substitutes.

The original LEVL:2002 initial records are retained, not homogenized:

| Native room | Skill | Maximum-life field | Initial marker |
| --- | --- | --- | --- |
| 4 | 0 | 105 | -1 |
| 6 | 0 | 3 | -1 |
| 11 | 3 | 3 | 0 |
| 15 | 2 | 3 | 0 |
| 20 | 5 | 4 | 0 |

SkelAddOpponent (4:198a) keeps the marker--1 bones dormant with no current
life; in particular the raw 105 is not displayed as 105 live health bottles.
The first slot with marker zero starts at 112, then 119. Activation follows
the ordinary level-three branch of 4:14c6/13a4: a living Prince on the same
floor, outside fall/recovery modes, within four columns and with an
unobstructed floor path. SetSkelShakes (4:17fa) supplies three shakes for
skill zero, otherwise `(skill + 1) & 1`; 4:1ab0 supplies inclusive Rnd(30)+15
delays. The final activation uses 88 and restores the record's full life.

The existing side-room coordinate view lets shaking finish and activation
begin while the Prince has already crossed into the adjacent room, provided
the original row/range/path tests still pass. The health meter now selects
the nearest living actor in the current or horizontal side rooms using the
original horizontal/vertical distance comparison described above,
independently of the same-room sword-control target. Dormant bones have no
meter; their restored life appears immediately at the start of rising 88,
even while the skeleton is still offscreen. Climbing onto another floor
does not hide its meter; moving beyond the adjacent rooms still removes it.
This fixes HUD visibility without changing skeleton activation timers,
shakes, combat decisions or physical room ownership.

DrawOppMeter (3:4c08-4c38) draws one full shape 298 per current life point;
lost enemy lives disappear rather than using empty shape 297. The Prince's
separate DrawKidMeter still retains empty bottles and its one-life blink.
Pixel tests cover progressive damage on both sides of a room boundary,
nearest-target selection, hidden opponents, inert bones and a live run past
the Room 15 skeleton into Room 17 before it finishes shaking and rises.

Sword contact must also include the active side-room actors. Previously,
AutoCtrl and drawing projected the Room 15 skeleton into Room 17, but
`resolve_contacts` only visited Room 17's ownership list. A skeleton at
X=473 could repeatedly strike an unarmed Prince waiting at X=40 in Room 17:
the projected distance was 98 (inside its existing 35..99 range), yet no
wound was ever processed. This was unrelated to God Mode.

Contact now visits the same active actors as AutoCtrl and projects the
defender into the attacker's coordinate space before the existing room,
row, height, range and block tests. Hurt and parry changes still apply to
the original actors, not their temporary views. Room ownership, activation
delays, profile probabilities, animations and contact ranges are unchanged.
Tests cover the recorded late-wake sequence through the live scene, both
horizontal boundaries, damage and collapse of the real skeleton, parries
in both directions, Prince priority for simultaneous hits, repeated-contact
suppression, ineligible targets and explicit God Mode protection.

The meter is not a combat-music gate. DrawOppMeter 3:4a9e-4ae6 first tries
GetOppIdxClosestToKid, then falls back to slot zero of the active NPC bank;
it does not require the selected actor to be on the Prince's floor. The
original closest-opponent routine itself accepts ordinary off-floor actors;
the port no longer substitutes a same-row-only search and first-living
fallback for that routine. Pixel tests retain the
three bottles above the Room 15 skeleton while the Prince is on Room 17's
upper ledge, independently of that skeleton's alert mode.

PlayAmbient and TimeForNewAmbient call OppToFight 6:2392-2492, not a sword
reach test. For ordinary guards and skeletons, a living actor with alert
mode greater than zero qualifies, including mode 1 across a gap. The Prince
is excluded in animation modes 3/4, shadow form, special flag 13 and native
dead poses. There is no additional distance or row test in this predicate:
alert acquisition already clears an ordinary enemy's alert on another
floor. The former port expression incorrectly required alert >=2, so a
distant alerted skeleton could not restore combat music after the jump.
Direct execution of the original routine matched 120 combinations of
Prince row, animation mode and NPC alert, including alert 1. Scene tests
cover combat -> upper ledge/exploration -> jump/combat, preserved enemy
health, Peaceful Mode and foreground-song priority. AI decisions and the
existing animation/room-cut rules are unchanged.

Ready skeletons use the recovered per-profile advance/block/reblock/counter/
strike tables, not new aggression constants. GetStrikeRange 6:5c34-5c40
adds three pixels to the Prince's upper strike bound against actor type 4.
Fatal sword hits select the native collapse 120 with cue 61 and the
120-update recovery timer from 4:170e-179e. AutoCtrl 4:169e-16ba also returns
an active skeleton to bones once the Prince's copied death counter reaches
five, rather than leaving it standing over the corpse. Falling deaths use the bones
sequence 112; lava uses 115 and the pool's original sinking-skeleton artwork
with cue 69, not the Prince's drowning sequence. Room revisits use the
record-save/reload rules below, rather than freezing every animation and
recovery timer exactly where the actor was left.

SetupSword 3:0b76-0b98 switches actor-type-4 poses 206-209 to the
environment shape bank, adding 109 to the FRAM shape index. The four piles
of bones therefore use Caverns shapes, not Skeleton SHAP 0-3; those latter
images are upright combat poses. Body drawing and collision bounds share
this selection, including shaking, standby, collapse and the start of rising.
AutoCtrl 4:16c0-16da / 1b9c-1be0 faces the Prince at rising pose 182 and
applies the original 16-pixel anchor adjustment only when facing changes.
The copied Prince death counter can interrupt rising as well as combat.
AnimCharTap 4:30f8-315a accepts skeleton running footsteps without treating
the ordinary sound callback as an unsupported opcode.

Tests exercise actual resources, individual records, inert bones, activation,
all reached sprite frames, strike range, collapse/recovery and persistence.
Scene renders have also been checked in rooms 11, 15 and 20. This is the
level-three subset, not certification of every native NPC-bank update order:
level-four exit-chasing skeletons (4:17aa), complete inactive-room bank
reconstruction and later special opponents remain outside this implementation.

Tests cover direct extraction from the originals, tables/thresholds, native RNG,
conditional roll order, animation gates, range boundaries, anticipating attack,
timers, priority, and the earlier opening/movement/contact/rendering regressions.

## First-Room Reinforcement

The initial 38-byte enemy generators and the 20-byte generation points are
different structures. CODE:6 `GetOppGenPt` addresses the latter at
`0x398e + native_room * 0x44 + index * 20`. Their header is at
`0x3986 + native_room * 0x44`: a count and a room-wide skill index. Both
structures, including raw words, are now exported from the original LEVL
resources. Native entry X comes from the expanded DATA/A5 tables `-0x4b8c`
and `-0x4b84`, not the room-rendering grid's screen X.

Native room 4 has one point, at `0x3a9e`. Its ten signed words are:

```text
0, 1, 1, 0, 5, 5, -1, 1, 1, -127
```

This supplies row 1, column 0, a five-frame initial/repeat countdown,
alternate row 1, one remaining generation, a maximum of one intervening
living NPC, and a packed life field whose low nibble is one. Unlike initial
generator health, a zero nibble does not default to three. The room header
selects skill 0. The guard starts at native X=105 / scene X=-102, facing right.

`pop2/opponent_generation.py` translates the supported rooftop branches:

- `IsActiveOppGenPt`, CODE:6 `0x3daa`: matching current/alternate row,
  nonzero remaining count and Prince more than two columns from the point.
- `IsTimeToGenOpp`, `0x3e0a`: living Prince, ordinary player type, current
  room, fewer than five NPC records (including corpses), every-third-frame
  exclusion, and generation-side living-NPC/wall checks.
- `CheckOppGenPts`, `0x3a0c`: only eligible world frames decrement the
  countdown. At zero, generate, reload and decrement the remaining count.
  Repeated keyboard callbacks cannot run this world-frame clock faster.
- `GenerateOpponent`, `0x3a84`: entry position/facing/skill and packed life.
  This one-life point enters unarmed using `84`, then loops through `208`.
  It is not spawned directly into a sword pose at a guessed onscreen position.

The encounter now owns an ordered NPC list. The corpse, second guard,
animation cursors, explicit selected sequences, life and profiles remain
separate. Hit pause uses the struck NPC's skill; shared encounter timers
decrement before each processed NPC's decision, including a corpse still in
the room. FrameAdv `2:64f2-651e` skips controllers below absolute Y=484 when
their room has no lower link; those fallen actors do not consume timer ticks.
The keyboard callback gate still allows only one NPC pass per world tick.
Contact checks remain NPC-first,
then Prince against each NPC, followed by the native simultaneous-hit rule.

The additional ordinary first-rooftop controller paths are:

- CODE:2 `0x6e7e`: closest living NPC on each side of the Prince can engage
  in alert mode 3; other same-side NPCs use waiting mode 2. Opening poses
  217-225/death disable engagement. The first room and its left neighbor
  have unobstructed floor along the entry path; special gate/modifier and
  non-rooftop terrain exceptions are not implemented by this subset.
- Main CODE:2 `0x6300`-`0x633c`: retain an opposing-facing living target;
  otherwise select the closest living ordinary same-floor target. Death
  changes the active target without deleting the old NPC record.
- AutoCtrl CODE:4 `0x057c`: startup poses finish; odd running poses test
  native distance/spacing before braking with `101`. Same-facing moving
  targets change the distance by +51; opposite-facing ones by -51. The
  >=102 chase exception skips spacing braking but still checks passing.
- Unarmed standing control at `0x04fc`/`0x4996` uses the original turn `80`
  or draw `90`, keeping each animation's own offsets and facing operation.
- WaitingEngarde `0x0c7e` and GenFight `0x0f28`: the supported clear-floor
  spacing uses 102, a 24-pixel margin and a 36-pixel adjustment for nearby
  later NPC records. Advance/retreat still use the native pose gates. Entry
  flags allow the original run restart `84` behind a moving Prince.

Tests exercise the raw first-room point, eligibility boundaries, living-NPC
blocking, corpse limits, cadence, native entry/brake/draw poses, per-NPC
probabilities and damage, target selection, waiting gates, traded-hit priority,
and an input-driven opening followed by two successful combats. New Game restores
the initial NPC and the unconsumed reinforcement point.

## Room Persistence

`CombatEncounter.enter_room` reads that room's initial generators and
reinforcement points on its first visit. Rooms with no initial NPC are valid;
the active target and enemy health display can be absent. Returning to a room
reuses its NPC identities and generation counters. Animation and life follow
the cold/resumed record rules below, rather than always freezing live actors.
The Prince's life and sword state are not reset by a screen change. New Game clears
these encounters and restores the opening.

NPCs use the rooftop physics and transfer between rooms, preserving the
original actor object. Ordinary guards and skeletons both use an explicit
active bank: current-room records first, then visible left/right imports,
up to five records. Unselected neighboring or distant pursuers do not keep
simulating. An imported actor remains selected until the next room entry,
even if it moves away from the original import threshold.
Coordinate views rebase a distant target for AI/rendering without moving its
actual actor. On the Prince's horizontal room cut, CutAllOpponents
`6:44c8-450a` carries ordinary NPC and skeleton running poses 186-201 with
nonzero movement flags and jump poses 202-212 with flag 1. TransferOppInfo
`6:3304/4864` changes ownership and rebases X by 510 without restarting
the animation. The subsequent InitOpps reload consumes its next pose, which
may itself move the actor; this is separate from transfer arithmetic. The carried NPC belongs
to the new target bank even while outside the image, so the Prince can
turn toward it after killing the first screen-5 opponent. Non-carried NPCs
still transfer on their own room cut; the port retains its five-record cap.
Generated offscreen entrants retain ownership of their spawn room until they
enter it or are carried by a subsequent Prince room cut. This lifecycle is
not a complete translation of every special-actor or full-capacity branch.
Player movement is documented in
[COLLISION_RECOVERY.md](COLLISION_RECOVERY.md).

### Ordinary Guard Room Records

`GuardRoomRecord` now implements ordinary type-2 UpdateOppInfo/InitOpps.
For an in-bounds native living actor, saving clears the cursor but retains
the generator's existing resource header. Reloading cursor zero starts
unarmed sequence 77 at full maximum life, except preserved corpse sequence
22. Nonzero cursors resume the saved current resource with saved life/sword
and one AnimChar step. Dead poses remain dead, including the native odd-bank-
slot corpse variant. Same-room refresh does not heal or restart an actor.

Absolute jump Y is saved only for selected sequences 100/186 and loaded only
when the record's current resource is 100. Other reloads start at their
decoded row floor before animation. In-bounds living cursor resets do not
overwrite that header. Non-following out-of-bounds records use the separate
365-pixel Cut normalization; carried records retain the 360-pixel transfer.
Terminal records are removed rather than respawned. Snapshots preserve both
pending reloads and active bank slots; older snapshots default missing fields.

The native ALIVE flag is distinct from HP during reload/control. A zero-HP
non-dead pose initially gets the native living flag, which PlayerCtrl clears
before the next decision. Record saving and armed-following decisions retain
that distinction. Other existing HP-based contact/target paths are not claimed
to reproduce every native sub-frame interaction.

The port retains stable source-room ownership plus rebased actor views rather
than copying/removing native bank memory literally. Complete target selection
and group-count consumers of those views remain separate recovery work; this
active scheduling/record change does not establish their full equivalence.

Independent original InitOpps/AnimChar agrees with the codec in 1,280 reloads
and 510 height-specific reloads. Another 384 SetSpecialOppInfo comparisons
cover metadata writes, and 1,600 original UpdateOppInfo/Cut comparisons cover
integrated storage, including retained live headers and normalized ownership.
The previous 46,080 room-cut decisions still match, plus 512 explicit HP versus
native-ALIVE cases. Resource/graphics lookup, supplied support cells and full-
capacity record loss remain outside these comparisons. Local probes are
`guard_reload_native_probe_v1.py`, `guard_height_native_probe_v1.py` and
`guard_record_native_probe_v1.py` in `rendered/`.

### Room-Cut Decisions And Skeleton Active Banks

The executable's actual per-NPC decision loop starts at CODE:6 `0x4476`,
not the wrapper labeled `CutAllOpponents` at `0x4382`. Its ordinary/type-4
branches now cover running/jumping carry, a supporting cell already inside
the destination, and living armed followers. For the last branch the new
room must contain fewer than five records. Leftward cuts require port X <124;
rightward cuts require X >=385 (native X includes the 207-pixel origin).
Upward/downward cuts require cached row <0 / >=3. Carry preserves life,
sequence, cursor and actor identity. Vertical carry uses the native 360-pixel
cut and recalculates row from absolute height, including mid-fall offsets.

A local Unicorn probe executed that original decision loop for 46,080
combinations of actor type, life, sword, destination occupancy, direction,
position, row, pose, movement flags and destination-cell membership. The
ordinary/skeleton decisions matched. LoadShad supplies a controlled actor;
IsCharInKidRoom is an independent boolean input in this decision test;
UpdateOppInfo/TransferOppInfo are observed rather than executed. This proves
the tested selection branches, not all room serialization or collision logic.
Separate original-code probes check 21,504 supporting-cell/room-link target
queries (IsCharInKidRoom) and 192 TransferOppInfo/Cut coordinate, row, facing,
sequence/cursor, sword and life outputs. The latter observes the emitted
record while substituting its storage endpoints; it executes the original
Cut arithmetic. The position query preserves the actor and follows a horizontal
link before retrying a missing vertical corner link, as the executable does.

On room entry, skeleton-bank selection keeps the room's own actors first,
then eligible left/right imports in that order, up to five slots.
CheckSideRoomsForVisibleOpps `6:2f4e` uses source X >378 on the left and
X <124 on the right; these are distinct from the armed-follow thresholds.
Import selection happens on room entry, not on every frame. Imported actors
keep their slot while moving, even if they leave that initial import region.
Their physical ownership/coordinate views remain separate from bank membership,
so damage still reaches the real actor. Unselected adjacent skeletons and
distant former pursuers no longer consume AI cycles or resurrection timers.
Full snapshots preserve selection/order; older actor records without these
fields remain readable. Current-room actor lists retain existing object identity.

### Skeleton Room Records And Reload

UpdateOppInfo `6:30b0` distinguishes an in-bounds living record from a dead
or transferred actor. The living record restarts with cursor zero on its next
load; dead and carried records retain their current resource and cursor, not
the last explicitly selected sequence. Terminal special states 4/5 and selected
sequences 154/196 remove the room record rather than leaving revivable bones.
Room ownership, actor identity, skill and the existing bank-selection rules
remain separate from this animation record.

InitOpps' actual entry is `6:2b7e`. A zero cursor delegates to
SkelAddOpponent `4:198a`: marker 1 starts armed sequence 63 at full life;
marker 0 in slot zero starts 112; other dormant slots start 119. Dormant
initialization restores the marker timer and skill-dependent shake count.
Marker 1 instead retains its existing timer/shakes. A nonzero cursor restores
saved life/sword and resumes the current SEQS resource. Both paths execute
one AnimChar step during loading, align to the current floor and clear
velocities, stale control flags and old queued events. This load step follows
the already-validated transfer; it is not a change to its coordinate arithmetic.

IsDeadPos then treats skeleton poses 185/206/207 as dead, clearing life and
the resurrection timer. Other poses receive the native living flag even when
their saved health is zero, as can happen partway through a shake. Skeleton
activation/timer scheduling retains that distinction instead of treating HP
alone as the native alive word. A living reload also clears the Prince's
noise flag and shared approach/attack pauses, but not the parry timer.

Two local original-code probes extend the preceding cut tests:

- 240 UpdateOppInfo combinations compare native alive state, HP, armed state,
  cursor saving and terminal-record removal. Current SEQS is compared when
  the cursor is nonzero; a zero-cursor record's unused sequence header is
  not asserted to be identical.
- 9,504 InitOpps/SkelAddOpponent combinations compare marker, skill, slot,
  saved life/sword, timer and reachable cursors across sequences 88, 112,
  119, 120 and 227. Outputs include current/selected SEQS, next pose/cursor,
  life, native alive state, sword, height, X, animation mode, timer and shakes.

These execute the original 68k save/load branches with controlled records.
Record lookup, side-room import and graphics setup are harness endpoints;
AnimChar uses the shared original SEQS interpreter. The load fixture supplies
flat floor, deliberately excluding SkelAddOpponent's ledge-position adjustment.
The existing 72 lifecycle scenarios still match all 23,040 frame snapshots.
Regression tests cover repeated departures, same-room refresh, carried and
reinitialized actors, terminal removal, stale-event clearing, reload pauses,
legacy snapshots and validation of saved room records. Normal player saves
remain checkpoint-based; this does not turn them into exact-state saves.

Remaining differences include special-actor record normalization,
SkelAddOpponent's ledge alignment, invisible-face removal,
all zero-HP/native-alive combat interactions, special actor types and the
remaining bank/target scheduler interactions. The port also retains an actor
when a full destination cannot accept it rather than reproducing the original
unconditional runner transfer's possible record loss. Do not read this scoped
validation as complete lifecycle equivalence.

### Zero-HP Reload Control Order

PlayerCtrl `4:3d64-3d6c` registers death when a negative native ALIVE word
has zero HP, before calling AutoCtrl. This is distinct from InitOpps'
pose-based initialization above: a resumed combat pose can initially have
ALIVE=-1 and HP=0, but must enter dead recovery during its first control
pass. Previously skeleton control ran before that registration and could
leave its recovery timer frozen indefinitely.

The port now registers zero HP before skeleton control, clears its native
living flag, and makes active/rising bookkeeping eligible for later waking
without restarting collapse, emitting a sound or resetting the timer. The
existing wake-before-control order is unchanged: timer one expires in the
control pass and waking is possible on the following frame, not earlier.
Control skipped below the native no-lower-room Y limit remains skipped.

The original PlayerCtrl prefix plus skeleton proximity/AutoCtrl match
128 scenarios and 25,600 frame snapshots, varying skill, timer, shakes,
facing and RNG seed with temporary range/mode interruptions. This uses the
existing cycle harness's shared SEQS decoder, flat floor and supplied RNG;
ordinary combat decisions are excluded. It does not prove every zero-HP
target-selection or alert interaction. Local probe:
`rendered/zero_hp_reload_native_probe_v1.py`. Integration regressions cover
an actual held-pose room-record reload through resurrection, plus phase,
sound and timer preservation at death registration.

### Non-Following Skeleton Record Normalization

UpdateOppInfo `6:3104-3118` tests GetCellI `4:29d8-2a22`, not the stricter
on-screen rectangle used by IsCharInKidRoom. Columns 0..9 in rows -1..2
can stay in the current room record. Row -1 is encoded as `-(column + 1)`.
Other cells return sentinel 30 and execute Cut `6:472a-485c` before storing
the actor in its physical destination and removing its former room record.
No destination means removal, not revivable off-map bones in the old room.

The port now applies this to non-following skeletons on room departure,
including actors imported into the previous active bank from a side room.
Normalization uses the old bank's coordinate view, preserves actor identity,
and retains the current animation cursor when Cut was required. It follows
vertical links before horizontal ones and retries a missing vertical corner
after a horizontal cut. Persistent Cut adds/subtracts **365** from absolute
Y and three from the cached row. Live follower TransferOppInfo/Cut still
uses its distinct **360**-pixel rule and recomputes the row from height.

An optional encoded `cell` in SkeletonRoomRecord preserves the native reload
row. InitOpps `6:2c26-2c3a` truncates signed cell/10 and then decrements for
negative cells, including -10, which reloads at row -2. TransferOppInfo uses
GetRowOffset `4:322a-325a`: -1/-11 for rows -1/-2, not row*10. Old snapshots
without `cell` retain their previous row behavior. Cell validation follows
the existing saved actor row range; new player saves remain checkpoints.

Original-code checks for this extension:

- 8,000 direct Cut inputs compare destination, cached row/column, X and
  absolute Y across generated room-link graphs: 5,614 valid destinations
  and 2,386 missing destinations, with no mismatches.
- 1,200 UpdateOppInfo inputs compare persisted destination, encoded cell,
  X, facing, current sequence/cursor, HP, sword and record removal. Record
  lookup/add/remove endpoints are observed fixtures; Cut/GetCellI execute
  original instructions. A zero-cursor record's unused sequence is not
  compared. This is not a full AddOpp capacity/bank scheduler trace.
- 1,308 InitOpps reloads cover cells -19..89 (the saved actor row domain),
  both facings, markers -1/0/1,
  and zero/nonzero cursors. They compare row and the existing animation,
  life/sword/timer/shake outputs. This retains the earlier shared SEQS
  interpreter and flat-floor fixture; ledge placement remains excluded.
- The earlier IsCharInKidRoom audit still matches all 21,504 room-link/foot
  queries after sharing Cut's traversal. Another 192 live follower transfers
  still match, now also checking the emitted record's row-offset cell.

Local probes are `rendered/opponent_position_native_probe_v1.py`,
`rendered/skeleton_normalization_native_probe_v1.py` and
`rendered/skeleton_cell_reload_native_probe_v1.py --extended`. Asset-free CI tests cover
the Cut boundaries, negative cell encodings and snapshot compatibility.
Resource-backed regressions cover real room ownership/re-entry, preserved
cursor, missing links, vertical height, repeated side imports, existing live
carry and full-bank retention. Bank-capacity fixtures now use actual in-room
anchors rather than their former default X=0 (whose supporting cell was
outside the room). The approved port safeguard against a full destination
discarding an incoming actor remains unchanged.

### Progress Accounting

The local `dmucli/pop2-port` reference documents 2,161 translated functions
out of 2,165 CODE 1-23 functions. Its four untranslated THINK C helpers are
three unused switch-table dispatchers and a return-path helper superseded by
the translated caller. That inventory includes compiler/runtime and Mohawk
functions, not just gameplay rules. Its function-for-function C architecture
differs from this higher-level Python implementation.

Consequently neither that denominator nor this project's named-routine marker
count is a completion percentage. A useful progress ledger must map original
rules/routines to their implementation, applicable levels/actors, regression
tests and native-comparison coverage, with explicit partial and not-applicable
states. Function size and significance also differ greatly. The validation
sections here record evidence and remaining scope instead of inventing a
numerical fidelity score.

IsTimeToGenOpp `6:3e56-3e68` divides the unsigned 16-bit frame counter
by three, swaps its quotient/remainder halves, then tests the entire long
word. This is not a modulo-three throttle: only counter zero fails. The
previous port skipped every third cycle and delayed incoming guards.
Executing the original instructions for all 65,536 counter values confirms
the corrected gate. Generator countdowns, probabilities and movement
speeds are unchanged. An input-driven scene regression runs/jumps through
screen 4, kills screen 5's initial guard and verifies the automatic turn
toward the same carried pursuer on the next animation cycle.

## Rooftop Pursuit And Jumping

- Preserve initial generator +0x14, not just reinforcement flags.
- CODE:4 `0x0fb8`-`0x1098` can resume run sequence 84 behind a same-facing
  moving Prince, subject to the two-empty-cell veto and a nonzero movement
  flag. See the far-branch conditions above; this is not a generic ready-pose
  transition whenever the Prince is outside the ordinary strike range.
- AutoCtrl `0x07dc`-`0x0974` checks jump capability at poses 192/196,
  the third tile ahead, the first empty tile and gap width. Gaps under four
  tiles are eligible; a four-tile gap uses the original capability-based
  random roll. A different permitted generator row also enables the wider
  gap branch at `0x093a`-`0x0948`. Special level/room exceptions remain missing.
- DoRunJump CODE:6 `0x1c14`-`0x1d58` uses an anchor look-ahead of 13,
  up to two clear tiles, and a 75-pixel NPC takeoff reserve. This is not the
  supporting foot used for the initial gap scan. Select SEQS:100, not 110:
  100 contains the ordinary running-jump poses 202-212; 110 belongs to the
  separate DoOppRunJump entry point and is not used by this AutoCtrl branch.
- AutoCtrl also checks pose 212 before re-entering the running loop.
- StartFall uses ordinary NPC sequences 82/83 for armed falls and 186 for
  failed sequence-100 jumps. A surviving 186 fall lands with 187; other
  ordinary NPC soft landings use 63 and arm the actor. HitFloor `0x0348`-
  `0x0444` makes velocity >=50 fatal for ordinary NPCs, unlike the Prince's
  survivable 50-62 interval.

The actual Guard FRAM/AFRM/SHAP assets supply support feet and body bounds.
No replacement jump animation or fixed-room X clamp is used. Shared body
wall sweeps remain a supported subset of native collision-buffer behavior.

## Alternate-Floor Rooftop Reinforcement

Initial generator word +0x20 and reinforcement `alternate_row` are retained
on the actual NPC. AutoCtrl `0x06da`-`0x06e2` skips same-floor distance braking
when an eligible alternate-floor target is below the pursuer, without skipping
the jump-pose checks. Native room 10 has a generation point at row 0, column
0, alternate row 1, wait/repeat 10, one remaining guard, flags 1 and packed
life word 0xff81. That upper NPC now runs, jumps with 100, falls with 186,
lands on row 1 and engages the Prince. It is not a hand-placed extra enemy.

## Unarmed Body Contact

FrameAdv, CODE:2 `0x6c64`-`0x6daa`, provides the ordinary opposing-guard
collision rule. An engaged living grounded NPC (alert >=2, animation state
<2), an unarmed available Prince, opposing facing and vertical velocity <59
are required. Absolute facing-relative distance <=24 triggers contact;
running jump sequence 4 also triggers it at distance <63. Scripted NPC jump
110 is excluded. The original pose selects bump 46 for actions 24/25,
40-42 and 102-106, otherwise 47, with its native +10/-10 facing offset.
The scene clears a pending run/jump after this interruption. No generic
invisible guard rectangle or substitute bump animation is introduced.
The full special-actor exclusion branches are not part of this ordinary
rooftop subset.

## Ordinary Rooftop Tumble Death (r12)

DoOppTumbleSeq, CODE:4 `0x0154`-`0x02cc`, is called by fatal-hit handling at
CODE:6 `0x56ba`. It chooses 185 with a -12 pre-offset instead of ordinary
85/-17. Rooftop rooms 19/16 or an empty tile behind a left-facing guard
force the tumble without a probability/facing veto. Other cases require any
generation point in the current room with packed life flag 0x80; this is
word +0x12, not the generator's movement flags at +0x0c. The room's NPC bank
then supplies the count of registered deaths: helper 4:03f4 scans the
death-state word at bank +0x1c, not life or slot occupancy. The actor newly
stabbed in this pass is not registered until 4:3d64-3d6c runs next frame.
Rnd(3) returns 0..3 inclusive; a roll <= that count selects a candidate.
If the roll fails and the count is nonzero, another actor at the same
supporting-foot column/row with dead pose 185 or 228 also selects it.
Same-facing kills and specific tiles under/behind reject the tumble. This
flag is separate from the NPC's jump capability. These ordinary selection
branches are now implemented, with tests for roll/count boundaries, the
packed flag, same-facing kills, tile vetoes and overlapping corpse poses.

185's callback 30 is a native sound event; its poses are 213-218 and its
continuation is 207. FrameAdv 2:65ee-6664 bypasses ordinary floors, barriers
and cuts in mode 9, derives the row from absolute Y and lets Move add gravity
and cap at Y=730. The prototype now uses that branch instead of inventing a
lower-floor landing or erasing a body. Ordinary mode-9 ClipChar bypass is
also translated; the special room 16/19 rendering cap is still not covered.

GetOppDeadSeq 4:0074-010a / FrameAdv 2:6544-654c chooses flat corpse sequence
195 (pose 228) for odd ordinary-NPC slot IDs. The helper computes slot ID
modulo two, not Rnd. Even slots retain pose 185. Slot order is the room's
ordered NPC list, including reinforcements/transferred actors. Special actor
corpse variants and the complete native bank/lifecycle implementation remain
outside this ordinary supported-room subset.

`Collide` (4:5740-5746) returns immediately for dead actors, before applying
barrier displacement or selecting a bump sequence. This gate applies to the
Prince and guards. Without it, a guard dying beside a wall could switch from
SEQS:85/213 into SEQS:65 and then combat idle 227, standing indefinitely with
zero life. Dead actors now finish their death sequence; living actors still
use the normal wall bump and recovery. Floor contact and tumble physics are
unchanged.

## Hurt Recovery And Facing

SwordCtrl (6:2258-22ea) can turn toward a live opponent at a ready pose
(animation state 0/1), including the end of an unfinished hurt sequence. It
does not wait for the port's recovery lock to expire. DoTurn's existing edge
clearance still applies. Turns require an engaged or waiting opponent (alert
mode >=2); gap/wall modes 1/0 do not turn. Uninterruptible animation states remain protected.

EnGarde (2:6f76-6f9c) scans the actors' supporting columns rather than their
sprite anchors. A hurt pose can move its anchor past the roof edge while its
supporting foot remains on the roof. Using the anchor here prematurely lost
the combat target and prevented the Prince from turning after the first hit.
The opening regression checks three stabs through death for fixed guard seeds,
without input. Different attack timings can put the supporting foot outside
the roof sooner; neither health nor the hit count overrides floor contact.

## Player Parry Recoil

GenCtrl `6:24da-2506` handles successful block pose 161. Without attack input,
it selects retreat SEQS:57 and applies `AddCharX(-9)` for the Prince. Ordinary
NPCs select the same retreat but do not receive that extra displacement.
SEQS:57 supplies the remaining movement and poses. The forced retreat does
not use the voluntary retreat's floor-clearance veto: a block at the edge
can push the Prince off the roof without taking health.

A buffered counter has priority and selects SEQS:66 from pose 150/161. Its
selection must not be overwritten by the recoil before AnimChar displays the
first counter pose. Held block input does not cancel the forced retreat.
Blocking without sword contact does not trigger it. Direct execution of the
original GenCtrl verifies SEQS:57 and the nine-pixel player offset in both
directions. Scene tests cover contact, recoil, edge fall, supported retreat
and counter priority through the actual animation tick.

## Fatal Hits At Edges

CheckStab (6:5428-54b2) chooses SEQS:81 rather than a flat corpse if the
struck actor's supporting cell is empty, or the cell behind it is empty and
GetDist1 is at least six pixels. Types 6, 7, 8 and 11 bypass this branch.
The offset is GetDist1 - 12, with another -51 when the queried cell differs
from the cached supporting column. The row advances while absolute Y is
preserved. Ordinary hurt/flat-death branches instead set the actor to its
current floor and clear vertical velocity.

For an opposing-facing ordinary guard, CheckStab first applies the hit's
-10 offset (6:52ec-5302), even when fatal. The subsequent edge test retains
the pre-displacement supporting column. Omitting that order changes both
the death position and the choice between an edge fall and rooftop tumble.
Direct execution of the original CheckStab verifies the Prince's initial
roof fall and the guard's existing tumble/flat-death cases.

Shift catches require a living Prince, as Catch (4:37ca) requires a negative
native alive word. The port also retains hit provenance throughout the shared
fall loop: a fall entered from hurt sequences 74/94 cannot be caught, matching
the recorded knockback behavior. A new voluntary retreat retains the catch;
this does not prevent either fighter from being knocked off an edge.
