# Temple gate face and back distances

The prior contact probe supplied4:5eae's final distance. This block recovers
the lower-level geometric services4:6562 and4:6610 with real gate admission,
barrier classification4:52bc and AdjustRoom4:56e6. It does **not** yet replace
the complete4:5eae selector or make the temple playable.

For environment2's ordinary gate, DATA's cell anchor is229+51*column;
barrier1 adds40 at one side and50 at the other. A native left-facing actor's
face distance is body-left minus(anchor+50); right-facing is(anchor+40)
minus body-right. The back service exchanges the two sides. Negative values
are meaningful; they are not clamped to zero. Arithmetic stores signed words.

The face service first executes4:5b0e. If the visible body can pass, it
returns-1 without changing the old anchor at A5-35fc. The back service has
no matching admission short circuit: it still computes the ordinary gate
distance and writes the anchor. Kind1 and selected source68 are included
in that asymmetry. Foreground high bits do not substitute for gate position.

AdjustRoom compares the requested room with the displayed room first.
Three supplied left-neighbor slots shift the anchor by-510; three right
slots shift it by+510. Left wins if a malformed/control fixture lists the
same room on both sides. An unrelated room keeps its unshifted coordinate.
This probe supplies the room slots and does not certify InitRoom's creation
of them or independently assert every slot's topological meaning.

## Evidence

`tools/probe_temple_gate_distance.py` executes79,104 comparisons with zero
mismatches:78,720 at all41 actual temple gate anchors and384 controls for
neighbor precedence, signed edges and room adjustment. Both facings, face/
back, visible heights34/74, kinds0/1/4, sources9/68 and eight foreground
values are crossed with body positions around the gate. These prepared
rectangles are not claimed reachable sprite trajectories.

The full A5 data bank is compared, permitting only the independently
predicted anchor write. Working/saved actor, cache, TROBs, level bytes and
other fields remain unchanged. No native endpoint is supplied or stubbed;
the actor, collision edges, room slots and level are input fixtures. The
independent model does not use the gameplay terrain implementation.
Ten asset-free tests pin the geometric sides, signed wrapping, admission
asymmetry, kind/source exceptions and room priorities.

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_gate_distance --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_gate_distance_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_gate_distance_reference
```

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Compared-output SHA256:
`bccefb575e62d378cbb717744c1558eadc60a9646938e44efe57748d037973b6`.
Original bytes and detailed reports remain ignored locally.

Next: use these real distances in4:6202 gate ejection and the hard branch
of4:60e4. General4:5eae can also inspect the forward cell/floor/lava and has
separate distance-kind/remainder effects; it must not be replaced by a
single face-distance call. Collision-bank construction, actual body setup,
floor/support, damage/death and repeated-world integration remain open.
