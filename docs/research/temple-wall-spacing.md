# Post-response wall spacing

The isolated4:3982 helper now executes with real GetCharPoint/GetDist1,
GetCellsInFront, ReadCell, IsWall, relative movement and Kid frame/column reload.
It ends by refreshing the current cell and returns that tile kind. Incoming
actor/contact admission and current18-byte frame metadata are prepared inputs.
No animation runs in this helper; the selected pose is preserved.

## Decisions and ordering

- Actor word+52 equal4 and actor type11 skip displacement/frame reload, but
  still read and return the current cell. Word+52 is an offset-level condition;
  it is not the movement mode at+16.
- A separate exception is **room3**, environment6, support column<0. It is not
  row3. This is covered as a synthetic live-room control, not a claim about a
  playable non-temple environment or its undefined-cell fallback.
- Otherwise GetCharPoint uses current metadata's frame displacement and low
  six flag bits. GetDist1 converts its signed point and uses the actual division
  remainder. Facing0 returns50 minus the remainder; facing-1 uses the remainder.
- GetCellsInFront(1) reads the cell adjacent to the supplied support column,
  even if distance already determines the following branch. Native facing-1
  queries column-1; facing0 queries column+1.
- Distance>=18, or a near forward tile in wall kinds2/7/20/25, uses relative
  delta distance-51. Otherwise the relative delta is distance+18. Tile4 does not
  count as a wall for this branch. The 17/18 distinction is exact.
- After moving, real LoadFrame reloads the existing pose's original Kid frame
  and attachment, updates the support column/remainder, then35a6 reads the cell
  at that **new** column. The incoming metadata need not match the later frame.
  Mark, animation cursor/source, HP, ALIVE and unrelated globals stay untouched.

## Evidence and explicit boundaries

`tools/probe_temple_wall_spacing.py` compares27,364 original calls with zero
mismatches. It covers all1,345 wall/crevice/barrier anchors across levels10–13,
two facings and four local X controls, then all352 incoming Kid poses, warm/cold
cell cache, exceptions and exact distance17/18/19 against seven forward tile
kinds. Both original AFRM25001 and25201 bindings are checked separately.
Ten asset-free tests reject the wrong row3 interpretation, a missing forward
query/final refresh, the wrong near-wall branch and metadata conflation.

The environment6 controls explicitly link their cells to live fixture rooms;
non-temple undefined-cell behavior is an excluded reference boundary. Ordinary
temple undefined cells and horizontal/vertical traversal use the already
recovered temple reader. Direct helper/pose fixtures do not prove physical
reachability or Collide admission. Some wall kinds include crevices and rock
markers: enumerating their anchors does not mean the full controller is done.

Complete A5 output, ordered cell reads, frame events and returned tile agree.
Checks guard saved actor, animation state, mark, frame metadata, remainder,
cached cell/pointers and unrelated state. Original level data, FRAM/AFRM bytes
and prepared handles remain unchanged. Frame handles are supplied; no geometry,
movement, cell or frame-reload services are stubbed in this module.

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_wall_spacing --source PATH_TO_RECOVERY --output rendered\temple_wall_spacing_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_wall_spacing_reference
```

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Compared-output SHA256:
`80481a24ae1403399a05e6e7b3409574b69b75b79a7f5623728508406e39e56b`.

Reports/original resources remain ignored. Next bounded step: compose the
grounded/unarmed/armed response leaves and this spacing helper with actual
Collide4:5738, retaining supplied body/admission geometry as an explicit boundary.
ShapeBounds/contact construction, repeated physical frames and playable temple
remain open. No production, artwork or README changes in this module.
