import unittest
import struct
from types import SimpleNamespace

from pop2.cavern_state import CavernState
from pop2.scythes import Scythes
from pop2.sequence_runtime import SequenceState
from pop2.terrain import LevelMap


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


class ScytheContactTests(unittest.TestCase):
    def test_guard_inset_shortens_the_right_edge_not_the_height(self):
        level = bytearray(0x2200)
        struct.pack_into('>2H', level, 25 * 2, 12, 13)
        terrain = LevelMap(level)
        trap = Scythes(foreground={(0, 25): 2, (0, 26): 2})
        terrain.caverns = CavernState(scythes=trap)
        state = SequenceState(2, target_x=300, facing=1, actor_type=2)
        motion = SimpleNamespace(room=0, row=2)
        record = SimpleNamespace(offset_x=0, aux=0)
        # Native phase2 blade: (top293,left292,bottom307,right397).
        # Guard CheckScytheHit5:5910 moves RIGHT to387; bottom stays307.
        self.assertFalse(trap.cut(terrain, motion, state, (390, 295, 395, 300), record))
        self.assertTrue(trap.cut(terrain, motion, state, (300, 300, 310, 305), record))


if __name__ == '__main__':
    unittest.main()
