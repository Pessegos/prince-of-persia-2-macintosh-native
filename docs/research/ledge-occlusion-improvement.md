# Ledge descent and ascent: intentional visual improvement

The user supplied DOS/port recordings and Photoshop targets for both directions
of the animation in level 6, native room 8 (port room 7). The requested change
deliberately improves the Macintosh layering: trousers, shirt and boots must
not show through the slab while the Prince climbs or backs down. The DOS clip
is a visual comparison, not an authority for gameplay or native recovery.

## Drawing policy

For the Prince's poses 135–144 in selected SEQS 10 (climb) and 68 (controlled
descent), retain every pixel on and above the floor's support line. Below that
line, use the intersecting floor's actual alpha, with its sloping outline,
transparent corners and underside. Feet below a thin slab remain visible.
The drawn top identifies the upper floor throughout the animation, including
the physical row change at pose 141. The policy applies in both facings.

`ledge_surface_clip` defines that limited region. Cavern-family rooms repaint
their existing full floor records within it instead of selecting the original
pose-dependent half repaint. This includes caverns, ruins, temple and final
palace artwork and uses the current loose-floor/plate/bridge room variant.
Rooftop masks add the intersecting near-edge/plank alpha in the same region;
the projected shaded side stays behind the Prince outside the building.
Existing facade/parapet, pillar and decoration masks remain in force.
Custom bridge planks have only a partial repaint in the export; where there
is no full floor record, their existing native repaint is preserved.

The original ComputeHalfRect tables, ClipChar clipping and normal floor
redraw selection are retained for other sequences and actors. No sprite,
scenery asset, import format, motion, collision, input, timing or save data
changes. This is not a newly recovered native rule or a native pixel-parity
claim. The desert's custom scenes have no corresponding floor records and
receive no new mask.

## Verification

`tests.test_ledge_occlusion` checks the support line across the row change,
both facings and both sequences, exact alpha corners/holes/undersides,
foreground pillars, rooftop near edges/shaded sides and harbor planks, and exclusions
for other actors/poses/sequences. A separate regression retains a custom
bridge plank's original repaint when no full floor record exists.

The actual level-6 room-8 input replay descends, holds and climbs back up.
Poses 138/140/141/143/144 in both sequences replace the intruding pixel at
scene (225,227) with the stone color (157,114,98). All pixels on/above Y226
and below the slab at Y245 are unchanged, including hands and dangling feet.
Rendering leaves the full sequence state unchanged.

Ten hidden real-input round trips cover both facings across roof, cavern,
ruins (levels 6/7), temple and final-palace scenery, reaching all climb poses
135–148 and returning alive to idle on the starting floor. Starts are supplied
at real, unmodified level cells; this is not an entrance-to-exit route audit.
With the new drawing region disabled, the four drawing regressions fail
(including their subcases); the previous behavior is explicitly rejected.

Local review frames and an enlarged before/after animation are generated under
`rendered/ledge-mask/`. These contain imported artwork and remain untracked.
The level-6 targets guided the visual check; this does not claim a pixel-for-pixel
comparison against the user's Photoshop files or exhaustive inspection of every
ledge in every room. No live game window or physical input is used.

Validation commands (worktree Python):

```powershell
$env:POP2_SHARED_DESKTOP = '1'
.venv\Scripts\python.exe -m unittest -q tests.test_ledge_occlusion tests.test_bridge tests.test_caverns tests.test_render_opening tests.test_game_ui
.venv\Scripts\python.exe run_game.py --check-dependencies
.venv\Scripts\python.exe -m ruff check --select F,E9 .
.venv\Scripts\python.exe -m tools.recovery_catalog --check
git diff --check
```

The final focused run passed 232 tests, without skips. All 248 discovery
modules were also run in isolated interpreters (4,165 cases, ten skips):
the junction body-pixel regression exposed an overbroad shaded-side mask;
the production mask was narrowed and the unchanged test passed in the final
focused run. The other 247 modules passed. Audio and frame-cost modules ran
serially. The eight new tests include the subsequent bridge preservation
regression (added after that discovery-module run). Ordinary single-process
discovery was stopped for growing retained caches, not counted as a result.
The ten exclusions were nine exclusive-desktop tests and the unavailable local
native-enemy profile. No exclusive desktop run or native-equivalence claim.
