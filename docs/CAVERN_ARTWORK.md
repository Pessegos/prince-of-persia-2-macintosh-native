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

## Level4 room22: gradient behind the column

The user approved room22 V1 on 2026-10-26. Two source-checked background crops
(SHAP3550 and3518) grade the marked colour discontinuity behind the left column.
The213 changed native pixels are confined to X37..42/Y259..317. The actual
foreground column, its outline, transparency and actor masks stay intact;
the existing doorway blend is preserved. This is a baked native-palette pixel
gradient, not an overlay or an RGB blur. The combined render's RGB SHA256 is
`74912e7249bf2e288597df09ca426527045adc8cc55a9e75c0883408060cde16`.
The exit animation retains the same local correction. Local review images
remain under `rendered/level4-room22-shadow-v1/`.

## Level4 final batch: rooms5,14,26 and28

The user approved these four rooms individually, then approved integration of
the complete batch on 2026-10-27. Seventeen additional source-checked crops
apply only to these level4 placements. Earlier atlas crops remain unchanged.

| Room | Approved version | Changed native pixels | Render RGB SHA256 |
| --- | --- | --- | --- |
| 5 | V1 | 382 | `421ee7b40f740af3598ef7d1c3b8acf5ba6a5b4fd4394a2a684ed017f53d5290` |
| 14 | V1 | 608 | `6c545e48efa6fde6a208453d89c3bd5785bdb9fcf1bdee055d086521553c7933` |
| 26 | V4 | 481 | `9ef82c6d26f7540b12e655ed87dcebaf0ab4f3ba810f609ac75d0735ab096197` |
| 28 | V3 | 336 | `d60832d8900669a315a5868ea9d069755f5b330f4c12b5618e6567578c8e1d63` |

Room5 continues the matching approved room12 lighting. Room14 grades a wider
shadow beside its upper column. In room26, follow the widening column contour
and continue the accepted upper gradient gradually into the lower rim; resetting
the shading at a fixed row produced a rejected horizontal cut. The lit column
bodies retain their original pixels. Only their outer dark shadow fringe may
change colour; alpha, silhouettes and actor masks stay identical.

Room28 preserves its foreground completely. The right-hand circle in the first
reference indicated an area, not a contour to trace: the requested gradient is
across the vertical background join beside the stalactite. V3 also softens the
small squared shadow shoulder below it. Keep the approved left join unchanged
while revising the right. All four use the native palette and pixel grid, with
local texture retained rather than blurred. Local previews and the approval
manifest remain under ignored `rendered/level4-art-batch/` and the corresponding
`rendered/level4-room*-shadow-v*/` folders.

## Level5 final batch: eight approved rooms

The user approved room17 V2 and closed the cavern-artwork review on2026-10-27.
Forty-one room/placement-specific crops reproduce the eight approved images,
changing9497 visible native pixels across the review states below. Earlier
level3/4 crops and doorway blends remain unchanged. Imported resources stay
untouched, and the runtime's native-artwork opt-out remains available.

| Room | Version | Changed pixels | Render RGB SHA256 |
| --- | --- | --- | --- |
| 6 | V2 | 2747 | `2ef93b2f6a12554f9f77acc4b07a523187769454c65eab587417dbebeb805eae` |
| 7 | V1 | 1196 | `d879511695be25224c60c436910ba09e3b6f44fa602f44dbd165966b3a13ad7f` |
| 14 | V1 | 764 | `dc3972e7a39d9f9499afc088edcf5b4792346376e500d5a1ff548922e86c96c5` |
| 15 | V1 | 643 | `2e5bc07ca34916df66c27435e220421e87f77f0e2e4ccdd7859ab7fe42c0e756` |
| 16 | V1 | 1231 | `5cadd904b80f1fc11fd21a8eb4fd3d44ccee4ff62b8f9ba2f831b9270e3c3413` |
| 17 | V2 | 1619 | `fbb686730f48d2a6e589fb13b4202a0fdcdeecddc1c3aaa751499c22ff44e471` |
| 23 | V1 | 226 | `0cb8d78015db256f4843c6cf58a55104476a7ad8507b345d2fc865534467e789` |
| 25 | V2 | 1071 | `4ba338d53567d00d272402a59fec0fb9664aee9fd3a164cc0ac65341f23d74a6` |

Room7's approval shows the stone gate fully open (`pressure_key=(46,0,0)`). Its
wide gradient belongs exclusively to the two static wall pieces, not the gate;
the same local artwork must remain correct throughout the gate's movement.
Rooms6,15,16 and25 follow the actual widening column contours. Only their outer
dark shadow fringe may recolour; lit column bodies and silhouettes stay native.
Room25's right-hand lower wall was explicitly left unchanged.

Rooms6 and17 reuse the approved room1 level3 wall behind their own foreground
columns. A source-checked crop can still expose a previously hidden edge in a
different placement: this produced a thin dark stroke at X396 in room6 and
X192 in room17. Their final approved versions remove those introduced strokes.
Room17 restores its exposed right margin exactly to native pixels. The last
three colour columns of the neighboring foreground rock faces may grade
locally, as approved; physical foreground columns remain exact.

All edits retain the native palette and pixel grid. Transparency, retained
pixels, actor occlusion, climbing/floor redraw masks and moving-gate masks
are unchanged. Gradients are baked into the bundled atlas and applied when
building cached room images, not recomputed pixel by pixel each frame.
Local approvals and baking reports remain under ignored
`rendered/level5-art-review/`. README comparison selection is a separate user
decision; this artwork review does not replace its wording.

## Level8 room5: clipped upper-left column fragment

The user approved the comparison's right-hand preview on2026-11-05.
Omit only the back-layer SHAP3525 command at X0/bottom5/mode16/row-1, with
its exact native clip and library4. That mostly offscreen column left a beige
triangle at the upper-left corner. The existing wall underneath replaces24
visible pixels within X0..7/Y0..4. This is an intentional port improvement,
not a correction to the original resources or a native drawing rule.

Combined RGB SHA256:
`c05c2e3cd36ad9d88399c0ac1cba8c2edd39cd6988568dd72a10595ef414a6f9`.
Foreground, retained pixels, actor/climb/floor/cell/gate masks are unchanged.
The native-artwork opt-out still draws the original fragment. No atlas or
imported-resource writes are required; the command omission applies only
to level8 room5. The comparison is kept locally at
`rendered/ruins-second-batch/room5-review.png`.

## Repeated column shadows: five-room review

The user approved the V4 proposals on 2026-11-07. They retain the V2 wall
continuation and adjust only the isolated bright sample that repeated as a
one-pixel vertical strip. The broader V3 reduction was rejected. Preserve the
accepted wall texture and lighting rather than reducing the whole treatment.

These are placement-specific cached sprite crops. Imported resources, lit
column bodies, transparency, actor occlusion and floor/climb/gate masks are
unchanged. Existing approved source edits are composed into the updated crops.
Room numbers below are native, one-based; only column 1 in each reviewed room
is included. Other columns found during the inventory are not approved targets.

| Level | Room | Column X / bottom | Added visible changes | Combined render RGB SHA256 |
| --- | --- | --- | --- | --- |
| 3 | 1 | 111 / 243 | 585 | `470358256d02d9371eabfc773426c3b6949e14c62852acbf6b9eac022ad44f02` |
| 3 | 5 | 60 / 243 | 585 | `1dce1829805dde96885605ac6cd555351d5969147d14626401a2979da95a12a5` |
| 3 | 13 | 213 / 243 | 591 | `d7dceac57950745d0880bdc06aea68f923d59006f722dda0a823b0d14e0f9298` |
| 5 | 2 | 60 / 243 | 591 | `1f686b8ae78cb4885972c07d6d62baf4fb691568eb0aac6e745b6c25d08c324f` |
| 5 | 23 | 60 / 243 | 593 | `cad5cd9c75b8de390f507820356915a8bf915adfe8eb29731e39a54f4b533f4e` |

The enlarged comparisons and approval manifest remain local under
`rendered/column-shadow-five-v4/`. Each row's hash uses the static cached room
without separately animated scenery items, matching the gameplay renderer.

Level5 room23 retains its earlier226 wall edits; the combined static artwork
now differs from native at819 pixels. Its67 foreground changes are confined
to the approved outer shadow fringe, with the column body and masks intact.
These five-room goldens supersede the earlier level3 room1 and level5 room23
whole-room hashes while preserving their other approved artwork.

## Level3 rooms7 and8: missed column-shadow contexts

The user approved the follow-up previews on 2026-11-07. Room7's affected
lower shadow context is pixel-identical to room5 before V4, even though the
wall above is darker. Classifying a join from that upper colour alone missed
this placement. Room8 is a close variant of level5 room2; its small native
texture differences are retained when applying the approved lighting change.

The follow-up extends the five-room approval only to these two placements:

| Level | Room | Column X / bottom | Added visible changes | Combined render RGB SHA256 |
| --- | --- | --- | --- | --- |
| 3 | 7 | 366 / 363 | 585 | `07151ff23ba5c20cf5fbf29a65b08c80c80041705ecf7657fa18e4fcb6294d5e` |
| 3 | 8 | 366 / 243 | 589 | `9043537b7de6fc860b4b72ec272dd8c44486179d4e224914df2fd90b676c8073` |

Earlier approved rooms, lit column bodies, transparency and physical/actor
masks remain unchanged. Comparisons are local under
`rendered/column-shadow-followup-v1/`. The audit covers static contexts of this
column model; its former exclusion list is not proof that all cavern artwork
has been corrected. Keep visual review of genuinely different contexts separate.

## Short columns: approved upper and lower joins

The user approved the short-column V2 review on 2026-11-07. Room5's small
P3 column at X212/bottom362 needs the continuation on its upper half too.
The new treatment follows the actual SHAP3531 contour through the dark
outer source fringe and adjacent wall, retaining native texture and palette.
It preserves the lit stone, alpha and all actor/floor/climb/gate masks.

Five source-checked crops add690 visible changes to this room. The earlier
long-column V4 remains intact; the combined cached RGB hash is now
`4c21295ad0cc54ed2aecc91cf40433df13f4576ee3fab320c53544783cc798a5`.
The approved comparisons remain local under `rendered/short-column-selected-v2/`.

The same review approves level4 room6's P1 and P2 short columns, both at
X365 with bottoms242 and362. Ten placement-specific crops add1242 visible
changes. The upper column's overlying rock stays intact; only the visible
dark contour and adjacent wall are treated. The combined cached RGB hash is
`78c0838162512e9e1c29a17e6d160173e6c7c4545935e3908c20a340a3adaabb`.

Level5 room22's P1 at X110/bottom242 completes this four-column selection.
Five crops add691 visible changes, with cached RGB hash
`85d1c7b09db45de43cd81f3af54943bddbff9413b088d25236a44bf6dad1609b`.
All four preserve the native source alpha and the inner/lit stone body.
The upper dark-fringe changes are limited to the outer three pixels of the
actual contour, with native RGB at most66 and green at most33; this is a
local reviewed exception to the earlier darker-fringe-only treatments.
The first short-column proposal was not approved because it left the upper
join untreated. V2 retains its lower treatment and extends through the upper
join; none of the inventory's other similar contexts are approved targets.

## Level3 room24: long-column shadow and lower wall join

The user approved room24's two separate local comparisons on 2026-11-07.
The upper/middle SHAP3533 at X264/bottom243 uses four source-checked crops
to continue the wall lighting along its actual contour, changing553 visible
pixels. Its lit stone and all alpha/actor/floor/climb/gate masks stay intact.
The neighboring background SHAP3534 column is preserved completely.

The upper adjustment alone has cached RGB hash
`2fe216b59e1f62efb5a7376bcbb895d9d7ceebfe250a0d0cf2accf742f291d7f`.
The separate and combined approved previews remain local under
`rendered/level3-room24-review-v1/`.

The second adjustment treats the wall join at X345/346, to the right of the
lower column at X315/bottom363. Four more source-checked crops grade the
lighting between SHAP3551 and3513 and continue the column's outer shadow,
changing601 visible pixels. The central brown wall left of the columns was
not the reported target and stays unchanged. Both neighboring background
columns, all lit column bodies and all masks retain their native pixels.

The combined1154-pixel correction has cached RGB hash
`155016d0323e511fe037104e7edda38d6a9045cfcd70bc4ad3f7984dd206d567`.
Only the eight approved manifest sources are bundled; intermediate proposals
that recoloured background-column bases were excluded before visual review.

## Level3 room11: diagonal floor join

The user approved the marked-reference V3 on 2026-11-07. Two source-checked
background crops (SHAP3551 at X51/bottom125 and SHAP3525 at X53/bottom125)
change156 visible native pixels along the marked diagonal. The cached RGB
hash is `f3b222a29bdbec22895500caffde12090d18f10d1101095ca1e41f7d25c05051`.

V1's small lighting offsets left the cut visible. V2 spread reflected floor
texture too far into the wall end, washing out relief while leaving dark
pixels on the other side of the seam. Both were rejected. V3 starts from
the current artwork and bridges nearby native colours on both sides of the
actual contour: two native pixels towards the wall and three towards the
floor, grading the ends and retaining the native palette. Wall detail beyond
that narrow band, foreground columns, alpha, masks and earlier edits stay
unchanged. This is a baked artwork improvement, without per-frame filtering.

The approved comparison remains local under
`rendered/floor-join-marked-reference-v3/`. Approval covers this room only;
the remaining selected floor joins still require their own visual previews.

## Remaining selected floor joins: approved V3

The user approved these V3 floor joins on 2026-11-07, excluding level5
room9/J21 because its button artwork needs a separate correction. They use
the narrow two-sided transition approved for level3 room11. Earlier edits,
foreground pixels, source alpha and physical masks remain unchanged.
Comparisons stay local under `rendered/floor-join-selected-v3/`.

| Level | Room | Added pixels | Cached RGB SHA256 |
| --- | --- | --- | --- |
| 3 | 12 | 169 | `9152e74b8fdb313e8d91c09d631c695bbe6e47b93c64c6695041a87df2ac6519` |
| 3 | 15 | 155 | `1eac3788306c661ce31fee4fa3c51e458189f2d1f85d16465dad67312551d430` |
| 3 | 21 | 156 | `7ed2ab1071684891b8a2fab70a1bbefeee8327f39e2509ea64886ce9b2403912` |
