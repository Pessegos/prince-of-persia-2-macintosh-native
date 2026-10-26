# Ruins tunnel reveal coverage

The initial repair directly reproduced level6 room18's disappearing Prince;
its scenery comparison also covered the linked room17. It cleared stale
per-cell actor masks when RedrawCell painted new background over a wall.
That was a shared renderer fix, but was not then an exhaustive tunnel audit.

The follow-up checks all actual tile7 cells in levels6-9 against exported
reveal units:11 connected tunnel groups,45 cells across16 rooms. It renders
all31 nonempty reveal combinations in affected exports, including neighbor
drawing dependencies and rooms with two groups. Each is checked both during
incremental reveal and upon entry into an already-revealed room:62 renders.

An in-memory simulation omits only the previous cell-mask clearing block.
Scenery pixels remain byte-identical; stale actor masks return in every
actual tunnel room below. The current renderer has zero mask pixels left
over where the foreground has already been erased, in all checked states.
The actor-mask selection path is also checked at three prone-body bounds
per actual tunnel cell. This is automated offscreen rendering, not manual
gameplay through each entrance or independent native QuickDraw proof.

| Level | Tunnel groups | Cells | Rooms affected by the old mask omission |
| --- | --- | --- | --- |
| 6 | 2 | 9 | 17,18,22,25 |
| 7 | 3 | 17 | 1,5,18,19 |
| 8 | 4 | 12 | 2,4,5,17,18 |
| 9 | 2 | 7 | 7,19,20 |

These are native/user-facing room numbers. A neighbor drawing in level9
room1 also loses two obsolete mask pixels; it is not an additional tunnel.
Other neighbor-only dependencies have no stale pixels in this simulation.
The room18 fix already covers all of these; no additional gameplay or
asset change is needed, and original resources are unchanged.

```powershell
.venv\Scripts\python.exe -m tools.audit_ruins_tunnels --output rendered\ruins-tunnels\mask-audit.json
.venv\Scripts\python.exe -m unittest -q tests.test_ruins_tunnel_masks tests.test_ruins_scenery_items tests.test_crevices
```

The detailed report stays local/ignored. The legacy simulation is a host
regression control, not execution of an older executable. The audit and
three imported-asset regressions were added after the user's coverage query.
