"""The desert's gameplay wind over the horse movie's three desert shots."""

from itertools import chain
import random

import numpy

from pop2.ruins_ambience import (
    DESERT_COLOURS, HEIGHT, WIDTH, DesertWind, Dunes, chasm_crosswind_pixels, chasm_dunes,
    chasm_fall_pixels, chasm_rising_sand_pixels, chasm_updraft_pixels, gentler_colour,
    nearest_colours, paler, palette_rgb, sand_mask,
)


HORSE_STATUE_BACKDROP = 404250
HORSE_GALLOP_BACKDROP = 625385
HORSE_GORGE_BACKDROP = 404264
GORGE_Y = 10
GALLOP_DUNE = 625393
GALLOP_GROUND = 625397
GALLOP_DUNE_Y = 242
GALLOP_CREST = 245
GALLOP_PLAIN = 263
# ANI25012's repeating near-dune layer, unwrapped at the tile seam.
GALLOP_DUNE_SCROLL = (0, 122, 244, 371, 497)
GALLOP_FRAME_TICKS = 6
GALLOP_WHIRL_PASS_FRAME = 40
# Match the level's west-to-east wind through the gorge, dunes and statue.
DESERT_SHOTS = (HORSE_GORGE_BACKDROP, HORSE_GALLOP_BACKDROP, HORSE_STATUE_BACKDROP)


def gallop_scroll(frame):
    """Distance travelled by the near dunes since the first gallop frame."""
    cycle, phase = divmod(frame, len(GALLOP_DUNE_SCROLL) - 1)
    index = int(phase)
    left, right = GALLOP_DUNE_SCROLL[index:index + 2]
    return cycle * GALLOP_DUNE_SCROLL[-1] + left + (phase - index) * (right - left)


class GallopSand:
    """Wind over the dunes that the camera tracks past during the gallop."""

    def __init__(self, dunes):
        # Give the wind a longer repeat than the near dune's four-frame texture cycle.
        self.wind = DesertWind(Dunes.join((dunes,) * 4), random.Random(22))
        self.wind.prime()
        self.frames = []

    def in_view(self, tick, travel, whirl):
        while len(self.frames) <= tick:
            breeze = chain.from_iterable(self.wind.breeze_pixels(origin) for origin in range(0, self.wind.width, WIDTH))
            self.frames.append((tuple(breeze), tuple(self.wind.gust_pixels())))
            self.wind.advance()
        breeze, gusts = self.frames[tick]
        for x, y, shade in breeze:
            yield (x + travel) % self.wind.width, y, shade
        # The funnel occupies one position along the route and exits to the right.
        whirl_travel = travel - gallop_scroll(GALLOP_WHIRL_PASS_FRAME)
        for x, y, shade in whirl:
            yield x + whirl_travel, y, shade
        for x, y, shade in gusts:
            yield (x + travel) % self.wind.width, y, shade


class SandPalette:
    """Choose the game's blends in the shot's palette, then draw with its live inks."""

    def __init__(self, palette):
        self.palette = palette
        self.colours = palette_rgb(palette)
        self.indices = {rgb: index for index, rgb in palette.items()}
        self.sand = nearest_colours(palette, DESERT_COLOURS)
        self.grains = {}
        self.wisps = {}

    def grain_ink(self, index, shade):
        key = index, shade
        if key not in self.grains:
            behind = self.palette[index]
            drawn = self.sand[shade][:3]
            colour = gentler_colour(behind, drawn, self.colours) if behind != drawn else behind
            self.grains[key] = self.indices[colour] if colour != behind else index
        return self.grains[key]

    def wisp_ink(self, index, amount):
        key = index, amount
        if key not in self.wisps:
            behind = self.palette[index]
            colour = paler(behind, amount, self.colours)
            self.wisps[key] = self.indices[colour] if colour != behind else index
        return self.wisps[key]


class HorseDesert:
    def __init__(self, shapes, palettes, sky_palettes, statue_dunes):
        gorge_palette = palettes[sky_palettes[HORSE_GORGE_BACKDROP]]
        gorge = numpy.asarray(shapes[HORSE_GORGE_BACKDROP])[:HEIGHT - GORGE_Y, :WIDTH]
        rgb = numpy.array([gorge_palette.get(i, (0, 0, 0)) for i in range(256)], dtype=numpy.uint8)[gorge]
        self.gorge = chasm_dunes(numpy.pad(sand_mask(rgb), ((GORGE_Y, 0), (0, 0))))

        # The travelling sand follows the height of the animated crest at draw time.
        dune = numpy.asarray(shapes[GALLOP_DUNE])
        self.gallop_crest = GALLOP_DUNE_Y + (dune != 0).argmax(axis=0)
        ground = numpy.broadcast_to(numpy.arange(HEIGHT)[:, None] >= GALLOP_CREST, (HEIGHT, WIDTH))
        gallop = Dunes(numpy.full(WIDTH, GALLOP_CREST), numpy.full(WIDTH, GALLOP_PLAIN), ground, ground, ())
        self.gallop = GallopSand(gallop)
        self.wind = DesertWind(Dunes.join((self.gorge, gallop, statue_dunes)), random.Random(21))
        self.wind.prime()
        self.first_tick = self.wind.tick
        self.frames = []
        # The gorge and statue share an indexed palette.
        inks = {palette_id: SandPalette(palettes[palette_id])
                for palette_id in {sky_palettes[shot] for shot in DESERT_SHOTS}}
        self.inks = {shot: inks[sky_palettes[shot]] for shot in DESERT_SHOTS}

    def sand_at(self, backdrop, tick):
        """Cache the same deterministic wind for live play, seeks and replays."""
        while len(self.frames) <= tick:
            frames = {}
            for section, shot in enumerate(DESERT_SHOTS):
                origin = section * WIDTH
                pixels = self.wind.devil_pixels(origin) if shot == HORSE_GALLOP_BACKDROP else self.wind.desert_pixels(origin)
                frames[shot] = tuple((x - origin, y, shade) for x, y, shade in pixels
                                     if origin <= x < origin + WIDTH and 0 <= y < HEIGHT)
            self.frames.append(frames)
            self.wind.advance()
        return self.frames[tick][backdrop]

    def draw(self, frame, display, palette, backdrop, tick, *, scenery, covered, crest_x, gallop_motion):
        inks = self.inks[backdrop]
        sand = self.sand_at(backdrop, tick)
        wisps = ()
        if backdrop == HORSE_GORGE_BACKDROP:
            # Use the same bank falls and gully currents as the playable gorge.
            phase = tick + self.first_tick
            sand = chain(sand, chasm_fall_pixels(phase, self.gorge.sand), chasm_rising_sand_pixels(phase))
            wisps = chain(chasm_updraft_pixels(phase), chasm_crosswind_pixels(phase))
        elif backdrop == HORSE_GALLOP_BACKDROP:
            local_tick, travel = gallop_motion
            sand = self.gallop.in_view(local_tick, travel, sand)
            sand = self.follow_crest(sand, crest_x)

        display = display.load()
        scenery = scenery.load() if scenery is not None else None
        covered = covered.load() if covered is not None else None
        canvas = frame.load()

        def behind(x, y):
            if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
                return None
            if covered is not None and covered[x, y]:
                return None
            index = display[x, y]
            if scenery is not None and index != scenery[x, y]:
                return None
            return index if index in inks.palette else None

        pixels = {}
        for x, y, shade in sand:
            index = behind(x, y)
            if index is not None:
                pixels[x, y] = inks.grain_ink(index, shade)
        for x, y, amount in wisps:
            index = behind(x, y)
            if index is not None:
                pixels[x, y] = inks.wisp_ink(pixels.get((x, y), index), amount)
        for point, index in pixels.items():
            canvas[point] = (*palette[index], 255)

    def follow_crest(self, sand, crest_x):
        for x, y, shade in sand:
            if not 0 <= x < WIDTH:
                continue
            if y < GALLOP_PLAIN:
                height = self.gallop_crest[(x - crest_x) % len(self.gallop_crest)]
                # Keep the ground streams level as they move below the crest spray.
                share = min(1, (GALLOP_PLAIN - y) / 8)
                y += round((int(height) - GALLOP_CREST) * share)
            yield x, y, shade
