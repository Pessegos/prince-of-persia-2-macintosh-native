"""Synthetic coordinate checks for the isolated neck-alignment reference."""

import unittest

from tools.probe_level7_neck_alignment import neck_alignment


class NeckAlignmentReferenceTests(unittest.TestCase):
    def test_opposite_facings_use_metadata_offset(self):
        self.assertEqual(neck_alignment((-10, 5), 20, 7, -1, 0, (100, 200)),
                         dict(screen_x=105, screen_y=190, native_x=312))
        self.assertEqual(neck_alignment((-10, 5), 20, 7, 0, -1, (100, 200)),
                         dict(screen_x=95, screen_y=190, native_x=302))

    def test_same_facings_include_sprite_width_and_type_seven_adjustment(self):
        self.assertEqual(neck_alignment((-10, 5), 20, 7, -1, -1, (100, 200)),
                         dict(screen_x=58, screen_y=190, native_x=265))
        self.assertEqual(neck_alignment((-10, 5), 20, 7, 0, 0, (100, 200)),
                         dict(screen_x=142, screen_y=190, native_x=349))

    def test_type_eight_has_distinct_same_and_opposite_facing_offsets(self):
        self.assertEqual(neck_alignment((-10, 5), 20, 8, -1, -1, (100, 200)),
                         dict(screen_x=60, screen_y=190, native_x=267))
        self.assertEqual(neck_alignment((-10, 5), 20, 8, -1, 0, (100, 200)),
                         dict(screen_x=115, screen_y=190, native_x=322))

    def test_vertical_metadata_is_not_changed_by_facing_or_width(self):
        for actor in (7, 8):
            for facing in (-1, 0):
                self.assertEqual(neck_alignment((7, 0), 13, actor, facing, 0,
                                                (100, 200))['screen_y'], 207)

    def test_width_only_affects_matching_facings(self):
        for width in (10, 20, 30):
            self.assertEqual(neck_alignment((0, 5), width, 7, -1, 0,
                                            (100, 200))['screen_x'], 105)

    def test_missing_drawn_prince_returns_no_new_alignment(self):
        self.assertIsNone(neck_alignment((0, 5), 20, 7, -1, 0, None))

    def test_untested_type_or_facing_is_rejected(self):
        for actor, own, prince in ((11, -1, 0), (7, 1, 0), (8, -1, 1)):
            with self.subTest(actor=actor, own=own, prince=prince), self.assertRaises(ValueError):
                neck_alignment((0, 0), 20, actor, own, prince, (100, 200))


if __name__ == '__main__':
    unittest.main()
