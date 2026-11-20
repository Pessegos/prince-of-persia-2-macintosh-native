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
              patch('pop2.caverns.customized_rooms', return_value=frozenset()),
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

    def test_a_piece_reaching_into_the_next_column_does_not_hide_a_body_there(self):
        # Level 12 room 8's statue: drawn from cell (3, 1), 5 px past X 204.
        # The (3, 1) redraw is clipped to its cell (ComputeClipRect 5:0162).
        commands = [['front', 3530, 160, 240, 16, 1, [125, 160, 245, 210], 4, 3, 1]]
        program = {'version': 6, 'level': 12, 'rooms': {'8': commands}}
        shapes = {3530: Image.new('RGBA', (50, 100), 'gray')}
        with (patch('pop2.caverns.room_assets', return_value=(program, {}, {}, shapes)),
              patch('pop2.caverns.loose_variant', return_value=None),
              patch('pop2.caverns.customized_rooms', return_value=frozenset()),
              patch('pop2.caverns.temple_wall_redraws', return_value=frozenset())):
            art = cavern_room(8, level_number=12)
        mask = art.actor_mask(1, bounds=(194, 101, 231, 190))
        self.assertEqual(mask.getpixel((203, 160)), 255)
        # The unclipped masks hid the leg in column 4 as well.
        self.assertEqual(mask.getpixel((206, 160)), 0)
        self.assertEqual(art.actor_cell_occlusion[(3, 1)][1], (160, 140))
        self.assertEqual(art.actor_cell_occlusion[(3, 1)][0].size, (44, 100))

    @unittest.skipUnless(TEMPLE_IMPORTED, 'Imported temple artwork required')
    def test_the_wall_cells_come_from_the_level_words(self):
        walls = temple_wall_redraws(10)
        self.assertIn((2, 5, 0, 3523), walls)
        self.assertNotIn((2, 4, 0, 3523), walls)
        # Native room 21's border row is room 13's last row (RedrawTopFast 3:1f4e).
        self.assertIn((20, 9, -1, 3523), walls)
        self.assertNotIn((20, 8, -1, 3523), walls)
        self.assertEqual(temple_wall_redraws(6), frozenset())


class BorderRowTests(unittest.TestCase):
    # A floor along the border row (the upper room's last row, 0-5) and a
    # row-0 piece that reaches above it.
    COMMANDS = [['back', 3528, 0, 5, 16, -1, [0, 0, 5, 90], 4, 0, -1],
                ['front', 3529, 0, 5, 16, -1, [0, 0, 5, 102], 4, 0, -1],
                ['front', 3530, 102, 60, 16, 0, [0, 102, 60, 153], 4, 2, 0]]

    def art(self, customized):
        program = {'version': 6, 'level': 13, 'rooms': {'25': self.COMMANDS}}
        shapes = {3528: Image.new('RGBA', (90, 5), 'blue'), 3529: Image.new('RGBA', (102, 5), 'red'),
                  3530: Image.new('RGBA', (51, 60), 'gray')}
        with (patch('pop2.caverns.room_assets', return_value=(program, {}, {}, shapes)),
              patch('pop2.caverns.loose_variant', return_value=None),
              patch('pop2.caverns.customized_rooms', return_value=frozenset({25} if customized else ())),
              patch('pop2.caverns.temple_wall_redraws', return_value=frozenset())):
            return cavern_room(25, level_number=13)

    def test_the_border_row_hides_a_head_only_in_its_own_strip_and_cell(self):
        # MarkTop 5:16f2 marks the border cell; RedrawTopFast 3:1f4e redraws
        # its front clipped to it, after row 0's redraw stops at Y 5.
        cells = self.art(False).actor_cell_occlusion
        mask, position = cells[(0, -1)]
        self.assertEqual((position, mask.size), ((0, 0), (51, 5)))
        mask, position = cells[(2, 0)]
        self.assertEqual((position, mask.size), ((102, 5), (51, 55)))
        head = self.art(False).actor_mask(0, bounds=(30, 0, 120, 40))
        self.assertEqual(head.getpixel((30, 2)), 255)
        # Neither the border piece past its cell nor row 0's top hides him.
        self.assertEqual(head.getpixel((60, 2)), 0)
        self.assertEqual(head.getpixel((110, 2)), 0)
        self.assertEqual(head.getpixel((110, 5)), 255)

    def test_a_customized_room_has_no_border_row(self):
        # IsCustomizedRoom 3:1310: RedrawCellFast 3:1cb0-1cb4 skips the
        # border, and row 0's clip reaches the top (ComputeClipRect 5:01ba-01c4).
        art = self.art(True)
        self.assertNotIn((0, -1), art.actor_cell_occlusion)
        self.assertEqual(art.actor_cell_occlusion[(2, 0)][1], (102, 0))
        self.assertEqual(art.background.getpixel((10, 2))[:3], (0, 0, 0))
        self.assertEqual(art.foreground.getpixel((10, 2))[3], 0)
        head = art.actor_mask(0, bounds=(30, 0, 120, 40))
        self.assertEqual((head.getpixel((30, 2)), head.getpixel((110, 2))), (0, 255))
        # Earlier imports drew the default floor along the border.
        self.assertEqual(self.art(False).background.getpixel((10, 2))[:3], (0, 0, 255))


@unittest.skipUnless(unicorn is not None and (RECOVERY / 'resource_forks').is_dir() and TEMPLE_IMPORTED,
                     'Unicorn, the original recovery and the imported temple are required')
class NativeForegroundCellTests(unittest.TestCase):
    # 10:20's border row repeats room 13's wall face; 13:25 is customized
    # (foreground 0xc000) without a CUST record and has no border row.
    ROOMS = {(10, 2), (10, 16), (10, 20), (11, 25), (12, 30), (13, 21), (13, 25)}

    def test_every_dirty_cell_redraw_is_in_the_port_masks(self):
        from tools.probe_foreground_cells import run_probe

        report = run_probe(RECOVERY, levels=(10, 11, 12, 13), rooms=self.ROOMS)
        self.assertEqual(report['totals']['cells'], 280)
        self.assertEqual(report['totals']['missing_pixels'], 0, report['cases'])
        # Nor does a cell hide more: a face whose right cell redraws the
        # empty shape 3522 (12:30) stays inside the left cell.
        self.assertEqual(report['totals']['bleed_pixels'], 0, report['cases'])
        self.assertEqual(report['cases'], {})

    def test_the_masks_without_the_right_column_redraw_are_rejected(self):
        from tools.probe_foreground_cells import run_probe

        with patch('pop2.caverns.temple_wall_redraws', return_value=frozenset()):
            report = run_probe(RECOVERY, levels=(10,), rooms={(10, 2), (10, 20)})
        # 255 of them in 10:20's border cell (9, -1).
        self.assertEqual(report['totals']['missing_pixels'], 6375)

    def test_a_border_row_in_a_customized_room_is_rejected(self):
        from tools.probe_foreground_cells import run_probe

        from pop2.caverns import room_assets

        if not any(command[5] == -1 for command in room_assets(13, 25)[0]['rooms']['25']):
            # An import since recover_room skips it has no border row to
            # bring back (customized_room).
            return
        with patch('pop2.caverns.customized_rooms', return_value=frozenset()):
            report = run_probe(RECOVERY, levels=(13,), rooms={(13, 25)})
        self.assertEqual(report['totals']['own_extra_pixels'], 2550)


    def test_rooms_in_motion_match_each_dirty_cell(self):
        # 10:1's loose floors and scythes, one unit state at a time, and
        # 10:2's gate heights and plate (the native level words changed).
        from tools.probe_foreground_cells import run_pressure_probe, run_variant_probe

        report = run_variant_probe(RECOVERY, levels=(10,), rooms={(10, 1)})
        self.assertEqual(report['totals']['states'], 59)
        self.assertEqual(report['cases'], {})
        report = run_pressure_probe(RECOVERY, levels=(10,), rooms={(10, 2)})
        self.assertEqual(report['totals']['states'], 9)
        self.assertEqual(report['cases'], {})

    def test_two_units_at_once_and_crevices_revealed_on_screen(self):
        # 10:11's two loose floors moving together; 8:1's crevice runs
        # revealed while the room is shown (their cells redrawn).
        from tools.probe_foreground_cells import pair_states, run_variant_probe

        self.assertEqual([label for label, _states in pair_states([2, 4, 1])],
                         ['0=1,1=1', '0=1,1=3'])
        report = run_variant_probe(RECOVERY, levels=(10,), rooms={(10, 11)}, pairs=True)
        self.assertEqual((report['totals']['states'], report['cases']), (2, {}))
        report = run_variant_probe(RECOVERY, levels=(8,), rooms={(8, 1)}, revealed=True)
        self.assertEqual((report['totals']['states'], report['cases']), (2, {}))

    def test_the_masks_at_rest_are_rejected_for_rooms_in_motion(self):
        import tools.probe_foreground_cells as probe

        at_rest = probe.cavern_room

        def resting(room, **arguments):
            return at_rest(room, animated=True, level_number=arguments['level_number'])

        with patch.object(probe, 'cavern_room', resting):
            moved = probe.run_variant_probe(RECOVERY, levels=(10,), rooms={(10, 1)})['totals']
            pressed = probe.run_pressure_probe(RECOVERY, levels=(10,), rooms={(10, 2)})['totals']
        self.assertEqual(moved['missing_pixels'], 14427)
        self.assertEqual(pressed['own_extra_pixels'], 51)

if __name__ == '__main__':
    unittest.main()
