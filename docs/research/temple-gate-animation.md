# Temple Gate TROB Animation

Research only, based on `86b67a2`. Executes AnimTrob5:0cd6's stored-kind4
dispatch to5:41aa-445c in temple environment2, including the real StopGate
body5:14a8-152e and inert saved-actor reaction5:153c-15a2. It does not port
these routines or change intentional stone-gate improvements in the game.

## Findings

- DATA opening/slow-close steps for phases0..3 are `-1,-4,4,4`. Phase4
  increments to5 **before** subtracting60; subsequent fast-closing steps are
  80,100,120, with phase8 retained until completion.
- Opening phases2/3 request movement sound0x110 only at positions divisible
  by8 in this environment. Normal closing phase1 requests that sound on
  each admitted step. These are cue requests, not sample timing or arbitration.
- Ordinary opening reaching184 stores position237 and phase0. The immediate
  redraw request occurs before that write and observes the old foreground.
  Phase0 then decrements per helper call; equality at184 keeps phase0, and
  position183 switches to phase1. A supplied180/phase2 start reaches closed
  phase-1 after101 helper calls, not a proven rendered-frame duration.
- Phase3 reaching the open limit stores255 and stops. Ordinary closing at
  zero invokes StopGate. Fast closing at/below zero requests the level4
  relief predicate5:4766 and can set the sigh countdown to4 when its supplied
  result is true. A true return is a forced control, not reachable native
  temple relief: the real predicate first rejects every level except4.
- The foreground's high decoration byte is retained. Negative phase skips
  motion but can still request a redraw when the low byte is<=184.

## Evidence

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_gate_animation --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_gate_animation_v2.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_gate_animation_reference
```

**6,300 native/reference comparisons, zero mismatches**:820 at all41
header-admitted original gate anchors,5,120 covering every low position byte
with phases-1..8/forced relief controls, and360 decoration-byte boundary controls.
Original gate counts by level10..13 are7/11/20/3. DATA tables and the native
stored-kind jump target are checked against the actual executable before use.

The full level, gate scratch/OS foreground, phase, relief-countdown word and
ordered cue/redraw/relief/LoadKid requests are compared. Current/saved
actors, TROB bank/count, MOB count, pressure flag and ReadCell cache canaries
remain unchanged. Twelve asset-free tests pin the transition boundaries.

Explicit supplied endpoints:

-5:3828 gate sound: request only;
-5:0fe6 RedrawGate: request only, including observed foreground/phase;
-4:4b02 LoadKid: no-op instead of the real62-byte saved-to-current actor copy;
-5:4766 level4 relief predicate: supplied false/true return value.

Semantic correction after tracing the callees: the initial v1 labels
`support_cache`, `contact` and `damage` were wrong.4:4b02 is LoadKid and
a5-0x5008 is the once-per-level sigh countdown, not pending damage. Native
gate transitions/counts are unchanged; v2 reruns them with correct field and
service names. [Real gate services](temple-gate-services.md) removes both
supplied endpoints and proves the temple rejection and actual LoadKid copy.

Current actor mode0 and saved actor room0 deliberately exclude hanging
reactions. Environment3's special gate/actor branch is not executed. This
probe does not establish actual support/contact geometry, collision/death,
audio/drawing, bank compaction, full FrameAdv, saves or playable temple logic.

Executable SHA256 is
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`;
compared-output digest is
`49ffe048f61b792c7245ce7199528ebd6c3254b7abd6f2a407e41a0900897fe4`.
Original level hashes remain in the ignored report. The subsequent
[mixed-lifetime probe](temple-mixed-lifetime.md) now connects these steps to
the two original mixed chains and stable TROB removal within its stated scope.
