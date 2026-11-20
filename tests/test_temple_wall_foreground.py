"""A temple wall's two-column face covers a character in its right column too."""

from pathlib import Path
import unittest
from unittest.mock import patch

from PIL import Image

from pop2.caverns import cavern_room, temple_wall_redraws
from pop2.paths import ASSET_DIR

RECOVERY = Path(__file__).resolve().parents[2] / 'PoP2-Mac-Code-Recovery'

try:
    import unicorn  # noqa: F401
except ImportError:  # pragma: no cover - optional research dependency
    unicorn = None

TEMPLE_IMPORTED = all((ASSET_DIR / name).is_file()
                      for name in ('Prince.rsrc', 'Temple.rsrc', 'temple_level10.json'))


class TempleWallFaceTests(unittest.TestCase):
    def art(self, walls):
        # Native room 3 of level 10: the clean cut draws SHAP 3523, 102 wide,
        # from cell (4, 0) only; cell (5, 0) is a wall with fg & 3 == 3.
        commands = [['front', 3523, 204, 125, 16, 0, [5, 204, 125, 306], 4, 4, 0]]
        program = {'version': 6, 'level': 10, 'rooms': {'2': commands}}
        shapes = {3523: Image.new('RGBA', (102, 120), 'red')}
        with (patch('pop2.caverns.room_assets', return_value=(program, {}, {}, shapes)),
              patch('pop2.caverns.loose_variant', return_value=None),
              patch('pop2.caverns.temple_wall_redraws', return_value=walls)):
            return cavern_room(2, level_number=10)

    def test_a_character_in_the_right_column_alone_is_behind_the_face(self):
        # A dirty (5, 0) redraws shape 20 + 3 one column left (10:03b6-03c2).
        art = self.art(frozenset({(2, 5, 0, 3523)}))
        mask = art.actor_mask(0, bounds=(270, 60, 300, 110))
        self.assertEqual(mask.getpixel((280, 80)), 255)
        # The earlier masks kept the face under the cell that drew it.
        old = self.art(frozenset()).actor_mask(0, bounds=(270, 60, 300, 110))
        self.assertEqual(old.getpixel((280, 80)), 0)

    def test_the_left_column_and_other_shapes_are_unchanged(self):
        art = self.art(frozenset({(2, 5, 0, 3522)}))
        self.assertEqual(art.actor_mask(0, bounds=(270, 60, 300, 110)).getpixel((280, 80)), 0)
        self.assertEqual(art.actor_mask(0, bounds=(215, 60, 240, 110)).getpixel((220, 80)), 255)

    @unittest.skipUnless(TEMPLE_IMPORTED, 'Imported temple artwork required')
    def test_the_wall_cells_come_from_the_level_words(self):
        walls = temple_wall_redraws(10)
        self.assertIn((2, 5, 0, 3523), walls)
        self.assertNotIn((2, 4, 0, 3523), walls)
        self.assertEqual(temple_wall_redraws(6), frozenset())


@unittest.skipUnless(unicorn is not None and (RECOVERY / 'resource_forks').is_dir() and TEMPLE_IMPORTED,
                     'Unicorn, the original recovery and the imported temple are required')
class NativeForegroundCellTests(unittest.TestCase):
    ROOMS = {(10, 2), (10, 16), (11, 25), (12, 30), (13, 21)}

    def test_every_dirty_cell_redraw_is_in_the_port_masks(self):
        from tools.probe_foreground_cells import run_probe

        report = run_probe(RECOVERY, levels=(10, 11, 12, 13), rooms=self.ROOMS)
        self.assertEqual(report['totals']['cells'], 150)
        self.assertEqual(report['totals']['missing_pixels'], 0, report['cases'])
        # A face whose right cell redraws the empty shape 3522 stays the
        # clean cut's alone: the original never repaints it over a body.
        self.assertEqual(report['cases']['12:30'], [
            dict(cell=[3, 1], missing=0, bleed={'2,1': 5763}, own_extra=0)])

    def test_the_masks_without_the_right_column_redraw_are_rejected(self):
        from tools.probe_foreground_cells import run_probe

        with patch('pop2.caverns.temple_wall_redraws', return_value=frozenset()):
            report = run_probe(RECOVERY, levels=(10,), rooms={(10, 2)})
        self.assertEqual(report['totals']['missing_pixels'], 6120)


if __name__ == '__main__':
    unittest.main()
