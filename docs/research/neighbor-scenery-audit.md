# Connected-room animation audit (2026-11-13)

Follow-up to the user's level-12 room-3 recordings and the moving-panel fix
5060d03. This checks the port's imported scenery and drawing paths; it is
not a native gameplay or whole-renderer equivalence claim.

## Confirmed affected locations

Six views have a tile-26 panel in the bottom row of their upper neighbour.
The previous current-room-only filter omitted the moving panel in every
case. The existing fix covers all six; no additional runtime edit was needed.
Rooms below are native one-based; columns are zero-based.

| Level | View room | Panel's room above | Column |
| --- | --- | --- | --- |
| 10 | 4 | 25 | 1 |
| 10 | 9 | 8 | 5 |
| 10 | 19 | 12 | 7 |
| 12 | 3 | 21 | 3 |
| 12 | 17 | 10 | 1 |
| 13 | 7 | 17 | 1 |

The imported-resource regression enumerates all four temple levels and checks
all 16 phases at each location, requiring a visible phase-3 panel in the
lower view. This verifies supplied activation at the actual level cells,
not a physically reachable player route to every activation.

## Other mechanisms checked

`python -m tools.audit_neighbor_scenery --output rendered/neighbor-inventory.json`
inventories all 384 stored views of levels 3-14. Unused room slots are included.
References are unique by source cell per view, not unique world objects:

| Source family | References owned by another room |
| --- | ---: |
| Pressure mechanisms (gates, plates, exits and dart mouths) | 91 |
| Loose-floor/static mutation slots | 228 |
| Scythe units | 12 |
| Lava records | 3 |
| Torches/candles | 1 |
| Bridge units and potion instances | 0 |

These families use source-room/cell keys from the export, rather than
discarding every noncurrent source. Pressure, loose and scythe signatures
include those keys in the room cache; torch advancement and lava pool setup
also consume the current view's external records. Potions traverse the
exported drawing commands through `LevelMap.tile`, including boundary cells.

A local raster experiment mutated each external pressure/floor source to an
export-supported variant, checked all 60 scythe phase/blood states, stepped
lava for 24 frames and candles through six frames. Changed pixels were
observed for 57 pressure references, 82 floor references and the candle.
The remaining metadata references produced no changed pixels in that sweep;
they are **not certified as correct** by a negative image difference. Some
tables retain dependencies outside the view or beneath later scenery, and
the experiment uses the port's own imported decoder/export. This is not an
independent check of the native renderer or export completeness.

Permanent tests reject stale neighbouring-room gate/floor caches in level 3
and a frozen source-cell candle in level 13's stored room 32. Together with
the six-panel enumeration, these are `tests.test_neighbor_scenery`.

Falling slabs already project upper/lower rooms. Sliding rocks already
project neighbouring MOBs and rectangles; their documented native projection
uses 365 vertically, so it was not replaced with the panel's 364. Spikes
already have a left-neighbour drawing path. Darts retain a current-room draw
restriction: original 8:2e58-2e60 compares the object's room with the view
before enqueuing its picture. Removing all room filters would change that
native rule. Existing spike, rock, dart and slab regressions were selected.

Level-1 harbor and level-2 desert draw paths were also inspected, without a
new native or full raster audit of those environments. Harbor wave-bearing
rooms have no lower link through which their bottom-row animation could
repeat this upper-panel omission. Their room-specific ship/water and desert
CUST animations were not generalized to arbitrary neighbouring rooms.

No second mechanism with the same confirmed omission was found in this
bounded audit. Horizontal/diagonal panels, actor/NPC visibility, atmosphere,
all animation-state combinations, native pixel comparison and campaign
reachability remain outside its result. The separate wall-sticking/room-cut
report remains open.

Validation: 300 focused tests passed without skips (neighbour scenery,
trap-door drawing, temple arrival/candles, scythes, darts, spikes, rocks,
loose floors, lava, harbor and desert). Dependency, Ruff F/E9,
recovery-catalogue and diff checks passed. No runtime change, full-suite run,
live desktop interaction or user-save modification was needed for this audit.
