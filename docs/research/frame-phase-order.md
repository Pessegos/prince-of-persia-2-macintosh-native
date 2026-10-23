# Frame Phase Order: Original FrameAdv Versus The Port

Research note, 2026-10-23, `claude/ai-research`, for the architecture track
in `..\COORDINATION.local.md`. Addresses are original CODE `segment:offset`.
**[D]** is read directly from the listing; **[?]** is a helper whose role is
not yet established. This is a static reading, not a native trace: no probe
has executed FrameAdv yet.

## Original: one game update (FrameAdv 2:60fc)

FrameAdv loops `2:6100-6212` while the game runs. Each pass:

1. `2:6100-610a` [D]: when the game is live (a5-0x4fee), ResetFrameVars
   `2:68c0` and SaveRebirthPtStatus `2:15d0`.
2. `2:610e` [D]: the world update `2:6224` (below), which returns -2 for an
   ordinary frame.
3. `2:6114-61fc` [D]: level change and the exit-song gate (`2:6134-6168`,
   see `docs/LEVEL_TRANSITION.md`), the frame timer wait (`17:3032`,
   `17:31b8`), the restart-key gate and SetRebirthPtInitials `2:179e`.
4. `2:6200-6204` [D]: CheckCursorVisibility, CheckCheatModes.

The world update `2:6224`:

| Step | Site | Work |
| --- | --- | --- |
| 1 | `2:622c` | MakeRubble `5:29e8`: falling debris moves [D] |
| 2 | `2:6230` | AnimTrobs `5:0c38`: every object animation (gates, plates, exits, loose floors, spikes, scythes, bridge planks, carpet...) [D] |
| 3 | `2:623a-6252` | opponent set 2 or a5-0x5200 = 10: `4:14c6` [?]; CheckOppGenPts `6:3a0c` for the current room [D] |
| 4 | `2:6258` | environment hook `2:6e7e` [?] |
| 5 | `2:625c` | the Prince: `2:62e6` (below) [D] |
| 6 | `2:626c` | the opponents: `2:648c`, the same steps per opponent (PlayerCtrl `2:6468`, AnimChar `2:6538`, collision/press/hazards `2:65f6-6654`, room changes `2:6680-6700`) [D] |
| 7 | `2:627c-6280` | unless invulnerable (a5-0x4f90) and in room 0: TestStrike `6:57b2`, CheckStab `6:5092` [D] |
| 8 | `2:6284-6290` | AddSFX `5:4cde`, CheckAlert `2:6b46`, `2:7124` [?], ChangeMeters `2:54d6` [D] |
| 9 | `2:6294-62b6` | CutAllOpponents `6:4382`, PrepCut `2:532c`; on a cut CutOpponent `6:424c`, `2:51f4` [?], `2:7194` [?] [D] |

A cut returned by step 5 (d3 != 0) skips steps 7-9 except the opponents,
`2:7124`, ChangeMeters and PrepCut (`2:62c4-62da`).

The Prince's update `2:62e6`:

| Step | Site | Work |
| --- | --- | --- |
| a | `2:62ea-62f4` | LoadKid `4:4b02`; `4:3788` [?] nonzero (not live) -> only PlayerCtrl and `4:3688` (`2:6468-646e`) |
| b | `2:62f8-6342` | choose the opponent for the Prince (GetOppIdxClosestToKid `6:36f2`) and LoadShadAsOpp `4:3312` [D] |
| c | `2:6348-6350` | LoadFrame `4:2a72`, SetupSword `3:0ac8`, GetCharEdges `4:5cbc` (edges before moving) [D] |
| d | `2:6354` | PlayerCtrl `4:3b88`: keys to controls, GenCtrl (crouch, crawl, carpet, pick-up...) [D] |
| e | `2:6372` | AnimChar `4:2c0c`: one SEQS step (unless a5-0x4fac) [D] |
| f | `2:637e-6382` | `4:341a`, `4:3464` [?] (motion after the step) |
| g | `2:6386-638e` | LoadFrame, SetupSword, GetCharEdges (edges after moving) [D] |
| h | `2:6392` | `2:6c64` [?] |
| i | `2:6396-639e` | CheckBarr `4:4e34`, CheckCollide1 `4:54da`, CheckGateForKid `4:60e4` [D] |
| j | `2:63a2-63a6` | `5:1202` [?], CheckPress `5:127e` (plates, loose floors) [D] |
| k | `2:63aa-63fe` | environment hazards: caverns (3) spikes `5:3c42`, darts `8:2e82`, `5:3af8`, lava `8:33fc`; temple (2) spikes, `10:2540`, `5:3af8`, then the scythes; ruins (4) scythe start `5:57bc` and CheckScytheHit `5:588a`. Damage checks are skipped while invulnerable [D] |
| l | `2:6402` | `2:6c1c` (the queued row shake, CheckAlert's request) [D] |
| m | `2:640c-6446` | level four's relief countdown (sound 110) [D] |
| n | `2:644e-6482` | save the edges and the Prince record (SaveKid) [D] |

Drawing happens after FrameAdv returns, in the main loop, not inside these
steps.

## Port: current tick (`ScenePrototype.advance_animation`)

Recorded before any reorganization (main at 6fb3899):

1. Death counter and keyboard (`death.advance`, `sample_keyboard`).
2. `advance_cavern_floors`: hit flashes cleared, spikes, darts, falling
   debris, plate/loose events, `loose.advance_tiles`, scythes, plates, the
   relief countdown. This is steps 1-2 of `2:6224`, plus the darts' flight
   and the spikes' animation, and step m.
3. `advance_story_clock` (may return early).
4. Prince controls: carpet, crevices, crawl, potions (the potion branch
   returns early with terrain, combat, level events, rebirth, audio,
   render), then falling/dead, locked-combat and opening branches, each
   with its own copy of the tail.
5. The ordinary branch: many `resume_*` controls, `prepare_next_sequence`
   (the SEQS step), ledge handling.
6. Tail: `advance_terrain` (motion, walls, floors, room cuts, plates and
   loose floors, the cavern hazards including the scythes, the bridge,
   the gate crush, torches, room redraw), `advance_combat` (opponents,
   strikes, alerts), `advance_harbor`, `advance_level_events` (potions,
   flip, floating), `advance_rebirth`, `advance_audio`, `render`.

The tail is repeated in five branches with small differences (the potion
and opening branches omit `advance_harbor`; the opening branch also omits
terrain, level events and rebirth).

## Known Differences To Investigate

- The darts' flight and the spikes' animation run with the objects (step
  2) in the port; natively darts are MOBs (`5:3c42`, `8:2e82`) and need
  checking against AnimTrobs/MOB order.
- The opponents run after the Prince's hazards in both, but the port's
  `advance_combat` also contains the strike checks (steps 7-9); their
  relative order with respect to the opponents' own collisions is not yet
  compared.
- Rendering is part of the tick in the port; natively it is after the
  whole update. Equivalent as long as nothing reads drawn state.

## Plan

1. Behaviour-preserving extraction: one explicit list of named phases per
   tick mode (ordinary, potion, falling/dead, locked combat, opening), run
   by a small orchestrator with an optional trace; a regression asserts
   the current order of each mode.
2. Native trace probes for the unresolved steps ([?] above), then
   separately committed order corrections, each with its evidence.
3. Runtime drawing of animated objects, one mechanism at a time (first the
   bridge planks, which already re-render, then the scythes, then loose
   floors), compared against the original renderer's command lists and
   pixels, with baseline and new import time, asset size, draw cost and
   cache growth measured on the same cases.
4. Explicit coordinate conversions (native/port X, rooms, actor-X versus
   supporting-foot columns) where touched, with boundary regressions.

## Stage 1 Result (2026-10-23)

`pop2/frame_phases.py` lists each tick mode's world phases;
`ScenePrototype.run_world_phases` runs them in that order and can record a
trace (`frame_trace`). The five early-return tails of `advance_animation`
now use it, with the same order and arguments as before (the combat sweep
argument only in the ordinary mode). `tests/test_frame_phases.py` pins the
table and checks the ordinary and falling modes on a live tick. Focused
suites (terrain, levels five/six, bridge, combat, potions, opening,
rebirth, harbor, pursuit, skeletons: 491 tests) pass; the full suite waits
for a slot that does not overlap the user's playtesting.

## Stage 3 Baseline: Loose-Floor Variants (2026-10-23)

Measured on this machine with `extract_loose_floor_scenery` and the current
exports (same inputs for later comparison):

| Level | Export time | Loose-floor data | Variants | Largest room |
| --- | --- | --- | --- | --- |
| 3 | 10.7 s | 5.3 MB | 354 | port 6: 53 |
| 4 | 1.1 s | 0.5 MB | 43 | port 19: 17 |
| 5 | 45.9 s | 24.8 MB (full lists) | 1,656 | port 19: 1,295 |
| 6 | 269.8 s | 24.3 MB (delta) | 9,753 | port 19: 7,775 |
| 7 | 16.6 s | 0.8 MB (delta) | 597 | port 4: 215 |

Using the existing variants as the native oracle:

- Composing a multi-cell variant from its single-cell patches (removal and
  anchored insertion) reproduces the native list exactly in most cases:
  level 4 21 of 22, level 3 236 of 273 (another 18 have the same commands
  in another order), level 7 209 of 299 checkable. The other 19 level-3
  cases and one in level 4 differ in content: a loose cell and the cell
  directly above it in another room change the same front lip (e.g. level
  4, port room 18 cell 6 with room 28 cell 26, SHAP 3604). Level 7's other
  229 cases are crevice runs, which only change as a whole.
- Grouping commands by their drawing cell (command fields 8-9) and layer
  does not keep a fixed sequence of groups: falling or shaking cells add or
  remove whole groups.

So independent per-cell patches are not enough; a runtime model needs each
cell's drawing as a function of its own state and its neighbours' (at
least the cell above), or the native piece drawers themselves. Next step:
read DrawCaveLoose `8:24dc`/the ruins' loose drawer `7:2bd6` and the floor
drawers' neighbour reads to fix that dependency set from the code, then
validate a composed model against every existing variant before replacing
the export.

## Stage 3 Result: Per-Slot Dynamic Scenery (2026-10-23)

The export harness (`recover_room`) already called the original piece
drawers once per (row, column, pass) and then applied DumpTable's stable
layer order. Each command now carries its slot, and a memory-read hook
(`CavernRecovery(track_reads=True)`) records which level cells (LEVL kinds
and foregrounds, and the a5 current/previous/below-row caches) each slot's
drawers read. A dynamic unit (a loose floor, a crevice run, a scythe, a
bridge plank, the entrance door) can only change the slots that read it, so
`tools/extract_slots.py` renders the product of states only over the units
one slot reads and stores, per slot, its fragment for each such
combination. `pop2/slot_drawing.py` composes any combination at run time
(about 0.2 ms) and the rest of `cavern_room` is unchanged. Loose-floor data
is schema 2 in export version 16; version-15 imports keep working.

Oracle check (`python -m tools.check_slot_scenery --source ...`): every
whole-room variant of the previous export, with its floor and climbing
redraws and entrance frames, renders identically from the slots:

| Level | Variants | Checks | Slot export | Whole-room export | Slot data | Whole-room data |
| --- | --- | --- | --- | --- | --- | --- |
| 3 | 354 | 1,097 | 8.2 s | 12.0 s | 0.37 MB | 5.3 MB |
| 4 | 43 | 129 | 1.2 s | 1.2 s | 0.10 MB | 0.5 MB |
| 5 | 1,656 | 4,968 | 6.6 s | 55.8 s | 0.23 MB | 24.8 MB |
| 6 | 9,753 | 29,259 | 69.6 s | 287.8 s | 0.45 MB | 24.3 MB |
| 7 | 597 | 1,791 | 11.9 s | 18.1 s | 0.26 MB | 0.8 MB |

Single-change detection alone missed slots that change only when two cells
change together (20 floor-redraw cases in level 3, 96 in level 7); the read
sets fix that. Scythes (60 states) and bridge planks (rest, wobble up and
down, fallen) are now slot units too: 120 random scythe states, half of
them combined with loose floors in the same room, and 60 random plank
combinations match native renders, as the previous scythe patches and plank
rules did for single cases. Whole cavern exports: level 3 10.8 s/0.84 MB,
4 3.1 s/0.49 MB, 5 11.8 s/0.58 MB, 6 83.6 s/0.89 MB, 7 25.3 s/0.97 MB
(previously 5.8, 0.9, 25.1, 24.6 and 1.3 MB). The previous scythe patches
are still exported (the import check expects them) but no longer drawn when
the slots cover the room. Room renders stay cached per state as before.

Not yet slot units: pressure plates, gates, exits, the room-3 bars, darts and
torches (still `pressure_drawing_commands` and the torch/lava layers).
