# Prince Sword Turn Routine `6:26b8`

Research note, 2026-10-21, `claude/ai-research`.

**Implemented in `1e45090`, with the user's authorization; not yet in
`main`.**
- `combat_turn_offset` takes optional bounds and counts a tile-4 cell as a
  barrier when `stone_gate_blocks` holds in environment 3.
- `choose_player_turn` forwards the bounds. The only `scene_prototype.py`
  change is the call site, which passes `player_bounds()`.
- The regression compares a closed gate with a wall, an open gate with clear
  floor, and the case without bounds.

Earlier notes treated this routine as a decision endpoint only. This note
decodes it and compares it with `LevelMap.combat_turn_offset`
(`pop2/terrain.py`). Labels: **[D]** direct reading; **[I]** inference.

## Dispatch `6:2638` [D]

| Actor type `+0x8` | Turn |
| --- | --- |
| 7, 8 | JumpSeq(156), unless the selected sequence is already 156 or 166, or `7:16b8` vetoes |
| 0, 1 (Prince) | `6:26b8` |
| 10 | none in poses 213-217; otherwise as below |
| others | JumpSeq(60), the ordinary NPC turn |

## Prince routine `6:26b8-277a` [D]

1. In level 5, room 10 (native) with a5-0x3130 > 0, it returns with no turn.
2. The allowance `d4` starts at -1, meaning no reserve:
   - **First cell in front** (GetCellsInFront(1), `4:39fc`): if
     `3:4da6` (neither IsWall nor IsSpace) is false, the allowance is 0. A
     tile-4 gate for which the gate collision `4:5b0e` reports a block also
     gives 0.
   - **Second cell**, only when the first was clear: the same test gives 51.
3. When an allowance exists:
   - it gains 22 if the selected sequence is 94, or 51 if the pose is 207;
   - with `d3` = floor-edge distance (`4:3a92`) + allowance, the routine
     moves X by `d3 - 84` when `d3 < 84` (AddCharX, `4:2bae`).
4. JumpSeq(127) always follows.

IsSpace `3:4eb2` (0, 9, 27, 47, 49) and IsWall `3:4ef2` (20, 2, 7, 25, 43)
equal the port's `EMPTY_TILES` and `WALL_TILES`.

## Port comparison

`combat_turn_offset` implements steps 2-3 for walls and gaps, the 94/207
extras and the 84-pixel reserve. Its comment calls it the "ordinary rooftop
subset". The test of `3:4da6` comes before the gate test, so the only
missing case is the **gate**:
- a tile-4 cell that `4:5b0e` reports as blocking is a barrier in the
  original;
- the port treats every tile 4 as floor.

The native turn path has no environment test. The port's own gate collision
(`stone_gate_blocks`) is the counterpart of `4:5b0e`, and it needs the
actor's bounds. `choose_player_turn` passes only the frame record.

### Where it can matter

These are cells of a guard spawn row, not executed fights.

| LEVL | Level | Room (port) | Row | Gate column | Spawn |
| --- | --- | --- | --- | --- | --- |
| 2002 | 3 | 5 | 2 | 9 | skeleton at X 149 |
| 2002 | 3 | 19 | 2 | 0 | skeleton at X 302 |

No other level 1, 3, 4 or 5 spawn row (LEVL 2000, 2002-2004) contains a
tile 4.

## Proposed change (needs coordination)

`pop2/terrain.py` and `pop2/combat.py` are shared interfaces, and caverns
are the level-four track.
- **Change:** `combat_turn_offset` treats a tile-4 cell as a barrier when
  `stone_gate_blocks(tile.foreground, bounds, state)` is true. The call site
  supplies the Prince's bounds.
- **Regressions:**
  - a closed gate one cell ahead gives the offset of a wall;
  - an open gate does not;
  - the existing rooftop turn tests stay unchanged.
