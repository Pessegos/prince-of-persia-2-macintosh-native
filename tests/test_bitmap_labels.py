from types import SimpleNamespace
import unittest

from PIL import Image, ImageDraw

from pop2.bitmap_labels import label_text


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


if __name__ == '__main__':
    unittest.main()
