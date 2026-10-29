"""Native hanging input gate, consumption and the protected climb handoff."""

from itertools import product
import unittest
from unittest.mock import patch


class LedgeSelectorTests(unittest.TestCase):
    def test_gate_matches_independent_original_model(self):
        from pop2.mac_input import DirectionalInput, ledge_input_request
        from tools.reference_input_bank import InputBank
        from tools.reference_ledge_input import ledge_request
        for up, modifier, grip, alive, mode, facing in product(
                (-1, 0, 1), (-2, -1, 0, 1, 2), (0, 1, 12), (-1, 0), (0, 11), (0, 1)):
            bank = InputBank(-1, 1, up, -1, modifier)
            actual = DirectionalInput(*bank.words()).remap(facing_right=bool(facing))
            self.assertEqual(ledge_input_request(actual, grip=grip, alive=alive < 0, sequence_mode=mode),
                             ledge_request(bank, grip=grip, alive=alive, sequence_mode=mode))

    def test_runtime_consumption_matches_original_prefix_model(self):
        from types import SimpleNamespace
        from pop2.ledge_controls import LedgeControls
        from pop2.mac_input import DirectionalInput
        from tools.reference_input_bank import InputBank
        from tools.reference_ledge_input import climb_input, release_input
        for axes, modifier, action in product(product((-1, 0, 1), repeat=4),
                                              (-2, -1, 0, 1, 2), ('climb', 'release')):
            bank = InputBank(*axes, modifier)
            # Input-only prefix: the sampler has already supplied this bank,
            # exactly as in the native probe. No terrain/animation claim.
            scene = SimpleNamespace(directional_input=DirectionalInput(*bank.words()),
                                    waiting_controls_available=lambda: True,
                                    sample_waiting_controls=lambda: None,
                                    pending_action=object(), ledge_jump_chord_direction=1)
            LedgeControls.consume_ledge_input(scene, action)
            expected = climb_input(bank) if action == 'climb' else release_input(bank)
            self.assertEqual(scene.directional_input.words(), expected.words())
            self.assertEqual(scene.modifier_input, expected.modifier)
            self.assertIsNone(scene.pending_action)
            self.assertEqual(scene.ledge_jump_chord_direction, 0)


class LedgeSceneTests(unittest.TestCase):
    def test_released_up_waits_for_grip_then_climbs_without_another_press(self):
        from tests.test_game_ui import GameWindowTests
        fixture = GameWindowTests()
        fixture.setUp()
        scene = fixture.scene
        try:
            with patch.object(scene, 'render'):
                fixture.place(3, 2, 75, facing=0)
                fixture.clear_guards()
                scene.shift_held = True
                scene.in_animation_tick = True
                scene._begin_native_ledge(9)
                fixture.tick()
                scene.ledge_grip_delay = 2
                scene.set_key_state('up', True)
                scene.set_key_state('up', False)
                self.assertIsNone(scene.pending_action)
                fixture.tick()
                self.assertFalse(scene.ledge_climbing)
                self.assertEqual(scene.directional_input.up, -1)
                fixture.tick()
                self.assertTrue(scene.ledge_climbing)
                # Climb consumes Up, then the released physical key samples
                # that positive word back to zero in the same host tick.
                self.assertEqual(scene.directional_input.words(), (0, 0, 0, 0, 1))
        finally:
            fixture.doCleanups()

    def test_modal_clear_discards_climb_taps_and_automatic_repeat(self):
        from pop2.mac_input import DirectionalInput
        from tests.test_animation_data import AnimationDataTests
        AnimationDataTests.setUpClass()
        scene = AnimationDataTests().sword_scene()
        scene.directional_input = DirectionalInput(-1, -1, -1, -1, -2)
        scene.ledge_jump_chord_direction = -1
        scene.ledge_auto_repeat = scene.ledge_repeat_after_tick = True
        scene.clear_waiting_controls()
        self.assertIsNone(scene.directional_input)
        self.assertEqual(scene.ledge_jump_chord_direction, 0)
        self.assertFalse(scene.ledge_auto_repeat)
        self.assertFalse(scene.ledge_repeat_after_tick)

    def test_ctrl_can_keep_a_native_free_air_hang_after_shift_is_released(self):
        from tests.test_game_ui import GameWindowTests
        fixture = GameWindowTests()
        fixture.setUp()
        scene = fixture.scene
        try:
            with patch.object(scene, 'render'):
                fixture.place(3, 2, 75, facing=0)
                fixture.clear_guards()
                scene.shift_held = True
                scene.in_animation_tick = True
                scene._begin_native_ledge(9)
                fixture.tick()
                scene.set_key_state('ctrl', True)
                scene.set_key_state('shift', False)
                fixture.tick()
                self.assertTrue(scene.native_ledge)
                self.assertFalse(scene.terrain_motion.falling)
                self.assertEqual(scene.directional_input.modifier, -2)
                scene.set_key_state('ctrl', False)
                fixture.tick()
                self.assertFalse(scene.native_ledge)
        finally:
            fixture.doCleanups()

    def test_climb_exit_keeps_released_up_down_independent(self):
        from tests.test_animation_data import AnimationDataTests
        AnimationDataTests.setUpClass()
        fixture = AnimationDataTests()
        for facing, order in product((0, 1), (('up', 'down'), ('down', 'up'))):
            with self.subTest(facing=facing, order=order):
                scene = fixture.sword_scene()
                scene.sequence_state.facing = facing
                scene.native_ledge = scene.ledge_hanging = scene.ledge_climbing = True
                scene.up_held = scene.jump_started_for_press = True
                scene.in_animation_tick = True
                scene.start_sequence(10)
                scene.advance_animation()
                scene.set_key_state('up', False)
                for name in order:
                    scene.set_key_state(name, True)
                    scene.set_key_state(name, False)
                self.assertIsNone(scene.pending_action)
                self.assertEqual((scene.directional_input.up, scene.directional_input.down), (-1, -1))
                for _ in range(30):
                    scene.advance_animation()
                    if not scene.native_ledge:
                        break
                self.assertEqual((scene.sequence_state.sequence_id, scene.action), (28, 67))


if __name__ == '__main__':
    unittest.main()
