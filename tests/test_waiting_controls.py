"""Runtime bank parity and scene behavior at the first migrated ready gates."""

from itertools import product
import unittest

class WaitingSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_animation_data import AnimationDataTests
        AnimationDataTests.setUpClass()
        cls.fixture = AnimationDataTests()

    def step(self, facing=1):
        scene = self.fixture.sword_scene()
        scene.sequence_state.facing = facing
        scene.shift_held = True
        direction = 1 if facing else -1
        scene.horizontal_key(None, direction, True)
        scene.horizontal_key(None, direction, False)
        return scene

    def test_up_and_down_stay_independent_and_priority_does_not_depend_on_arrival_order(self):
        for facing, up_first in product((0, 1), (False, True)):
            with self.subTest(facing=facing, up_first=up_first):
                scene = self.step(facing)
                for key in (('up', 'down') if up_first else ('down', 'up')):
                    if key == 'up':
                        scene.up_key(None)
                    else:
                        scene.set_key_state(key, True)
                    scene.set_key_state(key, False)
                self.assertEqual((scene.directional_input.up, scene.directional_input.down), (-1, -1))
                self.assertIsNone(scene.pending_action)
                for _ in range(12):
                    scene.advance_animation()
                self.assertEqual((scene.sequence_state.sequence_id, scene.action), (28, 67))
                self.assertIsNone(scene.directional_input)
                self.assertIsNone(scene.pending_action)

    def test_modifier_is_read_at_dispatch_instead_of_baked_into_the_queued_direction(self):
        for facing in (0, 1):
            scene = self.step(facing)
            direction = 1 if facing else -1
            scene.queue_grace_remaining_ms = 0
            scene.horizontal_key(None, direction, True)
            scene.horizontal_key(None, direction, False)
            scene.up_key(None)
            scene.set_key_state('up', False)
            scene.set_key_state('shift', False)
            self.assertEqual((scene.directional_input.up, scene.directional_input.modifier), (-1, 0))
            for _ in range(12):
                scene.advance_animation()
            self.assertEqual((scene.sequence_state.sequence_id, scene.action), (3, 16))

    def test_internal_producers_merge_directions_instead_of_using_the_old_slot(self):
        from pop2.scene_prototype import BufferedCommand
        scene = self.step()
        scene.buffer_input(BufferedCommand('jump'))
        scene.buffer_input(BufferedCommand('crouch'))
        self.assertEqual((scene.directional_input.up, scene.directional_input.down), (-1, -1))
        self.assertIsNone(scene.pending_action)

    def test_focus_clear_drops_bank_and_legacy_request_together(self):
        scene = self.step()
        scene.up_key(None)
        scene.set_key_state('up', False)
        scene.clear_keys(None)
        self.assertIsNone(scene.directional_input)
        self.assertIsNone(scene.pending_action)
        for _ in range(20):
            scene.advance_animation()
        self.assertEqual(scene.action, 15)

    def test_running_turn_sequence_43_is_not_misclassified_as_a_cautious_step(self):
        scene = self.step()
        scene.start_sequence(43)
        self.assertIsNone(scene.directional_input)
        self.assertFalse(scene.waiting_controls_available())

    def test_a_direct_physics_sequence_change_cannot_replay_the_step_bank_after_landing(self):
        scene = self.step()
        scene.up_key(None)
        scene.set_key_state('up', False)
        # Physics selects through SequenceState rather than Scene.start_sequence.
        scene.sequence_state.select(23)
        scene.retire_waiting_controls()
        scene.sequence_state.select(2)
        self.assertIsNone(scene.directional_input)
        self.assertIsNone(scene.pending_action)
        self.assertFalse(scene.waiting_controls_available())

    def test_a_selected_step_loads_its_first_pose_before_another_ready_gate_runs(self):
        scene = self.fixture.sword_scene()
        scene.in_animation_tick = True
        scene.sequence_state.facing = 1
        scene.sequence_runtime.next_frame()
        scene.shift_held = True
        scene.horizontal_key(None, 1, True)
        self.assertEqual((scene.sequence_state.sequence_id, scene.sequence_state.cursor,
                          scene.sequence_state.action), (42, 0, 15))
        scene.set_key_state('shift', False)
        for _ in range(3):
            scene.update_waiting_controls()
        # JumpSeq changed selection/cursor but action still describes the old
        # idle pose. It cannot admit a run before AnimChar loads the step.
        self.assertEqual((scene.sequence_state.sequence_id, scene.sequence_state.cursor), (42, 0))
        scene.advance_animation()
        self.assertEqual(scene.action, 121)


if __name__ == '__main__':
    unittest.main()
