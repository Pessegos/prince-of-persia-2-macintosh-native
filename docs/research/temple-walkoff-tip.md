# Temple first-fall frame: rear tip behind the diagonal

Status: 2026-11-14. The user's second image asks for a small extra occlusion
of the rear leg, only in the first fall frame at level 10, native room 19.
It does not ask to reveal the boot or change the rest of the fall.

The broader support-line extension in `4d76353` was explicitly rejected.
Commit `70ec8d1` reverts it exactly; its tracked tree matches the accepted
`8163600` state. The original approved climb/descent mask and the accepted
temple exit, corner and transition repairs are preserved.

## Corrected drawing

The supplied supported start is room index 18, row 1, X225, facing left.
Seven actual Left ticks reach source SEQS 7, pose 102, X151, relative Y -115,
physical row 2, drawn bounds (139,161,195,231). The original half-floor
repaint begins at Y220. The visible complete floor plane (SHAP3528) begins
at Y216 and has the diagonal which the user's target follows.

Rooms retain that complete plane's alpha and position, with colours sampled
from the finished room composition. After the unchanged ordinary repaint,
the extra contour is drawn only inside the actor's bounds, only for the
Prince in environment 2, source SEQS 7, pose 102, mode 3, facing left.
Other frames, facings, actors, environments and controllers are excluded.
The general `ledge_surface_clip` behavior is back to the accepted original
climb/descent scope. There are no physics, timing, input, sprite, imported
resource or save changes.

In the reported pose, the change hides exactly 17 native pixels in
X185..194/Y217..219. Every changed pixel receives the already visible floor
colour. It reveals no boot or trouser pixels. The next fall poses and the
preceding run frames remain pixel-identical to the restored renderer.
The before/after crop was visually compared with the supplied target;
this is not a pixel-for-pixel comparison against the attached image file.

## Verification and boundaries

`tests.test_temple_walkoff_tip` checks the narrow admission, actual diagonal
alpha, hole, underside, bounds and foreground pillar. A real input replay
checks the 17-pixel region and floor colours, unchanged sequence state,
and unchanged renderings for run poses 2-7 and fall poses 103-106.
Disabling this correction makes both new tests fail, without errors.
The restored ledge, temple-door/corner and gate-repaint group passes
21 tests, without skips. Ignored images and negative-control output live
under `rendered/temple-first-fall-mask`.
The remaining bridge/cavern/opening/arrival/exit/ending group passes another
193 tests, without skips: 214 focused cases across the two groups.
Dependency, Ruff F/E9, recovery-catalog and whitespace checks pass.

This is the user's narrowly specified port visual improvement, not a newly
recovered Macintosh rule. No new native probe or full-discovery run is
claimed. The earlier rejected broad fall-mask tests are removed, and their
passing counts are not evidence that the rejected appearance was correct.
