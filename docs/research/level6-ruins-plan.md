# Level Six: Ruins Scenery And Integration Plan

Research note, 2026-10-22, `claude/ai-research`. Level six is not playable
yet. Codex's level-seven notes (branch `codex/level7-preparation`) cover the
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

## Remaining Steps

1. Import `Ruins.rsrc` and `Head.rsrc`; export `ruins_level6.json` with
   environment-aware plate/gate/exit tables.
2. Make the scenery runtime (`pop2/caverns.py`, `level_rendering.py`,
   `game_session.py`) choose its resource file and JSON by environment, and
   run the shared mechanism state (plates, gates, loose floors, potions) for
   environment 4.
3. CUST room palettes/hooks, the sword item (RuinSetCreviceRevealed and
   crevices from Codex's notes), Prince palette 25004, level-six music.
4. Route the level-five exit into level six and allow level 6 in saves and
   the level menu. Level six starts without a sword (`3:6202-6216`).
5. Heads and serpents (Codex's level-seven research, actor types 7/8/11).
