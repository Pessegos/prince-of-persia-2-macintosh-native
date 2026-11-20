"""CheckGateInFore 3:26e4 draws a gate's moving stone over a character at it."""

from pathlib import Path
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops

from pop2.caverns import CavernRoom, cavern_room
from pop2.paths import ASSET_DIR

RECOVERY = Path(__file__).resolve().parents[2] / 'PoP2-Mac-Code-Recovery'

try:
    import unicorn  # noqa: F401
except ImportError:  # pragma: no cover - optional research dependency
    unicorn = None

TEMPLE_IMPORTED = all((ASSET_DIR / name).is_file()
                      for name in ('Prince.rsrc', 'Temple.rsrc', 'temple_level10.json'))


class TempleGateCoverTests(unittest.TestCase):
    def art(self, commands, cells):
        program = {'version': 14, 'level': 10, 'rooms': {'7': commands},
                   'pressure_plates': {'rooms': {'7': [
                       {'kind': 4, 'commands': [['back', 3576, 4, column, row]]} for column, row in cells]}}}
        shapes = {3576: Image.new('RGBA', (30, 126), 'gray'), 3542: Image.new('RGBA', (30, 126), 'gray')}
        with (patch('pop2.caverns.cavern_assets', return_value=(program, {}, {}, shapes)),
              patch('pop2.caverns.customized_rooms', return_value=frozenset())):
            return cavern_room(7, level_number=10)

    def test_the_temple_stone_covers_a_character_in_its_tile_column_or_the_one_before(self):
        # Level 10 room 8's gate at (6, 1): DrawTempGateMovable 10:0976 draws
        # SHAP 3576 on the tile's right edge (x 356), in cell 7's redraw.
        art = self.art([['back', 3576, 356, 235, 16, 1, [109, 356, 235, 386], 4, 6, 1]], [(6, 1)])
        self.assertEqual(set(art.gate_occlusion), {(6, 1)})
        cover, position = art.gate_occlusion[6, 1]
        self.assertEqual((position, cover.size), ((356, 109), (30, 126)))
        for column, covered in ((4, False), (5, True), (6, True), (7, False)):
            with self.subTest(column=column):
                self.assertEqual(bool(art.gate_peel(column, 1)), covered)
                self.assertEqual(art.gate_peel(column, 0), ())

    def test_a_temple_gate_in_the_last_column_has_no_cell_to_redraw_it(self):
        art = self.art([['back', 3576, 509, 235, 16, 1, [109, 509, 235, 510], 4, 9, 1],
                        ['back', 3542, 200, 235, 16, 1, [109, 200, 235, 230], 4, 3, 1]], [(9, 1), (3, 1)])
        self.assertFalse(art.gate_occlusion)

    def test_the_cover_is_clipped_to_the_cell_right_of_the_tile(self):
        # The temple's clip starts a pixel left of that cell (3:2892-28a0).
        art = self.art([['back', 3576, 340, 235, 16, 1, [109, 340, 235, 370], 4, 6, 1]], [(6, 1)])
        cover, position = art.gate_occlusion[6, 1]
        self.assertEqual((position, cover.size), ((356, 109), (14, 126)))


@unittest.skipUnless(unicorn is not None and (RECOVERY / 'resource_forks').is_dir() and TEMPLE_IMPORTED,
                     'Unicorn, the original recovery and the imported temple are required')
class NativeGatePeelTests(unittest.TestCase):
    ROOMS = {(3, 2), (7, 0), (10, 8), (12, 4)}

    def test_the_original_peel_matches_the_port_covers(self):
        from tools.probe_gate_peel import run_probe

        report = run_probe(RECOVERY, levels=(3, 7, 10, 12), rooms=self.ROOMS, modes=True)
        totals = report['totals']
        self.assertEqual(report['cases'], {})
        self.assertEqual((totals['missing_pixels'], totals['extra_pixels']), (0, 0))
        self.assertGreater(totals['peeled'], 0)
        # 12:4's gate 4:0 shares cell 0's pressure key with room 1's 1:9.
        self.assertEqual(totals['shared_slot_states'], 8)
        # The port's crush keeps the row's stones in front; the original
        # repeats only the gate cell's front pieces (3:2922).
        self.assertGreater(totals['crushed_port_pixels'], totals['crushed_native_pixels'])

    def test_the_temple_without_its_stone_cover_is_rejected(self):
        from tools.probe_gate_peel import run_probe

        with patch.object(CavernRoom, 'gate_peel', lambda *_arguments: ()):
            report = run_probe(RECOVERY, levels=(10,), rooms={(10, 8)})
        self.assertGreater(report['totals']['missing_pixels'], 0)


@unittest.skipUnless(TEMPLE_IMPORTED, 'Imported temple artwork required')
class TempleGateSceneTests(unittest.TestCase):
    def test_a_half_open_temple_gate_stays_in_front_of_the_head(self):
        from tests.test_terrain import RooftopSceneTests
        from unittest.mock import Mock
        from pop2.scene_prototype import ROOM_ORIGIN_X

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(10)
        scene.peaceful = True
        scene.in_animation_tick = True
        scene.render = Mock()
        scene.game.caverns.plates.foreground[8, 16] = 120
        for x, facing in ((362, 1), (366, 0)):
            with self.subTest(facing=facing):
                scene.jump_to_room(8, row=1, x=x, facing=facing)
                type(scene).render(scene)
                room = scene.room_cache[8]
                cover, position = room.gate_occlusion[6, 1]
                mask = Image.new('L', scene.background.size)
                mask.paste(cover, position)
                bounds = scene.player_bounds()
                self.assertIsNotNone(mask.crop(bounds).getbbox())
                scenery = Image.alpha_composite(scene.background, scene.foreground)
                actual = scene.screenshot_viewport.crop((ROOM_ORIGIN_X, 0, ROOM_ORIGIN_X + 510, 365))
                difference = ImageChops.difference(actual.convert('RGB'), scenery.convert('RGB'))
                self.assertIsNone(ImageChops.multiply(difference, mask.convert('RGB')).getbbox())
                with patch.object(CavernRoom, 'gate_peel', lambda *_arguments: ()):
                    type(scene).render(scene)
                actual = scene.screenshot_viewport.crop((ROOM_ORIGIN_X, 0, ROOM_ORIGIN_X + 510, 365))
                difference = ImageChops.difference(actual.convert('RGB'), scenery.convert('RGB'))
                self.assertIsNotNone(ImageChops.multiply(difference, mask.convert('RGB')).getbbox())


if __name__ == '__main__':
    unittest.main()
