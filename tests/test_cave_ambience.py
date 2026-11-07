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
    AMBIENCE_ROOMS, ALL_INKS, ASH_INKS, Air, Ash, BRIGHT_DUST, COARSE_DUST, CavernAmbience, Colours, DUST_HEADING,
    DUST_POCKETS, DUST_POCKETS_APART, DUST_REST_DEPTH, DUST_SHINE_INK, DUST_WARM_INK, Drip, FINE_DUST, FLASH_INKS,
    Flicker,
    HEAT_REACH, HEIGHT, LIGHT_HOLD, LIGHT_LEVELS, LONGEST_REACH, MOST_ASH, MOST_DUST, Mote, POOL_GLOW_REACH, QUICK_DEPTH,
    QUICK_FOLLOW, SHORTEST_REACH, SLOW_DEPTH, SLOW_FOLLOW, SPLASH_INKS, STEAM_INKS, SWELL_TICKS, WIDTH,
    flame_pixels, glow_along, landing, on_the_pixels, read_torch, soft_spot, stalactite_tips, steady_wall,
)
from pop2.firelight import DIRECTIONS, LIGHT_REACH, gaussian
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


def room_air(drips=(), flames=(), pools=(), opened=255, covered=None, pool_glows=False, torches=()):
    centres = tuple((sum(columns) / len(columns), sum(columns.values()) / len(columns)) for columns in pools)
    return Air(blank(opened), covered if covered is not None else blank(), tuple(drips), tuple(flames),
               tuple(pools), COLOURS, palette(), centres,
               tuple(glow_along(columns, POOL_GLOW_REACH, COLOURS.lavalight) for columns in pools if pool_glows),
               tuple(torches))


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
        for kind in (FINE_DUST, BRIGHT_DUST, COARSE_DUST):
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
        rising = strengths[:COARSE_DUST.fade_in // 2 + 1]
        falling = strengths[-(COARSE_DUST.fade_out // 2 + 1):]
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
            self.assertLessEqual(mote.life, FINE_DUST.life[1])

    def test_dust_gathers_in_a_few_pockets_of_air(self):
        # Evenly spread and falling, it looked like snow.
        scene = CavernAmbience(0, room_air(flames=[(255, 180)]), random.Random(3))
        self.assertEqual(len(scene.pockets), DUST_POCKETS)
        for index, (x, y) in enumerate(scene.pockets):
            for other_x, other_y in scene.pockets[index + 1:]:
                self.assertGreater(math.hypot(x - other_x, y - other_y), DUST_POCKETS_APART)
        with patch('pop2.cavern_ambience.DUST_BY_FLAME', 0.0), patch('pop2.cavern_ambience.DUST_BY_POOL', 0.0):
            for _ in range(100):
                mote = scene.new_mote()
                nearest = min(math.hypot(mote.x - x, mote.y - y) for x, y in scene.pockets)
                self.assertLess(nearest, 90)

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
        self.assertEqual(scene.dust_colour(self.mote(20, 20, BRIGHT_DUST))[3], 1.0)
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

    def test_there_is_little_dust_and_nearly_all_of_it_is_fine(self):
        # Sixty grains, a lot of them coarse, looked like snow.
        self.assertLess(MOST_DUST, 35)
        self.assertGreater(FINE_DUST.count, 3 * BRIGHT_DUST.count)
        self.assertLessEqual(COARSE_DUST.count, 3)

    def test_the_coarse_grains_are_the_slowest(self):
        self.assertLess(COARSE_DUST.speed[1], FINE_DUST.speed[1])
        coarse = [math.hypot(mote.dx, mote.dy) for mote in self.grains(COARSE_DUST)]
        fine = [math.hypot(mote.dx, mote.dy) for mote in self.grains(FINE_DUST)]
        self.assertGreater(numpy.mean(fine), numpy.mean(coarse) * 1.3)

    def test_a_bright_grain_does_not_last(self):
        self.assertLess(BRIGHT_DUST.life[1], FINE_DUST.life[0] / 2)
        self.assertTrue(all(mote.life <= BRIGHT_DUST.life[1] for mote in self.grains(BRIGHT_DUST)))

    def test_only_the_coarse_grains_sink(self):
        self.assertFalse(any(mote.sink for mote in self.grains(FINE_DUST)))
        self.assertFalse(any(mote.sink for mote in self.grains(BRIGHT_DUST)))
        share = numpy.mean([mote.sink > 0 for mote in self.grains(COARSE_DUST)])
        self.assertGreater(share, 0.6)
        self.assertLess(share, 1.0)

    def test_a_sinking_grain_lives_past_where_it_was_heading(self):
        grain = next(mote for mote in self.grains(COARSE_DUST) if mote.sink)
        self.assertGreaterEqual(grain.life, COARSE_DUST.life[0])

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
        self.assertLess(scene.dust_colour(self.mote(100.0, 100.0))[3], 0.7)
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
        self.assertGreaterEqual(changed[:, 1].min(), 300 - POOL_GLOW_REACH[0])
        self.assertLess(changed[:, 1].max(), 340 + POOL_GLOW_REACH[0])
        self.assertGreaterEqual(changed[:, 0].min(), 228 - POOL_GLOW_REACH[1])
        self.assertLess(changed[:, 0].max(), 228 + POOL_GLOW_REACH[1])
        self.assertGreater(pixels[220:228, 310:330, 0].mean(), pixels[205:210, 310:330, 0].mean())

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

    def test_only_the_prototype_room_has_it(self):
        self.assertEqual(AMBIENCE_ROOMS, {(4, 16)})
        renderer = self.renderer
        renderer.enter_room(15, self.world)
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
        return (near > 0.6) if inward else ((near < 0.25) & (near > 0.03))

    def test_the_recess_is_no_bright_plate(self):
        # Lit like the rock it stood out as an oval the shape of the sprite, the
        # same oval whatever the flame did.
        torch = self.air.torches[0]
        steady = torch.firelight.steady
        # A light that fades is brighter inside, but not several times over.
        self.assertLess(steady[self.beside_the_edge_of_the_recess(torch, True)].mean(),
                        steady[self.beside_the_edge_of_the_recess(torch, False)].mean() * 1.5)

    def test_the_light_gets_out_of_the_recess(self):
        # With the flame close to the rock, the rim of the recess shut the light in.
        torch = self.air.torches[0]
        self.assertGreater(torch.firelight.steady[self.beside_the_edge_of_the_recess(torch, False)].mean(), 0.2)

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
        self.assertGreater(numpy.mean(left), 0.15)

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
        self.assertLess(numpy.mean(beyond), 45)
        self.assertLess(max(beyond), 62)
        areas = numpy.array([(firelight.at(reach, 1.0) > 0.3).sum() for reach in reaches[::20]])
        self.assertLess(areas.max(), 6500)
        self.assertGreater(areas.min(), 2500)

    def test_dust_keeps_to_the_colours_of_the_rock(self):
        inks = self.air.inks
        for kind in (FINE_DUST, BRIGHT_DUST, COARSE_DUST):
            red, green, blue, _alpha = inks[kind.ink]
            self.assertGreaterEqual(red, green)
            self.assertGreaterEqual(green, blue)
        self.assertLess(sum(inks[FINE_DUST.ink][:3]), sum(inks[BRIGHT_DUST.ink][:3]))

    def test_the_cracks_stay_as_they_were_painted(self):
        scene = CavernAmbience(16, replace(self.air, pool_glows=()), random.Random(2))
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
        scene = CavernAmbience(16, replace(self.air, torches=()), random.Random(2))
        scene.motes.clear()
        frame = Image.alpha_composite(self.art.background, self.art.foreground)
        before = numpy.asarray(frame).astype(int)
        scene.draw(frame)
        change = numpy.asarray(frame).astype(int)[..., :3] - before[..., :3]
        box = self.air.pool_glows[0].box
        self.assertGreaterEqual(box[0], min(pool) - POOL_GLOW_REACH[0])
        self.assertLessEqual(box[2], max(pool) + POOL_GLOW_REACH[0])
        self.assertEqual(change[:box[1]].max(initial=0), 0)
        self.assertEqual(change[:, :box[0]].max(initial=0), 0)
        inside = change[box[1]:box[3], box[0]:box[2]]
        self.assertLess(numpy.abs(inside).mean(), 3)

    def test_the_light_stays_on_the_rock_near_the_torch(self):
        # A wide light over everything looked like a bomb about to go off.
        scene = CavernAmbience(16, replace(self.air, pool_glows=()), random.Random(2))
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
        self.assertGreaterEqual(rows.min(), 172 - LIGHT_REACH)
        self.assertLessEqual(rows.max(), 172 + LIGHT_REACH)
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
