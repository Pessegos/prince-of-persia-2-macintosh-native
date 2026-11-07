"""The optional cave ambience: pixels only, tied to the scenery, off by default."""

from dataclasses import replace
import math
from pathlib import Path
import random
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy
from PIL import Image

from pop2.cavern_ambience import (
    AMBIENCE_LEVELS, ALL_INKS, ASH_INKS, Air, Ash, COARSE_DUST, CavernAmbience, Colours, DUST_BRIGHT_LIFE,
    DUST_FADE_IN, DUST_FADE_OUT, DUST_HEADING, DUST_LIFE_SPREAD, DUST_PALE_INK, DUST_PATCH, DUST_POCKETS,
    DROP_INKS, DROP_LAVA_INK, DROP_SHINE_LIGHT, DROP_WARM_LIGHT, SWELL_INKS,
    DUST_POCKETS_APART, DUST_REST_DEPTH, DUST_SHINE_INK, DUST_WARM_INK, Drip, FINE_DUST, FLASH_INKS, Flicker,
    HAZE_OVER_FLAME, HAZE_OVER_POOL, HAZE_RISE, HAZE_WAVE, QUIET_DUST, flame_of, haze_of, haze_over, room_torches,
    shows,
    HEAT_REACH, HEIGHT, LIGHT_HOLD, LIGHT_LEVELS, LONGEST_REACH, MOST_ASH, MOST_DUST, Mote, QUICK_DEPTH,
    QUICK_FOLLOW, SHORTEST_REACH, SLOW_DEPTH, SLOW_FOLLOW, SPLASH_INKS, STEAM_INKS, SWELL_TICKS, WIDTH,
    flame_pixels, landing, lifespan, on_the_pixels, pool_glow, read_torch, soft_spot, stalactite_tips, steady_wall,
)
from pop2.firelight import DIRECTIONS, LIGHT_REACH, gaussian, trace_lavalight
from pop2.game_menu import GameMenu
from pop2.paths import ASSET_DIR

CAVERNS_INSTALLED = (ASSET_DIR / 'caverns_level4.json').is_file()
WALL = (24, 8, 8, 255)
ROCK = (140, 115, 90, 255)
FIRE = (255, 127, 0, 255)
COVER = (11, 222, 33, 255)


def blank(value=0):
    return bytes([value]) * (WIDTH * HEIGHT)


def palette():
    colours = {index: (index, 255 - index, 7, 255) for index in ALL_INKS}
    # A dark ramp, so blends and light have somewhere to land.
    colours.update({300 + step: (24 + step * 24, 8 + step * 20, 8 + step * 16, 255) for step in range(10)})
    colours.update({1: WALL, 2: ROCK, 3: FIRE})
    return colours


COLOURS = Colours(palette())


def liquid_of(pool, depth=6):
    return {x: (y - depth, y + depth) for x, y in pool.items()}


def plain_rock():
    return numpy.full((HEIGHT, WIDTH), 0.5, dtype=numpy.float32)


def nothing_in_front():
    return numpy.zeros((HEIGHT, WIDTH), dtype=bool)


def room_air(drips=(), flames=(), pools=(), opened=255, covered=None, pool_glows=False, torches=(), hazes=()):
    centres = tuple((sum(columns) / len(columns), sum(columns.values()) / len(columns)) for columns in pools)
    return Air(blank(opened), covered if covered is not None else blank(), tuple(drips), tuple(flames),
               tuple(pools), COLOURS, palette(), centres,
               tuple(pool_glow(liquid_of(columns), plain_rock(), nothing_in_front(), COLOURS)
                     for columns in pools if pool_glows),
               tuple(torches), tuple(hazes))


def still_ambience(air, **options):
    """No dust unless a test places it."""
    scene = CavernAmbience(0, air, random.Random(5), **options)
    scene.motes.clear()
    return scene


def ticks_of(scene, mote, terrain=None):
    """Each tick a grain lasts. One that never ends fails rather than hanging the tests."""
    for _ in range(4000):
        if not scene.advance_mote(mote, 0.0, terrain):
            return
        yield mote
    raise AssertionError('The grain never ended.')


def wall_frame():
    return Image.new('RGBA', (WIDTH, HEIGHT), WALL)


def colours_in(frame):
    return {colour for _count, colour in frame.getcolors(maxcolors=4096)}


def run_until(ambience, condition, limit=2000):
    for _ in range(limit):
        ambience.advance()
        if condition():
            return True
    return False


def scenery(colour=ROCK):
    return numpy.full((HEIGHT, WIDTH, 3), colour[:3], dtype=numpy.uint8)


def burning_torch(x=300, y=200, frames=3):
    """A torch that is only there for its light: a flame around a point."""
    sprite = numpy.zeros((frames, 40, 30, 4), dtype=numpy.uint8)
    sprite[...] = ROCK
    sprite[:, 10:30, 12:18] = FIRE
    return read_torch(sprite, sprite[0], x - 15, y - 20, scenery(), COLOURS.firelight)


def tile_map(kinds):
    """A one-room map: kinds[(column, row)], empty elsewhere."""
    return SimpleNamespace(tile=lambda _room, column, row: SimpleNamespace(kind=kinds.get((column, row), 0)))


class StalactiteTipTests(unittest.TestCase):
    def picture(self):
        shades = bytearray(blank(10))
        for offset in range(20):
            # A cone narrowing to one pixel at y=70.
            width = 1 + offset // 4
            y = 70 - offset
            for x in range(100 - width // 2, 100 + width // 2 + 1):
                shades[y * WIDTH + x] = 150
        return bytes(shades)

    def test_the_tip_is_the_lowest_pixel_of_a_thin_hanging_run(self):
        self.assertEqual([tip[:2] for tip in stalactite_tips(self.picture())], [(100, 70)])

    def test_the_edge_of_a_wide_ceiling_is_no_stalactite(self):
        shades = bytearray(blank(10))
        for y in range(40):
            shades[y * WIDTH:y * WIDTH + WIDTH] = bytes([150]) * WIDTH
        self.assertEqual(stalactite_tips(bytes(shades)), [])

    def test_a_drop_lands_on_the_first_floor_under_it(self):
        terrain = tile_map({(2, 1): 1, (2, 2): 1})
        self.assertEqual(landing(terrain, 0, 2 * 51 + 5, 60), 226)
        self.assertEqual(landing(terrain, 0, 2 * 51 + 5, 230), 346)
        self.assertIsNone(landing(terrain, 0, 3 * 51, 60))


class DropTests(unittest.TestCase):
    def test_a_drop_moves_once_per_game_tick(self):
        # Three times a tick was too smooth for a game that runs at twelve.
        scene = still_ambience(room_air([Drip(100, 50, 300, False)]))
        fall = scene.falls[0]
        fall.y, fall.speed = 52.0, 0.0
        heights = []
        for _ in range(4):
            scene.advance()
            heights.append(fall.y)
        self.assertEqual([round(height, 2) for height in heights], [53.15, 55.45, 58.9, 63.5])

    def test_a_drop_swells_on_the_tip_then_falls_straight_down_its_column(self):
        scene = still_ambience(room_air([Drip(100, 50, 200, False)]))
        scene.falls[0].wait = 0
        columns, rows = set(), []
        for _ in range(SWELL_TICKS + 60):
            scene.advance()
            pixels = list(scene.fall_pixels(scene.falls[0]))
            columns.update(pixel[0] for pixel in pixels)
            if pixels:
                rows.append(pixels[0][1])
            if scene.flecks:
                break
        self.assertEqual(columns, {100})
        self.assertEqual(rows[0], 51)
        self.assertEqual(rows, sorted(rows))
        self.assertLessEqual(rows[-1], 200)

    def test_a_splash_on_the_floor_and_a_hiss_on_the_lava(self):
        scene = still_ambience(room_air([Drip(100, 50, 200, False)]))
        self.assertTrue(run_until(scene, lambda: scene.flecks))
        self.assertEqual({fleck.inks for fleck in scene.flecks}, {SPLASH_INKS})
        scene = still_ambience(room_air([Drip(100, 50, 200, True)]))
        self.assertTrue(run_until(scene, lambda: scene.flecks))
        self.assertEqual({fleck.inks for fleck in scene.flecks}, {STEAM_INKS, FLASH_INKS})

    def test_a_floor_that_has_fallen_no_longer_stops_the_drop(self):
        drip = Drip(102, 50, 226, False)
        scene = still_ambience(room_air([drip]))
        self.assertEqual(scene.fall_bottom(drip, tile_map({(2, 1): 1})), 226)
        self.assertEqual(scene.fall_bottom(drip, tile_map({(2, 1): 0, (2, 2): 1})), 346)
        self.assertEqual(scene.fall_bottom(drip, tile_map({})), HEIGHT)

    def test_a_drop_leaving_the_room_makes_no_splash(self):
        scene = still_ambience(room_air([Drip(102, 50, 226, False)]))
        scene.falls[0].wait = 0
        for _ in range(200):
            scene.advance(tile_map({}))
            self.assertEqual(scene.flecks, [])

    def test_each_stalactite_keeps_its_own_rhythm(self):
        scene = still_ambience(room_air([Drip(100, 50, 200, False), Drip(200, 50, 200, False)]))
        periods = [fall.period for fall in scene.falls]
        self.assertNotEqual(periods[0], periods[1])
        for _ in range(3000):
            scene.advance()
            for fall, period in zip(scene.falls, periods):
                self.assertLessEqual(fall.wait, period + 14)


class DropInTheLightTests(unittest.TestCase):
    def falling(self, **options):
        scene = still_ambience(room_air([Drip(300, 20, 340, False)], **options))
        fall = scene.falls[0]
        fall.speed = 12.0
        return scene, fall

    def inks_at(self, scene, fall, y):
        fall.y = float(y)
        return [ink for _x, _y, ink in scene.fall_pixels(fall)]

    def beside_a_torch(self):
        return self.falling(flames=[(300, 200)], torches=[burning_torch(300, 200)])

    def test_water_in_the_dark_is_only_water(self):
        scene, fall = self.falling()
        self.assertEqual(self.inks_at(scene, fall, 200), list(DROP_INKS))

    def test_a_drop_shines_by_the_flame_and_only_its_front(self):
        scene, fall = self.beside_a_torch()
        self.assertEqual(self.inks_at(scene, fall, 200), [DUST_SHINE_INK, *DROP_INKS[1:]])

    def test_the_shine_fades_with_the_light_on_the_way_down(self):
        scene, fall = self.beside_a_torch()
        seen = []
        for y in range(200, 340):
            front = self.inks_at(scene, fall, y)[0]
            if not seen or seen[-1] != front:
                seen.append(front)
        self.assertEqual(seen, [DUST_SHINE_INK, DUST_WARM_INK, DROP_INKS[0]])

    def test_each_shine_is_where_the_light_says(self):
        scene, fall = self.beside_a_torch()
        for y in range(200, 340, 3):
            light = scene.light_at(300, y)[0]
            expected = (DUST_SHINE_INK if light >= DROP_SHINE_LIGHT else DUST_WARM_INK if light >= DROP_WARM_LIGHT
                        else DROP_INKS[0])
            self.assertEqual(self.inks_at(scene, fall, y)[0], expected, y)

    def test_a_drop_about_to_fall_catches_the_light_but_not_a_new_one(self):
        scene = still_ambience(room_air([Drip(300, 195, 340, False)], flames=[(300, 200)],
                                        torches=[burning_torch(300, 200)]))
        fall = scene.falls[0]
        fall.swell = 1
        self.assertEqual([ink for _x, _y, ink in scene.fall_pixels(fall)], [SWELL_INKS[0]])
        fall.swell = SWELL_TICKS - 1
        self.assertEqual([ink for _x, _y, ink in scene.fall_pixels(fall)], [DUST_SHINE_INK, SWELL_INKS[0]])

    def test_over_the_lava_the_front_of_a_drop_is_lit_from_below(self):
        pool = {x: 300 for x in range(280, 320)}
        scene, fall = self.falling(pools=[pool])
        self.assertEqual(self.inks_at(scene, fall, 285), [DROP_LAVA_INK, *DROP_INKS[1:]])
        self.assertEqual(self.inks_at(scene, fall, 100), list(DROP_INKS))

    def test_catching_the_light_takes_no_random_numbers(self):
        scene, fall = self.beside_a_torch()
        before = scene.rng.getstate()
        self.inks_at(scene, fall, 200)
        self.assertEqual(scene.rng.getstate(), before)


class DustTests(unittest.TestCase):
    def mote(self, x, y, kind=COARSE_DUST):
        return Mote(x, y, 0.0, 0.0, 0.0, 1000.0, kind, age=500.0)

    def test_a_grain_keeps_its_shape_as_it_crosses_the_pixels(self):
        # Split among the four nearest pixels the brightest fell to a quarter
        # and back on every pixel crossed: a worm going round a small square.
        brightest, seen = [], []
        for step in range(60):
            weights = [weight for _column, _row, weight in soft_spot(100 + step * 0.17, 100 - step * 0.06)]
            brightest.append(max(weights))
            seen.append(sum(weight >= 0.1 for weight in weights))
        self.assertGreater(min(brightest), 0.55)
        self.assertLess(max(seen) - min(seen), 7)

    def test_a_grain_is_a_small_soft_spot(self):
        scene = still_ambience(room_air())
        scene.motes.append(self.mote(100.0, 100.0))
        frame = scene.draw(wall_frame())
        changed = numpy.argwhere((numpy.asarray(frame) != WALL).any(axis=2))
        self.assertGreaterEqual(len(changed), 5)
        self.assertLessEqual(len(changed), 13)
        self.assertLessEqual(changed.max(axis=0).tolist(), [102, 102])
        self.assertGreaterEqual(changed.min(axis=0).tolist(), [98, 98])

    def test_a_blend_is_still_a_palette_colour(self):
        scene = still_ambience(room_air(flames=[(100, 100)], torches=[burning_torch(100, 100)]))
        for offset in range(20):
            scene.motes.append(self.mote(100 + offset * 3, 100 + offset * 2))
        allowed = {tuple(colour) + (255,) for colour in COLOURS.rgb.tolist()}
        self.assertLessEqual(colours_in(scene.draw(wall_frame())), allowed)

    def share_of_the_brightest_pixel(self, x, y):
        scene = still_ambience(room_air(torches=[burning_torch()]))
        frame = wall_frame()
        scene.dust_spot(frame.load(), self.mote(x, y))
        change = numpy.abs(numpy.asarray(frame).astype(int)[..., :3] - WALL[:3]).sum(axis=2)
        return change.max() / change.sum()

    def test_a_grain_is_soft_in_the_dark_and_sharp_in_the_light(self):
        self.assertLess(self.share_of_the_brightest_pixel(20.2, 20.2), 0.4)
        self.assertGreater(self.share_of_the_brightest_pixel(300.2, 200.2), 0.45)

    def test_in_focus_a_grain_waits_on_a_pixel_and_crosses_quickly(self):
        self.assertEqual(on_the_pixels(100.2, 1.0), 100.0)
        self.assertEqual(on_the_pixels(100.8, 1.0), 101.0)
        self.assertAlmostEqual(on_the_pixels(100.5, 1.0), 100.5)
        self.assertEqual(on_the_pixels(100.2, 0.0), 100.2)
        steps = [on_the_pixels(100 + share / 100, 1.0) for share in range(0, 100)]
        self.assertEqual(steps, sorted(steps))
        self.assertLess(on_the_pixels(99.8, 1.0), on_the_pixels(100.2, 1.0) + 1e-9)

    def strengths(self, scene, x, y, ticks=600):
        mote = self.mote(x, y)
        result = []
        for _ in range(ticks):
            result.append(scene.dust_colour(mote)[3])
            mote.age += 1
            mote.life += 1
        return result

    def test_only_a_grain_in_the_light_glints(self):
        scene = still_ambience(room_air(flames=[(300, 200)], torches=[burning_torch()]))
        lit, dark = self.strengths(scene, 300, 200), self.strengths(scene, 20, 20)
        self.assertEqual(max(dark), min(dark))
        self.assertGreater(max(lit), min(lit))

    def test_a_glint_is_a_moment_and_no_grain_is_a_beacon(self):
        scene = still_ambience(room_air(flames=[(300, 200)], torches=[burning_torch()]))
        strengths = numpy.array(self.strengths(scene, 300, 200, 2000))
        bright = strengths > strengths.min() + (strengths.max() - strengths.min()) / 2
        self.assertLess(bright.mean(), 0.12)
        # Runs of brightness, and how high each one goes.
        starts = numpy.flatnonzero(numpy.diff(bright.astype(int)) == 1)
        ends = numpy.flatnonzero(numpy.diff(bright.astype(int)) == -1)
        peaks = [strengths[start:end + 1].max() for start, end in zip(starts, ends) if end > start]
        self.assertGreater(len(peaks), 2)
        self.assertGreater(max(peaks) - min(peaks), 0.02)

    def test_air_is_drawn_in_beside_a_flame_and_rises_through_it(self):
        scene = still_ambience(room_air(flames=[(300, 200)]))
        self.assertGreater(scene.wind_at(260, 205)[0], 0)
        self.assertLess(scene.wind_at(340, 205)[0], 0)
        self.assertLess(scene.wind_at(300, 180)[1], 0)
        self.assertEqual(scene.wind_at(300 + HEAT_REACH + 1, 200), (0.0, 0.0))

    def test_air_over_a_flame_spreads_out(self):
        scene = still_ambience(room_air(flames=[(300, 200)]))
        self.assertLess(scene.wind_at(280, 170)[0], 0)
        self.assertGreater(scene.wind_at(320, 170)[0], 0)

    def test_a_grain_rides_the_air_with_some_weight(self):
        scene = still_ambience(room_air(flames=[(300, 200)]))
        mote = Mote(280.0, 205.0, 0.0, 0.0, 0.0, 1000.0, COARSE_DUST, age=100.0)
        speeds = []
        for _ in range(30):
            scene.advance_mote(mote, 0.0)
            speeds.append(mote.moving_x)
        self.assertLess(abs(speeds[0]), 0.02)
        self.assertGreater(speeds[-1], speeds[0])
        self.assertLess(max(abs(after - before) for before, after in zip(speeds, speeds[1:])), 0.02)

    def walled_air(self):
        opened = bytearray(blank())
        for y in range(HEIGHT):
            opened[y * WIDTH:y * WIDTH + 200] = bytes([255]) * 200
        return Air(bytes(opened), blank(), (), (), (), COLOURS, palette())

    def test_a_grain_settles_before_it_touches_the_rock(self):
        # It used to vanish on the spot.
        scene = still_ambience(self.walled_air())
        mote = Mote(190.0, 100.0, 0.2, 0.0, 0.0, 1000.0, COARSE_DUST, age=100.0, moving_x=0.2)
        strengths = []
        for _ in ticks_of(scene, mote):
            strengths.append(scene.dust_colour(mote)[3])
            self.assertLess(mote.x, 200)
        self.assertLessEqual(mote.settling, 0)
        self.assertAlmostEqual(strengths[-1], 0, places=2)
        self.assertLess(max(before - after for before, after in zip(strengths, strengths[1:])), 0.05)

    def test_the_draught_turns_only_slowly(self):
        scene = CavernAmbience(0, room_air(flames=[(200, 200)]), random.Random(6))
        before = (scene.motes[0].moving_x, scene.motes[0].moving_y)
        scene.advance()
        after = (scene.motes[0].moving_x, scene.motes[0].moving_y)
        self.assertLess(numpy.hypot(after[0] - before[0], after[1] - before[1]), 0.03)

    def test_dust_drifts_slowly(self):
        # Twice what the coarse grains do was too fast for the user, and they are
        # the slowest: the rest stay well short of that.
        scene = CavernAmbience(0, room_air(flames=[(200, 200)]), random.Random(6))
        for kind in (FINE_DUST, COARSE_DUST):
            self.assertLessEqual(kind.speed[1], 0.31)
            for _ in range(100):
                mote = scene.new_mote(kind)
                self.assertLessEqual(math.hypot(mote.dx, mote.dy), kind.speed[1] + 1e-9)

    def test_a_grain_comes_and_goes_gradually(self):
        scene = still_ambience(room_air(flames=[(300, 200)]))
        mote = Mote(310.0, 200.0, 0.0, 0.0, 0.0, 300.0, COARSE_DUST)
        strengths = []
        for age in range(0, 301, 2):
            mote.age = age
            strengths.append(scene.dust_colour(mote)[3])
        self.assertEqual(strengths[0], 0)
        self.assertAlmostEqual(strengths[-1], 0, places=6)
        rising = strengths[:int(COARSE_DUST.life * DUST_FADE_IN) // 2 + 1]
        falling = strengths[-(int(COARSE_DUST.life * DUST_FADE_OUT) // 2 + 1):]
        self.assertEqual(rising, sorted(rising))
        self.assertEqual(falling, sorted(falling, reverse=True))
        self.assertLess(max(abs(after - before) for before, after in zip(strengths, strengths[1:])), 0.05)

    def test_a_new_grain_has_air_for_its_whole_life(self):
        opened = bytearray(blank())
        for y in range(HEIGHT):
            opened[y * WIDTH:y * WIDTH + 200] = bytes([255]) * 200
        air = Air(bytes(opened), blank(), (), ((100, 150),), (), COLOURS, palette())
        scene = CavernAmbience(0, air, random.Random(3))
        for _ in range(100):
            mote = scene.new_mote()
            self.assertLess(mote.x + mote.dx * mote.life, 208)
            self.assertLessEqual(mote.life, FINE_DUST.life * DUST_LIFE_SPREAD[1])

    def test_dust_gathers_in_a_few_pockets_of_air(self):
        # Evenly spread and falling, it looked like snow.
        scene = CavernAmbience(0, room_air(flames=[(255, 180)]), random.Random(3))
        self.assertEqual(len(scene.pockets), DUST_POCKETS)
        for index, (x, y) in enumerate(scene.pockets):
            for other_x, other_y in scene.pockets[index + 1:]:
                self.assertGreater(math.hypot(x - other_x, y - other_y), DUST_POCKETS_APART)
        apart = []
        with patch('pop2.cavern_ambience.DUST_BY_FLAME', 0.0), patch('pop2.cavern_ambience.DUST_BY_POOL', 0.0):
            for _ in range(200):
                mote = scene.new_mote()
                apart.append(min(math.hypot(mote.x - x, mote.y - y) for x, y in scene.pockets))
        # Nearly anywhere in the room is within a hundred pixels of some pocket,
        # so it is the typical distance that tells a patch from an even spread.
        self.assertLess(numpy.median(apart), 2 * DUST_PATCH)

    def test_pockets_are_in_the_open_air(self):
        opened = bytearray(blank())
        for y in range(HEIGHT):
            opened[y * WIDTH:y * WIDTH + 200] = bytes([255]) * 200
        air = Air(bytes(opened), blank(), (), ((100, 150),), (), COLOURS, palette())
        scene = CavernAmbience(0, air, random.Random(3))
        self.assertTrue(scene.pockets)
        self.assertTrue(all(x < 200 for x, _y in scene.pockets))

    def test_a_room_without_open_air_has_no_pockets(self):
        scene = CavernAmbience(0, room_air(opened=0), random.Random(3))
        self.assertEqual(scene.pockets, [])
        self.assertIsNone(scene.new_mote())

    def test_one_draught_crosses_the_room(self):
        # Every heading of its own looked like insects.
        scene = CavernAmbience(0, room_air(flames=[(200, 200)]), random.Random(6))
        self.assertLess(DUST_HEADING[1] - DUST_HEADING[0], 1.0)
        for _ in range(200):
            self.assertGreater(scene.new_mote().dx, 0)

    def test_the_dust_stays_as_much_as_it_was(self):
        opened = bytearray(blank())
        for y in range(HEIGHT):
            opened[y * WIDTH:y * WIDTH + 200] = bytes([255]) * 200
        air = Air(bytes(opened), blank(), (), ((100, 150),), (), COLOURS, palette())
        scene = CavernAmbience(0, air, random.Random(3))
        self.assertEqual(len(scene.motes), MOST_DUST)
        for _ in range(1500):
            scene.advance()
            self.assertEqual(len(scene.motes), MOST_DUST)
            self.assertTrue(all(mote.x < 200 for mote in scene.motes))

    def test_dust_is_shown_only_on_open_air(self):
        # Open air only in the left half of the room.
        opened = bytearray(blank())
        for y in range(HEIGHT):
            opened[y * WIDTH:y * WIDTH + WIDTH // 2] = bytes([255]) * (WIDTH // 2)
        air = Air(bytes(opened), blank(), (), ((150, 150),), (), COLOURS, palette())
        scene = CavernAmbience(0, air, random.Random(3))
        self.assertTrue(scene.motes)
        for _ in range(200):
            scene.advance()
            frame = wall_frame()
            scene.draw(frame)
            box = frame.crop((WIDTH // 2, 0, WIDTH, HEIGHT))
            self.assertEqual(colours_in(box), {WALL})

    def test_dust_can_be_seen_in_the_dark_and_more_by_the_fire(self):
        # Seen only by the torch, it was as good as not there.
        scene = still_ambience(room_air(flames=[(300, 200)], torches=[burning_torch()]))
        # A faint grain could only be found by someone who knew to look for it.
        self.assertEqual(scene.dust_colour(self.mote(20, 20, FINE_DUST))[3], 1.0)
        self.assertGreater(scene.dust_colour(self.mote(310, 200))[3], scene.dust_colour(self.mote(20, 20))[3])

    def test_a_grain_in_the_dark_stands_out_from_the_dark_wall(self):
        scene = still_ambience(room_air())
        scene.motes.append(self.mote(100.0, 100.0))
        frame = scene.draw(wall_frame())
        brightest = numpy.asarray(frame)[..., :3].astype(int).sum(axis=2).max()
        self.assertGreater(brightest, sum(WALL[:3]) + 150)

    def floor_map(self):
        return tile_map({(column, 1): 1 for column in range(10)})

    def sinking(self, x=100.0, y=190.0, **options):
        return Mote(x, y, 0.0, 0.0, 0.0, 1000.0, COARSE_DUST, age=100.0, moving_y=0.15, sink=0.15, **options)

    def floor_air(self):
        # Open air down to the floor's strip.
        opened = bytearray(blank())
        for y in range(205):
            opened[y * WIDTH:(y + 1) * WIDTH] = bytes([255]) * WIDTH
        return Air(bytes(opened), blank(), (), (), (), COLOURS, palette())

    def bring_down(self, scene, mote, terrain):
        for _ in range(2000):
            if not scene.advance_mote(mote, 0.0, terrain):
                return False
            if mote.rest is not None and mote.y >= mote.rest:
                return True
        self.fail('It never came down.')

    def test_a_sinking_grain_comes_down_on_the_floor(self):
        scene = still_ambience(self.floor_air())
        mote = self.sinking()
        self.assertTrue(self.bring_down(scene, mote, self.floor_map()))
        self.assertIn(226 - mote.rest, range(DUST_REST_DEPTH[0], DUST_REST_DEPTH[1] + 1))

    def test_it_lies_there_and_fades_away(self):
        scene = still_ambience(self.floor_air())
        mote, terrain = self.sinking(), self.floor_map()
        self.bring_down(scene, mote, terrain)
        place, strengths = (mote.x, mote.y), []
        for _ in ticks_of(scene, mote, terrain):
            strengths.append(scene.dust_colour(mote)[3])
            self.assertEqual((mote.x, mote.y), place)
        self.assertGreater(len(strengths), 60)
        self.assertEqual(strengths, sorted(strengths, reverse=True))
        self.assertLess(max(before - after for before, after in zip(strengths, strengths[1:])), 0.05)
        self.assertAlmostEqual(strengths[-1], 0, places=2)

    def test_it_shows_on_the_floor_as_one_sharp_speck(self):
        # The floor is not open air, which is all that other dust is drawn on.
        scene = still_ambience(self.floor_air())
        mote, terrain = self.sinking(), self.floor_map()
        self.bring_down(scene, mote, terrain)
        scene.motes.append(mote)
        frame = scene.draw(wall_frame())
        changed = numpy.argwhere((numpy.asarray(frame) != WALL).any(axis=2))
        self.assertTrue(len(changed))
        self.assertLessEqual(len(changed), 5)
        brightest = numpy.asarray(frame)[..., :3].astype(int).sum(axis=2).max()
        self.assertGreater(brightest, sum(WALL[:3]) + 150)

    def test_a_grain_that_does_not_sink_settles_where_it_is(self):
        scene = still_ambience(self.floor_air())
        mote = self.sinking()
        mote.sink = 0.0
        list(ticks_of(scene, mote, self.floor_map()))
        self.assertIsNone(mote.rest)

    def test_no_grain_lies_on_the_lava(self):
        pool = {x: 215 for x in range(80, 140)}
        air = replace(self.floor_air(), pools=(pool,))
        scene = still_ambience(air)
        mote = self.sinking()
        list(ticks_of(scene, mote, self.floor_map()))
        self.assertIsNone(mote.rest)

    def test_no_grain_lies_behind_the_foreground(self):
        scene = still_ambience(replace(self.floor_air(), covered=blank(255)))
        mote = self.sinking()
        list(ticks_of(scene, mote, self.floor_map()))
        self.assertIsNone(mote.rest)

    def test_a_floor_that_falls_takes_what_lies_on_it(self):
        scene = still_ambience(self.floor_air())
        mote = self.sinking()
        self.bring_down(scene, mote, self.floor_map())
        self.assertFalse(scene.advance_mote(mote, 0.0, tile_map({})))

    def test_without_a_map_it_only_settles(self):
        scene = still_ambience(self.floor_air())
        mote = self.sinking()
        list(ticks_of(scene, mote))
        self.assertIsNone(mote.rest)

    def test_only_some_grains_sink(self):
        scene = CavernAmbience(0, room_air(flames=[(200, 200)]), random.Random(6))
        sinking = sum(mote.sink > 0 for mote in scene.motes)
        self.assertGreater(sinking, 0)
        self.assertLess(sinking, len(scene.motes) * 0.2)

    def grains(self, kind, count=300):
        scene = still_ambience(room_air(flames=[(200, 200)]))
        return [scene.new_mote(kind) for _ in range(count)]

    def test_a_room_without_fire_has_less_dust_and_none_of_it_shines(self):
        # No dust at all made those rooms look dead, but with nothing to light it
        # it must show less.
        quiet = CavernAmbience(0, room_air(), random.Random(3))
        lit = CavernAmbience(0, room_air(flames=[(255, 180)]), random.Random(3))
        self.assertEqual(len(quiet.motes), sum(kind.count for kind in QUIET_DUST))
        self.assertLess(len(quiet.motes), len(lit.motes) * 0.6)
        self.assertLess(max(mote.brightness for mote in quiet.motes), 0.31)
        self.assertGreater(max(mote.brightness for mote in lit.motes), 0.31)
        faint = [mote.kind.strength for mote in quiet.motes if mote.kind.softness == COARSE_DUST.softness]
        self.assertTrue(faint)
        self.assertLess(max(faint), COARSE_DUST.strength)

    def test_a_grain_gone_from_a_room_without_fire_comes_back_quiet(self):
        scene = CavernAmbience(0, room_air(), random.Random(3))
        kinds = {mote.kind for mote in scene.motes}
        for _ in range(1200):
            scene.advance()
        self.assertTrue(scene.motes)
        self.assertLessEqual({mote.kind for mote in scene.motes}, kinds)

    def test_there_is_little_dust_and_most_of_it_is_fine(self):
        # Sixty grains, a lot of them coarse, looked like snow.
        self.assertLess(MOST_DUST, 35)
        self.assertGreater(FINE_DUST.count, 4 * COARSE_DUST.count)

    def test_the_brighter_a_grain_the_shorter_it_lasts(self):
        lives = [lifespan(FINE_DUST, brightness / 10) for brightness in range(11)]
        self.assertEqual(lives, sorted(lives, reverse=True))
        self.assertEqual(lives[0], FINE_DUST.life)
        self.assertAlmostEqual(lives[-1], DUST_BRIGHT_LIFE)

    def test_the_brightest_are_gone_in_about_three_seconds(self):
        # The user meant really short: three seconds or so.
        self.assertLessEqual(DUST_BRIGHT_LIFE * DUST_LIFE_SPREAD[1] / 12, 3.7)

    def test_a_grain_half_as_bright_is_already_much_shorter_lived(self):
        self.assertLess(lifespan(FINE_DUST, 0.5), FINE_DUST.life * 0.3)

    def test_most_fine_grains_are_dim(self):
        grains = self.grains(FINE_DUST)
        brightness = numpy.array([mote.brightness for mote in grains])
        self.assertGreater((brightness < 0.25).mean(), 0.5)
        self.assertGreater((brightness > 0.6).mean(), 0.05)
        self.assertLess((brightness > 0.6).mean(), 0.3)

    def test_a_grain_lives_what_its_brightness_says(self):
        for mote in self.grains(FINE_DUST):
            self.assertLessEqual(mote.life, lifespan(FINE_DUST, mote.brightness) * DUST_LIFE_SPREAD[1] + 1e-6)

    def test_coarse_grains_do_not_shine(self):
        self.assertTrue(all(mote.brightness == 0 for mote in self.grains(COARSE_DUST)))

    def test_a_brief_grain_still_comes_and_goes(self):
        scene = still_ambience(room_air())
        mote = Mote(100.0, 100.0, 0.0, 0.0, 0.0, DUST_BRIGHT_LIFE, FINE_DUST, brightness=1.0)
        strengths = []
        for age in range(0, DUST_BRIGHT_LIFE + 1):
            mote.age = age
            strengths.append(scene.dust_colour(mote)[3])
        self.assertEqual(strengths[0], 0)
        self.assertEqual(max(strengths), 1.0)
        self.assertAlmostEqual(strengths[-1], 0, places=6)

    def test_a_brighter_grain_is_paler(self):
        scene = still_ambience(room_air())
        dim = scene.dust_colour(self.mote(100, 100, FINE_DUST))[:3]
        bright = replace(self.mote(100, 100, FINE_DUST), brightness=1.0)
        self.assertEqual(tuple(scene.dust_colour(bright)[:3]), tuple(palette()[DUST_PALE_INK][:3]))
        self.assertEqual(tuple(dim), tuple(palette()[FINE_DUST.ink][:3]))

    def test_the_coarse_grains_are_the_slowest(self):
        self.assertLess(COARSE_DUST.speed[1], FINE_DUST.speed[1])
        coarse = [math.hypot(mote.dx, mote.dy) for mote in self.grains(COARSE_DUST)]
        fine = [math.hypot(mote.dx, mote.dy) for mote in self.grains(FINE_DUST)]
        self.assertGreater(numpy.mean(fine), numpy.mean(coarse) * 1.3)

    def test_only_the_coarse_grains_sink(self):
        self.assertFalse(any(mote.sink for mote in self.grains(FINE_DUST)))
        share = numpy.mean([mote.sink > 0 for mote in self.grains(COARSE_DUST)])
        self.assertGreater(share, 0.6)
        self.assertLess(share, 1.0)

    def test_a_sinking_grain_lives_past_where_it_was_heading(self):
        grain = next(mote for mote in self.grains(COARSE_DUST) if mote.sink)
        self.assertGreaterEqual(grain.life, COARSE_DUST.life * DUST_LIFE_SPREAD[0])

    def test_a_sinking_grain_starts_above_a_floor(self):
        # High up it could only settle on a pillar, long before it came down.
        opened = bytearray(blank())
        for y in range(205):
            opened[y * WIDTH:(y + 1) * WIDTH] = bytes([255]) * WIDTH
        air = Air(bytes(opened), blank(), (), ((100, 150),), (), COLOURS, palette())
        scene = still_ambience(air)
        heights = [mote.y for mote in (scene.new_mote(COARSE_DUST) for _ in range(200)) if mote.sink]
        self.assertGreater(numpy.mean(numpy.array(heights) > 135), 0.9)

    def test_a_fine_grain_goes_with_the_air_sooner(self):
        scene = still_ambience(room_air())
        fine, coarse = (Mote(100.0, 100.0, 0.2, 0.0, 0.0, 1000.0, kind, age=100.0) for kind in (FINE_DUST, COARSE_DUST))
        for mote in (fine, coarse):
            for _ in range(8):
                scene.advance_mote(mote, 0.0)
        self.assertGreater(fine.moving_x, coarse.moving_x * 1.3)

    def test_a_fine_grain_is_one_opaque_pixel_even_in_the_dark(self):
        scene = still_ambience(room_air())
        scene.motes.append(self.mote(100.1, 100.1, FINE_DUST))
        frame = numpy.asarray(scene.draw(wall_frame()))
        changed = numpy.argwhere((frame != WALL).any(axis=2))
        self.assertEqual(len(changed), 1)
        row, column = changed[0]
        self.assertEqual(tuple(int(value) for value in frame[row, column, :3]),
                         tuple(int(value) for value in COLOURS.nearest(*palette()[FINE_DUST.ink][:3])[:3]))

    def test_a_coarse_grain_is_soft_in_the_dark_and_shows_what_is_under_it(self):
        scene = still_ambience(room_air())
        self.assertLess(scene.dust_colour(self.mote(100.0, 100.0))[3], 0.75)
        scene.motes.append(self.mote(100.2, 100.2))
        frame = scene.draw(wall_frame())
        self.assertGreater(int((numpy.asarray(frame) != WALL).any(axis=2).sum()), 4)

    def test_a_glint_flashes_a_fine_grain_towards_the_fire(self):
        # An opaque grain has no strength left to give, so it is the colour that flashes.
        scene = still_ambience(room_air(flames=[(300, 200)], torches=[burning_torch()]))
        mote = self.mote(300, 200, FINE_DUST)
        shine = palette()[DUST_SHINE_INK]
        warm = palette()[DUST_WARM_INK]
        closest = math.inf
        for age in range(500, 2000):
            mote.age = age
            mote.life = age + 500
            closest = min(closest, sum(abs(value - target) for value, target in zip(scene.dust_colour(mote)[:3], shine)))
        self.assertLess(closest, sum(abs(a - b) for a, b in zip(warm, shine)) * 0.8)

    def test_dust_is_as_lit_as_the_traced_air_it_is_in(self):
        # By distance alone, a grain behind a ledge shone as if it could see the flame.
        art = burning_torch()
        lit_air = art.lit_air * 0
        scene = still_ambience(room_air(flames=[(300, 200)], torches=[replace(art, lit_air=lit_air)]))
        self.assertEqual(scene.light_at(310, 200)[0], 0.0)
        scene = still_ambience(room_air(flames=[(300, 200)], torches=[art]))
        self.assertGreater(scene.light_at(310, 200)[0], 0.5)
        self.assertEqual(scene.light_at(20, 20)[0], 0.0)

    def test_dust_takes_the_colour_of_the_light_on_it(self):
        pool = {x: 200 for x in range(300, 340)}
        scene = still_ambience(room_air(flames=[(100, 100)], pools=[pool], torches=[burning_torch(100, 100)]))
        by_flame = scene.dust_colour(self.mote(105, 100))[:3]
        by_pool = scene.dust_colour(self.mote(320, 180))[:3]
        self.assertNotEqual(by_flame, by_pool)
        self.assertEqual(by_flame, palette()[DUST_WARM_INK][:3])
        self.assertEqual(by_pool, palette()[210][:3])

    def test_dust_over_the_lava_stays_dimmer_than_by_the_flame(self):
        # The user wanted the lava's grains of ash, not a brighter haze.
        pool = {x: 200 for x in range(300, 340)}
        scene = still_ambience(room_air(flames=[(100, 100)], pools=[pool], torches=[burning_torch(100, 100)]))
        by_pool = scene.dust_colour(self.mote(320, 190))
        by_flame = [scene.dust_colour(replace(self.mote(100, 100), age=age))[3] for age in range(500, 540)]
        self.assertLessEqual(by_pool[3], min(by_flame))


class AshTests(unittest.TestCase):
    def pool(self):
        return {x: 228 for x in range(300, 340)}

    def test_a_grain_rises_from_the_surface_of_the_lava(self):
        scene = still_ambience(room_air(pools=[self.pool()]))
        with patch.object(scene.rng, 'random', return_value=0.0):
            scene.advance()
        self.assertEqual(len(scene.ash), 1)
        grain = scene.ash[0]
        self.assertIn(int(grain.x), self.pool())
        self.assertLess(abs(grain.y - 226), 2)

    def test_one_grain_at_a_time(self):
        # The second pass burst several together, and that was not subtle.
        scene = still_ambience(room_air(pools=[self.pool()]))
        with patch.object(scene.rng, 'random', return_value=0.0):
            for count in range(1, MOST_ASH + 1):
                scene.advance()
                self.assertEqual(len(scene.ash), count)
            scene.advance()
        self.assertEqual(len(scene.ash), MOST_ASH)

    def test_ash_is_a_single_crisp_pixel_of_the_palette(self):
        scene = still_ambience(room_air())
        scene.ash.append(Ash(320.6, 200.4, 0.0, 0.6, 0.0, 60.0))
        frame = scene.draw(wall_frame())
        self.assertEqual(colours_in(frame), {WALL, palette()[ASH_INKS[0]]})
        self.assertEqual(frame.getpixel((320, 200)), palette()[ASH_INKS[0]])

    def test_a_grain_rises_cools_and_goes_out(self):
        scene = still_ambience(room_air())
        grain = Ash(320.0, 220.0, 0.0, 0.6, 0.0, 60.0)
        scene.ash.append(grain)
        heights, inks = [], []
        for _ in range(55):
            scene.advance()
            heights.append(grain.y)
            inks.append(next(ink for _x, _y, ink in scene.crisp_pixels()))
        self.assertEqual(heights, sorted(heights, reverse=True))
        self.assertEqual(inks[0], ASH_INKS[0])
        self.assertEqual(inks[-1], ASH_INKS[-1])
        self.assertTrue(run_until(scene, lambda: grain not in scene.ash))

    def test_the_flame_lets_go_of_a_grain_now_and_then(self):
        scene = still_ambience(room_air(flames=[(100, 100)]))
        with patch.object(scene.rng, 'random', return_value=0.0):
            scene.advance()
        grain = scene.ash[0]
        self.assertLess(abs(grain.x - 100), 5)
        self.assertLess(grain.y, 96)

    def test_ash_stays_rare(self):
        # A little more often than the first pass's 0.022 a tick for a pool,
        # and no more than that: this is the amount the user asked for.
        scene = still_ambience(room_air(pools=[self.pool()]))
        with patch.object(scene, 'new_ash', wraps=scene.new_ash) as born:
            for _ in range(12000):
                scene.advance()
                self.assertLessEqual(len(scene.ash), MOST_ASH)
        self.assertGreater(born.call_count / 12000, 0.022)
        self.assertLess(born.call_count / 12000, 0.05)


def without_light(art):
    """The same torch casting no light, to see the wall under it."""
    firelight = replace(art.firelight, rest=art.firelight.rest * 0)
    return replace(art, firelight=firelight, light=replace(art.light, falloff=art.light.falloff * 0))


class TorchTests(unittest.TestCase):
    """Six frames: a flame growing in one column, over a painted vein, with a
    square of loose pixels that differ from frame to frame."""

    LEFT, TOP = 100, 120
    VEIN = (48, 28, 24, 255)
    LOOSE = (72, 48, 40, 255)
    FLAME = (255, 127, 0, 255)

    def art(self):
        frames = numpy.zeros((6, 16, 12, 4), dtype=numpy.uint8)
        frames[...] = WALL
        frames[:, 0] = 0
        frames[:, 2:6, 1:3] = self.VEIN
        for index in range(6):
            frames[index, 12 - index:13, 3] = self.FLAME
        frames[2:, 2:6, 6:10] = self.LOOSE
        unlit = numpy.array(frames[0])
        unlit[frames[0, ..., 0] == self.FLAME[0]] = WALL
        unlit[2:6, 1:3] = WALL
        return read_torch(frames, unlit, self.LEFT, self.TOP, scenery(WALL), COLOURS.firelight)

    def scene(self, **options):
        art = self.art()
        return still_ambience(room_air(torches=[art], **options)), art

    def painted(self, art, index=0):
        frame = wall_frame()
        sprite = Image.fromarray(art.frames[index])
        frame.paste(sprite, (self.LEFT, self.TOP), sprite)
        return frame

    def test_the_flame_stays_the_one_the_game_drew(self):
        # Choosing the frames here made the flame choppy.
        scene, art = self.scene()
        for index in range(6):
            frame = self.painted(art, index)
            before = numpy.asarray(frame.crop(art.box)).copy()
            scene.draw(frame)
            flame = before[..., 0] == self.FLAME[0]
            self.assertTrue((before[flame] == numpy.asarray(frame.crop(art.box))[flame]).all())

    def walls(self):
        art = without_light(self.art())
        scene = still_ambience(room_air(torches=[art]))
        for index in range(6):
            scene.advance()
            yield art, numpy.array(scene.draw(self.painted(art, index)).crop(art.box))

    def test_the_loose_pixels_stop_blinking(self):
        # Two lightings blinked at random, and looked low effort.
        art, first = next(self.walls())
        rock = ~art.flame.any(axis=0) & (art.frames[0, ..., 3] > 0)
        for _art, wall in self.walls():
            self.assertTrue((wall[rock] == first[rock]).all())

    def test_a_loose_pixel_keeps_the_colour_it_shows_most(self):
        _art, wall = next(self.walls())
        self.assertEqual(tuple(wall[3, 7]), self.LOOSE)

    def test_the_painted_wall_stays(self):
        # With the unlit recess in its place the wall came out plain and clean.
        _art, wall = next(self.walls())
        self.assertTrue((wall[2:6, 1:3] == self.VEIN).all())

    def test_it_stays_in_the_palette(self):
        scene, art = self.scene()
        allowed = {tuple(colour) + (255,) for colour in COLOURS.rgb.tolist()}
        for _ in range(60):
            scene.advance()
            self.assertLessEqual(colours_in(scene.draw(self.painted(art, 3))), allowed)

    def test_what_is_drawn_over_the_torch_stays(self):
        scene, art = self.scene()
        frame = self.painted(art, 4)
        left, top = self.LEFT + 6, self.TOP + 2
        frame.paste(Image.new('RGBA', (4, 4), COVER), (left, top))
        scene.draw(frame)
        self.assertEqual(colours_in(frame.crop((left, top, left + 4, top + 4))), {COVER})

    def test_a_room_without_the_torch_on_screen_gets_none(self):
        scene, _art = self.scene()
        self.assertEqual(colours_in(scene.draw(Image.new('RGBA', (WIDTH, HEIGHT), COVER))), {COVER})

    def test_it_uses_no_game_randomness(self):
        scene, art = self.scene()
        before = random.getstate()
        for _ in range(100):
            scene.advance()
            scene.draw(self.painted(art))
        self.assertEqual(random.getstate(), before)


class TorchInViewTests(unittest.TestCase):
    def torch(self, in_front=None):
        frames = burning_torch(300, 200).frames
        return read_torch(frames, frames[0], 285, 180, scenery(), COLOURS.firelight, in_front)

    def in_front(self, left=0, right=WIDTH):
        mask = numpy.zeros((HEIGHT, WIDTH), dtype=bool)
        mask[:, left:right] = True
        return mask

    def test_rock_in_front_of_a_torch_takes_no_light(self):
        # Lit, the pillars and walls in front of a torch stood out as pale plates.
        mask = self.in_front(320, 340)
        open_room, walled = self.torch().firelight, self.torch(mask).firelight
        front = mask[walled.top:walled.top + walled.rest.shape[0], walled.left:walled.left + walled.rest.shape[1]]
        self.assertTrue(front.any())
        reach = numpy.ones(DIRECTIONS)
        self.assertGreater(open_room.at(reach, 1.0)[front].max(), 0.05)
        self.assertEqual(walled.at(reach, 1.0)[front].max(), 0.0)
        numpy.testing.assert_array_equal(open_room.at(reach, 1.0)[~front], walled.at(reach, 1.0)[~front])

    def test_the_air_before_that_rock_is_still_lit(self):
        mask = self.in_front(320, 340)
        numpy.testing.assert_array_equal(self.torch().lit_air, self.torch(mask).lit_air)

    def test_a_torch_shut_behind_a_pillar_does_not_show(self):
        torch = self.torch()
        self.assertTrue(shows(torch, self.in_front(0, 0)))
        self.assertFalse(shows(torch, self.in_front(0, WIDTH)))
        # Half of it in view still counts: most torches stand a little behind one.
        half = torch.left + torch.frames.shape[2] // 2
        self.assertTrue(shows(torch, self.in_front(half, WIDTH)))

    def test_a_torch_listed_twice_is_one_torch(self):
        record = {'command': ['back', 3583, 149, 329, 16, 2, [245, 149, 329, 195], 4, 2, 2]}
        other = {'command': ['back', 3583, 149, 329, 16, 2, [245, 149, 329, 195], 4, 3, 2]}
        third = {'command': ['back', 3586, 455, 329, 16, 2, [245, 455, 329, 501], 4, 8, 2]}
        program = {'torches': {'0': [record, other, third]}}
        self.assertEqual([flame_of(found) for found in room_torches(program, 0)], [(172, 287), (478, 287)])
        self.assertEqual(room_torches(program, 1), ())


class SteadyWallTests(unittest.TestCase):
    def test_behind_the_flame_it_uses_the_frames_where_the_wall_shows(self):
        frames = numpy.zeros((3, 4, 4, 4), dtype=numpy.uint8)
        frames[...] = WALL
        frames[0, 1, 1] = FIRE
        frames[1:, 1, 1] = ROCK
        flame = flame_pixels(frames)
        self.assertEqual(tuple(steady_wall(frames, flame, numpy.array(frames[0]))[1, 1]), ROCK)

    def test_behind_the_flame_in_every_frame_there_is_the_unlit_recess(self):
        frames = numpy.zeros((3, 4, 4, 4), dtype=numpy.uint8)
        frames[...] = WALL
        frames[:, 1, 1] = FIRE
        unlit = numpy.array(frames[0])
        unlit[1, 1] = ROCK
        self.assertEqual(tuple(steady_wall(frames, flame_pixels(frames), unlit)[1, 1]), ROCK)


class FlickerTests(unittest.TestCase):
    def flicker(self):
        still = numpy.zeros(DIRECTIONS)
        return Flicker(numpy.zeros((1, 1), dtype=numpy.int32), still, still)

    def test_it_starts_as_traced(self):
        self.assertTrue((self.flicker().reach == 1).all())

    def test_a_frame_moves_the_licks_at_once_and_the_breath_slowly(self):
        flicker, outline = self.flicker(), numpy.full(DIRECTIONS, 0.1)
        flicker.follow(outline, 1.0)
        self.assertAlmostEqual(float(flicker.quick[0]), 0.1 * QUICK_FOLLOW)
        self.assertAlmostEqual(float(flicker.slow[0]), 0.1 * SLOW_FOLLOW)
        self.assertGreater(QUICK_FOLLOW, SLOW_FOLLOW * 2)

    def test_each_way_moves_by_itself(self):
        flicker, outline = self.flicker(), numpy.zeros(DIRECTIONS)
        outline[:6] = 0.2
        outline[20:26] = -0.2
        flicker.follow(outline, 1.0)
        reach = flicker.reach
        self.assertGreater(reach[3], 1)
        self.assertLess(reach[22], 1)
        self.assertEqual(reach[40], 1)

    def test_the_light_never_runs_away_or_shuts(self):
        flicker = self.flicker()
        flicker.follow(numpy.full(DIRECTIONS, 9.0), 1.0)
        self.assertEqual(float(flicker.reach.max()), LONGEST_REACH)
        flicker = self.flicker()
        flicker.follow(numpy.full(DIRECTIONS, -9.0), 1.0)
        self.assertEqual(float(flicker.reach.min()), SHORTEST_REACH)

    def test_a_hot_frame_burns_brighter_by_more_than_it_is_hotter(self):
        flicker = self.flicker()
        for _ in range(30):
            flicker.follow(numpy.zeros(DIRECTIONS), 1.1)
        self.assertGreater(flicker.burn, 1.2)


class CrackTests(unittest.TestCase):
    CRACK = (127, 0, 0, 255)
    DARK_RED = (74, 16, 8, 255)

    def colours(self):
        colours = palette()
        colours.update({400: self.CRACK, 401: self.DARK_RED, 402: (99, 41, 24, 255), 403: (115, 66, 33, 255)})
        return Colours(colours)

    def test_painted_cracks_do_not_receive_light(self):
        # Lifting them broke their thin lines into dashes and dots.
        colours = self.colours()
        crack = int(numpy.searchsorted(colours.keys, 127 << 16))
        self.assertFalse(colours.receives[crack])

    def test_dark_rock_does_not_turn_into_a_crack(self):
        # It came out as new red dots along the lines.
        colours = self.colours()
        lit = {tuple(colour) for colour in colours.firelight[:, colours.receives].reshape(-1, 3).tolist()}
        self.assertNotIn(self.CRACK[:3], lit)

    def test_rock_with_a_little_red_still_takes_light(self):
        colours = self.colours()
        dark_red = int(numpy.searchsorted(colours.keys, 74 << 16 | 16 << 8 | 8))
        self.assertTrue(colours.receives[dark_red])


class FlamePixelTests(unittest.TestCase):
    RIM = (127, 0, 0, 255)
    BLUE = (44, 94, 157, 255)

    def test_the_rim_and_the_blue_heart_are_flame(self):
        frames = numpy.zeros((1, 12, 12, 4), dtype=numpy.uint8)
        frames[...] = WALL
        frames[0, 5:8, 5:7] = FIRE
        frames[0, 8, 5:7] = self.BLUE
        frames[0, 4, 5:7] = self.RIM
        flame = flame_pixels(frames)
        self.assertEqual(int(flame.sum()), 10)

    def test_the_same_red_painted_on_the_wall_is_not(self):
        # Kept as flame, it left red specks all over the lit recess.
        frames = numpy.zeros((1, 30, 30, 4), dtype=numpy.uint8)
        frames[...] = WALL
        frames[0, 5:8, 5:7] = FIRE
        frames[0, 25, 25] = self.RIM
        self.assertFalse(flame_pixels(frames)[0, 25, 25])

    def test_transparent_pixels_are_nothing(self):
        frames = numpy.zeros((1, 4, 4, 4), dtype=numpy.uint8)
        frames[0, :, :, 0] = 255
        self.assertFalse(flame_pixels(frames).any())


class FirelightTests(unittest.TestCase):
    """Three frames: a flame on the left of the recess, one on the right, a small one."""

    LEFT, TOP = 200, 150

    def art(self):
        frames = numpy.zeros((3, 60, 40, 4), dtype=numpy.uint8)
        frames[...] = ROCK
        frames[0, 20:40, 8:12] = FIRE
        frames[1, 20:40, 28:32] = FIRE
        frames[2, 28:32, 18:22] = FIRE
        unlit = numpy.array(frames[0])
        unlit[...] = ROCK
        return read_torch(frames, unlit, self.LEFT, self.TOP, scenery(), COLOURS.firelight)

    def scene(self):
        art = self.art()
        return still_ambience(room_air(torches=[art])), art

    def painted(self, art, index):
        frame = Image.new('RGBA', (WIDTH, HEIGHT), ROCK)
        sprite = Image.fromarray(art.frames[index])
        frame.paste(sprite, (self.LEFT, self.TOP), sprite)
        return frame

    def warmth(self, frame, art):
        left, top, right, bottom = art.light.box
        return numpy.asarray(frame)[top:bottom, left:right, 0].astype(float)

    def play(self, scene, art, indices):
        for index in indices:
            scene.advance()
            scene.draw(self.painted(art, index))

    def test_each_frame_says_how_far_it_burns_each_way(self):
        outlines = self.art().firelight.outlines
        leftwards, rightwards = 0, DIRECTIONS // 2
        self.assertGreater(outlines[0, leftwards], outlines[1, leftwards])
        self.assertLess(outlines[0, rightwards], outlines[1, rightwards])

    def test_a_small_flame_burns_less(self):
        art = self.art()
        self.assertLess(art.firelight.burn[2], art.firelight.burn[0])

    def test_the_light_goes_to_the_side_the_flame_is_on(self):
        scene, art = self.scene()
        sides = []
        for index in (0, 1):
            self.play(scene, art, [index] * 60)
            frame = scene.draw(self.painted(art, index))
            warmth = self.warmth(frame, art)
            middle = warmth.shape[1] // 2
            sides.append(warmth[:, :middle].mean() - warmth[:, middle:].mean())
        self.assertGreater(sides[0], 0)
        self.assertLess(sides[1], 0)

    def test_the_light_moves_once_a_tick(self):
        scene, art = self.scene()
        self.play(scene, art, [0] * 5)
        flicker = scene.flickers[0]
        before = flicker.quick.copy(), flicker.slow.copy(), flicker.burn, flicker.steps.copy()
        scene.draw(self.painted(art, 1))
        self.assertTrue((flicker.quick == before[0]).all())
        self.assertTrue((flicker.slow == before[1]).all())
        self.assertEqual(flicker.burn, before[2])
        self.assertTrue((flicker.steps == before[3]).all())

    def test_the_light_takes_the_shape_of_the_flame_it_follows(self):
        scene, art = self.scene()
        for index in (0, 1):
            self.play(scene, art, [index] * 80)
            reach = scene.flickers[0].reach
            wanted = 1 + art.firelight.outlines[index] * (QUICK_DEPTH + SLOW_DEPTH)
            self.assertTrue(numpy.allclose(reach, wanted.clip(SHORTEST_REACH, LONGEST_REACH), atol=0.01))

    def test_a_pixel_keeps_its_step_while_the_light_only_trembles(self):
        # A third of the pixels that changed used to flip straight back.
        def flips(hold):
            art = self.art()
            firelight = replace(art.firelight, outlines=art.firelight.outlines * 0,
                                burn=numpy.array((0.995, 1.005, 1.0)))
            trembling = replace(art, firelight=firelight)
            scene = still_ambience(room_air(torches=[trembling]))
            count = 0
            with patch('pop2.cavern_ambience.LIGHT_HOLD', hold):
                self.play(scene, trembling, [2] * 5)
                for index in (0, 1, 2) * 20:
                    before = scene.flickers[0].steps.copy()
                    self.play(scene, trembling, [index])
                    count += int((scene.flickers[0].steps != before).sum())
            return count

        self.assertEqual(flips(LIGHT_HOLD), 0)
        self.assertGreater(flips(-0.5), 0)

    def test_a_pixel_follows_a_light_that_really_moved(self):
        scene, art = self.scene()
        self.play(scene, art, [0] * 60)
        before = scene.flickers[0].steps.copy()
        self.play(scene, art, [1] * 60)
        self.assertGreater(int((scene.flickers[0].steps != before).sum()), 100)

    def test_a_second_render_of_one_tick_draws_the_same_frame(self):
        scene, art = self.scene()
        for _ in range(30):
            scene.advance()
            first = scene.draw(self.painted(art, 1)).tobytes()
            self.assertEqual(scene.draw(self.painted(art, 1)).tobytes(), first)

    def test_it_stays_in_the_palette(self):
        scene, art = self.scene()
        allowed = {tuple(colour) + (255,) for colour in COLOURS.rgb.tolist()}
        self.assertLessEqual(colours_in(scene.draw(self.painted(art, 0))), allowed)

    def test_fire_does_not_receive_light(self):
        scene, art = self.scene()
        frame = scene.draw(self.painted(art, 0))
        self.assertEqual(frame.getpixel((self.LEFT + 9, self.TOP + 30)), FIRE)

    def test_a_colour_outside_the_palette_is_left_alone(self):
        strange = (11, 222, 33, 255)
        scene, art = self.scene()
        frame = self.painted(art, 0)
        frame.paste(Image.new('RGBA', (4, 4), strange), (self.LEFT - 6, self.TOP + 30))
        scene.draw(frame)
        self.assertEqual(frame.getpixel((self.LEFT - 4, self.TOP + 31)), strange)

    def test_there_is_no_light_without_a_torch_on_screen(self):
        scene, _art = self.scene()
        self.assertEqual(colours_in(scene.draw(Image.new('RGBA', (WIDTH, HEIGHT), WALL))), {WALL})

    def test_the_table_steps_every_palette_colour_through_the_levels(self):
        table = COLOURS.firelight
        self.assertEqual(table.shape, (LIGHT_LEVELS + 1, len(COLOURS.rgb), 3))
        rock = COLOURS.receives
        self.assertTrue((table[0][rock] == COLOURS.rgb[rock]).all())

    def test_lit_rock_never_turns_into_fire(self):
        # Pale rock came out as orange specks along the top of the pillar.
        fire = {tuple(colour) for colour in COLOURS.rgb[~COLOURS.receives].tolist()}
        self.assertTrue(fire)
        for table in (COLOURS.firelight, COLOURS.lavalight):
            lit = {tuple(colour) for colour in table[:, COLOURS.receives].reshape(-1, 3).tolist()}
            self.assertFalse(lit & fire)


class LavaGlowTests(unittest.TestCase):
    def scene(self):
        pool = {x: 228 for x in range(300, 340)}
        return still_ambience(room_air(pools=[pool], pool_glows=True))

    def test_it_warms_the_rock_by_the_pool_and_nothing_further(self):
        frame = Image.new('RGBA', (WIDTH, HEIGHT), ROCK)
        self.scene().draw(frame)
        pixels = numpy.asarray(frame)[..., :3].astype(int)
        changed = numpy.argwhere((pixels != ROCK[:3]).any(axis=2))
        self.assertTrue(len(changed))
        self.assertGreaterEqual(changed[:, 1].min(), 300 - LIGHT_REACH)
        self.assertLessEqual(changed[:, 1].max(), 340 + LIGHT_REACH)
        self.assertGreaterEqual(changed[:, 0].min(), 228 - LIGHT_REACH)
        self.assertLess(changed[:, 0].max(), 228 + LIGHT_REACH)
        self.assertGreater(pixels[215:228, 310:330, 0].mean(), pixels[178:183, 310:330, 0].mean())

    def test_the_lava_itself_receives_nothing(self):
        frame = Image.new('RGBA', (WIDTH, HEIGHT), FIRE)
        self.assertEqual(colours_in(self.scene().draw(frame)), {FIRE})

    def test_it_breathes_too_little_and_too_slowly_to_pulse(self):
        scene = self.scene()
        strengths = []
        for _ in range(1500):
            scene.advance()
            strengths.append(scene.pool_strength())
        self.assertLess(max(strengths) - min(strengths), 0.2)
        self.assertLess(max(abs(after - before) for before, after in zip(strengths, strengths[1:])), 0.01)


class LavaLightTests(unittest.TestCase):
    LIQUID = {x: (222, 234) for x in range(300, 360)}

    def light(self, shades=None, liquid=None):
        left, top, light = trace_lavalight(plain_rock() if shades is None else shades, liquid or self.LIQUID)
        room = numpy.zeros((HEIGHT, WIDTH), dtype=numpy.float32)
        room[top:top + light.shape[0], left:left + light.shape[1]] = light
        return room

    def test_it_is_strongest_by_the_pool_and_runs_out(self):
        room = self.light()
        self.assertGreater(room[215, 330], 2 * room[190, 330])
        self.assertEqual(room[228 - LIGHT_REACH - 1:, 300 - LIGHT_REACH - 1].max(), 0)
        self.assertEqual(room[228 - LIGHT_REACH - 1, 330], 0)

    def test_all_of_it_is_between_nothing_and_full(self):
        room = self.light()
        self.assertGreaterEqual(float(room.min()), 0)
        self.assertLessEqual(float(room.max()), 1)
        self.assertGreater(float(room.max()), 0.5)

    def test_lava_is_a_hollow_however_bright_it_is_painted(self):
        dark, bright = plain_rock(), plain_rock()
        dark[222:235, 300:360] = 0
        bright[222:235, 300:360] = 1
        numpy.testing.assert_allclose(self.light(dark), self.light(bright), atol=1e-6)

    def test_it_follows_the_veins_of_the_rock(self):
        shades = plain_rock()
        shades[180:215, ::7] = 0.9
        shades[180:215, 1::7] = 0.9
        # From one pixel to the next, as the slow change along a row is the same on both.
        veined = numpy.abs(numpy.diff(self.light(shades)[200, 305:355])).mean()
        plain = numpy.abs(numpy.diff(self.light()[200, 305:355])).mean()
        self.assertGreater(float(veined), 3 * float(plain))

    def test_a_ridge_shades_what_is_behind_it(self):
        shades = plain_rock()
        shades[205:209, :] = 1.0
        ridged = self.light(shades)[185:200, 310:350].mean()
        self.assertLess(float(ridged), float(self.light()[185:200, 310:350].mean()))

    def test_a_pool_of_a_few_pixels_still_lights(self):
        room = self.light(liquid={x: (222, 226) for x in range(300, 304)})
        self.assertGreater(float(room.max()), 0.5)

    def test_rock_rising_in_front_takes_no_light(self):
        in_front = nothing_in_front()
        in_front[150:228, 380:400] = True
        glow = pool_glow(self.LIQUID, plain_rock(), in_front, COLOURS)
        left, top = glow.box[:2]
        self.assertTrue((glow.falloff[150 - top:228 - top, 380 - left:400 - left] == 0).all())
        self.assertGreater(glow.falloff[210 - top:228 - top, 362 - left:380 - left].max(), 0.1)

    def test_the_floor_before_a_pool_takes_light(self):
        # The foreground starts there: the light used to stop dead along that line.
        in_front = nothing_in_front()
        in_front[235:, :] = True
        glow = pool_glow(self.LIQUID, plain_rock(), in_front, COLOURS)
        left, top = glow.box[:2]
        self.assertGreater(glow.falloff[240 - top:245 - top, 320 - left:340 - left].min(), 0.1)

    def test_it_warms_the_rock_more_than_it_brightens_it(self):
        lit = COLOURS.lavalight[LIGHT_LEVELS]
        for colour, step in zip(COLOURS.rgb, lit):
            if colour[0] in (ROCK[0],):
                self.assertLessEqual(int(step[0]) - int(colour[0]), 60)


class HazeTests(unittest.TestCase):
    TOPS = {x: 200 for x in range(100, 160)}

    def haze(self, in_front=None, height=30, strength=1.1, tops=None):
        in_front = numpy.zeros((HEIGHT, WIDTH), dtype=bool) if in_front is None else in_front
        return haze_over(self.TOPS if tops is None else tops, in_front, height, strength)

    def striped(self):
        """A frame in which every column has its own colour, to see where pixels go."""
        frame = numpy.zeros((HEIGHT, WIDTH, 4), dtype=numpy.uint8)
        frame[..., 0] = numpy.arange(WIDTH)[None, :] % 251
        frame[..., 1] = numpy.arange(WIDTH)[None, :] // 251
        frame[..., 3] = 255
        return Image.fromarray(frame)

    def moved(self, haze, tick):
        scene = still_ambience(room_air(hazes=[haze]))
        scene.tick = tick
        frame = self.striped()
        scene.shimmer(frame, haze)
        return numpy.array(frame).astype(numpy.int32), numpy.array(self.striped()).astype(numpy.int32)

    def test_a_pixel_moves_one_pixel_at_the_most(self):
        for options in (HAZE_OVER_FLAME, HAZE_OVER_POOL):
            for tick in range(40):
                after, before = self.moved(self.haze(**options), tick)
                self.assertLessEqual(numpy.abs(after[..., 0] - before[..., 0]).max(), 1)

    def test_pixels_are_only_moved_so_no_new_colour_appears(self):
        after, before = self.moved(self.haze(), 7)
        self.assertLessEqual({tuple(pixel) for pixel in after.reshape(-1, 4)},
                             {tuple(pixel) for pixel in before.reshape(-1, 4)})

    def test_it_is_light_only_some_of_the_air_moves(self):
        after, before = self.moved(self.haze(**HAZE_OVER_POOL), 7)
        rows = (after != before).any(axis=2)
        share = rows.sum() / self.haze(**HAZE_OVER_POOL).bend.size
        self.assertGreater(share, 0.03)
        self.assertLess(share, 0.3)

    def test_it_thins_out_as_it_rises_and_ends(self):
        bend = self.haze().bend.max(axis=1)
        self.assertEqual(list(bend), sorted(bend))
        self.assertEqual(bend[0], 0)
        self.assertGreater(bend[-1], 0.9)

    def test_it_thins_out_at_the_sides(self):
        bend = self.haze().bend.max(axis=0)
        self.assertEqual(bend[0], 0)
        self.assertEqual(bend[-1], 0)
        self.assertGreater(bend[len(bend) // 2], 0.9)

    def test_it_starts_above_what_burns_in_each_column(self):
        tops = {x: 180 + (x - 100) // 3 for x in range(100, 160)}
        haze = self.haze(tops=tops)
        for x, top in tops.items():
            column = haze.bend[:, x - haze.left]
            self.assertTrue((column[top - haze.top:] == 0).all(), x)

    def test_it_is_behind_what_stands_in_front(self):
        in_front = numpy.zeros((HEIGHT, WIDTH), dtype=bool)
        in_front[170:200, 120:140] = True
        haze = self.haze(in_front)
        self.assertTrue((haze.bend[:, 20:40] == 0).all())
        self.assertGreater(haze.bend[:, :20].max(), 0.5)

    def test_it_stops_at_the_top_of_the_room(self):
        haze = self.haze(tops={x: 10 for x in range(100, 160)})
        self.assertEqual(haze.top, 0)
        self.assertEqual(haze.box[3], 10)

    def test_the_waves_rise(self):
        haze = self.haze()
        steps = 10
        rows = round(steps * HAZE_RISE)
        self.assertEqual(rows, steps * HAZE_RISE)
        early, _before = self.moved(haze, 20)
        late, _before = self.moved(haze, 20 + steps)
        box = haze.left, haze.top, haze.box[2], haze.box[3]
        # Taken apart from how much the air thins: which way each pixel went.
        ways = [numpy.sign(numpy.sin((numpy.arange(box[1], box[3])[:, None] + tick * HAZE_RISE) * math.tau / HAZE_WAVE
                                     + haze.phase)) for tick in (20, 20 + steps)]
        numpy.testing.assert_array_equal(ways[0][rows:], ways[1][:-rows])
        self.assertFalse(numpy.array_equal(early, late))

    def test_it_moves_once_per_game_tick(self):
        haze = self.haze()
        one, _ = self.moved(haze, 5)
        again, _ = self.moved(haze, 5)
        other, _ = self.moved(haze, 6)
        numpy.testing.assert_array_equal(one, again)
        self.assertFalse(numpy.array_equal(one, other))

    def test_it_takes_no_random_numbers(self):
        scene = still_ambience(room_air(hazes=[self.haze()]))
        before = scene.rng.getstate()
        scene.draw(wall_frame())
        self.assertEqual(scene.rng.getstate(), before)

    def test_drawing_the_room_bends_it_before_the_dust(self):
        haze = self.haze()
        scene = still_ambience(room_air(hazes=[haze]))
        scene.tick = 3
        frame = self.striped()
        with patch.object(scene, 'shimmer', wraps=scene.shimmer) as shimmer:
            scene.draw(frame)
        shimmer.assert_called_once_with(frame, haze)

    def test_a_flame_heats_the_air_from_its_top_up(self):
        torch = burning_torch(300, 200)
        haze = haze_of(torch, numpy.zeros((HEIGHT, WIDTH), dtype=bool))
        rows, _columns = numpy.nonzero(torch.flame.any(axis=0))
        self.assertEqual(haze.box[3], torch.top + rows.min())
        self.assertEqual(haze.box[1], torch.top + rows.min() - HAZE_OVER_FLAME['height'])
        self.assertLess(abs((haze.box[0] + haze.box[2]) / 2 - 300), 2)

    def test_a_flame_by_the_edge_of_the_screen_stays_on_it(self):
        nothing = numpy.zeros((HEIGHT, WIDTH), dtype=bool)
        flame = numpy.ones((1, 40, 30), dtype=bool)
        self.assertEqual(haze_of(SimpleNamespace(flame=flame, left=-10, top=100), nothing).left, 0)
        self.assertEqual(haze_of(SimpleNamespace(flame=flame, left=495, top=100), nothing).box[2], WIDTH)


class PixelArtRuleTests(unittest.TestCase):
    def busy_scene(self, **options):
        drips = [Drip(100, 50, 226, False), Drip(320, 50, 228, True)]
        pool = {x: 228 for x in range(300, 340)}
        air = room_air(drips, [(200, 150)], [pool], **options)
        return CavernAmbience(0, air, random.Random(9))

    def test_the_game_random_generator_is_never_touched(self):
        random.seed(1234)
        before = random.getstate()
        scene = self.busy_scene()
        frame = wall_frame()
        for _ in range(500):
            scene.advance()
            scene.draw(frame)
        self.assertEqual(random.getstate(), before)

    def test_every_pixel_is_opaque_and_in_the_palette(self):
        scene = self.busy_scene()
        allowed = {tuple(colour) + (255,) for colour in COLOURS.rgb.tolist()}
        for _ in range(400):
            scene.advance()
            frame = wall_frame()
            scene.draw(frame)
            self.assertLessEqual(colours_in(frame), allowed)

    def test_few_pixels_change_without_any_light(self):
        scene = self.busy_scene()
        for _ in range(400):
            scene.advance()
            frame = wall_frame()
            scene.draw(frame)
            changed = int((numpy.asarray(frame) != numpy.asarray(wall_frame())).any(axis=2).sum())
            self.assertLess(changed, 200)

    def test_nothing_is_drawn_over_the_foreground(self):
        scene = self.busy_scene(covered=blank(255))
        frame = wall_frame()
        for _ in range(400):
            scene.advance()
            scene.draw(frame)
        self.assertEqual(colours_in(frame), {WALL})

    def test_a_second_render_of_one_tick_draws_the_same_frame(self):
        # The gate presentation renders between ticks too.
        scene = self.busy_scene()
        for _ in range(100):
            scene.advance()
            first, second = wall_frame(), wall_frame()
            self.assertEqual(scene.draw(first).tobytes(), scene.draw(second).tobytes())

    def test_the_same_seed_makes_the_same_ambience(self):
        first, second = self.busy_scene(), self.busy_scene()
        for _ in range(200):
            first.advance()
            second.advance()
        self.assertEqual(first.draw(wall_frame()).tobytes(), second.draw(wall_frame()).tobytes())


class MenuTests(unittest.TestCase):
    def test_the_toggle_starts_off_beside_the_audio_items(self):
        items = GameMenu().items
        actions = [item.action for item in items]
        self.assertEqual(actions.index('ambience'), actions.index('music') + 1)
        item = items[actions.index('ambience')]
        self.assertIs(item.checked, False)
        self.assertEqual(item.shortcut, 'Alt+A')
        self.assertIs(GameMenu(cave_ambience=True).items[actions.index('ambience')].checked, True)

    def test_every_row_stays_inside_the_panel(self):
        menu = GameMenu()
        self.assertLessEqual(menu.row_rect(len(menu.items) - 1)[3], menu.PANEL[3])


@unittest.skipUnless(CAVERNS_INSTALLED, 'Imported cavern resources required')
class EveryRoomTests(unittest.TestCase):
    """What was read wrongly when the effect first ran in all 84 rooms."""

    @classmethod
    def setUpClass(cls):
        from pop2.cavern_state import CavernState
        from pop2.cavern_ambience import room_air as analyze
        from pop2.level_data import LevelDefinition
        from pop2.level_rendering import LevelRenderer
        from pop2.render_opening import load_resource_file
        from pop2.terrain import LevelMap

        cls.rooms = {}
        for number in sorted(AMBIENCE_LEVELS):
            level = LevelDefinition.read(load_resource_file('Prince.rsrc'), number)
            renderer = LevelRenderer(level, preload_room=False)
            world = CavernState()
            world.configure_entry(renderer.cavern_program.get('entry_exit'))
            world.configure_torches(renderer.cavern_program.get('torches', {}))
            world.configure_lava(renderer.cavern_program.get('lava'))
            terrain = LevelMap(level.data)
            for room in renderer.supported_rooms():
                cls.rooms[number, room] = analyze(number, room, renderer.enter_room(room, world), terrain)

    def test_all_the_rooms_are_read(self):
        self.assertEqual(len(self.rooms), 84)

    def test_no_torch_is_counted_twice(self):
        for place, air in self.rooms.items():
            self.assertEqual(len(set(air.flames)), len(air.flames), place)
            self.assertEqual(len(air.flames), len(air.torches), place)

    def test_a_torch_shut_behind_rock_is_no_fire(self):
        self.assertEqual(self.rooms[4, 1].flames, ())
        self.assertEqual(self.rooms[5, 5].flames, ((427, 167),))
        self.assertNotIn((478, 167), self.rooms[5, 10].flames)

    def test_a_torch_mostly_behind_a_pillar_still_lights_the_rock(self):
        self.assertEqual(self.rooms[3, 2].flames, ((427, 287),))
        self.assertGreater(self.rooms[3, 2].torches[0].firelight.steady.max(), 0.3)

    def test_every_pool_is_on_the_screen(self):
        for place, air in self.rooms.items():
            for columns in air.pools:
                self.assertGreater(min(columns.values()), 0, place)
        for place in ((3, 12), (3, 27), (4, 23)):
            self.assertEqual(self.rooms[place].pools, (), place)

    def test_every_pool_lights_the_rock_around_it(self):
        for place, air in self.rooms.items():
            self.assertEqual(len(air.pool_glows), len(air.pools), place)
            for glow in air.pool_glows:
                self.assertGreater(float(glow.falloff.max()), 0.5, place)
                left, top, right, bottom = glow.box
                self.assertTrue(0 <= left < right <= WIDTH and 0 <= top < bottom <= HEIGHT, place)

    def test_every_fire_heats_the_air_over_it(self):
        for place, air in self.rooms.items():
            self.assertEqual(len(air.hazes), len(air.pools) + len(air.torches), place)
            for haze in air.hazes:
                left, top, right, bottom = haze.box
                self.assertTrue(0 <= left < right <= WIDTH and 0 <= top < bottom <= HEIGHT, place)
                self.assertLess(float(haze.bend.max()), 1.5, place)

    def test_hot_air_over_a_pool_shows_and_over_most_torches_too(self):
        def moves(haze):
            return int((haze.bend >= 0.5).sum())

        pools = [moves(haze) for air in self.rooms.values() for haze in air.hazes[:len(air.pools)]]
        torches = [moves(haze) for air in self.rooms.values() for haze in air.hazes[len(air.pools):]]
        self.assertGreater(min(pools), 300)
        # A flame just under a ceiling has only that ceiling over it, in front of the air.
        self.assertGreater(sum(count > 100 for count in torches), 40)

    def test_every_drop_falls_where_it_can_be_seen(self):
        for place, air in self.rooms.items():
            for drip in air.drips:
                self.assertGreater(drip.bottom, drip.top + 40, (place, drip))
                seen = sum(not air.is_covered(drip.x, y) for y in range(drip.top + 1, min(drip.bottom, HEIGHT)))
                self.assertGreater(seen, (drip.bottom - drip.top) * 0.5, (place, drip))


@unittest.skipUnless(CAVERNS_INSTALLED, 'Imported cavern resources required')
class ChosenRoomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pop2.cavern_state import CavernState
        from pop2.cavern_ambience import room_air as analyze
        from pop2.level_data import LevelDefinition
        from pop2.level_rendering import LevelRenderer
        from pop2.render_opening import load_resource_file
        from pop2.terrain import LevelMap

        level = LevelDefinition.read(load_resource_file('Prince.rsrc'), 4)
        cls.renderer = LevelRenderer(level, preload_room=False)
        cls.world = CavernState()
        cls.world.configure_entry(cls.renderer.cavern_program.get('entry_exit'))
        cls.world.configure_torches(cls.renderer.cavern_program.get('torches', {}))
        cls.world.configure_lava(cls.renderer.cavern_program.get('lava'))
        cls.terrain = LevelMap(level.data)
        cls.art = cls.renderer.enter_room(16, cls.world)
        cls.air = analyze(4, 16, cls.art, cls.terrain)

    def test_every_room_of_a_cavern_level_has_it(self):
        self.assertEqual(AMBIENCE_LEVELS, {3, 4, 5})
        renderer = self.renderer
        renderer.enter_room(15, self.world)
        renderer.advance_ambience(15, self.terrain)
        self.assertEqual(renderer.ambience.room, 15)
        renderer.ambience = None

    def test_no_other_level_has_it(self):
        renderer = self.renderer
        with patch.object(renderer, 'level', SimpleNamespace(number=6)):
            renderer.advance_ambience(15, self.terrain)
        self.assertIsNone(renderer.ambience)
        frame = Image.new('RGBA', (WIDTH, HEIGHT))
        self.assertIs(renderer.ambient_layer(frame, 15), frame)

    def test_drops_hang_from_the_long_stalactites(self):
        self.assertEqual([(drip.x, drip.top, drip.into_lava) for drip in self.air.drips],
                         [(280, 98, False), (336, 57, True), (387, 57, True), (437, 84, False)])
        pool = self.air.pools[0]
        for drip in self.air.drips:
            if drip.into_lava:
                self.assertEqual(drip.bottom, pool[drip.x])
            else:
                self.assertIn(drip.bottom, range(223, 230))

    def test_the_torch_and_the_pool_come_from_the_room(self):
        self.assertEqual(self.air.flames, ((478, 167),))
        self.assertEqual((min(self.air.pools[0]), max(self.air.pools[0])), (331, 413))

    def test_the_torch_is_read_from_its_nine_frames(self):
        self.assertEqual(len(self.air.torches), 1)
        torch = self.air.torches[0]
        self.assertEqual(torch.box, (455, 125, 501, 209))
        self.assertEqual(len(torch.firelight.outlines), 9)
        # Each flame, and none of the hundreds of wall pixels painted around it.
        for flame in torch.flame:
            self.assertIn(int(flame.sum()), range(170, 240))

    def test_the_painted_recess_is_kept_and_nothing_on_it_blinks(self):
        torch = self.air.torches[0]
        solid = (torch.frames[0, ..., 3] > 0) & ~torch.flame.any(axis=0)
        loose = (torch.frames[..., :3] != torch.frames[0, ..., :3]).any(axis=(0, 3)) & solid
        self.assertIn(int(loose.sum()), range(90, 140))
        # The wall is as painted, but for those few pixels.
        different = (torch.wall[..., :3] != torch.frames[0, ..., :3]).any(axis=2) & solid
        self.assertLess(int(different.sum()), 80)
        self.assertLessEqual(int((different & ~loose).sum()), 0)

    def ring_around_the_flame(self, torch, inner, outer):
        left, top, right, bottom = torch.light.box
        rows, columns = numpy.mgrid[top:bottom, left:right]
        distance = numpy.hypot(columns - 478, rows - 172)
        return (distance >= inner) & (distance < outer)

    def beside_the_edge_of_the_recess(self, torch, inward):
        """Pixels a little way in from the edge of the sprite, or out from it."""
        firelight = torch.firelight
        height, width = firelight.rest.shape
        outline = numpy.zeros((height, width), dtype=bool)
        left, top = torch.left - firelight.left, torch.top - firelight.top
        drawn = torch.frames[0, ..., 3] > 0
        rows, columns = numpy.nonzero(drawn)
        outline[rows + top, columns + left] = True
        near = gaussian(outline.astype(float), 6.0)
        # Rock in front of the torch takes no light, so it says nothing of the light.
        return ((near > 0.6) if inward else ((near < 0.25) & (near > 0.03))) & (firelight.taken > 0)

    def test_the_recess_is_no_bright_plate(self):
        # Lit like the rock it stood out as an oval the shape of the sprite, the
        # same oval whatever the flame did.
        torch = self.air.torches[0]
        steady = torch.firelight.steady
        # A light kept close fades fast, so it is brighter inside. The plate was
        # 2.8 times brighter, with an edge.
        self.assertLess(steady[self.beside_the_edge_of_the_recess(torch, True)].mean(),
                        steady[self.beside_the_edge_of_the_recess(torch, False)].mean() * 2.5)

    def test_the_light_gets_out_of_the_recess(self):
        # With the flame close to the rock, the rim of the recess shut the light in.
        torch = self.air.torches[0]
        self.assertGreater(torch.firelight.steady[self.beside_the_edge_of_the_recess(torch, False)].mean(), 0.12)

    def reach_as_it_burns(self):
        firelight = self.air.torches[0].firelight
        order = random.Random(3)
        still = numpy.zeros(DIRECTIONS)
        flicker = Flicker(numpy.zeros((1, 1), dtype=numpy.int32), still, still)
        reaches = []
        for tick in range(400):
            index = order.randrange(9)
            flicker.follow(firelight.outlines[index], float(firelight.burn[index]))
            reaches.append(flicker.reach)
        return numpy.stack(reaches[40:]), flicker

    def test_the_light_changes_shape_and_does_not_only_move(self):
        # Sliding the old light into place made its next tick fit: an oval that
        # moved. Here what is left after sliding is the change of shape.
        firelight = self.air.torches[0].firelight
        reaches, _flicker = self.reach_as_it_burns()
        masks = numpy.stack([firelight.at(reach, 1.0) > 0.3 for reach in reaches[::40]])
        left = []
        for first, second in zip(masks, masks[1:]):
            fits = [(numpy.roll(numpy.roll(first, down, 0), across, 1) & second).sum()
                    / (numpy.roll(numpy.roll(first, down, 0), across, 1) | second).sum()
                    for down in range(-10, 11, 2) for across in range(-10, 11, 2)]
            left.append(1 - max(fits))
        # The old light that only moved left about 0.11.
        self.assertGreater(numpy.mean(left), 0.13)

    def test_each_way_of_the_light_keeps_to_itself(self):
        # A light that only grew and shrank would be the same oval.
        reaches, _flicker = self.reach_as_it_burns()
        self.assertGreater(reaches.std(axis=1).mean(), 0.15)
        left_and_up = numpy.corrcoef(reaches[:, 0], reaches[:, DIRECTIONS // 4])[0, 1]
        self.assertLess(abs(left_and_up), 0.8)

    def test_it_breathes_as_well_as_licks(self):
        reaches, _flicker = self.reach_as_it_burns()
        side = reaches[:, DIRECTIONS // 4]
        self.assertGreater(numpy.corrcoef(side[:-5], side[5:])[0, 1], 0.25)
        self.assertGreater(numpy.abs(numpy.diff(side)).mean(), 0.05)

    def test_the_light_stays_close_to_the_torch(self):
        # A light that went far out over the back wall made no sense for a flame in
        # a niche. How far it goes changes, and not by much.
        firelight = self.air.torches[0].firelight
        reaches, _flicker = self.reach_as_it_burns()
        rows, columns = numpy.mgrid[firelight.top:firelight.top + firelight.rest.shape[0],
                                    firelight.left:firelight.left + firelight.rest.shape[1]]
        beyond = []
        for reach in reaches[::10]:
            lit = firelight.at(reach, 1.0) > 0.3
            beyond.append(455 - int(columns[lit].min()))
        self.assertLess(numpy.mean(beyond), 10)
        self.assertLess(max(beyond), 14)
        areas = numpy.array([(firelight.at(reach, 1.0) > 0.3).sum() for reach in reaches[::20]])
        self.assertLess(areas.max(), 3700)
        self.assertGreater(areas.min(), 2300)

    def test_the_coarse_grains_are_all_in_the_room(self):
        # With three of them they were lost beside the fine ones.
        for seed in range(5):
            scene = CavernAmbience(16, self.air, random.Random(seed))
            self.assertGreaterEqual(sum(mote.kind is COARSE_DUST for mote in scene.motes), 5)

    def test_dust_keeps_to_the_colours_of_the_rock(self):
        inks = self.air.inks
        for ink in (FINE_DUST.ink, COARSE_DUST.ink, DUST_PALE_INK):
            red, green, blue, _alpha = inks[ink]
            self.assertGreaterEqual(red, green)
            self.assertGreaterEqual(green, blue)
        self.assertLess(sum(inks[FINE_DUST.ink][:3]), sum(inks[DUST_PALE_INK][:3]))

    def test_the_cracks_stay_as_they_were_painted(self):
        scene = CavernAmbience(16, replace(self.air, pool_glows=(), hazes=()), random.Random(2))
        scene.motes.clear()
        torch = self.air.torches[0]
        frame = Image.alpha_composite(self.art.background, self.art.foreground)
        sprite = Image.fromarray(torch.wall)
        frame.paste(sprite, torch.box[:2], sprite)
        left, top, right, bottom = torch.box
        before = numpy.asarray(frame)[top:bottom, left:right, :3].astype(int)
        torch_shown = Image.fromarray(torch.frames[0])
        frame.paste(torch_shown, torch.box[:2], torch_shown)
        painted = numpy.asarray(frame)[top:bottom, left:right, :3].astype(int)
        scene.advance()
        scene.draw(frame)
        after = numpy.asarray(frame)[top:bottom, left:right, :3].astype(int)
        crack = (painted == (127, 0, 0)).all(axis=2) & ~torch.flame[0]
        self.assertGreater(int(crack.sum()), 10)
        kept = crack & (before == (127, 0, 0)).all(axis=2)
        self.assertTrue((after[kept] == (127, 0, 0)).all())
        self.assertLessEqual(int(((after == (127, 0, 0)).all(axis=2) & ~crack & ~torch.flame.any(axis=0)).sum()), 0)

    def test_a_small_flame_never_puts_the_light_out(self):
        firelight = self.air.torches[0].firelight
        reach = numpy.ones(DIRECTIONS)
        small = firelight.at(reach, firelight.burn.min() ** 2.5).mean()
        large = firelight.at(reach, firelight.burn.max() ** 2.5).mean()
        self.assertGreater(small, large * 0.3)

    def test_the_light_follows_the_rock_and_is_no_ball(self):
        # At one distance from the flame, a blurred ball is even all the way round.
        torch = self.air.torches[0]
        ring = torch.firelight.steady[self.ring_around_the_flame(torch, 30, 60)]
        self.assertGreater(ring.std() / ring.mean(), 0.3)

    def test_the_lava_glow_is_fainter_than_the_torch_warmth(self):
        pool = self.air.pools[0]
        scene = CavernAmbience(16, replace(self.air, torches=(), hazes=()), random.Random(2))
        scene.motes.clear()
        frame = Image.alpha_composite(self.art.background, self.art.foreground)
        before = numpy.asarray(frame).astype(int)
        scene.draw(frame)
        change = numpy.asarray(frame).astype(int)[..., :3] - before[..., :3]
        box = self.air.pool_glows[0].box
        self.assertGreaterEqual(box[0], min(pool) - LIGHT_REACH)
        self.assertLessEqual(box[2], max(pool) + LIGHT_REACH + 1)
        self.assertEqual(change[:box[1]].max(initial=0), 0)
        self.assertEqual(change[:, :box[0]].max(initial=0), 0)
        inside = change[box[1]:box[3], box[0]:box[2]]
        self.assertLess(numpy.abs(inside).mean(), 3)

    def test_the_light_stays_on_the_rock_near_the_torch(self):
        # A wide light over everything looked like a bomb about to go off.
        scene = CavernAmbience(16, replace(self.air, pool_glows=(), hazes=()), random.Random(2))
        scene.motes.clear()
        torch = self.air.torches[0]
        frame = Image.alpha_composite(self.art.background, self.art.foreground)
        sprite = Image.fromarray(torch.frames[0])
        frame.paste(sprite, torch.box[:2], sprite)
        before = numpy.asarray(frame).astype(int)
        scene.draw(frame)
        change = numpy.abs(numpy.asarray(frame).astype(int)[..., :3] - before[..., :3]).sum(axis=2)
        rows, columns = numpy.nonzero(change)
        self.assertTrue(len(rows))
        self.assertGreaterEqual(columns.min(), 478 - LIGHT_REACH)
        self.assertGreaterEqual(rows.min(), 171 - LIGHT_REACH)
        self.assertLessEqual(rows.max(), 171 + LIGHT_REACH)
        every_row, every_column = numpy.mgrid[:HEIGHT, :WIDTH]
        far = numpy.hypot(every_column - 478, every_row - 172) > 70
        self.assertLess(change[far].mean(), 4)
        self.assertLess((change[far] > 0).mean(), 0.1)
        self.assertLess(change.mean(), 8)

    def test_colours_are_read_from_the_room_palette(self):
        from pop2.caverns import room_assets

        palette_colours = room_assets(4, 16)[2]
        for index, colour in self.air.inks.items():
            self.assertEqual(colour, tuple(palette_colours[index][:3]) + (255,))
        allowed = {tuple(colour[:3]) for colour in palette_colours.values()}
        self.assertEqual({tuple(colour) for colour in self.air.colours.rgb.tolist()}, allowed)

    def test_the_lit_room_is_still_only_the_room_palette(self):
        scene = CavernAmbience(16, self.air, random.Random(2))
        frame = Image.alpha_composite(self.art.background, self.art.foreground)
        before = colours_in(frame)
        allowed = {tuple(colour) + (255,) for colour in self.air.colours.rgb.tolist()} | before
        for _ in range(60):
            scene.advance(self.terrain)
        scene.draw(frame)
        self.assertLessEqual(colours_in(frame), allowed)

    def test_rock_is_not_open_air(self):
        # The solid row under the lava, and the floor it lies on.
        self.assertFalse(self.air.is_open(255, 300))
        self.assertFalse(self.air.is_open(200, 226))
        self.assertTrue(self.air.is_open(340, 150))

    def test_a_room_cut_cannot_keep_a_particle(self):
        # Retained pixels come from cavern_scenery (DoCleanCut 2:608c).
        renderer = self.renderer
        renderer.ambience = CavernAmbience(16, self.air, random.Random(4))
        frame = Image.alpha_composite(self.art.background, self.art.foreground)
        renderer.remember_scenery(frame)
        before = renderer.cavern_scenery.tobytes()
        renderer.ambient_layer(frame, 16)
        self.assertNotEqual(frame.tobytes(), before)
        self.assertEqual(renderer.cavern_scenery.tobytes(), before)
        renderer.ambience = None


@unittest.skipUnless(CAVERNS_INSTALLED, 'Imported cavern resources required')
class RealSceneTests(unittest.TestCase):
    """The same inputs with the toggle off and on, in the hidden real scene."""

    def harness(self):
        from tools.audit_temple_routes import Harness

        random.seed(77)
        harness = Harness(4, peaceful=False, draw=True)
        harness.scene.audio = None
        harness.scene.jump_to_room(16, row=1, x=3 * 51 + 30, facing=1)
        return harness

    def play(self, enabled):
        from tools.audit_temple_routes import press

        harness = self.harness()
        try:
            scene = harness.scene
            scene.cave_ambience_enabled = enabled
            harness.tick(20)
            press(harness, 'R', True)
            harness.tick(5)
            press(harness, 'R', False)
            harness.tick(40)
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
        self.assertIsNotNone(on.pop('drawn'))
        before, after = numpy.asarray(off.pop('view')), numpy.asarray(on.pop('view'))
        # The retained scenery above is equal too: nothing survives a cut.
        self.assertEqual(off, on)
        changed = (before != after).any(axis=2)
        self.assertTrue(changed.any())
        # The HUD strip is not part of the room.
        self.assertFalse(changed[365:].any())

    def test_it_moves_once_per_game_tick(self):
        harness = self.harness()
        self.addCleanup(harness.close)
        scene = harness.scene
        scene.cave_ambience_enabled = True
        harness.tick(2)
        renderer = scene.level_renderer
        with patch.object(renderer, 'advance_ambience', wraps=renderer.advance_ambience) as advance:
            harness.tick(5)
        self.assertEqual(advance.call_count, 5)

    def test_it_asks_for_no_frames_between_ticks(self):
        harness = self.harness()
        self.addCleanup(harness.close)
        scene = harness.scene
        scene.cave_ambience_enabled = True
        harness.tick(2)
        pending = scene.root.after
        scene.root.after = Mock(return_value='timer')
        self.addCleanup(setattr, scene.root, 'after', pending)
        # The harness replaces this on the instance.
        type(scene).schedule_next_animation(scene)
        scene.root.after.assert_called_once()
        self.assertEqual(scene.root.after.call_args.args[1], scene.advance_animation)


class SourceTests(unittest.TestCase):
    def test_the_module_imports_no_game_state(self):
        source = Path('pop2/cavern_ambience.py').read_text(encoding='utf-8')
        self.assertNotIn('cavern_state', source)
        self.assertNotIn('random.random(', source)
        self.assertNotIn('save_game', source)


if __name__ == '__main__':
    unittest.main()
