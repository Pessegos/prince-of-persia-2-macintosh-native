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

## Cave ambience

An optional port effect, not a recovered behavior: the original has no dust,
ash, water drops or cast light, and its torch does not behave like this.
`pop2/cavern_ambience.py` draws them while the F1 item Cave ambience (Alt+A) is
on, and `pop2/firelight.py` works out the light. It is off by default, and the
choice is kept between sessions in `preferences.json` (`pop2/preferences.py`).

It is a prototype under the user's review. It runs in one room,
`AMBIENCE_ROOMS` = level 4 room 16 (Room 17 in the development menu). Adding a
room means reviewing it in motion: the tips and the air are read from the art,
and only this room has been looked at.

Two rules keep it from looking like a modern filter. Every pixel it leaves on
the frame is a colour of the room's own palette, and everything moves once per
game tick. The second rule was learned the hard way: a pass at 36 Hz made the
drops and the dust glide, and they stood out against a game running at 12. If
the whole game ever runs faster, the ambience can follow it.

What the user has reviewed and how each part ended up:

- **Drops** hang from the stalactite tips (`stalactite_tips`, read from the
  art), keep each source's rhythm and end in a splash on the floor or a hiss in
  the lava. Crisp and opaque.
- **Ash** is single crisp pixels. They rise from the lava's surface, and from
  the flame. A pass with sparks in bursts, with trails, was rejected: "a little
  more presence" meant a small step in the style that was there.
- **Firelight** replaced a blurred ball of the flame's shape. The user asked for
  light that behaves like ray tracing. The room is only a painting, so
  `rock_height` reads its shape from the paint: lit paint stands forward, dark
  paint falls back, and the torch's recess is its sprite's outline sunk into
  that surface. `trace_firelight` cuts the flame into cells and runs rays from
  each cell over the relief. A surface takes light by how much it faces the
  cell, how far away it is, and whether rock stands in between. So the rock
  lights up along its veins, the lip above the recess catches the light from
  below, and hollows stay dark. The relief has to stay shallow against the
  flame: deeper, and the rim of the recess shuts the light in, one steady oval
  however the flame moves. A light laid over everything "looked like a bomb
  about to go off".
- **The candle.** The first traced light had one map for each of the nine frames,
  and it read as a steady oval. The frames come in random order and their
  middles are a pixel or two apart, so following them only made the light tremble
  in place, and the rock by the flame sat at full light with nothing left to move.
  Now the flame is traced five times, at rest and moved 14 pixels each way, and a
  tick mixes those (`Firelight.at`), so the light can stand anywhere among them.
  Each frame pushes on a damped spring (`Flicker.sway`), which turns the random
  frames into a swing of about a second, as if a draught had caught the flame,
  and the shadows swing with it. How hot the frame burns makes the quick flicker
  on top. The trace takes about 180 ms on entering the room, only with the
  ambience on, and a tick only mixes.
- **Keeping it calm.** A pixel keeps its step of light until the light has really
  moved past it (`LIGHT_HOLD`): before that, a third of the changing pixels
  flipped straight back. With the swing only about 5% do. More pixels change than
  in the original, but they are the light moving across the rock, not noise.
- **Lava glow** is fainter than that warmth and hugs the pool (`glow_along`). It
  is the same table and dither, and breathes over several seconds.
- **The wall behind the torch.** `CaveGetTorchFrame` (8:3b4e) picks one of nine
  frames at random each tick. They paint a rich wall of veins and specks, but
  about a hundred loose pixels of it differ from frame to frame, so those blink.
  While the ambience is on `steady_wall` keeps each such pixel at the colour it
  shows most often, and the light above falls on that. Replacing the whole wall
  with the unlit recess (SHAP 3590) was tried and rejected: it came out plain, as
  it was only the loose pixels that were wrong. The unlit recess is what the
  relief is read from, as lit paint there would be taken for height. The flame
  stays exactly the game's: a pass that also chose the frames made it choppy.
  `flame_pixels` tells flame from wall by colour. Its dark red rim counts only
  next to the flame, as the same red is painted on the wall's cracks.
  `light_torch` only touches pixels that show the sprite, so whatever is drawn
  over the torch stays, and a torch that is not there gets no light either.
- **Dust** went through the most tries. Slow crisp grains hopped from pixel to
  pixel. Crisp grains fast enough to hide that looked in a hurry. Grains split
  among the four nearest pixels swelled and shrank on every pixel crossed: the
  brightest pixel fell from all of the grain to a quarter and back, and it
  looked like a worm going round a small square. `soft_spot` keeps one small
  soft shape wherever the grain falls between pixels. The user then asked for a
  realistic mix of the three variants they had seen: a soft grain, one pixel
  sliding, and still glints. Real dust is only seen where light catches it, so
  the light decides which of the three a grain is. In the dark it is a faint soft
  spot. In the light it comes into focus (`on_the_pixels`): one sharp pixel that
  waits and slides into the next, and as it tumbles a face of it catches the fire
  for a moment. A glint is as strong as the light on the grain, so there are none
  in the dark, and two rhythms keep any grain from flashing like a beacon. How lit
  a grain is comes from the traced light, spread out a little (`lit_air`), so the
  air behind a ledge stays dark. The dark spot started so faint that only someone
  who knew where to look could find it, so it is paler and there are 46 grains.
- **The air** moves the dust. One slow draught crosses the room and turns very
  slowly. Fire draws the air in beside it, sends it up through the flame and
  spreads it out above (`wind_at`). A grain has some weight, so it follows any
  change in the air slowly, and it sways a little. With rock ahead it slows and
  settles over 3 seconds instead of vanishing. A third of the grains are heavier
  and sink. One that reaches a floor comes down on it (`land`), and lies there as
  one pale speck for 7 to 14 seconds, fading. It does not land on the lava, or
  behind the foreground, and a floor that falls takes it along. Otherwise a grain
  has a lifespan:
  it comes up over 4 seconds and goes over 7. A new one starts unseen, in the
  emptiest of five places with air ahead for its whole life (`new_mote`), so the
  amount in the room stays the same and old and new never show as a swap. Over
  the lava it is duller, so that it is not read as more ash.

The firelight and the glow are tables of what each palette colour becomes at
each of ten brightness levels (`Colours.light_table`), stepped through a 4x4
ordered dither like the stipple in the art. Firelight multiplies what the paint
already is, so hollows stay dark. Flame and lava do not receive light, and lit
rock never turns into a colour of fire.

Pixels only. Its generator is private, so turning it on changes no opponent,
route or test. Its state is on the `LevelRenderer`, not in `CavernState`, so it
never reaches a save. `RealSceneTests` plays the same keys with the toggle off
and on and compares the game state and the random generators.

It is drawn right after `remember_scenery` and not in `animated_layer`, where
the first idea had put it. DoCleanCut (2:608c) keeps the previous room's scenery
in the next room's unpainted pixels, so a particle or lit pixel drawn before
that snapshot could stay on screen for good. Being before the actors, it passes
behind them and does not light them. The foreground's alpha hides particles
behind pillars and rock.
