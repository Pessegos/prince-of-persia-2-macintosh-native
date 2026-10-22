# Level Seven Preparation

This is an independent research track, not an enabled campaign level. The
baseline is `5dfc13a`; levels 1-6 and shared runtime integration belong to the
parallel campaign track. No gameplay, importer, save or README changes are
part of this preparation.

## Reproducible Resource Inventory

Run against a local read-only original recovery directory:

```powershell
python -m tools.inspect_level7 --source PATH_TO_RECOVERY --output rendered/level7-inventory.json
python -m unittest -q tests.test_inspect_level7
```

The command reads resource forks, never the user's running game or emulator.
Its detailed JSON stays local: it includes the 32 rooms' tile words and raw
generator records and is not a distributable scenery program. Unit tests use
synthetic records without original resources. The inventory shares the port's
LEVL decoder; it is not an independent native comparison of that decoder.

## Identity And Dependencies

Original `Prince.rsrc` LEVL 2006 identifies level 7, environment 4. It starts
in native room 32, cell 24, facing word 0xffff (port facing 1, right). All
32 rooms are reachable through room links; this is topological reachability,
not proof that the Prince can traverse every route. Checkpoint slot 2 is
room 3, cell 0; slot 1 is empty. Preserve the slot number rather than
renumbering the surviving checkpoint.

The executable's expanded A5 file tables select:

| Dependency | Original Evidence | Level-Seven Value |
| --- | --- | --- |
| Scenery resource fork | OpenLevelRsrcFile 3:51fa, six-byte entries at A5-0x4724 indexed by environment | `Ruins.rsrc` |
| Opponent resource fork | LoadOppSet 3:5f58/6014, entries at A5-0x464a indexed by LEVL +0x21a4 | `Head.rsrc`, set 5 |
| Prince palette | SetKidPalette 3:5f1c, CTBL 25000 + environment | CTBL 25004 |
| Entry sequence | SetKidDefaults 2:5d98-5e36 | Ordinary standing SEQS 5, original selector executed to just before JumpSeq |

Level 6 also uses environment 4 and opponent set 5. A future ruins renderer
and special-actor support should therefore be shared between levels 6 and 7,
not copied into a separate level-seven controller. Do not substitute Temple
(environment 2), Birdhead or the ordinary-guard decoder for these assets.

`Ruins.rsrc` has 131 SHAP, three CTBL, one PIEC and nine CUST resources.
`Head.rsrc` has 130 SHAP, three CTBL and FRAM/AFRM/SHPL 750. LoadOppSet
3:60a6-60c8 also requests resource 755 of type zero for sets 5/6. Its
contents need separate investigation; the inventory does not interpret it.

IsCustomizedRoom 3:1310 checks foreground bits 0xc000. None of level 7's
rooms set them, so no CUST room is required by that check. This does not
mean no animated or special scenery is needed.

## Mechanism And Actor Inventory

The original level has 14 initial generator records in ten rooms:
2, 3, 7, 9, 10, 20, 22, 24, 29 and 31. Six records start with SEQS 170,
the other eight with SEQS 130. These are raw generator fields, not proof
of actor controller semantics or complete dynamic spawn counts.

In particular, the set number 5 is not an instruction to make every actor
type 5: the records' +0x18 words contain six 5s, two 6s and six 8s. This
mixed metadata needs the native initialization/dispatch path; copying the
ordinary-guard constructor with a new palette would discard it. The native
selector/dispatch probe below now establishes their distinct actor types.

Potential integration targets, retaining native room/cell numbers:

| Data | Locations | Interpretation / Limits |
| --- | --- | --- |
| Tile 7, 17 cells | Room 1 cells 20-24; room 5 cell 29; room 18 cells 13-19; room 19 cells 14-17 | Ruin crevices, see DrawRuinCrevice 7:2344 and RuinSetCreviceRevealed 7:3404; foreground low bits and bit 0x80 matter |
| Tile 4, six cells | 1:13, 11:0, 12:21, 15:27, 20:16, 32:28 | Gate mechanisms; generic cavern artwork cannot be reused |
| Tile 10, nine cells | 2:27, 6:15, 7:18, 11:12, 19:12, 22:1, 24:3, 29:27, 30:19 | Flask metadata needs native type decoding; no claim all are health potions |
| Tile 21, eight cells | 1:12, 2:25, 10:23, 15:28, 16:16, 23:20, 24:0, 29:10 | Ruins-specific rendering/behavior must be checked before treating as ordinary floor |
| Tile pair 16/17 | Rooms 4, 21 and 32 | Exit/entry pieces; room 32 contains the starting entrance, not necessarily a usable campaign exit |

Counts come from all 960 cells in the original resource. Level seven also
has tile types 0, 1, 3, 5, 6, 8, 9, 11-15 and 20. Listing a tile is not
recovery of all its behavior.

## Native Entry Points To Investigate

- RuinSetCreviceRevealed 7:3404 is called by character control only for
  environment 4 at 6:0814 and 6:09ac. It rejects selected sequence 17,
  asks GetCellsInFront(1), and requires tile 7 whose foreground low two
  bits are not 3. It then calls the helper at 7:332a with reveal=1.
- Do not call the named RuinChangeCrevices jump target 7:3328 expecting
  that helper: the actual exported entry is an immediate RTS. The scan
  routine starts two bytes later. Name ranges in the symbol index can
  conceal this distinction.
- HeadAttackProg 7:064c, HeadLockedProg 7:1164, IsHeadLockedOn 7:16b8
  and SnakeComeOutOfHole 7:1824 describe a special actor family, not an
  ordinary guard reskin. Controller dispatch and all persistence fields
  still need independent traces.

## Integration Gates

1. Original ruins draw/export and palettes, including crevice state variants.
2. Special-actor decoding, activation, collision, neck attachment and removal.
3. Native entry/exit and story selection for 6 -> 7 -> 8.
4. Mechanisms present in this level and checkpoint/save semantics.
5. Headless regressions followed by coordinated in-game comparison.

The inventory does not make level 7 playable, decode its art or prove AI,
movement, timing, full-level solvability or visual equivalence. No source
resources are bundled. Native probes and later milestones must state their
supplied endpoints and exclusions separately.

## Native Crevice And Entry Probe

```powershell
python -m tools.probe_level7_rules --source PATH_TO_RECOVERY --output rendered/level7-native-rules.json
python -m unittest -q tests.test_inspect_level7 tests.test_probe_level7_rules
```

The probe executes the original 68000 instructions with Unicorn. It loads
the real DATA/ZERO, jump-table targets and LEVL 2006; its comparison model
uses its own narrow decoder, not the port's LevelMap. Every instruction
must stay in a declared routine range, a relocated jump stub or an explicit
supplied service. Each call has a 50,000-instruction limit and must reach
its designated stop. Errors/differences abort the command.

Results on the preserved executable (SHA-256
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`):

- Helper 7:332a: 1,920 cases, all 960 actual cells with reveal=0/1.
  74 cases change the level bytes; zero native/reference differences.
- Front trigger 7:3404: 3,840 cases, all cells, both native facings and
  selected sequence 5/17. 26 cases change the level bytes; zero differences.
- Another 31 supplied-foreground controls force low bits to 3 at actual
  crevice cells adjacent to an in-room actor: all reject revelation.
  These are counterfactual controls, not untouched level fixtures.
- 7:3328 returns without changing the level or calling a supplied service.
- The original entry selector returns SEQS 5. Execution stops at 2:5e36,
  before JumpSeq; this is not a complete SetKidDefaults/entry-animation test.
- GetEndSong 5:4e0c returns 124, not the cavern cue 32. IsTimeForNIS
  2:00e8 returns false for the tested fresh and resumed level-seven entries
  with demo/disable/death fields cleared. This does not bypass or recover
  the separate CheckPlayNIS tree-scene decision between campaign levels.

### Recovered Mutation Rule

The scan helper does **not** only search two or three cells around the actor.
It scans columns `min(actor_column - 2, 0)` through
`max(actor_column + 3, 10) - 1`, finds the first tile-7 group, walks left to
its start, and then changes the entire contiguous group. Native ReadCell
follows horizontal links, so a group can cross a room boundary. It stops at
the next non-7 cell, rather than affecting every separate crevice on the row.

Reveal sets foreground bit 0x80; hide clears it. All other bits are retained.
The front-trigger wrapper rejects selected sequence 17, a non-7 front tile,
or a front tile with low bits equal to 3, otherwise invoking that scan with
reveal=1. Existing bit-0x80 cells are not evidence of a different tile kind.

### Exclusions And Supplied Endpoints

- IsVisibleRoomCell 5:3960 returns false; redraw 5:1936 returns without
  drawing. No native visibility result, redraw side effect or pixels are
  certified. Neighbor-redraw call sites still execute around these stubs.
- ReadCell, CalcBlue, FirstInRow, GetCellsInFront and the original direction
  tables execute natively. No port collision/geometry decoder is substituted
  for them. The reference covers in-range rows and horizontal traversal only.
- Actor positions, facing and selected sequence are supplied independently.
  The probe does not establish that every supplied state is reachable in
  ordinary play, or recover controller/frame scheduling.
- Full-level byte comparisons cover the crevice mutations, not CPU flags,
  all A5 scratch fields, special enemies, audio playback or timing.

The 16 synthetic unit tests validate inventory/reference edge cases without
assets; they do not independently rerun the native comparisons. Runtime
integration, visual variants and the special-actor controllers remain open.

## Native Special-Actor Selection And Lock Predicate

```powershell
python -m tools.probe_level7_actors --source PATH_TO_RECOVERY --output rendered/level7-native-actors.json
```

The executable's `InitOpps` preserves each record's +0x18 kind when the
level's opponent set is 5 or 6 (6:2bd2-2bfe). It then converts that kind
through the original DATA table at A5-0x5280 (6:2bfe-2c0e). These are three
different concepts: resource set, record kind, and working actor type.

Executing that original selector for all 14 actual records, followed by
the original AutoCtrl dispatch at 6:4eb6, establishes:

| Record Kind | Working Actor Type | Count | Controller Entry |
| --- | --- | --- | --- |
| 5 | 7 | 6 | 7:1324, head controller |
| 6 | 8 | 2 | 7:1324, head controller |
| 8 | 11 | 6 | 7:1824, SnakeComeOutOfHole |

The eight head-family records start at SEQS 130. The six snake-family
records start at SEQS 170, in rooms 3 (two), 20 (one), 29 (two) and 31
(one). This is not a reconstruction of their complete spawn behavior.
The two head actor types share an entry point, but that does not establish
identical movement, collision or art selection.

`IsHeadLockedOn` 7:16b8 calls the original GetOppInfoIdx 6:3642, returns
false for a missing record, and otherwise tests whether record word +0x1c
equals 3. A positive result does not independently test life/ALIVE, range
or facing. There were zero differences in 144 supplied head-record cases
(eight actual slots x six mode values x three life values), with no changes
to the level bytes. Another 33 missing-record controls (one-past-count in
each room and room 0/slot 0) return false.

No services are stubbed in this actor probe. A3 and working actor type are
supplied for the two selector/dispatch slices; mode and life fields are
supplied for the predicate controls. Execution stops before CheckLoadedOppSet
at 6:2c12 and before entering either AI controller. This establishes the
kind conversion, routing and narrow lock predicate, **not** full InitOpps,
neck attachment, bite/damage, knock-off, flight, snake activation or actor
record persistence. Invalid negative slots are not certified.

### Follow-Up From The Initial Milestone

Trace the eight head-family records through HeadAddOpponent 7:0574 and
the mode dispatch at 7:1324 with real FRAM/SEQS data, keeping the Prince's
cached state and generator record separate. Record mode transitions and
services before translating a controller. Investigate SnakeComeOutOfHole
separately; do not apply the head mode layout to its records by assumption.
The autonomous continuation below covers initialization, frame loading and
bounded wrapper routing. Full AI leaf effects and animation/cadence remain open.

## Autonomous Continuation

The next initialization and frame-loading blocks are now recorded separately:

- [Head/serpent initialization](level7-head-initialization.md): complete native
  HeadAddOpponent, including signed ALIVE behavior and kind-zero fallback.
- [Special-actor frame loading](level7-frame-loading.md): original FRAM/AFRM
  loading for all tested head/serpent pose combinations, including type-8 remap.
- [Head mode routing](level7-head-mode-routing.md): original wrapper with
  native frame/record loading, supplied visibility and inert AI leaves.
- [Neck alignment](level7-neck-alignment.md): full original coordinate helper,
  native drawn-object lookup and actual alignment metadata/sprite dimensions.

These results do not enable the campaign or claim complete special-actor AI.
