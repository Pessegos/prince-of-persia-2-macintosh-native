# Temple Prince Frame Metadata And Supporting Column

Research only. This bounds type0 LoadFrame before connecting it to the
[real controller geometry](temple-controller-geometry.md). No runtime changes.

Actual `4:2a72` calls `4:2a8e` to copy original Kid FRAM metadata and its
indexed AFRM attachment, then `4:2a7c/3a72/3ad6` and `5:48b0` to calculate
the supporting column and signed division remainder. Type0 uses Kid handles
at A5-3472/3476, not just the generic handles read on entry. Prepared handles
are installed directly; their Resource Manager selection policy is not proved.

- All352 FRAM25001 records are tested against separately supplied AFRM25001
  and25201 bindings. This does not claim which binding a temple story state
  chooses. The18-byte frame/attachment result is compared in full.
- The supporting foot applies FRAM dx minus the low six flag bits, then
  facing. Its column can differ from the actor anchor's column.
- Signed division truncates toward zero. The native sign extension precedes
  a low-word subtraction: at foot X22..25 this differs dramatically from a
  naive Python division. The existing independent head-support model is reused
  here and checked against actual Kid frames, not the port terrain decoder.
- This helper changes actor column, not actor row/Y, HP/ALIVE, pose or sequence.
  It does not calculate sprite bounds or frame width. Those belong to the
  still-separate GetCharEdges/shape path and must not be inferred from FRAM dx.

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_kid_frames --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_kid_frames_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_kid_frames_reference
```

**22,528 native/reference comparisons, zero mismatches:**352 poses, two
facings,16 supplied X values and two attachment banks. Complete actor/frame
bytes, signed remainder, saved actor, cell cache, TROB storage and level
canaries are checked. Original tables and prepared handles remain read-only.
No native service endpoint is supplied. Eight asset-free regressions bound
attachment selection, flags, facing, mutation scope, signed wrapping and
unsupported actors/indices.

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Compared-output SHA256:
`a4dd8695945ca4d0e1afd55d5a69af885025b70aa551cd0eabea161b40f1a416`.
Resource hashes remain in the ignored report, not original resource bytes.

Excluded: GetCharEdges, shape dimensions/rasterization, supporting-foot Y/row,
animation/controller scheduling, physically reachable poses/coordinates,
complete FrameAdv, saves and playable temple integration. Next connect this
loader before/after animation inside the real caller, then track persistent
clip effects without presenting a supplied continuation schedule as physics.
