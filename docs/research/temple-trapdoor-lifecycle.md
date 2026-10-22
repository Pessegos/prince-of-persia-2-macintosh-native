# Trap-Door Connected Lifecycle

Research/reference only; this is not a complete native game-frame simulation.

```powershell
python -m tools.probe_temple_trapdoor_lifecycle --source PATH_TO_RECOVERY --output rendered/temple-native-trapdoor-lifecycle.json
python -m unittest -q tests.test_temple_trapdoor_lifecycle_reference
```

## Connected Native Calls

The probe uses the actual original constructor10:25aa/25e8 with native
ReadCell/CalcBlue/AddMob, then carries CPU/memory, level and object-bank
state through repeated original MakeRubble5:29e8 and ATMLoose5:307c calls.
Both original indirect dispatchers execute for type10. The former advances/
compacts the bank; the latter calls ATMTrapDoor10:225c for presentation and
restoration. No fixture reset is performed between the connected calls.

This update-then-presentation order is SUPPLIED explicitly. The experiment
does not execute every surrounding FrameAdv instruction, input sampling,
Prince/enemy update, sound queue or room-cut decision.

40 traces pass across all ten actual type26 locations, both constructor
states1/75 and visibility false/true. Each trace carries state through20
supplied cycles, for800 cycles total. Six asset-free tests check the
reference orchestration independently from the native run.

Checks after EACH update include full bank/canaries, active records/count
and unchanged level. Checks after EACH presentation include full level,
bank/canaries/active records, pending cue and query/sound/reset/redraw/
dimension/rectangle/object-draw requests. Original unused bank-tail bytes
are retained; clearing them is not required for the reference to pass.

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Temple.rsrc SHA256:
`7c7b532ef5251949b299d6177962062bdb003b385675285873d77f865ea68ccf`.
The ignored JSON records the output digest and each trace's snapshots.

## Observed Stages

| Initial Word+0xe | Constructor Bank Count | Restoration/Marked-Deleted Cycle | Compaction Cycle |
| --- | --- | --- | --- |
| 1 | 1 | 16 | 17 |
| 75, low phase11 | 1 | 6 | 7 |

Cycle numbers refer only to the supplied order above, not certified elapsed
frames or real time. A presentation immediately after construction, extra
draws during room cuts, paused updates or another scheduler can change the
number/order of calls without changing either recovered helper.

At restoration, tile26 returns in the original room/cell and object word+6
becomes-1, but the entry still occupies its bank slot. The following update
compacts it out. In the tested current-room cases, visibility does not alter
restoration/deletion timing or final level state. All40 traces return the
ENTIRE level bytes to the untouched original fixture, not merely its tile kind.

This confirms that render-only x/y offsets do not accumulate as physics
motion and that the new object's phase survives real bank load/save calls.
The probe never substitutes Python-produced objects into the native bank
between stages; Python references are comparison outputs only.

## Supplied Services And Remaining Work

Presentation services are those documented in
[presentation/restoration](temple-trapdoor-presentation.md): visibility,
draw/redraw/audio boundaries, supplied SectRect and a prepared image cache
using actual original SHAP headers. No pixel decoding/rendering is performed.

The connected probe supplies PrinceSndOn197=true and198=false throughout,
including when the recorded AddSound requests occur. This is deliberately
NOT an assertion about actual sound durations, channels or queue updates.
Sound admission's independent booleans/order are covered in the separate
[advance probe](temple-trapdoor-advance.md).

There is one constructed type10 object in an otherwise empty, canary-filled
bank, with current-room view state. Multi-type interactions, visible-neighbor
rectangle paths, simultaneous platforms, caller admission/character contact,
collision/crush, exact FrameAdv cadence, save/restart and campaign integration
remain unverified. The earlier update probe covers all-type10 mixed deletion
and capacity iteration, not arbitrary other object types.

Next independent mechanism: sliding-rock activation, movement and persistence.
Keep integration with shared terrain/render/scheduler code coordinated with
the parallel campaign track; the temple is still not enabled for gameplay.
