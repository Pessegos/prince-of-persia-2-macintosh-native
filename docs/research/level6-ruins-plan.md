# Level Six: Ruins Scenery And Integration Plan

Research note, 2026-10-22, updated 2026-10-23, `claude/ai-research`. Level
six is playable from the cliff, without its heads and serpents. Codex's level-seven notes (branch `codex/level7-preparation`) cover the
shared environment-4 dependencies and the head/serpent actors; this note
covers the campaign track: scenery export and runtime integration.

## Identity

LEVL 2005 is level six, environment 4 (Ruins), start room 27 (port 26),
cell 23, opponent set 5 (`Head.rsrc`). Levels six and seven share
`Ruins.rsrc` (CTBL 3500-3502, PIEC 3500, SHAP 3501+, CUST 4025, 4200, 4250,
4275, 4300, 4325, 4350, 4375 and 4650) and the Prince palette CTBL 25004.

## Native Scenery Export (done)

`tools/extract_caverns.py` now draws any environment whose piece table is
decoded (`DRAW_KINDS`):

- The per-environment piece-drawing tables sit at a5-0x4aea + 4 * env. The
  caverns' table has 45 entries (kinds 0-44); the ruins' has 24 (0-23),
  followed by unrelated data.
- The ruins drawers in CODE 7 call SectRect (a5-0x1f58) at `7:1f2e`,
  `7:1f8c`, `7:2760`, `7:2b1a` and UnionRect (a5-0x1f5c) at `7:1f48`,
  `7:1fa2`, like CODE 8's cavern drawers.
- Shape library 0 is the sword item (SHAP 1000 + index, `Prince.rsrc`):
  level six's room 17 (port 16) has a tile-22 sword at cell 15.

With these, all 32 rooms of level six export with the original renderer
under Unicorn; levels three to five export byte for byte as before. A test
render of port room 16 matches the ruins look.

## Known Differences From The Caverns

- Pressure plates and gates use other SHAPs. In levels six and seven a plate
  (kinds 5/6) changes SHAP 3554 to 3555 and also redraws 3552 (kind 5) or
  3553 (kind 6); the exit moves 3547 (caverns: 3566); the gate is 3542
  (caverns: 3562/3563). `tools/extract_pressure_plates.py` and the runtime's
  shape remapping (`pop2/caverns.py`) assume the cavern shapes and need
  per-environment tables or stored variant commands.
- Port room 26 (the start room) is a CUST room (4650, kind 22). Its enter
  hook `7:37a6` (template table a5-0x4c2e) loads CTBL 3502 at entry 64
  (`S03_508A`), covering entries 64-218; with that overlay the exported
  room renders correctly. Its leave hook `7:37b6` restores CTBL 3500 at 64
  under a condition still to read. The shared hook `7:37d6` (kinds 20-22)
  only acts in level nine (rooms 16 and 2).
- The sword item SHAP needs the Prince/sword palette, not CTBL 3500.
- Cavern-only data (torches 3581-3589, lava) are skipped for environment 4.

## Implemented (2026-10-22)

- Import of `Ruins.rsrc`/`Head.rsrc` and `ruins_level6.json` (loose-floor
  variants delta-encoded: 24 MB instead of 115 MB, identical expansion).
- Ruins plates use their exported toggled commands; gates (3542) and exits
  (3547) move like the caverns' with clips 19/10 pixels above the row. All
  plate/gate/exit records of levels six and seven match native redraws.
- Loose floors shake with the column-parity tables a5-0x2c66/-0x2c7e
  (7:2bd6); both nonzero images share the phase-1 variant (approximation).
- Level six starts on the cliff (SEQS 2, native X 374) without a sword
  (a5-0x500a = -1, 3:6202); crouching at the sword item (tile 22) takes it
  (6:14ce-1574, SEQS 91, FindSwd 183). Saves keep a changed sword type.
- Finishing level five loads level six; the ruins' exit song is 124.
- Tile predicates (IsSpace/IsWall/IsFloor, CODE 3) are environment
  independent, so the existing collision rules apply.
- Crevices (tile 7) start covered (InitState 3:5dce clears bit 0x80) and a
  crouching or crawling Prince uncovers the first run of the row
  (RuinSetCreviceRevealed 7:3404, scan 7:332a).
- Crawling (2026-10-23): crouched with Down held, forward into a crevice
  whose foreground low bits are not 3, or a scythe (12/13), lies down
  (GenCtrl 6:0a4e-0b28, SEQS 125, X aligned to at most 10 pixels into that
  column facing right, 34 past its right edge facing left). Prone (poses
  246-261, 6:07ee-0994): forward crawls (122), back (123); he stands (124)
  when neither his own, the front nor the rear cell is 7/12/13, or with Up
  once clear of a crevice behind him (6:08a4-0942). A body at most 34 pixels
  high passes an open crevice (CheckCollide 4:5ade-5b0a, heads excepted),
  and the wall alignment skips a prone body in a crevice (4:35e6, 4:5830).
  These rules are environment independent, so level two's two crevices
  (port rooms 9 and 11) can now be crawled too.
- Scythes (2026-10-23, port rooms 18 and 20): tile 13 holds the state and
  AnimScythe (5:4584, in an unmapped listing region) copies its low byte to
  the tile 12 on its left. A living Prince or guard on a scythe cell, at
  most 30 pixels above the floor and more than 28 pixels into the column
  (5:57bc), starts a resting scythe (TriggerScythe 5:5fde). Each update
  advances phases 1-19 (sound 277 leaving 0, 276 leaving 15; from 16 a
  bloody blade also bloodies the handle, 0x80), then returns to 0 keeping
  the blood. CheckScytheHit (5:588a) tests only the first scythe cell among
  the character's columns -1..+1: phases 2, 16 and 17 (GetScytheHitType)
  cut with the rectangles a5-0x372a/-0x3722 offset by the cell (tile 13 one
  column right; guards 10 pixels shorter), except poses 267-271 and SEQS
  44: SEQS 113 and death method 5 for the Prince (SEQS 190 for a guard),
  sound 278 and blood (0x40) on both halves. The drawing of each of the 60
  states is exported as a patch of the native room drawing
  (`tools/extract_scythes.py`); it needs a reimport, and older imports
  leave the scythes still. Not reproduced: the climbing redraw layers for
  a blade and the scythe test S05_5F1A for tile 13 (it reads only the
  static blade state).

## Remaining Steps

1. Heads and serpents: level six has special opponents in rooms 4, 7, 16,
   20 and 25 (native numbering); `GuardSpawn` rejects them, so the level is
   currently empty of enemies. Codex's level-seven notes cover their
   selection, initialization, frames and idle/movement rules.
2. Cutscene 1 between levels five and six (CheckPlayNIS(5, 6)).
3. The start room's leave hook `7:37b6` and the retained cliff image when
   walking left from the start (to compare with the original).
4. Sword type 2 graphics (S03_5A4E) and the two shake images per parity.
