"""Moving panels must remain visible across room boundaries."""

import unittest
from unittest.mock import Mock, patch

from PIL import Image

from pop2.caverns import draw_trapdoors


class TrapDoorDrawingTests(unittest.TestCase):
    def test_panels_cross_vertical_links_and_clip_to_the_view(self):
        terrain = Mock()
        terrain.neighbor.side_effect = lambda room, direction: {
            'up': 1, 'down': 2}[direction]
        sprite = Image.new('RGBA', (40, 30), 'cyan')
        # Each projected panel has its bottom at (20, 20), leaving the top
        # ten pixels offscreen.
        for room, x, y in ((0, 20, 20), (1, 20, 384), (2, 20, -344)):
            with self.subTest(room=room), \
                    patch('pop2.caverns.room_assets', return_value=(None, None, None, None)), \
                    patch('pop2.caverns.cavern_command_sprite', return_value=sprite):
                background = Image.new('RGBA', (510, 365))
                result = draw_trapdoors(background, 0, [(room, 3551, x, y, x)], terrain)
                self.assertEqual(result.getbbox(), (20, 0, 60, 20))
                self.assertEqual(result.getpixel((20, 0)), (0, 255, 255, 255))
                self.assertIsNone(background.getbbox())

    def test_unrelated_room_and_missing_link_do_not_draw(self):
        terrain = Mock()
        terrain.neighbor.return_value = None
        background = Image.new('RGBA', (510, 365))
        with patch('pop2.caverns.room_assets') as assets:
            self.assertIs(draw_trapdoors(background, 0, [(8, 3551, 20, 20, 20)], terrain),
                          background)
        assets.assert_not_called()


if __name__ == '__main__':
    unittest.main()
