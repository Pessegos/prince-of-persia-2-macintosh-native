"""One directional owner from takeoff through the grounded accepting gate."""

from itertools import product
import unittest

from pop2.mac_input import DirectionalInput
from tools.audit_airborne_handoff import host_trace


class AirborneHandoffTests(unittest.TestCase):
    def test_real_platform_keeps_up_priority_for_both_late_tap_orders(self):
        for facing, late, order in product((0, 1), (False, True),
                                           (('up', 'down'), ('down', 'up'))):
            with self.subTest(facing=facing, late=late, order=order):
                result = host_trace(facing, order, late)
                self.assertEqual(result['choice'], 'up' if late else 'none')


class AirborneBankTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_animation_data import AnimationDataTests
        AnimationDataTests.setUpClass()
        cls.fixture = AnimationDataTests()

    def jump_at(self, sequence, pose, facing=1):
        scene = self.fixture.sword_scene()
        scene.sequence_state.facing = facing
        scene.in_animation_tick = True
        scene.start_sequence(sequence)
        for _ in range(30):
            scene.advance_animation()
            if scene.action == pose:
                return scene
        self.fail(f'No pose {pose}')

    def test_takeoff_consumes_native_directions_without_a_second_slot(self):
        for sequence, facing in product((3, 4), (0, 1)):
            with self.subTest(sequence=sequence, facing=facing):
                scene = self.fixture.sword_scene()
                scene.sequence_state.facing = facing
                scene.directional_input = DirectionalInput(-1, -1, -1, -1, -2)
                scene.start_sequence(sequence)
                relative = scene.directional_input.remap(facing_right=bool(facing))
                self.assertEqual(relative.words(), (1, -1, 1, -1, 0) if sequence == 3
                                 else (0, 0, 1, 0, 0))

    def test_reset_clears_all_four_directions_and_preserves_modifier(self):
        for sequence, modifier in product((3, 4), ('shift', 'ctrl')):
            pose = 26 if sequence == 3 else 44
            with self.subTest(sequence=sequence, modifier=modifier):
                scene = self.jump_at(sequence, pose)
                scene.set_key_state(modifier, True)
                scene.directional_input = DirectionalInput(-1, -1, -1, -1,
                                                            -1 if modifier == 'shift' else -2)
                scene.update_airborne_controls()
                self.assertEqual(scene.directional_input.words(),
                                 (0, 0, 0, 0, -1 if modifier == 'shift' else -2))

    def test_modal_clear_discards_the_arc_bank_and_wall_followup(self):
        for sequence in (3, 4):
            with self.subTest(sequence=sequence):
                scene = self.jump_at(sequence, 22 if sequence == 3 else 40)
                scene.up_held = True
                scene.held_directions = [1]
                scene.sample_keyboard()
                scene.horizontal_key(None, 1, False)
                scene.set_key_state('down', True)
                self.assertTrue(scene.airborne_vertical_followup)
                scene.clear_keys(None)
                self.assertIsNone(scene.directional_input)
                self.assertFalse(scene.airborne_vertical_followup or scene.run_repeat_up)
                scene.advance_animation()
                self.assertEqual(scene.directional_input.words(), (0, 0, 0, 0, 0))

    def test_released_automatic_repeat_does_not_outlive_the_ordinary_jump(self):
        scene = self.jump_at(3, 25)
        scene.up_held = scene.jump_repeat_armed = True
        scene.advance_animation()  # display26
        scene.advance_animation()  # clear26 then load27/re-sample on release
        self.assertTrue(scene.run_repeat_up)
        scene.set_key_state('up', False)
        self.assertEqual(scene.directional_input.up, 0)
        for _ in range(10):
            scene.advance_animation()
        self.assertEqual((scene.sequence_state.sequence_id, scene.action), (2, 15))

    def test_inverted_callbacks_have_the_same_late_up_priority(self):
        for facing in (0, 1):
            with self.subTest(facing=facing):
                scene = self.jump_at(3, 27, facing)
                scene.controls_flipped = True
                for key in ('down', 'up'):  # logical Up, then logical Down
                    scene.set_key_state(key, True)
                    scene.advance_animation()
                    scene.set_key_state(key, False)
                    scene.advance_animation()
                self.assertEqual((scene.directional_input.up, scene.directional_input.down), (-1, -1))
                for _ in range(8):
                    scene.advance_animation()
                    if scene.sequence_state.sequence_id != 3:
                        break
                self.assertEqual(scene.sequence_state.sequence_id, 28)


if __name__ == '__main__':
    unittest.main()
