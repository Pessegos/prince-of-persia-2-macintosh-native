# Unarmed airborne collision response

Original4:589e now executes its unarmed type0 branch through real31fa
alignment, AddCharX, JumpSeq, AnimChar and Kid LoadFrame. This is an isolated
response leaf with supplied incoming actor/admission, not a completed Collide
or playable-temple implementation. The armed path remains outside this module.

## Recovered decisions

- At least30 pixels above row*120+106 redirects to the previously recovered
  GroundBump before air alignment. Equality selects GroundBump.
- Otherwise31fa aligns Y to row*120+106. Its33-pixel adjustment tests actor
  types7/8 at+8, not movement modes7/8 at+16; it never applies to this type0 probe.
- Signed vertical velocity>=50 moves17 pixels backward relative to facing
  and reloads the existing frame, preserving velocity, pose and change mark.
  This occurs before checking native ALIVE, even if ALIVE is0.
- Below50, vertical velocity becomes0. Native ALIVE0 returns after alignment
  without animation, frame reload or change mark. HP is a separate field.
- Poses246..261 inclusive move5 pixels backward, clear word+24 and set mode0
  before requesting SEQS121. They do not clear horizontal velocity. The real
  first slice then sets mode1 and pose251, so mode0 is not the final mode.
- Other poses need signed32-bit HP+pending-health>0. Poses24/25,40..42 and
  102..106 select SEQS46; other eligible poses select47. Their first slices
  produce different movement/poses:46 moves5 backward and7 upward to102;
  47 moves16 backward to50. Both set mode5.
- Missing requested resources retain and animate the old prepared SEQS2;
  explicit response writes, such as121's initial backoff/word+24 clear, remain.
  A selected animation reloads frame/supporting column and sets the type0 mark1.

Word+24 is named by offset here. The existing
[pending-cue research](death-counter-kill-song.md) distinguishes it from native
ALIVE; this module proves its clear in this branch, not a complete cue lifecycle.
Incoming poses excluded by the outer Collide caller can still appear in the
direct leaf corpus. No assertion of physical reachability is made for them.

## Evidence and boundaries

`tools/probe_temple_air_collision.py` compares9,648 original calls with zero
mismatches across all352 incoming Kid poses, both facings, signed velocity49/50
and negative controls, present/missing sequence resources, health/pose edges,
signed-X wrapping, ALIVE0, movement modes, row controls and the exact29/30/31
height boundary. Both original AFRM25001 and25201 bindings are tested separately.
Eleven asset-free regressions pin these distinctions.

Whole A5 output comparison guards actor, frame metadata, supporting-column
remainder, mark, saved actor, cell cache, TROBs and unrelated state. Original
level data, sequence/frame bytes and prepared handles remain unchanged. Ordered
animation/resource/frame events match. Resource Manager/hGetSequence and Memory
Manager HGetState/HLock/HSetState are explicit supplied endpoints. Native31fa,
relative movement, JumpSeq, AnimChar and Kid frame/column reload execute.

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_air_collision --source PATH_TO_RECOVERY --output rendered\temple_air_collision_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_air_collision_reference
```

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Compared-output SHA256:
`837b877a40117de55cf8036926ef0074f352cd2d65c27a70f40961cd06f52c74`.

Original resources and reports remain ignored locally. Armed4:591a-59b4,
post-response4:3982 spacing, real contact/body construction, nonempty rock
overlays, caller composition and repeated FrameAdv remain separate steps.
No production gameplay, artwork or README changed in this module.

The later [armed response](temple-armed-collision.md) separately recovers the
type0 armed branch with actual static-rock queries, strike predicate and clips.
It does not expand this unarmed probe's admission or full-frame coverage.
