# Temple First-Press Setup

Research-only continuation of [mixed pressure links](temple-mixed-plate-links.md).
This adds the fresh timer<2 path in native `PushPlate` 5:240c, with explicit
audio/redraw request sinks. It does not change the playable port. Native rooms
are one-based, cells/link indices zero-based; CODE offsets include the header.

## Decision And Ordering

The tested entry arguments are `(0, -1)`: use cached source kind and low-byte
foreground link index after native `ReadCell`. Explicit argument overrides are
not part of this probe. The original saves source room, cell and foreground
before linked target processing can change the cache.

| Original signed link timer | Work before Trigger |
| --- | --- |
| 31 | Leave timer unchanged; no source TROB/audio/redraw setup |
| >=2, except31 | Set timer5; no source TROB/audio/redraw setup |
| <2 | Set timer5; request source TROB phase1; conditional sound27; redraw source |

Fresh-path order is:

1. `ChangeLinkTimer` 5:22b8 writes5.
2. `AddTrob` 5:20a0 requests `(source room, source cell, phase1, source kind)`.
3. Unless pose185 or level13/source room4, call `AddSound` 5:4d84 with27.
4. Call `RedrawPlate` 5:0f38.
5. Run `Trigger` 5:1c4c and its gate/rock targets in stored order.
6. Set A5-4f9e to1 (held/permanent paths leave its prior value untouched).
7. Write saved source foreground OR0x2000 to the source cell.

The redraw request therefore sees the source's previous depressed-bit state.
Setting that bit beforehand does not suppress first-press setup when timer<2.
The branch checks pose185 specifically, not the entire `IsDeadPos` predicate.
The room4 sound exception requires level13 as well; supplied room/level controls
separate this from an unconditional room4 or level13 suppression.

## Capacity Consequences

The source plate competes with its gate target for TROB capacity. With19
nonmatching records, a fresh press takes the last slot for the plate. A missing
gate TROB cannot then be appended. Gate foreground changes still occur before
the failed append; no rollback occurs. Sliding-rock activation uses the separate
MOB bank and still runs.

A matching source TROB is updated in place, including at capacity, retaining
its kind even if the supplied record has a different kind. No slot is consumed
by that update. If the source itself cannot be appended, sound/redraw requests,
link traversal, the flag and final source write are still performed.

On the next immediate call, the refreshed timer5 takes the held path. It does
not repeat the initial sound/redraw or source registration. This experiment
does not advance animation or decay timers between its two calls.

## Fixtures And Evidence

Original admitted sources containing rock targets:

| Level | Native room / cell |
| --- | --- |
| 10 | 28 / 24 |
| 11 | 3 / 15, 3 / 16, 29 / 4 |
| 12 | 1 / 21 |
| 13 | 5 / 18, 16 / 17 |

Raw level12 room29/cell4 remains excluded: it lies beyond the declared26 rooms.
Three explicitly synthetic source placements/header controls test level13
room4 sound suppression. They are not additional original gameplay sources.

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_fresh_plate_setup --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_fresh_plate_setup_v1.json
.venv\Scripts\python.exe -m unittest tests.test_temple_fresh_plate_setup_reference -q
```

4,800 comparisons, zero mismatches:3,360 calls on original-source fixtures and
1,440 calls on supplied sound controls. Each fixture runs two consecutive calls
with persistent banks/level/cache. Inputs cross timers-1/0/1/2/31, both depressed
bit states, poses0/185, three MOB banks and four TROB banks. Native sinks record
648 sound requests and1,440 redraw requests. Ten asset-free regressions pin
ordering, capacity, suppressed sound, final source writes and the held transition.

Checks include full level bytes, complete banks/unused storage, counts/scratch,
ordered source/target/sound/redraw calls, redraw-time source foreground,
native ReadCell requests/cache, unchanged working/saved actors, press flag and
unchanged pending-audio canary (the audio endpoint is supplied).

SHA256:

- Executable: `ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`
- Compared outputs: `2660494493845a85cfc5023bf37f1d473d1d4f29d7625b670a7b94868254cc53`
- Original LEVL hashes are recorded individually in the local JSON report.

## Supplied Boundaries

Two native bodies are deliberately replaced by no-op request sinks:

- 5:4d84 `AddSound`: record cue27, return0. No native sound priority, pending
  queue, playback or port audio-overlap behavior is certified.
- 5:0f38 `RedrawPlate`: record source coordinates and its foreground, return0.
  No native rectangle calculations, redraw queues or pixels are certified.

All link, gate, rock, TROB and source/timer writes execute original instructions.
Caller scheduling and actor context remain supplied. Actual pressure admission,
release/timer decay, TROB animation/removal, combined motion/contact/drawing,
FrameAdv cadence and save/checkpoint/reset remain open. This is neither a
full original frame trace nor proof that these temple levels are playable.
