# Temple Preparation

Independent research, baseline `da0b021`, branch `codex/temple-preparation`.
The level-six/ruins runtime integration remains on the parallel campaign
track. This work does not enable temple gameplay, import scenery, change
saves/README or claim complete AI equivalence.

## Resource And Level Inventory

```powershell
python -m tools.inspect_temple --source PATH_TO_RECOVERY --output rendered/temple-inventory.json
python -m tools.probe_temple_headers --source PATH_TO_RECOVERY --output rendered/temple-native-headers.json
python -m unittest -q tests.test_inspect_temple tests.test_temple_headers_reference
```

The inventory reuses existing LevelDefinition/LevelMap readers; it is NOT
independent native proof of the whole decoder. Its full room/record JSON
stays ignored locally. Unit tests contain synthetic fixtures only.

All four levels use environment 2, opponent set 7: Temple.rsrc,
Birdhead.rsrc and Prince palette CTBL 25002. These are not the ruins/head
assets used by levels 6-9. File-table selection follows 3:51fa/5f58,
as in the earlier resource inventory.

| Level | LEVL | Start Room:Cell | Checkpoints, Native Slots | Initial Generators | Link-Reachable Rooms |
| --- | --- | --- | --- | --- | --- |
| 10 | 2009 | 22:23 | none | five raw kind7, SEQS77 | all32 |
| 11 | 2010 | 5:25 | slot2 =6:17 | two raw kind7, SEQS77 | all32 |
| 12 | 2011 | 19:22 | slot1 =11:10; slot2 =2:9 | three kind7/77; one kind1/105 | 1..26 |
| 13 | 2012 | 3:14 | slot1 =32:19 | three raw kind7, SEQS77 | 29 rooms; excludes21/23/26 |

Link reachability is not gameplay traversability/solvability; omitted rooms
are not automatically broken or intended destinations.

Temple.rsrc contains 123 SHAP, one CTBL, one PIEC, one SHPL and CUST
4025/4075. Birdhead.rsrc contains FRAM/AFRM/SHPL750 and one CTBL750.
Its FRAM has 108 ten-byte records and AFRM has 85 eight-byte records;
do not substitute the Head bank's single attachment record.

### Custom Room Caveat

Native IsCustomizedRoom flags level13 rooms2/4/26, and none in levels10-12.
Candidate IDs are4025/4075/4625. The first two are present in Temple.rsrc;
4625 is absent in that preserved fork and in the other checked resource
forks. Room26 is not link-reachable from the supplied level13 start.

This is not proof of corruption, a fatal importer dependency or a playable
missing room. Static LoadCustomRoomData3:1378 tests a null GetResource result
at3:13a6 and branches to return; full loading/fallback behavior still needs
an independent trace, including old custom state and callbacks.

## Native Header Results

Original executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
The two ignored reports record original level hashes.

| Rule | Source | Evidence / Scope |
| --- | --- | --- |
| Entry selector | 2:5d98 to before5e36 | R: four original headers; level10 selects2 and sets nativeX430; others select5 and preserve supplied X |
| End-song selector | 5:4e0c-4e42 | R: all four return187; no sound playback |
| Custom-room predicate | 3:1310-1362 | R:128 actual-room queries +16 supplied high-bit controls |
| Actor kind conversion | 6:2bca to before2c12 | R:210 selector invocations across14 actual slots with raw-kind controls; no full InitOpps |

All comparisons pass; no native services are supplied in this header probe.
13 asset-free unit tests cover inventory/reference branches, not original
execution. `R` means recovered/reference, not implemented gameplay.

The kind selector uses the level set7 for ordinary kinds, preserving only
exceptional raw kinds1/3/9/10. The original DATA table maps actual raw7
to **working actor2**, and the level12 raw1 at room7/slot0 to **actor10**.
Set number, generator kind and working actor type are different concepts.
This does not establish identical ordinary-guard/Birdhead AI or initialization.

Entry testing stops BEFORE JumpSeq/AnimChar. Native X600 is a canary for
the non-level10 selectors, not their actual spawn coordinate. Actual entry
position, SEQS2 execution, level9->10 story playback and restarts remain open.
The nativeX430 special selection corresponds to portX223 under the usual
207-pixel conversion, not the header's portX175. Do not simply reuse the
generic header start when integrating that entry.

## Mechanism Priorities And Integration Gates

The gate-contact follow-up now includes independent
[face/back distances](temple-gate-distance.md), with real admission and
room adjustment, and [hard contact/ejection](temple-gate-ejection.md).
The [general soft distance selector](temple-gate-soft-distance.md) is also
recovered independently and [composed with the real contact caller](temple-full-contact.md).
Collision-bank construction and repeated physical support remain separate
steps; no new temple runtime is enabled by these research modules.
The first bank boundary is now recovered as
[collision history selection](temple-collision-history.md), followed by the
[actual row sweep](temple-collision-sweep.md). Caller-generated intervals,
three-row composition and sliding-rock overlays remain separate steps.

The inventory retains candidate tile IDs without assuming all behavior:

- Tile25:2/2/6/2 cells by level10/11/12/13. Sliding-rock machinery is in
  CODE10, including TriggerSlideRock10:2152 and ATMSlideRock10:1456.
- Tile26:3/1/3/3 cells. Falling6:0210 and ShakeEm5:28c8 call
  TriggerTrapDoor10:25aa. Its constructor10:25e8 and ATM10:225c need
  separate state/animation/collision traces, not an ordinary loose-floor alias.
- Tile43 occurs once, level13 room4/cell11. Altar/shadow/flame logic and
  NISTemple15:5fd4 are separate targets; no behavior inferred from the tile alone.

The first bounded mechanism block is now recorded in
[trap-door triggering](temple-trapdoors.md): actual cells, full native
constructor/append/capacity handling, explicit sound/redraw boundaries.
The follow-up probes below recover bounded animation/lifecycle effects;
full caller scheduling and collision remain open. Then investigate
sliding-rock activation/persistence, temple draw
dispatch/custom callbacks, Birdhead combat/frame data, altar/flame/story rules.
Do not treat this list as complete temple rule coverage.

These are raw resource counts. Level12 room29 contains one of the six tile25
markers and a linked plate, but lies beyond the header's26 declared rooms;
native ReadCell returns wall20 for that source. The caller-admission probe
below distinguishes direct raw-link controls from admitted gameplay sources.

## Trap-Door Follow-Up

- [Phase advancement](temple-trapdoor-advance.md): native phase/audio-gate
  helper and MakeRubble update/save/compaction; initial1/75 reaches low17
  after16/6 helper calls, not a millisecond delay.
- [Presentation/restoration](temple-trapdoor-presentation.md): native full
  ATM body restores level cell even when invisible, with prepared image-cache
  headers, transient draw coordinates and explicit visibility/drawing services.
- [Connected lifecycle](temple-trapdoor-lifecycle.md): real constructor and
  both native bank dispatchers across40 stateful traces/800 supplied cycles;
  restoration and next-update compaction, without complete FrameAdv simulation.

These supersede the initial animation-state gaps only in their documented
subsets. Actual pixels, complete scheduling, sound state and collision remain open.

## Sliding-Rock Follow-Up

[Activation and row lookup](temple-slide-rock-trigger.md) now covers the
complete native trigger, record selection and normal-cell initialization:
4,620 comparisons over all 12 actual marker cells, with supplied control
inputs/banks and no supplied native services. It establishes one selected
live type-6 record per matching room/row lookup, control-word changes and
capacity behavior, not movement or a complete actor controller.

[Motion control](temple-slide-rock-motion.md) now covers the complete native
10:1d5c body with supplied geometry/audio/actor endpoints:3,190 comparisons,
including real left links, native division/IsWall and62-byte actor copies.
Control is not speed: ordinary movement proposes X-2 per helper call; the band
predicate can stop it from control8, and mark1 finalizes to control100. These results
do not yet validate actual geometry or the subsequent crush body.

[Real geometry](temple-slide-rock-geometry.md) now independently validates the
native band scans and ReadCell/normalization/cache without supplied endpoints:
32,082 comparisons over all four maps and bounded arithmetic/topology controls.
Important correction: true means neither IsSpace nor marker25 in both scanned
bands (including vacuous empty intervals), NOT empty/clear space. The supplied
motion probe now calls this response `filled`; its transitions are unchanged.

[Connected updates and crush admission](temple-slide-rock-update.md) now execute
real geometry/cache plus motion10:1d5c, contact gate10:16f6 and native type6/bank
dispatch. 13,708 comparisons include24 activation/update traces over all12
markers,3840 updates and supplied view-selector changes. Live bank state persists
or compacts as expected; this is NOT file-save/checkpoint/restart persistence.
That update probe supplies reaction10:1b04 and the movement actor reactions,
so it alone is not damage/death/animation proof. The contact gate's mode4 bypass is word+52,
not actor-kind4, and still requires matching Prince room/row.

[Native contact consequences](temple-slide-rock-contact.md) now replace10:1b04
with its full body, health/death-method primitives, JumpSeq and the actual first
AnimChar call for clips47/48/71/93. 8,322 comparisons include all12 original
anchors and eight connected six-update contact traces. Terminal solid contact
can set alive0/pose185/pending damage; action5 and tile2 have explicit bypasses.
Resource/handle management and audio remain supplied; later animation/death
progression, other actor reaction bodies and full FrameAdv remain excluded.

[Native presentation](temple-slide-rock-presentation.md) now covers full
ATMSlideRock, decoration strips, rectangle computation and native object-queue
appends through both direct and ATMLoose/type6 entry. 1,416 comparisons include
all12 actual anchors and3,292 object appends. The16-byte rock/bank is restored;
two dimension-table heights are canonicalized to the saved height7. Visibility,
rectangle system services and the redraw-list sink remain supplied. This is
queue-write evidence, not raster output, real room cuts or FrameAdv coverage.

[Connected lifecycle](temple-slide-rock-lifecycle.md) now carries the real bank,
dimensions, cell cache and object queue through trigger/update/presentation.
19,504 native/reference operations pass in60 actual-anchor and4 multi-record
traces. Another7,680 comparisons confirm identical persistent physics with
absent, visible, invisible, alternating or repeated drawing. Scheduling,
visibility and queue reset boundaries are supplied; no actor reaction endpoint
is reached. This does not extend damage/death, actual pixels or FrameAdv proof.

[Caller admission](temple-slide-rock-admission.md) now executes TriggerObject's
tile25 branch, six raw rock-only link chains and repeated held/permanent
PushPlate calls on five header-admitted sources:8,609 comparisons pass without
supplied native services. Caller mode5 selects rock how2; other tested words
select how1. Return-1 skips TROB creation while link traversal continues.
The fresh timer<2 branch and two mixed chains are covered by the subsequent
bounded experiments below, with their own stated service boundaries.

[Mixed gate/rock links](temple-mixed-plate-links.md) executes both original
level11 room3 chains, native gate admission and TROB lookup/append/update:
9,206 comparisons pass without supplied services. The two banks have independent
capacity limits; rejected creation in one does not abort the other mechanism.
First coordinate match updates only the TROB phase, even at capacity. Repeated
held/permanent plate calls preserve source write/cache ordering. This does not
establish fresh plate setup, actual actor admission or combined animation.

[First-press setup](temple-fresh-plate-setup.md) now covers PushPlate's fresh
branch and its immediate held repeat on all seven admitted rock-linked sources,
plus three explicitly supplied sound-exception controls:4,800 comparisons pass.
The source TROB request precedes target activation and takes the last available
slot ahead of a missing gate TROB. Audio and redraw bodies are request sinks,
not native playback/pixel proof; other gameplay writes execute natively.

[Plate release and TROB lifetime](temple-plate-release.md) recovers the previously
unlisted5:2554 helper, stored-kind dispatch and stable bank compaction.10,640
comparisons pass over68 header-admitted original plate markers and supplied
bank topologies. Timers decrement per record; timer1 lifts the plate, whereas
timer>=31 removes the record while retaining its depressed bit. No Trigger or
sound call occurs in this helper. Redraw remains a supplied request sink.

[Connected plate lifetime](temple-plate-lifetime.md) now carries native press,
held refresh, release/compaction and re-press across600 persistent traces on
five admitted original rock-only sources:14,400 operation comparisons pass.
Ordinary re-press re-registers the source and reuses the rock; plate release
leaves rock control unchanged. Supplied full-bank controls expose a timer5
source with no animation record after rejected registration. Pressure-first
and animation-first schedules are compared explicitly, not asserted as FrameAdv.

[Actor pressure admission](temple-pressure-admission.md) now executes original
CheckPress, real above/current ReadCell helpers and temple cell traversal:
16,461 comparisons pass. It covers actor/float/selected-sequence exclusions,
pose/mode/FRAM/Y boundaries, ALIVE versus type4 permanent-pressure selection,
and the pose79 early loose-floor/trapdoor dispatch. The supporting cell and
actor/FRAM state are supplied; four outgoing mechanism bodies are request sinks.
This does not yet connect actor admission to the earlier lifetime traces.

[Actor-to-plate lifetime](temple-actor-plate-lifetime.md) now connects native
CheckPress to ordinary/permanent pressure and release on the five admitted
rock-only sources:540 persistent traces/7,110 comparisons pass. It also
executes5:252e's timer31-before-PushPlate ordering. Supporting-foot calculation,
frame scheduling, target gate animation and reset/save remain separate.
The constructor's X>510 branch and full movement/contact/presentation
lifecycle remain open.

[Permanent-pressure setup](temple-permanent-pressure.md) independently bounds
the complete5:252e wrapper and timer setter over all68 admitted original
plates plus explicit cache controls:1,304 comparisons pass. Timer31 precedes
the explicit PushPlate(kind,index) call; the wrapper alone does not change
the source depressed bit or banks. PushPlate is a request sink in this
independent wrapper probe, not in the five-source connected lifecycle above.

[Gate TROB animation](temple-gate-animation.md) now executes the temple's
stored-kind4 dispatch, native DATA motion tables and bounded StopGate body:
6,300 comparisons pass over all41 original anchors plus supplied position/
phase/forced relief controls. LoadKid, level4 relief return, cue playback
and redraw remain supplied; actors are explicitly non-hanging. The relief
countdown is not a damage word. Real crush consequences remain separate.

[Mixed lifetimes](temple-mixed-lifetime.md) now connect real actor admission,
both original level11 room3 link orders, source/target TROBs, gate motion and
stable compaction across120 traces/14,784 comparisons. The pressure cache,
unused bank storage and actor canaries are preserved/checked at every step.
Rock motion and actual support/contact geometry remain excluded, not inferred
from passing the connected activation/animation trace.

[Gate services](temple-gate-services.md) corrects the initial support/contact
labels and executes the real LoadKid4:4b02 and level4 relief5:4766 bodies.
11,361 comparisons pass, including3,075 connected original temple gate steps.
LoadKid copies all62 saved actor bytes; relief rejects temple levels before
looking at any opponent. Positive level4 controls use supplied actors/counts,
not original level4 gameplay. Hanging reactions and full FrameAdv remain P.

The same real callees now run inside the120 persistent mixed traces via
`--native-gate-services`:14,784 comparisons pass, including64 full LoadKid
copies and30 native relief rejections. Current actor/FRAM inputs are supplied
afresh before each operation, not evolved through a native Prince controller.
[Mixed rock motion](temple-mixed-rock-motion.md) now joins real geometry/
motion/crush admission and both bank compactions to the plate/gate chain:
192 traces/83,040 comparisons pass, with saved Prince room0/frame0 deliberately
excluding actor reactions. Working actors and both call orders remain supplied;
this is not full FrameAdv, reachable gameplay or a damage timeline.

[Gate hanging helpers](temple-gate-hanging.md) now cover native StopGate /
JumpSeq47/copyback and the separate sound29 predicate at all41 original
gate anchors:14,268 comparisons pass. Actor fields and SEQS existence are
supplied; the clip itself and full caller schedule are not executed. These
helper proofs do not extend the non-contact mixed-motion trace's scope.

[Hanging gate animation](temple-gate-hanging-animation.md) connects those
helpers through the real type4 TROB body:26,568 comparisons at all41 anchors
pass for six explicit phase/position controls. Ordinary/fast/permanent gate
paths have different actor-copy/sequence/cue ordering. No AnimChar or full
bank/frame scheduling is inferred from native JumpSeq selection alone.

[Actor clip progression](temple-gate-actor-clip.md) now follows that gate
selection through native AnimChar and the original SEQS47-to2 link:
2,952 traces/73,800 operation comparisons pass. The first actor update
changes mode2 to5 and X+16 before poses50/51/52; the fourth enters idle
mode0 while retaining selected source47. This is not physical fall proof:
Y/health remain unchanged without GenCtrl/physics. Resource/handle services
and the actor-update/copyback schedule remain explicitly supplied.

[Actor and gate-bank progression](temple-gate-actor-bank.md) now executes
full native AnimTrobs iteration/compaction between actor clip updates:
2,460 traces/78,720 operation comparisons pass. Both supplied update orders,
full20 banks, stable compaction and duplicate-record controls are checked.
First-cycle actor effects differ with the order, so this still does not
choose an original FrameAdv cadence or establish physical falling/contact.

[World/Prince callers](temple-world-prince.md) now replace that supplied
schedule with actual2:6224/62e6 calls and actor save2:6472:8,528 persistent
traces/34,112 world comparisons plus2,400 gravity controls pass. Animation,
control-return, room0, invulnerability, countdown and cut/time guards are
bounded. PlayerCtrl, geometry/contact, opponents and presentation/clock
services remain supplied; this is not outer FrameAdv or physical gameplay.

[Hanging controls](temple-hanging-control.md) separately replace supplied
GenCtrl with the real hanging/climb/release/preview decisions after gate
selection:28,220 traces/112,880 operation comparisons pass. The controller
can retain47 or replace it with25/10/73/11/23/99 before ordinary animation.
DoJumpHang's preview restores sequence fields but retains pose/mode/X effects.
Cell/bars responses and sampled latches are supplied; this composition does
not yet run PlayerCtrl or the world coordinator around the real controller.

[PlayerCtrl in the world caller](temple-player-control.md) now closes that
specific composition gap:7,090 native/reference world updates pass with real
PlayerCtrl preparation, restore/normalization/orientation/cooldown, hanging
GenCtrl, latch save and actual Prince save. Cooldown1 can admit climbing in
the same update; consumed Up1 also satisfies the hanging branch's nonzero
test. Sixteen real preview calls retain their actor effects through save.
Input polling and cell/bars/physical-contact services remain supplied;
these are single-update fixtures, not complete gameplay/input parity.

[Real controller geometry](temple-controller-geometry.md) replaces the three
cell-query sinks and executes SlideRockInCell, correcting the old `bars`
name:9,534 world comparisons plus8,064 direct query/edge comparisons pass.
All cache words, cross-room reads, static MOB-bank selection, gate/rock climb
admission and final actor state are compared. Left-edge clipping uses `max`,
not `min`, and depends on supplied frame width/facing. Actor anchors, widths,
static banks and sampled axes remain fixtures; other physical contact and
multi-frame gameplay are not yet proved by this composition.

[Prince frame metadata](temple-kid-frames.md) now independently executes real
type0 LoadFrame and supporting-column calculation with all352 original Kid
frames:22,528 comparisons pass across two facings,16 X values and two
separately supplied attachment bindings. This recovers the column input,
not foot Y/row, sprite bounds/frame width or reachable frame progression.

[Frames in world control and bounded progression](temple-frame-progression.md)
connect that real loader before/after animation inside the actual caller:
2,214 world calls plus21,750 persistent AnimChar/LoadFrame operations match.
Scripted X/Y/row changes and refreshed supporting columns are compared;
manual helper continuation is not another complete world/physics update.
GetCharEdges/width, support/contact and outer FrameAdv remain separate gaps.

[Prince sprite bounds](temple-sprite-bounds.md) independently executes real
LoadFrame/SetupSword/GetCharEdges with original Kid dimensions supplied from
SHAP headers:33,792 comparisons pass. Collision width includes one extra
pixel and an optional sword extension; the clipped visible rectangle is
separate and lives in the actor record. World composition, support/contact
physics and full FrameAdv are not implied by this isolated bounds proof.

[Sprite bounds in the world caller](temple-world-bounds.md) closes that
composition gap:8,856 native world updates match with real Kid drawing/edges,
two hanging poses and empty/occupied static rock banks. Final actor rectangles
and edge saves are compared; keeping width fixed18 would change18 selected
animations in this corpus. Physical contact/floor/hazards, initial placement,
sampled input and shape/graphics services remain supplied. This is not a
complete physical climb/fall or repeated FrameAdv/playable-temple proof.

[Gate admission](temple-gate-admission.md) now recovers native4:5b0e and its
visible-height threshold:102,400 controlled direct comparisons and14,080
predicate comparisons after2,816 real Kid frame/bound chains match. Equality
permits passage; clipping and signed-word height matter. This does not yet
execute the contact/barrier caller or imply physically reachable passage.

[Standing clearance](temple-gate-standing.md) executes GateBarrToStandUp and
real cell traversal with no service replacements:39,318 comparisons match.
The first gate wins; only low-byte positions1..183 and an inclusive native-X
band block this helper. Cache and room-base-pointer writes are compared.
Caller/standing animation and full physical contact remain outside this proof.

[Contact routing](temple-gate-contact.md) extends the chain through actual
CheckGateForKid/ReadCell/admission/JumpSeq50:61,382 comparisons match. The
contact caller checks neighbors in a different order from standing; exact
overlap, resource failure and ALIVE/HP separation matter. Distance, overlap
construction, ejection/cave terminal responses and repeated physical world
updates remain supplied or excluded; this is not crush/death parity.
