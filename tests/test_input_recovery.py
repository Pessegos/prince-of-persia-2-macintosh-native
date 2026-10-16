"""Source-backed input gaps; expected failures are not parity coverage."""

import unittest

from pop2.control_mapping import (
    CROUCH_RISE_SEQUENCE,
    IDLE_SEQUENCE,
    JUMP_FORWARD_SEQUENCE,
    RUN_JUMP_SEQUENCE,
    STANDING_TURN_SEQUENCE,
    SHIFT_STEP_SEQUENCE,
    SWORD_DRAW_SEQUENCE,
    SWORD_GUARD_SEQUENCE,
)
from pop2.scene_prototype import RUN_CYCLE_SEQUENCES
import tests.test_animation_data as animation_tests


class InputRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        animation_tests.AnimationDataTests.setUpClass()
        cls.fixture = animation_tests.AnimationDataTests()

    def forward_jump(self, pose):
        scene = self.fixture.sword_scene()
        scene.sequence_state.facing = 1
        scene.up_key(None)
        scene.horizontal_key(None, 1, True)
        scene.set_key_state("up", False)
        scene.horizontal_key(None, 1, False)
        for _ in range(pose - 16):
            scene.advance_animation()
        self.assertEqual((scene.sequence_state.sequence_id, scene.action),
                         (JUMP_FORWARD_SEQUENCE, pose))
        return scene

    def sword_guard(self):
        scene = self.fixture.sword_scene()
        scene.sequence_state.facing = 1
        scene.sword_drawn = True
        scene.start_sequence(SWORD_GUARD_SEQUENCE)
        scene.advance_animation()
        self.assertEqual(scene.action, 158)
        return scene

    def test_shift_opposite_press_turns_without_adding_a_step(self):
        for facing in (0, 1):
            direction = -1 if facing else 1
            for held in (False, True):
                with self.subTest(facing=facing, held=held):
                    scene = self.fixture.sword_scene()
                    scene.sequence_state.facing = facing
                    scene.set_key_state('shift', True)
                    scene.horizontal_key(None, direction, True)
                    self.assertEqual(scene.action, 45)
                    self.assertIsNone(scene.pending_action)
                    if not held:
                        scene.horizontal_key(None, direction, False)
                    poses = [scene.action]
                    for _ in range(20):
                        scene.advance_animation()
                        poses.append(scene.action)
                    self.assertEqual(poses[:8], list(range(45, 53)))
                    self.assertEqual(set(poses[8:]), {15})
                    self.assertEqual(scene.player_x, 116 + 9 * direction)
                    self.assertEqual(scene.sequence_state.facing, 1 - facing)
                    self.assertIsNone(scene.pending_action)
                    if held:
                        scene.horizontal_key(None, direction, False)
                    scene.horizontal_key(None, direction, True)
                    self.assertEqual(scene.sequence_state.sequence_id, SHIFT_STEP_SEQUENCE)

    def test_turn_ready_poses_accept_all_ordinary_buffered_commands(self):
        from pop2.scene_prototype import BufferedCommand

        for facing in (0, 1):
            for kind, expected in (('crouch', 50), ('jump', 28), ('sword_draw', 55)):
                for pose in (50, 51, 52):
                    with self.subTest(facing=facing, kind=kind, pose=pose):
                        scene = self.fixture.sword_scene()
                        scene.sequence_state.facing = facing
                        scene.start_sequence(STANDING_TURN_SEQUENCE)
                        while scene.sequence_state.action != pose:
                            scene.advance_animation()
                        scene.pending_action = BufferedCommand(kind)
                        scene.advance_animation()
                        self.assertEqual(scene.sequence_state.sequence_id, expected)
                        self.assertIsNone(scene.pending_action)
                        self.assertNotEqual(scene.sequence_state.sequence_id, IDLE_SEQUENCE)

    def test_held_direction_is_reinterpreted_after_the_turn_changes_facing(self):
        from pop2.scene_prototype import BufferedCommand

        for facing in (0, 1):
            scene = self.fixture.sword_scene()
            direction = -1 if facing else 1
            scene.sequence_state.facing = facing
            scene.start_sequence(STANDING_TURN_SEQUENCE)
            scene.held_directions = [direction]
            scene.pending_action = BufferedCommand('horizontal', direction, 'turn')
            for _ in range(4):
                scene.advance_animation()
            self.assertEqual(scene.action, 48)
            scene.advance_animation()
            self.assertEqual(scene.action, 1)
            self.assertTrue(scene.run_active)
            self.assertIsNone(scene.pending_action)

    def test_ctrl_during_run_retains_intentional_stop_and_draw_extension(self):
        # Port QoL: preserve the draw request, unlike native modifier sampling.
        for facing in (0, 1):
            for held_ctrl in (False, True):
                for pose in range(4, 15):
                    with self.subTest(facing=facing, held_ctrl=held_ctrl, pose=pose):
                        scene = self.fixture.sword_scene()
                        scene.sequence_state.facing = facing
                        direction = 1 if facing else -1
                        scene.horizontal_key(None, direction, True)
                        for _ in range(20):
                            if (scene.sequence_state.sequence_id in RUN_CYCLE_SEQUENCES
                                    and scene.action == pose):
                                break
                            scene.advance_animation()
                        else:
                            self.fail(f"Run did not reach pose {pose}")

                        before = (scene.sequence_state.sequence_id, scene.action)
                        scene.set_key_state("ctrl", True)
                        if not held_ctrl:
                            scene.set_key_state("ctrl", False)
                        self.assertEqual((scene.sequence_state.sequence_id, scene.action), before)
                        self.assertFalse(scene.sword_drawn)

                        draw_poses = []
                        for _ in range(25):
                            scene.advance_animation()
                            if scene.sequence_state.sequence_id == SWORD_DRAW_SEQUENCE:
                                draw_poses.append(scene.action)
                                self.assertFalse(scene.run_active)
                            if scene.sequence_state.sequence_id == SWORD_GUARD_SEQUENCE:
                                break
                        else:
                            self.fail("Ctrl draw request did not reach sword guard")
                        self.assertEqual(draw_poses, [207, 208, 209, 210])
                        self.assertEqual(scene.action, 158)
                        self.assertTrue(scene.sword_drawn)
                        self.assertIsNone(scene.pending_action)
                        self.assertEqual(scene.sequence_state.facing, facing)

    def test_ctrl_during_running_jump_draws_at_landing_without_an_extra_run_cycle(self):
        for facing in (0, 1):
            direction = 1 if facing else -1
            for held_direction in (False, True):
                reference = self.fixture.running_jump_scene(facing)
                reference.set_key_state("up", False)
                if not held_direction:
                    reference.horizontal_key(None, direction, False)
                original_arc = []
                while reference.sequence_state.sequence_id == RUN_JUMP_SEQUENCE:
                    original_arc.append((reference.action, reference.player_x,
                                         reference.sequence_state.current_y))
                    reference.advance_animation()
                landing = (reference.action, reference.player_x, reference.sequence_state.current_y)
                self.assertEqual(landing[0], 7)
                for held_ctrl in (False, True):
                    for pose in range(34, 45):
                        with self.subTest(facing=facing, held_direction=held_direction,
                                          held_ctrl=held_ctrl, pose=pose):
                            scene = self.fixture.running_jump_scene(facing)
                            scene.set_key_state("up", False)
                            if not held_direction:
                                scene.horizontal_key(None, direction, False)
                            for _ in range(pose - 34):
                                scene.advance_animation()
                            before = (scene.sequence_state.sequence_id, scene.action, scene.player_x)
                            scene.set_key_state("ctrl", True)
                            if not held_ctrl:
                                scene.set_key_state("ctrl", False)
                            self.assertEqual((scene.sequence_state.sequence_id, scene.action, scene.player_x), before)
                            arc = []
                            while scene.sequence_state.sequence_id == RUN_JUMP_SEQUENCE:
                                self.assertFalse(scene.sword_drawn)
                                arc.append((scene.action, scene.player_x, scene.sequence_state.current_y))
                                scene.advance_animation()
                            self.assertEqual(arc, original_arc[pose - 34:])
                            self.assertEqual((scene.action, scene.player_x, scene.sequence_state.current_y), landing)
                            self.assertFalse(scene.sword_drawn)
                            draw_poses = []
                            for _ in range(5):
                                scene.advance_animation()
                                if scene.sequence_state.sequence_id == SWORD_DRAW_SEQUENCE:
                                    draw_poses.append(scene.action)
                                    self.assertFalse(scene.run_active)
                                    self.assertIsNone(scene.pending_action)
                                else:
                                    break
                            self.assertEqual(draw_poses, [207, 208, 209, 210])
                            self.assertEqual((scene.sequence_state.sequence_id, scene.action),
                                             (SWORD_GUARD_SEQUENCE, 158))
                            self.assertEqual(scene.sequence_state.facing, facing)

    def test_ctrl_after_running_jump_does_not_wait_for_the_remaining_run_cycle(self):
        for facing in (0, 1):
            direction = 1 if facing else -1
            for pose in range(7, 15):
                with self.subTest(facing=facing, pose=pose):
                    scene = self.fixture.running_jump_scene(facing)
                    scene.set_key_state("up", False)
                    for _ in range(25):
                        if scene.sequence_state.sequence_id in RUN_CYCLE_SEQUENCES and scene.action == pose:
                            break
                        scene.advance_animation()
                    else:
                        self.fail(f"Jump did not reach post-landing run pose {pose}")
                    scene.horizontal_key(None, direction, False)
                    scene.set_key_state("ctrl", True)
                    scene.set_key_state("ctrl", False)
                    scene.advance_animation()
                    self.assertEqual((scene.sequence_state.sequence_id, scene.action), (SWORD_DRAW_SEQUENCE, 207))
                    self.assertFalse(scene.run_active)
                    self.assertIsNone(scene.pending_action)

    @unittest.expectedFailure
    def test_released_turn_before_jump_pose_26_is_discarded(self):
        # GenCtrl 6:074a-0760 clears directional latches at pose 26.
        scene = self.forward_jump(21)
        scene.horizontal_key(None, -1, True)
        scene.horizontal_key(None, -1, False)
        for _ in range(13):
            scene.advance_animation()
        self.assertEqual(scene.action, 15)
        self.assertEqual(scene.sequence_state.facing, 1)
        self.assertIsNone(scene.pending_action)

    def test_released_turn_after_jump_pose_26_survives_until_landing(self):
        scene = self.forward_jump(27)
        scene.horizontal_key(None, -1, True)
        scene.horizontal_key(None, -1, False)
        for _ in range(7):
            scene.advance_animation()
        self.assertEqual((scene.sequence_state.sequence_id, scene.action),
                         (STANDING_TURN_SEQUENCE, 45))
        self.assertIsNone(scene.pending_action)

    @unittest.expectedFailure
    def test_released_direction_during_crouch_rise_mode_5_is_discarded(self):
        # GenCtrl 6:0576-059c clears directions before dispatch in mode 5.
        scene = self.fixture.sword_scene()
        scene.sequence_state.facing = 1
        scene.start_sequence(CROUCH_RISE_SEQUENCE)
        scene.advance_animation()
        self.assertEqual((scene.action, scene.sequence_state.animation_state),
                         (110, 5))
        scene.horizontal_key(None, -1, True)
        scene.horizontal_key(None, -1, False)
        scene.advance_animation()
        self.assertIsNone(scene.pending_action)

    @unittest.expectedFailure
    def test_released_ctrl_before_legal_block_attack_gate_cancels_attack(self):
        # 4:3f38 clears released Ctrl; 6:27e8 accepts only 150/161 here.
        scene = self.sword_guard()
        scene.up_key(None)
        scene.set_key_state("up", False)
        self.assertEqual(scene.action, 169)
        scene.set_key_state("ctrl", True)
        scene.advance_animation()
        self.assertEqual(scene.action, 150)
        scene.set_key_state("ctrl", False)
        scene.advance_animation()
        self.assertEqual((scene.sequence_state.sequence_id, scene.action),
                         (SWORD_GUARD_SEQUENCE, 158))

    @unittest.expectedFailure
    def test_shift_suppresses_backward_sword_step(self):
        # OnAlert 6:256e-257c requires cb80 == 0 for ordinary retreat.
        scene = self.sword_guard()
        scene.set_key_state("shift", True)
        scene.horizontal_key(None, -1, True)
        scene.advance_animation()
        self.assertEqual(scene.sequence_state.sequence_id, SWORD_GUARD_SEQUENCE)


if __name__ == "__main__":
    unittest.main()
