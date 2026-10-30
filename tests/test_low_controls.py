"""Directional-bank ownership through low movement and protected rise."""

from itertools import product
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class LowSelectorTests(unittest.TestCase):
    def test_gate_and_consumption_match_the_existing_independent_model(self):
        from dataclasses import replace
        from pop2.mac_input import DirectionalInput, low_input_request
        from tools.reference_input_bank import InputBank
        from tools.reference_low_input import LowContext, low_control
        base = LowContext()
        contexts = [base, replace(base, gate_blocked=True), replace(base, ahead_kind=7),
                    replace(base, ahead_kind=7, foreground=3), replace(base, ahead_kind=12),
                    replace(base, selected=111), replace(base, mode=5), replace(base, selected=27)]
        for pose in (246, 250, 251, 252, 261, 262, 263):
            for selected in (121, 124):
                for own, ahead, behind, blocked in ((7, 7, 7, False), (1, 7, 1, False),
                                                   (1, 1, 1, False), (1, 7, 12, True)):
                    contexts.append(replace(base, pose=pose, sequence=selected, selected=selected,
                                            here_kind=own, ahead_kind=ahead, behind_kind=behind,
                                            scythe_blocked=blocked))
        for axes, modifier, context in product(product((-1, 0, 1), repeat=4),
                                               (-2, -1, 0, 1, 2), contexts):
            bank = InputBank(*axes, modifier)
            expected = low_control(bank, context)
            inside = any(kind in (7, 12, 13) for kind in
                         (context.here_kind, context.ahead_kind, context.behind_kind))
            can_stand = context.here_kind != 7 and not context.scythe_blocked
            actual, sequence = low_input_request(
                DirectionalInput(*bank.words()), context.pose, mode=context.mode, selected=context.selected,
                can_rise=not context.gate_blocked,
                low_ahead=context.ahead_kind in (12, 13) or context.ahead_kind == 7 and context.foreground & 3 != 3,
                inside_low=inside, can_stand_prone=can_stand)
            self.assertEqual((actual.words(), sequence),
                             (expected.bank.words(), expected.requests[-1] if expected.requests else None))

    def test_real_lower_and_rise_modes_are_not_replaced_by_one_generic_clear(self):
        from pop2.mac_input import DirectionalInput, low_input_request
        from tools.reference_input_bank import InputBank
        from tools.reference_input_routes import unarmed_route
        for pose, mode in ((107, 1), (108, 1), (110, 1), (112, 1),
                           (110, 5), (116, 5), (117, 1), (119, 1)):
            bank = InputBank(-1, -1, -1, -1, -2)
            expected, events = unarmed_route(bank, pose, mode=mode, sequence=49)
            actual, sequence = low_input_request(DirectionalInput(*bank.words()), pose, mode=mode, selected=49)
            self.assertEqual(actual.words(), expected.words())
            self.assertIsNone(sequence)
            self.assertEqual(events, ())


class LowSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_animation_data import AnimationDataTests
        AnimationDataTests.setUpClass()
        cls.fixture = AnimationDataTests()

    def at_pose(self, sequence, pose, facing=0):
        scene = self.fixture.sword_scene()
        scene.sequence_state.facing = facing
        scene.in_animation_tick = True
        scene.start_sequence(sequence)
        for _ in range(25):
            scene.advance_animation()
            if scene.action == pose:
                return scene
        self.fail(f'Missing pose {pose} in {sequence}')

    def test_low_step_conflicting_taps_do_not_replay_a_jump_after_rising(self):
        for facing, order in product((0, 1), (('up', 'down'), ('down', 'up'))):
            with self.subTest(facing=facing, order=order):
                scene = self.at_pose(79, 111, facing)
                for key in order:
                    scene.set_key_state(key, True)
                    scene.set_key_state(key, False)
                self.assertIsNone(scene.pending_action)
                poses = []
                for _ in range(30):
                    scene.advance_animation()
                    poses.append(scene.action)
                self.assertNotIn(67, poses)
                self.assertEqual(scene.action, 15)

    def test_protected_rise_clears_released_up_instead_of_jumping_at_the_end(self):
        for facing in (0, 1):
            with self.subTest(facing=facing):
                scene = self.at_pose(49, 112, facing)
                scene.set_key_state('up', True)
                scene.set_key_state('up', False)
                poses = []
                for _ in range(25):
                    scene.advance_animation()
                    poses.append(scene.action)
                self.assertNotIn(67, poses)
                self.assertEqual(scene.action, 15)
                self.assertIsNone(scene.pending_action)

    def test_released_up_survives_only_after_the_last_protected_rise_pose(self):
        for facing, pose in product((0, 1), (116, 117)):
            with self.subTest(facing=facing, pose=pose):
                scene = self.at_pose(49, pose, facing)
                scene.set_key_state('up', True)
                scene.set_key_state('up', False)
                seen = []
                for _ in range(8):
                    scene.advance_animation()
                    seen.append(scene.action)
                self.assertEqual(67 in seen, pose == 117)
                self.assertIsNone(scene.pending_action)

    def test_prone_body_clears_a_released_tap_but_held_direction_rearms_at_idle(self):
        for held in (False, True):
            with self.subTest(held=held):
                scene = self.fixture.sword_scene()
                scene.sequence_state.facing = 1
                scene.in_animation_tick = True
                scene.start_sequence(122)
                scene.action = scene.sequence_runtime.next_frame().action
                scene.terrain_motion = SimpleNamespace(falling=False, sinking=False, dead=False)
                with patch.object(scene, 'crawl_cell', return_value=(4, SimpleNamespace(kind=7, foreground=0))):
                    scene.horizontal_key(None, 1, True)
                    if not held:
                        scene.horizontal_key(None, 1, False)
                    scene.update_crawl()
                    self.assertEqual(scene.directional_input.words(), (0, 0, 0, 0, 0))
                    scene.start_sequence(121)
                    scene.action = scene.sequence_runtime.next_frame().action
                    scene.update_crawl()
                self.assertEqual(scene.sequence_state.sequence_id, 122 if held else 121)

    def test_second_host_poll_cannot_rearm_input_cleared_in_the_same_tick(self):
        from pop2.mac_input import DirectionalInput
        scene = self.at_pose(117, 109, facing=1)
        scene.down_held = True
        scene.held_directions = [1]
        scene.directional_input = DirectionalInput(right=1, down=1)
        scene.in_animation_tick = True
        self.assertFalse(scene.update_waiting_controls())
        first = scene.directional_input
        self.assertEqual(first.words(), (0, 0, 0, 1, 0))
        self.assertFalse(scene.prepare_next_sequence())
        self.assertEqual(scene.directional_input, first)
        scene.retire_waiting_controls()  # End this simulation tick.
        self.assertTrue(scene.update_waiting_controls())
        self.assertEqual(scene.sequence_state.sequence_id, 79)

    def test_wall_bump_and_wall_stop_belong_to_the_bank_and_clear_in_mode_5(self):
        # SEQS 46 (102-109, rising through 49 to 116) and 47 (50-52) are
        # mode 5: GenCtrl 6:0576-059c clears every direction there, so a
        # tap made during the bump is gone and a held key is fresh after it.
        for sequence, last in ((46, 116), (47, 52)):
            for key in ('up', 'down', 'right'):
                for held in (False, True):
                    with self.subTest(sequence=sequence, key=key, held=held):
                        scene = self.fixture.sword_scene()
                        scene.start_sequence(sequence)
                        scene.advance_animation()
                        self.assertTrue(scene.waiting_controls_available())
                        if key == 'right':
                            scene.horizontal_key(None, 1, True)
                        elif key == 'up':
                            scene.up_key(None)
                        else:
                            scene.set_key_state('down', True)
                        if not held:
                            if key == 'right':
                                scene.horizontal_key(None, 1, False)
                            else:
                                scene.set_key_state(key, False)
                        self.assertIsNone(scene.pending_action)
                        while scene.action != last:
                            scene.advance_animation()
                            self.assertIsNone(scene.pending_action)
                        self.assertEqual(scene.directional_input.words()[:4], (0, 0, 0, 0))
                        for _ in range(4):
                            scene.advance_animation()
                        moved = scene.sequence_state.sequence_id not in (sequence, 49, 2)
                        self.assertEqual(moved, held)

    def test_real_tunnel_approach_does_not_repeat_the_first_lie_down_pose(self):
        from tests.test_level6 import LevelSixSceneryTests
        fixture = LevelSixSceneryTests()
        fixture.setUp()
        scene = fixture.scene
        try:
            scene.peaceful = True
            scene.jump_to_room(16, 1, 350, 1)
            with patch.object(scene, 'render'):
                scene.set_key_state('down', True)
                fixture.tick(10)
                scene.horizontal_key(None, 1, True)
                seen = []
                for _ in range(50):
                    fixture.tick()
                    seen.append((scene.sequence_state.sequence_id, scene.action))
                self.assertTrue(any(sequence == 79 for sequence, _ in seen))
                self.assertTrue(any(sequence == 125 for sequence, _ in seen))
                self.assertTrue(any(sequence == 122 for sequence, _ in seen))
                self.assertFalse(scene.terrain_motion.dead or scene.terrain_motion.falling)
        finally:
            fixture.doCleanups()

    def test_released_prone_idle_tap_is_dispatched_from_the_bank(self):
        for facing, forward in product((0, 1), (False, True)):
            with self.subTest(facing=facing, forward=forward):
                scene = self.fixture.sword_scene()
                scene.sequence_state.facing = facing
                scene.in_animation_tick = True
                scene.start_sequence(121)
                scene.action = scene.sequence_runtime.next_frame().action
                scene.terrain_motion = SimpleNamespace(falling=False, sinking=False, dead=False)
                # Supplied low-cell geometry isolates the input handoff.
                with patch.object(scene, 'crawl_cell', return_value=(4, SimpleNamespace(kind=7, foreground=0))):
                    direction = (1 if facing else -1) * (1 if forward else -1)
                    scene.horizontal_key(None, direction, True)
                    scene.horizontal_key(None, direction, False)
                    scene.update_crawl()
                self.assertEqual(scene.sequence_state.sequence_id, 122 if forward else 123)
                self.assertIsNone(scene.pending_action)


if __name__ == '__main__':
    unittest.main()
