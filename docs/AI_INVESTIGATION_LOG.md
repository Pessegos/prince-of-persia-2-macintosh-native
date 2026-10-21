# Enemy AI Investigation Log

This is the resumable work log for the autonomous recovery pass started on
2026-10-21. The Macintosh executable remains the authority. Existing native
comparisons establish their stated branch subsets, not whole-game parity.

## Working Contract

- Prioritize enemy AI in the playable levels before later-level rules.
- Execute original instructions where feasible; distinguish supplied fixture
  inputs from independently verified upstream geometry and scheduling.
- Implement confirmed differences with focused regressions, then run the
  affected broader suites. Commit small coherent changes and check GitHub CI.
- Preserve approved port improvements, especially the dock-guard stand-down
  after the Prince catches the boat. Do not change probabilities by taste.
- Record uncertainty rather than inventing behavior. If one path is blocked,
  investigate another independent branch while meaningful work remains.

## Starting State

Base: `97189fd`, clean `main`; this includes the user's README status update
after `62589be`. Latest GitHub Tests successful. The previous
ledge-release fix is committed and approved in game.

The existing implementation already includes ordinary guard decisions,
probability tables, pursuit, sword contact, skeleton lifecycle, side-room
contacts, and scoped skeleton bank/save/load recovery. See
[AI_RECOVERY.md](AI_RECOVERY.md) for evidence and its limitations.

Important open fronts, not an exhaustive count:

1. Alert acquisition (`2:6e7e-7114`): audit the entire ordinary path, including
   endpoint gates, cavern tile-24 exception, scan ordering and linked cells.
2. Skeleton initialization: `SkelAddOpponent` ledge-position adjustment;
   complete out-of-bounds room-record normalization and invisible facing.
3. Ordinary rooftop active-bank scheduling and other noise producers.
4. Level-5 bridge exceptions and later special actor controllers. Level 4+
   are follow-on work, not evidence that the current AI is already complete.

## Alert Acquisition: Confirmed Differences

The direct native baseline found 24 mismatches in 19,200 cases. All were
the two statically identified omissions: `2:6fc2-6fce` excludes a gate at
the larger supporting column, and `2:7084-709c` permits cavern tile 24 when
both actors are at or to the right of its normalized column. This is an
endpoint exception, not permission to pursue through an interior obstacle.

The local probe is `rendered/alert_native_probe_v1.py`; the baseline report
is `rendered/alert-native-baseline-v1.json`. It executes the original alert
loop, GetBlock and tile classifiers. Actor load/save endpoints and nearest
candidate results are supplied fixtures, so this does not validate bank
scheduling or upstream supporting-foot geometry. The matrix uses actor type
4, four environments, 50 tile kinds, four modifiers and both actor orders
plus a same-column case.

The shared alert method now implements those two limits. Ten asset-free
regression tests initially passed locally; the old method produced 18
assertion failures in that first test version. Broader
AI/combat/pursuit/generation/skeleton/harbor coverage:
318 tests pass, one optional source-validation test skips. Ruff passes.

Final comparison: all 19,200 cases match after the fix. Another 480 original
comparisons cover type-2/type-4 actors, adjacent and linked-room endpoints,
walls, tile 24 and gates with low-byte/flag combinations. Reports remain in
`rendered/alert-native-probe-v1.json` and the baseline file above. New tests
are included in CI. No full-AI parity claim.

Commit `e9a29a1` contains this rule. Its first GitHub run exposed an asset
dependency in the test module: importing combat loads extracted probability
profiles. Follow-up extracts the path rule into `pop2/enemy_alerts.py` and
splits nine genuinely asset-free path tests from two optional integration
tests. The whole module also passes in an isolated temporary project without
an assets directory (only the two integration checks skip). The 480 native
endpoint comparisons still match after extraction.

## Skeleton Edge Initialization: Input-Provenance Audit

The next branch, SkelAddOpponent `4:19f0-1a54`, demonstrably uses the caller's
cached FRAM supporting-foot fields, not a newly decoded heap pose. InitOpps
sets anchor/row/facing before the call but does not call LoadFrame there.
The appearance-loading path changes resource handles, not these cached
FRAM values. This dependency matters; do not silently choose a heap frame.

Local `rendered/skeleton_edge_native_probe_v1.py` extends the previous
InitOpps harness by executing its real front/rear tile queries and alignment
arithmetic. With the same dormant record at X=180 and an empty left cell,
four supplied prior-FRAM pairs produce X=230/214/198/223 when facing left,
or X=229/194/210/185 when facing right. Marker-1 living initialization stays
at X=180 for all eight controls. Results are in
`rendered/skeleton-edge-native-v1.json` (16 cases).

No alignment change is justified yet. The previous InitOpps probe explicitly
excluded this geometry; reusing the visible heap's foot would invent an
upstream input. Next: trace the last native LoadFrame before room entry and
establish how this cache is initialized for actual supported room records.
If this requires unavailable full-runtime state, keep the limitation explicit
and advance another independent AI branch rather than hardcoding positions.
