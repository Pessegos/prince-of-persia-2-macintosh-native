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

from pop2.cavern_ambience import SHUT_PUFF, SLAM_PUFF, STEP_PUFF, TILE_PUFF, Footing, Thud
from pop2.paths import ASSET_DIR
from pop2 import ruins_ambience
from pop2.ruins_ambience import (
    BODY_PALER, BRIGHT, CURL_RADIUS, CURL_RISE, CURL_SPEED, DESERT_STAR_APART, DESERT_STAR_CLEAR, DESERT_STARS,
    DIM, DIP_TICKS, FAINT, FIREBALL, FIRST_SHOOTER, GOLD_BRIGHT, GRAZER, GRIT_HEAD, GUST_TICKS, HEIGHT, MID,
    NORMAL, ROSE_BRIGHT, ROSE_MID, SECOND_STREAK_BELOW, SHOOTERS, STAR_APART, STAR_CLEAR, STARS_PER_SKY,
    STREAK_SPEED, TICKS_BETWEEN_GUSTS, TICKS_BETWEEN_SHOOTERS, WIDTH, RuinsAmbience, Shooter, blueness, new_streak,
    paler, read_room, ribbon, shooter_path, shooter_pixels, sky_mask, streak_pixels,
)

RUINS_INSTALLED = (ASSET_DIR / 'ruins_level6.json').is_file()

DEEP = (16, 0, 120)
MIDDLE = (36, 0, 110)
PURPLE = (70, 0, 100)
STONE = (96, 92, 104)
SAND = (166, 120, 104)
WARM = (ROSE_MID, ROSE_BRIGHT, GOLD_BRIGHT)
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

    def test_more_where_the_sky_is_bluest_and_none_by_the_horizon(self):
        deep = middle = 0
        for room in range(16):
            for _x, y, _kind in night(6, room, (DEEP, 90), (MIDDLE, 90), (PURPLE, 80)).stars:
                self.assertLess(y, 180)
                deep += y < 90
                middle += y >= 90
        self.assertGreater(deep, 2 * middle)
        self.assertGreater(middle, 0)

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

    def test_they_are_rare_and_one_at_a_time(self):
        ambience = self.ambience(5)
        starts, previous = [], None
        for tick in range(12 * 60 * 30):
            ambience.advance()
            if ambience.shooter is not None and ambience.shooter is not previous:
                starts.append(tick)
            previous = ambience.shooter
        # About two a minute in a room the Prince stays in.
        self.assertGreater(len(starts), 40)
        self.assertLess(len(starts), 70)
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

    def test_its_flight_stays_over_the_deep_blue(self):
        air = night(6, 11, (DEEP, 100), (PURPLE, 100))
        rng = random.Random(2)
        for kind in SHOOTERS * 30:
            x, y, dx, dy = shooter_path(air, kind, rng)
            travel = kind.speed * kind.ticks
            for share in (0, 0.5, 1):
                self.assertLess(y + dy * travel * share, 100)
            self.assertGreater(dy, 0)
            self.assertLessEqual(math.degrees(math.asin(dy)), kind.angle[1])

    def test_no_shooting_star_without_deep_blue(self):
        ambience = self.ambience(4, (PURPLE, 200))
        for _ in range(4000):
            ambience.advance()
            self.assertIsNone(ambience.shooter)

    def test_the_tail_shortens_as_it_burns_out(self):
        # The fireball's trail stays behind it as it goes (below).
        for kind in (FAINT, NORMAL, GRAZER):
            first = len(list(shooter_pixels(Shooter(kind, 100, 40, 0.9, 0.3, 0))))
            last = len(list(shooter_pixels(Shooter(kind, 100, 40, 0.9, 0.3, kind.ticks - 1))))
            self.assertGreater(first, last, kind.name)

    def test_only_the_fireball_bursts_and_leaves_its_trail(self):
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
    def busy(self):
        ambience = RuinsAmbience(11, night(6, 11, (DEEP, 150), (PURPLE, 60)), random.Random(8))
        for _ in range(200):
            ambience.advance()
        ambience.twinkles[0] = [0, 2]
        ambience.shooter = Shooter(FIREBALL, 120, 30, math.cos(0.3), math.sin(0.3), 4)
        return ambience

    def test_only_the_sky_still_showing_is_drawn(self):
        ambience = self.busy()
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
        ambience = self.busy()
        ambience.air = replace(ambience.air, inks=read_room(6, 11, picture(), palette).inks)
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

    def test_its_pixels_are_a_clean_line(self):
        for seed in range(20):
            pixels, _ = ribbon(20, 150, random.Random(seed))
            for a, b in zip(pixels, pixels[1:]):
                self.assertLessEqual(max(abs(a[0] - b[0]), abs(a[1] - b[1])), 1)
                self.assertNotEqual(a, b)
            for a, b in zip(pixels, pixels[2:]):
                self.assertFalse(abs(a[0] - b[0]) == 1 and abs(a[1] - b[1]) == 1, seed)

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

    def test_only_a_room_open_to_the_sky_is_windy_and_never_the_desert(self):
        self.assertTrue(night(6, 4, (PURPLE, 30)).windy)
        self.assertFalse(night(6, 4, (PURPLE, 12)).windy)
        self.assertFalse(read_room(9, 11, picture((PURPLE, 70), (SAND, 200)), PALETTE).windy)
        ambience = RuinsAmbience(4, night(6, 4, (PURPLE, 12)), random.Random(1))
        for _ in range(1000):
            ambience.advance()
            self.assertEqual(ambience.streaks, [])

    def test_a_gust_sends_one_or_two_streaks_the_second_below_the_first(self):
        ambience = RuinsAmbience(4, replace(night(6, 4), stars=()), random.Random(2))
        gusts = []
        for tick in range(6000):
            before = list(ambience.streaks)
            ambience.blow()
            new = [streak for streak in ambience.streaks if streak not in before]
            if new:
                gusts.append((tick, new))
            ambience.advance_streaks()
        self.assertGreater(len(gusts), 25)
        self.assertEqual({len(new) for _, new in gusts}, {1, 2})
        for _, new in gusts:
            if len(new) == 2:
                self.assertGreaterEqual(new[1].y - new[0].y, SECOND_STREAK_BELOW[0])
                self.assertLessEqual(new[1].y - new[0].y, SECOND_STREAK_BELOW[1])
        gaps = [b - a for (a, _), (b, _) in zip(gusts, gusts[1:])]
        self.assertGreaterEqual(min(gaps), GUST_TICKS + TICKS_BETWEEN_GUSTS[0])
        self.assertLessEqual(max(gaps), GUST_TICKS + TICKS_BETWEEN_GUSTS[1] + 1)

    def test_it_is_paler_than_what_it_crosses_and_behind_the_foreground(self):
        rgb = picture((DEEP, 150), (PURPLE, 60))
        covered = numpy.zeros((HEIGHT, WIDTH), dtype=bool)
        covered[:, 180:200] = True
        air = replace(read_room(6, 11, rgb, PALETTE, covered), stars=())
        ambience = RuinsAmbience(11, air, random.Random(3))
        streak = new_streak(random.Random(8))
        streak.pixels = [(x, 100 + (x % 7 == 0)) for x in range(80, 300)]
        streak.curl, streak.length, streak.head, streak.shown = (400, 410), 60, 140, 10
        ambience.streaks = [streak]
        frame = frame_of(rgb)
        ambience.draw(frame)
        after = numpy.asarray(frame)[..., :3].astype(int)
        changed = (after != rgb).any(axis=2)
        self.assertEqual(int(changed.sum()), 60 - 20)
        self.assertFalse(changed[covered].any())
        self.assertTrue((after[changed].sum(axis=1) > rgb[changed].astype(int).sum(axis=1)).all())
        shown = {tuple(value) for value in after[changed]}
        self.assertLessEqual(shown, {colour[:3] for colour in PALETTE.values()})

    def test_paler_is_never_the_colour_behind(self):
        palette = numpy.array(sorted({colour[:3] for colour in PALETTE.values()}))
        for behind in (DEEP, PURPLE, STONE, (84, 86, 140)):
            for amount in ((1, 1, 1), (17, 17, 21), BODY_PALER):
                colour = paler(behind, amount, palette)
                self.assertNotEqual(colour, behind)
                self.assertGreater(sum(colour), sum(behind))


class Floor:
    def __init__(self, kind):
        self.kind = kind


class FloorBelow:
    """A level map with a floor along the bottom row only."""

    def tile(self, room, column, row):
        return Floor(1 if row == 2 else 0)


TERRAIN = FloorBelow()
GROUND = 346


def grit_air(**changes):
    """A dark room under three ceilings, with two cracks."""
    lines = tuple(tuple(c * 120 + 7 if 20 <= x < 490 else -1 for x in range(WIDTH)) for c in range(3))
    air = replace(night(6, 4, (PURPLE, 12)), stars=(),
                  grit=(ruins_ambience.Crack(100, 130, GROUND), ruins_ambience.Crack(300, 130, GROUND)), ceilings=lines)
    return replace(air, **changes)


def run_out(ambience, ticks=400):
    for _ in range(ticks):
        ambience.advance(TERRAIN)
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
        for _ in range(12 * 200):
            ambience.advance(TERRAIN)
            seen.extend(trickle for trickle in ambience.trickles if all(trickle is not other for other in seen))
        self.assertGreater(len(seen), 40)
        self.assertLess(len(seen), 100)
        self.assertAlmostEqual(sum(trickle.pour for trickle in seen) / len(seen), ruins_ambience.POUR_CHANCE,
                               delta=0.12)
        self.assertEqual({trickle.source.x for trickle in seen}, {100, 300})

    def test_a_pour_falls_straight_down_from_its_crack(self):
        # It used to sway a pixel aside, and to be two pixels wide under the crack.
        for seed in range(6):
            ambience = self.ambience(seed)
            ambience.start(100, 130, 26, 0, True, TERRAIN)
            thread_at_crack = False
            for _ in range(200):
                ambience.advance(TERRAIN)
                # Not the bits that come away from the crack first, or kick up on landing.
                flecks, ambience.flecks = ambience.flecks, []
                pixels = list(ambience.grit_pixels())
                ambience.flecks = flecks
                for x, y, _shade in pixels:
                    if 130 <= y < GROUND - 10:
                        self.assertEqual(x, 100, (seed, y))
                    thread_at_crack |= (x, y) == (100, 130)
                if not ambience.trickles:
                    break
            self.assertTrue(thread_at_crack)

    def test_one_trickle_at_a_crack(self):
        ambience = self.ambience()
        ambience.start(100, 130, 20, 0, True, TERRAIN)
        ambience.start(101, 130, 20, 0, True, TERRAIN)
        ambience.start(102, 130, 4, 0, False, TERRAIN)
        self.assertEqual(len(ambience.trickles), 1)
        ambience.start(300, 130, 4, 0, False, TERRAIN)
        ambience.start(301, 130, 4, 0, False, TERRAIN)
        self.assertEqual(len(ambience.trickles), 3)
        ambience.start(299, 130, 20, 0, True, TERRAIN)
        self.assertEqual(len(ambience.trickles), 3)

    def test_the_rhythm_picks_a_crack_that_is_free(self):
        ambience = self.ambience()
        ambience.start(100, 130, 20, 0, True, TERRAIN)
        for _ in range(10):
            ambience.quiet_wait = 1
            ambience.quiet_trickle(TERRAIN)
        self.assertEqual({trickle.source.x for trickle in ambience.trickles[1:]}, {300})

    def test_a_pour_heaps_a_small_mound_that_wears_away(self):
        ambience = self.ambience(3)
        ambience.start(100, 130, 26, 0, True, TERRAIN)
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
            trickle = ruins_ambience.Trickle(ruins_ambience.Crack(100, 130, GROUND), 0, 1)
            ambience.release(trickle)
            sizes.append(trickle.grains[0].size)
        self.assertAlmostEqual(sizes.count('speck') / 300, 0.7, delta=0.08)
        self.assertAlmostEqual(sizes.count('chip') / 300, 0.25, delta=0.08)
        self.assertGreater(sizes.count('crumb'), 0)
        landed = []
        ambience.land = lambda x, bottom, pour, trickle=None: landed.append(x)
        trickle = ruins_ambience.Trickle(ruins_ambience.Crack(100, 130, GROUND), 0, 0)
        trickle.grains = [ruins_ambience.Grain(GROUND - 1.0, 3.0, 100.0, GRIT_HEAD, size='crumb')]
        ambience.trickles = [trickle]
        ambience.advance_trickles()
        self.assertEqual(landed, [100.0, 101.0])

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
        trickle = ruins_ambience.Trickle(ruins_ambience.Crack(100, 130, GROUND), 0, 0)
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
        streak = new_streak(random.Random(1))
        streak.pixels = [(x, 150) for x in range(100, 300)]
        streak.curl, streak.length, streak.head = (500, 510), 60, 150
        ambience.streaks = [streak]
        # It shows from x 190 to 249.
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
        starry = {place for place, air in self.rooms.items() if air.stars and not air.desert}
        self.assertEqual(starry, {(6, 1), (6, 11), (6, 12), (6, 14), (7, 24), (7, 25), (7, 26), (8, 12)})
        for place, air in self.rooms.items():
            if air.desert:
                self.assertEqual(len(air.stars), DESERT_STARS, place)

    def test_the_wind_blows_in_every_room_open_to_the_sky_but_the_desert(self):
        windy = {place for place, air in self.rooms.items() if air.windy}
        self.assertEqual(windy, {(6, room) for room in (1, 4, 7, 8, 11, 12, 14, 20, 22)}
                         | {(7, room) for room in (13, 15, 16, 18, 19, 24, 25, 26, 27)}
                         | {(8, 12)} | {(9, room) for room in (3, 4, 5, 7, 15)})

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

    def test_level_six_room_twelve_has_the_sky_that_was_approved(self):
        stars = self.rooms[6, 11].stars
        self.assertEqual(len(stars), 19)
        self.assertEqual(sum(kind in WARM for *_, kind in stars), 4)

    def test_every_star_is_on_clear_sky(self):
        for place, air in self.rooms.items():
            clear = DESERT_STAR_CLEAR if air.desert else STAR_CLEAR
            for x, y, _kind in air.stars:
                self.assertTrue(air.sky[y - clear:y + clear + 1, x - clear:x + clear + 1].all(), (place, x, y))

    def test_no_shooting_star_over_the_desert(self):
        # The desert's sky is the purple by the horizon, as the approved look had it.
        rng = random.Random(0)
        for place, air in self.rooms.items():
            if air.desert:
                for kind in SHOOTERS:
                    self.assertIsNone(shooter_path(air, kind, rng), place)


@unittest.skipUnless(RUINS_INSTALLED, 'Imported ruins resources required')
class RealSceneTests(unittest.TestCase):
    """The same inputs with the toggle off and on, in the hidden real scene."""

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


class SourceTests(unittest.TestCase):
    def test_the_module_reads_no_game_state(self):
        source = Path('pop2/ruins_ambience.py').read_text(encoding='utf-8')
        self.assertNotIn('cavern_state', source)
        self.assertNotIn('random.random(', source)
        self.assertNotIn('save_game', source)


if __name__ == '__main__':
    unittest.main()
