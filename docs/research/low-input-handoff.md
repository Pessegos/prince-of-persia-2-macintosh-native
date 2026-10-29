# Crouch, rise and prone directional-bank runtime

The sixth input migration carries the existing `DirectionalInput` through
ordinary lowering26/50, low hold117, low step79, rise49, soft landing17 and
prone lie/idle/crawl/stand125/121/122/123/124. The old directional command
slot no longer owns those admitted contexts. Armed controls, other special
contexts and the existing SEQS46 wall/climb recovery remain separate.

## Reused original evidence

This implements the input effects already recovered in
[low/prone consumption](low-input-consumption.md):76,357 original calls/steps,
including actual JumpSeq selection and100 persistent saved-player steps.
That native matrix was not repeated for this migration. Its input, pose,
terrain, resource and scheduling exclusions remain unchanged.

Relevant CODE6 ranges are0576-059c (protected clears),07ee-0998 (prone),
099a-0b58 (low controller) and1068-10e2 (ordinary crouch entry).
`pop2/mac_input.py:low_input_request` performs facing-relative input selection
at supplied geometry boundaries:

- Crouch entry clears directions and consumes Down, preserving the modifier.
- At109, released/inactive Down allows rise before Forward unless clearance
  vetoes it. Active Down plus fresh Forward consumes Forward after a clear,
  choosing79 or125; otherwise Down is consumed after clearing other directions.
  A newly tapped Up cannot wait behind that Down and jump after rising.
- Protected modes4/5/9 and selected27/110 clear directions, preserving Shift/
  Ctrl. Ordinary rise110-116 is protected;117-119 is not. The mode comes from
  the actual resource, not a generic rule based on a similar-looking pose.
- Prone non-idle246-261 clears directions. At251, eligible Up stands before
  fresh Forward/Backward; consumed horizontal holds alone do not start a crawl.
  Outside the low cells,124 is selected before crawl, and its selected ID
  prevents another crawl in the same call.262/263 retain the bank.
- Successful low pickup clears directions and consumes the modifier before
  the existing item action takes ownership. Carpet/reveal/pickup services
  continue to run in their established scene phases.

The actual26/50 resources use mode1 on107/108;17 uses mode5 there. The earlier
persistent native probe supplied protected lowering modes explicitly and did
not prove animation progression. Runtime now respects the actual resource
mode: a released direction can survive ordinary lowering, while protected
landing/rise input clears. Eight lower/rise mode observations are checked
against the existing independent GenCtrl routing model.

## One bank, one poll per simulation tick

`pop2/low_controls.py` adapts the existing terrain/action methods. Physical
callbacks update independent latches. The existing immediate horizontal
low-step callback remains; prone dispatch and protected resets occur in the
simulation. Scripted directional requests are imported once, then removed
from `pending_action`. The old low-step classifier, crouch pending-slot
consumer and raw-held prone dispatcher are removed from the scene.

The scene can ask for controls both before preparing the next sequence and
inside that preparation. Low control must run once per simulation tick:
otherwise clearing directions on the first call and resampling the held
arrow on the second call rearms Forward and restarts lie-down125 at109
forever. A per-tick poll marker prevents this; it carries no command and is
reset at the world-phase boundary. The regression verifies both repeated
calls within a tick and held input becoming eligible on the next tick.

## Preserved host policies and boundaries

- Held low steps repeat complete animations at109 without an extra stationary
  rearming frame. The established rapid repeated-tap filter remains scoped
  to the same low step; it does not expire other pending directions.
  Rearming applies only at hold117, never125's first109: approaching a real
  tunnel through repeated low steps must continue into prone movement.
- Releasing the Down inherited from an already-started low step can cancel
  that hold before109. A genuinely new Down tap during the step still stays
  pending. This existing fluid-release tolerance is explicit, rather than
  changing the native selector's ordinary consumption rule.
- Shift/Down still starts the existing rooftop hang in either key order.
- SEQS46 recovery links through49 with selected source46, often without a
  live ledge flag. It retains its existing owner and vertical wall-climb
  tolerance. Its old protected horizontal/crawl clear is retained only for
  that source. Ordinary49 is owned by the bank and clears released Up too.
  Real cavern wall-recovery tests keep their previous poses, pause behavior,
  climb success and final positions.
- Menu/focus/restart clears discard the bank and low repeat/poll markers.
  Existing pause and upside-down physical mapping are reused.

Existing low-cell alignment, gate-rise clearance and prone stand-clearance
geometry are reused, not newly certified. The original218f/S05:5f1a scythe
rise predicate remains separate geometry work; this stage does not claim its
full runtime parity. Native signed-coordinate edge cases, pickup/carpet action
bodies, special resources, full FrameAdv order and OS sampling are excluded.
No original assets, artwork, save format or release artifact are changed.

## Regression evidence

Before the migration, three new scene tests rejected the old runtime in ten
subcases: released Up replayed after protected rise, low-step Up/Down taps
used an executable last-command slot, and a released prone-idle horizontal
tap was lost. The final tests keep those cases plus both facings, the116/117
reset boundary, prone body hold/release, duplicate polling and source46.

The production selector is compared with the separate original-backed
`reference_low_input` model in25,920 bounded cases, plus eight lower/rise
observations against `reference_input_routes`. This is an input-only
comparison, not a synchronized native/port gameplay recording. Those two
tests run in asset-free GitHub CI. No new native-call count is claimed.

Older crouch/landing tests now inspect the bank instead of the retired slot.
Their animation/position expectations are retained. One old test deliberately
expected queued Jump/Backward to survive active Down at109; that expectation
now follows the recovered0b2e clear and cannot replay after rising. Unowned
sword requests retain their separate path.

Focused input/animation/wall/tunnel validation passed224 tests in11.102s.
The first broader234-test run exposed the duplicate-poll lie-down loop and
an accidentally adopted source46 recovery; both were fixed without weakening
the real tunnel/wall expectations. A preliminary full run was interrupted
during review to preserve source46's remaining protected-direction clear;
it is not counted as completed validation. The next full run passed3259 tests
in554.558s with ten skips. A subsequent targeted check of approaching the
level6 room17 tunnel through multiple low steps exposed held-step rearming
on125's first109. The repeat policy is now restricted to117, and a real-room
regression verifies79 ->125 ->122 without the restart loop. All225 focused
tests then passed in10.620s. Final discovery is recorded below when complete;
the earlier green full run is not presented as validation of this last fix.

Final shared-desktop discovery on the release candidate:3260 tests in545.950s,
**OK**, with ten explicit exclusive-desktop skips. No runtime changes followed
this run. Ruff F/E9, dependency, recovery-catalog and whitespace checks pass;
the asset-free CI subset passes locally. All scenes use hidden isolated
widgets/temporary user data; no live game/emulator, physical focus/input or
real user saves/settings were operated. No reimport is needed.

Next: inventory and migrate the remaining armed input gates, keeping the
existing attack-repeat policies explicit. SEQS46/fall and special input
contexts still need their own boundaries; this is not whole-game queue parity.
