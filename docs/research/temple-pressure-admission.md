# Temple Actor Pressure Admission

Research only, based on `69848f3`. This executes original `CheckPress`
5:127e-13dc, both above/current cell helpers (4:3ff8 and4:35a6), and native
`ReadCell` traversal on temple resources. It does not enable temple gameplay.

## Inputs And Boundaries

The actor record begins at a5-0x5056. Relevant word offsets within it are:

| Offset | Supplied field |
| --- | --- |
| +6 | Native absolute Y |
| +8 | Actor kind |
| +10 | Pose |
| +12 / +14 | Supporting column / row |
| +16 | Movement mode |
| +22 | Room (one-based) |
| +28 | Native ALIVE word, not HP |
| +40 | Selected sequence |

The FRAM auxiliary word (a5-0x520a), floating word (a5-0x4fa6), and view room
are also supplied. Supporting-foot computation, FRAM decoding, controller
input and frame scheduling are not exercised. Column/row caches already name
the supporting cell; no X-origin conversion is inferred here.

Four outgoing routines are request-only sinks:

- PushPlate5:240c, capturing its `(0, -1)` arguments;
- permanent pressure5:252e;
- loose-floor trigger5:2710, capturing argument0;
- temple trapdoor trigger7:36a0.

Their bodies and effects are NOT part of this probe. Earlier plate lifetime
and trapdoor experiments cover their own subsets separately; passing these
isolated blocks is not proof of their combined scheduling.

## Findings

- Actor kinds10/11 return before any cell read. Floating suppresses kind0
  only. Kind1 with selected sequence29..42 inclusive also returns immediately;
  this gate tests the selected sequence, not the displayed pose.
- Poses87..99 and135..140 read above directly, irrespective of movement mode
  or FRAM0x40. They still face the final Y gate.
- Other poses admit signed mode<2 or mode5/7/8. They first read above; only
  then does FRAM0x40 authorize reading the current row. Failed FRAM admission
  leaves the above-cell cache intact without treating that cell as pressed.
- Pose79 with above kind11/15 dispatches directly to loose floor/trapdoor,
  bypassing both FRAM0x40 and the later Y gate. This early path does not write
  the press flag. No equivalent early branch exists for an above plate.
- Ordinary final admission requires Y>=row*120+95. Equality is admitted.
- Plate kinds5/6/34 use ordinary PushPlate if ALIVE<0 or actor kind4;
  otherwise they call permanent pressure. This is not an HP/dead-pose test.
- Ordinary loose-floor/trapdoor requests write a5-0x4f9e=1 first. Plate
  dispatch itself leaves that flag unchanged for its downstream routine.

No production behavior has changed. In particular, the pose79 early branch
is documented as original behavior, not silently added to the runtime.

## Evidence

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_pressure_admission --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_pressure_admission_v1.json
.venv\Scripts\python.exe -m unittest tests.test_temple_pressure_admission_reference -q
```

16,461 native/reference comparisons, zero mismatches:

-3,660 original declared-room cells, including non-pressure controls;
-113 original markers (45 kind5,23 kind6,45 kind11), with actor/ALIVE,
  pose/FRAM, mode, height, float and selected-sequence boundary variants;
-732 linked-column cases, including above-row traversal and missing links;
-2,916 explicitly supplied above/current cell combinations, covering kinds
  34/15 that are absent as original source markers in these levels.

Original markers are admitted by each header's declared room count: the raw
level12 room29 marker is not promoted to a reachable original fixture.

Outcomes:9,143 no request,3,306 ordinary pressure,1,032 permanent pressure,
2,634 loose-floor requests and346 trapdoor requests. Counts are experiment
coverage, not a game-completion score. They include supplied actor states
and positions, not demonstrations that all those combinations occur in play.

Each comparison checks ordered outgoing requests and stack arguments, ordered
ReadCell requests, the complete six-word cell cache, press flag, unchanged
level bytes and unchanged current/saved actor records. Eight asset-free tests
pin the branch boundaries. The native code whitelist rejects unlisted calls.

SHA256:

- Executable: `ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`
- Compared outputs: `b4a1e4e2600898ba7d70be4607d4cd9c568f4196626b20431f76cd2c810f40ba`
- All four LEVL hashes are in the generated report.

## Next Block

Connect this admission to the already recovered pressure/lifetime chain, or
recover target gate TROB animation. Supporting-foot cache calculation and
actual FrameAdv cadence remain distinct requirements. Do not wire the temple
into ScenePrototype/environments during the parallel environment refactor.
