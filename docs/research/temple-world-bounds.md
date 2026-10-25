# Temple Sprite Bounds Inside World Control

Research only. Composes [real sprite bounds](temple-sprite-bounds.md) with
[the frame/world chain](temple-frame-progression.md). No runtime or artwork
changes; the user's local README preview is deliberately left uncommitted.

## Actual Native Chain

World2:6224/Prince2:62e6 now executes LoadFrame4:2a72, SetupSword3:0ac8 and
GetCharEdges4:5cbc both before controls and after ordinary animation.
PlayerCtrl4:3b88/GenCtrl use the actual supporting column and body width in
current/front/above ReadCell and SlideRockInCell10:2036. Actor save2:6472
retains the clipped visible rectangle, and the saved edge bank receives the
**final** sprite edges rather than the old supplied constants.

The body width is no longer a supplied18 in this composition. Initial
poses89 and91 have original header widths29 and20, hence collision widths
30 and21. Pose89 uses active clip210 at cursor2, selected source9; pose91
uses clip9 at cursor3. These are prepared animation states with supplied
positions, not a claim that every room/input combination is reachable.

The corpus covers all41 original gate anchors in levels10..13, three
position/phase pairs, two facings, three sampled input combinations, two
initial poses, three X offsets and empty/one-record static rock banks.
Tile words remain original; only the chosen gate position/phase and supplied
actors/banks are fixtures. The occupied-bank placements include real native
left-edge wall clipping, where the Prince's body width is an input.

A separate reference-only counterfactual holds controller width at18 to
measure selection differences. Its calls are not counted as additional native
comparisons or evidence for reachable gameplay. Six asset-free regressions
bound width-dependent climb choice, pre/post-control ordering, final saved
edges/rectangle, animation suppression and missing-size preservation.

**8,856 actual world calls, zero mismatches:**4,428 empty-bank and4,428
occupied-bank cases. Initial collision widths are30/21, and final widths
include17/18/25/29/37 as different animations load different poses. Native
left-edge clipping executes120 times. The fixed18 counterfactual changes the
selected source in18 fixtures; the real-width reference matches native.

Complete actor records (including final visible rectangle), saved/current
edges, frame metadata, drawing setup, edge-cell rows/columns, remainder,
level/TROB/cache/MOB bytes, input/cooldown state and ordered native/supplied
events are compared. Sequence/frame bytes and their prepared handles stay
unchanged; default/screen rectangles and shared scratch flags are canaries.

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Compared-output SHA256:
`2f0bb627c71b681d2f1853e8b273eab52aa60f217d989d4e3fb2979313043b35`.
Original data and the detailed report remain ignored locally.

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_world_bounds --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_world_bounds_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_world_bounds_reference
```

## Boundaries

SHAP dimensions still come from a supplied service reading original Kid
headers; screen intersection is an explicit supplied SectRect callback.
Frame/sequence/library handles, input samples and initial placement/banks are
prepared. The original renderer, Resource Manager and QuickDraw are not run.
Only type0/unarmed actors and normal AFRM25001 are connected here; armed
extension and failed-size paths have the preceding isolated native proof.

Physical barrier/contact/floor/pressure/hazards, opponents, presentation and
clock services remain supplied and are listed by address in the report.
Static rocks do not advance in this corpus. This is a single-world-update
composition, not full FrameAdv, multi-world physics, climbing reachability or
playable temple integration. Previous pure reference defaults are unchanged.
