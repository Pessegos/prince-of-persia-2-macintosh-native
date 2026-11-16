# Temple (Levels 10-13): What Remains (2026-11-16)

A work queue for after [the level-14 queue](final-level-remaining.md). It was
written from [the route audit](temple-route-audit.md),
[the November playtest](temple-november-playtest.md),
[the level-12 video route](level12-video-route.md),
[the flaming sword](flame-sword.md), [the altar](temple-altar.md),
[the room-14 slab](temple-room14-loose-landing.md), the shared board and the
saves. It covers gameplay and recovery only: no menus, artwork or README.

## Where it stands

All four levels are playable and on main. Levels 10, 11 and 13 finish from a
fresh load in the route audit, but **with opponents off** (`peaceful`).
Level 12 finishes along the user's Macintosh video with opponents on
(`LEVEL_12_VIDEO`, life 12 supplied). The November playtest's reports are
fixed, and so are the 2026-11-14 slab, raster and guard-contact reports.

## Queue, in order

### 1. Saves (two confirmed faults)

**Done 2026-11-16**, together with level 14's: `Jinnee` is a saved record,
and a missing field with a default now takes the default (also `rocks`,
`trapdoors` and `flame`, which refused earlier cavern saves too).
`tests.test_save_records` walks every saved type.

Checked on 2026-11-16 with `save_game._pack` and `_unpack`:

- **Older saves of levels 3-14 no longer load.** `CavernState.jinnee` (added
  in 43f1fe5, 2026-11-06) is missing from the optional fields in
  `save_game._unpack`. A cavern-state record without it fails with
  `SaveGameError('Invalid CavernState fields')`, so a save made before that
  date in the caverns, ruins, temple or final level is refused.
- **Saving while level 12's genie is out fails.** `Jinnee` is not in
  `save_game.CLASSES`, so `_pack` raises "Unsupported save value: Jinnee".
- The same family as level 14's `PathInfo` and `final_magic` (queue item 1
  there). Fix them together, then add a test that walks every dataclass
  reachable from a game's snapshot fields. The test checks that each one
  can be packed, and that every field added since a type's first save
  either has a default and is optional or is omitted. Then a new field
  cannot break saves again.
- Acceptance: a save from before 43f1fe5 loads, using a fixture written
  without the field. A save with the genie mid-run loads, and he goes on to
  press his plate. Each regression must fail on the current code.

### 2. Play levels 10, 11 and 13 with opponents on

The routes for these three were searched without opponents, and their key
scripts diverge once guards act. Replay each from a fresh load with
opponents on, as `LEVEL_12_VIDEO` does, with `tools/audit_temple_routes.py`
and its fight macros (`strike`, `swordduel`, `duel`). This is the most likely
way to find the bugs that remain in the birdhead fights, alerts, falls,
scythes and blades, gates held by corpses and debris on guards. State any
supplied life. Each defect found gets its own trace, fix and regression.

### 3. Level 12: the landing beside the flaming sword

In the video the Prince runs east past the sword. In the port he lands
eight pixels to its left, is pushed back towards the edge, and has to parry
it down. Measure the port's landing against the native rules (the jump's
distance, CheckBarr and the sword's barrier, `alert_path_mode(floating=True)`),
and find which differs. Do not tune the route to hide it.

### 4. Level 13's altar

- Killing the altar birdhead makes the original unfinishable, from the
  user's own play. The player resets at the checkpoint. Check that the port
  behaves the same way, and that its checkpoint restart (or level restart)
  is a way back. Then replace "unknown" in the route audit's open questions
  with this. **Checked 2026-11-16**: it does (no shadow from the burn, mode
  12; the restart brings the birdhead back), `tests.test_temple_altar`;
  the route audit is updated.
- The birdhead that turns into the chasm (SEQS 60 with no floor test,
  CheckFloor 4:35ca) reads as original. Confirm it with a native probe of
  6:26a8 and 4:35ca if that is cheap; otherwise leave it documented.
- The route still supplies the guard's waking (the `altar` fixture). Try
  the real step wake from item 2's replay.

### 5. The loose floors' second shake pair (importer)

**Done 2026-11-16.** `loose_floor_cells` now exports phase 3's image for
the temple (environment 2) as it did for the ruins: 7:2bd6 serves both with
the parity tables a5-0x2c66/-0x2c7e. A new export carries
`loose_floors.shake_pairs`; `run_game` asks an older temple export for a
reimport ("needs the second loose-floor shake"). Only `loose_floors`
changes (48 of 101 cells, 58 room units). An odd column now shows its
second image in phases 3-4; in an even column the table's value 1 draws
the same pixels as the resting floor, so phases 3-4 rest there, as the
original's drawer gives. **The user's installation needs a reimport.**
`tests.test_temple_loose_shake`, `tests.test_loose_floors`,
`tests.test_run_game`.

Original temple shake phases use two pairs of pieces, 3545/3547 and
3546/3548. The temple import keeps only the first, so attached shakes whose
native phase 3 differs from phase 1 lose a step of the tremor. The user
noticed a missing tremor on 2026-11-14. Export the second pair and draw it
in phase 3. The import changes, so a reimport is needed: say so, and make
the port detect an old export, as it does for other missing temple units.

### 6. Native probes still missing

Each probe states its supplied endpoints and rejects a wrong model:

- The flaming sword: the wake, parry and bob paths, 4:02e0's impassable-cell
  branch (0372), Opponent1 3:09d8, IsCharInKidRoom 6:46a8, and the rest of
  CheckAlert's engagement at 70f2.
- The altar shadow's rise, its merge with the Kid and the whole flight
  (10:2850 decisions already agree, 24,576 cases).
- CheckSpikeHit's loop past the first spike: the port stops at the first
  lethal spike of the two columns. This only matters for two adjacent
  lethal spikes, so check whether any temple room has them before porting.

### 7. Needs the user's material or decision

- The fights' native timing (level 12's three fights, the birdheads), and
  the artefacts at x≈507 in NIS 3's flight shots: both need a Macintosh
  recording to compare.
- Anything that would change a look the user approved stays as it is.

## Rules for this queue

The same as [the level-14 queue](final-level-remaining.md#rules-for-this-queue).
Read the matching temple note before changing a rule, keep the approved
port exceptions (guards killed by the slab in room 13, the first-contact
leg) and follow the user's videos where they exist.
