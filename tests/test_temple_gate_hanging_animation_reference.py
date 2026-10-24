import unittest

from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_gate_hanging_animation import hanging_animation_reference


class TempleGateHangingAnimationTests(unittest.TestCase):
    def run_gate(self, position=3, phase=1, room=3, facing=-1, available=True):
        actor = actor_fixture(room, 1, 2, facing, 2)
        working = bytes(range(62))
        return actor, working, hanging_animation_reference(position, phase, actor, working, 3, 2, available)

    def test_slow_close_selects_and_copies_sequence_before_hanging_cue_and_redraw(self):
        _actor, _working, result = self.run_gate()
        self.assertEqual((result['foreground'], result['phase']), (0, -1))
        self.assertEqual(result['events'], [('sound', 0x112), ('load_kid',), ('jump_seq', 47),
                                            ('resource', 47), ('save_kid',), ('audio', 29), ('redraw', 0, -1)])
        self.assertEqual(result['prince'], result['working'])

    def test_fast_close_requests_hanging_cue_before_relief_and_slam_without_sequence(self):
        actor, working, result = self.run_gate(60, 4)
        self.assertEqual(result['events'], [('audio', 29), ('relief_check',), ('sound', 0x113), ('redraw', 0, -1)])
        self.assertEqual((result['prince'], result['working']), (actor, working))
        self.assertEqual(result['relief_countdown'], 4321)

    def test_permanent_open_stops_but_cannot_admit_zero_position_hanging_selection(self):
        actor, _working, result = self.run_gate(180, 3)
        self.assertEqual((result['foreground'], result['phase']), (255, -1))
        self.assertEqual(result['events'], [('sound', 0x112), ('load_kid',)])
        self.assertEqual((result['prince'], result['working']), (actor, actor))

    def test_ordinary_open_limit_redraws_old_state_without_touching_actors(self):
        actor, working, result = self.run_gate(180, 2)
        self.assertEqual(result['foreground'], 237)
        self.assertEqual(result['events'], [('redraw', 180, 2), ('sound', 0x111)])
        self.assertEqual((result['prince'], result['working']), (actor, working))

    def test_local_stop_selection_can_admit_room0_while_hanging_cue_cannot(self):
        _actor, _working, result = self.run_gate(room=0)
        self.assertIn(('jump_seq', 47), result['events'])
        self.assertNotIn(('audio', 29), result['events'])

    def test_missing_sequence_retains_actor_but_does_not_suppress_independent_cue(self):
        actor, _working, result = self.run_gate(available=False)
        self.assertEqual(result['prince'], actor)
        self.assertIn(('resource', 47), result['events'])
        self.assertIn(('audio', 29), result['events'])

    def test_other_facing_rejects_sequence_but_not_separate_hanging_cue(self):
        actor, _working, result = self.run_gate(facing=0)
        self.assertNotIn(('jump_seq', 47), result['events'])
        self.assertIn(('audio', 29), result['events'])
        self.assertEqual(result['prince'], actor)


if __name__ == '__main__':
    unittest.main()
