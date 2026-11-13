# Trap-Door Presentation And Restoration

The original probe below is research/reference only. The November 13 port
renderer follow-up is recorded at the end.

```powershell
python -m tools.probe_temple_trapdoor_presentation --source PATH_TO_RECOVERY --output rendered/temple-native-trapdoor-presentation.json
python -m unittest -q tests.test_temple_trapdoor_presentation_reference
```

## Evidence And Boundaries

| Rule | Source | Executed Scope |
| --- | --- | --- |
| Project object to current/neighbor view | 10:225c-2308 | Full original logic, supplied room relationship globals |
| Restore level cell and mark object deleted | 10:2328-23ce | Full original logic, sound reset/request supplied |
| Select animation metadata | 10:23d0-23fa; DATA-2866/-2842 | Original tables and instructions; valid low phases1..31 |
| Read cached shape dimensions | 3:533a-53fe | Native ready-cache branch, prepared item/handle/header memory |
| Build current-room moving-object rect | 5:32f6-33e6 | Native current-room branch with transient object coordinates |
| Draw/redraw, visibility, rectangle intersection | Supplied endpoints below | Not independent native renderer/visibility equivalence |

8,680 comparisons pass across all ten actual type26 locations. Low phases
1..31, upper bit0/64, pending cue-1/198 and seven view/visibility scenarios
are supplied. There are 1,240 visible-current-room cases and 4,200 terminal
restorations; these are subsets, not extra case counts. All five animation
records are used. Ten asset-free tests cover reference behavior separately.

Checks compare the entire level, all eight object words, pending cue,
projected screen-cell index, dimensions, visibility query coordinates,
requested image indices, audio/redraw calls, clipped rectangle requests and
object-draw coordinates. No SHAP pixels are rasterized or compared.

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Temple.rsrc SHA256:
`7c7b532ef5251949b299d6177962062bdb003b385675285873d77f865ea68ccf`.

## Recovered Lifecycle Effects

ATMTrapDoor does NOT advance word+0xe. Its low five bits select an animation
phase. If that phase is >16, BEFORE checking visibility:

- Mark object word+6=-1.
- Restore tile26 at the ORIGINAL object room/row/column, not projected view.
- Clear only the foreground LOW byte, preserving the high byte/background.
- Request sound reset198 and sound27; clear pending cue198 to-1, leaving
  other pending values untouched in the supplied cases.
- Use phase17 for subsequent metadata lookup, regardless of higher low phase.

Restoration therefore does not depend on the supplied visibility result.
Actual IsVisibleRoomCell geometry is not certified by that observation.
The advancement/bank-compaction pass is recovered separately in
[phase advancement](temple-trapdoor-advance.md).

In nonterminal visible cases, x/y offsets from the animation table temporarily
alter the object used for dimensions/rectangles/draw requests. The original
X and Y are restored before returning. These offsets are NOT persistent
physics motion, gravity or a change of stored row/room.

Terminal visible cases still request dimensions/redraw but do not enqueue
an object draw or its extra rectangle, because word+6 is now-1. Invisible
cases skip dimensions/redraw/object draw entirely, while still restoring
the level when terminal.

## View And Shape Details

Projection uses vertical +/-364 and horizontal +/-510 for the tested supplied
adjacent-room relationships; it does not replace364 with a generic360.
All relationship scenarios are tested with visibility false. Visible tests
are CURRENT ROOM ONLY: neighboring-room ComputeMobRect/OffsetRect paths
are deliberately excluded.

The visibility query uses projected room/column but the object's stored row.
The separate projected screen-cell index uses projected Y/120. Those two
indices need not be identical; a bottom-row object can produce sentinel30.

Animation lookup uses the original low-phase map and five six-byte records
(shape, dx, dy). The probe prepares native shape-cache entries/handles from
the five actual Temple SHAP headers and SHPL3500 base3501. Native
GetBGSetImgSize reads cached width/height; resource loading/decompression
is NOT executed. Native dimension/rectangle arithmetic then executes.

Phase0 is excluded: map entry0 is66, not one of the five animation records.
Constructor paths start at1/75 (low1/11) and the recovered advancement reaches
low17 without cycling through0. This is not a general proof that malformed
or externally supplied phase0 cannot occur elsewhere.

## Supplied Services

- 5:3960 visibility returns the supplied boolean; native query inputs checked.
- 5:5252 sound reset and5:4d84 sound request are recorded, without real audio.
- 5:33fa/19f8 redraw requests and5:346a object draw are recorded, not executed.
- A5-1f58 SectRect callback is supplied rectangle arithmetic with Pascal
  stack/result cleanup. No claim of native QuickDraw implementation equivalence.
- Prepared image-cache entries contain actual SHAP header bytes, not rendered
  images or proof of cache/resource-manager lifecycle equivalence.

The fixture supplies a roomy clipping rectangle. No visible-neighbor path,
sound queue, sprite pixels, collision/damage, complete FrameAdv scheduling,
save/restart or playable campaign integration is certified.
The subsequent [connected lifecycle probe](temple-trapdoor-lifecycle.md) joins
constructor, advance-bank and presentation-bank passes in explicit sequences,
observing deletion/compaction across calls without claiming complete FrameAdv.

## Upper-room animation missing in level 12 room 3 (2026-11-13)

The user's paired Macintosh/port recordings show the bottom-row panel in
native room 21 swinging into the top of room 3 after the Prince jumps. The
port removes the static closed panel but omits the moving panel entirely.
`draw_trapdoors` filtered its objects to the current room, even though
`TrapDoors.present` retained the upper-room animation object.

The drawing helper now receives the current terrain links and projects panels
from above by Y-364 and below by Y+364, then clips their sprites to the frame.
The original object coordinates, phase bank, activation, restored floor and
collision are unchanged. This applies to vertical links throughout the temple,
without a room-specific exception. Horizontal/diagonal neighbouring panels
remain outside this change.

Static evidence: ATMTrapDoor 10:2274-22da projects adjacent-room objects before
its screen-cell query; 10:2294-22a0 subtracts 364 for A5-4fbc. Room setup
3:1b1c-1b36 identifies A5-4fbc as the LEVL +4 (upper) link and A5-4fba as
+6 (lower). **The historical probe's `above`/`below` labels are reversed**:
its globals and matching arithmetic are supplied consistently, so its old
comparisons do not independently validate the semantic direction names.
The follow-up uses the actual room links and the recorded Macintosh picture.
No new native CPU or QuickDraw pixel-equivalence claim is made.

`tests.test_trapdoor_drawing` covers clipped sprites from the current, upper
and lower rooms, absent links and unrelated rooms without imported assets.
The real hidden scene regression in `tests.test_temple_arrival` triggers the
room-21 panel while viewing room 3 and checks visible top-edge pixels through
the environment's scenery path. All 16 animation phases also match the same
upper-room sprite raster translated by 364 pixels; the old current-room-only
filter fails this regression. Existing trap-door lifecycle and scenery tests
remain intact. No physical input or live game window is used.

Validation: 208 selected tests passed (arrival, playtest, candles, four
trap-door reference modules and cavern drawing/retouch modules); dependency,
Ruff F/E9, recovery-catalogue and diff checks passed. Full discovery was not
repeated for this drawing-only change. The separate wall-sticking/room-cut
report remains open and is not resolved by this animation fix.

## Room-1 flat-panel mask and missing front lip (2026-11-13)

The user's subsequent paired level12 room1 recordings show the rotating
tile's edge cutting into the floor. The moving-panel implementation drew
one masked SHAP for every animation record. That is incomplete for the flat
record (Temple piece28), used at low phases10 and15.

DrawObjTrapDoor10:26ea-2790 selects the animation piece from the original
phase map. For pieces51..54 it calls AddMid once, masked (transfer mode16).
For piece28, 10:272c-2766 instead emits **two** pieces:28 at the moving
object's X+1, then29 at the object's X with transfer mode0 (opaque copy).
Both raw calls use objectY-1; AddMid3:0302-030c stores the exclusive bottom
as rawY+1. The moving-object X already includes ATMTrapDoor's table offset;
the extra one-pixel offset of piece28 is a separate drawing adjustment.

The port now uses those two native drawing commands for the flat record.
The missing51x5 front lip previously exposed the red wall through the open
slot during that pose; the original copy operation fills it with the floor
edge. The actual Temple piece29 contains no transparent pixels, so the
missing piece/offset is the cause here, rather than a new SHAP-alpha decoder
bug. Its original mode0 is preserved. Other rotation pieces remain masked.
The existing moving-object clip is applied to both pieces. Drawing order,
physics, activation, phase advancement, cell restoration and upper/lower
room projection are unchanged; no room-specific exception is introduced.

```powershell
.venv\Scripts\python.exe -m tools.probe_trapdoor_drawing --source ..\PoP2-Mac-Code-Recovery --output rendered\trapdoor-drawing.json
.venv\Scripts\python.exe -m unittest -q tests.test_trapdoor_drawing tests.test_neighbor_scenery tests.test_temple_arrival
```

The probe executes original10:26ea-2790 for all ten actual tile26 locations
of levels10-13, low phases1..16 and upper bits0/64:320 comparisons,360
ordered drawing commands,40 flat poses, zero mismatches. The original phase
and frame records come from DATA, not the port constants. Level/environment
headers and the Temple SHPL3500 base3501 are checked. Level bytes remain
unchanged. Executable, Prince and Temple resource SHA256 values are recorded
in the local output.

AddMid is a recorded endpoint; the inclusive-bottom conversion is checked
by static reading of3:0302-030c, not by executing AddMid or QuickDraw. Phase
and projected X/Y are supplied fixtures. This verifies piece selection,
positions, modes and order, not full native dirty-cell ordering, actor
occlusion, pixel equivalence, resource-manager behavior or FrameAdv.

The real hidden-scene regression jumps in room1 away from the trap, observes
its flat pose and checks the front-edge pixel through the complete scene
renderer. It then verifies that the tile closes. Substituting the old drawing
fails with red wall RGB123,41,16 instead of lip RGB66,57,82; the old single
command also fails the native comparison at low phase10. An asset-free test
checks the body's extra X offset and opaque front call. Existing linked-room
tests retain all16 phases and all six upper-panel positions. Intentional
negative-control failures are not successful tests of the old implementation.

The focused temple and scenery suites pass219 tests (111+108, no skips).
Dependency, Ruff F/E9, recovery-catalogue and diff checks also pass. Full
gameplay discovery is not repeated for this drawing-only change. No live game/emulator, original
resource writes or user save/settings changes are involved.
