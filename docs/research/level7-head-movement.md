# Head Movement Admission

Research only; no runtime change. `R` means recovered/reference, not playable.

| Rule | Source | Status |
| --- | --- | --- |
| Four-way movement admission | 7:0936-0b02 | R: in-room tested columns/rows, actual level-seven cells |
| Horizontal rejection during vertical overshoot | 7:170a-1766 | R: sequences 143/144, strict inequalities |
| Inclusive X middle-of-cell window | 7:1768-17ae; 19:4bd0-4c4c | R: original signed remainder helper executes |
| Head gate clearance | 4:5b0e-5ba8 | R: ruins environment, supplied body bounds, both variants |

## Reproduction And Evidence

```powershell
python -m tools.probe_level7_head_movement --source PATH_TO_RECOVERY --output rendered/level7-native-head-movement.json
python -m unittest -q tests.test_level7_head_movement_reference
```

Original executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
The level is original Prince LEVL 2006, as inventoried in
[level-seven preparation](level7-preparation.md). The ignored report records
the output digest. No service/collision/geometry helper is stubbed.

All 43,160 native comparisons pass:

- 36,864 movement queries across all 32 rooms, rows 0..2, columns 1..8,
  both head types/facings, X offsets -13/0/+13 and directions 0..3.
- 2,592 additional sequence-143/144 Y-overshoot queries around the exact
  row-floor height in rooms 1/3/7/20/28/32.
- 396 direct gate queries with supplied foreground values/body heights.
- 3,303 direct X-middle queries, X=-100..1000 and tolerance 0/12/25.
- Five early-rejection controls: invalid direction or exceeded horizontal limit.

Movement queries compare return values, all 62 unchanged working bytes and
unchanged full level bytes. Scratch cell/remainder fields may change natively;
they are not part of the unchanged working structure assertion. Direct gate
and middle controls compare predicate results. Seven asset-free unit tests
cover the reference only, not independent original execution.

## Recovered Rules

Direction numbers are the controller's numeric inputs, not port input keys.
The helper decides whether movement may begin; it does not move the actor.

For directions 0/1, reject column <-1 / >10 respectively. Also reject either
of these vertical overshoots relative to `row * 120 + 73`:

- Selected 144 with working Y strictly greater than the row-floor value.
- Selected 143 with working Y strictly less than that value.

Otherwise, probe `AddCharX(26)` and convert that point through the original
GetCharCol. If it differs from the cached column, direction 0 tests column-1
and direction 1 tests column+1. A tile classified by native IsWall as
2/7/20/25/43 rejects movement, as does a type-4 gate with insufficient clearance.

Direction 1 additionally checks a gate in the CURRENT cell, even when the
26-pixel probe remains within that cell. Direction 0 has no matching current
gate check. Do not replace this asymmetry with a generic neighbor-wall test.

For direction 2, reject row 2, then require X within the middle window and
native IsSpace true for the current cell. Direction 3 rejects row 0 and
requires the same X window plus IsSpace true for the cell above. Native
IsSpace IDs here are 0/9/27/47/49, not simply every non-wall tile.

The X window is inclusive: signed remainder of `(native_x - 229) / 51`
must lie between `25 - tolerance` and `25 + tolerance`. Admission uses
tolerance 12. The original signed-remainder helper executes, not Python's
negative modulo semantics.

### Gate Variant Difference

In the ruins environment, derive body height from the supplied working
bottom-top words and add 46 for actor 7 or 33 for actor 8. The gate blocks if
`2 * ((foreground & 255) >> 2) + 11 < adjusted_height + 13`.
High foreground bits do not participate in this comparison. Equality admits
the move; it is not a blocking threshold. The two variants therefore cannot
share a single unqualified gate-clearance constant.

### Symbol Navigation Correction

The disassembly's `XWithinMiddleOfCell` name sits above 7:170a, but that
routine is the vertical-overshoot predicate. The actual X-middle helper
called by admission is 7:1768. Follow instructions/call sites rather than
treating that recovered name placement as proof of the body's behavior.

## Limits And Next Step

Body top/bottom, cached column, facing, position and selected sequence are
supplied. Bounds are not computed from drawn sprites. Poses/motion sequences
are not animated. The query matrix is deliberately broad and does not assert
that every combination is reachable in play. Column 0/9 room-boundary reads,
missing-neighbor fallback, offscreen movement and full collision remain open.

This can now support a native idle-choice probe with actual movement
admission, supplying only explicit random outcomes and resource-existence
decisions. Complete RNG seed evolution, animation timing and controller
cadence would remain separate obligations.
