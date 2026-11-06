# Temple Route Audit, Levels 10-13

Status: 2026-11-06. Port rules only: no route here has been compared with the
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
- A level's lives and potions are as loaded: level 11's route spends part of it on one life.

## Results

| Level | Result | Macros | Frames | What the route needs |
| --- | --- | --- | --- | --- |
| 10 | finishes | 9 | 442 | Loose 12:21 falls on plate 19:21 (door 19:15); trap door 12:27 drops beside the door |
| 11 | finishes | 87 | 3,627 | See below |
| 12 | not finished | | | No route found; see the last section |
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
   Room 26 is crossed by hopping over trap door 26:14: landing on it, or a step
   onto it, drops the Prince, and it offers no grip.
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

| A foot on a closed trap door did not open it | CheckTrapDoor 10:2540, from 2:63e6 and 2:6642 | Doors now open under the Prince and guards |
| Catch took a ledge past an open trap door | 4:393e calls IsLedge 4:3f58-3f6e | Levels 11 and 12 had relied on it; both routes were searched again |

The blades deserve a note. FrameAdv's environment 2 case falls through to the
ruins' scythe calls; none of 5:57bc, 5:5fde, 5:588a or 5:5a1c tests the
environment, and only the drawing (5:5ad0, 5:5c60) picks 10:0772 instead of
7:295e. The exporter recovers the swinging blade from the native room drawing.
A rendered sheet of phases 0-19 shows it leaving the wall's slot. This needs a
reimport; `run_game.py` asks for one when an export lacks the blades.

## Rocks and trap doors

- Trap doors are on the routes: levels 10, 11 and 13 each pass one, opening
  and closing through their full cycle (`pop2/trapdoors.py`).
- No sliding rock is on a finished route. The searches ran them in room 3 of
  level 11 and elsewhere over several million frames with no exception, and
  deaths by crushing were seen, but no route depends on them.
- Blades crossed: level 11's 28:27 and 29:23 and level 12's two in room 6, by
  crawling. Macros that run or leap at a blade die there; crawling is the rule.

Every search reported zero exceptions from the game.

## Open questions

- Level 12: the last section.
- Level 13's birdhead stands in SEQS 77 facing left and ignores a still Prince
  behind it. A step wakes it (`temple-altar.md`), so the Prince can fall to it
  without help. The `altar` fixture still supplies the waking, to keep the route
  short.
- If the player kills that birdhead, the burn at X <= 347 is the only death
  left in the room, and mode 12 excludes it from raising the shadow. Whether
  the level can then still be finished is unknown.

## Level 12

Not finished, and not proven impossible. The search ran without opponents,
and the level seems to need more than that allows.

Exit door 7:23 opens from plate 14:8 or plate 24:23.

- 24:23 is easy to reach, but the Prince cannot get back. He falls through gate
  18:19 into room 24, 24:22 shuts that gate, 23:29 is the only plate that
  reopens it, and gate 23:28 before that plate has no link at all.
- 14:8 lies under hole 7:28, behind gate 12:21. Plate 18:27 is too far from that
  gate, so the way in is plate 12:2 on the northern route: gate 5:2, gate 2:9,
  plate 2:22 (gate 1:3), plate 1:5 (gate 1:9), gate 3:2, then rooms 3, 11, 7, 12.

After the playtest fixes ([notes](temple-november-playtest.md)) the route to
these gates no longer catches the ledge past door 1:1.

From a fresh load, the audit crawls under room 6's two blades and works through
the northern gates. Real keys drop loose floors on plates 19:20, 5:28 and 9:0,
holding gates 3:2, 5:0 and 2:9 open for good (`LEVEL_12_GATES` in
`tests/test_temple_routes.py`). Gate 5:1 only opened for a moment there, from
the Prince on plate 4:27; loose 4:17 above that plate has not been dropped.

The blocker is gate 5:2. Only plate 9:24 opens it, for one press, with no loose
floor above. The gate stays useful for about 146 frames. From the plate to the
gate is two cells, five climbs and a three-cell leap: roughly 195 frames by the
measured climb of 31 frames. These figures are an estimate, not a proof: the
search tried for a further 1,200 seconds and failed, without covering every
timing.

What may resolve it, none checked:

- An opponent. A dead actor presses a plate for good (`push`, `permanent`),
  and room 9 holds the flaming sword (raw kind 1 at native X 305). The peaceful
  harness cannot show this.
- The flask of type 6 in 23:24, which the port does not model. Disassembled
  4:46b2 plays sound 12 and selects SEQS 111, whose -14 event 3 calls 4:1d7e.
  That routine sets up a type-12 actor (Jinnee.rsrc, SEQS 180, then the flying
  loop 225), a type-10 record, and removal outside columns -1..10 (4:1d64). The
  Jinnee skips gate contact (4:6046, 6:3190). What it does for the level has not
  been recovered, and it sits in the very rooms that have no exit.
- A native run of this level would settle all of this, and none was done.
