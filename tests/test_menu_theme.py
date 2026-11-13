import os
import unittest
from types import SimpleNamespace
from unittest import mock

from PIL import Image

from pop2 import menu_theme
from pop2.game_menu import GameMenu
from pop2.menu_theme import CAVERNS, DESERT, NEUTRAL, NEUTRAL_ROLES, PALACE, RUINS, TEMPLE, THEMES, c


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
        self.assertIs(menu_theme.theme_for(game(1, desert=object())), DESERT)
        self.assertIs(menu_theme.theme_for(game(3, caverns=object())), CAVERNS)
        self.assertIs(menu_theme.theme_for(game(4, caverns=object())), RUINS)
        self.assertIs(menu_theme.theme_for(game(2, caverns=object())), TEMPLE)
        # The last level (kind 6) shares the cavern state but is not a cavern:
        # the first version gave it the cavern rock.
        self.assertIs(menu_theme.theme_for(game(6, caverns=object())), NEUTRAL)
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

    def test_every_theme_keeps_text_readable_and_frames_free_of_black(self):
        def light(colour):
            red, green, blue = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
            return 0.299 * red + 0.587 * green + 0.114 * blue

        for theme in THEMES.values():
            with self.subTest(theme=theme.name):
                for back in ('panel', 'row', 'selected'):
                    self.assertGreater(light(theme.colour('text')) - light(theme.colour(back)), 110)
                    self.assertGreater(light(theme.colour('accent')) - light(theme.colour(back)), 90)
                self.assertGreater(light(theme.colour('muted')) - light(theme.colour('row')), 40)
                if theme.frame == 'rock':
                    self.assertEqual(theme.frame_width, 9)
                    for colour in [shade for shade, _count in theme.grain] + list(theme.shades):
                        self.assertGreater(light(colour), 15)
                    picture = menu_theme._frame_picture(theme.name, (120, 90)).load()
                    self.assertEqual(picture[0, 0][3], 0)
                    self.assertEqual(picture[60, 45], menu_theme._rgb(theme.colour('panel')) + (255,))
                elif theme.frame == 'bands':
                    self.assertEqual(theme.frame_width, len(theme.bands))
                    picture = menu_theme._frame_picture(theme.name, (120, 90)).load()
                    self.assertEqual(picture[60, 1], menu_theme._rgb(theme.bands[1][0]) + (255,))
                    self.assertEqual(picture[60, 45], menu_theme._rgb(theme.colour('panel')) + (255,))
                elif theme.frame is not None:
                    # Drawn frames: sand, the ruins' band of sockets, the temple's columns.
                    self.assertIn(theme.frame_width, (9, 11, 13))
                    picture = menu_theme._frame_picture(theme.name, (120, 90)).load()
                    self.assertEqual(picture[60, 45], menu_theme._rgb(theme.colour('panel')) + (255,))
                    for point in ((60, 3), (60, 86), (3, 45), (116, 45)):  # inside any worn edge
                        self.assertEqual(picture[point][3], 255)
                        self.assertGreater(sum(picture[point][:3]), 30)  # dark, never black
                else:
                    self.assertEqual(theme.frame_width, 0)

    def test_menu_frame_stays_clear_of_the_scroll_arrows(self):
        # The arrows are drawn at x 437-443, inside the panel's right edge.
        for theme in (PALACE, DESERT, CAVERNS, RUINS, TEMPLE):
            outer = menu_theme.frame_rect(GameMenu.PANEL, theme, True)
            self.assertGreaterEqual(outer[2] - theme.frame_width, GameMenu.PANEL[2])
            self.assertLessEqual(outer[0] + theme.frame_width, GameMenu.PANEL[0])

    def test_window_resolution_pages_get_the_frame_enlarged_without_smoothing(self):
        def point(x, y):
            return x * 3, y * 3

        image = Image.new('RGBA', (1536, 1152), (9, 9, 9, 255))
        self.assertFalse(menu_theme.panel_scaled(image, (28, 16, 484, 368), point))  # neutral: page draws it
        self.assertEqual(image.getpixel((300, 300)), (9, 9, 9, 255))
        menu_theme.use(PALACE)
        self.assertTrue(menu_theme.panel_scaled(image, (28, 16, 484, 368), point))
        # These pages cover the health strip, so the frame may reach below row 364.
        outer = (28 - 12, 16 - 6, 484 + 12, 368 + 7)
        lit = (0xff, 0xff, 0xd6, 255)
        for dx in range(3):
            for dy in range(3):  # one game pixel is one 3x3 block
                self.assertEqual(image.getpixel(((outer[0] + 40) * 3 + dx, (outer[1] + 1) * 3 + dy)), lit)
                self.assertEqual(image.getpixel(((outer[0] + 40) * 3 + dx, (outer[3] - 1) * 3 + dy)), lit)
        self.assertEqual(image.getpixel((outer[0] * 3 - 1, 600)), (9, 9, 9, 255))
        self.assertEqual(image.getpixel((768, 576)), (0x00, 0x18, 0x31, 255))
        colours = {colour for _count, colour in image.getcolors(1 << 20)}
        allowed = {menu_theme._rgb(colour) + (255,) for band in PALACE.bands for colour in band}
        self.assertLessEqual(colours, allowed | {(9, 9, 9, 255), (0x00, 0x18, 0x31, 255)})

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

    def test_desert_frame_is_sand_with_no_water_and_rounded_corners(self):
        size = (387, 364)
        picture = menu_theme._frame_picture('desert', size)
        pixels = picture.load()
        for corner in ((0, 0), (size[0] - 1, 0), (0, size[1] - 1), (size[0] - 1, size[1] - 1)):
            self.assertEqual(pixels[corner][3], 0)
        panel = menu_theme._rgb(DESERT.colour('panel')) + (255,)
        self.assertEqual(pixels[size[0] // 2, size[1] // 2], panel)
        band = {colour for _count, colour in picture.crop((40, 0, 340, 11)).getcolors()}
        # The first draft had a surf line: no colour of the band is bluer than it is red.
        self.assertTrue(all(blue < red for red, _green, blue, _alpha in band))
        # The details differ from one another: the top band is not the same strip repeated.
        strips = {picture.crop((left, 2, left + 30, 9)).tobytes() for left in range(40, 340, 30)}
        self.assertEqual(len(strips), 10)

    def test_ruins_frame_has_square_sockets_and_keeps_most_of_its_band(self):
        size = (387, 364)
        pixels = menu_theme._frame_picture('ruins', size).load()
        sunk = menu_theme._rgb('#413871') + (255,)
        for y in (4, size[1] - 5):
            run = longest = 0
            for x in range(size[0]):
                run = run + 1 if pixels[x, y] == sunk else 0
                longest = max(longest, run)
            self.assertLess(longest, 9)         # a draft joined two sockets into a rectangle 11 wide
        # Pieces are broken out of the edge, but never more than five of its nine rows.
        missing = [sum(pixels[x, y][3] == 0 for y in range(9)) for x in range(12, size[0] - 12)]
        self.assertGreater(max(missing), 1)
        self.assertLessEqual(max(missing), 5)
        self.assertGreater(missing.count(0), len(missing) // 2)

    def test_temple_frieze_is_never_cut_and_is_the_same_above_and_below(self):
        for size in ((387, 364), (330, 190), (480, 366), (316, 262)):
            with self.subTest(size=size):
                picture = menu_theme._frame_picture('temple', size)
                width, height = size
                top = picture.crop((0, 2, width, 9))
                self.assertEqual(top.tobytes(), picture.crop((0, height - 9, width, height - 2)).tobytes())
                # Both ends carry the whole corner block, whatever the width.
                self.assertEqual(top.crop((0, 0, 13, 7)).tobytes(), top.crop((width - 13, 0, width, 7)).tobytes())
                ground = menu_theme._rgb('#520808') + (255,)
                pixels = top.load()
                for x in (14, width - 15):      # bare ground beside each corner block: no motif runs into it
                    self.assertTrue(all(pixels[x, y] == ground for y in range(7)))

    def test_ruins_sign_darkens_only_the_page_backgrounds(self):
        menu_theme.use(RUINS)
        panel, row, text = (menu_theme._rgb(RUINS.colour(role)) + (255,) for role in ('panel', 'row', 'text'))
        image = Image.new('RGBA', (512, 384), panel)
        image.paste(row, (80, 150, 440, 170))
        image.paste(text, (200, 155, 300, 165))
        menu_theme.watermark(image, (64, 7, 448, 357))
        colours = {colour for _count, colour in image.getcolors()}
        self.assertEqual(len(colours), 5)                     # two backgrounds, each also darkened, and the text
        self.assertIn(text, colours)
        for colour in colours - {panel, row, text}:
            self.assertLess(sum(colour[:3]), sum(row[:3]))    # darker, as the sign is on the walls
        once = image.tobytes()
        menu_theme.watermark(image, (64, 7, 448, 357))
        self.assertEqual(image.tobytes(), once)               # drawing it again changes nothing
        menu_theme.use(CAVERNS)
        plain = Image.new('RGBA', (512, 384), panel)
        menu_theme.watermark(plain, (64, 7, 448, 357))
        self.assertEqual(len(plain.getcolors()), 1)           # only the ruins carry a sign

    def test_save_page_keeps_the_sign_when_only_its_list_is_redrawn(self):
        from pathlib import Path

        from pop2.save_slots import SaveBrowser, SaveSlot
        menu_theme.use(RUINS)
        font = FakeFont()
        frame = Image.new('RGBA', (1024, 768), (40, 30, 60, 255))
        slots = tuple(SaveSlot(Path(f'none-{i}'), f'Save {i}', True, level=i + 1, date='-') for i in range(5))
        browser = SaveBrowser(slots, 'load', selected=1)
        browser.focus = 100
        full = browser.draw(frame, font, background_key=1)
        browser.focus = 101                                   # a key press: the cached page, list repainted
        again = browser.draw(frame, font, background_key=1)
        row = menu_theme._rgb(RUINS.colour('row')) + (255,)
        signed = tuple(round(a + (b - a) * 0.4) for a, b in zip(row[:3], menu_theme._rgb(RUINS.mark))) + (255,)

        def count(image):
            return sum(n for n, colour in image.crop((80, 198, 445, 615)).getcolors(1 << 16) if colour == signed)

        self.assertGreater(count(full), 500)
        self.assertEqual(count(again), count(full))

    def test_save_dialog_takes_the_frame_and_carries_no_sign(self):
        from pathlib import Path

        from pop2.save_slots import SaveBrowser, SaveSlot
        font = FakeFont()
        frame = Image.new('RGBA', (1024, 768), (40, 30, 60, 255))
        slots = tuple(SaveSlot(Path(f'none-{i}'), f'Save {i}', True, level=i + 1, date='-') for i in range(5))

        def dialog(theme):
            menu_theme.use(theme)
            browser = SaveBrowser(slots, 'load', selected=1)
            browser.confirmation, browser.focus = 'delete', 30
            return browser.draw(frame, font, background_key=1)

        above = (500, 2 * 121 - 4)                            # just outside the dialog's top edge
        self.assertNotEqual(dialog(PALACE).getpixel(above), dialog(NEUTRAL).getpixel(above))
        palace = {menu_theme._rgb(colour) + (255,) for band in PALACE.bands for colour in band}
        self.assertIn(dialog(PALACE).getpixel(above), palace)
        # The serpent crossed this empty strip between the text and the buttons.
        strip = dialog(RUINS).crop((200, 418, 824, 438))
        self.assertEqual(strip.getcolors(), [(strip.width * strip.height,
                                              menu_theme._rgb(RUINS.colour('panel')) + (255,))])

    def test_cutscene_viewer_takes_the_theme_and_leaves_room_for_its_frame(self):
        from pop2.cutscene_gallery import CutsceneGallery
        from pop2.cutscenes import CutsceneCollection

        font = FakeFont()
        font.height = 10
        source = Image.new('RGBA', (1920, 1080), (40, 30, 60, 255))
        with mock.patch('pop2.cutscene_gallery.chapter_available', return_value=True):
            gallery = CutsceneGallery(CutsceneCollection(seen={'opening'}),
                                      lambda index: Image.new('RGB', (510, 384), '#773311'))
            neutral = gallery.draw(source, font, visible=True)
            self.assertEqual((gallery.PANEL[0], gallery.PANEL[3], gallery.PREVIOUS[0]), (8, 363, 8))
            plain = {colour for _count, colour in neutral.getcolors(1 << 20)}
            self.assertIn((0x8c, 0x79, 0x54), plain)                      # its own outline
            for theme in (PALACE, DESERT, CAVERNS, RUINS, TEMPLE):
                with self.subTest(theme=theme.name):
                    menu_theme.use(theme)
                    page = gallery.draw(source, font, visible=True)        # same gallery: nothing stale is reused
                    colours = {colour for _count, colour in page.getcolors(1 << 20)}
                    for role in ('panel', 'card', 'card_selected', 'accent', 'track'):
                        self.assertIn(menu_theme._rgb(theme.colour(role)), colours, role)
                    for grey in ('#181818', '#252525', '#493c25', '#8c7954', '#282828', '#999076'):
                        self.assertNotIn(menu_theme._rgb(grey), colours, grey)
                    # The frame stands outside the panel, and the arrows outside the frame.
                    self.assertGreater(gallery.PANEL[0], theme.frame_width)
                    self.assertEqual(gallery.PREVIOUS[0], gallery.PANEL[0])
                    self.assertEqual(gallery.PANEL[3], 368)
                    scale = 1080 / 384
                    inside = round((gallery.PANEL[0] + 2) * scale), round(200 * scale)
                    self.assertEqual(page.getpixel(inside), menu_theme._rgb(theme.colour('panel')))
                    outside = round((gallery.PANEL[0] - 4) * scale), round(200 * scale)
                    self.assertNotEqual(page.getpixel(outside), menu_theme._rgb(theme.colour('panel')))
            menu_theme.use(NEUTRAL)
            self.assertEqual(gallery.draw(source, font, visible=True).tobytes(), neutral.tobytes())


if __name__ == '__main__':
    unittest.main()
