"""Original armed request priority and the interim host-buffer bridge."""

from itertools import permutations, product
import unittest


class ArmedSelectorTests(unittest.TestCase):
    def test_request_gate_matches_independent_native_checked_model(self):
        from pop2.mac_input import DirectionalInput
        from pop2.sword_controls import armed_input_request
        from tools.reference_armed_input import on_alert
        from tools.reference_input_bank import InputBank
        for axes, modifier, pose, actor in product(
                product((-1, 0, 1), repeat=4), (-2, -1, 0, 1, 2),
                (15, 150, 151, 157, 158, 161, 165, 167, 168, 169, 170, 171), (0, 1, 7, 8)):
            self.assertEqual(armed_input_request(DirectionalInput(*axes, modifier), pose, actor_type=actor),
                             on_alert(InputBank(*axes, modifier), pose, actor))

    def test_blocked_down_does_not_fall_through_to_lower_priority_input(self):
        from pop2.mac_input import DirectionalInput
        from pop2.sword_controls import armed_input_request
        bank = DirectionalInput(left=-1, up=-1, down=-1)
        self.assertIsNone(armed_input_request(bank, 165))
        self.assertEqual(armed_input_request(bank, 158), 'sheathe')


class ArmedBufferSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_animation_data import AnimationDataTests
        AnimationDataTests.setUpClass()
        cls.fixture = AnimationDataTests()

    def during_draw(self, facing=0):
        scene = self.fixture.sword_scene()
        scene.in_animation_tick = True
        scene.sequence_state.facing = facing
        scene.start_sword_action('sword_draw')
        scene.advance_animation()
        scene.queue_grace_remaining_ms = 0
        return scene

    def test_conflicting_armed_requests_have_priority_in_either_arrival_order(self):
        from pop2.scene_prototype import BufferedCommand
        kinds = ('sword_attack', 'sword_sheathe', 'sword_block', 'sword_advance', 'sword_retreat')
        for facing, pair in product((0, 1), permutations(kinds, 2)):
            with self.subTest(facing=facing, pair=pair):
                scene = self.during_draw(facing)
                for kind in pair:
                    scene.buffer_input(BufferedCommand(kind))
                self.assertEqual(scene.pending_action.kind, min(pair, key=kinds.index))

    def test_real_key_callbacks_cannot_replace_a_queued_strike_with_other_commands(self):
        for facing, key in product((0, 1), ('up', 'down', 'forward', 'backward')):
            with self.subTest(facing=facing, key=key):
                scene = self.during_draw(facing)
                scene.set_key_state('ctrl', True)
                scene.set_key_state('ctrl', False)
                if key in ('up', 'down'):
                    scene.set_key_state(key, True)
                    scene.set_key_state(key, False)
                else:
                    direction = (1 if facing else -1) * (1 if key == 'forward' else -1)
                    scene.horizontal_key(None, direction, True)
                    scene.horizontal_key(None, direction, False)
                self.assertEqual(scene.pending_action.kind, 'sword_attack')
                poses = []
                for _ in range(25):
                    scene.advance_animation()
                    poses.append(scene.action)
                self.assertIn(151, poses)
                self.assertTrue(scene.sword_drawn)
                self.assertFalse(scene.sword_sheathing)

    def test_discarded_rapid_attack_does_not_erase_a_queued_block(self):
        scene = self.fixture.guarded_sword_scene()
        scene.in_animation_tick = True
        scene.queue_sword_action('sword_attack')
        scene.advance_animation()
        scene.queue_sword_action('sword_block')
        scene.queue_sword_action('sword_attack')
        self.assertEqual(scene.pending_action.kind, 'sword_block')

    def test_lower_priority_request_does_not_clear_attack_at_first_guard_boundary(self):
        from pop2.scene_prototype import BufferedCommand, SWORD_GUARD_SEQUENCE
        scene = self.during_draw()
        scene.pending_action = BufferedCommand('sword_attack')
        # JumpSeq has selected guard, but AnimChar has not loaded its pose.
        scene.start_sequence(SWORD_GUARD_SEQUENCE)
        scene.queue_sword_action('sword_sheathe')
        self.assertEqual(scene.pending_action.kind, 'sword_attack')
        self.assertFalse(scene.sword_sheathing)
        for _ in range(4):
            scene.advance_animation()
            if scene.action == 151:
                break
        self.assertEqual(scene.action, 151)

    def test_down_up_taps_during_draw_select_sheathe_in_either_order(self):
        for order in (('down', 'up'), ('up', 'down')):
            with self.subTest(order=order):
                scene = self.during_draw()
                for key in order:
                    scene.set_key_state(key, True)
                    scene.set_key_state(key, False)
                self.assertEqual(scene.pending_action.kind, 'sword_sheathe')
                for _ in range(30):
                    scene.advance_animation()
                self.assertFalse(scene.sword_drawn)
                self.assertFalse(scene.sword_sheathing)
                self.assertEqual(scene.action, 15)
