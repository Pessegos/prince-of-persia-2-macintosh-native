# Cavern and ruins exit-door contours

Status: 2026-11-14. The four supplied Macintosh/port recordings show a straight
cut through the irregular cavern jamb and a few Prince pixels over the ruins'
upper-right corner. Matching poses were inspected; differing input start times
in the clips are not treated as animation timing evidence.

## Original frame promotion

The existing `ClipChar` rectangle is only part of the draw pipeline. The
environment also puts a real scenery piece in the front BF table:

| Environment | Original CODE slice | Piece | Admission |
| --- | --- | --- | --- |
| Caverns | 8:1cfe-1d78 | SHAP3565, X col*51+14, bottom (row+1)*120+5-30 | Prince poses217-226 and absolute Y < player row*120+82 (relative Y<-24) |
| Ruins | 7:27c0-27fe | PIEC0x47c=(45,-11,-25), SHAP3545 | Prince poses217-226, no Y test |

The source clip begins at row*120+1 in the caverns and row*120-10 in the
ruins. The latter differs from pass5's extra full-height background copy.
The port retains the appropriate frame, its transparency and irregular edges.
Existing rectangular clipping remains in force.

`tools.probe_cavern_ruins_exit_foreground` checks the original conditionals,
`ResetNextBFItem` 3:29e2 and `TransferBFItemMidFields` 3:2b5c. Original level3/6
headers, PIEC offsets and SHAP dimensions are checked. Rows0-2, columns0-9,
poses216-227, Y0/-24/-25/-42 and foreground0/79 give 5,760 comparisons with
zero mismatches: 2,880 per environment, with 1,200 cavern and 2,400 ruins
front promotions.

Entry is after moving-door image admission. The next BF item, buffers,
source clip, PIEC pointer and Prince pose/row/Y are supplied.
`AddNextBFItemToTable` is a supplied original-shape-header/clip/counter
endpoint. The prefix, resource lookup, dirty scheduling, actor pixels,
full ClipChar/FrameAdv and hardware rasterization do not execute. This is
not an independent check of the port's SHAP decoder. The shared endpoint's
new clip method defaults to the prior full viewport; the temple control
still passes 4,320 cases with its previous output hash.

## Port composition and checks

`CavernRoom.actor_mask` adds the original frame alpha at the recovered gate.
It hides the Prince without painting cached RGB over live cave lighting or
particles, and retains character pixels in transparent areas. Temple painting,
the accepted corner/first-fall-frame repairs, physics, saves and transitions
are unchanged.

Fifteen prepared tile17 anchors across levels3/4/6/7/8/9 run the real stairs.
Doors are explicitly opened with supported supplied starts; these are not
fifteen natural campaign routes. Level7's upper-entry door is excluded and
the fixture clears prior level6 arrival selection before loading a canonical
level. Fourteen anchors have residual pixels; the level7 room21 fixture is
already clear and stays pixel-identical. The reported cavern room13 (level3)
removes up to92 pixels along the irregular jamb; ruins room16's right exit
(level6) removes up to6 at the upper-right corner.

`tests.test_exit_contours` requires zero character pixels over opaque stone,
unchanged pixels in transparent notches and outside actor bounds, a visible
character in the passage, correct admission, and unchanged sequence state.
A distinct live backdrop rejects static RGB repaint. Previous masks fail29
cases/subcases in the three new tests without errors. Final focused rendering,
door/ledge/bridge/arrival/ending/gate-repaint checks pass217 tests without skips
in92.006 seconds. No new full-discovery run is claimed. Video-stage sheets
and the final Macintosh/previous/fixed comparison were inspected under ignored
`rendered/exit-contours`.

```powershell
.venv\Scripts\python.exe -m tools.probe_cavern_ruins_exit_foreground --source ..\PoP2-Mac-Code-Recovery --output rendered\exit-contours\native.json
```

Executable SHA-256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Output SHA-256:
`4d6a63b5d6f1aa286ae166e81b2aa0c745d714ac472c74d49586e15449f32edf`.
Full native dirty/frame/cross-actor composition remains a separate boundary.
