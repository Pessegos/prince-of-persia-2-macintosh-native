# Standing Down at a ledge

The level 11 comparison shows the Prince leaving native room 32 earlier in
the Macintosh game. He lands on the closing plate at room 29, top row,
column 4 (zero-based). In the port recording he crouches at the edge first
and lands ahead of the plate.

For the ordinary unarmed standing gate, GenCtrl calls the standing handler
at `6:0614`, which dispatches Down to StairClimbing (`6:0d82/0e06`).
StairClimbing consumes Down at `6:0e96`, checks the facing neighbor with
GetCellsInFront (`4:39fc`) and IsSpace (`3:4eb2`), then measures supporting-foot
distance with `4:3a92`. When that distance is below 5, `6:0eb8-0ec6` advances
actor X by 15 in the facing direction and reloads the frame and supporting
column. The active sequence and pose are still the standing ones at
controller exit. AnimChar and CheckFloor then begin the ordinary fall
(`4:35ba → 4:4c1e`). The forward step takes precedence over the rear descent
and the SEQS 50 standing crouch fallback. Running Down has a separate
controller (`6:124a-1262`).

`tools.probe_crouch_ledge` executes these original routines using LEVL 2010
and 2003, Kid FRAM/AFRM 25001, and the original SEQS bytes, with prepared
resource handles and host Memory Manager trap returns. It supplies a
standing type-0 actor at pose 15, SEQS 2 cursor zero, fresh Down, and an empty
moving-object bank. It calls StairClimbing, AnimChar, gravity, vertical
movement, LoadFrame and CheckFloor explicitly. The 13 cases cover both
facings at distances 0–4 and 5, plus a modified temple tile blocking the
forward step. The five admitted temple starts (scene X224–228) all end the
first tick in SEQS 7, pose 102, scene X248, absolute Y245 and row 2
(zero-based). The equivalent left-facing checks use level 4, native room 3.
The probe ends at fall entry and excludes keyboard sampling, the complete
frame caller, sprite collision, room cuts, landing and pressure effects.

The port replays a real Shift-step to scene X224 and Down in level 11.
The first frame matches the native entry tuple. The existing fall and plate
logic then land the Prince at scene X277 in room 29 and activate the closing
plate. With the forward step disabled, the same inputs land at scene X292
with the plate untouched. A separate level 4 replay exercises an unbuffered
Down and the four- versus five-pixel boundary facing left.

```powershell
.venv\Scripts\python.exe -m tools.probe_crouch_ledge --source ..\PoP2-Mac-Code-Recovery
.venv\Scripts\python.exe -m unittest -q tests.test_temple_playtest.TemplePlaytestTests.test_down_from_room32_ledge_lands_on_room29_plate tests.test_run_crouch.StandingCrouchLedgeTests
```
