"""The optional cave ambience: pixels only, tied to the scenery, off by default."""

from pathlib import Path
import random
from types import SimpleNamespace
import unittest

import numpy
from PIL import Image

from pop2.cavern_ambience import (
    AMBIENCE_ROOMS, ALL_INKS, Air, CavernAmbience, Drip, FLASH_INKS, HEIGHT, SPLASH_INKS,
    STEAM_INKS, SWELL_TICKS, TORCH_INKS, WIDTH, landing, stalactite_tips,
)
from pop2.game_menu import GameMenu
from pop2.paths import ASSET_DIR

CAVERNS_INSTALLED = (ASSET_DIR / 'caverns_level4.json').is_file()


def blank(value=0):
    return bytes([value]) * (WIDTH * HEIGHT)


def inks():
    # A distinct colour per index, so a drawn pixel names its own ink.
    return {index: (index, 255 - index, 7, 255) for index in ALL_INKS}


def room_air(drips=(), torches=(), pools=(), opened=255, covered=None):
    return Air(blank(opened), covered if covered is not None else blank(), tuple(drips),
               tuple(torches), tuple(pools), inks())


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
    def ambience(self, drip):
        scene = CavernAmbience(0, room_air([drip]), random.Random(5))
        scene.motes.clear()
        return scene

    def test_a_drop_swells_on_the_tip_then_falls_straight_down_its_column(self):
        drip = Drip(100, 50, 200, False)
        scene = self.ambience(drip)
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
        scene = self.ambience(Drip(100, 50, 200, False))
        self.assertTrue(run_until(scene, lambda: scene.flecks))
        self.assertEqual({fleck.inks for fleck in scene.flecks}, {SPLASH_INKS})
        scene = self.ambience(Drip(100, 50, 200, True))
        self.assertTrue(run_until(scene, lambda: scene.flecks))
        self.assertEqual({fleck.inks for fleck in scene.flecks}, {STEAM_INKS, FLASH_INKS})

    def test_a_floor_that_has_fallen_no_longer_stops_the_drop(self):
        drip = Drip(102, 50, 226, False)
        scene = self.ambience(drip)
        self.assertEqual(scene.fall_bottom(drip, tile_map({(2, 1): 1})), 226)
        self.assertEqual(scene.fall_bottom(drip, tile_map({(2, 1): 0, (2, 2): 1})), 346)
        self.assertEqual(scene.fall_bottom(drip, tile_map({})), HEIGHT)

    def test_a_drop_leaving_the_room_makes_no_splash(self):
        drip = Drip(102, 50, 226, False)
        scene = self.ambience(drip)
        scene.falls[0].wait = 0
        for _ in range(200):
            scene.advance(tile_map({}))
            self.assertEqual(scene.flecks, [])

    def test_each_stalactite_keeps_its_own_rhythm(self):
        scene = CavernAmbience(0, room_air([Drip(100, 50, 200, False), Drip(200, 50, 200, False)]),
                               random.Random(2))
        periods = [fall.period for fall in scene.falls]
        self.assertNotEqual(periods[0], periods[1])
        for _ in range(3000):
            scene.advance()
            for fall, period in zip(scene.falls, periods):
                self.assertLessEqual(fall.wait, period + 14)


class DustTests(unittest.TestCase):
    def test_dust_is_shown_only_on_open_air(self):
        # Open air only in the left half of the room.
        opened = bytearray(blank())
        for y in range(HEIGHT):
            opened[y * WIDTH:y * WIDTH + WIDTH // 2] = bytes([255]) * (WIDTH // 2)
        air = Air(bytes(opened), blank(), (), (), (), inks())
        scene = CavernAmbience(0, air, random.Random(3))
        self.assertTrue(scene.motes)
        for _ in range(900):
            scene.advance()
            for x, y, _ink in scene.pixels():
                self.assertLess(x, WIDTH // 2)

    def test_dust_lights_up_as_it_nears_a_torch(self):
        scene = CavernAmbience(0, room_air(torches=[(300, 200)]), random.Random(1))
        self.assertIsNone(scene.light(100, 100))
        self.assertEqual(scene.light(300 + 70, 200), TORCH_INKS[0])
        self.assertEqual(scene.light(300 + 4, 200), TORCH_INKS[-1])

    def test_ash_rises_from_the_lava_and_dies_there(self):
        pool = {x: 228 for x in range(300, 340)}
        air = room_air(pools=[pool], opened=0)
        scene = CavernAmbience(0, air, random.Random(1))
        self.assertEqual(scene.motes, [])
        self.assertTrue(run_until(scene, lambda: scene.motes))
        ash = scene.motes[0]
        start = ash.y
        self.assertTrue(ash.ash)
        self.assertIn(int(ash.x), pool)
        self.assertEqual(start, 226)
        self.assertTrue(run_until(scene, lambda: ash.y < start - 15))
        # Born in front of the floor, where the map has no open air.
        self.assertTrue(any(pixel for pixel in scene.pixels()))
        self.assertTrue(run_until(scene, lambda: ash not in scene.motes))


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
        frame = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 255))
        for _ in range(500):
            scene.advance()
            scene.draw(frame)
        self.assertEqual(random.getstate(), before)

    def test_every_pixel_is_opaque_and_in_the_palette(self):
        scene = self.busy_scene()
        table = set(inks().values())
        background = (1, 2, 3, 255)
        for _ in range(600):
            scene.advance()
            frame = Image.new('RGBA', (WIDTH, HEIGHT), background)
            scene.draw(frame)
            colours = {colour for _count, colour in frame.getcolors(maxcolors=1024)}
            self.assertLessEqual(colours - {background}, table)

    def test_a_handful_of_pixels_at_a_time(self):
        scene = self.busy_scene()
        for _ in range(600):
            scene.advance()
            self.assertLess(len(list(scene.pixels())), 40)

    def test_nothing_is_drawn_over_the_foreground(self):
        scene = self.busy_scene(covered=blank(255))
        frame = Image.new('RGBA', (WIDTH, HEIGHT), (1, 2, 3, 255))
        for _ in range(600):
            scene.advance()
            scene.draw(frame)
        self.assertEqual(frame.getcolors(), [(WIDTH * HEIGHT, (1, 2, 3, 255))])

    def test_a_second_render_of_one_tick_draws_the_same_pixels(self):
        # The gate presentation renders between ticks.
        scene = self.busy_scene()
        for _ in range(300):
            scene.advance()
            self.assertEqual(list(scene.pixels()), list(scene.pixels()))

    def test_the_same_seed_makes_the_same_ambience(self):
        first, second = self.busy_scene(), self.busy_scene()
        for _ in range(300):
            first.advance()
            second.advance()
            self.assertEqual(list(first.pixels()), list(second.pixels()))


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
        self.assertEqual(self.air.torches, ((478, 167),))
        self.assertEqual((min(self.air.pools[0]), max(self.air.pools[0])), (331, 413))

    def test_colours_are_read_from_the_room_palette(self):
        from pop2.caverns import room_assets

        palette = room_assets(4, 16)[2]
        for index, colour in self.air.inks.items():
            self.assertEqual(colour, tuple(palette[index][:3]) + (255,))

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

    def play(self, enabled):
        from tools.audit_temple_routes import Harness, press

        random.seed(77)
        harness = Harness(4, peaceful=False, draw=True)
        try:
            scene = harness.scene
            scene.audio = None
            scene.cave_ambience_enabled = enabled
            scene.jump_to_room(16, row=1, x=3 * 51 + 30, facing=1)
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
        before, after = off.pop('view'), on.pop('view')
        # The retained scenery above is equal too: no particle survives a cut.
        self.assertEqual(off, on)
        changed = int((numpy.asarray(before) != numpy.asarray(after)).any(axis=2).sum())
        self.assertTrue(0 < changed < 40, changed)


class SourceTests(unittest.TestCase):
    def test_the_module_imports_no_game_state(self):
        source = Path('pop2/cavern_ambience.py').read_text(encoding='utf-8')
        self.assertNotIn('cavern_state', source)
        self.assertNotIn('random.random(', source)
        self.assertNotIn('save_game', source)


if __name__ == '__main__':
    unittest.main()
