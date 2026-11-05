# Throne grille foreground and sword-draw playtest

The supplied Macintosh and port recordings show the throne reached from
native room21 on the right. This is port room index8, native room9, in
level8. The first report concerns the Prince painting over the closed grille
in either facing. Original resources and all approved artwork remain intact.

## Native foreground promotion

DrawRuinGateMovable7:2b22-2b4a uses a special throne path when the displayed
room is native9 and the level is8. For the front BF pass2 it calls7:383a.
That routine temporarily changes CUST4200 record6's drawing pass from0 to1,
calls DrawCustomImg3:2438 with arguments6/1, then restores the record. Its
SHAP4206 is ordinarily a back-layer drawing, so the exported room alone did
not provide an actor foreground mask for these bars.

Retain that command's clipped alpha as the throne gate's positioned mask at
tile column8/row2. The existing CheckGateInFore selector owns admission: the
actor's supporting column is7 or8, its physical row is2, and hanging modes2/6
are excluded. The ordinary foreground and the original scenery pixels stay
unchanged; the affected actor pixels now show the existing grille in front.

`tools.probe_throne_gate` executes the actual temporary CUST modification
and restoration. Only the DrawCustomImg endpoint is supplied: it records the
arguments and promoted record, without rasterizing. A second probe executes
3:2722-2764 directly for300 row/column/mode inputs with an explicit caller
frame, actor fields and piece column9/row2. It admits16 cases, with no service
endpoints in that selector. Original resource files are read-only. Full
drawing lists, QuickDraw and FrameAdv are excluded; this does not independently
validate the shared SHAP decoder.

`tests.test_throne_gates` enters from the actual room21 under ordinary Left
input, then tests the real Prince composite facing towards the grille and
after an ordinary Shift turn away. The bars must cover real Prince pixels
while gaps remain visible. Separate cases enforce row/column/hanging gates.
Local video sheets and native output are under `rendered/ruins-gates/`.

## Back-facing sword draw cannot cross the grille

DoKidEngarde6:1f04 reserves space before selecting55. The first pose207
then moves the Prince farther back. CheckBarr4:4e34 uses the preceding
frame's mask bank, retained by4:5152; a rectangle sampled after the draw
reservation is already beyond this narrow barrier and loses that crossing.
For this first pose only, the port's wall sweep now uses the existing previous
contact rectangle instead of the post-reservation one in environments3/4,
where that cache is maintained each frame. Other environments retain their
ordinary wall-sweep input rather than reusing an old cavern-style rectangle.
If a fresh warp/load
has not yet sampled a frame, seed that transient rectangle before reserving
draw space. That initialization is a host safeguard, with no new saved field.

The native rear collision selects65 and moves the actual reproducer to
scene X493, pose160. As it reaches ready170, its right edge includes the sword.
ShapeBounds4:5d30-5d6a includes GetCharEdges4:5e6e's attachment extension in
both its cached drawing bounds and its collision bounds. The cache copy
4:23b4-23ba supplies CutChar6:4922-492a. The port had supplied only the body
sprite's rectangle to the horizontal cut. It now supplies the complete
collision rectangle, including that same sword extension. This reaches the
ordinary right-cut threshold and returns to native room21 at scene X-17.
The same throne gate stays exempt from ordinary gate responses across the
room link, as detailed below. No room-specific
teleport, changed sword offsets, opened bars or retimed animation is added.

The extended native probe supplies the prior standing rectangle and four
first-draw rectangles. Original CheckBarr, its history, ReadCell and
CheckCollide1 find rear corrections85/68/55/40 for X385/402/415/430. Collide
is recorded at that boundary, then executed separately with actual JumpSeq,
SEQS65/AnimChar and Kid LoadFrame; all four yield X493/pose160/source65.
Original Cut6:4864-4908 reads the actual room link and rebases each to
native21/X-17. A further24 actual CutChar4918-4c0e decision cases check the
horizontal threshold and both facings against the production cut helper.

Prepared inputs/services are the complete type0 actor, half-open rectangles,
empty MOB bank, original Kid FRAM25001/AFRM25201, synthetic SEQS handles and
Resource/Memory Manager/hGetSequence boundaries. The rectangles are supplied,
so this is not an independent ShapeBounds/SHAP-decoder validation. Full
FrameAdv, QuickDraw and Cut's reverse-link/redraw tail remain excluded.

The real input regression enters from room21, turns with Shift, presses Ctrl,
observes65 and the return to room21, then tries moving towards the still-closed
grille. A separate first-draw-after-warp case covers an empty contact history.
Removing only the history fix fails at source55 instead of65; removing only
the complete cut bounds leaves the camera in port room8 instead of20. Both
parts are necessary for the supplied Macintosh behavior.

## Sheathing beside the grille keeps the ordinary standing finish

The follow-up recording shows an unwanted crouch after putting the sword
away. A real-input regression now extends the approach, turn and rear draw
through a short Down tap and the complete long sheathe92. Previously, at
pose239, CheckGateForKid selected crouch50 even after Down had been released.
This was a collision response, rather than a second Down command.

CheckGateForKid4:6124-6138 exempts level8's throne gate using ReadCell's
resolved room at A5-0x34aa. The host used the actor's current room instead.
In room21 the nearby gate is still the tile from native room9, column8,
queried at camera-relative column-2. Use that tile's resolved room for this
exemption. Keep the other gate/barrier/standing selectors' room rules intact.
This also removes the earlier ordinary-gate ejection from X-17 to X4; it
was not required alignment. When the sword disappears, the normal camera
cut can return to the throne view while the Prince remains outside the bars.

The regression requires sheathe92 to finish standing without crouch50/49,
then attempts inward movement and verifies the closed bars still block it.
It rejects the earlier code with sources50/49. Existing native sheathe input
semantics, including a Down deliberately held through its mode5 clear, are
unchanged. No special sheathe sequence, position clamp or camera exception
is added.

A fresh `tools.probe_temple_gate_contact` run executes original
CheckGateForKid, cell traversal, admission and JumpSeq50 for61,382 cases,
including the two resolved-room9 controls; zero mismatches against its
bounded reference. The executable's4:6124-6138 reads the cell cache before
the overlap masks or admission checks. Inputs/endpoints remain explicit:
supplied overlap banks and actor rectangles, SEQS50 resource lookup,
distance fixture, log-only ejection/cave response. It excludes independent
overlap construction, AnimChar, full FrameAdv, crush damage and rasterization.
The real sheathe/input regression exercises production behavior separately.
