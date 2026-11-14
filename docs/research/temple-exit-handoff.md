# Temple exit clipping and level handoff

Status: 2026-11-14. The Prince now uses the temple's original stair-entry
rectangle, and completion of levels 10, 11 and 12 schedules the existing
end-song/story/next-level path. No gate timing, checkpoint, artwork or save
format changes are involved.

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
change visible pixels at every door. Manual image inspection confirms the
lintel/jamb occlusion, with identical animation state for each before/after
pair.

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
