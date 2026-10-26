# Cavern artwork review

These are intentional port artwork improvements, not recovered game rules.
Keep imported native resources untouched; bake approved pixel edits into the
source-hash-checked, level/room/placement-specific retouch atlas.

## Continuous wall and shadow joins

The user approved level4 room12's left V5 and right V3 on 2026-10-26. The
combined image changes791 native pixels in six background sprite placements.
Foreground columns, silhouettes, transparency and actor masks are unchanged.
The integrated render's RGB SHA256 is
`531028e35010c0fda94c7a6b20b9f89f2169f37f0a13bca7dae7d620faf92059`.

For future rooms with the same problem, use this approved visual approach:

- Continue the upper wall's texture and lighting through the junction. Merely
  feathering the outline of a differently lit rectangle leaves a visible patch.
- Follow the actual column contour. Where the column narrows, the newly
  exposed background also needs the continuation; a fixed vertical strip can
  miss it and leave a bright rectangular lower section.
- Retain local texture, the native pixel grid and palette. In this case the
  upper lighting profile was extended relative to the column edge, preserving
  local texture variation and grading into the lower shadow. No rectangular
  donor texture was pasted and the foreground column was not blurred.
- Confine changes to the affected join and compare both the whole room and
  enlarged detail. Keep previously approved neighboring artwork identical.

The room12 previews and pixel-edit scripts remain local under the existing
art-review worktree's ignored `rendered/level4-room12-shadow-v*/` outputs.
V1-V4 are intermediate proposals; V5 is the approved combined image. Future
matching cases should start from this method rather than repeat the rejected
outline-only treatment. Present the resulting local preview for art review
before committing a new room's artwork.

## Level4 room23: preserve V1 detail and fade the marked join

The user approved room23 V9 on 2026-10-26. It retains V1's wall texture and
stalactite colours, adding only a narrow gradient at the marked vertical join.
The lower dark side's added brightness is limited to avoid a continuous light
stripe. The final render changes2035 pixels from the native room in two
source-checked sprite placements: background3550 and foreground rock face3541.
The rock face's colours change locally; transparency, silhouette, actor masks
and physical columns remain unchanged. The integrated render's RGB SHA256 is
`f4a72ba65bba70226a882dcb4cb9394e1e85b8dc688340ccd5aca5a2dfdbe68a`.

Some grey areas are part of the stalactites' modelling. Broad grey recolouring
and dark-patch removal made the relief less legible and were rejected. Preserve
this detail when treating similar joins: follow the user's marked boundary,
compare the neighbouring rock in context, and avoid turning the gradient into
a bright rim. Do not classify all grey or dark pixels as dirt to remove.

V1 and V9 are the relevant reference images; the intermediate cleanup variants
are not part of the approved result. Local previews remain under the working
tree's ignored `rendered/level4-room23-shadow-v*/` directories.
