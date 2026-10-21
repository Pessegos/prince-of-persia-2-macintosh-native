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

The save-browser presentation regression now supplies an empty save list,
so it always exercises the fresh current-run preview it asserts, regardless
of the user's existing files. All four fitted window sizes pass; no game
rendering or user save was modified. Terminal pose correction committed as
`8fa923e`; GitHub Tests run 39555076890 passed. Test isolation committed as
`f5b7767`; GitHub Tests run 39555171263 also passed.

## Zero-HP Registration: Implementation In Verification

`choose_guard_action` now registers zero HP before skeleton AutoCtrl, not
after its early return. A resumed native living flag is cleared; active or
rising bookkeeping becomes collapsing without replaying the collapse
sequence, reset timer or sound. Existing dormant/collapsing/lava bookkeeping
is retained. The wake-before-control order and skipped-control Y limit are
unchanged.

The new held room-record regression verifies timer one expires on the first
control pass and resurrection starts on the next frame. A second regression
covers five phase states and verifies no collapse replay or timer reset.
They produce six assertion failures under the old control order, then pass
with the correction; all 78 skeleton/terminal-pose tests pass.

Extended original-prefix/lifecycle comparison: 128 scenarios, 25,600 frame
snapshots, no mismatches in native living flag, life, sequence/history,
pose/cursor, timer, shakes, sounds or RNG state. Varies skill, timer, shakes,
facing and seed with temporary player range/mode interruptions. The shared
decoder/flat-map/ordinary-combat exclusions remain explicit. Report:
`rendered/zero_hp_reload_native_probe_v1.json`.

Broader combat/persistence validation passed 345 tests. Full discovery passed
1,908 tests in 364 seconds (one optional skip, four expected failures, no
unexpected failures). The preceding 72 lifecycle scenarios also retain
23,040 matching frame snapshots. Ruff, catalog and diff checks pass.
Next investigation: ordinary guard reload/bank scheduling, jump-height
metadata, hidden-facing records and upstream cached-FRAM provenance. These
remain open; there is no complete-AI claim and no reason to skip to level 4
merely because individual recovered branches now agree.

## Follow-On Findings While Full Verification Runs

Initial generator inventory (`rendered/hidden_facing_inventory_v1.py`): none
of the 105 stored records across LEVL 2000..2013 starts with facing 0x56.
This does not dismiss dynamic hidden-slot removal. Static references at
4:4d0e/4d58 are sequence/range constants, not writes to the facing field;
the actual removal write at 4:493e-494e also clears mode, ALIVE and HP.
Trace callers and existing port removals before adding a third direction.

Another independently proven omission is AnimCharTap(0), 4:30e0-30f6 and
314e-315a: it silently sets the Prince's movement/noise flag without
incrementing the footstep counter or scheduling sound. SequenceRuntime
currently ignores it. The direct original routine agrees in 72 supplied
actor/environment/counter/flag combinations except the 12 Prince cases
where a clear flag should become one. Original SEQS 11 and 227 contain
(-15, 0). Probe/report: `rendered/silent_callback_native_probe_v1.py/.json`.
Implement separately with asset-free tests and an AI consumption regression;
do not accidentally make an NPC set the global player flag.

## Silent Callback: Implementation In Verification

The previous turn made authoritative progress: terminal pose restoration,
save-preview test isolation and zero-HP control registration were committed.
The latter is `f1a5382`; GitHub Tests run 39556011884 passed. The worktree
was clean when this continuation began.

Silent callback zero now raises the Prince's movement signal without sound
or footstep counter changes. Seven asset-free tests and one optional guard
consumer integration pass; they produced ten assertion failures under the
old interpreter. A genuinely isolated temporary project also passes the
combined 16 hold/noise tests, skipping only their two original-resource
integrations. The new noise module is included in the asset-free CI step.

Extended native evidence includes 288 independent original AnimChar steps
using original SEQS 11/227, not the portable decoder. Together with 72 direct
AnimCharTap calls, all 360 outputs match. The prior implementation mismatches
60 times. Local reports: `rendered/silent_callback_native_probe_v1.json` and
`rendered/silent-callback-native-baseline-v1.json`. This does not close all
noise producers or the full target/alert/control scheduler.

Focused animation/combat/pursuit/death/skeleton/alert/hold/noise validation
passed 358 tests. Full discovery passed 1,916 tests in 364 seconds (one
optional skip, four expected failures, no unexpected failures). Ruff,
catalog and diff checks pass. Check GitHub CI after committing.
Ordinary guard room-bank conversion remains the next larger task; recover
source flags, jump-height metadata and cold initialization before restricting
active actors, rather than merely freezing the current neighboring set.

## Ordinary Guard Height Metadata: Native Audit

`rendered/guard_height_native_probe_v1.py` executes original InitOpps with
independent AnimChar for 510 supplied row/height/current-resource/cursor
reloads. Type 2 loads saved absolute Y from generator word +1c only when
the saved current resource is 100; otherwise it starts at the decoded
row's floor before the first animation step. This also applies to a zero
cursor whose sequence is then reinitialized to 77. Do not preserve every
airborne actor's old Y as an invented improvement. The fixture's row*10
negative cell encoding still incurs InitOpps' exact-tens row decrement.

Another 384 original SetSpecialOppInfo calls confirm that saving word +1c
depends on the selected/source sequence being 100 or 186, not the current
resource; other ordinary-environment cases leave its previous value intact.
Actor types 0/2/4, current/selected resource differences and several prior
heights are included. Report: `rendered/guard_height_native_probe_v1.json`.
Graphics, resource handles and record lookup remain supplied endpoints.
This is evidence for the upcoming guard-bank implementation, not a claim
that ordinary reload/persistence has already been implemented.

## Two-Commit Follow-Up Requested By The User

The silent callback change is `1260554`; GitHub Tests run 39557010449 passed.
This continuation began with a clean worktree and is concrete progress, not
a repeated status-only turn. The user subsequently requested two more commit
blocks. Finish those two blocks, verify CI and leave a resumable handoff.

Block one introduces the ordinary GuardRoomRecord codec before wiring its
consumer. It preserves the generator's existing resource header when a live
in-bounds save clears its cursor, preserves selected-sequence height metadata,
restores a resumed pose versus cold sequence 77/22, applies the native odd-slot
corpse variant and retains zero-HP/native-ALIVE distinction until control.
Pending records are consumed once, while header metadata remains available
for the next room save. Eight resource-independent tests cover these rules.

The real codec agrees with independent native InitOpps/AnimChar in all 1,280
prior guard reload cases, not just with a shared decoder. Its height also
matches all 510 original height reloads; the 384 metadata-write comparisons
remain unchanged. Native reports retain their scoped graphics/resource/record
lookup exclusions. Block two must integrate records, active-bank membership,
normalization, carried actors and snapshot compatibility together; the codec
alone is not a claim that the game's room scheduling has changed.

Block one committed as `4aa8b56`; GitHub Tests run 39591195930 passed.
The extended height fixture initially omitted level_kind, making its sound
callback unsupported; supplying the actual ordinary environment fixed the
fixture and all 510 real-codec comparisons passed without a production edit.

## Ordinary Banks: Second Block In Verification

Ordinary guards now share explicit current-room/visible-side active-bank
selection with skeletons, retaining current records before side imports and
five active slots. Membership persists until the next room entry; a distant
unselected pursuer no longer advances indefinitely. On departure, ordinary
actors save native records through the shared position-normalization path;
carried actors retain their cursor and receive InitOpps' next animation step.
Current-room refresh does not restart them. New generation records receive
bank slots, and corpse parity uses the active slot rather than source-room
list order. The approved boat stand-down remains in the normal controller.

New original UpdateOppInfo/Cut audit matches 1,600 integrated guard record
outputs, including the unchanged live resource header, cursor, stored life,
sword, facing, normalized room/cell/X and conditional height. Supplied support
cells/lookup and the preexisting full-bank retention safeguard are explicitly
excluded. Existing skeleton normalization still matches all 1,200 cases.
All 46,080 earlier CutAllOpponents decisions pass, plus 512 new comparisons
that independently vary HP and native ALIVE. Armed followers use native ALIVE
rather than prematurely treating a pending zero-HP death as registered.

Snapshots serialize GuardRoomRecord and optional Fighter fields, accept older
records without them, and reject invalid resource/cursor/life/cell/height.
New integration tests cover frozen distant actors, cold healed/unarmed return,
same-room continuity, resumed zero-HP control order, normalized ownership,
five-slot priority, persistent side membership, terminal removal and snapshot
roundtrips. Replaying the previous active_guards method fails both the distant
pursuer and bank-cap regressions, with no fixture errors.

The first broad run (1,934 tests) found two outdated fixtures: one assigned HP
zero without the native control registration, and one reordered its manually
inserted corpses without updating bank slots. Both fixtures now model those
explicit phases; focused checks pass. Final full discovery passed 1,937 tests
in 365 seconds (one optional skip, four expected failures, no unexpected
failures). The final explicit generated-actor ALIVE initialization follows
6:3c20-3c22 and is covered by a subsequent-code 249-test focused run. Ruff,
catalog and diff checks pass. Verify CI for the second requested commit.
No further commits are
authorized by the user's latest two-block request without continuation.

Remaining recovery fronts are not closed by these banks: full HP/ALIVE
sub-frame target/contact scheduling, complete candidate/type filtering and
obstacle braking, cached-FRAM skeleton ledge initialization, dynamic hidden
slot removal, the shared global step counter/random stream, full-capacity
native record loss and later special controllers/level-four progression.
The current scoped equivalence is not full enemy-AI parity.
Source-room actor ownership is still represented with stable objects and
rebased views, not literal native bank-memory copies. Audit all target/group-
count consumers before claiming complete equivalence of that representation.

## Renewed Two-Update Request: Active Targets

The user explicitly requested two further updates. This is the first of those
two blocks, not a continuation beyond an exhausted authorization. The prior
second block was b483f41, with Tests run 39593459507 successful.

Original selector 6:36f2 and Main 2:62f8-633e confirm that target selection
operates on the whole current bank. The port instead searched the physical
owner list, losing imported targets. Selection now projects active actors,
returns their canonical identity, and preserves local-control views. Player
turn/bump comparisons likewise project the selected target without mutation.
Native ordinary ALIVE is distinct from HP. Main retains opposing-facing
targets even after death and falls back to bank slot zero if reselection
finds none. Empty banks clear stale references. Two old skeleton tests
expected no target for a selected side actor; their HUD assertions remain
unchanged, while target expectations now match the verified native rule.

rendered/active_target_native_probe_v1.py executes the original selector and
retention branches: 8,000 cases each, zero mismatches. The owner-only selector
still fails 2,164 cases even with the corrected ALIVE helper. The probe varies
HP/ALIVE independently, resident/side coordinates, bank order, facing, height
and directional selection. Bank input and coordinates are supplied; type 7/8
metadata filtering, skeleton initialization and contact dispatch are excluded.
Eight resource-free ordering tests run in CI; six integration regressions
cover imports, canonical identity, retention, fallback, turns, bumps and error
restoration. Focused combat/skeleton/pursuit/snapshot run: 317 tests pass,
one optional skip. Second update audits group consumers of the same bank.

## Renewed Request: Group Consumers (Second Update)

First update committed as 7c9b249; Tests run 39597163076 passed. The second
block corrects two remaining physical-owner-list consumers. Unarmed noise
consumption now checks the last selected bank slot, retaining rebased local
views during control. A resident no longer clears the signal before an
imported actor can react, and an unselected later source record cannot keep
it pending. Armed/dead trailing slots retain the original branch behavior.

Tumble selection counts registered deaths and overlapping corpses from the
active bank. It projects the struck actor and corpse foot columns into the
current room, uses that bank's generator permission and tile/forced-tumble
queries, and leaves physical actors unchanged. The newly struck actor is
still excluded from the registered-death count, as native control has not
registered its death yet. Six new integration tests cover noise ordering,
imported/unselected corpses, projected overlap and current-versus-source
generator flags. Focused run: 258 tests pass, one optional skip.

rendered/active_group_native_probe_v1.py executes original DoOppTumbleSeq,
LoadShad, dead-pose predicate, death-count scan and unarmed noise consumer.
All 4,000 tumble decisions and 90 noise cases match. The first diagnostic
used the helper's default cavern controller header with ordinary guard
poses, producing six pose-228 mismatches; supplying the actual level-one
controller header fixes that fixture inconsistency without a production
change. Special-environment corpse predicates are explicitly NOT validated.
Generator permission, RNG outputs, cached supporting columns, tile queries
and the separately audited unarmed decision are supplied endpoints. This
does not prove forced-rooftop tumble, random-stream order or all scheduling.

Regression check: all five targeted tests fail against the previous owner-
list methods, with no fixture errors. Initial full discovery (1,957 tests)
found a real integration mistake in block one's interpretation of Main:
Main retains an opposing dead FrameAdv target, but SwordCtrl 6:2174-21fa
validates a separate cached target using HP. The port shares that target.
Restore its HP validation while retaining whole-bank selection. Do not
describe the isolated Main audit as the combined scheduler's proof. The
revised target probe matches 8,000 selectors and 7,070 scoped Main cases;
930 dead-cache cases are explicitly excluded from Main and independently
match original SwordCtrl 6:2174-21fa, with HP words supplied in the native
bank. This still does not prove the combined frame/control scheduler.
Two alert fixtures also need
their manually constructed room banks initialized.

The fast carried-guard turn regression previously assumed immediate HP-based
reselection. Its trace now shows kill -> pending native ALIVE -> registration
during player mode-5 pose 155 -> ready pose 156 -> turn, three ticks rather
than one. This delay follows the independently verified ALIVE selector and
existing uninterruptible-pose gate. A new integration test ensures a pending
zero-HP nearest candidate ceases obstructing selection after NPC control.
The broad opening/combat regressions pass again with the HP cache validation.
Final focused runs pass: 168 room/terrain/generation/alert tests and 298
combat/death/skeleton/recorded-snapshot tests (one optional skip in the latter).
Final full discovery passed 1,958 tests in 365.818 seconds, one optional skip
and four expected failures, no unexpected failures. Full output is retained
in rendered/unittest-full-active-banks-v2.log (including existing Tk teardown
warnings). Ruff, catalog and diff checks pass. Verify the second commit's
GitHub Tests run before handoff; the first run is already green.
The user's current request authorizes exactly these two updates. Leave the
larger AI recovery unfinished and resumable; do not claim full parity or
start a third implementation block without a renewed request.
