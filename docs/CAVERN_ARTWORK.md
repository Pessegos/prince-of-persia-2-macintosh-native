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
| 3 | 26 | 156 | `64d955ab1a78694f3c1efee0b910f573f9dbdaef0695c167a7f42be941d4a67a` |
| 3 | 32 | 155 | `d23f55b7b625e87f2698dd5e8bd3399479c5293371cb9591b7b1987603f94e2f` |
| 4 | 13 | 312 | `e08b3742a5b27f099f9b01e4f253e7b2ff7f58a6cc93bb5ed35cf0007db0e97a` |
| 4 | 14 | 46 | `1b624888aa2e8417c4305244956567b77668b8d3c59931e0b7451d7a7eda2b7b` |
| 4 | 18 | 156 | `91ca82a8add9bbf792fae9d09f297a189c91849cdd4f4580edcc9faebfbaad65` |
| 5 | 11 | 201 | `bb1b2208c8f31a0be54d692a8fdd1d9bdf2c4d4ee04a951145ec138b1fae55c6` |
| 5 | 13 | 156 | `a97267870d5c5ca70e25822525085021a3200b9abdd9bd38ba53ebffd8214f4e` |
| 5 | 19 | 91 | `72de66968e0cb63ddf9e982da4c589e7e4926b331fc8c67c8d1d5cfee0238107` |

## Level5 room9/J21: preserve the pressure plate

The user approved the corrected V4 on 2026-11-07. The earlier two-sided V3
also changed101 pixels of SHAP3554, softening the button drawing, and was
rejected for this location. V4 changes only64 visible pixels in the wall-side
SHAP3551 at X102/bottom365, fading its narrow edge towards the existing floor.
Both pressure-plate sources, SHAP3554 and3555, remain completely native.

The cached RGB hash is
`c38b6f0dc49853d652be724aa228f18c3bb603b959650be594a91443796f5ee9`.
The approved comparison remains local under `rendered/floor-join-j21-button-v4/`.
Tests preserve every button pixel with the plate released and pressed, along
with all source alpha, foreground pixels and physical masks. Earlier approved
artwork stays unchanged. This completes the user's selected floor-join batch;
it does not certify that every cavern junction has been visually reviewed.

## Level3 room16: right tips beneath the column and shooting trap

The user approved the two right-tip reference proposals on 2026-11-07.
Both use SHAP3526, at X53 and X308/bottom245. They are separate from the
earlier left wall/floor joins. A narrow three-pixel band on the actual right
contour grades nearby native texture towards the existing neighboring floor,
retaining the native palette and pixel grid. The neighboring pieces remain
untouched, including the pressure-plate drawings in both states.

The two placement-specific crops change109 and111 visible pixels,220 in total.
The approved cached RGB hash is
`a5f823e2a653cfc956104a2483f8f1dc69fb94758ffee8135c12544e8cc25a38`.
Foreground pixels, column sources, source alpha, physical masks and earlier
approved artwork are preserved. The comparisons stay local under
`rendered/floor-right-edge-references-v1/`. This approval covers those two
examples only; other visible right tips require their own local previews.

## Remaining right floor tips: approved batch

The user approved all remaining96 visible right-tip proposals on 2026-11-07.
These room/placement-specific SHAP3526 crops use the reviewed room16 method
and preserve adjacent tiles, earlier retouches, native alpha and physical
masks. Local comparisons are under `rendered/floor-right-edge-remaining-v1/`.
Older wall/left-join goldens isolate this new layer using the exact approved
pixel masks, asserting the complete previous sprite hash after restoration.
Separate unmasked production-frame and source goldens cover the combined
artwork; no original golden or mask assertion is discarded.

| Level | Room | Added visible pixels | Combined cached RGB SHA256 |
| --- | --- | --- | --- |
| 3 | 2 | 128 | `42b5d9e0b5da04adb31e3c03d5d4d46363f73aa6e52e37f2a49f312dadb581fe` |
| 3 | 3 | 208 | `7c73c6a5ee731d4c34ef791eec54899003c2a57d9ae48f6bbf1dc3b5e149a7bf` |
| 3 | 4 | 220 | `e32ea54cf8d14f6adc3f7fea096aba6545760270b33b9cb3413a9ba2896a6acb` |
| 3 | 5 | 322 | `1b6b395bb6f397d44e5af41698c37698620c9cf31cea1aebed8db427795ab25a` |
| 3 | 6 | 108 | `104166ade6f8da682c7c3e366d5ba893dd1a8d5c3d4709f62ae39a129f7a0ab3` |
| 3 | 7 | 109 | `96faa88ac29fc1d55cc21e0f76bc088f99b8e1c2674a56385bd7472923ca52ff` |
| 3 | 8 | 168 | `ec6ca6490d876860047a25a0c01b9d6890dec30e1108533d262449f76faf34d8` |
| 3 | 9 | 65 | `c1a8a3cd8301ea6f74465ebaf5c77ce5cbae69a1b1e805e003b8a730d108fa7e` |
| 3 | 10 | 104 | `d6b101bb9a011a9f052e10cc4e8af62fe065793d0176af93fef0f009f489e9fb` |
| 3 | 11 | 110 | `79bc6828584c6ae4015d8901a929ab888e50b07ae9b7cc5161660a17fac82649` |
| 3 | 13 | 111 | `152dcada185e76138ceb1f808e9473966945ef6aeb1f0e3b9e6ea85a3b0d5844` |
| 3 | 14 | 109 | `e48e60b11ca2f01fcf7c2d5c369ed41415a653082cb427f2fa46b4700d8ef231` |
| 3 | 15 | 104 | `0e8af1a4f411a0837b5e735e3b68b81c088a27307dbcfb8be6b4a7d2fad3ef09` |
| 3 | 16 | 157 | `5526d1a75d78cba20723a63268615c941f0db242668e357478aab3e318cf7bb3` |
| 3 | 17 | 23 | `3dc2bcfb49ce67ff6967295a893dbd514247381744fc31f0138983688369ac20` |
| 3 | 19 | 109 | `736e6104482c5ee80b6deaf1563c0db7a30108fca4e3c04b5ed07c841aaec897` |
| 3 | 21 | 278 | `1a34f2f43244219c45e95444001cee7651c550109ff6ef847fc3a047fc1f2c71` |
| 3 | 22 | 427 | `19dd1e475e8192d541fde2d1d5d5b955282df477d93fc03f0b1fd723d422723a` |
| 3 | 25 | 91 | `674f430be840f72ab83b09f6487bae1b9ec585c1be794ae444d50417bc2540bd` |
| 3 | 26 | 109 | `6e04f9bfed10d215b626f11d3aea3c12ce3240be927e115e502efaf8038dfcf7` |
| 3 | 27 | 213 | `cc454eeb6151398ffa7a3dcabd742b0b554662261943b4f5e0516113bcdc857d` |
| 3 | 28 | 368 | `ec1b9f968335ea732aed7c30410a27260fcf6f069ebc9d4417afe0feac149169` |
| 3 | 30 | 109 | `0b9559d1cee7964b990599c5ad99af2576edfb21d56a03d5baae6526717697ea` |
| 3 | 31 | 69 | `a50b85c8f31b437b0b6a0c4459448f813cb46b8f79c41c97e2c1a30acdb6d766` |
| 4 | 1 | 155 | `7653744bceee45c1050c050a65c13a4f0fba6c66e9c6f9d72d25996d9e5c0b34` |
| 4 | 2 | 109 | `0de2c6cb86412b4b3ec614196fb05d858f07616877be42fe0d2777fadced9259` |
| 4 | 3 | 104 | `625759102b8c38d27999ce053979c8946ea768446c2efe63a8e24c2a80732cd8` |
| 4 | 7 | 317 | `cb64abe4532f4e143f9166016b91407848375648ea8d01edad29e5ad8fb58747` |
| 4 | 9 | 173 | `207f604acf2b2b33985b23889d690e6603e0560aca3d936050e37b0d2327b285` |
| 4 | 10 | 42 | `a9ffd0824b7b578e5b073ae0ae3f2de543540fd565cf6a76ab5ce3b0930f9075` |
| 4 | 12 | 111 | `d4a4c4778f2df40e15eeb24673d7f8e6bd141a2df016ca3d7ffdd76d38489efd` |
| 4 | 13 | 46 | `4fd093b2f15ed129e0c1d3951575e5bd208c6b547c99a47fae71d63afcafd8aa` |
| 4 | 15 | 234 | `93dcbef35c29d23ad737c8eaf49c5ac3317d673a3822a3c2f83d36206c30eefd` |
| 4 | 16 | 221 | `7be15f169f5d0262dd3ffc7eea23697b946f9733336facccddb8604bc5087956` |
| 4 | 17 | 176 | `a14a0e91705ed88ecb7f03ba13ffc020e3836f0659c3e2c685ff05aa2a34ac12` |
| 4 | 18 | 65 | `5850b83c46878845b118eaddda06d64fa0c47217993c8c33375178f993693dd4` |
| 4 | 25 | 85 | `f72820430652cace4f24467dd2db131717085fcd82c93422c47161334c336e9c` |
| 4 | 26 | 193 | `e553f6d062a187e9223ee6bc06afa66ea77cb1954fb12bb39363c6ad2830ac4a` |
| 4 | 27 | 218 | `2ddf9c81e6b04da5485e6f1cb930f1ff44ee600d86b521cabe1a3d0066901a45` |
| 4 | 28 | 213 | `badcf936da6514fbf38f0a63ccd30cb7d1eed4421c8c521b4f54c73412f5d172` |
| 5 | 1 | 324 | `191e417cbd09ff1c7a037d5d7f44560bcc670c7120ff6bbe00bb14020d10a4a4` |
| 5 | 2 | 176 | `111ebee78aae508212a53e93ee670505c751c36bd7fd4eab71d40b25e65d002b` |
| 5 | 4 | 218 | `00b7c782f585999d1a03bb5cad228b659d60a4d4ffd0c9a45590ce489be1aded` |
| 5 | 6 | 109 | `576df474f422ad918c26db18655b3f7ff70f9099ab30b7ef93f4ec34f1f7bdc1` |
| 5 | 7 | 326 | `40a77bce53a300c5b35a2c8572d4379932abbe8be68fb0c69f2121af86e59555` |
| 5 | 9 | 343 | `54977d24c3fe7a8a8f79b0343aae4b19f46773a8b6455fc5043ad48d51e73ab7` |
| 5 | 14 | 23 | `0f1b35c7e0e129ad6d89c9aa92c0f5f30be81c58c09515eb0f98992ef1034b67` |
| 5 | 15 | 24 | `8ba3d36673477ab5720b65e9980d505251c9efd176683fdef6a1d5df4610f8d0` |
| 5 | 16 | 105 | `21a38898ddec1ff513a18df8cd9025c032e095831691993d11fbb28f75ca0ac1` |
| 5 | 18 | 46 | `fc4fdb0430c3c932dae6353ff6bc3e55d376bfa8932e4d6adcd15eb534eb5e62` |
| 5 | 19 | 29 | `8f544d03d58a67e01522a846926c1c05a98742d96d7f629b7d0bccc218c06736` |
| 5 | 22 | 389 | `33350f724b846ffd82ea16f67eec6f374dfece5fe22ad8e78f4b3469413cc7cd` |
| 5 | 23 | 109 | `7185c7d6facf339702351f69a39117c9a8722e91cca6fe99e941547aebba104a` |

## Additional diagonal floor joins: approved local batch

The user approved the level3 room30 reference and39 additional diagonal-floor
comparisons on2026-11-08 for local application, without GitHub publication.
These placement- and source-hash-checked atlas crops preserve prior artwork,
native alpha, foreground columns and physical masks. Normal floors use the
reviewed narrow two-sided contour bridge; buttons and cut floor drawings
remain intact, with the adjustment confined to the wall side.

Earlier artwork goldens retain their original expected hashes by excluding
only this batch's explicitly reviewed, previously-native pixel coordinates.
The complete restored sprite must equal its previous RGBA hash. Independent
unmasked production-frame/source goldens test the full combined artwork;
button and cut-floor source variants retain their earlier full-image hashes.
Local review artifacts remain under `rendered/floor-join-selected-39-v1/` and
the separate `rendered/level3-room30-joins-v1/` reference.

| Level | Room | Added visible pixels | Combined cached RGB SHA256 |
| --- | --- | --- | --- |
| 3 | 30 | 67 | `aa0f165cab0af65f2e1e89bd4206678f6b79b282454522101fcd06022a0a2efb` |
| 3 | 4 | 163 | `ee6fd6d07eb4a6f43499d88f9cede46a17b1368fe6ee114fc68f7afab9e0d3c9` |
| 3 | 7 | 169 | `276d2c327c3716b60a5e5e631579af55e926cfce7c9fc02f382ce7f022d5c94a` |
| 3 | 9 | 162 | `0a7795108d68848a1d574ec1492bbce0f95f59a06403a79b6683506be67bcc7d` |
| 3 | 10 | 66 | `ad541f97e771d8f5e707924bc5ba52f44f351c8ff5d678cde43aea9995dfb360` |
| 3 | 12 | 149 | `bc6e705196c934f1c68109cd0e06c5263e33b5fcda8ac20ccf673c3f80e24133` |
| 3 | 13 | 67 | `30a42b8928ea617e81cb79c0886838825b574e208b2c2667c22e16dc08bc6c74` |
