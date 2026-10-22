# Trap-Door Presentation And Restoration

Research/reference only. No runtime or actual pixel renderer changes.

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
