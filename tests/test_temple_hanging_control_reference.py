import unittest

from tools.probe_temple_gate_actor_clip import clip_reference, put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_hanging_control import HangingInputs, hanging_reference
from tools.probe_temple_slide_rock_update import actor_word


CLIPS = {2: (-7, 0, 15), 9: (-7, 2, 91, -1, 210), 210: (90, 89, 88),
         47: (-7, 5, -5, -16, 50), 10: (-7, 1, 135), 11: (81,),
         23: (-7, 3, 81), 25: (-7, 6, 92), 73: (135,), 99: (-7, 3, 81)}


class TempleHangingControlTests(unittest.TestCase):
    def actor(self, *, facing=-1, mode=2, sequence=9, cursor=3, pose=91, release_word=0):
        result = bytearray(actor_fixture(3, 1, 2, facing, mode))
        for field, value in ((4, 400), (10, pose), (24, -1), (26, 0), (36, cursor),
                              (38, sequence), (40, sequence), (52, release_word)):
            put_actor(result, field, value)
        return bytes(result)

    def control(self, inputs=None, actor=None):
        inputs = HangingInputs() if inputs is None else inputs
        if actor is None:
            actor = self.actor(release_word=inputs.release_word)
        return hanging_reference(actor, CLIPS, inputs, (2, -3, inputs.up, 4, inputs.held))

    def test_solid_above_preserves_hang_but_space_above_releases(self):
        held = self.control()
        self.assertEqual(held['actor'], self.actor())
        self.assertEqual(held['latches'], (2, -3, 0, 4, 1))
        released = self.control(HangingInputs(above=0))
        self.assertIn(('release',), released['events'])
        self.assertEqual(actor_word(released['actor'], 40), 11)

    def test_ordinary_hold_does_not_erase_gate_selected47(self):
        actor = self.actor(sequence=47, cursor=0)
        result = self.control(actor=actor)
        self.assertEqual(result['actor'], actor)
        self.assertNotIn(('animate', 47, 0), result['events'])

    def test_release_word11_is_cleared_but_climb_has_priority(self):
        release = self.control(HangingInputs(release_word=11))
        self.assertEqual(actor_word(release['actor'], 52), 0)
        self.assertIn(('release',), release['events'])
        climb = self.control(HangingInputs(held=0, up=1, release_word=11))
        self.assertEqual(actor_word(climb['actor'], 52), 11)
        self.assertNotIn(('release',), climb['events'])
        self.assertEqual(actor_word(climb['actor'], 40), 10)

    def test_clear_controls_leaves_held_untouched_and_sets_down_on_release(self):
        result = self.control(HangingInputs(held=-1, release_word=11))
        self.assertEqual(result['latches'], (0, 0, 0, 1, -1))
        self.assertEqual(result['events'].count(('clear_controls',)), 1)

    def test_climb_sets_held_and_up_and_ignores_cooldown_only_when_zero(self):
        result = self.control(HangingInputs(up=-1))
        self.assertEqual(result['latches'], (0, 0, 1, 0, 1))
        delayed = self.control(HangingInputs(up=1, cooldown=1))
        self.assertNotIn(('climb',), delayed['events'])
        self.assertEqual(delayed['actor'], self.actor())

    def test_gate_climb_threshold_uses_low_byte_and_facing(self):
        for foreground, facing, expected in ((47, -1, 73), (48, -1, 10),
                                               (0xff2f, -1, 73), (47, 0, 10)):
            with self.subTest(foreground=foreground, facing=facing):
                result = self.control(HangingInputs(up=1, above=4, foreground=foreground),
                                      self.actor(facing=facing))
                self.assertEqual(actor_word(result['actor'], 40), expected)
                self.assertEqual(('bars', 0) in result['events'], expected == 10)

    def test_bars_query_can_select73_when_gate_shortcut_does_not(self):
        result = self.control(HangingInputs(up=1, bars=1))
        self.assertIn(('bars', 0), result['events'])
        self.assertEqual(actor_word(result['actor'], 40), 73)

    def test_wall_hold_selects25_except_mode6_but_gate_left_still_does(self):
        for mode, current, expected in ((2, 20, 25), (6, 20, 9), (6, 4, 25)):
            with self.subTest(mode=mode, current=current):
                result = self.control(HangingInputs(current=current), self.actor(mode=mode))
                self.assertEqual(actor_word(result['actor'], 40), expected)

    def test_both_space_preview_keeps_gate_x_mode_pose_side_effects(self):
        actor = self.actor(sequence=47, cursor=0)
        result = self.control(HangingInputs(held=0, current=0, front=9), actor)
        self.assertEqual(tuple(actor_word(result['actor'], i) for i in (4, 10, 16, 36, 38, 40)),
                         (416, 50, 5, 0, 99, 99))
        self.assertIn(('animate', 47, 0), result['events'])
        after = clip_reference(result['actor'], CLIPS)['actor']
        self.assertEqual(tuple(actor_word(after, i) for i in (4, 10, 16)), (416, 81, 3))

    def test_preview_greater_pose_selects23_instead_of99(self):
        actor = self.actor(sequence=210, cursor=1, pose=87)
        result = self.control(HangingInputs(held=0, current=0, front=0), actor)
        self.assertEqual(actor_word(result['actor'], 10), 89)
        self.assertEqual(actor_word(result['actor'], 40), 23)

    def test_release_floor_and_wall_offsets_follow_facing(self):
        for current, front, delta, sequence in ((20, 1, -23, 11), (0, 1, -12, 11),
                                                (1, 0, 10, 11), (1, 1, 0, 11), (11, 11, 0, 23)):
            for facing in (-1, 0):
                with self.subTest(current=current, front=front, facing=facing):
                    result = self.control(HangingInputs(held=0, current=current, front=front),
                                          self.actor(facing=facing))
                    self.assertEqual(actor_word(result['actor'], 4), 400 + (delta if facing == 0 else -delta))
                    self.assertEqual(actor_word(result['actor'], 40), sequence)

    def test_impassable_floor_against_wall_promotes_the_other_side(self):
        first = self.control(HangingInputs(held=0, current=20, front=11))
        self.assertEqual((actor_word(first['actor'], 4), actor_word(first['actor'], 40)), (423, 11))
        second = self.control(HangingInputs(held=0, current=11, front=20))
        self.assertEqual((actor_word(second['actor'], 4), actor_word(second['actor'], 40)), (390, 11))

    def test_selected73_first_pose_does_not_force_a_new_mode(self):
        result = self.control(HangingInputs(up=1, bars=1))
        after = clip_reference(result['actor'], CLIPS)['actor']
        self.assertEqual((actor_word(after, 16), actor_word(after, 10)), (2, 135))

    def test_outside_bounded_route_is_rejected(self):
        with self.assertRaises(ValueError):
            self.control(actor=self.actor(mode=5))
        actor = bytearray(self.actor())
        put_actor(actor, 26, 1)
        with self.assertRaises(ValueError):
            self.control(actor=actor)
        with self.assertRaises(ValueError):
            hanging_reference(self.actor(), CLIPS, HangingInputs(), (0, 0, 1, 0, 1))


if __name__ == '__main__':
    unittest.main()
