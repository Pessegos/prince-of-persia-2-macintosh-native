"""Front pieces over items and falling slabs, as the original repaints them."""

from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from pop2.paths import ASSET_DIR

TEMPLE_IMPORTED = all((ASSET_DIR / name).is_file()
                      for name in ('Prince.rsrc', 'Temple.rsrc', 'temple_level10.json'))
FINAL_IMPORTED = (ASSET_DIR / 'Prince.rsrc').is_file() and (ASSET_DIR / 'final_level14.json').is_file()


def level_data(number):
    from pop2.level_data import LevelDefinition
    from pop2.render_opening import load_resource_file

    return LevelDefinition.read(load_resource_file('Prince.rsrc'), number).data


@unittest.skipUnless(FINAL_IMPORTED, 'Imported level 14 required')
class ItemUnderLaterFrontPieceTests(unittest.TestCase):
    def frames(self):
        from pop2.cavern_state import CavernState
        from pop2.caverns import cavern_room, draw_cavern_flasks
        from pop2.terrain import LevelMap

        static = cavern_room(7, animated=False, level_number=14)
        animated = cavern_room(7, animated=True, level_number=14)
        # The static room draws every command in the front pass's order.
        original = np.asarray(Image.alpha_composite(static.background, static.foreground).convert('RGB'))
        frame = Image.alpha_composite(animated.background, animated.foreground)
        drawn = draw_cavern_flasks(frame, 7, CavernState(), LevelMap(level_data(14)), level_number=14)
        return original, np.asarray(drawn.convert('RGB'))

    def test_level_14_room_7_flask_stays_under_shape_4179(self):
        original, port = self.frames()
        self.assertEqual(int((original != port).any(axis=2).sum()), 0)

    def test_the_flask_over_the_finished_scenery_is_rejected(self):
        with patch('pop2.caverns.later_front_cover', return_value=None):
            original, port = self.frames()
        difference = (original != port).any(axis=2)
        self.assertEqual(int(difference.sum()), 3)
        self.assertTrue(difference[226:229, 447:449].any())


@unittest.skipUnless(TEMPLE_IMPORTED, 'Imported temple artwork required')
class FallingSlabFrontTests(unittest.TestCase):
    def frame(self, y):
        from pop2.caverns import cavern_room, draw_cavern_falling
        from pop2.loose_floors import FallingFloor

        art = cavern_room(19, animated=True, level_number=10)
        frame = Image.alpha_composite(art.background, art.foreground)
        state = SimpleNamespace(loose=SimpleNamespace(falling=[FallingFloor(19, 3, 0, y, mob_type=3)]))
        draw_cavern_falling(frame, 19, state, level_data(10), art, level_number=10)
        return np.asarray(frame.convert('RGB'))

    def test_a_statue_rim_outside_the_slab_rectangle_stays_behind_it(self):
        # Level 10 room 19 (native 20): the slab passing the statue's arm.
        # ComputeMobRect 5:32f6 marks its cells; each one's front redraw is
        # clipped to the cell and that rectangle.
        import pop2.caverns as caverns

        now = self.frame(159)
        with patch.object(caverns, 'mob_front_cover', lambda art, _mob: art.foreground.getchannel('A')):
            whole = self.frame(159)
        difference = (now != whole).any(axis=2)
        self.assertEqual(int(difference.sum()), 31)


if __name__ == '__main__':
    unittest.main()
