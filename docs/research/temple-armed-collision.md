# Armed airborne collision response

The isolated type0 armed branch of4:589e now executes with real alignment,
GetSlideRockX5:21f6/TempGetSlideRockX10:20fe, static-bank edge lookup,
IsStrikingPos6:5d60, relative movement, JumpSeq, AnimChar and Kid frame reload.
This is a response leaf, not physical contact admission or a playable level.

- Armed1 bypasses the unarmed30-pixel GroundBump redirect. Alignment happens
  before the signed vertical-speed50 threshold. Fast falls back off17 and reload
  even with ALIVE0; slower ALIVE0 actors merely align and clear vertical speed.
- A matching collision side/facing moves6 relative pixels and selects65. Active
  sequence55 plus pose207 adds17 before that move; source+40 is not this check.
- Opposite side selects64. Prince strike poses153/154/244/245 move25 before
  the first slice unless cached tile4 has low-byte position strictly greater
  than60. Such an open gate suppresses this reaction, animation and mark.
- The first live type6 MOB matching room/row wins. The native right-edge query
  can select its left edge when the Prince is to its left, with real raw-level
  clipping and supplied frame width. This service is active only in environment2.
- After the relative reaction move, X strictly below a nonzero rock edge
  overrides even gate suppression: select93 and clear armed. Equality does not.
- Reaction64's first slice moves10 backward to pose157/mode5, keeps the contact
  mark and requests sound10 unless the resulting selected source is56.
  Reaction65 yields160/mode5 and mark1. Reaction93 moves10 backward to234/mode1,
  with mark1. HP/pending-health do not replace the native ALIVE check here.
- Missing requested resources animate the prepared old sequence. Explicit
  relative moves and disarming survive lookup failure. Sound suppression uses
  source after selection, so failed lookup can preserve source56.

The bounded probe compares12,456 native calls with zero mismatches: all352
incoming Kid poses, both facings/sides, resource availability and velocity49/50;
strike/gate low-byte boundaries, active/source separation, ALIVE/health controls,
static rock filtering/first-record selection and environment2/3. Additional
raw-level tile1/4/20 and width0/40 controls exercise native left-edge clipping,
including X380 where clipping changes reaction65 into disarming93. Both original
Kid AFRM25001 and25201 bindings are separate. Twelve asset-free regressions pin
the rules. Direct pose fixtures do not establish physical reachability.

Whole A5 output, ordered query/animation/audio-request events, original level,
static MOB storage and sequence/frame resources are checked. Supplied endpoints
are Resource Manager/sequence handles, HGetState/HLock/HSetState and5:4d84 sound
playback (recorded request only). Incoming actor/side, cached tile, static MOB
bank and frame width are fixtures. Real rock movement, audio mixing, ShapeBounds,
outer Collide/CheckCollide1 composition and full FrameAdv remain excluded.

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_armed_collision --source PATH_TO_RECOVERY --output rendered\temple_armed_collision_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_armed_collision_reference
```

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Compared-output SHA256:
`e8ebb6cd71e447dea64e121af74054ef4d72c7cfc948d2dca1a4cadbe290d413`.
Reports and original bytes stay ignored locally. No runtime, art or README edits.
