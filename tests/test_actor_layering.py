import unittest
from types import SimpleNamespace

from pop2.combat_art import actor_draw_order
from pop2.sequence_runtime import SequenceState


class ActorLayeringTests(unittest.TestCase):
    def key(self, x=100, bottom=346, row=2, facing=0, mode=0, action=15):
        state = SequenceState(2, target_x=x, facing=facing, animation_state=mode, action=action)
        record = SimpleNamespace(offset_x=4, aux=70)
        return actor_draw_order(state, record, (x - 4, bottom - 78, x + 13, bottom), row)

    def test_cells_are_painted_bottom_up_then_left_to_right(self):
        self.assertLess(self.key(row=2), self.key(row=1))
        self.assertLess(self.key(x=70), self.key(x=130))

    def test_same_cell_uses_shape_bottom_then_draw_anchor(self):
        self.assertLess(self.key(bottom=346), self.key(bottom=356))
        self.assertLess(self.key(x=95), self.key(x=100))
        self.assertLess(self.key(facing=0), self.key(facing=1))

    def test_airborne_index_uses_drawn_bottom_and_climb_offsets_the_column(self):
        self.assertGreaterEqual(self.key(bottom=226, mode=1)[0], 11)
        self.assertEqual(self.key(bottom=4, mode=1)[0], 0)
        self.assertEqual(self.key(mode=2)[0], self.key()[0] + 1)
        self.assertEqual(self.key(mode=2, facing=1)[0], self.key(facing=1)[0] - 1)

    def test_offscreen_actors_share_the_first_bucket(self):
        self.assertEqual(self.key(x=0)[0], 0)
        self.assertEqual(self.key(x=560)[0], 0)
        self.assertEqual(self.key(row=3)[0], 0)
        self.assertLess(self.key(x=0), self.key(x=100))


if __name__ == '__main__':
    unittest.main()
