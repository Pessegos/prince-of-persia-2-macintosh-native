"""Vertical takeoff, protected landing and the boundary into native ledges."""

from itertools import product
import unittest

from tools.audit_vertical_handoff import host_trace


class VerticalSelectorTests(unittest.TestCase):
    def test_preparation_and_protected_landing_match_the_independent_router(self):
        from pop2.mac_input import DirectionalInput, vertical_input_request
        from tools.reference_input_bank import InputBank
        from tools.reference_input_routes import unarmed_route
        for axes, modifier, pose, mode in product(product((-1, 0, 1), repeat=4),
                                                  (-2, -1, 0, 1, 2), (67, 68, 69, 70, 83, 85), (1, 5)):
            bank = InputBank(*axes, modifier)
            expected, events = unarmed_route(bank, pose, mode=mode, sequence=28)
            actual, request = vertical_input_request(DirectionalInput(*bank.words()), pose, mode=mode)
            self.assertEqual(actual.words(), expected.words())
            self.assertEqual(request, events[0][0] if events else None)


class VerticalHandoffTests(unittest.TestCase):
    def test_real_platform_discards_early_taps_and_keeps_late_up_priority(self):
        for sequence, facing, late, order in product((14, 28), (0, 1), (False, True),
                                                    (('up', 'down'), ('down', 'up'))):
            with self.subTest(sequence=sequence, facing=facing, late=late, order=order):
                result = host_trace(sequence, facing, late, order)
                self.assertEqual(result['choice'], 'up' if late else 'none')
                self.assertTrue(all(step['pending'] is None for step in result['trace']))

    def test_inverted_late_taps_reach_the_same_ready_gate(self):
        for facing, order in product((0, 1), (('up', 'down'), ('down', 'up'))):
            with self.subTest(facing=facing, order=order):
                result = host_trace(28, facing, True, order, inverted=True)
                self.assertEqual(result['choice'], 'up')


class VerticalSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_animation_data import AnimationDataTests
        AnimationDataTests.setUpClass()
        cls.fixture = AnimationDataTests()

    def vertical_at(self, sequence, pose, facing=1):
        scene = self.fixture.sword_scene()
        scene.sequence_state.facing = facing
        scene.in_animation_tick = True
        scene.start_sequence(sequence)
        for _ in range(35):
            scene.advance_animation()
            if scene.action == pose:
                return scene
        self.fail(f'No vertical pose {pose}')

    def test_forward_during_preparation_converts_to_forward_jump_without_a_new_up(self):
        for sequence, facing, pose in product((14, 28), (0, 1), (67, 68, 69)):
            with self.subTest(sequence=sequence, facing=facing, pose=pose):
                scene = self.vertical_at(sequence, pose, facing)
                self.assertFalse(scene.up_held)
                scene.in_animation_tick = True
                scene.horizontal_key(None, 1 if facing else -1, True)
                self.assertEqual(scene.sequence_state.sequence_id, 3)
                self.assertIsNone(scene.pending_action)
                scene.advance_animation()
                self.assertEqual(scene.action, 16)

    def test_takeoff_consumes_up_and_clears_other_directions_without_consuming_modifier(self):
        from pop2.mac_input import DirectionalInput
        for sequence, modifier in product((14, 28), ('shift', 'ctrl')):
            with self.subTest(sequence=sequence, modifier=modifier):
                scene = self.fixture.sword_scene()
                setattr(scene, modifier + '_held', True)
                scene.directional_input = DirectionalInput(-1, -1, -1, -1,
                                                          -1 if modifier == 'shift' else -2)
                scene.start_sequence(sequence)
                self.assertEqual(scene.directional_input.words(),
                                 (0, 0, 1, 0, -1 if modifier == 'shift' else -2))
                self.assertIsNone(scene.pending_action)
                self.assertFalse(scene.update_waiting_controls())  # previous displayed pose15
                self.assertEqual(scene.sequence_state.cursor, 0)

    def test_forward_after_preparation_waits_and_is_cleared_by_landing(self):
        for facing in (0, 1):
            with self.subTest(facing=facing):
                scene = self.vertical_at(14, 70, facing)
                direction = 1 if facing else -1
                scene.horizontal_key(None, direction, True)
                scene.horizontal_key(None, direction, False)
                self.assertEqual(scene.sequence_state.sequence_id, 14)
                for _ in range(25):
                    scene.advance_animation()
                    if scene.sequence_state.sequence_id == 2:
                        break
                self.assertEqual((scene.sequence_state.sequence_id, scene.action), (2, 15))

    def test_landing_reset_preserves_the_modifier_and_cancels_released_auto_repeat(self):
        from pop2.mac_input import DirectionalInput
        for modifier in ('shift', 'ctrl'):
            with self.subTest(modifier=modifier):
                scene = self.vertical_at(14, 83)
                scene.set_key_state(modifier, True)
                scene.up_held = scene.jump_repeat_armed = True
                scene.directional_input = DirectionalInput(-1, -1, -1, -1,
                                                          -1 if modifier == 'shift' else -2)
                scene.update_airborne_controls()
                self.assertEqual(scene.directional_input.words(),
                                 (0, 0, 0, 0, -1 if modifier == 'shift' else -2))
                scene.set_key_state('up', False)
                scene.set_key_state(modifier, False)
                for _ in range(8):
                    scene.advance_animation()
                self.assertEqual((scene.sequence_state.sequence_id, scene.action), (2, 15))
                self.assertFalse(scene.sword_drawn)


class VerticalLedgeBoundaryTests(unittest.TestCase):
    def test_actual_cavern_ledge_entry_retires_the_bank_before_its_same_67_pose(self):
        from unittest.mock import patch
        from pop2.mac_input import DirectionalInput
        from tests.test_game_ui import GameWindowTests
        fixture = GameWindowTests()
        fixture.setUp()
        scene = fixture.scene
        try:
            with patch.object(scene, 'render'):
                for room, row, x, facing in ((25, 1, 445, 0), (0, 2, 90, 1)):
                    with self.subTest(facing=facing):
                        scene.load_level(3)
                        scene.peaceful = True
                        scene.jump_to_room(room, row, x, facing)
                        scene.in_animation_tick = True
                        scene.directional_input = DirectionalInput(-1, -1, -1, -1, -1)
                        self.assertTrue(scene.start_upper_ledge_jump())
                        self.assertEqual(scene.sequence_state.sequence_id, 24)
                        self.assertTrue(scene.native_ledge)
                        for _ in range(3):
                            fixture.tick()
                            self.assertEqual(scene.sequence_state.sequence_id, 24)
                            self.assertIsNone(scene.directional_input)
                        self.assertEqual(scene.action, 69)
        finally:
            fixture.doCleanups()


if __name__ == '__main__':
    unittest.main()
