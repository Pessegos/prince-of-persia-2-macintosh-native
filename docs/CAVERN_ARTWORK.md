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

The user approved how it looks on 2026-11-07, after eleven passes, in level 4 room
16 (Room 17 in the development menu). It now runs in all 84 rooms of levels 3 to 5
(`AMBIENCE_LEVELS`), and that wider run is under the user's review. The tips and
the air are read from the art, so a new room has to be seen in motion.

Two rules keep it from looking like a modern filter. Every pixel it leaves on
the frame is a colour of the room's own palette, and everything moves once per
game tick. The second rule was learned the hard way: a pass at 36 Hz made the
drops and the dust glide, and they stood out against a game running at 12. If
the whole game ever runs faster, the ambience can follow it.

What the user has reviewed and how each part ended up:

- **Drops** hang from the stalactite tips (`stalactite_tips`, read from the
  art), keep each source's rhythm and end in a splash on the floor or a hiss in
  the lava. Crisp and opaque. In the light the front of a drop shows the fire it
  is falling past (`caught`): pale warm by a flame, orange close over the lava, and
  blue again once it is out of the light. The rest of its tail stays water.
- **Ash** is single crisp pixels. They rise from the lava's surface, and from
  the flame. A pass with sparks in bursts, with trails, was rejected: "a little
  more presence" meant a small step in the style that was there.
- **Firelight** replaced a blurred ball of the flame's shape. The user asked for
  light that behaves like ray tracing. The room is only a painting, so
  `rock_height` reads its shape from the paint: lit paint stands forward and dark
  paint falls back. `trace_firelight` cuts the flame into cells and runs rays from
  each cell over the relief. A surface takes light by how much it faces the cell,
  how far away it is, and whether rock stands in between. So the rock lights up
  along its veins and hollows stay dark. A light laid over everything "looked like
  a bomb about to go off".
- **The oval** was the hardest part, and took three tries to see. The user kept
  describing one steady oval around the torch. It was not the falloff of the light:
  drawn alone, the light was a bright plate with a sharp edge, in the shape of the
  torch's sprite, because the sunken recess and a flame close to the rock shut the
  light in. Following the frames could only make that plate tremble, and tracing
  the flame in five places and swinging it on a spring only made it "the same oval,
  changing place". Now the flame stands further off the rock, so the light gets
  out of the recess, and the recess takes half the light (`RECESS_LIGHT`) with a
  soft edge, as it is painted as already lit.
- **Keeping it in.** With the plate gone the light ran out over the back wall,
  and the user found that it "does not make sense": a flame in a niche lights the
  niche and a little of the rock around it. Two passes pulled it in. It now reaches
  about 7 pixels past the recess, and the shape it takes moves that edge by a few
  pixels more.
- **The candle.** The light is traced once, in about 20 ms on entering the room,
  and then changes shape instead of moving. Each frame of flame is measured all the
  way round its middle (`flame_outlines`), and where it burns further than usual
  the light reaches further that way (`Firelight.at`), so a tall flame draws the
  light up and a squat one spreads it to the sides. Raising the light to a power
  does that: the bright rock stays, the fringe goes out or comes in, and the veins
  stay where they are, which sliding the light could not do. The frames come in
  random order, so `Flicker` follows them at two speeds, quickly for the licks and
  slowly for the breath. How hot the frame burns moves the whole light as well.
  A tick only does that sum, in about a millisecond.
- **Keeping it calm.** A pixel keeps its step of light until the light has really
  moved past it (`LIGHT_HOLD`): before that, a third of the changing pixels
  flipped straight back. About 8% do now. More pixels change than in the original,
  but they are the light moving across the rock, not noise.
- **The Prince's feet.** `Footing` is read from the game once a tick and never
  written back. FRAM's supporting foot stays put and then jumps to where the next
  foot lands (`floor_contact_x`), so that jump is a step: it raises a tuft of the same
  dust as the doors, a few small lobes just behind the heel and level with his shoes.
  That foot is the game's and not what is drawn, and in each stride of the run it is
  wrong twice. On frame 8 it has gone to a foot still in the air, which comes down 18
  pixels further on, on frame 9, and frame 12 is not marked as on the ground although a
  foot lands there. Left alone, one foot raised dust twice, once where no foot ever
  stood, and the other none, which looked out of place and out of time. The
  foot-on-the-floor flag cannot do this alone, as it is set on almost every frame of a
  run. Walking carefully raises none. A landing raises a few lobes to each side, more the
  faster he came down, and there is none on the
  lava. As he runs he drags the air along (`wake`), so grains he passes follow him
  and let go. Dust from the floor is drawn behind him like the rest of the ambience.
- **Gates, doors and fallen tiles.** Whatever comes down knocks up a puff of dust
  (`Cloud`): a few flat round lobes that go out low to both sides of its foot, hug the
  floor, swell as they slow and thin away. Each lobe keeps its own outline, as a pixel takes
  the thickest lobe over it and not their sum, and its top is thicker than its foot, so
  it has a lit top and a dull underside. It is painted over the rock in three hard
  shades of warm rock (`CLOUD_SHADES`), each pixel landing on the palette, and each pixel
  has its own grain, which crumbles the edges and lets the puff go by breaking up. The
  rock shows through, and the dust is always a little paler than what is behind it
  (`CLOUD_PALER`), or a lit floor swallows it. This took six tries, and is the middle
  ground the user asked for. Soft spots read as balls of cotton wool, a smooth dithered
  veil was far too realistic for the game, loose pixels alone were too little, an ordered
  dither made a grid of dots, a spray of pale palette pixels was only grey dots, and
  lobes added together, or solid, were a flat stain on the floor. It keeps close to
  what came down: at sixty pixels and more it was too long. Dust cannot pass through a
  slab, which stands slanted, so the puff starts lower on its near side than on its
  far side. An exit door faces the room, so two lobes in three come out at its front,
  fanning out, and the rest go to the sides. There is none on the lava. The game tells
  this in `PressurePlates.shut` and `LooseFloors.landed`, which are not game state and
  are left out of saves. The entry door that slams behind him at the start of a level
  does the same.
- **Gates stop the torch's light.** The light is traced on the room with its gates up,
  whatever they are doing when the Prince comes in. Traced on a shut gate, the light
  stopped at its front part, went on over the rest of it, and left a hole where the gate
  had been once it rose. A slab stands across the room with its near end on the left and
  its far end at the back wall, and shows its right-hand face. So the wall it comes down
  over is on the torch's side of it: the slab only hides that wall, which keeps all of
  its light however the gate moves. A first try cast the slab's shadow ray by ray, and a
  shadow came down that wall with the gate: the user saw that the wall is on the torch's
  side. What takes none is the slab itself, seen with its
  back to the flame, and the air in front of it (`GateView`). Those pixels are read by
  comparing the room as it stands with the room with its gates up, each time it is
  redrawn. A torch reaches 54 pixels, so of the 15 rooms with a gate and a torch this
  only shows in room 11 of level 4, where the torch stands nine pixels from the gate. A
  torch to the right of a gate lights its visible face, which is right.
- **Lava light** is traced over the rock with the same engine as the torch
  (`trace_lavalight`), a cell at a time along the pool, with the pool itself counted
  as a hollow, however bright it is painted. It is fainter than the torch's and more
  a warmth than a brightness: with more gain the pale floor by the pool became a
  plate. Rock rising in front of the pool takes none of it, and the floor before the
  pool does, or the light stops dead where the foreground starts. It uses a table of
  its own and the same dither, and breathes over several seconds. Before this it
  was an even oval around the pool, which the user approved as a start.
- **Heat haze** bends what is seen through the hot air over the lava and over a
  flame (`Haze`, `shimmer`), in waves that rise. It thins out as it rises and to the
  sides. All the air bends, by less than a pixel: each pixel leans part of the way
  towards its neighbour and lands on the nearest palette colour (`Colours.settle`).
  Whole pixels sliding aside were far too much. Keeping them to the crest of each
  wave was no answer: the user wanted the effect itself subtler, not smaller. The
  ceiling and stalactites are foreground, in front of the air, so 27 of the 75
  torches sit under rock and show next to none of it.
- **The wall behind the torch.** `CaveGetTorchFrame` (8:3b4e) picks one of nine
  frames at random each tick. They paint a rich wall of veins and specks, but
  about a hundred loose pixels of it differ from frame to frame, so those blink.
  While the ambience is on `steady_wall` keeps each such pixel at the colour it
  shows most often, and a lesser light falls on that. Replacing the whole wall
  with the unlit recess (SHAP 3590) was tried and rejected: it came out plain, as
  it was only the loose pixels that were wrong. The unlit recess is what the
  relief is read from, as lit paint there would be taken for height. The flame
  stays exactly the game's: a pass that also chose the frames made it choppy.
  `flame_pixels` tells flame from wall by colour. Its dark red rim counts only
  next to the flame, as the same red is painted on the wall's cracks. Those
  cracks do not receive light, and rock does not turn into their red: lit, their
  thin lines broke into dashes and dots.
  `light_torch` only touches pixels that show the sprite, so whatever is drawn
  over the torch stays, and a torch that is not there gets no light either.
- **Dust** went through the most tries. Slow crisp grains hopped from pixel to
  pixel. Crisp grains fast enough to hide that looked in a hurry. Grains split
  among the four nearest pixels swelled and shrank on every pixel crossed: the
  brightest pixel fell from all of the grain to a quarter and back, and it
  looked like a worm going round a small square. `soft_spot` keeps one shape
  wherever the grain falls between pixels. Then the dust was hard to see away from
  the torch, and a pass with 64 pale grains of mixed sizes "looked like snowing".
  That had three causes, all fixed: there was a lot of it, each new grain went to
  the emptiest place so it was evenly spread, and half of it was falling.
- **Two kinds of dust** (`DustKind`). Fine grains, 21 of them, are one small opaque
  pixel. The brighter one is, the shorter it lasts (`lifespan`): most are dim, in the
  colour of the rock. The dimmest last 22.5 seconds and a typical grain 7.5, and now and
  then a pale one shines for a little over 2 seconds and is gone. Coarse grains, 5, are soft and partly transparent, the
  slowest, and the only ones that sink, and last 20 seconds. With 3 of them, fainter, they were lost
  beside the fine ones. A grain warms as it enters the light, a coarse one comes into
  focus there (`on_the_pixels`), and as a grain tumbles a face of it catches the
  fire for a moment. A glint is as strong as the light on the grain, so there are
  none in the dark, and two rhythms keep any grain from flashing like a beacon. How
  lit a grain is comes from the traced light, spread out a little (`lit_air`), so
  the air behind a ledge stays dark.
- **Where it gathers.** Each visit to the room picks four pockets of open air, far
  apart (`find_pockets`), and grains start around those or near the fire. That
  leaves patches of dust and clean air between them.
- **The air** moves the dust. One slow draught crosses the room and turns very
  slowly. Fire draws the air in beside it, sends it up through the flame and
  spreads it out above (`wind_at`). A grain has some weight, so it follows any
  change in the air slowly, and it sways a little. With rock ahead it slows and
  settles over 3 seconds instead of vanishing. Most coarse grains sink, starting
  not far above a floor. One that reaches it comes down on it (`land`), about five
  times in two minutes, and lies there as one pale speck for 7 to 14 seconds, fading.
  It does not land on the lava, or
  behind the foreground, and a floor that falls takes it along. Otherwise a grain
  has a lifespan:
  it comes up over the first seventh of it and goes over the last quarter, and
  never takes more than 1.7 seconds to come or 2.5 to go. Half-transparent grains
  that stayed that way were what the user found too long: coarse ones took four
  seconds to come and eight to go. A new one starts unseen,
  around a pocket or near the fire, with air ahead for its whole life (`new_mote`),
  so old and new never show as a swap. Over the lava it is duller, so that it is
  not read as more ash.

The firelight and the glow are tables of what each palette colour becomes at
each of ten brightness levels (`Colours.light_table`), stepped through a 4x4
ordered dither like the stipple in the art. Firelight multiplies what the paint
already is, so hollows stay dark. Flame, lava and the painted cracks do not
receive light, and lit rock never turns into one of their colours.

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

Running it in every room showed what one room could not:

- **Rock in front of a torch.** Light fell on whatever the frame showed, so the
  pillars and walls standing in front of a torch turned into pale plates, worst in
  level 4 rooms 11 and 15 and level 5 room 6. That rock has its back to the flame, so
  the foreground takes no light now, and the air before it stays lit for the dust.
  In the approved room that took 240 of 4,464 lit pixels, all of them very faint.
- **Torches behind pillars.** Most stand a little behind one. A torch counts when
  35% of it shows (`TORCH_SEEN`), which brought back six that were half hidden and had
  no light. Three are shut behind rock (level 4 room 2, level 5 rooms 6 and 11): they
  are no fire at all, with no ash and no dust gathering around them.
- **Torches listed twice.** The level data lists each torch twice in 40 rooms, for
  ash and air worked out twice over. `room_torches` keeps one.
- **Lava off the screen.** Three rooms list a pool above their top edge (level 3
  rooms 13 and 28, level 4 room 24), and drops over it had a surface above their own
  tip. `lava_surfaces` leaves such a pool out.
- **Drops that cannot be seen.** 26 sources fell wholly behind the foreground and
  held a place a visible one could use. `choose_drips` skips those.
- **Rooms without fire.** They have `QUIET_DUST`: half the grains, none of them
  bright and the coarse ones fainter, as nothing there lights it. They had no dust at
  first, and the user found that a loss.

Extras built on 2026-11-07 for the user to try, not reviewed yet: drops catching
the light, heat haze, the lava's traced light and the Prince's feet. Two ideas wait.
The Prince's shadow on the rock would have to work on every level, not only the
caverns, so it comes near the end. Sound tied to all of it needs more calm.

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
