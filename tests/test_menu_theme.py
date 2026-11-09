import os
import unittest
from types import SimpleNamespace
from unittest import mock

from PIL import Image

from pop2 import menu_theme
from pop2.game_menu import GameMenu
from pop2.menu_theme import CAVERNS, NEUTRAL, NEUTRAL_ROLES, PALACE, c


class FakeFont:
    glyphs = {code: (0, 0, 6) for code in range(256)}

    def text(self, value, color=(255, 255, 255, 255)):
        return Image.new('RGBA', (max(1, 6 * len(value)), 10), color)


class MenuThemeTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(menu_theme.use, NEUTRAL)
        menu_theme.use(NEUTRAL)

    def test_neutral_theme_leaves_every_menu_colour_as_written(self):
        for neutral in NEUTRAL_ROLES.values():
            self.assertEqual(c(neutral), neutral)
        self.assertEqual(c('#F4D873'), '#F4D873')
        self.assertEqual(c('#abcdef'), '#abcdef')  # not a menu colour: untouched
        self.assertEqual((NEUTRAL.dim, NEUTRAL.frame), (100, None))

    def test_neutral_panel_is_the_plain_grey_rectangle(self):
        image = Image.new('RGBA', (60, 40), (9, 9, 9, 255))
        menu_theme.panel(image, (10, 5, 50, 30))
        self.assertEqual(image.getpixel((10, 5)), (0x85, 0x85, 0x85, 255))
        self.assertEqual(image.getpixel((30, 20)), (0x18, 0x18, 0x18, 255))
        self.assertEqual(image.getpixel((9, 5)), (9, 9, 9, 255))

    def test_a_theme_recolours_the_neutral_values(self):
        menu_theme.use(CAVERNS)
        self.assertEqual(c('#f4d873'), '#f7b54a')
        self.assertEqual(c('#F4D873'), '#f7b54a')
        self.assertEqual(c('#abcdef'), '#abcdef')
        self.assertEqual(menu_theme.current().dim, 140)
        self.assertIs(menu_theme.use(None), NEUTRAL)

    def test_unknown_role_is_rejected(self):
        with self.assertRaises(ValueError):
            menu_theme.MenuTheme('broken', {'no_such_role': '#000000'})

    def test_theme_follows_the_level(self):
        def game(kind=None, **state):
            fields = {'caverns': None, 'desert': None, 'harbor': None, **state}
            return SimpleNamespace(level=SimpleNamespace(kind=kind), **fields)

        patcher = mock.patch.dict(os.environ, {'POP2_MENU_THEME': ''})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.assertIs(menu_theme.theme_for(None), NEUTRAL)
        self.assertIs(menu_theme.theme_for(game()), NEUTRAL)
        self.assertIs(menu_theme.theme_for(game(5, harbor=object())), PALACE)
        self.assertIs(menu_theme.theme_for(game(1, desert=object())), NEUTRAL)
        self.assertIs(menu_theme.theme_for(game(3, caverns=object())), CAVERNS)
        # Ruins and temple are not drawn yet and must not borrow the cavern rock.
        self.assertIs(menu_theme.theme_for(game(4, caverns=object())), NEUTRAL)
        self.assertIs(menu_theme.theme_for(game(2, caverns=object())), NEUTRAL)
        # One theme can be forced everywhere; "neutral" turns the level themes off.
        os.environ['POP2_MENU_THEME'] = 'neutral'
        self.assertIs(menu_theme.theme_for(game(3, caverns=object())), NEUTRAL)
        os.environ['POP2_MENU_THEME'] = 'Caverns'
        self.assertIs(menu_theme.theme_for(game(5, harbor=object())), CAVERNS)

    def test_frame_stays_inside_the_playfield(self):
        self.assertEqual(menu_theme.frame_rect(GameMenu.PANEL, CAVERNS), (62, 2, 450, 364))
        self.assertEqual(menu_theme.frame_rect(GameMenu.PANEL, PALACE), (63, 1, 449, 364))
        self.assertEqual(menu_theme.frame_rect((0, 0, 511, 383), CAVERNS), (1, 0, 510, 364))
        # Controls: its labels reach the panel's sides, so the frame stands outside them.
        self.assertEqual(menu_theme.frame_rect((21, 7, 491, 357), CAVERNS, True), (12, 2, 500, 364))
        self.assertEqual(menu_theme.frame_rect((21, 7, 491, 357), PALACE, True), (9, 1, 503, 364))
        self.assertEqual(menu_theme.frame_rect((21, 7, 491, 357), NEUTRAL, True), (21, 7, 491, 357))

    def test_rock_frame_has_no_outline_and_no_black_in_the_rock(self):
        size = (389, 363)
        picture = menu_theme._frame_picture('caverns', size)
        self.assertIs(picture, menu_theme._frame_picture('caverns', size))  # drawn once
        pixels = picture.load()
        fill = (0x18, 0x08, 0x08, 255)
        self.assertEqual(pixels[size[0] // 2, size[1] // 2], fill)
        self.assertEqual(pixels[0, 0][3], 0)  # knocked-off corner shows the room
        rock = [pixels[x, y] for y in range(size[1]) for x in range(size[0])
                if pixels[x, y][3] and pixels[x, y] not in (fill, (0, 0, 0, 255))]
        self.assertGreater(len(rock), 9000)
        # The first mock-up repeated a black gap from the cropped art along the
        # outer edge. Every rock pixel is one of the rock shades, none black.
        self.assertTrue(all(sum(pixel[:3]) >= 60 for pixel in rock))
        # Black appears only as the rock's shadow on the panel, never in the outer band.
        for y in range(size[1]):
            for x in list(range(4)) + list(range(size[0] - 4, size[0])):
                self.assertNotEqual(pixels[x, y], (0, 0, 0, 255))
        for x in range(size[0]):
            for y in list(range(4)) + list(range(size[1] - 4, size[1])):
                self.assertNotEqual(pixels[x, y], (0, 0, 0, 255))

    def test_cornice_frame_is_lit_on_its_outer_edge_on_every_side(self):
        size = (387, 364)
        pixels = menu_theme._frame_picture('palace', size).load()
        middle_x, middle_y = size[0] // 2, size[1] // 2
        for point in ((middle_x, 1), (middle_x, size[1] - 2), (1, middle_y), (size[0] - 2, middle_y)):
            self.assertEqual(pixels[point], (0xff, 0xff, 0xd6, 255))
        for point in ((middle_x, 11), (11, middle_y), (size[0] - 12, middle_y)):
            self.assertEqual(pixels[point], (0xfd, 0xae, 0x61, 255))  # the inner orange trim
        self.assertEqual(pixels[middle_x, middle_y], (0x00, 0x18, 0x31, 255))

    def test_game_menu_takes_the_theme(self):
        viewport = Image.new('RGBA', (512, 384), (200, 200, 200, 255))
        font = FakeFont()
        neutral = GameMenu().draw(viewport.copy(), font)
        self.assertEqual(neutral.getpixel(GameMenu.PANEL[:2]), (0x85, 0x85, 0x85, 255))
        self.assertEqual(neutral.getpixel((5, 5)), (122, 122, 122, 255))  # 100/255 black veil
        menu_theme.use(CAVERNS)
        caverns = GameMenu().draw(viewport.copy(), font)
        self.assertEqual(caverns.getpixel((5, 5)), (90, 90, 90, 255))  # 140/255: darker room
        row = GameMenu().row_rect(0)
        self.assertEqual(caverns.getpixel((row[0], row[1])), (0xf7, 0xb5, 0x4a, 255))
        self.assertEqual(caverns.getpixel((row[0] + 3, row[1] + 3)), (0x52, 0x39, 0x31, 255))
        other = GameMenu().row_rect(1)
        self.assertEqual(caverns.getpixel((other[0] + 3, other[1] + 3)), (0x29, 0x10, 0x08, 255))
        menu_theme.use(NEUTRAL)
        self.assertEqual(list(GameMenu().draw(viewport.copy(), font).getdata()), list(neutral.getdata()))


if __name__ == '__main__':
    unittest.main()
