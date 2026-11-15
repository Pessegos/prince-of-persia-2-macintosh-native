# Falling slab: the last three pixels over the next tile

Status: 2026-11-14. User recordings `Macintosh room 8.mp4` and
`Port room 8.mp4` show level 10, native room 8 (port room 7), loose cell 13
(row 1, column 3). The port leaves a small moving stone strip on the
stationary floor to its right. The Macintosh recording retains that floor.

## Cause and correction

`draw_cavern_falling` paints whole exported SHAP images. The temple lip,
SHAP3528, is 90 by 29 pixels, while the ordinary falling object's logical
`ComputeMobRect` (CODE5:32f6) is 87 by 43. The host floor repaint reused the
logical width and stopped at X240 for this X153 slab. Three drawn columns,
X240..242, remained over the right-hand tile. Repainting only more pillar
foreground does not solve this: the residual pixels also cover back-layer
floor colours. That exploratory change was discarded.

The renderer now extends its repaint box to include every drawn piece,
retaining the logical box as its minimum. The existing next-column floor
records, their alpha and foreground order perform the repair. No change to
`FallingFloor.size`, collision, movement, damage, timing, resources, saves,
actor masks or the accepted first-frame ledge improvement.

The original references distinguish drawing from logical bounds:
DrawObjLoose CODE3:412c-41aa chooses pieces; ComputeMobRect CODE5:32f6
supplies the logical box; RedrawCell CODE3:1d12-1d38 and 1d3a-1de4 dispatch
back passes and DrawForeImg3:2598. This is a host whole-SHAP repaint repair
supported by the supplied videos, not a new original CPU/raster equivalence
claim. No native probe or independently decoded pixel comparison is claimed.

## Verification and scope

The regression forces the original loose tile to detach through its real
controller, checks its initial Y263, then renders four supplied fall positions.
Only X240..242 change, each changed pixel receives the finished stationary
scenery colour, and the falling object's state is unchanged. Reinstating the
87-pixel repaint makes this test fail without errors.

An ignored audit under `rendered/falling-floor-neighbour` visits every original
loose cell and breakable shelf in levels 3-13: 144 anchors in 95 rooms,
1,641 supplied drawing cases using actual detached variants. Of these,
35 temple anchors change in 211 cases; cavern and ruins outputs stay
pixel-identical to the previous painter. Every changed pixel had been
covered by the slab, and every restored colour equals the finished scenery.
This is an artwork/drawing audit, not 144 natural campaign routes. Heights
include viewport-border positions; it does not exhaust concurrent moving
objects, all animation phases or all cross-room gameplay histories.

Cavern pieces are 85x25 and 50x18; ruins pieces 89x30 and 51x5; temple
pieces 90x29 and 51x5. Transparent contour pixels do not necessarily need
repainting; the audit establishes which scenes actually change. Broken
shelves retain their 91x31 logical box. Levels 1-2 and 14 do not dispatch
this falling-slab painter (`LevelRenderer.animated_layer` admits kinds 2/3/4),
so this cause does not apply to their renderer.

The supplied clips, frame sheets, before/fixed image, audit JSON/generator
and negative log remain ignored. Original resources and user windows/data
were not modified.

Final focused check: `tests.test_falling_floor_occlusion`, `test_loose_floors`,
`test_caverns`, `test_ledge_occlusion`, `test_temple_walkoff_tip`,
`test_temple_exits`, `test_exit_contours`, `test_gate_repaint` and `test_bridge`
pass 167 tests without skips (69.351 seconds). Dependency, Ruff F/E9,
recovery-catalogue and whitespace checks pass. No full-discovery run is
claimed for this bounded rendering change.

## Follow-up: original temple MOB type (2026-11-14)

The subsequent [room14 contact investigation](temple-room14-loose-landing.md)
recovered the upstream reason for the87px temple box: the port had created
the cave's MOB0/Y+23 instead of the temple's native MOB3/Y+5. Its91px native
box already contains the90px lip. That spawn is now corrected, including the
18px vertical offset; this full-raster painter safeguard remains. The room8
regression now expects first detached Y245/MOB3, rather than the earlier
port-specific Y263/MOB0. Earlier audit counts above describe the painter
change on its original baseline, not a new whole-game native claim.
