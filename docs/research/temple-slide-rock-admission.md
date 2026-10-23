# Temple Sliding-Rock Caller Admission

Research only. Original CODE offsets include the resource header. The tool
executes the tile25/default branches of TriggerObject and the supported link/
held-plate callers with no supplied native service endpoints.

## Caller Mode Translation

TriggerObject starts at5:1ec8, with tile25 handled at5:1fba-1fda. Its arguments
are `(tile kind, native room, cell, caller mode)`.

| Caller Mode | TriggerSlideRock How | Consequence |
| --- | --- | --- |
| Exactly5 | 2 | Existing control-2 becomes2; no missing rock is created |
| Other tested signed words | 1 | Missing record may be created; existing nonnegative control except100 becomes-2 |

The mapping is an equality test against5, not a generic open/close flag.
As established by the motion probe, control-2 advances without the filled-band
stop test; control2 uses the geometry-dependent path. Neither reverses the
direction of motion. Terminal control100 remains terminal in both modes.

This branch does not consult the source plate's depressed bit. Direct calls
with supplied cache foreground0/0x2000 produce identical activation behavior.
Missing/full banks and existing records retain TriggerSlideRock's previously
verified capacity, room/row lookup and first-live-match rules.

TriggerObject returns-1 even when a rock is successfully created or changed.
This tells Trigger5:1c4c to skip AddTrob at5:1cb0-1cbe. It does **not** stop
traversing the link chain: the next-link lookup still executes at5:1cc0.
The rock has its separate MOB bank entry. Default/unhandled tile kinds also
return-1, without invoking the rock constructor.

## Original Resource Chains

The raw temple resources contain eight plate chains that include a tile25.
Rooms are native one-based numbers; cells and link indices are zero-based.

| Level | Plate Room:Cell / Kind | Link Path | Coverage |
| --- | --- | --- | --- |
| 10 | 28:24 /6 | 61 -> rock28:29 | Native chain and held plate |
| 11 | 3:15 /6 | 54 -> gate3:2;50 -> rock3:18 | Inventory; mixed gate body excluded |
| 11 | 3:16 /5 | 51 -> rock3:18;52 -> gate3:2 | Inventory; mixed gate body excluded |
| 11 | 29:4 /6 | 76 -> rock29:9 | Native chain and held plate |
| 12 | 1:21 /6 | 148 -> rock1:23 | Native chain and held plate |
| 12 | 29:4 /6 | 76 -> rock29:9 | Raw chain only; source reads as wall |
| 13 | 5:18 /6 | 186 -> rock5:19 | Native chain and held plate |
| 13 | 16:17 /6 | 171 -> rock16:19 | Native chain and held plate |

Level12's header atLEVL+2180 declares26 rooms. Although the raw room29 bytes
contain plate6 and marker25, original ReadCell returns tile20 for that plate.
The higher-level pressure path therefore cannot use it as an ordinary plate
under this header. Calling Trigger directly with link76 can still traverse the
raw record: Trigger obtains the target type from CalcBlue's raw room pointer.
Do not interpret that forced call as proof of gameplay accessibility.

Earlier reports' twelve "actual anchors" mean twelve original resource markers,
including this room29 marker; they are not twelve certified playable mechanisms.
Link reachability, header-valid room admission and actor traversability remain
different checks. The tool records the excluded raw source instead of changing
its room count or substituting a live plate fixture.

## Held And Permanent Plates

The complete PushPlate5:240c-251e runs with arguments `(0,-1)`, reading the source
kind/link from a preceding native ReadCell. The bounded corpus starts with timer
2,5 or31 and repeats each press three times without resetting bank or level.
Ordinary held timers become5; permanent31 remains31. Each press still calls
Trigger. Source foreground gains0x2000 after traversal, even when the target's
constructor changes the global cell cache to a different cell.

The five admitted rock-only sources are tested with empty, forced, conditional,
terminal and full banks, both supplied initial depression states, and all three
timer values. No timer below2 is used: that separate fresh-press branch also
needs plate TROB creation, audio and redraw setup.

A supplied three-target chain uses two different rows and repeats its first
target. Native traversal creates two records, reuses the first on repetition,
and continues after each return-1. Mode5 creates none when that bank is empty.

## Verification And Boundaries

```powershell
python -m tools.probe_temple_slide_rock_admission --source PATH_TO_RECOVERY --output rendered/temple-slide-rock-admission.json
python -m unittest -q tests.test_temple_slide_rock_admission_reference tests.test_temple_slide_rock_trigger_reference
```

8,609 native/reference comparisons pass:

| Corpus | Comparisons |
| --- | ---: |
| Twelve resource anchors,55 bank fixtures,six modes,two cache flags | 7,920 |
| Source-plate ReadCell queries | 8 |
| Six raw rock-only link chains | 180 |
| Repeated held/permanent calls on five admitted sources | 450 |
| Default/unhandled kind controls | 48 |
| Supplied multi-target chains | 3 |

Checks cover entire level bytes, raw MOB bank/count/tail/guards, scratch,
both actors, cell cache/requests, ordered TriggerObject/TriggerSlideRock
arguments, pending audio cue and TROB count. None of these paths calls a
supplied native service. Uncovered active-mechanism bodies fail explicitly.
23 focused synthetic tests pass, including thirteen new caller tests.

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Outputs SHA256:
`4eb956bfd8e847a2217af2bf6f360ce698e69c058cfdee0a03fda7d63eb46f8d`.

The two mixed gate/rock chains, fresh timer<2 plate setup, actor foot/contact
admission, constructor X>510, moving/contact/drawing cadence, file saves,
checkpoints and restarts remain open. This does not verify complete FrameAdv
or enable temple gameplay. Production pressure and rendering modules are unchanged.
