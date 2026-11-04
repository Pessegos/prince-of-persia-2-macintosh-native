# Ruins hanging: turban clipping and grip expiry

## Reports and reproduction (2026-11-04)

The user's `macintosh turbante.mp4` and `port turbante.mp4` show level6
native room8 (port room7). The Prince descends from the left edge of the
right platform and swings below it. In the port, a few turban pixels cross
the slab; on grip expiry he catches the same edge again, with another grip
sound. The Macintosh hides the turban and lets him fall to native room4.

The scene fixture starts at X245, physical row1, facing right. Shift+Down
selects SEQS68 and aligns X241, then its descent reaches X230,row2. Keep
Shift or Ctrl held and release Down. SEQS210 swings through poses87-99,
sets sequence mode11, and must release through SEQS99 to the fall loop.
The test observes the native sequence steps, not video wall-clock timing.

The preceding hands fix removed an excessive mask made from complete
back-layer slab surfaces. That restored the left-facing hands but left
ordinary Ruins actor top clipping unwired. Reintroducing the slab mask
would erase the hands again. Both reported routes are now regression cases.

## Ordinary actor top clipping

ClipChar `4:4146` builds the character clip rectangle, then its ordinary
body at `4:4230-43de` can raise the top to `physical row * 120 + 5`.
This branch also applies to environment4. The port only called its existing
implementation for environment3; it now also calls it for Ruins.

For the right-facing swing at X230,row2, the original returns top245.
This hides the leaked turban pixels, including viewport(222,236..239) at
pose87. The body below that boundary stays visible. In the earlier report's
left-facing fallen-slab catch at X122,row2, the original disables this
recrop, so the hands and forearms in poses79,80,91 remain complete.
Native DrawHalf/DrawFloorBuf commands and ordinary foreground still run.
No back-slab mask, sprite edit or room-specific pixel patch is added.

`tools.probe_ruins_hanging` executes LoadFrame, SetupSword, GetCharEdges,
MakeFCharClipRect and ClipChar through `4:43de`, stopping before environment
hooks. All2,400 native/port clip-top comparisons agree: levels6-9, port
rooms3/7, rows1/2, both facings, X108/122/230, poses79/80,87-99,135-144.
These supplied actor fixtures do not claim every combination is reachable.
The level6 room3 fixture clears loose cells12,13,22,23 to match the hands
recording. LEVL environment/number headers are checked.

Supplied endpoints: original Kid frame/attachment bindings, dimensions from
original SHAP headers, SectRect intersection and visible-actor admission
(`IsCharNonViewable` returns zero). Native terrain lookup, column calculation
and the clip body execute. Environment hooks after `4:43e2`, non-player and
entry/exit actors, native rasterization and full FrameAdv are excluded.

## Catch scheduling during release

CheckFloor `5:1202-127a` dispatches by animation mode. Its mode3 branch at
`5:1254-1268` calls Catch `4:37ca` only for poses102-106. Mode4 calls Falling
`6:00a6`; mode9 calls it only with nonzero vertical velocity. Other modes
do not enter this falling-catch path.

The port called Catch whenever its host `motion.falling` flag was true.
Grip expiry selected SEQS99, then its very first pose81 called Catch again
at X230,Y0 while the modifier remained held. That restarted SEQS15/9/210
instead of completing the release. The native source-sequence99 geometric
extension was already implemented; changing it would target the wrong rule.

`falling_catch_scheduled` now gates the scene's falling-catch callback using
the original dispatcher. SEQS99 completes its three mode3 poses81 before
mode4 admits Falling/Catch. On this route the Prince is then below the edge
and falls to room3,row2. Ordinary mode3 falls at poses102-106 can still catch;
the existing geometry, modifier and speed/height checks remain in place.

The probe executes the actual CheckFloor dispatcher in220 cases: type0,
modes0-9, eleven poses around both admission boundaries and velocities0/1.
Floor, Catch and Falling are inert routing sinks; this slice verifies which
endpoint is called, not their geometry or full animation/physics.

## Verification and scope

```powershell
.venv\Scripts\python.exe -m tools.probe_ruins_hanging --source PATH_TO_RECOVERY --output rendered/ruins-hanging-native.json
```

There are zero mismatches in the stated native slices. Original executable
SHA256: `ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Output SHA256: `4e2cbfc5cca238ac281eb1d6667658a5dea8bc98fa5f1e79dad540666d14c93a`.
Original files remain read-only; the executable is checked unchanged afterward.

Scene regressions cover all13 swing poses with scenery above top245 and
visible actor pixels below it, grip expiry while holding Shift and Ctrl,
the complete fall to room3, and the preceding left-facing hands/climb route.
Against09a7a9c, only the two new methods fail (42 subcases); the hands case
passes. All83 focused cavern/ledge/playtest tests pass with the fixes.
Shared-desktop discovery under Python3.12 ran3,406 tests with10 explicit
desktop skips and one failure: the fresh-import GUI cancellation subprocess
aborts with `Tcl_AsyncDelete: async handler deleted by the wrong thread`.
That same test also fails on unchanged09a7a9c under the same Python3.12
interpreter, and passes on09a7a9c with the primary's Python3.10. The importer
failure is therefore recorded as an existing environment issue, not hidden
as a passing full run. Integration checks are recorded in the local handoff.
No emulator/input replay, complete visual parity or new catch geometry is
claimed. Further ruins reports remain the next bounded task.
