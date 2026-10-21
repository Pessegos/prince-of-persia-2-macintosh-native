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

Follow-up `9fe69cb` passes GitHub Tests (run 39550717111). Final local scope
was 319 tests, one optional skip. The full 19,200-case matrix was also
repeated after extraction and still has zero mismatches.

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

Initial-record inventory: all eight level-three skeletons have a nonempty
left anchor cell, so this initialization branch is inactive for those fixed
spawns. Level-four room 14 has a dormant record whose left cell is space.
This does not establish what happens after a moved skeleton is reloaded.

## WaitingEngarde Group Audit

`rendered/waiting_group_native_probe_v1.py` executes the full WaitingEngarde
decision routine and GenFight with actual GetBlock/IsAdvancableId. All 6,000
seeded synthetic group cases matched; no behavioral edit was warranted.
Cases vary 2..5 bank records, corpses in later slots, facings, selected run
history, flags, alert 1/2, Prince movement poses/mode, spacing thresholds and
front/rear tiles. Nearest-candidate indices are supplied from the existing
selector and input-to-animation acceptance is isolated at ready pose 171.
This does not independently revalidate target selection or the entire frame
scheduler. Report: `rendered/waiting-group-native-v1.json`.

## Skeleton Record Normalization: Implementation In Verification

The non-following UpdateOppInfo path was missing physical room normalization.
`cut_opponent_position` now reproduces the separate 365-pixel persistent Cut;
the existing live follower's 360-pixel path is unchanged. Type-4 actors are
stored from their previous bank view, moved to their real room without a
duplicate, or removed if no room link can receive them. Existing full-bank
retention is deliberately preserved rather than reproducing native loss.

Direct original Cut matches all 8,000 random graph/position cases, including
2,386 missing destinations. The combined original UpdateOppInfo probe then
exposed another important distinction: GetCellI accepts row -1 without Cut.
Implemented that predicate and the negative cell encoding instead of hiding
the mismatch in the fixture. An optional room-record cell preserves InitOpps'
signed decode, including cell -10 -> row -2. Earlier snapshots still decode
without that field. TransferOppInfo uses negative row offsets -1/-11, not
row*10; the stored cell now preserves that distinction too.

Final original comparisons: 1,200 complete observed record outputs
and 1,308 cell/marker/facing/cursor reloads match, in addition to the 8,000 Cut
cases. Endpoints supplied by the harness and excluded geometry are documented
in AI_RECOVERY.md. Local probes use the three `*_native_probe_v1.py` files
named there. Asset-free position/record-format tests pass in an isolated
temporary project; only the two asset-backed alert integrations skip.

The earlier 21,504 supporting-cell/room-link queries still match, and the
192 follower transfer cases now also compare their emitted encoded cells.
Four new integration regressions fail under the old enter_room method and
pass under the new one, with no fixture errors. Broad AI/combat/pursuit/
generation/skeleton/harbor/save/slots/rebirth/terrain scope passed 561 tests
(one optional skip); subsequent focused validation passed 97 tests including
the final negative-offset helper, extended snapshot validation and reload.

Committed as `9aa7f9c`, GitHub Tests run 39552814145 passed. Lint, catalog and
diff checks passed. Final isolated asset-free run: 24 tests, two optional
integration skips. Pending follow-on
fronts remain the cached-FRAM initialization provenance, hidden-facing removal,
ordinary rooftop bank scheduling, noise producers and later special actors.

## Ordinary Guard Room-Bank Investigation

The current rooftop active set still includes neighboring/distant pursuers
without the explicit five-slot room-bank selection used by skeletons. Before
changing this, recover ordinary InitOpps reload and its native alive word;
otherwise restricting updates alone would preserve the wrong room lifecycle.
Static review: a zero cursor normally chooses unarmed sequence 77 (except
saved sequence 22) and restores full life. A nonzero cursor restores current
sequence/cursor, stored sword and HP, then executes one AnimChar. Source flags,
jump-height metadata and corpse-slot selection are additional dependencies.

Local `rendered/guard_reload_native_probe_v1.py` audits this path. Its first
version used the shared decoder and exposed a missing -23 rule before any
bank conversion was attempted. Do not interpret its preliminary counts as a
completed ordinary-guard bank implementation.

## Terminal Pose Recovery: Implementation In Verification

Original `4:2f00-2f14` rewinds to max(0, entry_cursor - 1) and continues
decoding. The old interpreter just returned the cached action, which can be
zero after reload. Implemented the original reread in SequenceRuntime; this
is a prerequisite correction for both skeleton and ordinary guard records.

Independent original AnimChar execution matched all 867 final cases versus
861 baseline mismatches. The probe supplies only resource lookup and Toolbox
handle locking, not a replacement animation decoder. Reports are local
`rendered/sequence-hold-native-v1.json` and
`rendered/sequence-hold-native-baseline-v1.json`.

Eight focused tests pass, including a real held skeleton combat reload.
Replaying the previous method yields six failures and no test errors. In a
clean temporary project, the seven asset-free checks pass and the single
original-resource integration skips. The prior 9,504 InitOpps/SkelAddOpponent
audit still agrees after this correction.

The ordinary guard InitOpps comparison now uses native AnimChar independently:
all 1,280 observed reload outputs agree with the corrected shared decoder.
This includes 416 cases with negative native ALIVE but zero HP, and 240
zero-cursor sequence reinitializations. It does not prove the full room bank.

Full discovery ran 1,906 tests: four failures (the four window sizes in one
save-browser pixel test), one skip and four expected failures. Replaying the
previous interpreter reproduces all four failures. The test reads a real
user save with an embedded preview, but compares it with a newly rebuilt
preview; these need not agree. Isolate its save list rather than changing
production rendering or user data. Focused animation/skeleton/save-format
validation passed 92 tests; lint, catalog and diff checks passed.

## Zero-HP Reload: Next Proven Lifecycle Difference

`rendered/zero_hp_reload_native_probe_v1.py` executes PlayerCtrl's original
4:3d24-3d70 prefix before skeleton AutoCtrl. A resumed held pose can have
native ALIVE=-1 with HP=0. PlayerCtrl registers death before AutoCtrl and the
recovery timer counts down: 99 -> 98/97/96/95 over four frames. The port keeps
native_alive=True and timer=99 throughout. This is not a reason to alter
reload semantics: the missing operation belongs to the control phase.
The probe retains the existing cycle harness's flat-map, RNG and shared-SEQS
limitations. Implement and test this scheduling correction separately.
Keep ordinary rooftop bank conversion open; do not claim complete AI.
