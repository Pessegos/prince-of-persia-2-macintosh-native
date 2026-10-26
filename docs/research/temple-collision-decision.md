# Temple collision candidate selection

Original CheckCollide1 at4:54da now runs with actual ReadCell, tile
admission predicates, room adjustment and barrier spans, both alone and
after the native CheckBarr banks. The response boundary Collide4:5738 is
recorded and returns without effects. This recovers the decision and its
signed correction argument, not the physical/animation response or gameplay.

Modes2/6 and unsigned poses135..144 skip the decision. The low-side index
has priority. If it exists but facing or admission rejects it, this call
does not try the high-side index. An unarmed actor accepts only its front
side; the precise armed value1 enables the rear side too.

The selected current-bank room tag supplies ReadCell's room. Physical row
is folded once into0..2. Gate admission uses visible actor height; crevices
use the supplied collision height, actor kind and low two phase bits.
Scythes require a tall body and active low-five-bit phase3..15, excluding
kinds1/7/8/11. Kind10 tiles reject; serpent actor11 rejects even when the
ordinary tile predicate would block. Successful admission writes the
adjusted anchor and queries the normalized cell again for raw span geometry.

With synthetic incoming indices, even a floor can reach this geometry;
that is a controlled decision fixture, not evidence that normal banks
produce collisions against clear floor. Empty-rock fallback is executed
only when the span edge reaches its original sentinel.

## Evidence

`tools/probe_temple_collision_decision.py` compares41,264 calls with zero
mismatches:32,000 tile/phase/kind/height/facing/armed/index controls,480
mode/pose/row controls and8,784 compositions over all122 declared rooms
of levels10-13. The compositions execute actual4:4e34 first, including
history, generated column intervals and three sweeps; indices are not
supplied to the subsequent decision. Initial actor/body/history remain
fixtures and the MOB bank is explicitly empty.

Whole A5 comparison verifies bank/metadata/cache/anchor changes and guards
the actor, saved actor, TROBs and unrelated globals. Ordered cell/rock
queries and Collide arguments agree. Level and MOB guard memory remain
unchanged. The sole supplied endpoint is the no-op Collide response; no
admission, geometry, history or sweep endpoint is stubbed. Twelve asset-free
tests pin priority/no retry, armed value, unsigned exclusions, admission,
serpent/scythe rules, tagged-room lookup, row folding, room slots and rocks.

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_collision_decision --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_collision_decision_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_collision_decision_reference
```

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Compared-output SHA256:
`a9bc0d229512bca8a86b5f8bb3f633475fdcc74561f7a4c2eb46cc6262a1df39`.
Reports/resources stay local and ignored. Collide/GroundBump/airborne
responses, nonempty sliding rocks, floating ceiling checks, ShapeBounds,
animation/frame refresh and complete FrameAdv remain separate boundaries.
