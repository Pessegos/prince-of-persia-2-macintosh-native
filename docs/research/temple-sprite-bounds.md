# Temple Prince Drawing Setup And Collision Edges

Research only. Builds on [Kid frame metadata](temple-kid-frames.md), without
changing runtime, ruins, rendering or the user's uncommitted README preview.

Actual type0 LoadFrame4:2a72, SetupSword3:0ac8 and GetCharEdges4:5cbc execute,
including GetSwordLength4:5e6e, GetRow4:3afa and the original column division.
Prepared FRAM25001/AFRM25001 and Kid SHPL25001 shape indices are used.

- SetupSword chooses library2 and drawing point X +/- frame dx -207,
  Y+frame dy. Pose0 or two imageless shape sources leave the previous setup.
- Collision width is SHAP header width **plus one**. An armed value exactly1
  and nonzero attachment can extend it by max(0, attachment word2 -3).
  Facing determines the side of extension. Body top is capped at365.
- The visible rectangle uses the unextended image width, screen-relative X
  and a supplied screen intersection. It is not the collision rectangle.
- The visible rectangle is stored inside the working62-byte actor, offsets
  42..49. Each call first copies the default rectangle there, even when the
  sprite is absent or its dimension service fails. Other old edges/cells and
  the division remainder survive those early returns.
- Edge columns call5:48b0 **directly**, without GetCharCol's additional-22.
  Left column is lower-bounded0, right upper-bounded9. Bottom row-1 becomes3;
  top row is not given that special treatment. GetRow subtracts5 in a signed
  word and subtracts one again for nonpositive adjusted coordinates.

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_sprite_bounds --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_sprite_bounds_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_sprite_bounds_reference
```

**33,792 native/reference comparisons, zero mismatches:**352 original poses,
two facings, armed0/1, six X/Y pairs, successful/failed dimensions and two
prepared library-equality controls. Both17:673a and3:533a dimension call paths
are exercised, not their loader implementations. Ten asset-free regressions
bound drawing offsets, body/visible rectangles, sword extension, missing
images, preservation, row quirks, clipping and mutation scope.

Complete working/saved actor, frame metadata, drawing setup, seven collision
words, four edge-cell words, remainder, ordered dimension/intersection calls,
level/cache/TROB canaries and immutable resource/handle bytes are compared.
Default/screen rectangles are checked unchanged. No additional native service
is silently accepted by the instruction allowlist.

Supplied boundaries: prepared resource/library bindings; dimensions read
independently from original Kid SHAP headers (or controlled failure); a
Pascal SectRect callback with explicit half-open intersection and supplied
screen0,0,365,510; initial actor/drawing/edge fixtures. This does not execute
the Macintosh Resource Manager, shape decoder, QuickDraw or rasterization.
Only AFRM25001 is used. Synthetic extreme positions are not reachable states.

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Compared-output SHA256:
`ee3f9460d8fde28227293984d124e7dbe21ce0623941ec624fcce74ba16957cb`.
Original bytes and detailed reports remain ignored locally.

Next compose these real bounds with world/Prince/PlayerCtrl/rock queries;
support/contact physics, full FrameAdv and playable temple remain separate.
