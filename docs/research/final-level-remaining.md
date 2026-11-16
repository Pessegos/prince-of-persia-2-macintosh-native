# Level 14: What Remains (2026-11-16)

A work queue for the final level's gameplay, written after reading
[the preparation ledger](final-level-preparation.md),
[the earlier handoff](final-level-claude-handoff.md),
[the video reference](final-level-video-reference.md), the `pop2/final_*`
modules, `Final` in `pop2/environments.py` and the saves. It covers gameplay
and recovery only: menu looks, the Hall of Fame page's look and README
wording are out of scope.

## Where it stands

The whole route is integrated and on main: level-13 exit, NIS 3, the tower
(rooms 1-2) and the window gate, NIS 5 and the last sound's wait, the
chessboard, room 6's four false Princes (9:1526), the palace path
controller (9:16fe), the turns, body, shadow and fire, the burning Jaffar,
NIS 11 and the Hall of Fame, the defeat in the bedroom (9:0062), room 3's
respawning copies and their flasks (9:00e2), the moving scenery and the
rooms' music. Both 2026-11-11 playtest blockers are fixed.

The twelve final-level suites (`tests.test_final_*`, `tests.test_happy_ending`)
ran on 2026-11-16 in this worktree: 101 tests, all passing.

Native CPU probes exist for the spell gate, clone frames, Jaffar generation
and record, the dead copy, the completion caller and the scenery. The ledger
names no probe for 9:1526, 9:16fe, the magic rules, the defeat or HappyFunc's
timing.

## Queue, in order

Work on a branch of its own from main (for example `claude/final-level-play`),
not on `claude/final-level`: that branch holds menu drafts (crystal, escher)
still waiting for the user's review, which must not reach main with this work.

### 1. Saving during the battle (a confirmed fault)

**Done 2026-11-16.** A save keeps only the checkpoint, so the faults were in
the rebirth snapshot: `PathInfo` is a saved record now, and the checkpoint
no longer copies `final_magic` (SetKidDefaults clears the turns, 2:5e56).
`final_drops`, `final_events`/`final_songs`, `final_saved_prince` and
`final_music_room` are frame or presentation state that a save never kept.
See the ledger's "Saves and the retry" and `tests.test_save_records`.

- `Fighter.final_info` holds a `PathInfo` (`pop2/combat.py:211`), which is
  not in `save_game.CLASSES`. `_pack(PathInfo())` raises
  `SaveGameError('Unsupported save value: PathInfo')`. Once the final Jaffar
  has run his controller, a save from the menu likely fails. Reproduce this
  through the real save path before fixing it.
- `FinalMagic` (turns, flash, shadow, body, fireball, palette) sits on the
  cavern state as a dynamic attribute (`caverns.final_magic`, set with
  `getattr` in `Final.magic`). It is not a `CavernState` field, so a save
  silently drops it. A load in shadow form would then give a Prince without
  a body record.
- Check the other dynamic host state the same way: `combat.final_drops`,
  `combat.final_events`/`final_songs`, `scene.final_saved_prince`,
  `scene.final_music_room` and `Final.shadow_died`/`fireball_sprite`.
- Acceptance: round-trip tests (save, load, run on) in hidden level-14
  scenes after one to three turns, in shadow form with the body down, with
  a fireball in flight, with Jaffar between positions, with a room-3 flask
  pending, and in room 4 just after NIS 5. Older saves must still load
  (optional fields). Each test must fail on the current code.
- The temple has two faults of the same kind (`CavernState.jinnee` and
  `Jinnee`; [temple queue](temple-remaining.md) item 1). Fix all of them in
  one change, together with the test that walks every saved type.

### 2. Jaffar's floor kills too soon (open divergence)

**Done 2026-11-16.** 9:16fe reads the Prince's armed word (+0x1a), not
ALIVE: he closes in and casts only at a Prince without a sword. See the
ledger's "Route playthrough fixes". The gates of 0a42, 09ca, 0ba6 and 14c8
were read again and match the port.

Recorded under "Route playthrough fixes": standing in range on Jaffar's floor
kills before four turns are possible. SEQS 242 reaches pose 282 in 11 frames;
four standing turns take about 15. The user's run survived this. Trace the
native gates of 9:0a42/9:0ba6/9:14c8 with the Prince on Jaffar's row (pose
tests, FRAM 0x40, row and column zones, the dissolve branch 9:177e), and also
when 9:16fe is called at all. Find which gate the port misses. Do not add a
delay or timer.

### 3. Native probes for the unprobed controllers

Each probe states its supplied endpoints and includes a regression that
rejects a wrong model:

1. 9:16fe and its callees (flee or close in, dissolve, kill, position
   routes): decision tables from recorded Kid calls. **Done 2026-11-16**
   (`tools.probe_final_path`, 6,000 cases; CharDistance's life gate fixed).
2. 9:1526 (room-6 strikes, dissolves, SEQS 240 for the last copy, and the
   9:090e/19fa hand-off). **9:1526 done 2026-11-16** (`tools.probe_final_copies`,
   6,000 cases, no difference); 9:090e and 9:19fa are not probed.
3. The magic rules: 4:1fb2 (turns), 4:2046 (the eighth-turn test), 4:2174
   (flashes), 4:2206 LeaveBody, 4:1f1e and 4:24b2 (lying down and rejoining),
   4:25ce and 4:2338. **4:1fb2, 4:2046, 4:2174, 4:250a and 4:2590 done
   2026-11-16** (`tools.probe_final_magic`; the fatal eighth turn fixed).
   Lying down (4:1f1e with 4:24b2) done 2026-11-16 (`tools.probe_final_body`;
   the distance before turning fixed). LeaveBody, rejoining and 4:2338 are
   not probed.
4. The fire: 9:2674 (cast), 9:27a0 and 9:25e4 (flight), 9:24ee (hit).
   **Traced 2026-11-16**: the cast and hit already matched; the fire now
   starts in state 2, tests its cell when thrown, restarts on a second cast
   and resets songs 265/258 as 9:2880, 9:25e4 and 9:27a0 do; then
   `tools.probe_final_fire` (5,000 cases, no difference). 9:24ee not run.
5. 9:0062 (the defeat) and InitOpps' room-11 laugh. **Done 2026-11-16**
   (`tools.probe_final_defeat`, 364 + 2,560 cases, no difference).

### 4. Behaviour that was assumed, not traced

- The relocation's call site: CutOpponent 6:424c -> UpdateOppInfo 6:30b0.
- The port choice that only a burning figure (SEQS 230) finishes out of
  view: establish what the original does out of view, and keep the victory
  reachable. **Answered 2026-11-16**: 9:25d0 moves the view room
  (a5-0x4fc4) to the burning Jaffar's room, so the original never burns him
  out of view; the port has no separate view room and keeps its exception.
- The video reference's "victory bedroom actors, native room 11 and the
  following NIS call", end to end.

### 5. Small rules not yet ported

- The shadow's fall off the bottom of the screen (4:3780). **Checked
  2026-11-16**: 4:374a (below Y 730 with no room beneath) costs 100 life,
  and for type 1 calls CutToKidRoom 4:2338. The port's void death and
  `Final.shadow_died` already do this; port room 7's row-2 gap at column 0
  is such a fall, now a regression.
- The lie-down's native Y - 1, left out to keep the Kid on his floor: find
  why it would leave the floor. **Answered 2026-11-16**: it has no effect;
  SEQS 71 opens with SetCharFloor (-19, 4:2f72 -> 4:31fa), which sets Y to
  row * 120 + 106 before the frame is drawn.
- In room 11 after a defeat, the 9:16fe flee branch (four or more turns on
  the same row). **Answered 2026-11-16**: with the Kid at life 0 the flee
  needs life above 2, closing in moves only towards a Prince with life and
  CharDistance's life gate blocks the dissolve, so 9:16fe never moves the
  figure there (`tests.test_final_path`, the probe's life 0 cases).
- KeepTime's trobs for crystal and gargoyle cells on the neighbouring rooms'
  edges, with their Rnd draws.
- The ChessRm song starts about two seconds later than on the Macintosh
  (the room-4 wait). **Done 2026-11-16**: it starts as the scene's last
  wait begins (`IntroPlayer.code_hooks`, `Final.enter_chess_room`).

### 6. Whole-route regressions

- One hidden run from the level-13 exit to the introduction's return, with
  a real AudioEngine on SDL's dummy device.
- The variants: a room-3 detour that drinks a life-enhancement flask; a
  Prince too weak for the eighth turn (collapse, method 17); 2 life or less
  (no cast); a missed fireball, then a healing flask restores the flame;
  death and retry at the room-4 checkpoint.
- The strategy guide's leads (a careless copy kills in one strike, the
  final Jaffar resists the sword, the pursuit reverses after a miss): check
  each against the code, not the guide.

### 7. Needs the user's material, not done overnight

- Room 3's fight timing and the pixels of SEQS 238/239: the winning video
  skips that room, so a new Macintosh recording is needed.
- The mode-13 palette compared with the video (inventory milestone 1).
- The Hall of Fame's song cue 180 and the native pixel limit on the name.
  Both are on the Hall page, which is a menu, so they wait for the user.

## After this queue

Continue with [the temple's queue](temple-remaining.md).

## Rules for this queue

- Make small, focused commits, each with a regression that fails on the old
  code. Update the ledger (`final-level-preparation.md`, `RECOVERY_CATALOG`).
- Run the focused final suites after each change, and
  `tools.run_tests --slow` once per batch before integrating. Integrate only
  with a reserved slot.
- Do not operate the user's game window, saves or settings. Do not change
  menus.
