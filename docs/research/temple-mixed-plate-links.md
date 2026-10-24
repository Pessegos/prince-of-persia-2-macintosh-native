# Temple Mixed Gate/Rock Pressure Links

Research-only continuation of [caller admission](temple-slide-rock-admission.md).
No production controller, renderer or frame order changes. Native room numbers
are one-based; cells and link indices are zero-based. CODE offsets include the
resource's four-byte header.

## Original Chains

Level11, native room3 has two pressure chains containing both kinds:

| Source cell / kind | Link chain | Targets in execution order |
| --- | --- | --- |
| 15 / 6 | 54 -> 50 -> -3 | Gate3:2, rock3:18 |
| 16 / 5 | 51 -> 52 -> -3 | Rock3:18, gate3:2 |

These are the two mixed chains excluded by the earlier admission probe. Both
sources are within the declared room count. The resource chains and target
kinds are checked before running fixtures; bank, actor and foreground states
are supplied, not claimed to be captured gameplay states.

## Recovered Behavior

- `Trigger` 5:1c4c traverses both targets in stored order. A negative return
  from `TriggerObject` 5:1ec8 skips `AddTrob`, not subsequent links.
- Gate4 uses `TriggerGate` 5:1d50. Rock25 uses 10:2152 and returns-1 even if
  it created/changed a MOB. Thus its activation never consumes a TROB slot.
- `GetTrobRoomCell` 5:38a6 selects the first `(cell, room)` match. It does not
  filter kind or negative phase. `AddTrob` 5:20a0 updates only that record's
  phase, retaining its kind and leaving scratch untouched.
- With no match, `AddTrob` appends only below20 records. It writes its four-word
  scratch only on successful append. At capacity, an existing record can
  still be updated. Record layout is `(cell, room, phase, kind)`.
- MOB capacity30 and TROB capacity20 are independent. Failure to append a
  gate TROB does not prevent rock creation; failure to append a rock MOB does
  not prevent gate activation. Gate foreground changes can precede TROB
  capacity rejection; this is not an atomic transaction with rollback.

For source mode5, gate foreground high-byte decoration is preserved. Low-byte
255 does nothing. Below184 the new low byte is `(position+3)&0xfc`. At/above184
it becomes237 or255. The choice and requested TROB phase depend on native
ALIVE at A5-503a and transition-room context A5-4fc4, not a generic HP boolean:

- ALIVE>=0, or a nonzero transition room different from actor room: phase3;
  low byte255 in the upper band.
- Otherwise: phase2 below184; low byte237 and no TROB request in the upper band.

For source mode6, no foreground write occurs. It requests phase4 except when
the native dead-pose predicate is true with ALIVE>=2, an absent TROB accompanies
position0, or the first matching TROB already has phase4. Native `IsDeadPos`
4:47a0 executes for supplied kind-zero actors on level11; other actor kinds
and the level-five special branch are outside this experiment.

Held `PushPlate` 5:240c (timers2/5/31) executes both mechanisms. It refreshes
non31 timers to5, then marks the saved source foreground with0x2000 after the
chain. The rock constructor can replace the global cell cache; the final write
still addresses the source plate. Repeated calls do not duplicate bank records.

## Evidence

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_mixed_plate_links --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_mixed_plate_links_v1.json
.venv\Scripts\python.exe -m unittest tests.test_temple_mixed_plate_links_reference -q
```

9,206 native/reference comparisons, zero mismatches:

| Group | Comparisons |
| --- | ---: |
| Both resource chains, eight boundary positions, eight actor contexts, seven TROB and five MOB banks | 4,480 |
| All256 position bytes through both chains and eight actor contexts | 4,096 |
| Held/permanent plate traces, three consecutive calls | 630 |

All native services execute; no service endpoint is supplied. Tests compare
the full level, both banks including unused bytes, both scratch records,
working/saved actor canaries, cell cache/reads, ordered object/rock/TROB calls
and unchanged sound/redraw flags. Fifteen asset-free tests pin first-match,
capacity, ordering, context, decoration and repeated-source-write behavior.

SHA256:

- Executable: `ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`
- LEVL2010: `3f3559f2d1dd4853098d9a812692a69a64fd86ac1ae677745f8fea6cdb6f1664`
- Compared outputs: `47c357db3debe59dfa07132421f0caa6f6b9b6a60c9eadea160607df70e83936`

## Boundaries

This establishes activation and held calls, not fresh timer<2 plate setup,
actual actor pressure admission, gate motion, combined gate/rock updates,
frame cadence, visual output or save/reset parity. Gate modes14/34 and other
actor kinds remain excluded. The raw out-of-range level12 room29 source from
the earlier inventory is not made playable by these results. No GUI, importer,
main-branch runtime or Claude-owned architecture code is changed.
