"""The optional cave ambience: pixels only, tied to the scenery, off by default."""

import math
from pathlib import Path
import random
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy
from PIL import Image

from pop2.cavern_ambience import (
    AMBIENCE_ROOMS, ALL_INKS, ASH_INKS, Air, Ash, CavernAmbience, Colours, Drip, FLASH_INKS,
    FRAMES_PER_TICK, HEIGHT, LIGHT_LEVELS, MOST_ASH, Mote, RECESS_REACH, SPLASH_INKS, STEAM_INKS,
    SWELL_TICKS, WIDTH, glow_around, landing, stalactite_tips,
)
from pop2.game_menu import GameMenu
from pop2.paths import ASSET_DIR

CAVERNS_INSTALLED = (ASSET_DIR / 'caverns_level4.json').is_file()
WALL = (24, 8, 8, 255)
ROCK = (140, 115, 90, 255)
FIRE = (255, 127, 0, 255)


def blank(value=0):
    return bytes([value]) * (WIDTH * HEIGHT)


def palette():
    colours = {index: (index, 255 - index, 7, 255) for index in ALL_INKS}
    # A dark ramp, so blends and light have somewhere to land.
    colours.update({300 + step: (24 + step * 24, 8 + step * 20, 8 + step * 16, 255) for step in range(10)})
    colours.update({1: WALL, 2: ROCK, 3: FIRE})
    return colours


COLOURS = Colours(palette())


def room_air(drips=(), flames=(), pools=(), opened=255, covered=None, glows=False):
    centres = tuple((sum(columns) / len(columns), sum(columns.values()) / len(columns)) for columns in pools)
    lights = ()
    if glows:
        lights = tuple(glow_around(x, y, RECESS_REACH, COLOURS.firelight) for x, y in flames)
    return Air(blank(opened), covered if covered is not None else blank(), tuple(drips), tuple(flames),
               tuple(pools), COLOURS, palette(), lights, centres)


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
        return Mote(x, y, 0.0, 1.0, 1000.0, size, age=500.0)

    def test_a_mote_between_two_pixels_shares_itself_between_them(self):
        # The first pass snapped each grain to one pixel: it crawled.
        scene = still_ambience(room_air(flames=[(100, 100)]))
        frame = wall_frame()
        canvas = frame.load()
        scene.share(canvas, 100.0, 100.0, (*ROCK[:3], 1.0))
        self.assertEqual(canvas[100, 100], ROCK)
        self.assertEqual(canvas[101, 100], WALL)
        frame = wall_frame()
        canvas = frame.load()
        scene.share(canvas, 100.5, 100.0, (*ROCK[:3], 1.0))
        self.assertNotEqual(canvas[100, 100], WALL)
        self.assertEqual(canvas[100, 100], canvas[101, 100])
        self.assertNotEqual(canvas[100, 100], ROCK)

    def test_a_blend_is_still_a_palette_colour(self):
        scene = still_ambience(room_air(flames=[(100, 100)]))
        frame = wall_frame()
        canvas = frame.load()
        for offset in range(20):
            scene.share(canvas, 100 + offset * 0.37, 100 + offset * 0.61, (*ROCK[:3], 0.6))
        allowed = {tuple(colour) + (255,) for colour in COLOURS.rgb.tolist()}
        self.assertLessEqual(colours_in(frame), allowed)

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

    def test_dust_is_seen_only_where_light_reaches_it(self):
        scene = still_ambience(room_air(flames=[(300, 200)]))
        near = scene.dust_colour(self.mote(310, 200))[3]
        far = scene.dust_colour(self.mote(20, 20))[3]
        self.assertGreater(near, 0.5)
        self.assertLess(far, 0.15)

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
        self.assertLess(scene.dust_colour(self.mote(320, 190))[3], scene.dust_colour(self.mote(100, 100))[3])


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

    def test_the_light_does_not_pulse(self):
        scene = self.scene()
        strengths = []
        for _ in range(2000):
            scene.advance()
            strengths.append(scene.flame_strength())
        self.assertLess(max(strengths) - min(strengths), 0.1)

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
            scene.advance(dt=0.5)
            first, second = wall_frame(), wall_frame()
            self.assertEqual(scene.draw(first).tobytes(), scene.draw(second).tobytes())

    def test_the_same_seed_makes_the_same_ambience(self):
        first, second = self.busy_scene(), self.busy_scene()
        for _ in range(200):
            first.advance()
            second.advance()
        self.assertEqual(first.draw(wall_frame()).tobytes(), second.draw(wall_frame()).tobytes())

    def test_frames_between_ticks_do_not_change_its_speed(self):
        first, thirds = still_ambience(room_air()), still_ambience(room_air())
        for scene in (first, thirds):
            scene.motes.append(Mote(200.0, 200.0, 1.0, 1.0, 900.0, 1.0))
            scene.ash.append(Ash(300.0, 300.0, 0.0, 0.6, 0.0, 900.0))
        for _ in range(60):
            first.advance()
            for _third in range(3):
                thirds.advance(dt=1 / 3)
        self.assertLess(math.hypot(first.motes[0].x - thirds.motes[0].x,
                                   first.motes[0].y - thirds.motes[0].y), 0.5)
        self.assertLess(abs(first.ash[0].y - thirds.ash[0].y), 0.5)


class BareSceneTests(unittest.TestCase):
    def test_a_scene_without_the_toggle_schedules_nothing(self):
        # The control suites drive scenes built without __init__.
        from pop2.scene_prototype import ScenePrototype

        scene = ScenePrototype.__new__(ScenePrototype)
        scene.schedule_ambience_presentation()
        self.assertIsNone(scene.ambience_after_id)


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

    def test_the_recess_is_barely_warmer(self):
        # Rock keeps its look: a warmth only seen when the toggle is flicked.
        scene = CavernAmbience(16, self.air, random.Random(2))
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

            def ticks(count):
                for _ in range(count):
                    harness.tick()
                    if enabled:
                        for _frame in range(FRAMES_PER_TICK - 1):
                            scene.advance_ambience_presentation(0)

            ticks(20)
            press(harness, 'R', True)
            ticks(5)
            press(harness, 'R', False)
            ticks(40)
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

    def test_frames_between_ticks_are_dropped_rather_than_late(self):
        harness = self.harness()
        self.addCleanup(harness.close)
        scene = harness.scene
        scene.cave_ambience_enabled = True
        harness.tick(2)
        scene.root.after = Mock(return_value='timer')
        scene.next_animation_at = harness.clock.now + 0.001
        scene.schedule_ambience_presentation()
        scene.root.after.assert_not_called()
        scene.next_animation_at = harness.clock.now + 1 / 12
        scene.schedule_ambience_presentation()
        scene.root.after.assert_called_once()
        delay, callback, left = scene.root.after.call_args.args
        self.assertEqual(callback, scene.advance_ambience_presentation)
        self.assertEqual(left, FRAMES_PER_TICK - 2)
        self.assertLess(delay, 1000 / 12)
        scene.ambience_after_id = None

    def test_a_tick_moves_only_what_the_frames_between_ticks_did_not(self):
        harness = self.harness()
        self.addCleanup(harness.close)
        scene = harness.scene
        scene.cave_ambience_enabled = True
        harness.tick(2)
        with patch.object(scene.level_renderer, 'advance_ambience') as advance:
            scene.advance_ambience_tick()
            self.assertEqual(advance.call_args.args[2], 1.0)
            scene.ambience_presented = 2 / 3
            scene.advance_ambience_tick()
            self.assertAlmostEqual(advance.call_args.args[2], 1 / 3)
            self.assertEqual(scene.ambience_presented, 0.0)

    def test_nothing_moves_or_is_scheduled_while_paused_or_off(self):
        harness = self.harness()
        self.addCleanup(harness.close)
        scene = harness.scene
        scene.cave_ambience_enabled = True
        harness.tick(2)
        scene.render = Mock()
        scene.paused = True
        scene.advance_ambience_presentation(0)
        scene.render.assert_not_called()
        scene.paused = False
        scene.cave_ambience_enabled = False
        scene.schedule_ambience_presentation()
        self.assertIsNone(scene.ambience_after_id)
        scene.advance_ambience_presentation(0)
        scene.render.assert_not_called()


class SourceTests(unittest.TestCase):
    def test_the_module_imports_no_game_state(self):
        source = Path('pop2/cavern_ambience.py').read_text(encoding='utf-8')
        self.assertNotIn('cavern_state', source)
        self.assertNotIn('random.random(', source)
        self.assertNotIn('save_game', source)


if __name__ == '__main__':
    unittest.main()
