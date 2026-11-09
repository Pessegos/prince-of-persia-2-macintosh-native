# Temple candles, 2026-11-09

The user's first new temple playtest report was that the candles did not
animate. Their images were present in the exported scenery, but the exporter
only recorded live torches for environment 3. Temple `torches` lists were empty,
and the runtime assumed the caverns' nine frames at SHAP 3581.

## Recovered rules and integration

- DrawTempTorch **10:10ea**, specifically **10:1196-11cc**, selects library 4,
  SHAP **3596 + (foreground & 15)**. PIEC 3500 at **0x186/0x188** supplies the
  flame's X/Y offsets (42, -77). These are six original 47x42 images, including
  the wall, candle holder and changing light; no new artwork was made.
- TriggerTorch **5:1ffa-208e**, called by room activation at **2:5112**, selects
  **Rnd(5)** in the temple (**5:2054**), versus Rnd(8) in the caverns. It supplies
  the initial low foreground bits and appends the tile-19 TROB.
- TempGetTorchFrame **10:12b6-12e2** takes the previous phase, requests Rnd(5),
  and advances/wraps a repeated choice. The output is 0..5 and never repeats
  the previous valid phase. The native random stream itself is not reproduced.
- `CavernState` uses the record's frame count, retaining the existing default
  of nine and the port's upper-foreground preservation. Visible clips of the
  same logical candle share one phase and advance once per simulation tick.
  The existing pause and restart paths remain responsible for freezing and
  reinitializing the animation.

The exporter now records temple candles from the original shape-info source
column/row. Existing imports are upgraded **in memory** when loaded: the
runtime derives the source column from the drawing's X and the PIEC offset,
then resolves the source cell through the original level. A drawing slot in
the next column is not the candle's source. The imported JSON files are not
rewritten and a resource reimport is unnecessary.

Older temple checkpoints contain an empty candle phase bank. After loading
one, retry restores that bank. The first visible update now seeds missing
entries from the exported foreground before selecting a phase. This is host
compatibility handling, not a newly recovered native branch. A real level-12
checkpoint/retry reproduction failed with KeyError before this safeguard.

Unlike the cavern flames, all six temple frames have the same alpha outline
and cover every changing pixel opaquely. The static image can remain beneath
its live replacement without leaving an old flame behind. The renderer tracks
which candle pixels survive later **background** pieces; the existing
foreground pass still covers them normally. A plain paste otherwise paints
over the floor at the lower-right corner of level 10 room 1's candle, among
other overlaps. The visibility masks belong to the existing cached room,
including mechanism variants; animation does not rebuild the background.

## Native checks

`tools/probe_temple_candles.py` runs original CODE in Unicorn:

| Check | Scope and supplied endpoints | Result |
| --- | --- | --- |
| Temple frame selection | All 36 previous/random pairs, 10:12b6; only Rnd supplied | 0 differences |
| Cavern frame selection | All 81 previous/random pairs, 8:3b4e; only Rnd supplied | 0 differences |
| Temple initialization | 24 cases, 5:1ffa; supplied cache, visible=true, Rnd and AddTrob sink | 0 differences |
| Old-import source reconstruction | All 128 native rooms; original shape-info source fields versus reconstruction from X/PIEC | 0 differences |

The reconstructed metadata contains 39/26/31/22 logical candles in levels
10/11/12/13, represented by 43/30/36/24 visible clips. These are inventory
counts, not level-completion claims.

An additional local render check runs the native room drawer for all six
phases in room 1 of each temple level: 24 room/phase pictures and 42 candle
clips agree with the live port drawing. The port and this check share the
SHAP decoder. It verifies native frame/position selection and compositing,
not an independent Macintosh raster decoder. The six images were also
inspected in `rendered/temple-candles/six-native-frames.png`.

The room exporter supplies its existing drawing, resource and rectangle
services. TriggerTorch's visibility body (TempVisibleTorch 10:12fa), full
FrameAdv/TROB scheduling, original random seeds and native desktop output
are excluded. No emulator or user's game window was operated.

## Verification and handoff

`tests/test_temple_candles.py` rejects the previous empty metadata and
nine-frame policy; it covers source-cell identity, every temple candle's
initial scenery overlap, six distinct real scene pictures in all four levels,
pause/resume, cache retention, old checkpoint retries and unchanged imported files.

```powershell
$env:POP2_SHARED_DESKTOP = '1'
.venv\Scripts\python.exe -m unittest -q tests.test_temple_candles tests.test_caverns tests.test_temple_playtest tests.test_temple_arrival
.venv\Scripts\python.exe -m tools.probe_temple_candles --source ..\PoP2-Mac-Code-Recovery --output rendered\temple-candles-native.json
.venv\Scripts\python.exe -m unittest discover -q
.venv\Scripts\python.exe run_game.py --check-dependencies
.venv\Scripts\python.exe -m ruff check --select F,E9 .
.venv\Scripts\python.exe -m tools.recovery_catalog --check
git diff --check
```

Final focused scene/cavern/playtest/save/rebirth checks: **202 tests OK, no
skips**. Dependencies, Ruff, recovery catalogue and whitespace checks pass.
The native probe above passes. A separate fresh headless import of the original
image also completes successfully with the new exporter.

Full shared-desktop discovery was attempted but interrupted after its fresh
GUI-import subprocess did not finish within its timeout; it is **not** an
overall passing result. The direct fresh import subsequently succeeded. The
user asked for validation proportionate to this visual patch rather than
letting the global suite delay delivery. Desktop-exclusive checks were not run.
Existing Tk ThemeChanged teardown and Pillow deprecation warnings were observed.

Next bounded step: resume the user's normal temple playtest, starting the game
again to load the new code. Level 12's unresolved complete route is unchanged;
this repair does not certify the wider temple mechanics.
