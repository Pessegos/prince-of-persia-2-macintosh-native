# Temple Controller With Real Cell Geometry

Research only, extending [PlayerCtrl in the world caller](temple-player-control.md).
No runtime, artwork, save or playable temple changes.

## Correction And Connected Findings

The old supplied-bool field/event `bars` was misnamed: original `10:2036`
is SlideRockInCell. It tests a sliding rock against the cached cell. Older
corpora only supplied its boolean; they never proved bars behavior. Their
comparison digests remain unchanged. This composition executes the real body.

Actual world/Prince/PlayerCtrl/GenCtrl now use native current/front/above
helpers `4:35a6/3a48/3ff8`, ReadCell `4:27ee`, room normalization/cache,
SlideRockInCell `10:2036`, GetSlideRockX `10:180e`, room/row lookup `10:1a9e`
and type6 MOB enumeration `5:293c` before the ordinary clip and actor save.

- Cell kinds/foreground now come from original temple level bytes, not
  supplied controller answers. Reads preserve native conditional order and
  all six cache words: kind, foreground, cell, room, column and row.
- The native front-cell DATA offsets are+1 for facing-1 and-1 for facing0.
  Do not replace this with a guessed sign from the actor's visual X/facing:
  the controller's supplied column is an anchor, not a recovered foot cell.
- Horizontal/vertical traversal updates cached normalized room/column/row.
  The subsequent rock lookup uses that cache, including an upstairs or
  neighboring room, rather than blindly querying the actor's original room.
- Header room admission still applies. Raw level12 room29 data is not
  automatically a valid cell. Level13 undefined-cell results can depend on
  view room, as in the separately recovered ReadCell proof.
- Rock lookup selects the first matching live type6 record for that normalized
  room/row, skipping mark-1. Control100 does not by itself remove a record.
  An absent rock is false; static supplied rocks can change climb10 to73.
- Occupancy tests the right edge first, with inclusive boundaries and an
  immediate true return. Otherwise it computes the left edge. Wall/gate
  clipping reads raw level words and the native column table, not ReadCell;
  this must not replace or corrupt the controller's cached cell.
- Left-edge calculation writes the signed division remainder used by the
  native column helper. Facing0 can add the supplied frame width to the
  clipping boundary. The raw edge is raised to that boundary with `max`,
  not reduced with `min`. Testing only the final occupancy boolean can conceal
  a bad edge value, so direct controls also compare the edge itself.
- Gate-bank selection, live control decisions, preview/ordinary animation
  and actual Prince save remain connected. Real geometry can replace47;
  preview actor effects continue through the final save.

## Reproducer And Validation

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_controller_geometry --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_controller_geometry_v4.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_controller_geometry_reference
```

**9,534 native/reference world-update comparisons, zero mismatches.**
There are3,660 all-admitted-cell climbs,4,392 room-edge controls,738 gate
controls,144 normalized-border controls and600 static-rock climb controls.
12,720 ReadCell entries and423 real DoJumpHang previews occur in that corpus.

**8,064 additional direct helper comparisons, zero mismatches**, across4,032
fixtures: an occupancy result and an actual left-edge result per fixture.
3,708 native left-clipping branches execute. These are not extra world frames.
The first reference's `min` hypothesis failed these controls and was corrected
to the native `max`: for X102, a raw gate, facing0 and width40, the native
left edge is337, not320. Tests preserve this distinction.

World fixtures cover a climb request at every header-admitted cell in all
four temple levels, edge-column requests in both facings, all41 original
gate anchors, normalized border/undefined-room controls and supplied static
rock banks. Direct helper fixtures vary X, cached column, margins0/5/51,
facing, supplied frame width and raw space/floor/gate/wall words.

World comparisons include complete level data, both62-byte actors, TROB
count/records/storage/scratch, object scratch, return value, ordered events
and service counts, latch banks/axes/cooldown, all cell-cache words, division
remainder, saved edges/countdown/view/exit flag and the full512-byte guarded
MOB-bank region. MOB scratch/pointer, count, pending effect and prepared
sequence data/handles are also checked. The bank pointer occupies bytes16..19
of the22-byte scratch/canary region and is initialized accordingly.

Direct controls compare both the occupancy result and actual returned left
edge, their ordered native calls, division remainder, level/cache, actor
records, TROB storage and guarded MOB bank. No service sink is reached by
these direct query calls. Fifteen asset-free tests reject incorrect neighbor
offsets, stale cache/room use, eager extra query events, any-match bank lookup,
wrong edge boundaries/clipping, lost division remainder and unsupported bounds.

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
World compared-output SHA256:
`4651d56e34b8f358690cae9987bceeecbdac23d70aadaae26326915c1830f101`.
Direct helper compared-output SHA256:
`d0e11464cee949b925c7ac2612552d3b9ee66626c10e70f987bdbb3736a197f9`.
Original level/sequence hashes stay in the ignored report; no original
resource bytes are committed. The world digest is also checked unchanged
after adding/correcting the separately counted direct-edge controls.

## Boundaries And Next Work

This replaces the three cell-query and rock-occupancy sinks of the previous
composition. Input polling `2:55d2` still supplies sampled axes. Other
world/Prince `ENDPOINTS` remain request/result sinks: frame/sword/edges,
barrier/collision/gate/floor/pressure/hazards, rubble/generators/opponents,
effects/environment/cuts/clock/timeout. Cue/redraw/audio `5:3828/0fe6/4d84`,
prepared sequence handles `17:330e/4:3098` and state0 handle traps remain
supplied. Demo controls are inactive, as in the previous caller proof.

Actor column/row/X/Y, frame width, gate phases and static MOB banks are
fixtures. Rock generation/movement and dynamic MOB-bank lifetime are not
executed here; a passing query does not prove the supplied actor or rock
placement physically reachable. Direct clipping controls stay within checked
raw level offsets/table indices, not arbitrary signed-overflow coordinates.

These are single-world-update fixtures, not persistent gameplay, complete
FrameAdv, actual keyboard sampling, full support/foot geometry, collision/
fall/death, drawing/audio, save/reset or temple runtime integration. Next:
recover the frame/foot/edge calculation that supplies those controller anchors,
then carry real geometry through persistent actor movement and contact.
