# Temple ground bump through animation and frame refresh

Original GroundBump4:5868 now runs through real JumpSeq, AnimChar and
LoadFrame/supporting-column computation. The probe uses original Kid FRAM
and both separately prepared AFRM bindings; it does not replace animation
or frame reload with a supplied final pose.

First the actor moves ten pixels backwards relative to facing. Mode4 clears
horizontal velocity and skips sequence selection/animation. Other modes
request SEQS45 and advance one pose. Its initial slice selects mode5,
adds5 to Y and reaches pose102. Opcode-10 is not a sound request: with
floating timer0 it only consumes its operand; while floating it links the
active clip to229. The selected source stays45, and the pose cursor then
belongs to229. A failed JumpSeq45 lookup still animates the old prepared
SEQS2 from its old cursor.

The type0 change mark becomes1, then LoadFrame refreshes the metadata and
supporting column after movement/animation. Health, native ALIVE, vertical
velocity and visible rectangle are not recomputed by this routine. Body
bounds and collision admission belong to later composition.

## Evidence

`tools/probe_temple_ground_bump.py` compares45,056 original calls with zero
mismatches:all352 incoming poses, both facings, modes0/4, signed/visible X
controls, present/missing SEQS45, float timer0/1 and AFRM25001/25201.
Those are prepared states, not physically reachable pose assertions.

Whole A5 comparison permits only predicted actor/metadata/remainder/mark
writes. Saved actor, cache, TROBs, level and unrelated fields are guarded.
Original sequence/frame bytes and prepared handles are verified unchanged.
Resource Manager/hGetSequence and Memory Manager HGetState/HLock/HSetState
are supplied explicitly. No audio endpoint is invoked in the tested slice.
Eight asset-free tests distinguish mode4, failed selection, floating links,
source versus active clip, frame ordering, signed X and preserved health.

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_ground_bump --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_ground_bump_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_ground_bump_reference
```

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Compared-output SHA256:
`b167275333a48360c4b4f4c56a50f007403e9fc12885b1f9d2853dd27e5d4118`.
Reports/resources remain ignored locally. Collide's tile/ground admission,
airborne responses, ShapeBounds, rendering, resource-selection policy and
complete FrameAdv remain separate boundaries. Temple gameplay is not enabled.
