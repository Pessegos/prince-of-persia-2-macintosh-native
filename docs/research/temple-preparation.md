# Temple Preparation

Independent research, baseline `da0b021`, branch `codex/temple-preparation`.
The level-six/ruins runtime integration remains on the parallel campaign
track. This work does not enable temple gameplay, import scenery, change
saves/README or claim complete AI equivalence.

## Resource And Level Inventory

```powershell
python -m tools.inspect_temple --source PATH_TO_RECOVERY --output rendered/temple-inventory.json
python -m tools.probe_temple_headers --source PATH_TO_RECOVERY --output rendered/temple-native-headers.json
python -m unittest -q tests.test_inspect_temple tests.test_temple_headers_reference
```

The inventory reuses existing LevelDefinition/LevelMap readers; it is NOT
independent native proof of the whole decoder. Its full room/record JSON
stays ignored locally. Unit tests contain synthetic fixtures only.

All four levels use environment 2, opponent set 7: Temple.rsrc,
Birdhead.rsrc and Prince palette CTBL 25002. These are not the ruins/head
assets used by levels 6-9. File-table selection follows 3:51fa/5f58,
as in the earlier resource inventory.

| Level | LEVL | Start Room:Cell | Checkpoints, Native Slots | Initial Generators | Link-Reachable Rooms |
| --- | --- | --- | --- | --- | --- |
| 10 | 2009 | 22:23 | none | five raw kind7, SEQS77 | all32 |
| 11 | 2010 | 5:25 | slot2 =6:17 | two raw kind7, SEQS77 | all32 |
| 12 | 2011 | 19:22 | slot1 =11:10; slot2 =2:9 | three kind7/77; one kind1/105 | 1..26 |
| 13 | 2012 | 3:14 | slot1 =32:19 | three raw kind7, SEQS77 | 29 rooms; excludes21/23/26 |

Link reachability is not gameplay traversability/solvability; omitted rooms
are not automatically broken or intended destinations.

Temple.rsrc contains 123 SHAP, one CTBL, one PIEC, one SHPL and CUST
4025/4075. Birdhead.rsrc contains FRAM/AFRM/SHPL750 and one CTBL750.
Its FRAM has 108 ten-byte records and AFRM has 85 eight-byte records;
do not substitute the Head bank's single attachment record.

### Custom Room Caveat

Native IsCustomizedRoom flags level13 rooms2/4/26, and none in levels10-12.
Candidate IDs are4025/4075/4625. The first two are present in Temple.rsrc;
4625 is absent in that preserved fork and in the other checked resource
forks. Room26 is not link-reachable from the supplied level13 start.

This is not proof of corruption, a fatal importer dependency or a playable
missing room. Static LoadCustomRoomData3:1378 tests a null GetResource result
at3:13a6 and branches to return; full loading/fallback behavior still needs
an independent trace, including old custom state and callbacks.

## Native Header Results

Original executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
The two ignored reports record original level hashes.

| Rule | Source | Evidence / Scope |
| --- | --- | --- |
| Entry selector | 2:5d98 to before5e36 | R: four original headers; level10 selects2 and sets nativeX430; others select5 and preserve supplied X |
| End-song selector | 5:4e0c-4e42 | R: all four return187; no sound playback |
| Custom-room predicate | 3:1310-1362 | R:128 actual-room queries +16 supplied high-bit controls |
| Actor kind conversion | 6:2bca to before2c12 | R:210 selector invocations across14 actual slots with raw-kind controls; no full InitOpps |

All comparisons pass; no native services are supplied in this header probe.
13 asset-free unit tests cover inventory/reference branches, not original
execution. `R` means recovered/reference, not implemented gameplay.

The kind selector uses the level set7 for ordinary kinds, preserving only
exceptional raw kinds1/3/9/10. The original DATA table maps actual raw7
to **working actor2**, and the level12 raw1 at room7/slot0 to **actor10**.
Set number, generator kind and working actor type are different concepts.
This does not establish identical ordinary-guard/Birdhead AI or initialization.

Entry testing stops BEFORE JumpSeq/AnimChar. Native X600 is a canary for
the non-level10 selectors, not their actual spawn coordinate. Actual entry
position, SEQS2 execution, level9->10 story playback and restarts remain open.
The nativeX430 special selection corresponds to portX223 under the usual
207-pixel conversion, not the header's portX175. Do not simply reuse the
generic header start when integrating that entry.

## Mechanism Priorities And Integration Gates

The inventory retains candidate tile IDs without assuming all behavior:

- Tile25:2/2/6/2 cells by level10/11/12/13. Sliding-rock machinery is in
  CODE10, including TriggerSlideRock10:2152 and ATMSlideRock10:1456.
- Tile26:3/1/3/3 cells. Falling6:0210 and ShakeEm5:28c8 call
  TriggerTrapDoor10:25aa. Its constructor10:25e8 and ATM10:225c need
  separate state/animation/collision traces, not an ordinary loose-floor alias.
- Tile43 occurs once, level13 room4/cell11. Altar/shadow/flame logic and
  NISTemple15:5fd4 are separate targets; no behavior inferred from the tile alone.

The first bounded mechanism block is now recorded in
[trap-door triggering](temple-trapdoors.md): actual cells, full native
constructor/append/capacity handling, explicit sound/redraw boundaries.
Animation, caller scheduling and collision remain open. Then investigate
sliding-rock activation/persistence, temple draw
dispatch/custom callbacks, Birdhead combat/frame data, altar/flame/story rules.
Do not treat this list as complete temple rule coverage.
