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
| Entry sequence | SetKidDefaults 2:5d98-5e36 | Ordinary standing SEQS 5, static branch reading |

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
