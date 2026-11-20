"""CheckGateInFore 3:26e4 draws a gate's moving stone over a character at it."""

from pathlib import Path
from types import SimpleNamespace
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
        # 12:4's gate 4:0 shares cell 0's slot with room 1's 1:9; only an
        # import from before X/row keys leaves its states out.
        self.assertIn(totals.get('old_export_states', 0), (0, 8))
        # The port's crush keeps the row's stones in front; the original
        # repeats only the gate cell's front pieces (3:2922).
        self.assertGreater(totals['crushed_port_pixels'], totals['crushed_native_pixels'])

    def test_the_temple_without_its_stone_cover_is_rejected(self):
        from tools.probe_gate_peel import run_probe

        with patch.object(CavernRoom, 'gate_peel', lambda *_arguments: ()):
            report = run_probe(RECOVERY, levels=(10,), rooms={(10, 8)})
        self.assertGreater(report['totals']['missing_pixels'], 0)

    def test_each_gate_moves_only_its_own_stones(self):
        # 12:4's cell 0 and 11:8's slot each draw two gates' SHAP 3576.
        from tools.probe_gate_peel import run_drawing_probe

        report = run_drawing_probe(RECOVERY, levels=(11, 12), rooms={(11, 8), (12, 4)})
        self.assertEqual(report['cases'], {})
        self.assertGreater(report['totals']['states'], 0)
        if not report['totals'].get('old_export_states'):
            self.assertEqual(report['totals']['states'], 48)


class GateClipTests(unittest.TestCase):
    """CheckGateInFore's choice of whose rectangle clips each stone."""

    def art(self):
        return SimpleNamespace(gate_occlusion={(6, 1): (Image.new('L', (30, 126), 255), (357, 109))})

    def clips(self, kid, opponents):
        return CavernRoom.gate_clips(self.art(), kid, opponents)

    KID = (5, 1, 0, False, (280, 150, 330, 246))
    GUARD = (2, 6, 1, 0, (300, 150, 350, 246))

    def test_the_kid_is_tested_first_and_his_rectangle_clips_the_stone(self):
        self.assertEqual(self.clips(self.KID, [self.GUARD]), {(6, 1): self.KID[4]})
        # Hanging (modes 2/6) or another row does not match.
        self.assertEqual(self.clips((5, 1, 2, False, self.KID[4]), []), {})
        self.assertEqual(self.clips((5, 0, 0, False, self.KID[4]), []), {})

    def test_an_opponent_is_clipped_by_the_next_slots_object(self):
        # A type-2 slot after it: GetObjTableType(3, 2) finds the first
        # type-2 guard filed as (3, 2), here the matching one itself.
        far = (2, -9, -9, 0, (0, 0, 10, 10))
        self.assertEqual(self.clips(None, [self.GUARD, far]), {(6, 1): self.GUARD[4]})
        # Nothing after it, or no such object: the cell's clip from Y 125.
        self.assertEqual(self.clips(None, [self.GUARD]), {(6, 1): (0, 125, 510, 365)})
        # A type-1 opponent is filed under kind 2: never found either.
        self.assertEqual(self.clips(None, [self.GUARD, (1, -9, -9, 0, (0, 0, 10, 10))]),
                         {(6, 1): (0, 125, 510, 365)})

    def test_type_11_slots_and_a_crushed_kid_draw_no_stone(self):
        self.assertEqual(self.clips(None, [(11, 6, 1, 0, self.GUARD[4])]), {})
        self.assertEqual(self.clips((5, 1, 0, True, self.KID[4]), [self.GUARD]), {})


@unittest.skipUnless(unicorn is not None and (RECOVERY / 'resource_forks').is_dir() and TEMPLE_IMPORTED,
                     'Unicorn, the original recovery and the imported temple are required')
class NativeGateOpponentTests(unittest.TestCase):
    ROOMS = {(3, 19), (7, 19)}

    def test_the_opponents_branch_matches_the_original(self):
        from tools.probe_gate_peel import run_opponent_probe

        report = run_opponent_probe(RECOVERY, levels=(3, 7), rooms=self.ROOMS)
        self.assertEqual(report['cases'], {})
        self.assertGreater(report['totals']['peeled'], 0)

    def test_every_character_at_a_gate_under_the_whole_stone_is_rejected(self):
        from tools.probe_gate_peel import run_opponent_probe

        with patch.object(CavernRoom, 'gate_clips', lambda self, *_arguments: dict.fromkeys(self.gate_occlusion)):
            report = run_opponent_probe(RECOVERY, levels=(3, 7), rooms=self.ROOMS)
        self.assertGreater(report['totals']['extra_pixels'], 0)


class SharedSlotKeyTests(unittest.TestCase):
    # Level 12 room 4's cell 0 slot: its own gate's stone and the left room's.
    OWN = ['back', 3576, 50, 235, 16, 0, [0, 50, 120, 80], 4, 0, 0]
    LEFT = ['back', 3576, -1, 235, 16, 0, [0, 0, 120, 29], 4, 0, 0]

    def test_a_slot_drawing_a_shape_twice_keys_each_by_x_and_row(self):
        from tools.extract_pressure_plates import command_key, keyed_commands

        key = command_key(self.OWN)
        self.assertEqual(set(keyed_commands([self.OWN, self.LEFT], {key})),
                         {key + (50, 0), key + (-1, 0)})
        self.assertEqual(set(keyed_commands([self.OWN], set())), {key})

    def test_a_gate_moves_only_the_stone_of_its_own_key(self):
        from pop2.caverns import pressure_drawing_commands

        shape = {'data': bytes(4) + (30).to_bytes(2, 'big') + (126).to_bytes(2, 'big')}
        records = [{'room': 4, 'cell': 0, 'kind': 4, 'foreground': 0,
                    'commands': [['back', 3576, 4, 0, 0, 50, 0]]}]
        own, left = pressure_drawing_commands([self.OWN, self.LEFT], records, (10,), {'SHAP': {3576: shape}})
        self.assertEqual(own[3], 235 - 20)
        self.assertEqual(left, self.LEFT)


@unittest.skipUnless(TEMPLE_IMPORTED,'Imported temple artwork required')
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
                with (patch.object(CavernRoom, 'gate_peel', lambda *_arguments: ()),
                      patch.object(CavernRoom, 'gate_clips', lambda *_arguments: {})):
                    type(scene).render(scene)
                actual = scene.screenshot_viewport.crop((ROOM_ORIGIN_X, 0, ROOM_ORIGIN_X + 510, 365))
                difference = ImageChops.difference(actual.convert('RGB'), scenery.convert('RGB'))
                self.assertIsNotNone(ImageChops.multiply(difference, mask.convert('RGB')).getbbox())


if __name__ == '__main__':
    unittest.main()
