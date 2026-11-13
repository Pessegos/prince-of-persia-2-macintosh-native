# Level 12 jump and catch reports (2026-11-13)

The four supplied Macintosh/port clips expose a confirmed room-2 scheduling
bug and a separate vertical-boundary error in the shared fall admission.
Native room numbers below are one-based. No live game/emulator was operated.

## Room 2 to room 10

Both recordings start at scene X220 (native X427), on row1. Matching the
blue head/pose after rescaling the recorded viewport shows the same airborne
positions before the camera transition. A hidden real-key scene reproduces
the old port's standing SEQS3 jump catching room10's upper platform.

FrameAdv calls CutAllOpponents at **2:6294**, whose player branch loads the
Prince at **6:4390**, then calls CutChar at **6:4394**. AnimChar, gravity,
Move and CheckFloor follow at **2:6372/637e/6382/63a2**. Cut samples the
preceding position. Downward Cut **6:48f2-4902** subtracts360 and recomputes
GetRow. The port instead cut after Move, then advanced the new room's floor
inside Falling in that same tick. That admitted the following frame's grip.

The shared falling-player downward cut now follows Falling, so GetRow's
result belongs to the following tick, as it does in the original. The host
retains its existing camera timing: Y439 moves to445, then cuts to85 in the
same tick. This is a deliberate host scheduling tolerance, not full native
FrameAdv order. An initial implementation moved the camera check before
Move too; it changed the first visible harbor landing pose and the head's
activation timing in an approved ruins route. Keeping the existing camera
event tick preserves those behaviors while correcting the floor state.
In the supplied standing jump, the Prince now
misses the grip and dies in room10. A real-key running jump from X100 over
the intact middle tile still reaches room10's upper platform alive.

The older room14->13 grip tests supplied row2 with absoluteY446, although
Falling had already crossed that row's floor346. Their fixture now supplies
row3 at the same absoluteY. Catch/collapse/guard impact and permanent-grip
controls pass with the corrected scheduling. No collapse expectation weakened.

## Shared vertical window and room 3

Falling **6:011e-0120** rejects Y-floor >=3, then **6:0122-012e** admits
Y-floor >=-48. The resulting interval is **[-48,3)**. The previous port
included3 in Falling modes4/9, granting a final extra grip attempt. The resource-free regression
now distinguishes accepted2 from rejected3. Mode3 calls raw Catch directly;
its existing host admission at3 is retained and tested separately. Full mode3
height admission remains outside this caller correction.

`tools.probe_falling_catch_window` executes the original caller in28 fixtures:
four rows and seven boundary heights. Catch4:37ca is an inert counting sink;
actor type0, velocity33 and the already-set scream flag are supplied.
All28 match. Geometry, animation, floor work after6:0156 and full FrameAdv
are excluded. Original executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.

Room3's supplied clips are not identical takeoffs: at matching airborne poses,
the port is consistently **7 pixels farther right** (e.g. head-left309 versus
302, then391 versus384 at the first free-fall pose). The original Catch with
the corresponding row1/Y196 fixtures refuses X404 and accepts X411. Thus the
recorded port takeoff can catch in the original too. A temporary direct native
DoRunJump6:1c14 diagnostic checked542 room3 X/facing fixtures against the port
alignment with zero differences; JumpSeq and ClearControls were supplied
sinks, original tile readers and distance arithmetic executed. It does not
prove host keyboard/takeoff timing equivalence. No horizontal range constant
was changed, and the exact recorded room3 takeoff is not claimed to become a
miss. Matching the earlier Macintosh takeoff removes the erroneous Y-floor3
last chance; the video's seven-pixel difference remains a timing constraint
for any further control investigation.

## Reproduction

```powershell
.venv\Scripts\python.exe -m tools.probe_falling_catch_window --source ..\PoP2-Mac-Code-Recovery --output rendered\falling-catch-window.json
.venv\Scripts\python.exe -m tools.probe_temple_jump_alignment --source ..\PoP2-Mac-Code-Recovery --output rendered\temple-jump-alignment.json
.venv\Scripts\python.exe -m unittest -q tests.test_ledge_catch tests.test_terrain tests.test_temple_playtest
```

Tests isolate user data; source videos and extracted frames remain ignored.
Neither fix is temple-only. Horizontal/upward cut ordering and complete native
FrameAdv equivalence are outside this change.

The older level12 gate replay depended on the erroneous final-height grip.
A fresh search from its unchanged first47 macros found the replacement tail
`runL8, leapcatchL11, hopcatchL`, followed by a searched safe final macro
`leapcatchR5` (the search's initial `tapL` candidate died after opening them).
Fresh replay retains all three original
held-gate assertions; none was removed or relaxed. Search output remains in
`rendered/route-search-result.json`.
