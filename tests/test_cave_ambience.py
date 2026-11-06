"""The optional cave ambience: pixels only, tied to the scenery, off by default."""

from dataclasses import replace
from pathlib import Path
import random
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy
from PIL import Image

from pop2.cavern_ambience import (
    AMBIENCE_ROOMS, ALL_INKS, ASH_INKS, Air, Ash, CavernAmbience, Colours, DUST_BRIGHTEST, DUST_FADE_IN,
    DUST_FADE_OUT, DUST_HEADING, DUST_LIFE, DUST_SPEED, Drip, FLASH_INKS, Flicker, HEIGHT, LIGHT_LEVELS,
    MOST_ASH, MOST_DUST, Mote, POOL_GLOW_REACH, RECESS_REACH, SPLASH_INKS, STEAM_INKS, SWELL_TICKS, WALL_EASE,
    WIDTH, glow_along, glow_around, landing, read_torch, stalactite_tips,
)
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


def room_air(drips=(), flames=(), pools=(), opened=255, covered=None, glows=False, pool_glows=False,
             torches=()):
    centres = tuple((sum(columns) / len(columns), sum(columns.values()) / len(columns)) for columns in pools)
    lights = ()
    if glows:
        lights = tuple(glow_around(x, y, RECESS_REACH, COLOURS.firelight) for x, y in flames)
    return Air(blank(opened), covered if covered is not None else blank(), tuple(drips), tuple(flames),
               tuple(pools), COLOURS, palette(), lights, centres,
               tuple(glow_along(columns, POOL_GLOW_REACH, COLOURS.lavalight) for columns in pools if pool_glows),
               tuple(torches))


def still_ambience(air, **options):
    """No dust unless a test places it."""
    scene = CavernAmbience(0, air, random.Random(5), **options)
    scene.motes.clear()
    return scene


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
    def mote(self, x, y, size=1.0):
        return Mote(x, y, 0.0, 0.0, 0.0, 1000.0, size, age=500.0)

    def test_a_mote_between_two_pixels_shares_itself_between_them(self):
        # One pixel at a time it hopped or shot past; the user chose this one.
        scene = still_ambience(room_air(flames=[(100, 100)]))
        scene.motes.append(self.mote(100.0, 100.0))
        whole = scene.draw(wall_frame())
        self.assertNotEqual(whole.getpixel((100, 100)), WALL)
        self.assertEqual(whole.getpixel((101, 100)), WALL)
        scene.motes[0].x = 100.5
        shared = scene.draw(wall_frame())
        self.assertNotEqual(shared.getpixel((100, 100)), WALL)
        self.assertEqual(shared.getpixel((100, 100)), shared.getpixel((101, 100)))
        self.assertNotEqual(shared.getpixel((100, 100)), whole.getpixel((100, 100)))

    def test_a_blend_is_still_a_palette_colour(self):
        scene = still_ambience(room_air(flames=[(100, 100)]))
        for offset in range(20):
            scene.motes.append(self.mote(100 + offset * 3, 100 + offset * 2))
        allowed = {tuple(colour) + (255,) for colour in COLOURS.rgb.tolist()}
        self.assertLessEqual(colours_in(scene.draw(wall_frame())), allowed)

    def test_dust_drifts_slowly(self):
        # About twice this was too fast for the user.
        self.assertLessEqual(DUST_SPEED[1], 0.26)
        scene = CavernAmbience(0, room_air(flames=[(200, 200)]), random.Random(6))
        for _ in range(200):
            mote = scene.new_mote()
            speed = (mote.dx ** 2 + mote.dy ** 2) ** 0.5
            self.assertGreaterEqual(speed, DUST_SPEED[0] - 1e-9)
            self.assertLessEqual(speed, DUST_SPEED[1] + 1e-9)

    def test_a_grain_comes_and_goes_gradually(self):
        scene = still_ambience(room_air(flames=[(300, 200)]))
        mote = Mote(310.0, 200.0, 0.0, 0.0, 0.0, 300.0, 1.0)
        strengths = []
        for age in range(0, 301, 2):
            mote.age = age
            strengths.append(scene.dust_colour(mote)[3])
        self.assertEqual(strengths[0], 0)
        self.assertAlmostEqual(strengths[-1], 0, places=6)
        rising = strengths[:DUST_FADE_IN // 2 + 1]
        falling = strengths[-(DUST_FADE_OUT // 2 + 1):]
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
            self.assertLessEqual(mote.life, DUST_LIFE[1])

    def test_a_new_grain_fills_the_thinnest_part_of_the_air(self):
        scene = CavernAmbience(0, room_air(), random.Random(3))
        self.assertEqual(scene.motes, [])
        crowded = [Mote(x, y, 0.0, 0.0, 0.0, 300.0, 1.0) for x in range(0, 255, 16) for y in range(0, 365, 16)]
        scene = still_ambience(room_air(flames=[(255, 180)]))
        scene.motes.extend(crowded)
        places = [scene.new_mote() for _ in range(40)]
        self.assertGreater(sum(mote.x > 255 for mote in places), 34)

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
        scene = still_ambience(room_air(flames=[(300, 200)]))
        near = scene.dust_colour(self.mote(310, 200))[3]
        far = scene.dust_colour(self.mote(20, 20))[3]
        self.assertGreater(far, 0.4)
        self.assertGreater(near, far)
        self.assertLessEqual(near, DUST_BRIGHTEST)

    def test_dust_takes_the_colour_of_the_light_on_it(self):
        pool = {x: 200 for x in range(300, 340)}
        scene = still_ambience(room_air(flames=[(100, 100)], pools=[pool]))
        by_flame = scene.dust_colour(self.mote(105, 100))[:3]
        by_pool = scene.dust_colour(self.mote(320, 180))[:3]
        self.assertNotEqual(by_flame, by_pool)
        self.assertEqual(by_flame, palette()[207][:3])
        self.assertEqual(by_pool, palette()[210][:3])

    def test_dust_over_the_lava_stays_dimmer_than_by_the_flame(self):
        # The user wanted the lava's grains of ash, not a brighter haze.
        pool = {x: 200 for x in range(300, 340)}
        scene = still_ambience(room_air(flames=[(100, 100)], pools=[pool]))
        self.assertLessEqual(scene.dust_colour(self.mote(320, 190))[3], scene.dust_colour(self.mote(100, 100))[3])


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


class TorchTests(unittest.TestCase):
    """Six frames: a flame growing in one column, and a lighting painted on a square of wall."""

    LEFT, TOP = 100, 120
    LIT = (140, 115, 90, 255)
    FLAME = (255, 127, 0, 255)

    def art(self):
        frames = numpy.zeros((6, 16, 12, 4), dtype=numpy.uint8)
        frames[...] = WALL
        frames[:, 0] = 0
        for index in range(6):
            frames[index, 12 - index:13, 3] = self.FLAME
        frames[3:, 2:6, 6:10] = self.LIT
        return read_torch(frames, self.LEFT, self.TOP)

    def scene(self, **options):
        art = self.art()
        return still_ambience(room_air(torches=[art], **options)), art

    def painted(self, art, index=0):
        frame = wall_frame()
        sprite = Image.fromarray(art.frames[index])
        frame.paste(sprite, (self.LEFT, self.TOP), sprite)
        return frame

    def lit_wall_pixels(self, frame, art):
        pixels = numpy.asarray(frame.crop(art.box))
        return int((pixels[art.wall] == self.LIT).all(axis=1).sum())

    def test_it_reads_the_two_lightings(self):
        art = self.art()
        self.assertEqual(art.lighting, (0, 0, 0, 1, 1, 1))
        self.assertEqual(int(art.wall.sum()), 16)

    def test_the_flame_stays_the_one_the_game_drew(self):
        # Choosing the frames here made the flame choppy.
        scene, art = self.scene()
        for index in range(6):
            frame = self.painted(art, index)
            before = numpy.asarray(frame.crop(art.box)).copy()
            scene.draw(frame)
            after = numpy.asarray(frame.crop(art.box))
            self.assertTrue((before[~art.wall] == after[~art.wall]).all())

    def test_the_wall_eases_to_a_new_lighting_instead_of_blinking(self):
        scene, art = self.scene()
        scene.flickers[0] = Flicker(0.0)
        counts = []
        for _ in range(round(1 / WALL_EASE) + 1):
            counts.append(self.lit_wall_pixels(scene.draw(self.painted(art, 5)), art))
            scene.advance()
        self.assertEqual(counts[0], 0)
        self.assertEqual(counts, sorted(counts))
        self.assertLess(counts[1], 8)
        self.assertEqual(counts[-1], 16)
        self.assertLess(max(after - before for before, after in zip(counts, counts[1:])), 8)

    def test_the_wall_follows_whichever_frame_is_on_screen(self):
        scene, art = self.scene()
        scene.draw(self.painted(art, 0))
        self.assertEqual(scene.flickers[0].wanted, 0)
        scene.draw(self.painted(art, 5))
        self.assertEqual(scene.flickers[0].wanted, 1)

    def test_it_uses_only_the_colours_of_the_torch(self):
        scene, art = self.scene()
        allowed = {tuple(colour) for frame in art.frames for colour in frame[frame[..., 3] > 0].tolist()}
        for _ in range(60):
            scene.advance()
            self.assertLessEqual(colours_in(scene.draw(self.painted(art, 3))), allowed)

    def test_what_is_drawn_over_the_torch_stays(self):
        scene, art = self.scene()
        scene.flickers[0] = Flicker(0.0)
        frame = self.painted(art, 4)
        left, top = self.LEFT + 6, self.TOP + 2
        frame.paste(Image.new('RGBA', (4, 4), COVER), (left, top))
        scene.draw(frame)
        self.assertEqual(colours_in(frame.crop((left, top, left + 4, top + 4))), {COVER})

    def test_a_room_without_the_torch_on_screen_gets_none(self):
        scene, _art = self.scene()
        self.assertEqual(colours_in(scene.draw(Image.new('RGBA', (WIDTH, HEIGHT), ROCK))), {ROCK})

    def test_it_uses_no_game_randomness(self):
        scene, art = self.scene()
        before = random.getstate()
        for _ in range(100):
            scene.advance()
            scene.draw(self.painted(art))
        self.assertEqual(random.getstate(), before)


class LightTests(unittest.TestCase):
    def scene(self):
        return still_ambience(room_air(flames=[(200, 200)], glows=True))

    def test_rock_warms_towards_the_flame(self):
        scene = self.scene()
        frame = Image.new('RGBA', (WIDTH, HEIGHT), ROCK)
        scene.draw(frame)
        pixels = numpy.asarray(frame)[..., :3].sum(axis=2)
        self.assertGreater(pixels[196:204, 196:204].mean(), pixels[196:204, 216:224].mean())
        self.assertGreaterEqual(pixels[196:204, 216:224].mean(), sum(ROCK[:3]))

    def test_the_light_does_not_leave_the_recess(self):
        # A wider light looked like a bomb about to go off.
        scene = self.scene()
        frame = Image.new('RGBA', (WIDTH, HEIGHT), ROCK)
        scene.draw(frame)
        changed = numpy.argwhere((numpy.asarray(frame)[..., :3] != ROCK[:3]).any(axis=2))
        self.assertTrue(len(changed))
        self.assertGreaterEqual(changed[:, 0].min(), 200 - RECESS_REACH[1])
        self.assertLess(changed[:, 0].max(), 200 + RECESS_REACH[1])
        self.assertGreaterEqual(changed[:, 1].min(), 200 - RECESS_REACH[0])
        self.assertLess(changed[:, 1].max(), 200 + RECESS_REACH[0])

    def test_the_light_moves_like_a_candle(self):
        scene = self.scene()
        strengths = []
        for _ in range(2000):
            scene.advance()
            strengths.append(scene.flame_strength())
        # A candle: it moves, a little, and never beats like the second pass.
        self.assertGreater(max(strengths) - min(strengths), 0.2)
        self.assertLess(max(strengths) - min(strengths), 0.42)
        self.assertLess(max(abs(after - before) for before, after in zip(strengths, strengths[1:])), 0.1)

    def test_light_stays_in_the_palette(self):
        scene = self.scene()
        frame = Image.new('RGBA', (WIDTH, HEIGHT), ROCK)
        scene.draw(frame)
        allowed = {tuple(colour) + (255,) for colour in COLOURS.rgb.tolist()}
        self.assertLessEqual(colours_in(frame), allowed)

    def test_fire_does_not_receive_light(self):
        frame = Image.new('RGBA', (WIDTH, HEIGHT), FIRE)
        self.scene().draw(frame)
        self.assertEqual(colours_in(frame), {FIRE})

    def test_a_colour_outside_the_palette_is_left_alone(self):
        strange = (11, 222, 33, 255)
        frame = Image.new('RGBA', (WIDTH, HEIGHT), strange)
        self.scene().draw(frame)
        self.assertEqual(colours_in(frame), {strange})

    def test_the_table_steps_every_palette_colour_through_the_levels(self):
        table = COLOURS.firelight
        self.assertEqual(table.shape, (LIGHT_LEVELS + 1, len(COLOURS.rgb), 3))
        self.assertTrue((table[0] == COLOURS.rgb).all())


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
        scene = self.busy_scene(glows=True)
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
        self.assertEqual(len(self.air.glows), 1)

    def test_the_torch_is_read_from_its_nine_frames(self):
        self.assertEqual(len(self.air.torches), 1)
        torch = self.air.torches[0]
        self.assertEqual(torch.box, (455, 125, 501, 209))
        self.assertEqual(sorted(set(torch.lighting)), [0, 1])
        self.assertIn(int(torch.wall.sum()), range(80, 120))

    def test_the_lava_glow_is_fainter_than_the_torch_warmth(self):
        pool = self.air.pools[0]
        scene = CavernAmbience(16, replace(self.air, glows=()), random.Random(2))
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

    def test_the_recess_is_barely_warmer(self):
        # Rock keeps its look: a warmth only seen when the toggle is flicked.
        scene = CavernAmbience(16, replace(self.air, pool_glows=()), random.Random(2))
        scene.motes.clear()
        frame = Image.alpha_composite(self.art.background, self.art.foreground)
        before = numpy.asarray(frame).astype(int)
        scene.draw(frame)
        change = numpy.asarray(frame).astype(int)[..., :3] - before[..., :3]
        box = self.air.glows[0].box
        # The recess is about 46 x 84 around the flame at (478, 167).
        self.assertGreaterEqual(box[0], 445)
        self.assertGreaterEqual(box[1], 120)
        self.assertLessEqual(box[2], 512)
        self.assertLessEqual(box[3], 215)
        self.assertEqual(change[:box[1]].max(initial=0), 0)
        self.assertEqual(change[:, :box[0]].max(initial=0), 0)
        inside = change[box[1]:box[3], box[0]:box[2]]
        self.assertLess(numpy.abs(inside).mean(), 5)

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
