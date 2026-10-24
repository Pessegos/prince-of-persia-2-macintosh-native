import unittest


class ScytheDrawingPatchTests(unittest.TestCase):
    def test_a_patch_rebuilds_the_variant_from_the_base_list(self):
        from pop2.caverns import with_scythe
        from tools.extract_scythes import command_patch

        base = [['back', 1, 0, 0], ['back', 2, 0, 0], ['front', 3, 0, 0], ['front', 4, 0, 0]]
        variant = [['back', 1, 0, 0], ['back', 9, 0, 0], ['back', 2, 0, 0],
                   ['front', 3, 0, 0], ['front', 8, 0, 0], ['front', 7, 0, 0]]
        patch = command_patch(base, variant)
        self.assertEqual(with_scythe(base, patch), variant)
        # A loose-floor variant lacking an anchor still receives the blade.
        shifted = [command for command in base if command[1] != 3]
        self.assertIn(['front', 8, 0, 0], with_scythe(shifted, patch))

    def test_blade_rectangles_follow_the_hit_phases(self):
        from pop2.scythes import LOWER_BLADE, UPPER_BLADE, blade_rect

        self.assertEqual(blade_rect(2), (53, 37, 67, 142))
        self.assertEqual((blade_rect(16), blade_rect(17)), (UPPER_BLADE, LOWER_BLADE))
        self.assertEqual([phase for phase in range(20) if blade_rect(phase)], [2, 16, 17])


if __name__ == '__main__':
    unittest.main()
