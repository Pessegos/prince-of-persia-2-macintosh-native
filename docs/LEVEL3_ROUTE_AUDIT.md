# Level 3 Route Audit

## Reference And Limits

Reference: `lvl 3 clean route macintosh.mp4`, supplied by the user. The recording
is approximately 155.5 seconds at 60 fps, beginning before the manual challenge
and ending at the final door. Overview frames were sampled every two seconds;
the entrance and both health upgrades were examined at shorter intervals.
Times below are navigation references, not recovered engine timing constants.

Room numbers are one-based Macintosh LEVL/F2 `Room` numbers, not a numbered
walkthrough. Room identification uses scenery and the original room links;
intermediate rooms can be traversed between overview samples. Black frames and
the manual dialog must not be classified as cavern rooms.

The route avoids most lethal trap contacts. It is useful for navigation,
layering, object activation, upgrades, enemy encounters and exit behavior.
It does not establish lethal lava/spike rules or every projectile outcome.
Those still require native-code recovery and, where useful, targeted recordings.
Do not derive collision windows or trap delays from this successful route alone.

## Reference Moments

| Approximate Time | Macintosh Observation | Port Boundary |
| --- | --- | --- |
| 6-12 s | Room 1 entrance door closes; Prince descends past the foreground columns and the camera cuts down to Room 4 | Door remains at its exported initial phase; no cavern door/plate controller exists |
| 12-24 s | Upper/lower routes through Rooms 4, 16, 3, 10, 2 and 14; loose pieces move and foreground geometry conceals parts of the actor | Common movement follows links, but the exported drawing and static row masks are not a validated movement model |
| 24-36 s | Skeleton activation and evasion in Room 14 | Special opponents are deliberately omitted by the preview encounter host |
| 37.5-39.5 s | First mega potion, Room 10, row 1/column 7; drink animation, flask removal and health capacity 3 -> 4 | Flask drawing is incorrectly sourced; collection and upgrades are not implemented |
| 40-66 s | Route through Rooms 14, 15, 17, 19, 22 and 18, with jumps, descents and active hazards | Object and hazard controllers are absent; scenery availability is not route playability |
| 68-70 s | Second mega potion, Room 20, row 0/column 8; health capacity 4 -> 5 | No cavern potion interaction or capacity upgrade |
| 71-90 s | Skeleton combat on the lower floor of Room 20 | No skeleton sprites, activation, combat or persistence |
| 92-138 s | Return through Rooms 21, 26, 27, 28, 25, 24 and 23; non-upgrade flasks are passed without drinking | Preserve potion types and locations from LEVL; do not label every visible flask as a mega potion |
| 140-155 s | Room 13 final door is opened and entered | Cavern exit controller and completion behavior remain unrecovered |

The two visible upgrades are in Rooms 10 and 20. The flask near the lava at
Room 26 is passed, not collected. Its blue bubbles are not a health-upgrade
specification. Potion behavior must be decoded independently of visual color.

## Confirmed Exporter Defect

The importer intercepts AddNextBFItemToTable at CODE:3 0004. The BF descriptor's
first word identifies the shape library. `recover_room` currently replaces all
libraries with `3500 + shape_index`, then runtime decodes Caverns.rsrc with
CTBL:3500. That is only appropriate for cavern items, not flask items.

Observed while executing the original drawing code for Room 26:

```text
item_type  shape_index  draw_mode  column  row
1          1            16         6       2
1          9            233        6       2
1          19           234        6       2
```

The latter two are exported incorrectly as Caverns SHAP:3509 and SHAP:3519,
both large rock pieces, at X 331/bottom 332. The body is likewise interpreted
as a cavern shape. This is an actual import/rendering bug, not a missing
gameplay controller or a Macintosh/DOS difference.

Native source: GetFlaskBubbleColor (3:46fc, including item-type assignment at
4764-4768) and LoadFlaskSet (3:5614, selecting SHPL:3000 at 5630-5638 and palette
relocation at 564c-5658). Prince.rsrc contains SHPL:3000 with SHAP:3001-3033.
Some of these are monochrome/compressed masks, so changing the shape-ID base
alone is insufficient: recover the library, palette relocation, mask decoding
and draw mode together. Runtime currently discards the draw-mode field too.

## Recovery Order And Acceptance

1. Correct the portable export's library identities and drawing modes. Validate
   room images against Macintosh frames, especially flask rooms; a nonblank
   image or successful room load is insufficient.
2. Make Room 1 functional: entry door, plates, terrain contact, descent/climb
   occlusion and camera cuts. Compare actor positions and layer ordering, not
   elapsed route time with unknown player inputs.
3. Recover reusable gate, plate and loose-floor state across rooms. Keep native
   tile phases in the session and feed the same state to drawing and collision.
4. Recover potion collection and both upgrades, including sequence, capacity,
   effects, removal and persistence. Test their original tile types, not a
   special case for the two rooms on this route.
5. Recover skeleton resources and native activation/combat/death behavior.
6. Recover hazards, music and the exit; then test the complete route and side
   rooms. Cavern ambient music is currently not requested by `advance_audio`.

Useful native entry points already indexed include TriggerGateWithRevPlate
(8:2c38), DrawCaveExitMovable (8:1ba4), Trigger/PushPlate and CloseExit (CODE:5),
DrawObjCaveLoose (8:2bb4), skeleton routines (4:17aa-1a86), CheckDartHit/MobDart
(8:2e82/2f98), lava routines (8:31fe-38e4), and CaveMoveSquishingGate (8:3a58).
Their presence in the recovery catalog does not mean their rules are already
implemented or semantically verified.

No gameplay changes were made during this audit. The previous 32-room tests
still establish coverage and clip handling only; they do not certify a
Macintosh-faithful level 3, even in the starting room.
