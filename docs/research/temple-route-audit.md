# Temple Route Audit, Levels 10-13

Status: 2026-11-05. Port rules only: no route here has been compared with the
native game, and a route found in the port proves that the port can finish a
level, not that the original plays the same way. Native rooms are one-based.

## Method

`tools/audit_temple_routes.py` runs the hidden real scene with its real key
entry points (`set_key_state`, `horizontal_key`), stubs only the drawing, and
searches best-first over named key macros (run, step, hop, leap, catch, climb,
crawl, drink, short waits). A node is a deep copy of the game plus the scene's
plain controls. Hints (`--prefix`, `--waypoints`) only steer the search; every
reported route is replayed from a fresh load without copied state, and
`tests/test_temple_routes.py` repeats those replays.

Supplied or left out:

- `peaceful`: opponents do not act. The routes prove the terrain and
  mechanisms, not the fights. With opponents on, exact key scripts diverge.
- The `altar` macro supplies level 13's death: a birdhead kills the Prince
  east of the chasm. See the open questions below.
- The final macro of level 11's plate return (`rushcatchL`) was found by a
  separate timing grid, because the search stops between macros.
- A level's lives and potions are as loaded: some routes end on one life.

## Results

| Level | Result | Macros | Frames | What the route needs |
| --- | --- | --- | --- | --- |
| 10 | finishes | 9 | 442 | Loose 12:21 falls on plate 19:21 (door 19:15); trap door 12:27 drops beside the door |
| 11 | finishes | 85 | 3,558 | See below |
| 12 | see below | | | |
| 13 | finishes | 35 | 1,616 | Plate 10:10 opens gate 19:11; death at the altar; the shadow lands on plate 4:12 and opens door 32:12 |

### Level 11

The order of the level, as the route found it:

1. 5 to 1, 4, then a jump under loose 10:26 from room 4's top row, and a climb
   through the hole to gate 10:29.
2. Room 9, a long catch to 2:8, the stairs to 3:0 and up room 12.
3. Plate 12:4 opens gate 6:19 for about a hundred frames, with a blade just
   past the plate. Landing beyond native X 283 starts the blade and cuts. The
   route lands at 251 and returns without stopping: two running jumps, a catch
   of the ledge 7:11 from a row above, a climb and a hop through the gate.
   Macros that stop on the way arrive with the gate already falling. This is
   the tightest step found, and it was only checked in the port.
4. Rooms 6, 13, 18, 17, 23, 25, 18, 24, 19, 24, 26, 28, 27, 22, 21, 32 and 29.
   Loose 29:7 gives way into the sealed east end of room 29's bottom row.
5. Plate 29:25 starts exit door 24:25, which stays open. A crawl under the
   blade 29:22-23 leads to room 20.
6. A leap catches 20:21 while loose 20:26 falls six rooms, down column 6, onto
   plate 1:26. Its impact opens gate 20:20 for good, the only way out.
7. Rooms 27, 28, 26 and 24, to the door.

## Defects the audit found and fixed

| Defect | Native | Effect on the routes |
| --- | --- | --- |
| Temple `IsLedge` was inverted, refusing every ordinary back ledge | 4:3f44, 6:162c | Level 11's hole 10:26 could not be climbed |
| Sliding rocks' refusal within 51 pixels missing at ledges | 6:162c | Rule only |
| The shadow never pressed plates | 2:6602 (CheckPress for opponents) | Level 13's door could not open |
| A sword death at the altar raised no shadow | 10:2a62 reads the pose, not a fall | Level 13's only exit needs that death |
| A key during SEQS 11 could run a frame that cleared the control bank, then crash | Port defect | `AttributeError` during play |
| Temple blades (tiles 12/13) never ran | 2:63e2-63f4, 5:57bc, 5:588a; drawn by 10:0772 | Every blade in levels 10-13 was a harmless slot |

The blades deserve a note. FrameAdv's environment 2 case falls through to the
ruins' scythe calls; none of 5:57bc, 5:5fde, 5:588a or 5:5a1c tests the
environment, and only the drawing (5:5ad0, 5:5c60) picks 10:0772 instead of
7:295e. The exporter recovers the swinging blade from the native room drawing.
A rendered sheet of phases 0-19 shows it leaving the wall's slot. This needs a
reimport; `run_game.py` asks for one when an export lacks the blades.

## Rocks and trap doors

- Trap doors are on the routes: levels 10, 11 and 13 each pass one, opening
  and closing through their full cycle (`pop2/trapdoors.py`).
- No sliding rock is on a finished route. The searches ran them in rooms 3 of
  level 11 and elsewhere over several million frames with no exception, and
  deaths by crushing were seen, but no route depends on them.
- Blades crossed on foot: level 11's 28:27 and 29:23, by crawling.

Every search reported zero exceptions from the game.

## Open questions

- Level 12 is the subject of the next section.
- Level 13's birdhead stands in SEQS 77 facing left and did not turn toward a
  Prince behind it during 1,800 frames, even with his sword drawn at 25 pixels.
  The `altar` fixture supplies its waking. This may be a gap in the opponent's
  rules; it has not been compared with the native game.
- If the player kills that birdhead, the burn at X <= 347 is the only death
  left in the room, and mode 12 excludes it from raising the shadow. Whether
  the level can then still be finished is unknown.
- Falling into level 12's rooms 23-24 (below) may be a one-way trap.

## Level 12

Exit door 7:23 opens from plate 14:8 or plate 24:23.

- 24:23 is easy to reach, but gate 18:19 then seals the Prince in: 24:22 shuts
  it, 23:29 opens it, and gate 23:28 before that plate has no link at all.
- 14:8 lies under hole 7:28. Its way in is gate 12:21, from plate 12:2 or 18:27.
  18:27 is too far from the gate for a gate's hundred frames, so the route seems
  to be the northern one, from plate 12:2: rooms 5 and 2 (gates 5:0-2 and 2:9,
  dropping loose floors on plates 5:28, 4:27 and 9:0), plate 2:22 (gate 1:3),
  plate 1:5 (gate 1:9), 3:20 dropped on plate 19:20 (gate 3:2), then rooms 3,
  11, 7 and 12.
- The flask of type 6 in 23:24 is not modelled. Disassembled 4:46b2: sound 12
  and SEQS 111, whose -14 event 3 calls 4:1d7e. That routine creates a type-10
  record and a type-12 actor (Jinnee.rsrc, SEQS 180 then the flying loop 225,
  removed outside columns -1..10, and exempt from gate contact at 4:6046 and
  6:3190). What it does for the level has not been recovered. It may be the
  designed way out of rooms 23-24.
