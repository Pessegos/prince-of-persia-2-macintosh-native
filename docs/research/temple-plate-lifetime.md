# Connected Temple Plate Lifetime

This joins [first pressure](temple-fresh-plate-setup.md) and
[release/compaction](temple-plate-release.md) in one native machine with
persistent level bytes, MOB/TROB banks, scratch, OS words and cell cache.
The deliverable is research evidence; no playable runtime is changed.

## Source And Operation Scope

Five original, header-admitted sources have rock-only chains:

| Level | Native room / cell |
| --- | --- |
| 10 | 28 / 24 |
| 11 | 29 / 4 |
| 12 | 1 / 21 |
| 13 | 5 / 18, 16 / 17 |

All five sources are kind6. The mixed gate/rock sources in level11 room3 are
excluded because this block does not animate target gate TROBs. Raw level12
room29/cell4 remains excluded by its header's declared room count.

Two supplied operations execute original instructions:

- `press`: native `ReadCell` 4:27ee, then `PushPlate` 5:240c with cached defaults.
  This includes `Trigger`/`TriggerObject`, rock lookup/activation and `AddTrob`.
- `animate`: native `AnimTrobs` 5:0c38, stored-kind `AnimTrob` 5:0cd6, original
  plate helper5:2554, phase writeback and stable compaction. Supplied kind1
  records take the native default-removal branch.

The harness supplies three schedules: tap/wait/re-press, repeated pressure
before animation, and animation before repeated pressure. These explicitly
test operation ordering; neither repeated schedule claims native FrameAdv order
or measures elapsed game time. Rock motion, contact and drawing are not advanced.

## Connected Findings

- A fresh press creates a source phase1 TROB and activates its rock. Five
  uninterrupted animation calls from timer5 lift and remove the source. A new
  press then registers the source again and reuses the existing rock record.
- With pressure immediately before each animation, timer5 is refreshed and
  becomes4 each pass; source and rock records do not accumulate duplicates.
  When pressure stops, four further animation calls release that timer4 source.
- Pressure after animation instead ends at timer5, requiring five subsequent
  calls to release. This is why an eventual integration must follow the actual
  frame order rather than infer cadence from the timer's name or value.
- Release does not call the rock trigger or change its control word. An ordinary
  existing rock activated by kind6 remains forced at-2 after the plate lifts;
  terminal100 remains100. Other callers are needed for mode5/how2 behavior.
- Animation uses source TROB scratch and OS, while the separate ReadCell cache
  can still name the rock last read by its constructor. Both persist independently.
  The release redraw sink records the source coordinates, not stale cache data.
- Timer31 pressure keeps the source depressed without an animation record or
  repeated first-press sound/redraw. This is the permanent branch, not a leak.

### Supplied Capacity Controls

If a fresh source cannot register because20 unrelated TROBs already occupy the
bank, `PushPlate` still sets timer5 and the source depressed bit. Once the
unrelated default-kind controls are removed, the source has no TROB to decrement
its timer. A subsequent pressure sees timer>=2, takes the held path and does not
register it. In these fixtures it remains depressed with timer5.

Animating those default controls before the first pressure frees capacity in
time, and normal release follows. This is a counterexample under supplied bank
states; it does not establish that ordinary gameplay reaches that situation.
No production safeguard or original-behavior change is introduced here.

MOB capacity remains independent: rejecting rock creation at30 records does not
prevent a successfully registered source from releasing and being compacted.

## Evidence

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_plate_lifetime --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_plate_lifetime_v1.json
.venv\Scripts\python.exe -m unittest tests.test_temple_plate_lifetime_reference -q
```

600 persistent traces, 14,400 operation comparisons, zero mismatches:

| Group | Count |
| --- | ---: |
| Native pressure operations | 4,000 |
| Native TROB animation operations | 10,400 |
| Sound requests observed | 550 |
| Redraw requests observed | 1,050 |

Each source crosses three schedules, timers0/31, five MOB states and four TROB
states (empty,19/20 default controls, full with an existing source). All final
states match:250 traces released at timer0,300 permanent traces retain31, and
50 capacity controls retain5. The350 depressed sources without TROBs comprise
the300 permanent cases and50 supplied capacity cases, not350 gameplay defects.

Checks compare the entire level, banks/unused storage/counts/scratch, OS words,
ordered native calls and redraws, ReadCell requests/cache, press flag, actors
and unchanged pending-audio canary after every operation. Ten asset-free tests
pin ordinary re-registration, held refresh, ordering, capacity, permanent
sources, frozen rock controls and independent cache/OS state.

SHA256:

- Executable: `ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`
- Compared outputs: `def2efb6e210ffebb34b4a6416173572a7c9a59c24f3f0455ff333be5186f489`
- Original LEVL hashes are recorded in the linked first-pressure/release reports.

## Supplied Boundaries

`AddSound` 5:4d84 and `RedrawPlate` 5:0f38 remain no-op request sinks. The latter
uses the source ReadCell cache for pressure calls and TROB scratch/OS for release
calls. No real sound priority/playback, rectangle effects or pixels are verified.
Actor input/pressure admission, target gate animation, rock motion/contact/drawing,
actual FrameAdv order and save/checkpoint/reset remain separate. These traces
do not make the temple campaign playable or certify a complete game frame.
