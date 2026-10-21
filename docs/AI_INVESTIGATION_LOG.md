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

Base: `62589be`, clean `main`, latest GitHub Tests successful. The previous
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
regression tests pass; the old method produces 18 assertion failures in
those tests. Broader AI/combat/pursuit/generation/skeleton/harbor coverage:
318 tests pass, one optional source-validation test skips. Ruff passes.

Final comparison: all 19,200 cases match after the fix. Another 480 original
comparisons cover type-2/type-4 actors, adjacent and linked-room endpoints,
walls, tile 24 and gates with low-byte/flag combinations. Reports remain in
`rendered/alert-native-probe-v1.json` and the baseline file above. New tests
are included in CI. No full-AI parity claim.

Next independent investigation is the
previously excluded SkelAddOpponent ledge alignment (`4:19f0-1a54`). Review
its input-frame provenance before integrating: InitOpps has not loaded the
new pose when it invokes this adjustment. Do not blindly reuse the visible
heap's supporting foot and assume that matches the original call site.
