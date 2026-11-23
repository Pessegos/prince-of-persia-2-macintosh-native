"""The optional ambience of the ruins: what the user approved, kept as approved."""

from dataclasses import replace
import math
from pathlib import Path
import random
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy
from PIL import Image

from pop2.cavern_ambience import (
    GATE, LANDING_PUFF, MOST_LANDING_LOBES, SHUT_PUFF, SKID_PUFF, SLAM_PUFF, STEP_PUFF, TILE_PUFF, Footing, Thud,
    door_coming_down, tile_landing,
)
from pop2.paths import ASSET_DIR
from pop2 import ruins_ambience
from pop2.ruins_ambience import (
    BODY_PALER, BRIGHT, CURL_RADIUS, CURL_RISE, CURL_SPEED, DESERT_ROOMS, DESERT_STAR_APART, DESERT_STAR_CLEAR, DESERT_STARS,
    DIM, DIP_TICKS, FAINT, FIREBALL, FIRST_SHOOTER, GOLD_BRIGHT, GRAZER, GRIT_HEAD, HAZE_APART, HAZE_DIM,
    HAZE_MID, HEIGHT, MID, NORMAL, ROSE_BRIGHT, ROSE_MID, SECOND_STREAK_BELOW, SHOOTERS, STAR_APART, STAR_CLEAR, STARS_PER_SKY,
    STREAK_SPEED, TICKS_BETWEEN_SHOOTERS, WIDTH, DesertWind, Dunes, RuinsAmbience, Shooter,
    blueness, new_streak,
    paler, read_room, ribbon, shooter_path, shooter_pixels, sky_mask, streak_pixels,
)

RUINS_INSTALLED = (ASSET_DIR / 'ruins_level6.json').is_file()

DEEP = (16, 0, 120)
MIDDLE = (36, 0, 110)
PURPLE = (70, 0, 100)
STONE = (96, 92, 104)
SAND = (166, 120, 104)
WARM = (ROSE_MID, ROSE_BRIGHT, GOLD_BRIGHT)
HAZE = (HAZE_DIM, HAZE_MID)
PALETTE = {index: (*colour, 255)
           for index, colour in enumerate(sorted({DEEP, MIDDLE, PURPLE, STONE, SAND, *ruins_ambience.INK_COLOURS}))}


def picture(*bands):
    """An RGB room of horizontal bands (colour, rows), stone below them."""
    rgb = numpy.zeros((HEIGHT, WIDTH, 3), dtype=numpy.uint8)
    top = 0
    for colour, rows in bands:
        rgb[top:top + rows] = colour
        top += rows
    rgb[top:] = STONE
    return rgb


def frame_of(rgb):
    return Image.fromarray(rgb).convert('RGBA')


def night(number=6, room=11, *bands):
    return read_room(number, room, picture(*(bands or ((DEEP, 180), (PURPLE, 60)))), PALETTE)


class SkyTests(unittest.TestCase):
    def test_the_sky_is_the_night_blue_and_the_purple_by_the_horizon(self):
        rgb = picture((DEEP, 10), (MIDDLE, 10), (PURPLE, 10), (SAND, 10))
        self.assertEqual(sky_mask(rgb)[:, 0].tolist(), [True] * 30 + [False] * (HEIGHT - 30))
        self.assertEqual([round(float(value), 2) for value in blueness(rgb)[(0, 10, 20), 0]], [1.0, 0.5, 0.0])


class StarTests(unittest.TestCase):
    def test_stars_keep_to_clear_sky_and_apart(self):
        rgb = picture((DEEP, 120), (STONE, 20), (DEEP, 60))
        rgb[:, 200:230] = STONE
        sky = sky_mask(rgb)
        for room in range(8):
            stars = read_room(6, room, rgb, PALETTE).stars
            self.assertTrue(stars)
            for x, y, _kind in stars:
                self.assertTrue(sky[y - STAR_CLEAR:y + STAR_CLEAR + 1, x - STAR_CLEAR:x + STAR_CLEAR + 1].all())
            for one in stars:
                for other in stars:
                    if one is not other:
                        self.assertGreaterEqual(math.hypot(one[0] - other[0], one[1] - other[1]), STAR_APART)

    def test_more_where_the_sky_is_bluest_and_only_faint_ones_by_the_horizon(self):
        deep = middle = 0
        for room in range(16):
            for _x, y, kind in night(6, room, (DEEP, 90), (MIDDLE, 90), (PURPLE, 80)).stars:
                if kind in HAZE:
                    continue
                self.assertLess(y, 180)
                deep += y < 90
                middle += y >= 90
        self.assertGreater(deep, 2 * middle)
        self.assertGreater(middle, 0)

    def test_the_purple_has_a_few_faint_stars_apart_from_the_others(self):
        # The user, 2026-11-22: stars in the purple too, a little less visible.
        haze = 0
        for room in range(16):
            stars = night(6, room, (DEEP, 90), (PURPLE, 150)).stars
            faint = [star for star in stars if star[2] in HAZE]
            haze += len(faint)
            for x, y, kind in faint:
                self.assertGreaterEqual(y, 90)
                for a, b, other in stars:
                    if (a, b) != (x, y):
                        self.assertGreaterEqual(math.hypot(a - x, b - y), HAZE_APART if other in HAZE else STAR_APART)
        # Fewer than the deep blue would have there: 32 * 0.4 * 150 / 365 makes about five a room.
        self.assertTrue(3 * 16 <= haze <= 7 * 16, haze)
        self.assertEqual([star for star in night(6, 3, (DEEP, HEIGHT)).stars if star[2] in HAZE], [])

    def test_the_purple_stars_are_fainter_and_never_flare(self):
        for kind in HAZE:
            self.assertFalse(kind.cross)
            self.assertLess(sum(kind.steps[-1]), sum(MID.steps[-1]))

    def test_a_whole_sky_of_deep_blue_has_its_full_count(self):
        self.assertEqual(len(night(7, 3, (DEEP, HEIGHT)).stars), STARS_PER_SKY)

    def test_a_room_has_the_same_stars_every_time_it_is_read(self):
        self.assertEqual(night(6, 11).stars, night(6, 11).stars)
        self.assertNotEqual(night(6, 11).stars, night(6, 12).stars)
        self.assertNotEqual(night(6, 11).stars, night(7, 11).stars)

    def test_most_are_dim_lilac_and_a_few_middling_and_bright_ones_warm(self):
        kinds = [kind for room in range(32) for *_, kind in night(8, room, (DEEP, HEIGHT)).stars]
        share = {kind: kinds.count(kind) / len(kinds) for kind in set(kinds)}
        self.assertAlmostEqual(share[DIM], 0.7, delta=0.06)
        middling = kinds.count(MID) + kinds.count(ROSE_MID)
        self.assertAlmostEqual(kinds.count(ROSE_MID) / middling, 0.35, delta=0.1)
        bright = kinds.count(BRIGHT) + kinds.count(ROSE_BRIGHT) + kinds.count(GOLD_BRIGHT)
        self.assertAlmostEqual((kinds.count(ROSE_BRIGHT) + kinds.count(GOLD_BRIGHT)) / bright, 0.5, delta=0.15)
        self.assertGreater(kinds.count(GOLD_BRIGHT), 0)


class DesertTests(unittest.TestCase):
    def test_a_room_of_sky_and_sand_is_desert_with_a_few_stars(self):
        rgb = picture((PURPLE, 70), (SAND, 200))
        sky = sky_mask(rgb)
        air = read_room(9, 11, rgb, PALETTE)
        self.assertTrue(air.desert)
        self.assertEqual(len(air.stars), DESERT_STARS)
        for x, y, kind in air.stars:
            self.assertIn(kind, (MID, BRIGHT))
            self.assertTrue(sky[y - DESERT_STAR_CLEAR:y + DESERT_STAR_CLEAR + 1,
                                x - DESERT_STAR_CLEAR:x + DESERT_STAR_CLEAR + 1].all())
            for a, b, _ in air.stars:
                if (a, b) != (x, y):
                    self.assertGreaterEqual(abs(a - x) + abs(b - y), DESERT_STAR_APART)

    def test_sand_without_sky_or_sky_without_sand_is_no_desert(self):
        self.assertFalse(read_room(9, 1, picture((SAND, 200)), PALETTE).desert)
        self.assertFalse(read_room(9, 1, picture((DEEP, 200), (SAND, 30)), PALETTE).desert)


CREST = 200
ROCK = (slice(260, 280), slice(200, 240))


def dunes_air(rock=True):
    """Sky down to the crest at row 200, sand below it, and a rock on the plain."""
    rgb = picture((PURPLE, 70), (DEEP, CREST - 70), (SAND, HEIGHT - CREST))
    if rock:
        rgb[ROCK] = STONE
    return read_room(9, 11, rgb, PALETTE)


def blown_sand(ambience, ticks, plain):
    """{(x, y)} of every pixel the blown sand changed, tick after tick."""
    changed = set()
    air = read_room(9, 11, plain, PALETTE)
    for _ in range(ticks):
        ambience.advance()
        frame = frame_of(plain)
        ambience.put_sand(frame.load(), air)
        ys, xs = numpy.nonzero((numpy.asarray(frame.convert('RGB')) != plain).any(axis=2))
        changed |= set(zip(xs.tolist(), ys.tolist()))
    return changed


def steady_gust(born=0, **changes):
    """A gust at full strength over the crest and the plain, crossing the whole room."""
    return replace(ruins_ambience.Gust(born, -20.0, 10.0 ** 4, ruins_ambience.CREST_FRONT, 1.0), **changes)


class DuneTests(unittest.TestCase):
    def test_the_dunes_crest_their_plain_and_a_rock(self):
        dunes = dunes_air().dunes
        self.assertEqual(set(dunes.crest.tolist()), {CREST})
        self.assertEqual(set(dunes.ground_top), {CREST + ruins_ambience.GROUND_FROM})
        self.assertEqual(len(dunes.rocks), 1)
        rock = dunes.rocks[0]
        self.assertEqual((rock.left, max(rock.foot)), (200, 239))
        self.assertEqual(set(rock.foot.values()), {279})
        # Its lee lifts no sand: a rock's width downwind, about its foot.
        self.assertFalse(dunes.open_sand[271:283, 240:279].any())
        self.assertTrue(dunes.open_sand[271:283, 280:].all())
        self.assertTrue(dunes.open_sand[220:260].all())

    def test_sand_that_is_not_a_plain_of_dunes_has_none(self):
        sand = numpy.zeros((HEIGHT, WIDTH), dtype=bool)
        sand[200:, :300] = True
        self.assertIsNone(ruins_ambience.read_dunes(sand))
        steep = numpy.zeros((HEIGHT, WIDTH), dtype=bool)
        for x in range(WIDTH):
            steep[150 + x // 5:, x] = True
        self.assertIsNone(ruins_ambience.read_dunes(steep))

    def quiet(self, seed=1, **changes):
        ambience = DesertWind(dunes_air(**changes).dunes, random.Random(seed))
        ambience.desert_gust_wait = ambience.devil_wait = 10 ** 6
        return ambience

    def test_gusts_come_in_spells_and_lulls_about_as_often_as_before(self):
        # The user, 2026-11-22: a straight wave each time on the same beat. Before, every
        # gap was 70 to 100 ticks.
        ambience = DesertWind(dunes_air().dunes, random.Random(4))
        ambience.devil_wait = 10 ** 6
        starts = []
        for _ in range(12 * 60 * 10):
            before = [gust.born for gust in ambience.desert_gusts]
            ambience.advance()
            starts += [gust.born for gust in ambience.desert_gusts if gust.born not in before]
        self.assertTrue(ruins_ambience.FIRST_DESERT_GUST[0] <= starts[0] <= ruins_ambience.FIRST_DESERT_GUST[1] + 1)
        gaps = [b - a for a, b in zip(starts, starts[1:])]
        soon = sum(gap <= ruins_ambience.GUST_SOON[1] for gap in gaps) / len(gaps)
        self.assertTrue(0.3 <= soon <= 0.6, soon)
        self.assertGreater(max(gaps), 150)
        self.assertTrue(70 <= sum(gaps) / len(gaps) <= 105, sum(gaps) / len(gaps))

    def test_each_gust_is_its_own(self):
        ambience = self.quiet(9)
        gusts = [ambience.new_gust() for _ in range(400)]
        strengths = [gust.strength for gust in gusts]
        self.assertLess(min(strengths), 0.65)
        self.assertGreater(max(strengths), 1.3)
        self.assertAlmostEqual(sum(strengths) / len(strengths), 1.0, delta=0.06)
        self.assertGreater(max(gust.speed for gust in gusts) - min(gust.speed for gust in gusts), 2.5)
        kinds = [(gust.crest, gust.plain) for gust in gusts]
        self.assertAlmostEqual(kinds.count((True, True)) / 400, 0.6, delta=0.08)
        self.assertGreater(kinds.count((True, False)), 30)
        self.assertGreater(kinds.count((False, True)), 60)
        # Some die away before they have crossed the room, some come down inside it.
        self.assertTrue(any(gust.start + gust.reach < WIDTH - 100 for gust in gusts))
        self.assertTrue(any(gust.start > 80 for gust in gusts))
        self.assertGreater(sum(gust.start < 0 for gust in gusts), 200)

    def test_a_gust_rises_blows_harder_and_softer_and_dies_away(self):
        gust = ruins_ambience.Gust(0, 0.0, 400.0, 6.0, 0.8, phase=1.0)
        self.assertEqual(gust.strength_at(0), 0.0)
        self.assertEqual(gust.strength_at(400), 0.0)
        middle = [gust.strength_at(run) for run in range(60, 260, 4)]
        self.assertTrue(all(0.35 < value <= 0.8 * 1.1 for value in middle))
        self.assertGreater(max(middle) - min(middle), 0.15)
        self.assertLess(gust.strength_at(380), min(middle))

    def blown_by(self, gust, ticks=40, seed=10):
        ambience = self.quiet(seed)
        ambience.desert_gusts = [gust]
        count = 0
        for tick in range(ticks):
            ambience.tick = tick
            ambience.blown, ambience.spray = [], []
            ambience.blow_the_crest()
            ambience.blow_the_plain()
            count += len(ambience.blown) + len(ambience.spray)
        return ambience, count

    def test_a_weak_gust_lifts_less_sand_and_each_blows_only_its_own_part(self):
        _, strong = self.blown_by(steady_gust(strength=1.45))
        _, weak = self.blown_by(steady_gust(strength=0.55))
        self.assertLess(weak, 0.55 * strong)
        self.assertGreater(weak, 0)
        crest_only = self.quiet(11)
        crest_only.desert_gusts = [steady_gust(plain=False)]
        plain_only = self.quiet(11)
        plain_only.desert_gusts = [steady_gust(crest=False)]
        for tick in range(30):
            for ambience in (crest_only, plain_only):
                ambience.tick = tick
                ambience.blow_the_crest()
                ambience.blow_the_plain()
        self.assertTrue(crest_only.spray)
        self.assertEqual(crest_only.blown, [])
        self.assertTrue(plain_only.blown)
        self.assertEqual(plain_only.spray, [])

    def test_a_gust_blows_sand_off_the_crest_and_along_the_plain_and_never_above_it(self):
        ambience = self.quiet(2)
        ambience.desert_gusts = [steady_gust(ambience.tick)]
        plain = picture((PURPLE, 70), (DEEP, CREST - 70), (SAND, HEIGHT - CREST))
        plain[ROCK] = STONE
        changed = blown_sand(ambience, 90, plain)
        rows = {y for _, y in changed}
        # A low spray just over the crest, and sand off the plain; none higher.
        self.assertTrue(any(CREST - 6 <= y < CREST for y in rows))
        self.assertTrue(any(y >= ambience.dunes.ground_top[0] for y in rows))
        self.assertGreaterEqual(min(rows), CREST - 8)
        xs = {x for x, _ in changed}
        self.assertLess(min(xs), 60)
        self.assertGreater(max(xs), WIDTH - 60)

    def test_blown_sand_is_gentler_than_the_sand_it_is_drawn_in(self):
        air = dunes_air()
        palette = {tuple(colour[:3]) for colour in PALETTE.values()}
        for drawn in ruins_ambience.DESERT_COLOURS:
            ink = air.inks[drawn][:3]
            softer = air.gentle(SAND, ink)[:3]
            self.assertIn(softer, palette)
            self.assertNotEqual(softer, SAND)

    def test_the_plain_lifts_sand_only_out_of_the_rocks_lee(self):
        ambience = self.quiet(3)
        dunes = ambience.dunes
        for tick in range(0, 90, 3):
            ambience.tick = tick
            ambience.desert_gusts = [steady_gust()]
            ambience.blown = []
            ambience.blow_the_plain()
            for grain in ambience.blown:
                self.assertTrue(dunes.open_sand[int(grain.y), int(grain.x)], (grain.x, grain.y))

    def test_a_grain_running_into_a_rock_bounces_up_its_face(self):
        ambience = self.quiet(4)
        grain = ruins_ambience.Blown(185.0, 277.0, 277.0, 0.9, 4.0, -0.1, 0.12, 30)
        ambience.blown = [grain]
        for _ in range(6):
            ambience.advance_blown()
            if grain.bounced:
                break
        self.assertTrue(grain.bounced)
        self.assertLess(grain.x, 200)
        self.assertLess(grain.dy, 0)

    def test_as_a_gust_reaches_a_big_rock_sand_runs_at_its_foot(self):
        ambience = self.quiet(5)
        ambience.desert_gusts = [steady_gust()]
        ambience.tick = (200 - 20 + 20) // 7
        ambience.run_at_rocks()
        self.assertTrue(ambience.blown)
        for grain in ambience.blown:
            self.assertTrue(170 <= grain.x <= 197)
            self.assertTrue(276 <= grain.y <= 281)
        ambience = self.quiet(5)
        ambience.desert_gusts = [steady_gust()]
        ambience.tick = 5
        ambience.run_at_rocks()
        self.assertEqual(ambience.blown, [])

    def test_the_dust_devil_rises_on_the_crest_spins_and_dies_away(self):
        ambience = self.quiet(6, rock=False)
        ambience.devil_wait = 1
        plain = picture((PURPLE, 70), (DEEP, CREST - 70), (SAND, HEIGHT - CREST))
        changed = blown_sand(ambience, 2, plain)
        self.assertEqual(len(ambience.devils), 1)
        devil = ambience.devils[0]
        foot = CREST + ruins_ambience.DEVIL_FOOT
        changed |= blown_sand(ambience, devil.life, plain)
        self.assertTrue(changed)
        for x, y in changed:
            self.assertGreaterEqual(y, foot - ruins_ambience.DEVIL_HEIGHTS[1] - 12)
            self.assertLessEqual(y, foot + 3)
            # Sand sprayed left can travel about 25 pixels from the wandering base.
            self.assertGreaterEqual(x, devil.start - devil.wander - 26)
        while ambience.devils:
            ambience.advance()
        low, high = ruins_ambience.TICKS_BETWEEN_DEVILS
        self.assertTrue(low <= ambience.devil_wait + 0 <= high)

    def test_each_dust_devil_is_its_own(self):
        # The user, 2026-11-22: the devil was always the same, with the same moves.
        ambience = self.quiet(12, rock=False)
        devils = [ambience.new_devil() for _ in range(60)]
        for name in ('life', 'drift', 'height', 'top', 'lean', 'grain_count', 'sway', 'sway_speed', 'foot'):
            values = [getattr(devil, name) for devil in devils]
            low, high = min(values), max(values)
            self.assertGreater(high - low, 0.3 * high, name)
        self.assertEqual(len({devil.phase for devil in devils}), 60)
        # The old devil had one height and one life.
        self.assertGreater(len({devil.life for devil in devils}), 20)

    def test_a_devil_wanders_to_and_fro_and_thickens_and_thins(self):
        crest = numpy.full(WIDTH, CREST)
        devil = ruins_ambience.Devil(0, 200.0, life=200, drift=0.3, wander=4.0, wander_ticks=10.0,
                                     pulse=0.4, pulse_ticks=8.0)
        steps = [devil.base(tick + 1, crest)[0] - devil.base(tick, crest)[0] for tick in range(30, 150)]
        self.assertTrue(any(step < 0 for step in steps))
        self.assertTrue(any(step > 0.3 for step in steps))
        strengths = [devil.strength(tick) for tick in range(40, 160)]
        self.assertLess(min(strengths), 0.7)
        self.assertGreater(max(strengths), 0.95)

    def test_sand_whirls_at_the_devil_s_foot_and_is_thrown_out_and_falls_back(self):
        ambience = self.quiet(13, rock=False)
        ambience.devil_wait = 1
        plain = picture((PURPLE, 70), (DEEP, CREST - 70), (SAND, HEIGHT - CREST))
        air = dunes_air(rock=False)
        kicks_seen = 0
        spray_sides = []
        most_bright_pixels = {-1: 0, 1: 0}
        for _ in range(120):
            ambience.advance()
            if not ambience.devils:
                continue
            devil = ambience.devils[0]
            base_x, base_y = devil.base(ambience.tick, ambience.dunes.crest)
            self.assertLessEqual(len(devil.kicks), 12)
            for kick in devil.kicks:
                x, y = devil.kick_point(kick, base_x, base_y)
                kicks_seen += 1
                self.assertLessEqual(abs(x - base_x), 4.25)
                self.assertTrue(base_y - 2 <= y <= base_y + 1, (y, base_y))
            for grain in devil.thrown:
                self.assertNotEqual(grain.dx, 0)
                self.assertTrue(grain.ground - 6 <= grain.y < grain.ground + 1)
                self.assertLessEqual(abs(grain.dx * grain.age), 23)
            new_grains = [grain for grain in devil.thrown if grain.age == 1]
            if len(new_grains) >= 4:
                sides = {1 if grain.dx > 0 else -1 for grain in new_grains}
                self.assertEqual(len(sides), 1)
                spray_sides.extend(sides)
            pixels = list(ambience.desert_pixels())
            if devil.kicks:
                self.assertTrue(any(abs(y - base_y) <= 2 and abs(x - base_x) <= devil.foot + 1
                                    for x, y, _ in pixels))
            if devil.thrown:
                frame = frame_of(plain)
                canvas = frame.load()
                ambience.put_sand(canvas, air)
                for side in most_bright_pixels:
                    spray = {(x, y) for x, y, _ in pixels if (x - base_x) * side > 4
                             and abs(y - base_y) <= 6 and canvas[x, y][1] >= SAND[1] + 15}
                    most_bright_pixels[side] = max(most_bright_pixels[side], len(spray))
        self.assertGreater(kicks_seen, 0)
        self.assertEqual(set(spray_sides), {-1, 1})
        self.assertTrue(any(first == second for first, second in zip(spray_sides, spray_sides[1:])))
        self.assertGreaterEqual(min(most_bright_pixels.values()), 5)

    def test_the_devil_s_foot_does_not_trip_on_a_dip_in_the_crest(self):
        crest = numpy.full(WIDTH, CREST)
        crest[150:154] = CREST + 9
        devil = ruins_ambience.Devil(0, 140.0)
        for tick in range(0, 80):
            self.assertEqual(devil.base(tick, crest)[1], CREST + ruins_ambience.DEVIL_FOOT)

    def test_a_dust_devil_rises_only_where_the_crest_runs_all_its_way(self):
        ambience = self.quiet(7, rock=False)
        dunes = ambience.dunes
        crest = dunes.crest.copy()
        crest[:WIDTH - 60] = -1
        ambience.dunes = replace(dunes, crest=crest)
        ambience.devil_wait = 1
        ambience.advance()
        self.assertFalse(ambience.devils)

    def test_gust_stream_and_devil_continue_across_the_same_room_seam(self):
        air = dunes_air(rock=False)
        wind = DesertWind(Dunes.join((air.dunes, air.dunes)), random.Random(74))
        wind.tick = 40
        wind.desert_gust_wait = wind.devil_wait = 1000
        gust = steady_gust(0, start=WIDTH - 240)
        stream = ruins_ambience.Stream(40, 0.5, WIDTH - 1, 8, 380, 0)
        crest_grain = ruins_ambience.Blown(WIDTH - 1, CREST - 3, CREST - 3, 0.0, 3, -0.4, 0.12, 15)
        floor_grain = ruins_ambience.Blown(WIDTH - 1, 270, 270, 0.5, 4, -0.4, 0.12, 15)
        devil = ruins_ambience.Devil(-10, WIDTH - 21, foot=3.5)
        wind.desert_gusts = [gust]
        wind.streams = [stream]
        wind.spray = [crest_grain]
        wind.blown = [floor_grain]
        wind.devils = [devil]
        self.assertLess(devil.base(wind.tick, wind.dunes.crest)[0], WIDTH)
        for _ in range(4):
            wind.advance()
        self.assertIs(wind.desert_gusts[0], gust)
        self.assertIs(wind.streams[0], stream)
        self.assertIs(wind.devils[0], devil)
        self.assertGreater(devil.base(wind.tick, wind.dunes.crest)[0], WIDTH)
        self.assertTrue(any(front > WIDTH for front, _ in wind.fronts(ruins_ambience.CREST_FRONT, 'crest')))
        self.assertTrue(any(grain is crest_grain and grain.x >= WIDTH for grain in wind.spray))
        self.assertTrue(any(grain is floor_grain and grain.x >= WIDTH for grain in wind.blown))
        local = frame_of(picture((DEEP, CREST), (SAND, HEIGHT - CREST)))
        previous = local.tobytes()
        wind.put_sand(local.load(), air, WIDTH)
        self.assertNotEqual(local.tobytes(), previous)


class TwinkleTests(unittest.TestCase):
    def test_a_star_mostly_holds_its_light_and_dips_a_few_ticks_at_a_time(self):
        ambience = RuinsAmbience(11, night(6, 11, (DEEP, HEIGHT)), random.Random(3))
        lit = dips = 0
        run = [0] * len(ambience.twinkles)
        runs = []
        for _ in range(3000):
            ambience.advance()
            for index, (dipped, flared) in enumerate(ambience.twinkles):
                lit += not dipped
                if dipped:
                    run[index] += 1
                elif run[index]:
                    runs.append(run[index])
                    run[index] = 0
                    dips += 1
                if flared:
                    self.assertTrue(ambience.air.stars[index][2].cross)
        self.assertGreater(lit / (3000 * len(ambience.twinkles)), 0.93)
        self.assertGreater(dips, 100)
        self.assertGreaterEqual(min(runs), DIP_TICKS[0])
        self.assertLessEqual(max(runs), DIP_TICKS[1])

    def test_a_dipped_star_shows_its_dim_step_and_a_flaring_one_its_cross(self):
        air = replace(night(), stars=((100, 50, BRIGHT), (200, 60, MID)))
        ambience = RuinsAmbience(11, air, random.Random(1))
        self.assertEqual(list(ambience.sky_pixels()), [(100, 50, BRIGHT.steps[1]), (200, 60, MID.steps[1])])
        ambience.twinkles = [[0, 3], [2, 0]]
        self.assertEqual(list(ambience.sky_pixels()), [
            (100, 50, BRIGHT.steps[1]), (101, 50, BRIGHT.steps[0]), (99, 50, BRIGHT.steps[0]),
            (100, 51, BRIGHT.steps[0]), (100, 49, BRIGHT.steps[0]), (200, 60, MID.steps[0])])


class ShootingStarTests(unittest.TestCase):
    def ambience(self, seed, *bands):
        return RuinsAmbience(11, replace(night(6, 11, *bands), stars=()), random.Random(seed))

    def test_none_comes_as_the_prince_walks_in(self):
        for seed in range(40):
            ambience = self.ambience(seed)
            for tick in range(FIRST_SHOOTER[0] - 1):
                ambience.advance()
                self.assertIsNone(ambience.shooter, (seed, tick))

    def test_they_come_every_ten_to_twenty_five_seconds_one_at_a_time(self):
        # The user, 2026-11-22: they had waited and seen none; they were not meant to be
        # that rare. About three a minute in a room the Prince stays in, the first soon.
        self.assertEqual((FIRST_SHOOTER, TICKS_BETWEEN_SHOOTERS), ((24, 120), (120, 300)))
        ambience = self.ambience(5)
        starts, previous = [], None
        for tick in range(12 * 60 * 30):
            ambience.advance()
            if ambience.shooter is not None and ambience.shooter is not previous:
                starts.append(tick)
            previous = ambience.shooter
        self.assertGreater(len(starts), 80)
        self.assertLess(len(starts), 130)
        self.assertLessEqual(starts[0], FIRST_SHOOTER[1])
        self.assertGreaterEqual(min(b - a for a, b in zip(starts, starts[1:])), TICKS_BETWEEN_SHOOTERS[0])

    def test_the_fireball_is_the_rarest(self):
        ambience = self.ambience(9)
        counts = {kind: 0 for kind in SHOOTERS}
        for _ in range(3000):
            ambience.shooter, ambience.shooter_wait = None, 1
            ambience.advance_shooter()
            counts[ambience.shooter.kind] += 1
        self.assertGreater(counts[FAINT], counts[NORMAL])
        self.assertGreater(counts[NORMAL], counts[GRAZER])
        self.assertGreater(counts[GRAZER], counts[FIREBALL])
        self.assertAlmostEqual(counts[FIREBALL] / 3000, 0.07, delta=0.02)

    def test_its_flight_stays_over_the_sky_the_purple_too(self):
        air = night(6, 11, (DEEP, 100), (PURPLE, 100))
        rng = random.Random(2)
        purple = 0
        for kind in SHOOTERS * 30:
            x, y, dx, dy = shooter_path(air, kind, rng)
            travel = kind.speed * kind.ticks
            for share in (0, 0.25, 0.5, 0.75, 1):
                self.assertLess(y + dy * travel * share, 200)
            purple += y + dy * travel >= 100
            self.assertGreater(dy, 0)
            self.assertLessEqual(math.degrees(math.asin(dy)), kind.angle[1])
        # Before, none crossed the purple, which most rooms show more of than the deep blue.
        self.assertGreater(purple, 20)

    def test_a_sky_all_purple_has_shooting_stars_and_stone_none(self):
        ambience = self.ambience(4, (PURPLE, 200))
        seen = 0
        for _ in range(4000):
            ambience.advance()
            seen += ambience.shooter is not None
        self.assertGreater(seen, 0)
        ambience = RuinsAmbience(11, read_room(6, 11, picture((STONE, HEIGHT)), PALETTE), random.Random(4))
        for _ in range(4000):
            ambience.advance()
            self.assertIsNone(ambience.shooter)

    def test_the_tail_shortens_as_it_burns_out(self):
        # The fireball's trail stays behind it as it goes (below).
        for kind in (FAINT, NORMAL, GRAZER):
            first = len(list(shooter_pixels(Shooter(kind, 100, 40, 0.9, 0.3, 0))))
            last = len(list(shooter_pixels(Shooter(kind, 100, 40, 0.9, 0.3, kind.ticks - 1))))
            self.assertGreater(first, last, kind.name)

    def test_only_the_regular_fireball_bursts_and_leaves_its_trail(self):
        for kind in (FAINT, NORMAL, GRAZER):
            self.assertEqual(list(shooter_pixels(Shooter(kind, 100, 40, 1, 0, kind.ticks))), [])
            self.assertEqual(kind.lasts, kind.ticks)
        burst = list(shooter_pixels(Shooter(FIREBALL, 100, 40, 1, 0, FIREBALL.ticks)))
        end = round(100 + FIREBALL.speed * (FIREBALL.ticks - 1))
        self.assertIn((end, 40, FIREBALL.head), burst)
        self.assertIn((end + 1, 40, FIREBALL.colours[0]), burst)
        trail = list(shooter_pixels(Shooter(FIREBALL, 100, 40, 1, 0, FIREBALL.lasts - 1)))
        self.assertTrue(trail)
        self.assertEqual({colour for *_, colour in trail}, {FIREBALL.colours[-1]})
        self.assertGreaterEqual(min(x for x, *_ in trail), end - 28)

    def test_it_ends_when_it_has_lasted(self):
        ambience = self.ambience(1)
        ambience.shooter, ambience.shooter_wait = None, 1
        while ambience.shooter is None or ambience.shooter.kind is not FIREBALL:
            ambience.shooter, ambience.shooter_wait = None, 1
            ambience.advance_shooter()
        for _ in range(FIREBALL.lasts - 1):
            ambience.advance_shooter()
            self.assertIsNotNone(ambience.shooter)
        ambience.advance_shooter()
        self.assertIsNone(ambience.shooter)


class DrawingTests(unittest.TestCase):
    def busy(self, *, windy=True, palette=PALETTE):
        air = read_room(6, 11, picture((DEEP, 150), (PURPLE, 60)), palette)
        ambience = RuinsAmbience(11, replace(air, windy=windy), random.Random(8))
        for _ in range(200):
            ambience.advance()
        if windy:
            ambience.wind = ruins_ambience.RuinsWind(random.Random(8))
            ambience.wind.prime()
        ambience.twinkles[0] = [0, 2]
        ambience.shooter = Shooter(FIREBALL, 120, 30, math.cos(0.3), math.sin(0.3), 4)
        return ambience

    def test_only_the_sky_still_showing_is_drawn(self):
        ambience = self.busy(windy=False)
        rgb = picture((DEEP, 150), (PURPLE, 60))
        # A gate down in front of the sky, drawn after the room was read.
        rgb[0:150, 100:220] = STONE
        frame = frame_of(rgb)
        ambience.draw(frame)
        after = numpy.asarray(frame)[..., :3]
        changed = (after != rgb).any(axis=2)
        self.assertTrue(changed.any())
        self.assertFalse(changed[:, 100:220].any())
        self.assertFalse(changed[210:].any())

    def test_every_pixel_left_is_a_colour_of_the_palette(self):
        palette = {index: (*colour, 255) for index, colour in enumerate(
            (DEEP, PURPLE, STONE, (60, 60, 120), (130, 130, 170), (220, 220, 230), (200, 140, 140)))}
        ambience = self.busy(palette=palette)
        self.assertTrue(ambience.streaks)
        frame = frame_of(picture((DEEP, 150), (PURPLE, 60)))
        ambience.draw(frame)
        shown = {tuple(value) for value in numpy.asarray(frame).reshape(-1, 4)}
        self.assertLessEqual(shown, set(palette.values()))
        self.assertGreater(len(shown), 3)

    def test_drawing_twice_in_a_tick_draws_the_same(self):
        ambience = self.busy()
        twinkles = [list(twinkle) for twinkle in ambience.twinkles]
        first, second = frame_of(picture((DEEP, 150))), frame_of(picture((DEEP, 150)))
        ambience.draw(first)
        ambience.draw(second)
        self.assertEqual(first.tobytes(), second.tobytes())
        self.assertEqual(ambience.twinkles, twinkles)
        self.assertEqual(ambience.shooter.age, 4)


class PuffTests(unittest.TestCase):
    """The caves' puffs from his feet and whatever comes down (the user, 2026-11-22), in
    the dust of the ruins' stone."""

    # A run to the left, as the caves' FeetTests play it: his body, the game's foot and
    # the frame. A foot lands on frames 6, 9 and 12.
    RUN = ((313, 341, 5), (306, 318, 6), (293, 316, 7), (283, 288, 8), (269, 270, 9), (262, 269, 10), (244, 268, 11),
           (228, 230, 12), (226, 228, 13), (220, 226, 14), (200, 223, 7), (190, 195, 8), (176, 177, 9))
    TURN = ((220, 226, 14), (200, 223, 7), (198, 197, 53), (197, 197, 54), (170, 167, 55), (164, 163, 56),
            (139, 145, 57), (131, 138, 58))

    def ambience(self, covered=None):
        air = replace(read_room(6, 11, picture((DEEP, 100)), PALETTE, covered), stars=())
        ambience = RuinsAmbience(11, air, random.Random(3))
        ambience.quiet_wait = ambience.shooter_wait = 10 ** 6
        return ambience

    @staticmethod
    def made(ambience, **inputs):
        """The puffs this tick raised."""
        ambience.advance(**inputs)
        return [cloud for cloud in ambience.clouds if cloud.age.max() == 1]

    def footing(self, x, foot, action=0):
        return Footing(x, foot, 226, action != 12, False, 0, action)

    def test_each_foot_raises_a_tuft_where_it_lands_and_a_skid_sprays_ahead(self):
        ambience = self.ambience()
        stepped = []
        for step in self.RUN:
            made = self.made(ambience, footing=self.footing(*step))
            if made:
                stepped.append(step[2])
                self.assertEqual([cloud.kind for cloud in made], [STEP_PUFF])
        self.assertEqual(stepped, [6, 9, 12, 9])
        skids = [step[2] for step in self.TURN
                 if any(cloud.kind is SKID_PUFF for cloud in self.made(ambience, footing=self.footing(*step)))]
        self.assertEqual(skids, [55, 57])

    def test_a_landing_raises_more_the_further_he_fell(self):
        ambience = self.ambience()
        self.made(ambience, footing=Footing(200, 200, 226, True, True, 36))
        made = self.made(ambience, footing=Footing(205, 200, 226, True, False))
        self.assertEqual(len(made), 1)
        self.assertEqual(len(made[0].x), 2 * MOST_LANDING_LOBES)
        self.assertEqual(made[0].kind.size, LANDING_PUFF.size)

    def test_a_tile_and_a_gate_coming_down_raise_theirs(self):
        ambience = self.ambience()
        tile, = self.made(ambience, thuds=[tile_landing(14)])
        self.assertIs(tile.kind, TILE_PUFF)
        gate, = self.made(ambience, thuds=[door_coming_down(GATE, 17, True)])
        self.assertIs(gate.kind, SLAM_PUFF)
        # None in front of the slab that came down: it is behind it.
        self.assertTrue(gate.hidden.any())

    def test_they_thin_away(self):
        ambience = self.ambience()
        self.made(ambience, thuds=[tile_landing(14)])
        for _ in range(TILE_PUFF.life[1] + 1):
            ambience.advance()
        self.assertEqual(ambience.clouds, [])

    def landed(self, covered=None, rgb=None):
        ambience = self.ambience(covered)
        self.made(ambience, footing=Footing(200, 200, 226, True, True, 36))
        self.made(ambience, footing=Footing(205, 200, 226, True, False))
        for _ in range(3):
            ambience.advance()
        rgb = picture((DEEP, 100)) if rgb is None else rgb
        frame = ambience.draw(frame_of(rgb))
        return rgb, numpy.asarray(frame)

    def test_over_a_speckled_floor_it_is_flat_lumps_not_speckles(self):
        # Taken pixel by pixel, the puff came out as speckles again on the ruins' floors.
        rgb = picture((DEEP, 100))
        rgb[100:][(numpy.indices((HEIGHT - 100, WIDTH)).sum(axis=0) % 2) == 1] = SAND
        rgb, after = self.landed(rgb=rgb)
        changed = (after[..., :3] != rgb).any(axis=2)
        self.assertGreater(changed.sum(), 40)
        ys, xs = numpy.nonzero(changed[:, :-1] & changed[:, 1:])
        same = (after[ys, xs, :3] == after[ys, xs + 1, :3]).all(axis=1)
        self.assertGreater(same.mean(), 0.7)

    def test_its_pixels_are_the_palette_s_paler_than_the_floor_and_low_on_it(self):
        rgb, after = self.landed()
        changed = (after[..., :3] != rgb).any(axis=2)
        self.assertTrue(changed.any())
        ys, xs = numpy.nonzero(changed)
        self.assertTrue(226 - LANDING_PUFF.height <= ys.min() and ys.max() < 226 + 12)
        self.assertTrue(150 < xs.min() and xs.max() < 250)
        self.assertTrue((after[changed][:, :3].astype(int).sum(axis=1) > sum(STONE)).all())
        self.assertLessEqual({tuple(value) for value in after.reshape(-1, 4)}, set(PALETTE.values()))

    def test_none_over_what_the_foreground_covers(self):
        covered = numpy.zeros((HEIGHT, WIDTH), dtype=bool)
        covered[:, :200] = True
        rgb, after = self.landed(covered)
        changed = (after[..., :3] != rgb).any(axis=2)
        self.assertTrue(changed[:, 200:].any())
        self.assertFalse(changed[:, :200].any())


class WindTests(unittest.TestCase):
    def test_a_streak_rolls_one_small_curl_that_comes_out_a_little_higher(self):
        for seed in range(40):
            pixels, (begin, end) = ribbon(20, 150, random.Random(seed))
            curl = pixels[begin:end + 1]
            xs, ys = [x for x, _ in curl], [y for _, y in curl]
            self.assertLessEqual(max(xs) - min(xs), 2 * CURL_RADIUS[1] + 2, seed)
            self.assertLessEqual(max(ys) - min(ys), 2 * CURL_RADIUS[1] + 2, seed)
            self.assertLess(min(ys), pixels[begin][1] - 2 * CURL_RADIUS[0] + 3, seed)
            self.assertIn(pixels[begin][1] - pixels[end][1], range(round(CURL_RISE) - 1, round(CURL_RISE) + 2), seed)

    def test_it_slows_down_to_wind_its_curl(self):
        streak = new_streak(random.Random(4))
        begin, end = streak.curl
        steps, in_curl = [], 0
        while not streak.gone:
            step = streak.step()
            steps.append(step)
            in_curl += begin <= streak.head <= end
            streak.head += step
        self.assertEqual(steps[0], STREAK_SPEED)
        self.assertEqual(steps[-1], STREAK_SPEED)
        self.assertIn(CURL_SPEED, steps)
        # About eight ticks, two thirds of a second, to wind it.
        self.assertGreaterEqual(in_curl, (end - begin) // CURL_SPEED)

    def test_it_fades_in_and_out_a_third_at_a_time(self):
        streak = new_streak(random.Random(6))
        strengths = []
        while not streak.gone:
            strengths.append(streak.strength())
            streak.head += streak.step()
            streak.shown += 1
        self.assertEqual(strengths[:5], [1 / 3, 1 / 3, 2 / 3, 2 / 3, 1])
        self.assertEqual(strengths[-1], 1 / 3)
        self.assertEqual(max(strengths), 1)
        for a, b in zip(strengths, strengths[1:]):
            self.assertLessEqual(abs(a - b), 1 / 3 + 1e-9)
        streak.head, streak.shown = 0, 0
        self.assertEqual({amount for *_, amount in streak_pixels(streak)} - {(0, 0, 0)}, set())
        streak.head = 30
        self.assertEqual({amount for *_, amount in streak_pixels(streak)},
                         {tuple(round(value / 3) for value in BODY_PALER), (9, 8, 10)})

    def test_a_winding_streak_rolls_into_a_small_spiral(self):
        for seed in range(40):
            streak = new_streak(random.Random(seed), winding=True)
            curl = streak.pixels[streak.turn:]
            width = max(x for x, _ in curl) - min(x for x, _ in curl)
            height = max(y for _, y in curl) - min(y for _, y in curl)
            self.assertIn(max(width, height), (4, 5), seed)

    def test_its_pixels_are_a_clean_line(self):
        for seed in range(20):
            pixels = new_streak(random.Random(seed), winding=True).pixels
            for a, b in zip(pixels, pixels[1:]):
                self.assertLessEqual(max(abs(a[0] - b[0]), abs(a[1] - b[1])), 1)
                self.assertNotEqual(a, b)
            for a, b in zip(pixels, pixels[2:]):
                self.assertFalse(abs(a[0] - b[0]) == 1 and abs(a[1] - b[1]) == 1, seed)

    def test_the_wind_crosses_more_of_the_ruins_in_a_longer_faster_stroke(self):
        for seed in range(20):
            streak = new_streak(random.Random(seed), winding=True)
            streak.shown = 20
            first = list(streak.visible_pixels())
            streak.advance()
            second = list(streak.visible_pixels())
            self.assertGreaterEqual(len(first), 50, seed)
            self.assertGreaterEqual(max(max(rgb) for _, _, rgb in first), 38, seed)
            self.assertGreaterEqual(second[-1][0] - first[-1][0], 5, seed)
            streak.shown = ruins_ambience.RUINS_STREAK_STYLE.lifetime - 1
            [(x, _, _)] = streak.visible_pixels()
            self.assertGreaterEqual(x - streak.pixels[0][0], 210, seed)
            self.assertLess(x, WIDTH, seed)

    def test_only_a_room_open_to_the_sky_is_windy_and_never_the_desert(self):
        self.assertTrue(night(6, 4, (PURPLE, 30)).windy)
        self.assertTrue(night(6, 4, (PURPLE, 12)).windy)
        self.assertFalse(night(6, 4, (PURPLE, 5)).windy)
        self.assertFalse(read_room(9, 11, picture((PURPLE, 70), (SAND, 200)), PALETTE).windy)
        ambience = RuinsAmbience(4, night(6, 4, (PURPLE, 5)), random.Random(1))
        for _ in range(1000):
            ambience.advance()
            self.assertFalse(ambience.streaks)

    def test_gusts_keep_both_styles_balanced_with_shorter_pauses(self):
        wind = ruins_ambience.RuinsWind(random.Random(2))
        gusts = []
        for tick in range(60000):
            before = list(wind.streaks)
            wind.advance()
            new = [streak for streak in wind.streaks if streak not in before]
            if new:
                gusts.append((tick, new))
        self.assertGreater(len(gusts), 585)
        self.assertEqual(gusts[0][0], 0)
        self.assertEqual({len(new) for _, new in gusts}, {1, 2})
        streaks = [streak for _, new in gusts for streak in new]
        winding = sum(isinstance(streak, ruins_ambience.WindingStreak) for streak in streaks)
        self.assertAlmostEqual(winding / len(streaks), 0.5, delta=0.06)
        self.assertTrue(any({type(streak) for streak in new} == {ruins_ambience.Streak, ruins_ambience.WindingStreak}
                            for _, new in gusts))
        for _, new in gusts:
            if len(new) == 2:
                self.assertGreaterEqual(new[1].y - new[0].y, SECOND_STREAK_BELOW[0])
                self.assertLessEqual(new[1].y - new[0].y, SECOND_STREAK_BELOW[1])
        gaps = [b - a for (a, _), (b, _) in zip(gusts, gusts[1:])]
        self.assertGreaterEqual(min(gaps), 70)
        self.assertLessEqual(max(gaps), 102)

    def test_it_is_paler_than_what_it_crosses_and_behind_the_foreground(self):
        rgb = picture((DEEP, 150), (PURPLE, 60))
        covered = numpy.zeros((HEIGHT, WIDTH), dtype=bool)
        covered[:, 180:200] = True
        air = replace(read_room(6, 11, rgb, PALETTE, covered), stars=())
        ambience = RuinsAmbience(11, air, random.Random(3))
        streak = new_streak(random.Random(8), winding=True)
        streak.pixels = [(x, 100 + (x % 7 == 0)) for x in range(80, 300)]
        streak.turn, streak.shown = 210, 23
        ambience.wind = ruins_ambience.RuinsWind(streaks=[streak])
        frame = frame_of(rgb)
        ambience.draw(frame)
        after = numpy.asarray(frame)[..., :3].astype(int)
        changed = (after != rgb).any(axis=2)
        self.assertEqual(int(changed.sum()), ruins_ambience.RUINS_STREAK_STYLE.length - 20)
        self.assertFalse(changed[covered].any())
        self.assertTrue((after[changed].sum(axis=1) > rgb[changed].astype(int).sum(axis=1)).all())
        shown = {tuple(value) for value in after[changed]}
        self.assertLessEqual(shown, {colour[:3] for colour in PALETTE.values()})

    def test_a_winding_streak_draws_and_pushes_grit_at_its_moving_tip(self):
        rgb = picture((PURPLE, 70), (STONE, 60))
        air = replace(read_room(6, 4, rgb, PALETTE), stars=())
        ambience = RuinsAmbience(4, air, random.Random(3))
        streak = new_streak(random.Random(8), winding=True)
        ambience.wind = ruins_ambience.RuinsWind(streaks=[streak])
        for _ in range(ruins_ambience.RUINS_STREAK_STYLE.lifetime - 1):
            ambience.wind.advance_streaks()
        [(x, y, amount)] = list(streak.visible_pixels())
        home_x, home_y = streak.pixels[-1]
        self.assertEqual((x, y), (home_x + 42, home_y))
        self.assertGreater(math.hypot(*ambience.streak_push(x, y)), 0)
        self.assertEqual(ambience.streak_push(home_x, home_y), (0.0, 0.0))
        frame = ambience.draw(frame_of(rgb))
        self.assertEqual(frame.getpixel((x, y)), air.paler_than(tuple(rgb[y, x]), amount))
        ambience.wind.advance_streaks()
        self.assertFalse(ambience.streaks)

    def test_paler_is_never_the_colour_behind(self):
        palette = numpy.array(sorted({colour[:3] for colour in PALETTE.values()}))
        for behind in (DEEP, PURPLE, STONE, (84, 86, 140)):
            for amount in ((1, 1, 1), (17, 17, 21), ruins_ambience.RUINS_STREAK_STYLE.paler):
                colour = paler(behind, amount, palette)
                self.assertNotEqual(colour, behind)
                self.assertGreater(sum(colour), sum(behind))


class Floor:
    def __init__(self, kind):
        self.kind = kind


class FloorBelow:
    """A level map: stone along the top row, the grit's cracks in its underside, open
    air below it, a floor along the bottom row, and no room above."""

    def tile(self, room, column, row):
        return Floor(20 if row == 0 else 1 if row == 2 else 0)

    def neighbor(self, room, direction):
        return None


TERRAIN = FloorBelow()


class FallenAbove(FloorBelow):
    """FloorBelow with the stone of some columns fallen from the top row, and the floor of
    others fallen from the bottom one."""

    def __init__(self, columns, floor_gone=()):
        self.columns, self.floor_gone = set(columns), set(floor_gone)

    def tile(self, room, column, row):
        if (row == 0 and column in self.columns) or (row == 2 and column in self.floor_gone):
            return Floor(0)
        return super().tile(room, column, row)
GROUND = 346


def grit_air(**changes):
    """A dark room under three ceilings, with two cracks."""
    lines = tuple(tuple(c * 120 + 7 if 20 <= x < 490 else -1 for x in range(WIDTH)) for c in range(3))
    air = replace(night(6, 4, (PURPLE, 12)), stars=(),
                  grit=(ruins_ambience.Crack(100, 125, GROUND), ruins_ambience.Crack(300, 125, GROUND)), ceilings=lines)
    return replace(air, **changes)


def run_out(ambience, ticks=400, terrain=TERRAIN):
    for _ in range(ticks):
        ambience.advance(terrain)
        if not ambience.trickles:
            return


class GritTests(unittest.TestCase):
    def ambience(self, seed=1, **changes):
        ambience = RuinsAmbience(4, grit_air(**changes), random.Random(seed))
        ambience.quiet_wait = 10 ** 6
        return ambience

    def test_the_room_sheds_a_little_every_few_seconds_now_and_then_a_pour(self):
        ambience = self.ambience()
        ambience.quiet_wait = 1
        seen = []
        # Ten minutes, for enough of them to count the pours by.
        for _ in range(12 * 600):
            ambience.advance(TERRAIN)
            seen.extend(trickle for trickle in ambience.trickles if all(trickle is not other for other in seen))
        # The user, 2026-11-22: "um pouco too much" - how often, not its colour. Every 24
        # to 60 ticks gave about 170 in ten minutes.
        self.assertGreater(len(seen), 75)
        self.assertLess(len(seen), 135)
        self.assertAlmostEqual(sum(trickle.pour for trickle in seen) / len(seen), ruins_ambience.POUR_CHANCE,
                               delta=0.12)
        self.assertEqual({trickle.source.x for trickle in seen}, {100, 300})

    def test_a_pour_falls_straight_down_from_its_crack(self):
        # It used to sway a pixel aside, and to be two pixels wide under the crack.
        for seed in range(6):
            ambience = self.ambience(seed)
            ambience.start(100, 125, 26, 0, True, TERRAIN)
            thread_at_crack = False
            for _ in range(200):
                ambience.advance(TERRAIN)
                # Not the bits that come away from the crack first, or kick up on landing.
                flecks, ambience.flecks = ambience.flecks, []
                pixels = list(ambience.grit_pixels())
                ambience.flecks = flecks
                for x, y, _shade in pixels:
                    if 125 <= y < GROUND - 10:
                        self.assertEqual(x, 100, (seed, y))
                    thread_at_crack |= (x, y) == (100, 125)
                if not ambience.trickles:
                    break
            self.assertTrue(thread_at_crack)

    def test_one_trickle_at_a_crack(self):
        ambience = self.ambience()
        ambience.start(100, 125, 20, 0, True, TERRAIN)
        ambience.start(101, 125, 20, 0, True, TERRAIN)
        ambience.start(102, 125, 4, 0, False, TERRAIN)
        self.assertEqual(len(ambience.trickles), 1)
        ambience.start(300, 125, 4, 0, False, TERRAIN)
        ambience.start(301, 125, 4, 0, False, TERRAIN)
        self.assertEqual(len(ambience.trickles), 3)
        ambience.start(299, 125, 20, 0, True, TERRAIN)
        self.assertEqual(len(ambience.trickles), 3)

    def test_the_rhythm_picks_a_crack_that_is_free(self):
        ambience = self.ambience()
        ambience.start(100, 125, 20, 0, True, TERRAIN)
        for _ in range(10):
            ambience.quiet_wait = 1
            ambience.quiet_trickle(TERRAIN)
        self.assertEqual({trickle.source.x for trickle in ambience.trickles[1:]}, {300})

    def test_a_pour_heaps_a_small_mound_that_wears_away(self):
        ambience = self.ambience(3)
        ambience.start(100, 125, 26, 0, True, TERRAIN)
        run_out(ambience)
        self.assertEqual(len(ambience.mounds), 1)
        mound = ambience.mounds[0]
        self.assertTrue(all(height <= most for height, most in zip(mound.heights, ruins_ambience.MOUND)))
        self.assertGreater(sum(mound.heights), 4)
        stays = ruins_ambience.MOUND_STAYS[1] + 20 * (ruins_ambience.MOUND_WEARS[1] + 1)
        for _ in range(stays):
            ambience.advance(TERRAIN)
        self.assertEqual(ambience.mounds, [])

    def test_mostly_specks_some_chips_and_a_few_crumbs_that_break_in_two(self):
        ambience = self.ambience()
        sizes = []
        for _ in range(300):
            trickle = ruins_ambience.Trickle(ruins_ambience.Crack(100, 125, GROUND), 0, 1)
            ambience.release(trickle)
            sizes.append(trickle.grains[0].size)
        self.assertAlmostEqual(sizes.count('speck') / 300, 0.7, delta=0.08)
        self.assertAlmostEqual(sizes.count('chip') / 300, 0.25, delta=0.08)
        self.assertGreater(sizes.count('crumb'), 0)
        landed = []
        ambience.land = lambda x, bottom, pour, trickle=None: landed.append(x)
        trickle = ruins_ambience.Trickle(ruins_ambience.Crack(100, 125, GROUND), 0, 0)
        trickle.grains = [ruins_ambience.Grain(GROUND - 1.0, 3.0, 100.0, GRIT_HEAD, size='crumb')]
        ambience.trickles = [trickle]
        ambience.advance_trickles()
        self.assertEqual(landed, [100.0, 101.0])

    def test_no_grit_falls_from_where_a_loose_floor_fell(self):
        # It kept falling from the hole the floor left, out of thin air.
        fallen = FallenAbove({1})
        ambience = self.ambience(4)
        ambience.quiet_wait = 1
        seen = set()
        for _ in range(12 * 60):
            ambience.advance(fallen)
            seen |= {trickle.source.x for trickle in ambience.trickles}
        self.assertEqual(seen, {300})
        # Nor does a blow shake any down from under the hole.
        for seed in range(10):
            ambience = self.ambience(seed)
            ambience.shake(100, 1, 1.0, 'bump', FallenAbove({1, 2}))
            self.assertTrue(ambience.trickles, seed)
            # (The top ceiling is the room above's floor, which still stands.)
            self.assertFalse([trickle for trickle in ambience.trickles
                              if 51 <= trickle.source.x < 153 and trickle.source.top == 127], seed)
            self.assertTrue([trickle for trickle in ambience.trickles if trickle.source.top == 127], seed)

    def test_a_pour_stops_when_its_stone_falls_and_its_mound_goes_with_the_floor(self):
        ambience = self.ambience(5)
        ambience.start(100, 125, 26, 0, True, TERRAIN)
        for _ in range(8):
            ambience.advance(TERRAIN)
        trickle = ambience.trickles[0]
        released = trickle.released
        self.assertGreater(released, 2)
        fallen = FallenAbove({1})
        for _ in range(40):
            ambience.advance(fallen)
        self.assertEqual(trickle.released, released)
        self.assertEqual(ambience.trickles, [])
        # A mound on a floor that then gives way goes with it.
        ambience = self.ambience(3)
        ambience.start(100, 125, 26, 0, True, TERRAIN)
        run_out(ambience)
        self.assertEqual(len(ambience.mounds), 1)
        ambience.advance(FallenAbove(set(), floor_gone={1}))
        self.assertEqual(ambience.mounds, [])

    def test_a_pour_falls_past_a_gap_to_the_next_visible_floor(self):
        from PIL import Image

        strip = Image.new('RGBA', (21, 6), 'white')
        floors = ruins_ambience.grit_floor_profile(((1, strip, (90, 235)), (2, strip, (90, 345))))
        ambience = self.ambience(grit_floor=floors)
        ambience.start(100, 125, 30, 0, True, TERRAIN)
        self.assertEqual(ambience.trickles[0].source.bottom, 235)
        for _ in range(6):
            ambience.advance(TERRAIN)
        ambience.grit_floor = floors.copy()
        # The upper floor has fallen since the pour started.
        ambience.grit_floor[1] = False
        run_out(ambience)
        self.assertEqual(len(ambience.mounds), 1)
        self.assertGreaterEqual(ambience.mounds[0].bottom, 345)
        ambience.grit_floor[2] = False
        ambience.advance(TERRAIN)
        self.assertEqual(ambience.mounds, [])

    def test_a_bump_shakes_grit_down_right_over_his_hands(self):
        for seed in range(10):
            ambience = self.ambience(seed)
            ambience.shake(250, 1, 1.0, 'bump', TERRAIN)
            over = [trickle for trickle in ambience.trickles
                    if abs(trickle.source.x - 250) <= 14 and trickle.source.top == 127 and trickle.wait <= 2]
            self.assertGreaterEqual(len(over), 3, seed)
            self.assertTrue(all(trickle.shaken for trickle in ambience.trickles))

    def test_a_harder_blow_shakes_more_and_further_off_later(self):
        # One short ceiling, so that no blow opens as many cracks as it may.
        line = tuple(127 if 150 <= x < 350 else -1 for x in range(WIDTH))
        lines = ((-1,) * WIDTH, line, (-1,) * WIDTH)

        def spots(strength, name):
            counts = []
            for seed in range(30):
                ambience = self.ambience(seed, ceilings=lines)
                ambience.shake(250, 1, strength, name, TERRAIN)
                counts.append(len(ambience.trickles))
                for trickle in ambience.trickles:
                    far = abs(trickle.source.x - 250) - 3
                    self.assertGreaterEqual(trickle.wait, int(max(0, far) / ruins_ambience.SHAKE_SPREAD))
            return sum(counts) / len(counts)

        self.assertGreater(spots(0.9, 'slam'), 1.5 * spots(0.35, 'shut'))

    def test_only_a_strong_blow_brings_down_pebbles(self):
        shut = slam = 0
        for seed in range(30):
            ambience = self.ambience(seed)
            ambience.shake(250, 1, ruins_ambience.STRENGTH['shut'], 'shut', TERRAIN)
            shut += len(ambience.pebbles)
            ambience = self.ambience(seed)
            ambience.shake(250, 1, ruins_ambience.STRENGTH['slam'], 'slam', TERRAIN)
            slam += len(ambience.pebbles)
        self.assertEqual(shut, 0)
        self.assertGreater(slam, 20)

    def test_what_shakes_the_ceilings(self):
        ambience = self.ambience()

        def footing(falling, speed=0):
            return Footing(250, 252, 226, True, falling, speed)

        ambience.footing = footing(True, 17)
        self.assertEqual(ambience.hits(footing(False), (), ()), [])
        ambience.footing = footing(True, 27)
        self.assertEqual(ambience.hits(footing(False), (), ()), [(252, 1, 0.75, 'landing')])
        ambience.footing = footing(True, 40)
        self.assertEqual(ambience.hits(footing(False), (), ())[0][2], 1.0)
        thuds = [Thud(100, 120, 226, 226, kind) for kind in (SLAM_PUFF, TILE_PUFF, SHUT_PUFF, STEP_PUFF)]
        self.assertEqual([name for *_, name in ambience.hits(None, thuds, ())], ['slam', 'tile', 'shut'])
        self.assertEqual(ambience.hits(footing(False), (), ((4, 'bump', 1), (5, 'stamp', 1))),
                         [(252, 1, 1.0, 'bump')])

    def test_one_blow_in_a_place_a_tick(self):
        ambience = self.ambience()
        shaken = []
        ambience.shake = lambda x, row, strength, name, terrain: shaken.append(name)
        ambience.footing = Footing(250, 252, 226, True, True, 30)
        ambience.advance(TERRAIN, Footing(250, 252, 226, True, False), (), ((4, 'stamp', 1),))
        self.assertEqual(shaken, ['landing'])

    def test_grit_bounces_off_the_prince_and_is_drawn_over_him(self):
        ambience = self.ambience()
        mask = numpy.zeros((HEIGHT, WIDTH), dtype=bool)
        mask[200:260, 90:111] = True
        ambience.prince_mask = mask
        trickle = ruins_ambience.Trickle(ruins_ambience.Crack(100, 125, GROUND), 0, 0)
        trickle.grains = [ruins_ambience.Grain(198.0, 3.0, 100.0, GRIT_HEAD)]
        ambience.trickles = [trickle]
        ambience.advance_trickles()
        self.assertEqual(trickle.grains, [])
        self.assertEqual(len(ambience.bits), 1)
        bit = ambience.bits[0]
        self.assertEqual(bit.y, 199)
        self.assertLess(bit.dy, 0)
        frame = frame_of(picture((PURPLE, 12)))
        ambience.before_actors = frame.copy()
        shown = ambience.over_actors(frame, (90, 200, 110, 260))
        self.assertEqual(shown.getpixel((100, 199)), ambience.air.inks[GRIT_HEAD])

    def test_his_pixels_are_what_the_actors_changed_within_his_bounds(self):
        ambience = self.ambience()
        before = frame_of(picture((PURPLE, 12)))
        ambience.before_actors = before
        frame = before.copy()
        frame.paste((200, 30, 30, 255), (95, 205, 105, 255))
        frame.paste((200, 30, 30, 255), (300, 205, 310, 255))
        ambience.over_actors(frame, (90, 200, 112, 258))
        ys, xs = numpy.nonzero(ambience.prince_mask)
        self.assertEqual((xs.min(), xs.max(), ys.min(), ys.max()), (95, 104, 205, 254))
        ambience.before_actors = None
        ambience.over_actors(frame, (90, 200, 112, 258))
        self.assertIsNone(ambience.prince_mask)

    def test_a_streak_passing_carries_the_grains_along_its_way(self):
        ambience = self.ambience()
        streak = new_streak(random.Random(1), winding=True)
        streak.pixels = [(x, 150) for x in range(100, 300)]
        streak.turn, streak.shown = 210, 23
        ambience.wind = ruins_ambience.RuinsWind(streaks=[streak])
        # The visible line spans x 196 to 249.
        push_x, push_y = ambience.streak_push(220, 155)
        self.assertAlmostEqual(push_x, ruins_ambience.STREAK_PUSH * (1 - 5 / ruins_ambience.STREAK_REACH))
        self.assertAlmostEqual(push_y, 0)
        self.assertEqual(ambience.streak_push(220, 170), (0.0, 0.0))
        self.assertEqual(ambience.streak_push(150, 155), (0.0, 0.0))

    def test_over_pale_stone_the_grit_is_a_step_darker_and_behind_the_foreground(self):
        luminance = numpy.zeros((HEIGHT, WIDTH), dtype=numpy.uint8)
        luminance[:, 200:] = 200
        covered = numpy.zeros((HEIGHT, WIDTH), dtype=bool)
        covered[:, 400:] = True
        ambience = self.ambience(luminance=luminance, covered=covered)
        frame = frame_of(picture((PURPLE, 12)))
        canvas = frame.load()
        ambience.put_grit(canvas, [(100, 150, GRIT_HEAD), (250, 150, GRIT_HEAD), (450, 150, GRIT_HEAD)])
        inks = ambience.air.inks
        self.assertEqual(frame.getpixel((100, 150)), inks[GRIT_HEAD])
        self.assertEqual(frame.getpixel((250, 150)), inks[ruins_ambience.GRIT_DIM])
        self.assertEqual(frame.getpixel((450, 150))[:3], STONE)

    def test_a_painting_sheds_no_grit(self):
        rgb = picture((PURPLE, 12))
        self.assertEqual(read_room(6, 4, rgb, PALETTE, terrain=TERRAIN, painted=True).grit, ())
        self.assertEqual(read_room(6, 4, rgb, PALETTE, terrain=TERRAIN, painted=True).ceilings, ())


class RendererTests(unittest.TestCase):
    def renderer(self, number, kind):
        from pop2.level_rendering import LevelRenderer

        return LevelRenderer(SimpleNamespace(number=number, kind=kind, start_room=0), preload_room=False)

    def test_the_ruins_have_their_own_ambience_and_the_caves_theirs(self):
        from pop2.cavern_ambience import CavernAmbience

        for number in (3, 4, 5):
            self.assertIs(self.renderer(number, 3).ambience_kind()[1], CavernAmbience)
        for number in (6, 7, 8, 9):
            self.assertIs(self.renderer(number, 4).ambience_kind()[1], RuinsAmbience)
        for number, kind in ((2, 5), (10, 2), (13, 2), (14, 6)):
            self.assertIsNone(self.renderer(number, kind).ambience_kind())

    def test_a_room_is_read_once_and_its_ambience_kept_until_he_leaves(self):
        renderer = self.renderer(6, 4)
        renderer.rooms = {11: 'room 11', 12: 'room 12'}
        reads = []

        def read(number, room, art, terrain, raised=None):
            reads.append((number, room, art))
            return night(number, room)

        with patch('pop2.ruins_ambience.ruins_air', read):
            renderer.advance_ambience(11, None)
            first = renderer.ambience
            renderer.advance_ambience(11, None)
            self.assertIs(renderer.ambience, first)
            self.assertEqual(first.tick, 2)
            renderer.advance_ambience(12, None)
            renderer.advance_ambience(11, None)
        self.assertIsNot(renderer.ambience, first)
        self.assertEqual(renderer.ambience.air.stars, first.air.stars)
        self.assertEqual(reads, [(6, 11, 'room 11'), (6, 12, 'room 12')])
        frame = frame_of(picture((DEEP, 180)))
        self.assertIs(renderer.ambient_layer(frame, 12), frame)

    def test_ruins_wind_is_visible_on_entry_and_runs_across_short_room_visits(self):
        renderer = self.renderer(6, 4)
        renderer.rooms = {4: 'outside', 5: 'inside', 7: 'outside again'}
        outside = replace(night(6, 4), stars=())
        renderer.ambience_air = {4: outside, 5: replace(outside, windy=False), 7: outside}
        scenery = frame_of(picture((DEEP, 180), (PURPLE, 60)))

        renderer.advance_ambience(5, None)
        self.assertIsNone(renderer.ruins_wind)
        with patch('pop2.ruins_ambience.RuinsWind',
                   return_value=ruins_ambience.RuinsWind(random.Random(2))):
            renderer.advance_ambience(4, None)
        wind = renderer.ruins_wind
        self.assertTrue(wind.streaks)
        first = wind.streaks[0]
        age = first.shown
        self.assertNotEqual(renderer.ambient_layer(scenery.copy(), 4).tobytes(), scenery.tobytes())

        renderer.advance_ambience(5, None)
        self.assertFalse(renderer.ambience.streaks)
        self.assertEqual(renderer.ambient_layer(scenery.copy(), 5).tobytes(), scenery.tobytes())
        renderer.advance_ambience(7, None)
        self.assertIs(renderer.ambience.wind, wind)
        self.assertIs(renderer.ambience.streaks[0], first)
        self.assertEqual(first.shown, age + 2)

        starts = 0
        for tick in range(310):
            renderer.advance_ambience(4 if tick % 2 else 7, None)
            starts += any(streak.shown == 1 for streak in wind.streaks)
        self.assertEqual(renderer.ambience.tick, 1)
        self.assertGreaterEqual(starts, 2)
        self.assertIs(renderer.ruins_wind, wind)

    def test_desert_draws_before_the_first_tick_and_reuses_the_wind_on_return(self):
        renderer = self.renderer(9, 4)
        renderer.rooms = dict.fromkeys(DESERT_ROOMS, 'dunes')
        terrain = None
        air = replace(dunes_air(rock=False), stars=())
        scenery = frame_of(picture((DEEP, CREST), (SAND, HEIGHT - CREST)))
        with patch('pop2.ruins_ambience.ruins_air', return_value=air):
            before_first_tick = renderer.ambient_layer(scenery.copy(), 1)
            self.assertNotEqual(before_first_tick.tobytes(), scenery.tobytes())
            wind = renderer.desert_wind
            self.assertEqual(wind.width, len(DESERT_ROOMS) * WIDTH)
            tick = wind.tick
            gust = steady_gust(tick, start=4 * WIDTH)
            wind.desert_gusts = [gust]
            wind.desert_gust_wait = 100
            renderer.advance_ambience(10, terrain)
            renderer.advance_ambience(11, terrain)
            renderer.advance_ambience(10, terrain)
        self.assertIs(renderer.desert_wind, wind)
        self.assertIs(wind.desert_gusts[0], gust)
        self.assertEqual(wind.tick, tick + 3)
        self.assertGreater(len(wind.spray) + len(wind.blown), 0)


@unittest.skipUnless(RUINS_INSTALLED, 'Imported ruins resources required')
class EveryRuinsRoomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pop2.cavern_state import CavernState
        from pop2.level_data import LevelDefinition
        from pop2.level_rendering import LevelRenderer
        from pop2.render_opening import load_resource_file
        from pop2.ruins_ambience import ruins_air
        from pop2.terrain import LevelMap

        cls.rooms = {}
        for number in (6, 7, 8, 9):
            level = LevelDefinition.read(load_resource_file('Prince.rsrc'), number)
            renderer = LevelRenderer(level, preload_room=False)
            world = CavernState()
            world.configure_entry(renderer.cavern_program.get('entry_exit'))
            world.configure_torches(renderer.cavern_program.get('torches', {}))
            world.configure_lava(renderer.cavern_program.get('lava'))
            terrain = LevelMap(level.data)
            for room in renderer.supported_rooms():
                cls.rooms[number, room] = ruins_air(number, room, renderer.enter_room(room, world), terrain)

    def test_the_desert_is_level_nine_by_the_horse_and_its_dunes(self):
        # Menu rooms 2 and 11-15; 16, by the river, is not.
        self.assertEqual({place for place, air in self.rooms.items() if air.desert},
                         {(9, 1), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14)})

    def test_stars_where_the_sky_is_deep_blue_and_over_the_desert(self):
        starry = {place for place, air in self.rooms.items()
                  if any(kind not in HAZE for *_, kind in air.stars) and not air.desert}
        self.assertEqual(starry, {(6, 1), (6, 11), (6, 12), (6, 14), (6, 26), (7, 24), (7, 25), (7, 26), (8, 12)})
        for place, air in self.rooms.items():
            if air.desert:
                self.assertEqual(len(air.stars), DESERT_STARS, place)
                self.assertFalse(any(kind in HAZE for *_, kind in air.stars), place)

    def test_faint_stars_in_the_purple_of_every_room_with_much_sky(self):
        for place, air in self.rooms.items():
            if not air.desert and air.cliff_wind_sky is None and air.sky.mean() > 0.1:
                self.assertTrue(any(kind in HAZE for *_, kind in air.stars), place)

    def test_shooting_stars_in_every_room_with_much_sky_but_the_desert(self):
        rng = random.Random(1)
        for place, air in self.rooms.items():
            if air.cliff_wind_sky is not None:
                self.assertIsNone(shooter_path(air, FAINT, rng), place)
            elif not air.desert and air.sky.mean() > 0.1:
                self.assertIsNotNone(shooter_path(air, FAINT, rng), place)

    def test_the_horizontal_wind_blows_in_open_ruins_outside_the_desert_and_chasm(self):
        windy = {place for place, air in self.rooms.items() if air.windy}
        self.assertEqual(windy, {(6, room) for room in (1, 4, 7, 8, 11, 12, 14, 20, 22, 26)}
                         | {(7, room) for room in (13, 15, 16, 18, 19, 24, 25, 26, 27)}
                         | {(8, 8), (8, 12)} | {(9, room) for room in (0, 3, 4, 5, 7)})

    def test_grit_comes_from_cracks_in_the_undersides_of_stone(self):
        from pop2.caverns import customized_rooms

        for place, air in self.rooms.items():
            if place[1] in customized_rooms(place[0]):
                self.assertEqual((air.grit, air.ceilings), ((), ()), place)
                continue
            self.assertLessEqual(len(air.grit), ruins_ambience.MOST_GRIT, place)
            for crack in air.grit:
                self.assertTrue((air.luminance[crack.top - 6:crack.top, crack.x] >= 72).all(), place)
                self.assertGreaterEqual(crack.bottom - crack.top, ruins_ambience.GRIT_SHORTEST_FALL - 3, place)
                for other in air.grit:
                    if other is not crack:
                        self.assertGreaterEqual(abs(other.x - crack.x), ruins_ambience.GRIT_APART, place)
        # The rooms of the approved clips.
        self.assertTrue(self.rooms[7, 4].grit)
        self.assertTrue(self.rooms[7, 19].grit)
        self.assertGreater(sum(bool(air.grit) for air in self.rooms.values()), 40)

    def test_the_pour_in_level_six_room_thirteen_reaches_the_sloped_ledge(self):
        air = self.rooms[6, 12]
        crack = next(crack for crack in air.grit if crack.x == 368)
        self.assertTrue(air.sky[349, crack.x])
        self.assertGreaterEqual(crack.bottom, 354)
        ambience = RuinsAmbience(12, air, random.Random(17))
        ambience.quiet_wait = 1000
        ambience.start(crack.x, crack.top, 30, 0, True)
        run_out(ambience, terrain=None)
        mound, = ambience.mounds
        self.assertEqual(mound.x, crack.x)
        self.assertFalse(air.sky[mound.bottom, mound.x - 3:mound.x + 6].any())

    def test_grit_in_room_nine_falls_on_when_the_upper_slab_detaches(self):
        from pop2.cavern_state import CavernState
        from pop2.level_data import LevelDefinition
        from pop2.level_rendering import LevelRenderer
        from pop2.render_opening import load_resource_file
        from pop2.terrain import LevelMap

        room, x = 8, 452
        level = LevelDefinition.read(load_resource_file('Prince.rsrc'), 6)
        terrain = LevelMap(level.data)
        terrain.caverns = world = CavernState()
        renderer = LevelRenderer(level, preload_room=False)
        renderer.enter_room(room, world)
        renderer.advance_ambience(room, terrain)
        ambience = renderer.ambience
        ambience.quiet_wait = 1000
        ambience.wind = None
        old = ambience.grit_bottom(x, 5, None)
        self.assertEqual(old, 106)

        # A mix of falling grains, airborne rebound and grit already
        # resting on the slab when its real controller removes it.
        grain = ruins_ambience.Grain(104, 3, x, GRIT_HEAD)
        trickle = ruins_ambience.Trickle(ruins_ambience.Crack(x, 5, old), 0, 0, grains=[grain])
        bit = ruins_ambience.Bit(x, 105, 0.0, 2.0, GRIT_HEAD, old)
        resting = ruins_ambience.GritFleck(x, 105, 0.0, 0.0, 0.0, (GRIT_HEAD,), 10, old, settled=True)
        splash = ruins_ambience.GritFleck(x, 105, 0.0, 2.0, 0.5, (GRIT_HEAD,), 10, old)
        pebble = ruins_ambience.Pebble(x, 105, old, 0, vy=0.0, bounced=True, rest=12)
        ambience.trickles = [trickle]
        ambience.bits = [bit]
        ambience.flecks = [resting, splash]
        ambience.pebbles = [pebble]

        world.loose.trigger(terrain.tile(room, 8, 0), force=True)
        world.loose.advance_tiles(terrain)
        self.assertEqual(terrain.tile(room, 8, 0).kind, 0)
        renderer.enter_room(room, world)
        for _ in range(4):
            renderer.advance_ambience(room, terrain)
        self.assertIs(renderer.ambience, ambience)
        self.assertEqual(ambience.grit_bottom(x, 105, None), 226)
        for particle, active in ((grain, trickle.grains), (bit, ambience.bits), (resting, ambience.flecks),
                                 (splash, ambience.flecks), (pebble, ambience.pebbles)):
            with self.subTest(particle=type(particle).__name__):
                self.assertIn(particle, active)
                self.assertGreater(particle.y, old)

    def test_pours_across_the_ruins_only_heap_on_visible_ground(self):
        for place, air in self.rooms.items():
            for crack in air.grit:
                ambience = RuinsAmbience(place[1], air, random.Random(17))
                ambience.quiet_wait = 1000
                ambience.start(crack.x, crack.top, 30, 0, True)
                run_out(ambience, terrain=None)
                for mound in ambience.mounds:
                    self.assertFalse(air.sky[mound.bottom, mound.x - 3:mound.x + 6].any(), (place, mound))

    def test_level_six_room_twelve_has_the_sky_that_was_approved(self):
        stars = [star for star in self.rooms[6, 11].stars if star[2] not in HAZE]
        self.assertEqual(len(stars), 19)
        self.assertEqual(sum(kind in WARM for *_, kind in stars), 4)
        self.assertEqual(stars, list(self.rooms[6, 11].stars[:19]))

    def test_every_star_is_on_clear_sky(self):
        for place, air in self.rooms.items():
            clear = DESERT_STAR_CLEAR if air.desert else STAR_CLEAR
            for x, y, _kind in air.stars:
                self.assertTrue(air.sky[y - clear:y + clear + 1, x - clear:x + clear + 1].all(), (place, x, y))

    def test_the_sand_blows_in_the_desert_of_the_dunes(self):
        # The strip continues to the horse, with the exposed ground around the statue.
        self.assertEqual({place for place, air in self.rooms.items() if air.dunes is not None},
                         {(9, room) for room in DESERT_ROOMS})
        for room in (10, 11, 12, 13, 14):
            dunes = self.rooms[9, room].dunes
            self.assertTrue(194 <= dunes.crest.min() and dunes.crest.max() <= 218, room)
            self.assertEqual(set(dunes.ground_top), {238}, room)
            self.assertTrue(20 <= len(dunes.rocks) <= 28, room)
        horse = self.rooms[9, 1].dunes
        self.assertTrue((horse.crest[:85] > 0).all())
        self.assertFalse(horse.sand[:200].any())
        self.assertFalse(horse.sand[:310, 268:370].any())
        self.assertTrue(horse.open_sand[280:330, :80].any())

    def test_chasm_sand_falls_from_each_ledge_and_a_little_rises_with_the_wind(self):
        air = self.rooms[9, ruins_ambience.CHASM_ROOM]
        self.assertTrue(air.chasm)
        self.assertFalse(air.windy)
        sand = air.dunes.sand
        self.assertTrue(sand[225:248, :125].any())
        self.assertTrue(sand[230:285, 450:].any())
        self.assertFalse(sand[:, 136:345].any())
        self.assertFalse((air.dunes.crest >= 0).any())

        first = next(ruins_ambience.chasm_fall_pixels(8, sand))
        later = next(ruins_ambience.chasm_fall_pixels(18, sand))
        self.assertGreater(later[1], first[1])
        self.assertLess(later[0], 165)
        falling = {(x, y) for tick in range(90) for x, y, _ in ruins_ambience.chasm_fall_pixels(tick, sand)}
        for x_tip, y_tip in ((132, 241), (77, 284), (40, 325)):
            self.assertTrue(any(x_tip <= x < x_tip + 20 and y_tip + 10 <= y < y_tip + 35
                                for x, y in falling), (x_tip, y_tip))

        low_sand = next(ruins_ambience.chasm_rising_sand_pixels(8))
        high_sand = next(ruins_ambience.chasm_rising_sand_pixels(20))
        self.assertGreater(low_sand[1], high_sand[1])
        self.assertLessEqual(abs(low_sand[0] - high_sand[0]), 2)
        for tick in range(90):
            self.assertLessEqual(len(list(ruins_ambience.chasm_rising_sand_pixels(tick))), 7)

    def test_chasm_updraft_rises_as_a_faint_line_before_curling(self):
        period = ruins_ambience.CHASM_UPDRAFT_PERIOD
        phase = ruins_ambience.CHASM_UPDRAFT_PHASE
        self.assertEqual(period, 52)
        lower = list(ruins_ambience.chasm_updraft_pixels(period - phase + 14))
        higher = list(ruins_ambience.chasm_updraft_pixels(period - phase + 27))
        self.assertLess(max(y for _, y, _ in higher), min(y for _, y, _ in lower))
        for frame in (lower, higher):
            self.assertGreaterEqual(len(frame), 34)
            self.assertLessEqual(len(frame), 36)
            self.assertLessEqual(max(x for x, _, _ in frame) - min(x for x, _, _ in frame), 6)
            peak = max(max(amount) for _, _, amount in frame)
            self.assertGreaterEqual(peak, 31)
            self.assertLessEqual(peak, 34)
            self.assertLess(max(frame[0][2]), peak)
            self.assertLess(max(frame[-1][2]), peak)
        for cycle, (path, turn) in enumerate(ruins_ambience.CHASM_UPDRAFT_PATHS, start=3):
            start = cycle * period - phase
            curl_pixels = set(path[turn:])
            overlap_age = period + 2
            drift = overlap_age - ruins_ambience.CHASM_STREAK_STYLE.glide_ticks
            next_glide = list(ruins_ambience.chasm_updraft_pixels(start + overlap_age))
            self.assertTrue(any((x, y + drift) in curl_pixels for x, y, _ in next_glide))
            self.assertTrue(any((x, y + drift) not in curl_pixels for x, y, _ in next_glide))
            self.assertGreater(turn, 90)
            run_steps = list(zip(path[:turn], path[1:turn]))
            self.assertTrue(all(first[1] >= second[1] for first, second in run_steps))
            self.assertTrue({-1, 1} <= {second[0] - first[0] for first, second in run_steps})
            curl = path[turn:]
            self.assertGreater(max(x for x, _ in curl) - min(x for x, _ in curl), 3)
            self.assertTrue(any(first[1] < second[1] for first, second in zip(curl, curl[1:])))

    def test_chasm_wind_crosses_the_left_bank_and_curls_over_the_gap(self):
        period = ruins_ambience.CHASM_CROSSWIND_PERIOD
        phase = ruins_ambience.CHASM_CROSSWIND_PHASE
        self.assertEqual(period, 63)
        early = list(ruins_ambience.chasm_crosswind_pixels(period - phase + 14))
        late = list(ruins_ambience.chasm_crosswind_pixels(period - phase + 27))
        self.assertLess(max(x for x, _, _ in early), min(x for x, _, _ in late))
        for frame in (early, late):
            self.assertGreaterEqual(len(frame), 34)
            self.assertLessEqual(len(frame), 36)
            self.assertTrue(all(210 <= y <= 228 for _, y, _ in frame))
        for cycle, (path, turn) in enumerate(ruins_ambience.CHASM_CROSSWIND_PATHS, start=3):
            run_steps = list(zip(path[:turn], path[1:turn]))
            self.assertTrue(all(first[0] <= second[0] for first, second in run_steps))
            self.assertTrue({-1, 1} <= {second[1] - first[1] for first, second in run_steps})
            coil = path[turn:]
            self.assertGreater(coil[0][0], 136)
            self.assertTrue(any(first[0] > second[0] for first, second in zip(coil, coil[1:])))
            end = (cycle + 1) * period - phase - 1
            self.assertEqual(list(ruins_ambience.chasm_crosswind_pixels(end)), [])

    def test_each_chasm_wind_line_moves_downwind_while_curling_without_dimming(self):
        sides = (
            (ruins_ambience.CHASM_UPDRAFT_PATHS, ruins_ambience.CHASM_UPDRAFT_PERIOD,
             ruins_ambience.CHASM_UPDRAFT_PHASE, ruins_ambience.chasm_updraft_pixels, (0, -1)),
            (ruins_ambience.CHASM_CROSSWIND_PATHS, ruins_ambience.CHASM_CROSSWIND_PERIOD,
             ruins_ambience.CHASM_CROSSWIND_PHASE, ruins_ambience.chasm_crosswind_pixels, (1, 0)),
        )
        for paths, period, phase, pixels, (dx, dy) in sides:
            for cycle, (path, turn) in enumerate(paths, start=3):
                start = cycle * period - phase + ruins_ambience.CHASM_STREAK_STYLE.glide_ticks
                coil = set(path[turn:])
                width = max(x for x, _ in coil) - min(x for x, _ in coil)
                height = max(y for _, y in coil) - min(y for _, y in coil)
                self.assertIn(max(width, height), (4, 5))
                # Track the shape in the frame of the moving wisp.
                frames = [
                    [(x - dx * offset, y - dy * offset, rgb) for x, y, rgb in pixels(start + offset)]
                    for offset in range(23)
                ]
                forming = frames[:16]
                winding = [[pixel for pixel in frame if pixel[:2] in coil] for frame in frames[16:]]
                counts = list(map(len, forming + winding))
                self.assertTrue(all(first > second for first, second in zip(counts, counts[1:])))
                self.assertTrue(any((x, y) not in coil for x, y, _ in forming[12]))
                self.assertTrue({(x, y) for x, y, _ in forming[-1]} <= coil)
                # The coiled line gets shorter every tick while each surviving pixel keeps its colour.
                joined = [forming[-1], *winding]
                for before, after in zip(joined, joined[1:]):
                    self.assertEqual(after, before[len(before) - len(after):])
                self.assertEqual([pixel[:2] for pixel in winding[-2]], [path[-1]])
                self.assertGreaterEqual(max(winding[-2][0][2]), 37)
                self.assertFalse(winding[-1])

    def test_no_random_shooting_star_over_the_desert(self):
        rng = random.Random(0)
        for place, air in self.rooms.items():
            if air.desert:
                for kind in SHOOTERS:
                    self.assertIsNone(shooter_path(air, kind, rng), place)

    def test_the_horse_arrival_star_has_a_white_head_and_lingering_sparks(self):
        air = self.rooms[9, ruins_ambience.HORSE_ROOM]
        shooter = ruins_ambience.horse_shooting_star()
        distance = int(shooter.kind.speed * (shooter.kind.ticks - 1))
        self.assertGreater(shooter.x - shooter.at(distance)[0], 230)
        self.assertLessEqual(shooter.kind.ticks, 9)
        line = {shooter.at(step) for step in range(distance + 1)}
        self.assertTrue(all(air.in_sky(x, y) and not air.is_covered(x, y) for x, y in line))

        glow_pixels = []
        for age in range(shooter.kind.ticks):
            shooter.age = age
            travelled = age * shooter.kind.speed
            head = shooter.at(travelled)
            drawn = {(x, y): colour for x, y, colour in shooter_pixels(shooter)}
            self.assertEqual(drawn[head], shooter.kind.head)
            if age > 0:
                self.assertEqual(drawn[shooter.at(travelled - 3)], shooter.kind.head)
            glow_pixels.append((head[0], head[1] - 1) in drawn)
        self.assertFalse(glow_pixels[0])
        self.assertTrue(glow_pixels[3])

        line_counts = []
        for age in (10, 15, 20, 22):
            shooter.age = age
            pixels = {(x, y) for x, y, _ in shooter_pixels(shooter)}
            line_counts.append(len(pixels & line))
        self.assertGreater(line_counts[0], line_counts[1])
        self.assertGreater(line_counts[1], line_counts[2])
        self.assertGreater(line_counts[2], 0)
        self.assertEqual(line_counts[3], 0)

        max_depths = []
        for age in (22, 48):
            shooter.age = age
            self.assertLess(age, shooter.kind.lasts)
            pixels = {(x, y) for x, y, _ in shooter_pixels(shooter)}
            self.assertGreaterEqual(sum(air.in_sky(x, y) for x, y in pixels), 6)
            depths = [y - (shooter.y + (x - shooter.x) * shooter.dy / shooter.dx) for x, y in pixels]
            max_depths.append(max(depths))
        self.assertLessEqual(max_depths[0], 4)
        self.assertGreater(max_depths[1], max_depths[0])
        self.assertLessEqual(max_depths[1], 9)

        rgb = numpy.where(air.sky[..., None], DEEP, STONE).astype(numpy.uint8)
        frame = frame_of(rgb)
        ambience = RuinsAmbience(ruins_ambience.HORSE_ROOM, replace(air, stars=()))
        ambience.shooter = shooter
        ambience.draw(frame)
        self.assertTrue(numpy.array_equal(numpy.asarray(frame)[~air.sky, :3], rgb[~air.sky]))


@unittest.skipUnless(RUINS_INSTALLED, 'Imported ruins resources required')
class RealSceneTests(unittest.TestCase):
    """The same inputs with the toggle off and on, in the hidden real scene."""

    def test_the_opening_cliff_draws_sand_and_stars_before_the_wind_fades_in(self):
        from tools.audit_temple_routes import Harness

        harness = Harness(6, peaceful=True, draw=True, god=True)
        try:
            scene = harness.scene
            scene.cave_ambience_enabled = True
            self.assertEqual(scene.room_id, 26)
            with patch('pop2.ruins_ambience.RuinsWind',
                       return_value=ruins_ambience.RuinsWind(random.Random(2))):
                scene.render()
            ambience = scene.level_renderer.ambience
            scenery = Image.alpha_composite(scene.background, scene.foreground)
            first = scenery.copy()
            ambience.draw_wind(first.load())
            self.assertEqual(first.tobytes(), scenery.tobytes())
            harness.tick()
            sky = ambience.air.cliff_wind_sky
            frame = scenery.copy()
            ambience.draw_wind(frame.load())
            changed = (numpy.asarray(frame) != numpy.asarray(scenery)).any(axis=2)
            self.assertGreaterEqual(int(changed.sum()), 12)
            self.assertFalse(changed[:, :250].any())
            self.assertFalse(changed[~sky].any())

            full = ambience.draw(scenery.copy())
            stars_and_sand = (numpy.asarray(full) != numpy.asarray(frame)).any(axis=2)
            stars = ambience.air.stars
            self.assertGreaterEqual(len(stars), 6)
            self.assertLessEqual(len(stars), 12)
            self.assertTrue(all(stars_and_sand[y, x] and y < 114 for x, y, _ in stars))
            self.assertFalse(stars_and_sand[114:265].any())

            grains = stars_and_sand[265:]
            self.assertTrue(stars_and_sand[310:342, 156:215].any())
            self.assertTrue(stars_and_sand[279:319, 387:].any())
            self.assertTrue(stars_and_sand[319:, 375:387].any())
            self.assertLessEqual(int(grains.sum()), 30)
            self.assertFalse(grains[:, :150].any())

            early_gain = (numpy.asarray(frame, dtype=int) - numpy.asarray(scenery)).sum()
            harness.tick(ruins_ambience.CLIFF_WIND_FADE_TICKS - 1)
            full_wind = scenery.copy()
            ambience.draw_wind(full_wind.load())
            self.assertGreater((numpy.asarray(full_wind, dtype=int) - numpy.asarray(scenery)).sum(),
                               early_gain * 3)
        finally:
            harness.close()

    def play(self, enabled):
        from tools.audit_temple_routes import Harness

        random.seed(61)
        harness = Harness(6, peaceful=False, draw=True)
        try:
            scene = harness.scene
            scene.audio = None
            scene.jump_to_room(12, row=1, facing=1)
            scene.cave_ambience_enabled = enabled
            harness.tick(60)
            state = scene.sequence_state
            return dict(random=random.getstate(), combat=scene.combat.rng.getstate(),
                        room=scene.room_id, x=scene.player_x, action=scene.action,
                        sequence=state.sequence_id, y=state.current_y,
                        scenery=scene.level_renderer.cavern_scenery.tobytes(),
                        drawn=scene.level_renderer.ambience,
                        view=scene.screenshot_viewport.convert('RGB'))
        finally:
            harness.close()

    def test_the_toggle_changes_no_game_state(self):
        off, on = self.play(False), self.play(True)
        self.assertIsNone(off.pop('drawn'))
        self.assertIsInstance(on.pop('drawn'), RuinsAmbience)
        before, after = numpy.asarray(off.pop('view')), numpy.asarray(on.pop('view'))
        self.assertEqual(off, on)
        self.assertEqual(on['room'], 12)
        changed = (before != after).any(axis=2)
        self.assertTrue(changed.any())
        self.assertFalse(changed[365:].any())

    def bump(self, enabled):
        from tools.audit_temple_routes import Harness, press

        random.seed(77)
        harness = Harness(7, peaceful=True, draw=True)
        try:
            scene = harness.scene
            scene.audio = None
            scene.cave_ambience_enabled = enabled
            scene.jump_to_room(4, row=1, x=250, facing=1)
            harness.tick(24)
            press(harness, 'up', True)
            harness.tick(3)
            press(harness, 'up', False)
            shaken = 0
            for _ in range(40):
                harness.tick()
                ambience = scene.level_renderer.ambience
                if ambience is not None:
                    shaken = max(shaken, sum(trickle.shaken for trickle in ambience.trickles))
            state = scene.sequence_state
            return dict(random=random.getstate(), room=scene.room_id, x=scene.player_x, action=scene.action,
                        sequence=state.sequence_id, y=state.current_y, shaken=shaken,
                        scenery=scene.level_renderer.cavern_scenery.tobytes())
        finally:
            harness.close()

    def test_jumping_up_against_the_ceiling_shakes_grit_down_and_nothing_else(self):
        off, on = self.bump(False), self.bump(True)
        self.assertEqual(off.pop('shaken'), 0)
        self.assertGreaterEqual(on.pop('shaken'), 3)
        self.assertEqual(off, on)

    def run_along(self, enabled):
        from tools.audit_temple_routes import Harness, press

        random.seed(71)
        harness = Harness(7, peaceful=True, draw=True)
        try:
            scene = harness.scene
            scene.audio = None
            scene.cave_ambience_enabled = enabled
            scene.jump_to_room(4, row=1, x=250, facing=1)
            harness.tick(12)
            press(harness, 'R', True)
            puffs = 0
            for _ in range(14):
                harness.tick()
                ambience = scene.level_renderer.ambience
                if ambience is not None:
                    puffs += sum(cloud.age.max() == 1 for cloud in ambience.clouds)
            press(harness, 'R', False)
            harness.tick(12)
            state = scene.sequence_state
            return dict(random=random.getstate(), room=scene.room_id, x=scene.player_x, action=scene.action,
                        sequence=state.sequence_id, y=state.current_y, puffs=puffs)
        finally:
            harness.close()

    def test_his_steps_raise_puffs_and_change_no_game_state(self):
        off, on = self.run_along(False), self.run_along(True)
        self.assertEqual(off.pop('puffs'), 0)
        self.assertGreaterEqual(on.pop('puffs'), 2)
        self.assertEqual(off, on)
        self.assertGreater(on['x'], 300)

    def walk_the_desert(self, enabled):
        from tools.audit_temple_routes import Harness, press

        random.seed(83)
        harness = Harness(9, peaceful=True, draw=True)
        try:
            scene = harness.scene
            scene.audio = None
            scene.cave_ambience_enabled = enabled
            scene.jump_to_room(11, row=2, facing=1)
            harness.tick(12)
            wind = scene.level_renderer.desert_wind
            if wind is not None:
                wind.desert_gust_wait = wind.devil_wait = 1
            press(harness, 'R', True)
            harness.tick(6)
            press(harness, 'R', False)
            harness.tick(30)
            state = scene.sequence_state
            return dict(random=random.getstate(), room=scene.room_id, x=scene.player_x, action=scene.action,
                        sequence=state.sequence_id, y=state.current_y,
                        sand=None if wind is None else (len(wind.blown) + len(wind.spray), bool(wind.devils)))
        finally:
            harness.close()

    def test_the_desert_s_sand_changes_no_game_state(self):
        off, on = self.walk_the_desert(False), self.walk_the_desert(True)
        self.assertIsNone(off.pop('sand'))
        grains, devil = on.pop('sand')
        self.assertGreater(grains, 0)
        self.assertTrue(devil)
        self.assertEqual(off, on)
        self.assertEqual(on['room'], 11)

    def test_running_through_the_desert_shows_sand_on_the_first_tick_in_each_room(self):
        from tools.audit_temple_routes import Harness, press

        def seeded_ambience(room, air):
            return RuinsAmbience(room, air, random.Random(90 + room))

        with patch('pop2.level_rendering.LevelRenderer.ambience_kind',
                   return_value=(ruins_ambience.ruins_air, seeded_ambience)):
            harness = Harness(9, peaceful=True, draw=True, god=True)
            try:
                scene = harness.scene
                scene.audio = None
                scene.cave_ambience_enabled = True
                scene.jump_to_room(ruins_ambience.CHASM_ROOM, row=2, x=435, facing=1)
                press(harness, 'R', True)
                visited = []
                wind = scene.level_renderer.desert_wind
                self.assertIsNotNone(wind)
                self.assertEqual(wind.devil_room_count, 6)

                def changed_sand():
                    room = scene.room_id
                    renderer = scene.level_renderer
                    self.assertIs(renderer.desert_wind, wind)
                    scenery = Image.alpha_composite(scene.background, scene.foreground)
                    with_sand = scenery.copy()
                    wind.put_sand(with_sand.load(), renderer.ambience_air[room], DESERT_ROOMS.index(room) * WIDTH)
                    return (numpy.asarray(with_sand) != numpy.asarray(scenery)).any(axis=2)

                for _ in range(260):
                    harness.tick()
                    if not visited or scene.room_id != visited[-1]:
                        visited.append(scene.room_id)
                        changed = changed_sand()
                        self.assertGreaterEqual(numpy.count_nonzero(changed), 12, scene.room_id)
                        if scene.room_id == 1:
                            self.assertFalse(changed[:310, 268:370].any())
                            break
                self.assertEqual(visited, list(DESERT_ROOMS))

                entered_horse = wind.tick
                press(harness, 'R', False)
                press(harness, 'L', True)
                for elapsed in range(1, 46):
                    harness.tick()
                    if scene.room_id == 10:
                        break
                self.assertEqual(scene.room_id, 10)
                self.assertEqual(wind.tick, entered_horse + elapsed)
                self.assertGreaterEqual(numpy.count_nonzero(changed_sand()), 12)
            finally:
                harness.close()

    def test_the_horse_room_shows_the_big_star_once_after_a_second_inside(self):
        from tools.audit_temple_routes import Harness, press

        horse = ruins_ambience.HORSE_ROOM
        harness = Harness(9, peaceful=True, draw=True, god=True)
        try:
            scene = harness.scene
            scene.audio = None
            scene.cave_ambience_enabled = True
            scene.jump_to_room(7, row=2, x=112, facing=0)
            renderer = scene.level_renderer

            def run_to(room, direction, opposite):
                press(harness, opposite, False)
                press(harness, direction, True)
                for _ in range(45):
                    harness.tick()
                    if scene.room_id == room:
                        return
                self.fail(f'Prince did not reach room {room}')

            run_to(horse, 'L', 'R')
            self.assertIsNone(renderer.ambience.shooter)
            self.assertFalse(renderer.horse_star_seen)
            scene.jump_to_room(7, row=2, x=112, facing=0)
            harness.tick()
            self.assertIsNone(renderer.ambience.shooter)
            self.assertFalse(renderer.horse_star_seen)

            run_to(horse, 'L', 'R')
            press(harness, 'L', False)
            self.assertIsNone(renderer.ambience.shooter)
            for _ in range(11):
                harness.tick()
                self.assertEqual(scene.room_id, horse)
                self.assertIsNone(renderer.ambience.shooter)
            harness.tick()
            star = renderer.ambience.shooter
            self.assertIsNotNone(star)
            self.assertIs(star.kind, ruins_ambience.HORSE_STAR)
            self.assertEqual(star.age, 0)
            run_to(7, 'R', 'L')
            self.assertIsNone(renderer.ambience.shooter)
            run_to(horse, 'L', 'R')
            press(harness, 'L', False)
            harness.tick(12)
            self.assertEqual(scene.room_id, horse)
            self.assertIsNone(renderer.ambience.shooter)
        finally:
            harness.close()


class SourceTests(unittest.TestCase):
    def test_the_module_reads_no_game_state(self):
        source = Path('pop2/ruins_ambience.py').read_text(encoding='utf-8')
        self.assertNotIn('cavern_state', source)
        self.assertNotIn('random.random(', source)
        self.assertNotIn('save_game', source)


if __name__ == '__main__':
    unittest.main()
