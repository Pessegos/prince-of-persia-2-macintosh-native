# Temple Collide branches leading to GroundBump

Original Collide4:5738 now executes its bounded branches into GroundBump,
including actual tile traversal, IsWall/IsSpace, empty sliding-rock queries,
JumpSeq/AnimChar and Kid LoadFrame. The signed correction and current-cell
cache remain inputs. This is not a complete collision/airborne implementation
or a proof that every supplied correction was physically admitted.

Native ALIVE>=0 or poses242/243 return without applying the correction.
Otherwise the signed-word correction is added directly to X, independently
of facing. The subsequent ten-pixel bump offset is relative to facing.
For wall kinds2/7/20/25, the routine inspects the adjacent cell on the
supplied collision side; selected source75 uses a two-cell stride instead
of one. Source and active animation sequence are distinct inputs.

The branch after IsSpace must not be inferred from the name GroundBump.
If IsSpace is true, the temple tests sliding-rock intersection; the actual
empty-bank result0 selects GroundBump. If IsSpace is false, it enters4:589e.
An unarmed actor at least30 pixels above row*120+106 then also selects
GroundBump. Other airborne responses remain outside this block. A target
still classified as wall reaches a separate post-response spacing helper;
those states are excluded explicitly before native execution.

## Evidence

`tools/probe_temple_ground_collision.py` compares8,848 original calls with
zero mismatches:8,608 admitted prepared barrier states across declared
temple rooms and240 ALIVE/pose/source/side/signed-correction controls.
All41 ordinary gate anchors are included. The scope filter excludes33,248
raw combinations requiring post-bump wall spacing; these are not passes
or a count of reachable gameplay situations. Remaining airborne admission
is a named boundary in the reference, not a guessed final state.

The caller's actual empty-MOB services10:2036/180e/1a9e and5:293c execute
without geometry stubs. Complete A5 comparison verifies actor, metadata,
remainder, mark and cell-cache/pointer effects, while guarding saved actor,
TROBs and unrelated state. Level, MOB and sequence/frame resources remain
unchanged. Ordered cell queries, rock queries and animation events agree.
Resource/Memory Manager services and prepared FRAM/AFRM25001/sequence
handles are the same explicit boundaries as the ground-bump leaf probe.

Ten asset-free tests reject inversion of the IsSpace branch, pin the exact
30-pixel condition and armed exclusion, and distinguish correction/backoff,
ALIVE versus HP, source75, signed wrapping and active/source clip state.
The native corpus fixes the non-space fixture at the30-pixel boundary;
the adjacent29-pixel exclusion is also read directly at4:58d2-58d8.

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_ground_collision --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_ground_collision_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_ground_collision_reference
```

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Compared-output SHA256:
`51e388a90e95c97ecc15c81c8ffec05076759764f92897853c4fbd114321cb95`.
Reports and original resources remain ignored locally. Nonempty rocks,
undefined-room correction, other airborne responses, post-bump wall spacing,
ShapeBounds, CheckCollide1/CheckBarr composition and FrameAdv remain separate
steps. This research does not enable temple gameplay or change production.

The subsequent [unarmed airborne leaf](temple-air-collision.md) recovers the
unarmed remainder of4:589e separately. It does not change this probe's bounded
caller coverage or remove its armed/post-response-spacing exclusions.

Later [armed reactions](temple-armed-collision.md) and
[post-response spacing](temple-wall-spacing.md) recover those helpers separately.
This grounded caller probe retains its exclusions until a composed native
caller comparison replaces them; leaf results do not enlarge its corpus.
