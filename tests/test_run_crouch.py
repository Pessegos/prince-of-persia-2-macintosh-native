import unittest
from unittest.mock import Mock

from pop2.paths import ASSET_DIR
from pop2.sequence_runtime import SequenceState


@unittest.skipUnless((ASSET_DIR / 'enemy_profiles.json').is_file(), 'Imported controller data required')
class RunningCrouchControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_animation_data import AnimationDataTests
        AnimationDataTests.setUpClass()
        cls.fixture = AnimationDataTests()

    def scene(self, action, facing, forward=True):
        from pop2.scene_prototype import BufferedCommand

        scene = self.fixture.sword_scene()
        scene.sequence_state = SequenceState(200, action=action, facing=facing, cursor=1)
        scene.horizontal_input = (1 if facing else -1) if forward else 0
        scene.held_directions = [scene.horizontal_input] if forward else []
        scene.run_active = True
        scene.run_stop_requested = False
        scene.run_direction = 1 if facing else -1
        scene._combat_controls_locked = Mock(return_value=False)
        scene.start_native_descent = Mock(return_value=True)
        scene.start_crouch_lower = Mock()
        scene.start_sequence = Mock()
        self.assertTrue(scene.buffer_input(BufferedCommand('crouch')))
        return scene

    def test_every_running_pose_ducks_without_consulting_a_ledge_behind(self):
        # GenCtrl 6:124a-1262 selects 26 directly, not StairClimbing.
        for facing in (0, 1):
            for action in range(4, 15):
                with self.subTest(facing=facing, action=action):
                    scene = self.scene(action, facing)
                    self.assertTrue(scene.resume_queued_crouch_during_run())
                    scene.start_native_descent.assert_not_called()
                    scene.start_crouch_lower.assert_called_once_with()

    def test_released_direction_still_brakes_first_on_supporting_poses(self):
        for facing in (0, 1):
            for action in (7, 11):
                with self.subTest(facing=facing, action=action):
                    scene = self.scene(action, facing, forward=False)
                    self.assertTrue(scene.resume_queued_crouch_during_run())
                    scene.start_sequence.assert_called_once_with(13)
                    scene.start_crouch_lower.assert_not_called()
                    scene.start_native_descent.assert_not_called()
                    # Native brake clears pending Down (6:11e4-1206).
                    # A still-held Down can rearm later; this released tap cannot.
                    self.assertEqual(scene.directional_input.down, 0)


@unittest.skipUnless((ASSET_DIR / 'caverns_level5.json').is_file(), 'Imported cavern scenery required')
class RunningCrouchSceneTests(unittest.TestCase):
    def test_other_cavern_ledges_in_both_directions_also_choose_crouch(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.render = Mock()
        # Real floor/space joins where the old dispatcher accepted a descent.
        for level, room, row, x, facing in ((3, 0, 1, 270, 0), (3, 0, 0, 348, 1),
                                            (4, 17, 1, 372, 0), (4, 0, 1, 399, 1),
                                            (5, 3, 1, 40, 0), (5, 5, 0, 450, 1)):
            with self.subTest(level=level, room=room + 1, facing=facing):
                scene.load_level(level)
                scene.peaceful = True
                scene.jump_to_room(room, row, x, facing)
                scene.in_animation_tick = True
                scene.start_sequence(200)
                scene.sequence_state.action = scene.action = 4
                scene.sequence_state.cursor = 1
                scene.run_active = True
                scene.run_direction = 1 if facing else -1
                scene.held_directions = [scene.run_direction]
                scene.sample_keyboard()
                self.assertIsNotNone(scene.level_map.descend_ledge(
                    room, row, scene.sequence_state, scene.frames[4]))
                scene.set_key_state('down', True)
                self.assertTrue(scene.resume_queued_crouch_during_run())
                self.assertEqual(scene.sequence_state.sequence_id, 26)
                self.assertFalse(scene.native_ledge)

    def test_room_two_running_down_after_the_loose_floor_falls_stays_on_the_platform(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(5)
        scene.peaceful = True
        scene.render = Mock()
        scene.jump_to_room(1, 1, 180, 1)
        scene.in_animation_tick = True
        loose = scene.game.caverns.loose
        loose.trigger(scene.level_map.tile(1, 2, 1), force=True)
        for _ in range(3):
            loose.advance_tiles(scene.level_map)
        self.assertEqual(scene.level_map.tile(1, 2, 1).kind, 0)
        scene.horizontal_key(None, 1, True)
        RooftopSceneTests.tick(self, 4)
        self.assertEqual(scene.action, 4)
        # The old common dispatcher interpreted this running request as a
        # standing ledge descent and selected68, eventually entering row2.
        self.assertIsNotNone(scene.level_map.descend_ledge(
            1, 1, scene.sequence_state, scene.frames[scene.action]))
        scene.set_key_state('down', True)
        RooftopSceneTests.tick(self)
        self.assertEqual((scene.sequence_state.source_sequence_id, scene.action), (26, 107))
        scene.horizontal_key(None, 1, False)
        for _ in range(18):
            RooftopSceneTests.tick(self)
            self.assertFalse(scene.native_ledge or scene.terrain_motion.falling)
            self.assertEqual(scene.terrain_motion.row, 1)
            self.assertEqual(scene.sequence_state.current_y, 0)
        self.assertEqual((scene.action, scene.combat.player.life), (109, 3))


if __name__ == '__main__':
    unittest.main()
