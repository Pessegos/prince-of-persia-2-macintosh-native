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
minimum spacing replaces these decisions. The existing special rooftop-room
exceptions and non-flat terrain branches remain outside this subset.

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

## Remaining Work

This is not a complete translation of every enemy controller. The default
prototype now loads guards and reinforcement points per visited room, and
grounded NPC clearance reads the current room's tiles. Full front/behind tile
checks, gates, NPC falling, cross-room pursuit, different-floor target
selection, full alert acquisition and special roof-room branches need the
corresponding collision/map work. Ordinary same-floor target selection,
flat-rooftop WaitingEngarde spacing and the first room's reinforcement now
have their own implementation and tests, detailed below.

Skeleton awakening/resurrection, bird controllers, actor type 10 and the final
battle must be translated separately from their own original code. Their
profiles/generators are recovered now, but those characters are not yet
playable in this port. Do not route them through the ordinary guard controller.

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
reuses its NPC objects, corpse poses, remaining life and generation counters.
The Prince's life and sword state are not reset by a screen change. New Game clears
these encounters and restores the opening.

NPCs now use the rooftop physics and transfer between visited horizontal
rooms, preserving the original actor object. Adjacent visited rooms and
already engaged pursuers keep simulating; other rooms remain inactive.
Coordinate views rebase a distant target for AI/rendering without moving its
actual actor. Transfer is performed only when the guard reaches a room cut.
Generated offscreen entrants retain ownership of their spawn room until they
enter it. This lifecycle is not a complete translation of all `CutOpponent`,
`CheckSideRoomsForVisibleOpps` and special-actor branches. Player movement is documented in
[COLLISION_RECOVERY.md](COLLISION_RECOVERY.md).

## Rooftop Pursuit And Jumping

- Preserve initial generator +0x14, not just reinforcement flags.
- CODE:4 `0x0fb8`-`0x1056` can resume run sequence 84 behind a same-facing
  moving Prince, subject to traversable look-ahead tiles and capability.
  The prototype performs that transition at the supported guard poses.
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
