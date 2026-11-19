import sys
import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy
from PIL import Image, ImageTk

from pop2 import tk_photo
from pop2.tk_photo import put_pixels
from pop2.window_controls import put_patch


class PhotoWriteTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        ground = Image.effect_noise((300, 200), 60).convert('RGB')
        self.photo = ImageTk.PhotoImage(ground, master=self.root)
        # Shown, as the window's photo is: Tk then prepares each written part for the display.
        canvas = tk.Canvas(self.root, width=300, height=200)
        canvas.create_image(0, 0, image=self.photo, anchor='nw')
        self.expected = ground.copy()

    def shown(self):
        return ImageTk.getimage(self.photo)

    def patches(self):
        rng = numpy.random.default_rng(5)
        pixels = rng.integers(0, 256, (37, 91, 4), dtype=numpy.uint8)   # alpha of every value
        opaque = Image.fromarray(pixels).convert('RGB')
        yield 'RGBA array', pixels, opaque
        yield 'RGB array', pixels[..., :3].copy(), opaque
        yield 'RGBA picture', Image.fromarray(pixels), opaque
        yield 'RGB picture', opaque, opaque
        # Rows wider than the part, as a column slice of a larger array has, and rows upside down.
        wide = rng.integers(0, 256, (12, 140, 4), dtype=numpy.uint8)
        yield 'RGBA slice', wide[:, 30:110], Image.fromarray(wide[:, 30:110].copy()).convert('RGB')
        yield 'flipped', wide[::-1, ::2], Image.fromarray(wide[::-1, ::2].copy()).convert('RGB')

    def test_a_part_is_written_opaque_by_tk_s_own_function_as_its_data_would_be(self):
        # Given as data, Tk 8.6 read an option of a menu at 3440x1440 in about 1.8 ms; copied
        # from another photo, any part made Tk look over the alpha of the whole window's photo.
        for index, (name, pixels, picture) in enumerate(self.patches()):
            with self.subTest(name):
                x, y = 7 + 41 * index, 3 + 29 * index
                written = put_pixels(self.photo, pixels, x, y)
                if sys.platform == 'win32':
                    self.assertTrue(written, "Tk's own function is reachable in the Tk Python ships")
                elif not written:
                    self.skipTest("Tk's own function is not reachable here")
                self.expected.paste(picture, (x, y))
                shown = self.shown()
                self.assertEqual(shown.convert('RGB').tobytes(), self.expected.tobytes())
                self.assertEqual(shown.getextrema()[3], (255, 255), 'every pixel opaque')

    def test_the_window_s_patches_use_neither_tk_s_data_nor_its_copy_when_its_function_is_there(self):
        if not put_pixels(self.photo, numpy.zeros((1, 1, 3), numpy.uint8), 0, 0):
            self.skipTest("Tk's own function is not reachable here")
        photo, commands = self.photo, []

        class Watched:
            """The window's photo, its Tk commands noted."""
            tk = property(lambda self: self)

            def interpaddr(self):
                return photo.tk.interpaddr()

            def call(self, *command):
                commands.append(command)
                return photo.tk.call(*command)

            def width(self):
                return photo.width()

            def height(self):
                return photo.height()

            def __str__(self):
                return str(photo)

        for _name, pixels, _picture in self.patches():
            put_patch(Watched(), pixels, 20, 30)
        put_patch(Watched(), Image.effect_noise((200, 150), 40).convert('RGBA'), 0, 0)
        self.assertEqual(commands, [])

    def test_without_tk_s_function_a_part_goes_as_data_or_from_another_photo(self):
        with patch.dict(tk_photo._writers, {self.photo.tk.interpaddr(): None}):
            self.assertFalse(put_pixels(self.photo, numpy.zeros((2, 2, 4), numpy.uint8), 0, 0))
            for index, (name, pixels, picture) in enumerate(self.patches()):
                with self.subTest(name):
                    x, y = 5 + 37 * index, 9 + 25 * index
                    put_patch(self.photo, pixels, x, y)
                    self.expected.paste(picture, (x, y))
                    self.assertEqual(self.shown().convert('RGB').tobytes(), self.expected.tobytes())
            # A part of a twentieth of the photo or more is copied from another photo.
            big = Image.effect_noise((120, 80), 40).convert('RGBA')
            put_patch(self.photo, big, 150, 100)
            self.expected.paste(big.convert('RGB'), (150, 100))
            self.assertEqual(self.shown().convert('RGB').tobytes(), self.expected.tobytes())

    def test_a_function_that_does_not_write_what_it_is_given_is_not_used(self):
        def find(_interp, _name):
            return 1

        def put(*_args):
            return 0   # writes nothing: the probe's pixels stay empty

        library = SimpleNamespace(Tk_FindPhoto=find, Tk_PhotoPutBlock=put)
        before, images = self.shown().tobytes(), set(self.root.image_names())
        with patch.dict(tk_photo._writers, clear=True), \
                patch.object(tk_photo, 'tk_library', return_value=library):
            self.assertFalse(put_pixels(self.photo, numpy.zeros((2, 2, 3), numpy.uint8), 0, 0))
            self.assertIsNone(tk_photo._writers[self.photo.tk.interpaddr()])
        self.assertEqual(self.shown().tobytes(), before)
        self.assertEqual(set(self.root.image_names()), images, 'its probe photo is gone')

    def test_only_rows_of_rgb_or_rgba_bytes_are_written(self):
        if not put_pixels(self.photo, numpy.zeros((1, 1, 3), numpy.uint8), 0, 0):
            self.skipTest("Tk's own function is not reachable here")
        for pixels in (numpy.zeros((2, 2), numpy.uint8), numpy.zeros((2, 2, 2), numpy.uint8),
                       numpy.zeros((2, 2, 4), numpy.uint16)):
            with self.subTest(shape=pixels.shape, dtype=pixels.dtype), self.assertRaises(ValueError):
                put_pixels(self.photo, pixels, 0, 0)


if __name__ == '__main__':
    unittest.main()
