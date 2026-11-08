# Game-over title colours

The user's Macintosh/port screenshots on 2026-11-08 showed the same tree
and title, but the port's title was entirely black until the tree faded out.

## Original evidence

- TreeCheck CODE15:0568 receives variant9 (NIS20; variant at A5-0x245c).
  CODE15:062c loads CTBL26003 as the target NIS fade table, initially black.
- Only variant9 takes CODE15:0632-0646. At15:0642 it calls
  SetSHAPColors17:0a52 with the look pointer at A5-0x5242 and CTBL26028.
  The pointer is the first stack argument; the resource id is at SP+4.
- SetSHAPColors17:0a5c-0a8e loads that CTBL, calls SetColors17:02de with
  flags7 and ShowColors17:0694 for entries1..254. This immediately shows
  the resource's existing indices without replacing the NIS fade handles.
- CTBL26028 supplies indices17..23: gold edges, red face and black shadow.
  SHAP26028 uses those indices plus transparent0.
- TreeFunc15:04e8 fades the loaded NIS tables in on animation frame2.
  TreeCheck15:0758 later loads CTBL26028 with flags114: fade the previous
  target tree table out, replace it with the title table, and show it.
  The earlier direct title colours therefore survive the tree fade.

The extractor previously treated SetSHAPColors as an irrelevant offscreen
table update and emitted nothing. That left indices17..23 black until15:0758.

## Repair and verification

The extractor now emits an immediate palette update with the original indices,
without assigning either fade slot. `read_program` inserts this same operation
at15:0642 for old variant9 programs identified by their original palette call
sites. Existing installations need no asset reimport; fresh imports contain
the operation once.

- 162 focused tests passed, no skips: tree scenes, intro format/player and
  extraction, carpet/throne, horse/temple arrival, viewer and covers.
  Tk emitted ThemeChanged callbacks after hidden test widgets were destroyed;
  there were no test failures.
- A synthetic coordinator regression checks SetSHAPColors argument placement;
  a compatibility regression covers old, fresh and unrelated programs.
  The actual imported scene regression compares every nontransparent title
  pixel with CTBL26028 over the tree, during its fade and over black.
- Executed the original TreeCheck/TreeFunc coordinators for all nine variants
  with `recover_tree`. Fresh output exactly matches normalized old imports.
  Variants1..8 are unchanged; variant9 gains only the15:0642 operation.
- Visually inspected an offscreen before/after render reproducing the reported
  black title and its corrected red/gold face and black shadow.
- Dependencies, Ruff F/E9, recovery catalogue and whitespace checks passed.

The coordinator extraction supplies drawing, palette, audio, timing, Resource
Manager and other host services through the existing extractor hooks; animation
scripts are expanded by the port. SetSHAPColors itself was read statically,
not run as an independent native CPU/pixel probe. The pixel regression uses
the port's resource decoder and is not an independent decoder check. No live
game/emulator or exclusive desktop input was used. Full gameplay discovery was
not repeated for this scene-program/import-only change.

Local evidence: `rendered/gameover-title-validation.json` and
`rendered/gameover-title-comparison.png`. Original resources remain private.
This fixes the reported title-colour defect; broader cutscene timing and native
pixel equivalence remain outside this check.
