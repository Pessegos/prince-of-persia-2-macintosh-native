import functools
import os
import random
import unittest
from types import SimpleNamespace
from unittest import mock

import numpy
from PIL import Image

from pop2 import menu_theme
from pop2.game_menu import GameMenu
from pop2.menu_theme import CAVERNS, CHESS, DESERT, NEUTRAL, NEUTRAL_ROLES, PALACE, RUINS, SPIDER, TEMPLE, THEMES, c


class FakeFont:
    glyphs = {code: (0, 0, 6) for code in range(256)}

    def text(self, value, color=(255, 255, 255, 255)):
        return Image.new('RGBA', (max(1, 6 * len(value)), 10), color)


def pixel_by_pixel_rock(theme, size, fill):
    """The rock frame as it was first painted, one pixel at a time: the reference."""
    width, height = size
    thickness = menu_theme._ROCK_THICKNESS
    rng = random.Random(width * 1000 + height)
    corner = (3, 2, 1)
    top_out, bottom_out = menu_theme._worn(width, rng, corner), menu_theme._worn(width, rng, corner)
    left_out, right_out = menu_theme._worn(height, rng, corner), menu_theme._worn(height, rng, corner)
    top_in, bottom_in = menu_theme._worn(width, rng, ()), menu_theme._worn(width, rng, ())
    left_in, right_in = menu_theme._worn(height, rng, ()), menu_theme._worn(height, rng, ())

    def solid(x, y):
        return (0 <= x < width and 0 <= y < height
                and top_out[x] <= y <= height - 1 - bottom_out[x]
                and left_out[y] <= x <= width - 1 - right_out[y])

    def hole(x, y):
        return (0 <= x < width and 0 <= y < height
                and thickness + top_in[x] <= y <= height - 1 - thickness - bottom_in[x]
                and thickness + left_in[y] <= x <= width - 1 - thickness - right_in[y])

    @functools.lru_cache(maxsize=None)     # each pixel is asked about by its four neighbours
    def rock(x, y):
        return solid(x, y) and not hole(x, y)

    grain_rng = random.Random(0x60C)
    shades = [menu_theme._rgb(colour) for colour, _count in theme.grain]
    weights = [count for _colour, count in theme.grain]
    every_shade = tuple(shades) + tuple(menu_theme._rgb(colour) for colour in theme.shades)
    period = 240
    grain = []
    for _row in range(thickness + 4):
        row = []
        while len(row) < period:
            row += [grain_rng.choices(shades, weights)[0]] * grain_rng.choice(menu_theme._ROCK_RUNS)
        grain.append(row[:period])

    @functools.lru_cache(maxsize=None)     # few grain colours, four ways of lighting them
    def nearest(colour, shade):
        lit = tuple(channel * shade for channel in colour)
        return min(every_shade, key=lambda s: sum((a - b) ** 2 for a, b in zip(s, lit)))

    picture = Image.new('RGBA', size, (0, 0, 0, 0))
    opaque_fill = fill + (255,)
    menu_theme._fill_inside(picture, thickness + 4, opaque_fill)
    pixels = picture.load()
    for y in range(height):
        for x in menu_theme._edge_columns(width, height, y, thickness + 4):
            if hole(x, y):
                # The rock stands proud of the panel: a hard shadow below and beside it.
                pixels[x, y] = (0, 0, 0, 255) if rock(x, y - 1) or rock(x - 1, y) else opaque_fill
                continue
            if not solid(x, y):
                continue
            vertical, horizontal = min(y, height - 1 - y), min(x, width - 1 - x)
            depth = min(vertical, horizontal, len(grain) - 1)
            shade = 1.0
            if not rock(x - 1, y):
                shade = 1.15
            if not rock(x + 1, y):
                shade = 0.7
            if not rock(x, y - 1):
                shade = 1.3
            if not rock(x, y + 1):
                shade = 0.6
            colour = grain[depth][(x if vertical <= horizontal else y) % period]
            if shade != 1.0:
                colour = nearest(colour, shade)
            pixels[x, y] = colour + (255,)
    return picture


class RockFrameTest(unittest.TestCase):
    def test_rock_frame_is_the_pixel_by_pixel_painting_drawn_faster(self):
        # The painter was rewritten with arrays (50 ms -> under 30 ms for a wide page);
        # every pixel must stay as the first painting drew it, small and odd sizes too.
        fill = menu_theme._rgb(CAVERNS.colour('panel'))
        sizes = [(660, 372), (470, 376), (700, 350), (30, 30), (26, 40), (40, 26), (12, 12), (27, 27), (300, 27)]
        rng = random.Random(5)
        sizes += [(rng.randint(20, 900), rng.randint(20, 500)) for _ in range(6)]
        for size in sizes:
            with self.subTest(size=size):
                self.assertEqual(menu_theme._rock_frame(CAVERNS, size, fill).tobytes(),
                                 pixel_by_pixel_rock(CAVERNS, size, fill).tobytes())


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
        # the first version gave it the cavern rock. Its theme follows the room.
        self.assertIs(menu_theme.theme_for(game(6, caverns=object())), NEUTRAL)
        for room, theme in ((0, PALACE), (1, PALACE), (2, SPIDER), (3, CHESS), (4, CHESS), (8, SPIDER),
                            (5, NEUTRAL), (10, PALACE)):
            with self.subTest(room=room):
                self.assertIs(menu_theme.theme_for(game(6, caverns=object(), room_id=room)), theme)
        # One theme can be forced everywhere; "neutral" turns the level themes off.
        os.environ['POP2_MENU_THEME'] = 'neutral'
        self.assertIs(menu_theme.theme_for(game(3, caverns=object())), NEUTRAL)
        os.environ['POP2_MENU_THEME'] = 'Caverns'
        self.assertIs(menu_theme.theme_for(game(5, harbor=object())), CAVERNS)

    def test_chess_frame_alternates_between_violet_corners(self):
        rgb = menu_theme._rgb
        violet, pearl = (rgb(shades[1]) + (255,) for shades in menu_theme._CHESS_SQUARES)
        for size in ((120, 90), (391, 305), (417, 340)):
            with self.subTest(size=size):
                width, height = size
                picture = menu_theme._frame_picture('chess', size).load()
                board = height - 3
                for x, y in ((5, 5), (width - 5, 5), (5, board - 5), (width - 5, board - 5)):
                    self.assertEqual(picture[x, y], violet)
                # Along each side the squares change at every run, so no two
                # neighbours share a colour and both corners end violet.
                for spans, point in (
                        (menu_theme._chess_runs(width - 20, 10), lambda along: (10 + along, 5)),
                        (menu_theme._chess_runs(board - 20, 10), lambda along: (5, 10 + along))):
                    self.assertEqual(len(spans) % 2, 1)
                    faces = [picture[point((start + end) // 2)] for start, end in spans]
                    self.assertEqual(faces, [pearl if index % 2 == 0 else violet for index in range(len(spans))])
                # Under the lower row: the board's front face, never black.
                for row, colour in enumerate(menu_theme._CHESS_FACE):
                    self.assertEqual(picture[width // 2, board + row], rgb(colour) + (255,))

    def test_frame_stays_inside_the_playfield(self):
        # The F1 list no longer scrolls, so its panel is shorter than the playfield.
        self.assertEqual(menu_theme.frame_rect(GameMenu.PANEL, CAVERNS), (62, 31, 450, 335))
        self.assertEqual(menu_theme.frame_rect(GameMenu.PANEL, PALACE), (63, 30, 449, 335))
        self.assertEqual(menu_theme.frame_rect(GameMenu.OPTIONS_PANEL, CAVERNS), (62, 34, 450, 332))
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
                    for point in ((60, 0), (60, 89), (0, 45), (119, 45)):
                        self.assertGreater(sum(picture[point][:3]), 150)    # a soft dark outline, not black
                elif theme.frame == 'spider':
                    # A coat of hair: the band is solid, the hairs beyond it leave the room showing.
                    self.assertEqual(theme.frame_width, 18)
                    picture = menu_theme._frame_picture(theme.name, (120, 90)).load()
                    self.assertEqual(picture[60, 45], menu_theme._rgb(theme.colour('panel')) + (255,))
                    for point in ((60, 14), (60, 75), (14, 45), (105, 45)):    # in the velvet band
                        self.assertEqual(picture[point][3], 255)
                        self.assertGreater(sum(picture[point][:3]), 20)
                elif theme.frame is not None:
                    # Drawn frames: sand, the ruins' band of sockets, the temple's columns,
                    # level 14's row of chessboard squares.
                    self.assertIn(theme.frame_width, (9, 10, 11, 13))
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

    def test_palace_cornice_is_laid_stone_by_stone_like_the_first_rooms_wall(self):
        # The pearls, the stone joints and the dotted trim repeat every 51 pixels
        # in the same order along every side, as on the room's wall; none of them
        # is speckled at random any more.
        woven = {depth for depth, band in enumerate(PALACE.bands) if isinstance(band, menu_theme._Weave)}
        self.assertEqual(woven, {3, 4, 5, 6, 8, 10})
        self.assertEqual(set(PALACE.bands[10]), {'#52b5bd', '#4993b5'})     # the wall's two turquoises
        width, height = size = (300, 200)
        picture = menu_theme._frame_picture('palace', size).load()
        for depth in woven:
            band = PALACE.bands[depth]
            self.assertEqual(len(band), 51)
            row = [menu_theme._rgb(colour) + (255,) for colour in band]
            for x in range(depth, width - depth):
                self.assertEqual(picture[x, depth], row[x % 51])
                self.assertEqual(picture[x, height - 1 - depth], row[x % 51])
            for y in range(depth + 1, height - 1 - depth):
                self.assertEqual(picture[depth, y], row[y % 51])
                self.assertEqual(picture[width - 1 - depth, y], row[y % 51])

    def test_spider_coat_stands_out_of_the_band_and_never_into_the_panel(self):
        size = (200, 150)
        picture = menu_theme._frame_picture('spider', size)
        pixels = picture.load()
        width, height = size
        zone = menu_theme._THICKNESS['spider'][0]
        outside = zone - len(menu_theme._SPIDER_VELVET)
        panel = menu_theme._rgb(SPIDER.colour('panel')) + (255,)
        hairs = bare = 0
        for y in range(height):
            for x in range(width):
                depth = min(x, y, width - 1 - x, height - 1 - y)
                alpha = pixels[x, y][3]
                if depth >= zone:
                    self.assertEqual(pixels[x, y], panel)           # the panel stays plain under its text
                elif depth >= outside:
                    self.assertEqual(alpha, 255)                    # the band is whole
                elif alpha:
                    hairs += 1
                else:
                    bare += 1
                if alpha:
                    self.assertGreater(sum(pixels[x, y][:3]), 0)    # browns, never black
        # Hairs reach out of the band, but leave gaps: a coat, not a solid rim.
        self.assertGreater(hairs, 0.25 * (hairs + bare))
        self.assertGreater(bare, 0.25 * (hairs + bare))
        self.assertEqual(menu_theme._spider_frame(SPIDER, size, panel[:3]).tobytes(), picture.tobytes())

    def test_spider_fur_covers_the_panel_and_darkens_only_its_backgrounds(self):
        menu_theme.use(SPIDER)
        self.addCleanup(menu_theme.use, None)
        panel, row, text = (menu_theme._rgb(SPIDER.colour(role)) + (255,) for role in ('panel', 'row', 'text'))
        image = Image.new('RGBA', (512, 384), panel)
        image.paste(row, (80, 150, 440, 170))
        image.paste(text, (200, 155, 300, 165))
        rect = (64, 7, 448, 357)
        menu_theme.watermark(image, rect)
        colours = {colour for _count, colour in image.getcolors()}
        self.assertEqual(len(colours), 5)                       # two backgrounds, each also darkened, and the text
        self.assertIn(text, colours)
        for colour in colours - {panel, row, text}:
            self.assertLess(sum(colour[:3]), sum(row[:3]))
        # The fur is over the whole panel (unlike the ruins' one sign), and
        # only the panel: the first time, everywhere in it; never outside it.
        pixels = image.load()
        for left, top in ((64, 7), (256, 7), (64, 182), (256, 182)):
            self.assertTrue(any(pixels[x, y] not in (panel, row, text)
                                for x in range(left, left + 192) for y in range(top, top + 175)))
        self.assertTrue(all(pixels[x, y] == panel for x in range(0, 64) for y in range(0, 384)))
        once = image.tobytes()
        menu_theme.watermark(image, rect)
        self.assertEqual(image.tobytes(), once)                 # drawing it again changes nothing

    def test_spider_lobes_looked_for_near_their_centres_are_the_whole_field(self):
        # Every lobe against every pixel, as the lobes were first drawn.
        def everywhere(width, height, cell):
            rng = numpy.random.default_rng(0x7A2C)
            count = int(width * height / (cell * cell)) + 1
            points = numpy.column_stack((rng.uniform(-cell, width + cell, count),
                                         rng.uniform(-cell, height + cell, count)))
            stretch = rng.uniform(0.7, 1.35, count)
            y, x = numpy.mgrid[0:height, 0:width].astype(float)
            wx = x + 2.5 * numpy.sin(y / 9.0 + 0.7) + 1.8 * numpy.sin((x + y) / 13.0)
            wy = y + 2.5 * numpy.sin(x / 10.0 + 1.9) + 1.8 * numpy.sin((x - y) / 15.0)
            first = numpy.full((height, width), numpy.inf)
            second = numpy.full((height, width), numpy.inf)
            near_x = numpy.zeros((height, width))
            near_y = numpy.zeros((height, width))
            for (px, py), squash in zip(points, stretch):
                dx, dy = (wx - px) * squash, (wy - py) / squash
                distance = numpy.hypot(dx, dy)
                closer = distance < first
                second = numpy.where(closer, first, numpy.minimum(second, distance))
                near_x = numpy.where(closer, dx, near_x)
                near_y = numpy.where(closer, dy, near_y)
                first = numpy.where(closer, distance, first)
            radius = numpy.maximum(1.0, (first + second) / 2)
            away = numpy.clip((near_x + near_y) / (1.41 * radius), 0, 1)
            crevice = numpy.clip(1 - (second - first) / 4.0, 0, 1)
            return numpy.clip(0.65 * away ** 1.6 + 0.8 * crevice ** 1.5, 0, 1), rng.random(20)

        width, height = 230, 170            # wider than a lobe's reach, so the windows matter
        y, x = numpy.mgrid[0:height, 0:width]
        band = numpy.minimum(numpy.minimum(x, y), numpy.minimum(width - 1 - x, height - 1 - y)) < 18
        for cell in (9.0, 15.0):
            whole, after = everywhere(width, height, cell)
            # The usual reach, and one so short that most pixels miss their
            # nearest lobes and are compared with every lobe instead.
            for reach in (2.5, 0.5):
                shade, rng = menu_theme._spider_shade(width, height, cell, reach=reach)
                self.assertTrue(numpy.array_equal(shade, whole))
                self.assertTrue(numpy.array_equal(rng.random(20), after))   # the specks' sequence is unchanged
                # A frame's band: only the strip near the edges is wanted, and it is the same.
                shade = menu_theme._spider_shade(width, height, cell, 18, reach)[0]
                self.assertTrue(numpy.array_equal(shade[band], whole[band]))

    def test_new_frames_take_no_more_of_a_panel_than_the_first_ones(self):
        # Every page's content was laid out to clear the first five frames'
        # bands; a later frame's band may reach no deeper into any panel.
        from pop2.controls_page import ControlsPage
        from pop2.game_ui import DevelopmentMenu
        from pop2.screenshot_gallery import ScreenshotGallery

        game = [(GameMenu.PANEL, True), (GameMenu.OPTIONS_PANEL, False), (GameMenu.DIALOG, False),
                (GameMenu.ABOUT_DIALOG, False), (GameMenu.HALL_PANEL, False), (GameMenu.SCREENSHOT_PANEL, False),
                (ControlsPage.PANEL, True), (DevelopmentMenu.PANEL, False)]
        # The classic saves page and its dialog, the screenshots page and its folder dialog.
        window = [(28, 16, 484, 368), (80, 121, 432, 270), ScreenshotGallery.PANEL, (48, 44, 464, 338)]
        places = [(rect, sides, menu_theme._LIMIT) for rect, sides in game]
        places += [(rect, True, menu_theme._SCREEN) for rect in window]

        def depths(theme, rect, sides, limit):
            """How far the band's inner edge lies inside the panel, on each side."""
            whole = menu_theme._frame_place(rect, theme, sides, limit)[0]
            across, top, bottom = ((theme.frame_width,) * 3 if theme.frame == 'bands'
                                   else menu_theme._THICKNESS[theme.frame])
            return (whole[0] + across - rect[0], whole[1] + top - rect[1],
                    rect[2] - (whole[2] - across), rect[3] - (whole[3] - bottom))

        first = (PALACE, DESERT, CAVERNS, RUINS, TEMPLE)
        for rect, sides, limit in places:
            deepest = [max(side) for side in zip(*(depths(theme, rect, sides, limit) for theme in first))]
            for theme in (CHESS, SPIDER):
                with self.subTest(theme=theme.name, rect=rect):
                    allowed = list(deepest)
                    if theme is CHESS and menu_theme.frame_rect(rect, theme, sides, limit)[3] == limit[3]:
                        # The board's front face makes the chess foot a row deeper than
                        # the temple's; where the playfield's foot stops it (Controls),
                        # it stays one row deeper. That page's keys are well clear.
                        allowed[3] += 1
                    for depth, most in zip(depths(theme, rect, sides, limit), allowed):
                        self.assertLessEqual(depth, most)

    def test_spider_hairs_are_cut_at_the_playfield_edge_and_the_band_keeps_its_place(self):
        # Controls fills the playfield: the frame would cross its top and the health strip.
        rect = (21, 7, 491, 357)
        whole, shown = menu_theme._frame_place(rect, SPIDER, True, menu_theme._LIMIT)
        self.assertEqual(shown, menu_theme.frame_rect(rect, SPIDER, True))
        self.assertLess(whole[1], shown[1])
        self.assertGreater(whole[3], shown[3])
        menu_theme.use(SPIDER)
        self.addCleanup(menu_theme.use, None)
        sentinel = (1, 2, 3, 255)
        image = Image.new('RGBA', (512, 384), sentinel)
        menu_theme.panel(image, rect, clear_sides=True)
        pixels = image.load()
        self.assertTrue(all(pixels[x, y] == sentinel for x in range(512) for y in range(365, 384)))
        full = menu_theme._frame_picture('spider', (whole[2] - whole[0] + 1, whole[3] - whole[1] + 1)).load()
        for x in (100, 256, 400):
            for y in range(shown[1], shown[3] + 1):
                colour = full[x - whole[0], y - whole[1]]
                self.assertEqual(pixels[x, y], colour if colour[3] else sentinel)
        # Other frames are drawn smaller instead: none of their pixels is loose.
        self.assertEqual(*menu_theme._frame_place(rect, CAVERNS, True, menu_theme._LIMIT))

    def test_sign_caches_keep_only_recent_window_sizes(self):
        menu_theme.use(RUINS)
        self.addCleanup(menu_theme.use, None)
        image = Image.new('RGBA', (1200, 900), menu_theme._rgb(RUINS.colour('panel')) + (255,))
        for step in range(40):
            scale = 1.5 + step / 40
            menu_theme.watermark(image, (64, 36, 448, 328), lambda x, y, s=scale: (round(x * s), round(y * s)))
        self.assertLessEqual(len(menu_theme._marks), 25)
        self.assertLessEqual(len(menu_theme._spots), 25)

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
