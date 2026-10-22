# Unmapped Code Sweep (CODE 2-8)

Research note, 2026-10-22, `claude/ai-research`.

The recovery listings (`code/NN.asm`) leave some real code as
`; unmapped XXXX-YYYY`. The level-four relief sigh (sound 110) sat in one of
them (ATMGate, CODE 5 `4198-4681`), so a search of the listings alone missed
its writer.

## Method

- Function starts came from the public declarations of an independent static
  recompilation of the same Macintosh program (GitHub `mac-recomp/pop2`,
  `gen/gen_decls.h`, 2,159 functions named `f<segment>_<offset>`). The
  repository states no license, so it is used only as an index of addresses;
  no code was copied. Its offsets equal our listing offsets.
- 53 of those starts in CODE 2-8 fall inside unmapped regions. Each was
  disassembled from the original CODE resource with capstone (68020 mode),
  naming jump-table and PC-relative calls from `jump_table.csv` and
  `symbols.csv`.

## Results

| Function | Content | Port status |
| --- | --- | --- |
| `5:41aa` | ATMGate | implemented; the relief branch `5:42c6-42ce` was missing (now added) |
| `5:4766` | relief predicate (level 4) | implemented |
| `5:15bc` | ATMExit | implemented; ResetSoundItem(0) before sound 18 not reproduced |
| `5:4396-43bc` | level 5 room-7 gate double step | noted, not implemented |
| `5:1446`, `5:16aa` | torch animation (CaveGetTorchFrame, TempGetTorchFrame) | implemented for caverns |
| `5:2554` | plate link timers | implemented |
| `5:2b10`, `5:2c36`, `5:2f42`, `5:2fd6`, `5:446a` | loose-floor shake, fall and impact | implemented (`pop2/loose_floors.py`) |
| `5:3128` | falling-mob drawing and floor marks | implemented (`pop2/caverns.py`) |
| `5:3fda` | blue-flame trap (sounds 282/284) | later levels, not caverns |
| `5:4584` | scythe trap (sounds 276/277) | later levels |
| `6:4f44` | level 13 room 4 hook (CODE 10) | later level |
| `2:0b22` and other CODE 2 entries | mob/UI bookkeeping, `GameWindow` | not gameplay rules for levels 3-5 |

Most single-instruction "functions" in the list are data or Macsbug name
strings, not code. No further hidden cavern rule for levels 3 and 4 was found
besides the relief sigh.

## CODE 15, 16 and 18

The same method finds ten starts in unmapped regions of CODE 15/16 and none
in CODE 18 (desert). Only `15:7226` is real code: NISTower (symbol marker at
`15:754e`), a later scene coordinator that loads TowerNIS and fades CTBL
25373/25302. The CODE 16 entries and `15:3050`/`15:3958` are data or name
strings. Levels 1-4 have no hidden rules in these segments.
