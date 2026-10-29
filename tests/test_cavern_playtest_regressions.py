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
            scene.start_sequence(4)
            scene.sequence_runtime.next_frame()
            if flipped:
                scene.set_key_state('down', True)
            else:
                scene.up_key(None)
            requests.append(scene.pending_action)
        self.assertIsNotNone(requests[0])
        self.assertEqual(requests[0], requests[1])

    def test_ruins_loose_slab_covers_the_turban_but_preserves_the_gripping_hand(self):
        from PIL import Image
        from pop2.scene_prototype import ROOM_ORIGIN_X
        scene = self.scene
        scene.load_level(6)
        scene.jump_to_room(3, 2, 108, 1)
        scene.action = scene.sequence_state.action = 91
        scene.sequence_state.animation_state = 2
        scene.render()
        scenery = Image.alpha_composite(scene.background, scene.foreground)
        # Stable hanging pose from the reported room4 screenshot: these blue
        # pixels used to show through the back-drawn loose platform surface.
        for pixel in ((107, 237), (100, 238)):
            self.assertEqual(scene.native_viewport.getpixel(pixel),
                             scenery.getpixel((pixel[0] - ROOM_ORIGIN_X, pixel[1])))
        self.assertNotEqual(scene.native_viewport.getpixel((108, 222)),
                            scene.background.getpixel((108, 222)))
        # The part of the turban below the actual slab stays visible.
        self.assertNotEqual(scene.native_viewport.getpixel((99, 246)),
                            scene.background.getpixel((99, 246)))

    def test_room4_vertical_reach_does_not_draw_through_the_loose_slab(self):
        from tests.test_terrain import RooftopSceneTests
        from pop2.scene_prototype import ROOM_ORIGIN_X
        scene = self.scene
        scene.load_level(6)
        scene.peaceful = True
        scene.jump_to_room(3, 2, 95, 1)
        scene.in_animation_tick = True
        scene.up_key(None)
        RooftopSceneTests.tick(self, 13)
        self.assertEqual(scene.action, 79)
        self.assertEqual(scene.native_viewport.getpixel((105, 226)),
                         scene.background.getpixel((105 - ROOM_ORIGIN_X, 226)))

    def test_ruins_floor_cover_rebuilds_after_loose_slabs_fall(self):
        scene = self.scene
        scene.load_level(6)
        scene.jump_to_room(3, 2, 108, 1)

        def covered():
            room = scene.level_renderer.room(3, scene.game.caverns)
            cover, (x, y) = room.floor_surface[1]
            point = 160 - x, 226 - y
            return (cover.getpixel(point) if 0 <= point[0] < cover.width
                    and 0 <= point[1] < cover.height else 0)

        self.assertEqual(covered(), 255)
        for cell in (12, 13):
            scene.game.caverns.loose.tiles[3, cell] = (0, 3)
            scene.game.caverns.loose.cleared.add((3, cell))
        self.assertEqual(covered(), 0)


if __name__ == '__main__':
    unittest.main()
