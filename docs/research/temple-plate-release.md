# Temple Plate Release And TROB Lifetime

Research continuation of [first-press setup](temple-fresh-plate-setup.md).
The unnamed original plate helper at5:2554 was absent from the recursive
disassembly. Reading original CODE5 bytes identifies it as the common target
for stored TROB kinds5/6/34 in `AnimTrob`'s jump table. No production code is
changed. Native rooms are one-based and CODE offsets include the four-byte header.

## Recovered Rules

`AnimTrob` 5:0cd6 calls `CalcBlue` 5:0004 and `GetOS` 5:29a8 for the record's
room/cell. Dispatch uses the stored TROB kind, not the raw tile kind just read.
Kinds5/6/34 branch at5:0d72 to helper5:2554-25a8, then to common foreground
writeback5:0e16. A supplied kind1 control takes the default removal branch.

The plate helper uses the low byte of the first foreground word as its link
index. The timer is signed16-bit:

| Input phase / old timer | Result |
| --- | --- |
| Phase<0 | Preserve phase, timer and foreground; no redraw request |
| Phase>=0, timer>=31 | Phase=-1; preserve timer and depressed bit; no redraw |
| Phase>=0, timer2..30 | Timer decreases by1; preserve phase and foreground |
| Phase>=0, timer<2 | Timer decreases by1; phase=-1; request redraw, then clear0x2000 |

Thus timer5 survives four calls while becoming4/3/2/1, and lifts on the fifth
call, when old timer1 becomes0. Timer31 and larger positive values retire the
record without lifting the plate. Signed underflow is retained: old-32768
becomes32767 and still takes the release branch based on its old value.

The redraw request sees the new timer and old foreground. Common writeback
changes only the first foreground word; the second word is preserved. The
helper never calls `Trigger`, never requests sound and never reverses a linked
rock or gate. This is the plate's animation path, not all possible actor callers.

## Bank Processing

`AnimTrobs` 5:0c38-0cc6 captures the initial count and visits each initial record
in order. It copies the eight-byte record to scratch, calls `AnimTrob`, and
writes only the returned scratch phase into the original record. If any phase
is negative, it then stably compacts all nonnegative records to the front.
Unused bytes after the new count are retained rather than cleared. Final
scratch/OS describe the last record visited, even if that record was removed.
An empty pass preserves scratch, OS and storage.

Timers are updated per visited record, not once per distinct link index.
Supplied records sharing an index can decrement the same timer twice in one
pass. For old timer2, the first record retains phase at timer1; the second
releases at timer0. The first can then release on the next pass. This is a
bank-topology control, not a claim that the real actor path creates duplicates.

## Evidence

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_plate_release --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_plate_release_v1.json
.venv\Scripts\python.exe -m unittest tests.test_temple_plate_release_reference -q
```

10,640 comparisons, zero mismatches:

- 6,800 direct `AnimTrob` calls over all68 header-admitted original temple
  plates (8/20/31/9 in levels10/11/12/13), ten timer boundaries, five phases
  and both depressed-bit states. No native kind34 markers occur in this inventory.
- 3,840 persistent `AnimTrobs` calls over supplied bank counts0/1/2/5/20,
  timer boundaries, distinct/shared timers, negative phases and default kinds.
  Eight consecutive passes per fixture, with original headers from all four levels.
- 2,560 redraw requests observed. Thirteen asset-free regressions cover release,
  ordering, overflow, shared clocks, stored-kind dispatch and stable compaction.

Whole-level bytes, count, full bank including unused storage, scratch, OS words,
ordered visits/redraws and unchanged cell cache, both actors, MOB scratch/count,
pending sound and press flag are checked. The native jump-table targets for
kinds5/6/34 are verified before executing the matrix.

SHA256:

- Executable: `ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`
- Compared outputs: `3b324340c5163ab94e1f82d9bddae68cfd7e99ea55b02be4ee5c5e20670efa11`
- Original LEVL hashes and full source inventory are in the local JSON report.

## Boundary

`RedrawPlate` 5:0f38 is a supplied no-op request sink recording scratch room/cell,
OS foreground and timer. Native rectangles/redraw queues/pixels remain outside
the experiment. All other executed bodies are original instructions. No actor
pressure, target activation, gate animation, actual FrameAdv cadence, file saves
or campaign equivalence is established. Scheduling of the supplied bank passes
does not measure real time. Header-admitted raw markers are not a reachability
proof for their rooms.
