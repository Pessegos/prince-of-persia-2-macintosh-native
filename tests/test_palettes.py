import struct
import unittest

from pop2.render_opening import kid_palette_for_level


class PaletteTests(unittest.TestCase):
    def test_prince_palette_uses_environment_not_animation_shape_bank(self):
        resources = {"CTBL": {
            25000 + kind: {"data": struct.pack(">H4B", 1, kind, 17, 28, 5)}
            for kind in range(1, 7)
        }}
        for kind in range(1, 7):
            with self.subTest(kind=kind):
                self.assertEqual(kid_palette_for_level(resources, kind),
                                 {5: (kind, 17, 28, 255)})

    def test_non_environment_ids_do_not_silently_choose_the_generic_palette(self):
        for kind in (0, 7, 8, -1):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                kid_palette_for_level({}, kind)
