# Temple Sliding-Rock Connected Lifecycle

Research on `codex/temple-preparation`. This connects the original mechanism
and presentation bodies in persistent CPU memory. It does not enable temple
gameplay or establish the original FrameAdv schedule.

## Executed Calls

Each original tile-25 anchor is used to call TriggerSlideRock (10:2152),
then MakeRubble (5:29e8) and ATMLoose (5:307c). Both native bank dispatchers
execute, including motion 10:1d5c, geometry/ReadCell/cache, crush admission
10:16f6, ATMSlideRock 10:1456 and AddMobObj 5:346a. The native functions write
their actual banks, dimensions and object queue. Python reference outputs are
compared afterwards and are never substituted into native persistent state.

The harness combines the existing motion and presentation instrumentation.
ReadCell is observed once, through the geometry probe. Only the existing
explicit audio/actor and presentation service boundaries are supplied.

For each of the twelve actual markers, five traces execute 160 update cycles:
no presentation, visible presentation, invisible presentation, alternating
visibility, and two presentations after each update. View selectors change
through current/left/below/unrelated every forty cycles in every trace;
unrelated presentation always receives visibility=false. These are supplied
view controls, not recovered room-cut transitions.

Trigger calls use how1 at cycles 0/64 and how2 at 8/72. The update-then-draw
order and these call times are supplied. The object count is reset once per
cycle, while raw object storage, dimensions, cell cache, actors and mob bank
persist. A repeated presentation within the same cycle appends to the existing
queue; it does not reset it. The research buffer has 128 guarded object slots.

## Results

19,504 native/reference operation comparisons pass:

| Operation | Comparisons |
| --- | ---: |
| Connected triggers | 240 |
| Bank updates | 9,632 |
| Bank presentations | 9,632 |

There are sixty actual-anchor traces plus four supplied multi-record controls
with bank sizes 0/1/3/6, each running eight cycles on the original level-10 map.
Every operation compares the complete level, both 62-byte actors, scratch mob,
bank/count/raw tail/guards, object bytes/count/padding/guards, fourteen heights
and widths, screen cell, cell cache/requests, pending cue and ordered events.

Another 7,680 checks compare the persistent physics state of each drawing mode
against its no-drawing counterpart after the same update. They all agree.
This is a drawing-frequency invariance check within the supplied traces, not
an additional set of independent native rule recoveries.

The original code produces 12,961 object appends in this corpus. The temporary
X/Y/type, width and height changes do not leak into the next physics update.
Visible presentation preserves the established dimension rule: both heights6/7
become the saved initial height7. Queue bytes beyond the written records remain
intact, including across count resets. Compaction also retains the original
bank's unused tail bytes rather than clearing them.

At the end of each actual-anchor mode, eight anchors retain a terminal control100
record, three retain control0, and level12 room10/cell0 has an empty bank after
its rock crosses an absent left link. Terminal/stopped records can still produce
presentation objects; zero motion alone does not suppress drawing. These
outcomes agree with the earlier update-only traces.

## Verification

```powershell
python -m tools.probe_temple_slide_rock_lifecycle --source PATH_TO_RECOVERY --output rendered/temple-slide-rock-lifecycle.json
python -m unittest -q tests.test_temple_slide_rock_lifecycle_reference tests.test_temple_slide_rock_update_reference tests.test_temple_slide_rock_presentation_reference
```

39 asset-free tests pass, including ten new lifecycle tests. They pin repeated
draw behavior, the next movement after drawing, shared queues/dimensions,
compaction tails, wall finalization, invisible and empty-bank behavior, trigger
reuse and unsupported fixture rejection.

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Outputs SHA256:
`5ce9230a54ef4de4522d447f6135c53d61f773b62637efd9d7669165ec9c6463`.
The ignored report records level hashes, all trace snapshots and event counts.

## Supplied Boundaries And Remaining Work

- Audio requests are recorded, and PrinceSndOn193 is false. Real sound state
  and playback timing are excluded.
- Visibility5:3960 is a supplied boolean. Redraw sink5:19f8 records requests;
  it does not mutate the real dirty-region list.
- SectRect and the OffsetRect trap use the same documented rectangle arithmetic
  and Pascal cleanup as the independent presentation probe.
- Actor reactions5:3cee,6:1a84,10:1b04 retain the update probe's marker endpoints.
  None is reached in this corpus. The separate contact probe remains the evidence
  for the bounded native reaction body; these traces do not add damage/death proof.
- Caller admission, exact update/presentation ordering, arbitrary mixed-type
  banks, real room visibility, SHAP selection/raster pixels, file saves,
  checkpoints, restarts and whole-level traversal remain outside this result.

The next bounded question is how TriggerObject admits tile25 and translates
its caller's activation mode into TriggerSlideRock's how word.
