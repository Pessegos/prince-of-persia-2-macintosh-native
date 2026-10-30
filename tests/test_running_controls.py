"""Grounded run routing and real-scene bank ownership at accepting gates."""

from itertools import product
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from pop2.mac_input import DirectionalInput, running_input_request
from tools.reference_input_bank import InputBank
from tools.reference_input_routes import unarmed_route


class RunningBankTests(unittest.TestCase):
    def test_production_run_selector_matches_the_independent_native_model(self):
        names = {('forward_jump',): 'forward_jump', ('sequence', 13): 'brake',
                 ('sequence', 6): 'reverse', ('run_jump', 4): 'running_jump',
                 ('sequence', 26): 'running_crouch'}
        banks = [InputBank(*axes, modifier) for axes in product((-1, 0, 1), repeat=4)
                 for modifier in (-2, -1, 0, 1, 2)]
        for bank, pose in product(banks, (*range(1, 15), *range(53, 66))):
            expected, events = unarmed_route(bank, pose)
            actual, request = running_input_request(DirectionalInput(*bank.words()), pose)
            self.assertEqual(actual.words(), expected.words(), (bank, pose))
            self.assertEqual(request, names[events[0]] if events else None, (bank, pose))
        for bank, (mode, sequence) in product(banks, ((4, 201), (5, 201), (9, 201), (0, 27), (0, 110))):
            actual, request = running_input_request(DirectionalInput(*bank.words()), 8,
                                                    mode=mode, sequence=sequence)
            self.assertEqual(actual.words(), bank.clear_directions().words())
            self.assertIsNone(request)


class RunningSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_animation_data import AnimationDataTests
        AnimationDataTests.setUpClass()
        cls.fixture = AnimationDataTests()

    def run_at(self, facing=1, pose=8):
        scene = self.fixture.sword_scene()
        scene.sequence_state.facing = facing
        scene.horizontal_key(None, 1 if facing else -1, True)
        for _ in range(25):
            if scene.sequence_state.action == pose:
                return scene
            scene.advance_animation()
        self.fail(f'Run did not reach {pose}')

    def test_rejected_geometry_keeps_up_until_an_actual_takeoff_accepts_it(self):
        for facing in (0, 1):
            with self.subTest(facing=facing):
                scene = self.run_at(facing)
                scene.room_id = 0
                scene.terrain_motion = SimpleNamespace(row=1, falling=False, sinking=False, dead=False)
                scene.level_map = SimpleNamespace(run_jump_offset=Mock(return_value=None))
                scene.in_animation_tick = True
                scene.up_key(None)
                self.assertFalse(scene.update_waiting_controls())
                self.assertLess(scene.directional_input.up, 0)
                scene.set_key_state('up', False)
                self.assertLess(scene.directional_input.up, 0)
                scene.level_map.run_jump_offset.return_value = 0
                self.assertTrue(scene.update_waiting_controls())
                self.assertEqual(scene.sequence_state.sequence_id, 4)
                self.assertEqual(scene.directional_input.words(), (0, 0, 1, 0, 0))

    def test_released_up_and_down_taps_do_not_replace_each_other_during_drift(self):
        for facing, up_first in product((0, 1), (False, True)):
            with self.subTest(facing=facing, up_first=up_first):
                scene = self.run_at(facing)
                direction = 1 if facing else -1
                scene.horizontal_key(None, direction, False)
                scene.horizontal_key(None, -direction, True)
                scene.advance_animation()
                self.assertEqual(scene.sequence_state.sequence_id, 6)
                for key in (('up', 'down') if up_first else ('down', 'up')):
                    scene.set_key_state(key, True)
                    scene.set_key_state(key, False)
                self.assertEqual((scene.directional_input.up, scene.directional_input.down), (-1, -1))
                for _ in range(30):
                    scene.advance_animation()
                    if scene.sequence_state.sequence_id == 4:
                        break
                self.assertEqual(scene.sequence_state.sequence_id, 4)

    def test_first_selected_run_pose_is_loaded_before_processing_other_directions(self):
        scene = self.fixture.sword_scene()
        scene.sequence_state.facing = 1
        scene.in_animation_tick = True
        scene.horizontal_key(None, 1, True)
        scene.horizontal_key(None, -1, True)
        for _ in range(3):
            self.assertFalse(scene.update_waiting_controls())
        self.assertEqual((scene.sequence_state.sequence_id, scene.sequence_state.cursor), (1, 0))
        self.assertLess(scene.directional_input.left, 0)

    def test_ctrl_does_not_skip_brake_or_make_a_released_draw_request(self):
        for held in (False, True):
            with self.subTest(held=held):
                scene = self.run_at()
                scene.set_key_state('ctrl', True)
                if not held:
                    scene.set_key_state('ctrl', False)
                scene.horizontal_key(None, 1, False)
                poses = []
                for _ in range(25):
                    scene.advance_animation()
                    poses.append(scene.action)
                self.assertEqual(poses[:4], [9, 10, 11, 53])
                self.assertEqual(poses[4:7], [54, 55, 56])
                self.assertEqual(scene.sword_drawn, held)


if __name__ == '__main__':
    unittest.main()
