"""AnimChar's terminal pose is resource data, not a cached action value."""

from dataclasses import asdict
import unittest

from pop2.paths import ASSET_DIR
from pop2.sequence_runtime import SequenceRuntime, SequenceState


class SequenceHoldTests(unittest.TestCase):
    def test_hold_restores_the_resource_pose_instead_of_a_stale_action(self):
        for actor in (0, 2, 4):
            for stale in (0, 15, 206, 999):
                state = SequenceState(1, cursor=2, action=stale, actor_type=actor)
                frame = SequenceRuntime({1: (150, 171, -23)}, state).next_frame()
                self.assertEqual((frame.action, state.action, state.cursor), (171, 171, 2))

    def test_hold_uses_entry_cursor_before_intervening_operations(self):
        state = SequenceState(1, cursor=1, action=999, animation_state=1)
        frame = SequenceRuntime({1: (150, -7, 3, -23)}, state).next_frame()
        self.assertEqual((frame.action, state.animation_state, state.cursor), (150, 3, 1))

    def test_hold_preserves_selected_sequence_across_a_resource_continuation(self):
        state = SequenceState(12, selected_sequence_id=99, cursor=2, action=0)
        SequenceRuntime({12: (106, 106, -23)}, state).next_frame()
        self.assertEqual((state.sequence_id, state.source_sequence_id, state.action, state.cursor),
                         (12, 99, 106, 2))

    def test_repeated_hold_does_not_replay_earlier_offsets_or_callbacks(self):
        state = SequenceState(1, actor_type=0, facing=1)
        runtime = SequenceRuntime({1: (-5, 10, -15, 30, 171, -23)}, state)
        runtime.next_frame()
        before = asdict(state)
        for _ in range(20):
            runtime.next_frame()
            self.assertEqual(asdict(state), before)

    def test_hold_does_not_move_or_turn_the_actor(self):
        for facing in (0, 1):
            state = SequenceState(1, cursor=1, facing=facing, current_x=10, target_x=20,
                                  current_y=-30, horizontal_velocity=2, vertical_velocity=33)
            SequenceRuntime({1: (106, -23)}, state).next_frame()
            self.assertEqual((state.current_x, state.target_x, state.current_y, state.facing,
                              state.horizontal_velocity, state.vertical_velocity),
                             (10, 20, -30, facing, 2, 33))

    def test_peeking_a_held_pose_does_not_mutate_the_source_state(self):
        state = SequenceState(1, cursor=1, action=0)
        before = asdict(state)
        frame = SequenceRuntime({1: (206, -23)}, state).peek_frame()
        self.assertEqual(frame.action, 206)
        self.assertEqual(asdict(state), before)

    def test_hold_without_any_pose_is_bounded_instead_of_yielding_a_fake_frame(self):
        runtime = SequenceRuntime({1: (-23,)}, SequenceState(1), max_operations_per_frame=8)
        with self.assertRaisesRegex(RuntimeError, 'did not yield'):
            runtime.next_frame()


@unittest.skipUnless((ASSET_DIR / 'enemy_profiles.json').is_file(), 'Imported game resources required')
class HeldSkeletonReloadTests(unittest.TestCase):
    def test_reloaded_held_combat_pose_is_visible_and_retains_life(self):
        from tests.test_skeletons import SkeletonTests
        from pop2.skeleton import SkeletonRoomRecord

        SkeletonTests.setUpClass()
        _, _combat, actor = SkeletonTests().encounter(14)
        actor.skeleton.timer = 99
        actor.skeleton.room_record = SkeletonRoomRecord(227, 10, 2, True, 27)
        actor.skeleton.restore_room(actor, 0)
        self.assertEqual(actor.state.action, 171)
        self.assertTrue(actor.skeleton.native_alive)
        self.assertEqual(actor.life, 2)
        self.assertEqual(actor.skeleton.timer, 99)


if __name__ == '__main__':
    unittest.main()
