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
                for _ in range(12):
                    scene.advance_animation()
                self.assertEqual((scene.sequence_state.sequence_id, scene.action), (28, 67))
                # Vertical takeoff now keeps ownership, consumes Up and
                # clears the losing Down without consuming Shift again.
                self.assertEqual(scene.directional_input.words(), (0, 0, 1, 0, 1))

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
        scene.latch_request(BufferedCommand('jump'))
        scene.latch_request(BufferedCommand('crouch'))
        self.assertEqual((scene.directional_input.up, scene.directional_input.down), (-1, -1))

    def test_focus_clear_drops_bank_and_legacy_request_together(self):
        scene = self.step()
        scene.up_key(None)
        scene.set_key_state('up', False)
        scene.clear_keys(None)
        self.assertIsNone(scene.directional_input)
        for _ in range(20):
            scene.advance_animation()
        self.assertEqual(scene.action, 15)

    def test_running_turn_sequence_43_is_not_misclassified_as_a_cautious_step(self):
        scene = self.step()
        scene.start_sequence(43)
        self.assertIsNotNone(scene.directional_input)
        self.assertEqual(scene.waiting_step_direction, 0)
        self.assertTrue(scene.waiting_controls_available())

    def test_a_direct_physics_sequence_change_cannot_replay_the_step_bank_after_landing(self):
        scene = self.step()
        scene.up_key(None)
        scene.set_key_state('up', False)
        # Physics selects through SequenceState rather than Scene.start_sequence.
        scene.sequence_state.select(23)
        scene.retire_waiting_controls()
        scene.sequence_state.select(2)
        self.assertIsNone(scene.directional_input)
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

    def brake(self, facing, pose):
        from pop2.control_mapping import RUN_STOP_SEQUENCE
        # A scripted run stop starts without a bank (SEQS 13: 53-56, 49, 50).
        scene = self.fixture.scene(sequence_id=RUN_STOP_SEQUENCE, facing=facing)
        scene.root, scene.next_animation_at = self.fixture.sword_scene().root, 0
        scene.animation_after_id, scene.render = None, lambda: None
        scene.advance_animation()
        while scene.action != pose:
            scene.advance_animation()
        return scene

    def test_brake_presses_are_bank_requests_with_native_priority(self):
        from pop2.control_mapping import CROUCH_STANDING_LOWER_SEQUENCE, STANDING_TURN_SEQUENCE
        for facing, pose, keys in product((0, 1), (55, 49), (
                ('backward',), ('down',), ('backward', 'down'), ('down', 'backward'))):
            with self.subTest(facing=facing, pose=pose, keys=keys):
                scene = self.brake(facing, pose)
                backward = -1 if facing else 1
                for key in keys:
                    if key == 'down':
                        scene.set_key_state('down', True)
                        scene.set_key_state('down', False)
                    else:
                        scene.horizontal_key(None, backward, True)
                        scene.horizontal_key(None, backward, False)
                    # The old host kept only the last tap in its slot.
                sequences = []
                for _ in range(12):
                    scene.advance_animation()
                    sequences.append(scene.sequence_state.sequence_id)
                # GenCtrl's standing gate prefers Backward to Down at 50, and
                # DoTurn clears the losing Down rather than crouching later.
                first = (STANDING_TURN_SEQUENCE if 'backward' in keys
                         else CROUCH_STANDING_LOWER_SEQUENCE)
                self.assertIn(first, sequences)
                if first == STANDING_TURN_SEQUENCE:
                    self.assertNotIn(CROUCH_STANDING_LOWER_SEQUENCE, sequences)
                    self.assertEqual(scene.sequence_state.facing, 1 - facing)

    def test_keys_held_into_a_scripted_brake_are_not_new_requests(self):
        from pop2.control_mapping import IDLE_SEQUENCE
        for facing in (0, 1):
            with self.subTest(facing=facing):
                scene = self.fixture.scene(sequence_id=13, facing=facing)
                scene.root, scene.next_animation_at = self.fixture.sword_scene().root, 0
                scene.animation_after_id, scene.render = None, lambda: None
                scene.held_directions = [-1 if facing else 1]
                scene.down_held = True
                scene.sample_keyboard()
                for _ in range(10):
                    scene.advance_animation()
                self.assertEqual((scene.sequence_state.sequence_id, scene.action),
                                 (IDLE_SEQUENCE, 15))


    def scripted_turn(self, facing, pose):
        from pop2.control_mapping import STANDING_TURN_SEQUENCE
        # Level entry, restart and the level-six cliff door start SEQS 5
        # (45-52) without a bank; 4:3e70/7:379a leave its latches at 0.
        scene = self.fixture.scene(sequence_id=STANDING_TURN_SEQUENCE, facing=facing)
        scene.root, scene.next_animation_at = self.fixture.sword_scene().root, 0
        scene.animation_after_id, scene.render = None, lambda: None
        scene.advance_animation()
        while scene.action != pose:
            scene.advance_animation()
        return scene

    def tap(self, scene, key):
        if key == 'down':
            scene.set_key_state('down', True)
            scene.set_key_state('down', False)
        else:
            facing = scene.sequence_state.facing
            direction = (1 if facing else -1) * (1 if key == 'forward' else -1)
            scene.horizontal_key(None, direction, True)
            scene.horizontal_key(None, direction, False)

    def test_scripted_turn_presses_are_bank_requests_with_native_priority(self):
        from pop2.control_mapping import CROUCH_STANDING_LOWER_SEQUENCE, STANDING_TURN_SEQUENCE
        for facing, keys in product((0, 1), (('backward', 'down'), ('down', 'backward'))):
            with self.subTest(facing=facing, keys=keys):
                scene = self.scripted_turn(facing, 46)
                facing_after = scene.sequence_state.facing
                for key in keys:
                    self.tap(scene, key)
                sequences = []
                for _ in range(10):
                    scene.advance_animation()
                    sequences.append(scene.sequence_state.source_sequence_id)
                # Backward wins at 50 and DoTurn clears the Down; the old slot
                # kept the last tap, so Backward then Down crouched.
                self.assertNotIn(CROUCH_STANDING_LOWER_SEQUENCE, sequences)
                self.assertIn(STANDING_TURN_SEQUENCE, sequences[4:])
                self.assertEqual(scene.sequence_state.facing, 1 - facing_after)

    def test_forward_tap_in_a_scripted_turn_runs_from_pose_48(self):
        # GenCtrl 6:062c/1014: a pending Forward at pose 48 is SEQS 43, even
        # when released; the old slot waited for 50 and started SEQS 1.
        for facing in (0, 1):
            with self.subTest(facing=facing):
                scene = self.scripted_turn(facing, 46)
                self.tap(scene, 'forward')
                trace = []
                for _ in range(4):
                    scene.advance_animation()
                    trace.append((scene.sequence_state.source_sequence_id, scene.action))
                self.assertIn((43, 1), trace)
                self.assertNotIn(1, [sequence for sequence, _ in trace])


if __name__ == '__main__':
    unittest.main()
