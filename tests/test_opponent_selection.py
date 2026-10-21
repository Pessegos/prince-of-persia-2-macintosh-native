"""Selection boundaries without imported resources or enemy profiles."""

from types import SimpleNamespace
import unittest

from pop2.opponent_selection import nearest_opponent


def actor(x=200, y=0, row=1, room=0, life=3, native_alive=None, kind=2):
    return SimpleNamespace(
        state=SimpleNamespace(target_x=x, current_y=y, actor_type=kind),
        row=row, room=room, alive=life > 0, native_alive=native_alive, skeleton=None)


class OpponentSelectionTests(unittest.TestCase):
    def test_explicit_native_alive_is_independent_of_hit_points(self):
        player = actor()
        for life in (0, 1, 3):
            for living in (False, True):
                guard = actor(life=life, native_alive=living)
                self.assertIs(nearest_opponent(player, [guard]), guard if living else None)

    def test_older_records_without_native_flag_use_hit_points(self):
        self.assertIsNone(nearest_opponent(actor(), [actor(life=0)]))
        guard = actor()
        self.assertIs(nearest_opponent(actor(), [guard]), guard)

    def test_skeleton_resume_flag_can_precede_hit_points(self):
        guard = actor(life=0, kind=4)
        guard.skeleton = SimpleNamespace(native_alive=True)
        self.assertIs(nearest_opponent(actor(), [guard]), guard)
        guard.skeleton.native_alive = False
        self.assertIsNone(nearest_opponent(actor(), [guard]))

    def test_equal_x_is_left_not_right(self):
        guard = actor()
        self.assertIs(nearest_opponent(actor(), [guard], -1), guard)
        self.assertIsNone(nearest_opponent(actor(), [guard], 1))

    def test_exact_vertical_threshold_retains_bank_order(self):
        near, far = actor(201, y=80), actor(300)
        self.assertIs(nearest_opponent(actor(), [near, far]), near)
        self.assertIs(nearest_opponent(actor(), [far, near]), far)
        near.state.current_y = 81
        self.assertIs(nearest_opponent(actor(), [near, far]), far)
        near.state.current_y = 79
        self.assertIs(nearest_opponent(actor(), [far, near]), near)

    def test_absolute_y_compares_across_rows(self):
        near, far = actor(201, row=0), actor(300)
        self.assertIs(nearest_opponent(actor(), [near, far]), far)

    def test_type_eleven_is_only_a_fallback_and_preserves_first_fallback(self):
        first, second, ordinary = actor(300, kind=11), actor(201, kind=11), actor(400)
        self.assertIs(nearest_opponent(actor(), [first, second]), first)
        self.assertIs(nearest_opponent(actor(), [first, ordinary, second]), ordinary)
        self.assertIs(nearest_opponent(actor(), [ordinary, first]), ordinary)

    def test_unrebased_room_is_not_a_candidate(self):
        self.assertIsNone(nearest_opponent(actor(), [actor(room=1)]))


if __name__ == '__main__':
    unittest.main()
