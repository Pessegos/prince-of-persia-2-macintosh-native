# An open temple gate reappeared during the climb

The user's paired Macintosh/port recordings of level 12, native room 3
(port room 2), show fragments of the closed gate near the Prince's head
as he climbs onto the middle platform. The original recording has no such
fragments. An offscreen port replay reproduces the artifact at the gate in
cell 18, without moving a live game window or changing user saves.

## Cause and correction

The imported pressure bindings identify the movable gate's **back** drawing
slot. The main room image used its current pressure phase, but DrawFloorBuf
and DrawHalf repeat that same gate in a **front** drawing slot. That slot
was not bound, so those actor repaints retained the initially closed gate.
The approved ledge masking also uses these floor records, exposing their
stale gate pixels below the floor's support line.

Apply the gate's existing pressure binding to its front slot too. Keep its
library, drawing column and row in the key: a same-numbered shape in another
slot must not move. Temple SHAP 3576 also needs the native row-top limit
`row*120-19`, rather than the generic cavern fallback `row*120-31`.
Both the full room and actor repaint now use that limit. No asset reimport,
animation, collision, motion, timing, save or approved ledge-policy change.

## Original evidence and limits

DrawHalf `CODE 3:3480` and DrawFloorBuf `3:371c` reach
DrawTempGateMovable `10:0976-0a44`, which admits drawing passes 5 and 2.
At `10:09ac-09b8` it sets the row limit to `row*120-19`; at
`09d8-09f0` it reads the live foreground byte and clamps its half-height
to 92. The port already quantizes gate presentation into quarter phases;
this correction retains that policy.

For room 3 cell 18, supplied foreground positions 0/92/184 yield native
gate bottoms 235/189/143 and command tops 109/101/101. Both floor and
pose-141 repaint commands follow the same current position. The previous
front slot remained at bottom 235 regardless of the opening.

`tools.probe_gate_repaint_height` executes the original drawers through the
existing command-capture exporter. It compares all 41 own-room temple gates
with front repaint commands across levels 10–13, positions 0/4/92/180/184/255,
and every exported climb pose containing that gate. There are 294 command
comparisons with zero differences, after normalizing clips to the viewport.
Native LEVL environment/level/foreground and imported SHAP headers are checked;
original executable and resource hashes are recorded in the local report.

The exporter supplies per-cell traversal and dirty rectangles, resource
handles, rectangle services, shape-header lookup and recorded draw endpoints;
dirty bookkeeping is inert. This is not independent SHAP decoding,
QuickDraw rasterization, real native actor admission, visible-neighbor
repaint coverage or a complete FrameAdv proof.

## Regression and visual verification

`tests.test_gate_repaint` checks exact closed/partial/open front commands,
unrelated slot/library controls, actual room-3 floor and pose-141 repaint
pixels, and a real-input descent/climb round trip with a supplied open gate.
The scene regression compares every climb pose 135–148 against an independent
drawing control that omits only that gate's front repaint; the gate's visible
main image remains. The complete sequence state stays unchanged by drawing.

Fourteen old/fixed climb images were captured locally. Only poses 140–144
change in this replay: stale gate fragments disappear while the pillar,
platform and Prince remain. Enlarged crops were visually checked against
the user's clips. Video compression/scaling and the intentionally improved
ledge mask preclude a native pixel-parity claim.

Restoring the previous pressure renderer makes the new tests fail in four
cases/subcases without errors, including the full-scene pixel control.
The final focused drawing/gate/ledge run passes 167 tests without skips.
Dependency, Ruff (`F,E9`), recovery-catalogue and whitespace checks pass.
Full discovery and exclusive-desktop tests were not run for this drawing-only
change.

```powershell
$env:POP2_SHARED_DESKTOP = '1'
.venv\Scripts\python.exe -m unittest -q tests.test_gate_repaint tests.test_ledge_occlusion tests.test_caverns tests.test_gate_scenery tests.test_stone_gates tests.test_neighbor_scenery tests.test_temple_candles tests.test_temple_arrival tests.test_throne_gates tests.test_final_scenery
.venv\Scripts\python.exe -m tools.probe_gate_repaint_height --source ..\PoP2-Mac-Code-Recovery --output rendered\gate-climb\native-repaint.json
```

Remaining scope: native dirty admission and actor/pixel composition for
moving gates at arbitrary positions and visible linked-room projections.
