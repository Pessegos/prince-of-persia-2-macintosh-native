"""Recovered input boundaries and explicitly retained host tolerances."""

import unittest

from pop2.control_mapping import (
    CROUCH_RISE_SEQUENCE,
    IDLE_SEQUENCE,
    JUMP_FORWARD_SEQUENCE,
    JUMP_VERTICAL_SEQUENCE,
    RUN_JUMP_SEQUENCE,
    STANDING_TURN_SEQUENCE,
    SHIFT_STEP_SEQUENCE,
    SWORD_DRAW_SEQUENCE,
    SWORD_GUARD_SEQUENCE,
)
from pop2.scene_prototype import RUN_CYCLE_SEQUENCES, RUN_SEGMENT_SEQUENCES
import tests.test_animation_data as animation_tests


class InputRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        animation_tests.AnimationDataTests.setUpClass()
        cls.fixture = animation_tests.AnimationDataTests()

    def forward_jump(self, pose, facing=1):
        scene = self.fixture.sword_scene()
        scene.sequence_state.facing = facing
        direction = 1 if facing else -1
        scene.up_key(None)
        scene.horizontal_key(None, direction, True)
        scene.set_key_state("up", False)
        scene.horizontal_key(None, direction, False)
        for _ in range(pose - 16):
            scene.advance_animation()
        self.assertEqual((scene.sequence_state.sequence_id, scene.action),
                         (JUMP_FORWARD_SEQUENCE, pose))
        return scene

    def sword_guard(self, facing=1):
        scene = self.fixture.sword_scene()
        scene.sequence_state.facing = facing
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
                    if held:
                        scene.horizontal_key(None, direction, False)
                    scene.horizontal_key(None, direction, True)
                    self.assertEqual(scene.sequence_state.sequence_id, SHIFT_STEP_SEQUENCE)

    def test_hard_fall_recovery_discards_up_tap_but_reads_still_held_keys(self):
        for facing in (0, 1):
            direction = 1 if facing else -1
            for recovery_frame in (0, 1, 10, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30):
                for held_up in (False, True):
                    with self.subTest(facing=facing, recovery_frame=recovery_frame, held_up=held_up):
                        scene = self.fixture.sword_scene()
                        scene.sequence_state.facing = facing
                        scene.held_directions = [direction]
                        scene.start_sequence(20)
                        scene.advance_animation()
                        for _ in range(recovery_frame):
                            scene.advance_animation()
                        self.assertEqual(scene.sequence_state.animation_state, 5)
                        scene.up_key(None)
                        scene.advance_animation()
                        if not held_up:
                            scene.set_key_state('up', False)
                        for _ in range(40):
                            scene.advance_animation()
                            if scene.sequence_state.source_sequence_id != 20:
                                break
                        self.assertEqual(scene.sequence_state.source_sequence_id,
                                         JUMP_FORWARD_SEQUENCE if held_up else 1)
                        self.assertEqual(scene.sequence_state.facing, facing)

    def test_hard_fall_recovery_presses_belong_to_the_bank_not_the_host_slot(self):
        for facing in (0, 1):
            forward = 1 if facing else -1
            for key in ('up', 'down', 'forward', 'backward'):
                for held in (False, True):
                    with self.subTest(facing=facing, key=key, held=held):
                        scene = self.fixture.sword_scene()
                        scene.sequence_state.facing = facing
                        scene.start_sequence(20)
                        for _ in range(6):
                            scene.advance_animation()
                        self.assertEqual(scene.sequence_state.sequence_id, 212)

                        def press(pressed):
                            if key in ('up', 'down'):
                                scene.set_key_state(key, pressed)
                            else:
                                scene.horizontal_key(
                                    None, forward if key == 'forward' else -forward, pressed)

                        press(True)
                        # The old host buffered this press until the next tick
                        # discarded it; the bank owns it from the callback on.
                        self.assertIsNotNone(scene.directional_input)
                        scene.advance_animation()
                        self.assertEqual(scene.directional_input.words()[:4], (0, 0, 0, 0))
                        if not held:
                            press(False)
                        for _ in range(40):
                            scene.advance_animation()
                            if scene.sequence_state.source_sequence_id != 20:
                                break
                        if held:
                            expected = {'up': 28, 'down': 50, 'forward': 1,
                                        'backward': STANDING_TURN_SEQUENCE}[key]
                            self.assertEqual(scene.sequence_state.source_sequence_id, expected)
                        else:
                            # A released tap leaves the Prince at rest.
                            self.assertEqual((scene.sequence_state.source_sequence_id,
                                              scene.action), (20, 15))

    def test_up_tap_after_hard_fall_protected_recovery_still_queues_jump(self):
        for facing in (0, 1):
            scene = self.fixture.sword_scene()
            scene.sequence_state.facing = facing
            scene.held_directions = [1 if facing else -1]
            scene.start_sequence(20)
            for _ in range(32):
                scene.advance_animation()
            self.assertEqual((scene.action, scene.sequence_state.animation_state), (117, 1))
            scene.up_key(None)
            scene.set_key_state('up', False)
            for _ in range(5):
                scene.advance_animation()
                if scene.sequence_state.source_sequence_id != 20:
                    break
            self.assertEqual(scene.sequence_state.source_sequence_id, JUMP_FORWARD_SEQUENCE)

    def test_hard_fall_recovery_resamples_ctrl_instead_of_retaining_a_released_tap(self):
        for held in (False, True):
            with self.subTest(held=held):
                scene = self.fixture.sword_scene()
                scene.start_sequence(20)
                scene.advance_animation()
                scene.set_key_state('ctrl', True)
                if not held:
                    scene.set_key_state('ctrl', False)
                for _ in range(40):
                    scene.advance_animation()
                    if scene.sequence_state.source_sequence_id != 20:
                        break
                self.assertEqual(scene.sequence_state.sequence_id,
                                 SWORD_DRAW_SEQUENCE if held else IDLE_SEQUENCE)

    def test_turn_ready_poses_accept_all_ordinary_buffered_commands(self):
        from pop2.scene_prototype import BufferedCommand

        for facing in (0, 1):
            for kind, expected in (('crouch', 50), ('jump', 28)):
                for pose in (50, 51, 52):
                    with self.subTest(facing=facing, kind=kind, pose=pose):
                        scene = self.fixture.sword_scene()
                        scene.sequence_state.facing = facing
                        scene.start_sequence(STANDING_TURN_SEQUENCE)
                        while scene.sequence_state.action != pose:
                            scene.advance_animation()
                        self.assertTrue(scene.latch_request(BufferedCommand(kind)))
                        scene.advance_animation()
                        self.assertEqual(scene.sequence_state.sequence_id, expected)
                        self.assertNotEqual(scene.sequence_state.sequence_id, IDLE_SEQUENCE)

    def test_held_direction_is_reinterpreted_after_the_turn_changes_facing(self):
        from pop2.scene_prototype import BufferedCommand

        for facing in (0, 1):
            scene = self.fixture.sword_scene()
            direction = -1 if facing else 1
            scene.sequence_state.facing = facing
            scene.start_sequence(STANDING_TURN_SEQUENCE)
            scene.held_directions = [direction]
            self.assertTrue(scene.latch_request(BufferedCommand('horizontal', direction, 'turn')))
            for _ in range(4):
                scene.advance_animation()
            self.assertEqual(scene.action, 48)
            scene.advance_animation()
            self.assertEqual(scene.action, 1)
            self.assertTrue(scene.run_active)

    def test_climb_chord_resolves_current_holds_without_discarding_a_complete_tapped_chord(self):
        for facing in (0, 1):
            direction = 1 if facing else -1
            for held_up in (False, True):
                for held_direction in (False, True):
                    with self.subTest(facing=facing, held_up=held_up, held_direction=held_direction):
                        scene = self.fixture.sword_scene()
                        scene.sequence_state.facing = facing
                        scene.native_ledge = scene.ledge_hanging = scene.ledge_climbing = True
                        scene.up_held = scene.jump_started_for_press = True
                        scene.start_sequence(10)
                        scene.advance_animation()
                        self.assertEqual(scene.action, 135)
                        scene.horizontal_key(None, direction, True)
                        if not held_up:
                            scene.set_key_state('up', False)
                        if not held_direction:
                            scene.horizontal_key(None, direction, False)
                        for _ in range(30):
                            scene.advance_animation()
                            if not scene.ledge_climbing:
                                break
                        self.assertFalse(scene.native_ledge or scene.ledge_hanging)
                        if not held_up and held_direction:
                            self.assertTrue(scene.run_active)
                            self.assertEqual(scene.action, 1)
                        else:
                            self.assertEqual((scene.sequence_state.sequence_id, scene.action), (3, 16))

    def test_releasing_run_jump_horizontal_adds_no_up_request_in_both_facings(self):
        for facing in (0, 1):
            direction = 1 if facing else -1
            for sequence in (RUN_JUMP_SEQUENCE, 46, 47):
                for held_up in (False, True):
                    with self.subTest(facing=facing, sequence=sequence, held_up=held_up):
                        scene = self.fixture.running_jump_scene(facing)
                        if sequence != RUN_JUMP_SEQUENCE:
                            scene.start_sequence(sequence)
                            scene.advance_animation()
                        if not held_up:
                            scene.set_key_state('up', False)
                        before = (scene.sequence_state.sequence_id, scene.action, scene.player_x)
                        up = scene.directional_input.up
                        scene.horizontal_key(None, direction, False)
                        self.assertEqual((scene.sequence_state.sequence_id, scene.action,
                                          scene.player_x), before)
                        if held_up:
                            # A release creates no request (4:3e84): the Up
                            # word keeps what the takeoff or the bump's mode-5
                            # clear (6:0576-059c) left there.
                            self.assertGreaterEqual(scene.directional_input.up, 0)
                            self.assertEqual(scene.directional_input.up, up)
                        if sequence != RUN_JUMP_SEQUENCE:
                            sequences = []
                            for _ in range(20):
                                scene.advance_animation()
                                sequences.append(scene.sequence_state.sequence_id)
                            self.assertEqual(JUMP_VERTICAL_SEQUENCE in sequences, held_up)

    def test_climb_overlap_keeps_shift_steps_and_turn_only_behavior_after_releasing_up(self):
        for facing in (0, 1):
            for reverse in (False, True):
                with self.subTest(facing=facing, reverse=reverse):
                    scene = self.fixture.sword_scene()
                    scene.sequence_state.facing = facing
                    scene.native_ledge = scene.ledge_hanging = scene.ledge_climbing = True
                    scene.up_held = scene.jump_started_for_press = scene.shift_held = True
                    scene.start_sequence(10)
                    scene.advance_animation()
                    direction = (1 if facing else -1) * (-1 if reverse else 1)
                    scene.horizontal_key(None, direction, True)
                    scene.set_key_state('up', False)
                    for _ in range(30):
                        scene.advance_animation()
                        if not scene.ledge_climbing:
                            break
                    self.assertEqual(scene.sequence_state.sequence_id,
                                     STANDING_TURN_SEQUENCE if reverse else SHIFT_STEP_SEQUENCE)
                    if reverse:
                        for _ in range(12):
                            scene.advance_animation()
                        self.assertEqual((scene.sequence_state.sequence_id, scene.action), (IDLE_SEQUENCE, 15))

    def test_releasing_standing_jump_or_run_horizontal_adds_no_up_request(self):
        for facing in (0, 1):
            direction = 1 if facing else -1
            for sequence in (JUMP_FORWARD_SEQUENCE, *sorted(RUN_SEGMENT_SEQUENCES)):
                for held_up in (False, True):
                    with self.subTest(facing=facing, sequence=sequence, held_up=held_up):
                        scene = self.fixture.running_jump_scene(facing)
                        scene.start_sequence(sequence)
                        scene.advance_animation()
                        if not held_up:
                            scene.set_key_state('up', False)
                        before = (scene.sequence_state.sequence_id, scene.action, scene.player_x)
                        up = scene.directional_input.up
                        scene.horizontal_key(None, direction, False)
                        self.assertEqual((scene.sequence_state.sequence_id, scene.action,
                                          scene.player_x), before)
                        if held_up:
                            # No request from the release (4:3e84).
                            self.assertEqual(scene.directional_input.up, up)

    def run_scene_at(self, facing, pose):
        scene = self.fixture.sword_scene()
        scene.sequence_state.facing = facing
        direction = 1 if facing else -1
        scene.horizontal_key(None, direction, True)
        for _ in range(20):
            if scene.sequence_state.sequence_id in RUN_CYCLE_SEQUENCES and scene.action == pose:
                return scene
            scene.advance_animation()
        self.fail(f'Run did not reach pose {pose}')

    def test_ctrl_tap_or_hold_does_not_stop_a_held_run(self):
        for facing in (0, 1):
            for held in (False, True):
                for pose in range(4, 15):
                    with self.subTest(facing=facing, held=held, pose=pose):
                        scene = self.run_scene_at(facing, pose)
                        baseline = self.run_scene_at(facing, pose)
                        scene.set_key_state('ctrl', True)
                        if not held:
                            scene.set_key_state('ctrl', False)
                        for _ in range(24):
                            scene.advance_animation()
                            baseline.advance_animation()
                            self.assertEqual((scene.action, scene.player_x, scene.run_active),
                                             (baseline.action, baseline.player_x, baseline.run_active))
                            self.assertFalse(scene.sword_drawn)

    def test_released_ctrl_during_run_preserves_the_complete_normal_brake(self):
        for facing in (0, 1):
            direction = 1 if facing else -1
            for pose in range(4, 15):
                with self.subTest(facing=facing, pose=pose):
                    scene = self.run_scene_at(facing, pose)
                    baseline = self.run_scene_at(facing, pose)
                    scene.set_key_state('ctrl', True)
                    scene.set_key_state('ctrl', False)
                    for actor in (scene, baseline):
                        actor.horizontal_key(None, direction, False)
                    poses = []
                    for _ in range(24):
                        scene.advance_animation()
                        baseline.advance_animation()
                        poses.append(scene.action)
                        self.assertEqual((scene.action, scene.player_x, scene.run_active),
                                         (baseline.action, baseline.player_x, baseline.run_active))
                        self.assertFalse(scene.sword_drawn)
                    self.assertIn(53, poses)
                    self.assertIn(56, poses)
                    self.assertEqual(scene.action, 15)
                    scene.set_key_state('ctrl', True)
                    self.assertEqual(scene.action, 207)

    def test_held_ctrl_can_draw_at_a_native_standing_brake_pose(self):
        for facing in (0, 1):
            direction = 1 if facing else -1
            scene = self.run_scene_at(facing, 8)
            scene.set_key_state('ctrl', True)
            scene.horizontal_key(None, direction, False)
            before = []
            for _ in range(24):
                before.append(scene.action)
                scene.advance_animation()
                if scene.sword_drawn:
                    break
            self.assertEqual(before[-1], 50)
            self.assertIn(53, before)
            self.assertIn(56, before)
            self.assertEqual(scene.action, 207)
            self.assertEqual(scene.modifier_input, 2)

    def test_ctrl_during_running_jump_preserves_arc_and_brakes_without_a_stored_draw(self):
        for facing in (0, 1):
            direction = 1 if facing else -1
            for pose in range(34, 45):
                with self.subTest(facing=facing, pose=pose):
                    scene = self.fixture.running_jump_scene(facing)
                    baseline = self.fixture.running_jump_scene(facing)
                    for actor in (scene, baseline):
                        actor.set_key_state('up', False)
                        for _ in range(pose - 34):
                            actor.advance_animation()
                    scene.set_key_state('ctrl', True)
                    scene.set_key_state('ctrl', False)
                    for actor in (scene, baseline):
                        actor.horizontal_key(None, direction, False)
                    for _ in range(28):
                        scene.advance_animation()
                        baseline.advance_animation()
                        self.assertEqual((scene.action, scene.player_x, scene.sequence_state.current_y),
                                         (baseline.action, baseline.player_x, baseline.sequence_state.current_y))
                        self.assertFalse(scene.sword_drawn)
                    self.assertEqual(scene.action, 15)

    def test_standing_draw_requires_fresh_ctrl_and_no_directions_or_shift(self):
        for other in ('up', 'down', 'shift', 'horizontal'):
            with self.subTest(other=other):
                scene = self.fixture.sword_scene()
                scene.start_sequence(IDLE_SEQUENCE)
                scene.advance_animation()
                if other == 'horizontal':
                    scene.held_directions = [1]
                else:
                    setattr(scene, other + '_held', True)
                scene.set_key_state('ctrl', True)
                self.assertFalse(scene.sword_drawn)
        scene = self.fixture.sword_scene()
        scene.modifier_input = 2
        scene.ctrl_held = True
        self.assertFalse(scene.try_draw_sword())
        scene.set_key_state('ctrl', False)
        scene.set_key_state('ctrl', True)
        self.assertTrue(scene.sword_drawn)

    def test_ctrl_consumed_by_an_attack_cannot_redraw_after_sheathing(self):
        for facing in (0, 1):
            for repeat in (False, True):
                with self.subTest(facing=facing, repeat=repeat):
                    self.check_attack_hold_after_sheathing(facing, repeat)

    def check_attack_hold_after_sheathing(self, facing, repeat):
        scene = self.sword_guard(facing)
        scene.set_key_state('ctrl', True)
        if repeat:
            # A second press held to pose 157 swings again (4:3f08), and
            # that strike consumes Ctrl as well.
            scene.set_key_state('ctrl', False)
            scene.set_key_state('ctrl', True)
        for _ in range(20):
            scene.advance_animation()
            if scene.sequence_state.sequence_id == SWORD_GUARD_SEQUENCE:
                break
        self.assertEqual(scene.sequence_state.sequence_id, SWORD_GUARD_SEQUENCE)
        scene.set_key_state('down', True)
        scene.set_key_state('down', False)
        for _ in range(50):
            scene.advance_animation()
        self.assertFalse(scene.sword_sheathing)
        self.assertFalse(scene.sword_drawn)
        self.assertEqual(scene.modifier_input, 2)
        scene.set_key_state('ctrl', False)
        scene.set_key_state('ctrl', True)
        self.assertTrue(scene.sword_drawn)

    def test_released_turn_before_jump_pose_26_is_discarded(self):
        # GenCtrl 6:074a-0760 clears directional latches at pose 26.
        for facing in (0, 1):
            for pose in (16, 21, 26):
                with self.subTest(facing=facing, pose=pose):
                    scene = self.forward_jump(pose, facing)
                    backward = -1 if facing else 1
                    scene.horizontal_key(None, backward, True)
                    scene.horizontal_key(None, backward, False)
                    for _ in range(34 - pose):
                        scene.advance_animation()
                    self.assertEqual(scene.action, 15)
                    self.assertEqual(scene.sequence_state.facing, facing)

    def test_released_turn_after_jump_pose_26_survives_until_landing(self):
        for facing in (0, 1):
            with self.subTest(facing=facing):
                scene = self.forward_jump(27, facing)
                backward = -1 if facing else 1
                scene.horizontal_key(None, backward, True)
                scene.horizontal_key(None, backward, False)
                for _ in range(7):
                    scene.advance_animation()
                self.assertEqual((scene.sequence_state.sequence_id, scene.action),
                                 (STANDING_TURN_SEQUENCE, 45))

    def test_pose_26_discards_a_vertical_follow_up_when_up_is_released(self):
        # Held vertical follow-ups keep the wall-climb tolerance, but a
        # released Up must not become an extra jump after landing.
        for facing in (0, 1):
            with self.subTest(facing=facing):
                scene = self.forward_jump(21, facing)
                scene.up_key(None)
                scene.set_key_state('up', False)
                self.assertLess(scene.directional_input.up, 0)
                for _ in range(20):
                    scene.advance_animation()
                self.assertEqual((scene.sequence_state.sequence_id, scene.action),
                                 (IDLE_SEQUENCE, 15))

    def test_shift_forward_while_crouched_keeps_the_low_step_instead_of_a_standing_step(self):
        for facing in (0, 1):
            for ready in (False, True):
                with self.subTest(facing=facing, ready=ready):
                    scene = self.fixture.sword_scene()
                    scene.sequence_state.facing = facing
                    scene.in_animation_tick = True
                    scene.set_key_state('down', True)
                    if ready:
                        for _ in range(12):
                            scene.advance_animation()
                            if scene.action == 109 and scene.sequence_state.cursor > 0:
                                break
                        self.assertEqual(scene.action, 109)
                    scene.set_key_state('shift', True)
                    direction = 1 if facing else -1
                    scene.horizontal_key(None, direction, True)
                    if ready:
                        self.assertEqual(scene.sequence_state.sequence_id, 79)
                    else:
                        self.assertLess(getattr(scene.directional_input,
                                                'right' if direction > 0 else 'left'), 0)
                        for _ in range(12):
                            scene.advance_animation()
                            if scene.sequence_state.sequence_id == 79:
                                break
                        self.assertEqual(scene.sequence_state.sequence_id, 79)
                    scene.horizontal_key(None, direction, False)
                    scene.set_key_state('down', False)
                    sequences = []
                    for _ in range(40):
                        scene.advance_animation()
                        sequences.append(scene.sequence_state.sequence_id)
                    self.assertEqual(scene.action, 15)
                    self.assertFalse(any(29 <= sequence <= 44 for sequence in sequences))

    def test_released_direction_during_crouch_rise_mode_5_is_discarded(self):
        # GenCtrl 6:0576-059c clears directions before dispatch in mode 5.
        for facing in (0, 1):
            for pose in range(110, 117):
                with self.subTest(facing=facing, pose=pose):
                    scene = self.fixture.sword_scene()
                    scene.sequence_state.facing = facing
                    scene.start_sequence(CROUCH_RISE_SEQUENCE)
                    for _ in range(pose - 109):
                        scene.advance_animation()
                    self.assertEqual((scene.action, scene.sequence_state.animation_state),
                                     (pose, 5))
                    backward = -1 if facing else 1
                    scene.horizontal_key(None, backward, True)
                    scene.horizontal_key(None, backward, False)
                    scene.advance_animation()

    def test_released_ctrl_before_legal_block_attack_gate_cancels_attack(self):
        # 4:3f38 clears released Ctrl; 6:27e8 accepts only 150/161 here.
        for facing in (0, 1):
            with self.subTest(facing=facing):
                scene = self.sword_guard(facing)
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

    def test_shift_suppresses_backward_sword_step(self):
        # OnAlert 6:256e-257c requires cb80 == 0 for ordinary retreat; Shift
        # requests the voluntary turn (6:22f2) instead.
        scene = self.sword_guard()
        scene.set_key_state("shift", True)
        scene.horizontal_key(None, -1, True)
        scene.advance_animation()
        self.assertEqual(scene.sequence_state.sequence_id, SWORD_GUARD_SEQUENCE)


if __name__ == "__main__":
    unittest.main()
