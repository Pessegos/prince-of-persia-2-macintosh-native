# Temple exit clipping and level handoff

Status: 2026-11-14. The Prince now uses the temple's original stair-entry
rectangle, and completion of levels 10, 11 and 12 schedules the existing
end-song/story/next-level path. No gate timing, checkpoint, artwork or save
format changes are involved.

Follow-up: the user's screenshot after the initial correction still showed
the Prince over the right jamb. The rectangular rule below was recovered
correctly, but was insufficient to establish complete doorway occlusion.
The missing pose-dependent foreground piece is now restored too; see the
follow-up section. The first milestone's full-suite totals below remain
historical validation of that milestone, not a new full run of this follow-up.

## Recovered clipping rule

`ClipChar` CODE 4:416a-420c handles actor type 0, poses 217 through 226,
strictly above row-relative Y -24. Its caller has already established the
actor visibility and ordinary clipping bounds. `ReadCell` supplies the
supporting-foot cell; tile 16 moves the rectangle one column right.
`GetBlockRect` CODE 5:01e2 offsets and intersects the environment rectangle
with the viewport. Only its top and right replace the actor's clip edges.

The original DATA pointer table at a5-0x452c selects `(13, -51, 364, 80)`
for environment 2, with rectangle words ordered top/left/bottom/right.
The port already translated this branch for environments 3 and 4, but its
rectangle lookup omitted environment 2. Consequently the late stair poses
were composited over the temple door's lintel and right jamb.

`tools.probe_ruins_exit_clip` now includes original levels 10-13 as well as
3-9. It executes the original CODE slice, actual `ReadCell` and
`GetBlockRect`, comparing the complete DATA image with the expected two
clip-word writes. The 31,680 cases have zero mismatches: all three rows,
ten columns, tiles 16/17, poses 216/217/226/227, Y -24/-25/-42, actor types
0/2 and both facings across these eleven levels.

Actor coordinates, the visibility/body prefix, initialized DATA pointers
and the `ClipChar` A6 frame are supplied. QuickDraw `OffsetRect`/`SectRect`
are supplied endpoints. Synthetic cells are placed in copies of the original
LEVL data; this is not a full native animation, rasterization, campaign-route
or `FrameAdv` comparison. Original files remain read-only.

Executable SHA-256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Comparison-output SHA-256:
`618170ec0acf9eade166afe50ac55bf0fa66d68944a86ac1663e02a72a79dc48`.

## Completion and story handoff

The real stair sequence emits completion, but `advance_level_events`'s
list of levels that create a `LevelExit` omitted 10, 11 and 12. The scene
therefore stopped with completion set and no pending transition. Adding
these levels reaches the already implemented `Temple.finish_exit` path.

Original `GetEndSong` CODE 5:4e0c-4e3e returns cue 187 for environment 2.
Direct calls with each original level 10-13 return 187 without service
endpoints. The original main-loop path CODE 2:6100-6168 advances frames
while waiting for the ending song, then calls `CheckPlayNIS` 2:0180 before
restarting at the next level. The port retains its existing audio completion
gate and duration fallback, then selects any due tree scene and loads
11, 12 or 13. Level 13's existing flight to 14 is unchanged.

This handoff is supported by static original-code reading and real hidden
port scenes; it is not an original CPU trace of the entire completion,
movie, restart and audio-driver loop.

## Integration checks

`tests.test_temple_exits` starts the real entry sequence at all six
non-entrance temple exit doors: native rooms 19 (level 10), 24 (11), 7 (12),
28 and both doors in 32 (13). The fixtures explicitly open each door and
place a supported Prince beside it; they do not assert natural full-level
reachability. Actual rendered late poses obey the top/right bounds and
change visible pixels at every door. That first image comparison established
the rectangular cut, but failed to reject the residual jamb overlap later
reported by the user. Each before/after pair used identical animation state.

The transition regressions finish the real stairs and exercise all three
requested level pairs with queued music and a timed playback backend. They
require the old level to remain active while cue 187 is busy, then check
the next start room, retained campaign clock object and health, and cleared
completion/exit state. With audio absent, they also exercise the duration
fallback, a due tree scene, and its next-level callback. Hardware playback
timing is not measured.

Negative controls substitute the previous implementations: the two clipping
tests fail in eight cases/subcases and the two transition tests fail in six,
without errors. The focused exit/arrival/ending/story group passes 79 tests.
Full discovery's 252 modules pass in isolated interpreters (bounded caches,
three workers, audio and frame-cost modules serial): 4,184 cases, zero
failures, zero expected failures, 416.31 seconds. Ten cases are skipped:
nine exclusive-desktop checks under `POP2_SHARED_DESKTOP=1` and one original
enemy-profile check requiring `POP2_RESEARCH_DIR`. Skips are not passes.
Dependency, Ruff F/E9, recovery-catalog and whitespace checks pass.
Ignored local reports, per-module suite logs and the visual comparison are
under `rendered/temple-exits`; the native report is
`rendered/temple-exit-clip-native.json`.

Reproduce the native check with:

```powershell
.venv\Scripts\python.exe -m tools.probe_ruins_exit_clip --source ..\PoP2-Mac-Code-Recovery --output rendered\temple-exit-clip-native.json
```

The remaining boundary is full native clipping/scheduling/audio equivalence,
not a new gameplay rule inferred from these bounded tests.

## Follow-up: the doorway's front-table piece

`DrawTempExitMovable` CODE 10:0562-0698 has another relevant rule. In pass 5,
10:0652-0660 tests the global Prince pose for 217 through 226, without a Y
test. It then resets a front BF item (`ResetNextBFItem` 3:29e2), transfers the
source cell's middle fields (`TransferBFItemMidFields` 3:2b5c), and adds
the PIEC record at offset 0x47c. Original Temple PIEC words are
`(79, -11, -27)`: SHAP 3579, X column*51-11, bottom (row+1)*120+5-27.
Outside these poses the same piece remains in the back table. Passes 1/2
do not emit it. The static room export used a non-entry pose, so retained
this arch/jamb only in the background.

`tools.probe_temple_exit_foreground` executes that original drawer and the
actual BF reset/previous-info/field-transfer routines. It checks all three
rows, ten columns, poses 216-227, passes 1/2/5 and foreground words
0/1/79/255: 4,320 comparisons, including 1,200 front promotions, zero
mismatches. Original level-10 environment 2, PIEC and SHAP headers are
checked. The BF caller state, buffer pointers, pass, pose and full viewport
are supplied. `AddNextBFItemToTable` 3:0004 is a supplied shape-header/clip
admission and counter endpoint; native resource lookup and rasterization
do not execute. Back pass 0, dirty scheduling, ClipChar, other-actor ordering
and full FrameAdv remain excluded.

The port retains the clipped original SHAP and position alongside the room
commands, and redraws it after the entering Prince's ordinary floor repaint.
The later corner repair below retains composed scenery colours under that
original SHAP alpha rather than repainting the raw SHAP colours.
This uses the sprite's own transparency, retaining the actual arch and jamb
contour, and leaves ordinary poses, NPCs and other environments alone. The
existing rectangular clip and all three level transitions remain unchanged.
Only the small positioned door pieces are retained, without an extra full-room
image per cached variant.

The six-door regression now compares the rendered image with the same pose
and repaint path with only the player sprite removed. It requires zero
player-colour differences over opaque door pixels in every entry frame,
including repeated late poses. Viewport crops account for the one-pixel
room origin. An asset-free test checks both pose endpoints, excluded poses,
actor type and independence from the rectangular clip's Y threshold.
Substituting the old drawing path rejects 15 cases/subcases, with no errors.
The final focused group passes 161 tests (temple exits/arrival, cavern exits,
cavern renderer, opening renderer and level endings), without skips. This
render-only follow-up does not rerun full discovery. Before/after images for
all six doors and a ten-pose strip were inspected. Initial test comparisons
were corrected to preserve floor repaints and crop the room origin; their
failures were not production pass results.

Reproduce the new native check with:

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_exit_foreground --source ..\PoP2-Mac-Code-Recovery --output rendered\temple-exit-foreground\native.json
```

Reports and images remain ignored under `rendered/temple-exit-foreground`.
Temple resource-fork SHA-256:
`7c7b532ef5251949b299d6177962062bdb003b385675285873d77f865ea68ccf`.
New comparison-output SHA-256:
`8a6d82ccbb34d70a85599652fc06c7185820eefb2e1b29d5a446cd9df7d552ad`.
Full native draw/audio/frame equivalence remains the next bounded research
boundary, not a prerequisite for this reproduced foreground repair.

## Follow-up: stable lower-right floor corner

The next user crop exposed a scenery change introduced by the whole-piece
repaint in `743ea0d`. In the level-10 exit, three pixels at room coordinates
(343,216), (344,216), (342,217) changed from the neighbouring floor's dark
colours to the jamb's brown colours as soon as pose 217 began. The source
commands place SHAP3579 before the next column's SHAP3528; the latter covers
these corner pixels in the composed room. Redrawing raw SHAP3579 after the
actor incorrectly replaced them. This is independent of the Prince's pixels.
The equivalent three-point corner occurs at all six tested exit doors.

The retained actor-occluding piece now takes its colours from the finished
background/foreground composition, while keeping the original door's alpha
and position. Only small cropped pieces are stored. This preserves the
visible floor and other already composed scenery while hiding the entering
Prince. Native pose admission and geometry remain as previously recovered;
the colour-preserving host composition is a renderer correction, not a new
claim about the complete Macintosh dirty-cell/raster pipeline.

The additional regression checks all three corner pixels and requires that
entry occlusion change no scenery outside the player's drawn bounds, in
every entry frame at all six doors. The previous renderer fails seven
cases/subcases without errors. The existing full-contour occlusion and
transition tests remain intact. The focused renderer/exit/arrival/ending
group now passes 162 tests, without skips, in 59.753 seconds. No new full
discovery or native probe run is claimed for this colour-only correction.
The normal/previous-entry/fixed-entry corner comparison was inspected:
fixed and normal have no differing pixels in that crop. Local evidence is
ignored under `rendered/temple-door-corner`.
