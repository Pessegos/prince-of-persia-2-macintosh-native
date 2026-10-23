# Temple Trap-Door Triggering

Research only, not a runtime implementation or full falling-platform model.
`R` denotes recovered/reference behavior in the stated scope.

| Rule | Source | Status |
| --- | --- | --- |
| Cached-state trigger admission | 10:25aa-25e6 | R: full native body with actual type26 cells and supplied actor columns |
| Remove floor and prepare moving object | 10:25e8-26d4 | R: full constructor; sound/redraw requests supplied |
| Append object up to capacity30 | 5:2914-293a | R: original append code, canary-guarded supplied bank |
| Advance phase, update/save/compact bank | 10:24fa;5:29e8 | R in the separate [advance probe](temple-trapdoor-advance.md) |
| Present/restore platform | 10:225c | R in the separate [presentation probe](temple-trapdoor-presentation.md), explicit services supplied |
| Actual pixels, collision, sound playback/full scheduling | Other callers/services | P: not certified by these probes |

## Reproduction And Evidence

```powershell
python -m tools.probe_temple_trapdoors --source PATH_TO_RECOVERY --output rendered/temple-native-trapdoors.json
python -m unittest -q tests.test_temple_trapdoor_reference
```

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
The ignored report includes all four level hashes and an output digest.

960 comparisons pass across the ten actual type26 cells in levels10-13.
Eight foreground controls, three relative actor columns and four supplied
mob counts0/1/29/30 are tested at each location. These include 360 bit-0x40
rejections, 450 successful appends and 150 full-bank rejections after level
mutation. The latter counts partition the 960 cases; they are not extra runs.

The checks compare full level bytes, all unchanged working actor bytes,
cached foreground, the complete 16-byte constructor scratch record, mob
count, the 30-record bank plus prefix/suffix canaries, and sound/redraw calls.
Seven asset-free reference tests are separate from native execution.

## Trigger And Cache Semantics

Original ReadCell/CalcBlue first establish cached room, row, column, cell
index, type/foreground and level-array pointers. This is NOT a supplied
collision result. TriggerTrapDoor itself does not recheck the tile kind;
the test invokes it only for actual type26 cells, with correct native caches.
Caller admission remains separate: known callers include Falling6:0210
and ShakeEm5:28c8.

If cached foreground has bit0x40, return without changing the level, mob
scratch/bank/count or issuing audio/redraw requests.

Otherwise, compare the actor's cached supporting column to the selected
cell's column. If different, set bit0x40 in cached foreground and temporarily
write it to the level foreground word. If equal, do not set that bit.
Both branches then invoke the same constructor with native room/cell.

The constructor sets the cell type to0 and writes foreground **0x81**.
It overwrites that level foreground word rather than preserving its old
high bits. The background word and all other level bytes remain unchanged.
Cached foreground is NOT overwritten with0x81: it retains the old word,
possibly OR0x40, and is still consumed by constructor logic.

This cache-vs-level difference matters. Do not make the constructor read
the newly written level word when deciding its initial object state.
The result is not proof that repeated direct calls with stale caches are
idempotent or that all host caller scheduling is understood.

## Prepared Object And Capacity

The 16-byte native moving-object record contains eight signed words:

| Offset | Value In This Constructor |
| --- | --- |
| +0 | column *51, without the actor's native +207 X origin |
| +2 | (row+1) *120 +5, from the original DATA Y table |
| +4 | native room |
| +6 | 0 |
| +8 | 0 |
| +0xa | object type10 |
| +0xc | row |
| +0xe | 75 if cached bit0x40 is set; otherwise1 |

The last field is an INITIAL animation-state value, not a delay in
milliseconds or game ticks. The [advance probe](temple-trapdoor-advance.md)
now establishes low-five-bit phases1/11, reaching17 after16/6 helper calls.
Presentation/restoration and full-frame scheduling remain separate.

The original append helper copies the scratch object and increments the
count only when count<30. Count29 uses the last slot; count30 does not append
or write beyond the bank. However, floor removal and scratch creation have
ALREADY happened, and sound/redraw requests still occur when the bank is full.
This is an observed native branch, not an instruction to remove the port's
capacity safeguards or reproduce a lost-animation failure silently.

## Supplied Endpoints And Next Work

- AddSound5:4d84 records cue197 without playing it.
- MarkMobRedraw5:33fa records argument0 without changing redraw state.
- The mob-bank pointer/count and canary-filled existing entries are supplied;
  their live scheduler provenance is not claimed. Native append code executes.
- Foreground and actor column controls are supplied independently and are
  not all certified reachable in live play.

This initial constructor probe does not certify animation update, actual
sound/pixels/redraw lifecycle, character collision/crush, full-frame ordering,
save/restart or campaign integration. Subsequent [advance](temple-trapdoor-advance.md),
[presentation](temple-trapdoor-presentation.md) and [connected lifecycle](temple-trapdoor-lifecycle.md)
probes establish their documented subsets without removing the broader gaps.
Sliding-rock mechanics remain a distinct next track.
