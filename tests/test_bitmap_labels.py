from types import SimpleNamespace
import unittest

from PIL import Image, ImageDraw

from pop2.bitmap_labels import crisp, label_text


class BitmapLabelTests(unittest.TestCase):
    @staticmethod
    def font():
        def text(value, color):
            image = Image.new('RGBA', (max(1, len(value) * 10), 16))
            draw = ImageDraw.Draw(image)
            for index, char in enumerate(value):
                if ord(char) > 127:
                    raise AssertionError('Unsupported character reached native font')
                draw.rectangle((index * 10 + 1, 4, index * 10 + 7, 10), fill=color)
            return image
        return SimpleNamespace(height=16, ascent=11, glyphs=dict.fromkeys(range(128)), text=text)

    def test_ascii_pixels_stay_exactly_native(self):
        font = self.font()
        expected = font.text('Screenshots', '#eeeeee')
        actual = label_text(font, 'Screenshots', '#eeeeee')
        self.assertEqual(actual.size, expected.size)
        self.assertEqual(actual.tobytes(), expected.tobytes())

    def test_portuguese_accents_are_composed_without_question_mark_substitution(self):
        font = self.font()
        label = label_text(font, 'Grava\u00e7\u00f5es de Ecr\u00e3', '#eeeeee')
        self.assertEqual(label.width, len('Gravacoes de Ecra') * 10)
        self.assertEqual(label.tobytes(), label_text(font, 'Gravac\u0327o\u0303es de Ecra\u0303', '#eeeeee').tobytes())
        self.assertNotEqual(label.tobytes(), label_text(font, 'Gravacoes de Ecra', '#eeeeee').tobytes())
        for accented, plain in zip('\u00c0\u00c1\u00c2\u00c3\u00c4\u00c5\u00c7\u010c', 'AAAAAACC'):
            rendered = label_text(font, accented, '#eeeeee')
            self.assertEqual(rendered.width, 10)
            self.assertNotEqual(rendered.getbbox(), None)
            baseline = Image.new('RGBA', rendered.size)
            baseline.paste(font.text(plain, '#eeeeee'), (0, 3))
            self.assertNotEqual(rendered.tobytes(), baseline.tobytes())

    def test_other_unicode_characters_use_a_visible_fallback(self):
        font = self.font()
        rendered = label_text(font, '\u0416\u4e2d', '#eeeeee')
        self.assertIsNotNone(rendered.getbbox())
        self.assertGreater(rendered.width, 2)
        self.assertEqual(font.glyphs, dict.fromkeys(range(128)))


class CrispScaleTests(unittest.TestCase):
    def test_near_whole_window_pixels_snap_and_others_stay(self):
        self.assertEqual(crisp(0.7, 3) * 3, 2)            # small text in a 3x window: 2.1 -> 2
        self.assertEqual(crisp(1, 3), 1)
        self.assertEqual(crisp(0.7, 2), 0.7)              # 1.4 is not near a whole number
        self.assertEqual(crisp(0.61, 3, limit=0.61), 0.61)   # rounding up to 2 would not fit
        self.assertEqual(crisp(0.1, 3), 0.1)              # below one window pixel


class WindowPageTextTests(unittest.TestCase):
    """The pages drawn at the window's resolution, in a 3x window."""

    def setUp(self):
        from tests.test_terrain import RooftopSceneTests
        RooftopSceneTests.setUp(self)

    def test_labels_take_whole_window_pixels_per_font_pixel(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import Mock, patch

        from pop2.cutscene_gallery import CutsceneGallery
        from pop2.cutscenes import CHAPTERS, CutsceneCollection
        from pop2.save_slots import SaveBrowser, SaveSlot
        from pop2.screenshot_gallery import ScreenshotGallery

        resize, uneven = Image.Image.resize, []

        def watch(image, size, *args, **kwargs):
            # Labels are short; at 2.1 window pixels per font pixel their columns
            # came out two or three pixels wide. Text shrunk to fit stays as it is.
            factor = size[0] / image.width
            if image.height <= 40 and factor >= 1.85 and abs(factor - round(factor)) > 0.02:
                uneven.append((image.size, size))
            return resize(image, size, *args, **kwargs)

        font = self.scene.ui_font
        frame = Image.new('RGBA', (1530, 1152), (0, 0, 0, 255))
        slots = tuple(SaveSlot(Path(f'none-{i}'), f'A rather long saved game {i}', True, level=i + 1,
                               date=f'16/11/2026 10:3{i}') for i in range(5))
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        pages = {
            'saves': lambda: SaveBrowser(slots, 'load', selected=1),
            'screenshots': lambda: ScreenshotGallery(folder.name),
            'cutscenes': lambda: CutsceneGallery(CutsceneCollection(seen={c.key for c in CHAPTERS}),
                                                 Mock(return_value=Image.new('RGB', (510, 384), '#773311'))),
        }
        for name, page in pages.items():
            uneven.clear()
            with self.subTest(page=name), patch.object(Image.Image, 'resize', watch):
                page().draw(frame, font, visible=True)
                self.assertEqual(uneven, [])


if __name__ == '__main__':
    unittest.main()
