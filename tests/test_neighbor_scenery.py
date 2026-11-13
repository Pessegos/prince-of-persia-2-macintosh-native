"""Imported scenery must observe mechanisms owned by a linked room."""

import unittest
from unittest.mock import patch

from PIL import Image, ImageChops

from pop2.cavern_state import CavernState
from pop2.caverns import cavern_assets, draw_cavern_torches, draw_trapdoors
from pop2.paths import ASSET_DIR


INSTALLED = all((ASSET_DIR / name).is_file() for name in (
    'caverns_entry.json', 'temple_level10.json', 'temple_level11.json', 'temple_level12.json',
    'temple_level13.json', 'Temple.rsrc', 'Caverns.rsrc'))


@unittest.skipUnless(INSTALLED, 'Imported cavern and temple scenery required')
class NeighborSceneryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pop2.game_session import GameResources

        cls.resources = GameResources.load()

    def test_all_upper_trapdoor_locations_have_visible_animation(self):
        from pop2.terrain import LevelMap

        found = []
        for number in (10, 11, 12, 13):
            terrain = LevelMap(self.resources.level(number).data)
            for view in range(32):
                upper = terrain.neighbor(view, 'up')
                if upper is None:
                    continue
                for column in range(10):
                    if terrain.tile(upper, column, 2).kind != 26:
                        continue
                    found.append((number, view + 1, upper + 1, column))
                    with self.subTest(location=found[-1]):
                        state = CavernState()
                        terrain.caverns = state
                        state.trapdoors.trigger(terrain, terrain.tile(upper, column, 2), column)
                        visible_phases = []
                        for phase in range(1, 17):
                            record = state.trapdoors.bank[0]
                            state.trapdoors.bank[0] = (*record[:7], phase)
                            _, objects = state.trapdoors.present(terrain)
                            frame = draw_trapdoors(Image.new('RGBA', (510, 365)), view,
                                                   objects, terrain, level_number=number)
                            if frame.getbbox() is not None:
                                visible_phases.append(phase)
                        self.assertIn(3, visible_phases)
                        terrain.caverns = None
        self.assertEqual(found, [(10, 4, 25, 1), (10, 9, 8, 5), (10, 19, 12, 7),
                                 (12, 3, 21, 3), (12, 17, 10, 1), (13, 7, 17, 1)])

    def test_neighbor_gate_and_floor_changes_rebuild_the_visible_room(self):
        from pop2.level_rendering import LevelRenderer

        renderer = LevelRenderer(self.resources.level(3), preload_room=False)
        for category, view, key in (('gate', 3, (5, 29)), ('floor', 0, (31, 28))):
            with self.subTest(category=category):
                state = CavernState()
                before = renderer.room(view, state)
                if category == 'gate':
                    state.plates.foreground[key] = 184
                else:
                    choices = renderer.cavern_program['loose_floors']['cells'][f'{key[0]}:{key[1]}']
                    state.loose.tiles[key] = choices[-1]
                after = renderer.room(view, state)
                self.assertIsNot(before, after)
                self.assertTrue(any(ImageChops.difference(a, b).convert('RGB').getbbox()
                                    for a, b in ((before.background, after.background),
                                                 (before.foreground, after.foreground))))

    def test_neighbor_candle_reads_and_advances_its_source_cell(self):
        program = cavern_assets(13)[0]
        records = program['torches']['31']
        self.assertIn((1, 19), {(r['room'], r['cell']) for r in records})
        state = CavernState(torches={(1, 19): 0})
        blank = Image.new('RGBA', (510, 365))
        before = draw_cavern_torches(blank.copy(), 31, state, level_number=13)
        with patch('pop2.cavern_state.random.randint', return_value=1):
            state.advance_torches(records)
        self.assertNotEqual(state.torches[1, 19], 0)
        after = draw_cavern_torches(blank.copy(), 31, state, level_number=13)
        self.assertIsNotNone(ImageChops.difference(before, after).convert('RGB').getbbox())


if __name__ == '__main__':
    unittest.main()
