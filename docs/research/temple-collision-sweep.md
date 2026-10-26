# Temple collision row sweep

The original4:536a sweep now builds ten-word room-tag and overlap-mask
arrays with actual ReadCell, GetBarrCode and span helpers4:541a/547c.
The row, first/last columns, collision edges/height, bars flag and initial
output arrays are still supplied. No temple gameplay is enabled.

The first anchor is229+51*first. Each requested column performs a left
and right cell query, then tests the span against the actor's opposite
edges. Left strictly below body-right contributes0x0f; right strictly
above body-left contributes0xf0. Equality does not count. Barrier-free
cells use original sentinels left921/right0, not an unconditional zero mask.
The anchor advances51 after each processed cell, including the final one.

The output index and room tag come from ReadCell's **normalized** column/
room. Neighbor requests can therefore write a different slot than the
requested column, and a later request can overwrite that same slot. Slots
not visited retain their prior values. An empty interval still initializes
the anchor but performs no reads or table clearing.

This is raw span construction. An open gate retains the same type1 span;
later admission checks its position/body clearance. The sweep itself does
not apply CheckCollide's serpent exception or decide damage/solid passage.
Crevice collision height and the explicit bars query flag affect classification.

## Evidence

`tools/probe_temple_collision_sweep.py` compares34,880 original calls,
zero mismatches:29,280 row/span/body fixtures over declared rooms of levels
10-13 and5,600 kind/foreground/strict-boundary/signed controls. The tested
span/table domain is first/last-2..11 and row-1..3, with real room traversal.
Controls include all50 tile kinds, short/tall bodies and both bars flags.
They are not additional admitted gameplay content or reachable poses.

Complete A5 comparison permits only output arrays, anchor, cell cache and
room-base pointers. Actor, saved actor, TROBs and level bytes are unchanged;
ordered cell requests agree. No native endpoint is supplied. Reported mask
values include untouched synthetic high-bit canaries, not extra overlap bits
invented by the sweep. Nine asset-free regressions pin strict comparisons,
sentinels, gate admission separation, normalized indexing/overwrite, empty
intervals, source-height classification and untouched columns.

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_collision_sweep --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_collision_sweep_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_collision_sweep_reference
```

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Compared-output SHA256:
`708c5a1a4ecb9acab2528d2c134fe2ef5c28eca9703b89831a968d5b806ab112`.
Original bytes/reports remain ignored locally. Next compose actual CheckBarr
history/min/max generation and three sweeps; its dynamic sliding-rock
overlay and incoming-collision selection are separate caller stages.
