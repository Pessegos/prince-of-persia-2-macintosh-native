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
