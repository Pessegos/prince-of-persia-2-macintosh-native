# Gate passage must survive a short tap and stopping pose

The user's follow-up confirms that the previous room-3 fix was incomplete:
holding Right passes the gate, but a short tap still throws the Prince behind
it. The ordinary run's SEQS 1 exception did not cover the subsequent SEQS 13
stop. Adding another animation exception would leave the same shared fault
available to other pose changes.

## Reproduction

In level 12, native room 3 (port room 2), supply supported idle X445, row 1,
facing right and gate cell 18 open at foreground 184. Press Right for one
update and release it. The real controller completes the minimum run, then
stops. It reaches X492/pose 53 and X493/pose 54 as the adjacent closing plate
starts the gate. On the next update the old overlap recovery replaces the
intended X520/pose 55 with X446/bump 47. This is the same wrong front response
from the trailing body, occurring during the stop instead of the held run.

With passage history, pose 55 stays at X520 and the real camera cuts to room
11 at X10. The stop finishes there at X15/idle pose 15, with the gate closed
behind him. All six release timings 1–6 complete that passage and can resume
running afterward. The existing continuous-run, vertical-jump and genie-route
regressions remain in force; their expectations were not weakened.

## Correction and lifecycle

`TerrainMotion.gate_passages` records resolved `(room, cell)` identities for
ordinary temple/ruins gates that admitted the current body while physically
passable. It remains valid while the current or preceding body overlaps the
gate. A pose/sequence change or gate closure cannot manufacture a fresh front
crossing for that admitted passage. The exact edge-crossing rule already used
by the native-backed run/jump cases applies to every subsequent unarmed pose.
The earlier bounded run/jump handling is retained too.

This distinguishes a real open-to-closed passage from a cold overlap with an
already closed gate. Cold recovery still handles the genie route's catch in
room 24, without an exception for SEQS 43. Genuine front crossings of a closed
gate still block. Wall, armed/NPC, cave contact/crushing, throne-grille and
approved visual policies are unchanged.

The history is per physical actor, not a frame/control cache. It updates after
the current body/fall movement and before wall correction; protected
hang/climb updates maintain it too. A clear body, different floor/gate,
replacement actor, arming, death or sinking drops admission. Stable resolved
cell identities survive the horizontal camera rebase, including the gate in
the left neighbor. The throne exception uses the resolved gate room.

The new field is saved with the motion, so a mid-passage snapshot can resume
without losing admission. It is optional when loading earlier saves, with an
empty default. The existing positional motion fields retain their order.
Save round-trip and legacy-field removal are tested. An older snapshot does
not invent evidence that a cold, already closed overlap was previously open.

This history is a deliberate port safeguard around the port's retained cold
overlap recovery. It is not claimed as a byte-for-byte reconstruction of the
native collision banks or complete gate-contact controller.

## Original evidence

The original CheckBarr `CODE 4:4e34`, specifically `4f7c-4fb4`, compares side
bits in current/previous collision banks before CheckCollide1 `4:54da` chooses
a side response. An already crossed edge is not a new unarmed front contact.
The earlier rule was not specific to continuous running.

`tools.probe_gate_stop_contact` runs original LoadFrame `4:2a72`, SetupSword
`3:0ac8`, GetCharEdges `4:5cbc`, warm CheckBarr and CheckCollide1 through
standing, running and every stopping pose. Both facings produce 32 original
snapshots and 30 port comparisons, with zero side-contact differences.
Actual Kid FRAM/AFRM/SHAP headers and the original room-3 gate/header are used;
the working native actor carries the proper selected sequence and mode.

Poses/X/foreground and the mirrored facing are supplied. The trace retains
room-3 X coordinates after the port's camera cut, intentionally excluding
native room-cut execution. SHAP size lookup and SectRect are supplied; Collide
is a recorded no-op. Native pressure/input controllers, physical support,
CheckGateForKid responses, full FrameAdv and pixels are excluded. The existing
held-run probe still passes 108 native snapshots/96 comparisons and its two
genuine front-crossing controls. Input hashes are recorded locally.

## Other gate locations

The same tool inventories actual ordinary gate anchors across levels 1–14:
22 cavern, 12 ruins and 41 temple gates. The special throne grille is excluded,
as are the harbor/desert custom exit mechanisms. At each of the 75 ordinary
anchors, both-facing run/stop snapshots give 2,250 port comparisons without
wrong gate-side displacement.

This is an explicitly isolated component audit: other tiles are supplied as
floor and horizontal self-links remove unrelated room-edge barriers. It is
not 75 naturally reachable input routes or native proof at every anchor.
Restoring the previous tile correction produces 212 bad comparisons across
all 53 ordinary ruins/temple anchors in that fixture; the cavern cases already
use the edge-crossing rule. This demonstrates that the cause was shared, not
a coordinate-specific room-3 defect.

## Verification and remaining scope

`tests.test_gate_passage_history` covers both facings/environments, arbitrary
pose changes after admission, repeated closure including phase zero, cold
overlaps, physical clearance versus descent exemptions, lifecycle invalidation,
linked-room identity and throne exclusion, then six actual short-tap replays.
The previous correction fails all six tap subcases without errors.
`tests.test_save_game` checks stored history and the legacy empty default.
An additional hidden real-input sweep covers 216 combinations of twelve
supported starting positions, release timings 1–6 and gate openings
184/200/255. All 216 close the gate without the large backward displacement.
This sweep uses temporary user data and supplied starts, not full-level routes.

The full shared-desktop module suite runs in isolated interpreters to bound
artwork caches; audio/frame-cost tests run serially. The final run completes
251 modules / 4,180 cases with ten explicit skips and zero failures in
445.27 seconds. The skips are nine exclusive-desktop cases and the unavailable
native enemy profile. All 83 focused history/passage/jump/route/save tests
pass without skips; dependency, Ruff (`F,E9`), recovery-catalogue and whitespace
checks pass. No live game window, exclusive desktop, user data or original
resources are modified.

```powershell
$env:POP2_SHARED_DESKTOP = '1'
.venv\Scripts\python.exe -m unittest -q tests.test_gate_passage_history tests.test_temple_gate_passage tests.test_vertical_jump_walls tests.test_temple_routes tests.test_save_game
.venv\Scripts\python.exe -m tools.probe_gate_stop_contact --source ..\PoP2-Mac-Code-Recovery --output rendered\gate-tap\native-stop.json
```

Native full gate-contact/bank initialization across arbitrary room/grip
transitions, natural routes through every gate and armed/NPC interactions
remain outside this bounded repair. The audit does not certify every gate
interaction in the game.
