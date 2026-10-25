# Temple Sliding-Rock Activation

Research only, original Macintosh executable SHA256
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
No runtime/importer/campaign changes are included.

## Evidence And Reproduction

```powershell
python -m tools.probe_temple_slide_rock_trigger --source PATH_TO_RECOVERY --output rendered/temple-slide-rock-trigger.json
python -m unittest -q tests.test_temple_slide_rock_trigger_reference
```

The probe executes the complete original TriggerSlideRock `10:2152-2246`,
GetSlideRockOnRoomRow `10:1a9e-1ae8`, GetMobTypeItem `5:293c-2994`, the
cell reader `5:4970-49a0`/`4:27ee`, and append `5:2914-293a`. The instruction
allow-list rejects undeclared paths; each call is bounded to 50,000
instructions and must return to its designated stop. No native services are
supplied in this probe: lookup, cell addressing and append run natively.

The caller is TriggerObject at `5:1fd2`. That call site's admission and the
meaning of its input values are not yet independently executed here. The
reference therefore calls the input `how`, not an assumed direction/open
boolean. Selected words and mob-bank fixtures are supplied controls, not
proof that all those states arise in ordinary play.

## Recovered Rules

The helper searches **room and row**, not the marker's exact cell or X.
It selects the first bank record whose type word at `+0xa` is 6, room at
`+4` matches, row at `+0xc` matches, and removal word at `+6` is not -1.
The search uses ordinal GetMobTypeItem calls, skipping other types and
records marked exactly -1. Other negative removal words are not excluded
by that native predicate.

For an existing matching record, only control word `+8` can change:

| Input | Existing Control Word | Result |
| --- | --- | --- |
| `how=1` | Nonnegative, except 100 | -2 |
| `how=1` | Negative or 100 | Unchanged |
| `how=2` | -2 | 2 |
| `how=2` | Any other word | Unchanged |
| Other `how` | Any word | Unchanged |

This does not establish movement speeds, delays or the complete meaning of
control value 100; those require the update controller.

If no record matches, only `how=1` constructs a new one. With the supplied
in-range marker cell, the eight words are:

| Offset | Value |
| --- | --- |
| `+0` | X = column * 51 |
| `+2` | Y = 116 + row * 120 |
| `+4` | Native room |
| `+6` | 0 |
| `+8` | -2 |
| `+0xa` | Type 6 |
| `+0xc` | Row |
| `+0xe` | Original X |

Append accepts a bank count below 30 and increments it. A full bank leaves
its records/count unchanged, but the constructor still overwrites the
scratch record. A deleted record still consumes physical bank capacity
until a separate compaction step. Activation does not mutate the level
cells, foreground, working character or request audio in the tested scope.

An integration must not create an independent actor for each tile-25
marker by default: successive triggers in one room/row reuse the first
matching live record. In particular, level 12 room 6 has three markers on
the same row. This is a consequence of the recovered lookup, not a claim
that every future controller or direct-construction path is covered.

## Validation

The preserved levels contain 12 tile-25 cells: two in level 10, two in 11,
six in 12 and two in 13. The ignored report records every location and
level hash. All those cells were tested with seven supplied `how` values
and 55 bank layouts each: **4,620 native/reference comparisons, zero
differences**.

Layouts include counts 0/1/29/30, eleven signed control words, removal
marks -2/-1/0/1, other types/rooms/rows, multiple matches, removed records,
30 nonmatching type-6 records and a match in the final slot. Outcomes:

- 3,192 existing-record selections, including unchanged states.
- 312 existing-record changes.
- 180 appended records.
- 24 full-capacity rejections after scratch initialization.

Each comparison covers all level bytes, the 62-byte working character,
bank count, all scratch words, and a 512-byte bank/canary region. The
output digest is
`89de74f15890a3ca586f27db5a73ced1efbcb912cf1df2cffeb814f2980be20b`.
Ten asset-free tests exercise the independent reference model; they do not
rerun the original executable or certify its fixture reachability.

## Exclusions And Next Work

The constructor also has an X>510/right-neighbor normalization branch at
`10:21f0-2208`. In-range cell arguments use original column-table values
0..459 and do not reach it. This branch is **not certified** by the probe;
do not silently remove it when integrating later.

This block does not recover actual TriggerObject admission, movement,
rendering, crush/collision geometry, whole FrameAdv timing, sound playback,
room-exit persistence, save/restart or level solvability. Banks are reset
between fixtures; no connected moving-rock lifecycle is claimed.

Next: decode the type-6 update target behind MakeRubble `5:29e8/2a94`,
separately from ATMLoose `5:307c/30c0` presentation and ATMSlideRock
`10:1456`. Trace native update state changes before importing assumptions
from the control word's sign or from presentation-only helpers.
