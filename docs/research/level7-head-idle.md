# Head Idle Decisions

Research only, not runtime AI. `R` means recovered/reference behavior.

| Rule | Source | Status |
| --- | --- | --- |
| Pose admission and idle direction choice | 7:1268-12c6 | R: actual body entry, supplied bounded random outcomes |
| Movement admission before variant selection | 7:12c6-131e; 7:0936 | R: full native geometry/cell/gate helpers |
| Idle sequence selection and normalization | 7:12d8-131c; 6:0006 | R: native JumpSeq/frame helpers, resource existence supplied |

The exported 7:1266 entry is RTS. The wrapper calls the actual idle helper
at 7:1268; probing the marker alone would miss the behavior entirely.

## Reproduction And Result

```powershell
python -m tools.probe_level7_head_idle --source PATH_TO_RECOVERY --output rendered/level7-native-head-idle.json
python -m unittest -q tests.test_level7_head_idle_reference
```

Original executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
The ignored report also records Prince/Head hashes and output digest.

38,016 supplied cases pass with zero differences: head-slot room/type pairs
from all eight actual records, poses 149/150/159, both facings, eight selected
sequence values, rows 0..2, X offsets -13/0/+13 around cached column 4 and
11 explicit random tapes. These are supplied positions, not spawn positions.

Within those cases, 25,344 reject the pose before any random call; 10,944
query original movement admission and 7,154 select a sequence. These counts
overlap the 38,016 cases and must not be added together. Every idle sequence
131..138 is selected in at least one case.

Checks include all 62 working bytes, declared global division remainder,
unchanged full level bytes, real frame/attachment bytes, requested random
bounds/results/order, movement-query directions, requested SEQS and frame
reload count. Eight asset-free unit tests cover reference branches only.

## Recovered Choice And Ordering

Only pose 150 makes idle decisions. Other tested poses return immediately
without consuming randomness or querying movement.

The first request is Rnd(3), an inclusive supplied outcome 0..3:

- 0: propose direction 0.
- 1: propose direction 1.
- 2: request Rnd(1), then propose direction 2 or 3.
- 3: continue direction 0 if selected SEQS is 131..133, or direction 1
  if it is 134..136. Other selected sequences return without a query.

The ORIGINAL movement-admission helper runs for the proposed direction,
using the cells/gate rules in [head movement](level7-head-movement.md).
If blocked, do not choose another direction, request a horizontal variant
or change sequence/cursor. Admission may still update the global division
remainder even when rejecting; that scratch effect is included in the probe.

If admitted:

| Direction | Requested SEQS | Additional Random Request |
| --- | --- | --- |
| 0 | 131..133 | Rnd(2) |
| 1 | 134..136 | Rnd(2) |
| 2 | 138 | none |
| 3 | 137 | none |

Native JumpSeq then performs the previously verified head normalization,
including facing, pose-150 displacement and supporting-column recalculation.
Do not omit those effects when integrating this decision in a host controller.
Selection still does not advance an animation pose or execute movement.

## Supplied Endpoints And Limits

- Rnd 17:6e06 returns explicit bounded outcomes from a supplied tape. The
  probe verifies exactly which draws are consumed; unused tape entries are
  not secretly consumed. Seed evolution, native random distribution, OS
  Random trap and replay timing are NOT certified by these tapes.
- GetResource 17:330e reports actual Prince SEQS existence, without loading
  sequence bytes. Real Head FRAM/AFRM are installed for native frame reloads.
- Working state, cached column, selected sequence and body bounds are
  supplied. Native ReadCell/CalcBlue, IsWall/IsSpace, gate clearance,
  signed-remainder math, AddCharX and supporting-column helpers execute.

No stubbed movement-admission/AI leaf, but no actual motion ticks, rendered
sprite bounds, all-state reachability, wrapper scheduling, full collision,
attack/locked/flee behavior or complete special-actor AI claim. Wrapper
admission remains covered separately by the routing probe; this experiment
invokes the real idle leaf directly.

Next bounded work: actual angry/attack or locked/flee transitions, followed
by SEQS execution/cadence and snake activation. Runtime integration should
remain separate until those dependencies and shared-file ownership are clear.
