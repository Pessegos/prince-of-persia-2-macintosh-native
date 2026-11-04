"""Reported post-alpha scenarios exercised through the scene host."""

from types import SimpleNamespace
import unittest

from pop2.paths import ASSET_DIR
from pop2.story_progress import MESSAGE_FRAMES


@unittest.skipUnless((ASSET_DIR / 'ruins_level6.json').is_file(), 'Imported game required')
class PlaytestSceneTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests
        RooftopSceneTests.setUp(self)

    def test_space_displays_running_campaign_time_in_ruins_even_after_teleport(self):
        scene = self.scene
        for number in (6, 7, 8, 9):
            with self.subTest(level=number):
                scene.load_level(number)
                scene.game.story.tree_stage = 1
                scene.game.story.minutes = 65
                scene.jump_to_room(3, 2, 180, 1)
                scene.dev_key_press(SimpleNamespace(keysym='space', state=0))
                self.assertEqual(scene.time_message, '65 Minutes Left')
                self.assertEqual(scene.time_message_frames, MESSAGE_FRAMES)
                self.assertEqual(scene.game.story.minutes, 65)
                scene.dev_key_release(SimpleNamespace(keysym='space'))

    def test_space_does_not_start_the_deferred_campaign_clock(self):
        scene = self.scene
        scene.load_level(3)
        scene.dev_key_press(SimpleNamespace(keysym='space', state=0))
        self.assertIsNone(scene.time_message)
        self.assertFalse(scene.game.story.clock_started)

    def test_space_used_to_resume_pause_does_not_also_request_the_clock(self):
        scene = self.scene
        scene.load_level(6)
        scene.game.story.tree_stage = 1
        scene.set_paused(True)
        event = SimpleNamespace(keysym='space', state=0)
        scene.dev_key_press(event)
        self.assertFalse(scene.paused)
        self.assertIsNone(scene.time_message)
        scene.dev_key_press(event)
        self.assertIsNone(scene.time_message)
        scene.dev_key_release(event)
        scene.dev_key_press(event)
        self.assertIsNotNone(scene.time_message)

    def test_inverted_run_jump_starts_while_physical_down_is_still_held(self):
        from tests.test_terrain import RooftopSceneTests
        scene = self.scene
        traces = []
        for flipped in (False, True):
            scene.load_level(6)
            scene.peaceful = True
            scene.jump_to_room(7, 1, 300, 1)
            scene.game.caverns.potions.flip_timer = 100 if flipped else 0
            scene.sync_flipped_controls()
            scene.in_animation_tick = True
            scene.horizontal_key(None, 1, True)
            RooftopSceneTests.tick(self, 4)
            if flipped:
                scene.set_key_state('down', True)
            else:
                scene.up_key(None)
            trace = []
            for _ in range(8):
                RooftopSceneTests.tick(self)
                trace.append((scene.sequence_state.source_sequence_id, scene.action))
            traces.append(trace)
            self.assertTrue(scene.up_held)
        self.assertEqual(traces[0], traces[1])
        self.assertTrue(any(sequence == 4 for sequence, _action in traces[1]))

    def test_inverted_jump_press_during_a_jump_matches_the_upright_handler(self):
        scene = self.scene
        requests = []
        for flipped in (False, True):
            scene.load_level(6)
            scene.jump_to_room(7, 1, 300, 1)
            scene.game.caverns.potions.flip_timer = 100 if flipped else 0
            scene.sync_flipped_controls()
            scene.in_animation_tick = True
            scene.held_directions = [1]
            scene.horizontal_input = 1
            scene.run_active = True
            scene.up_held = True
            scene.start_sequence(4)
            scene.sequence_runtime.next_frame()
            # A real takeoff consumes its held Up. Supply the release before
            # testing a new press in the arc, in physical key coordinates.
            scene.set_key_state('down' if flipped else 'up', False)
            if flipped:
                scene.set_key_state('down', True)
            else:
                scene.up_key(None)
            requests.append(scene.directional_input)
        self.assertLess(requests[0].up, 0)
        self.assertEqual(requests[0], requests[1])

    def test_room4_reach_and_catch_preserve_the_macintosh_hands(self):
        from tests.test_terrain import RooftopSceneTests
        from pop2.scene_prototype import ROOM_ORIGIN_X
        scene = self.scene
        scene.load_level(6)
        scene.peaceful = True
        # The supplied Macintosh/port recordings have already lost these
        # loose slabs. Intact slabs prevent this jump from reaching the edge.
        for cell in (12, 13, 22, 23):
            scene.game.caverns.loose.tiles[3, cell] = (0, 3)
            scene.game.caverns.loose.cleared.add((3, cell))
        scene.jump_to_room(3, 2, 108, 0)
        scene.in_animation_tick = True
        scene.up_key(None)
        scene.start_jump_if_needed()
        hands = {79: (250, 168, 97, 255), 80: (220, 141, 70, 255),
                 91: (250, 168, 97, 255)}
        seen = set()
        for _ in range(40):
            RooftopSceneTests.tick(self)
            if scene.action in hands:
                with self.subTest(pose=scene.action):
                    self.assertEqual((scene.player_x, scene.terrain_motion.row,
                                      scene.sequence_state.facing), (122, 2, 0))
                    # The fingers and forearm cross the perspective slab in
                    # the original video; the former full-surface mask erased
                    # both, including pixels below the logical floor plane.
                    self.assertEqual(scene.native_viewport.getpixel((124, 224)),
                                     hands[scene.action])
                    self.assertNotEqual(scene.native_viewport.getpixel((125, 230)),
                                        scene.background.getpixel((125 - ROOM_ORIGIN_X, 230)))
                seen.add(scene.action)
            if scene.action == 135:
                scene.set_key_state('up', False)
        self.assertEqual(seen, set(hands))
        self.assertEqual((scene.action, scene.terrain_motion.row), (15, 1))
        self.assertFalse(scene.ledge_hanging or scene.terrain_motion.falling)


if __name__ == '__main__':
    unittest.main()
