"""Reported post-alpha scenarios exercised through the scene host."""

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pop2.paths import ASSET_DIR
from pop2.story_progress import MESSAGE_FRAMES


@unittest.skipUnless((ASSET_DIR / 'ruins_level6.json').is_file(), 'Imported game required')
class RuinsBorderJumpTests(unittest.TestCase):
    def test_the_prince_is_visible_through_the_top_after_the_ruins_floor_breaks(self):
        from PIL import Image

        from pop2.caverns import room_assets
        from tools.audit_temple_routes import Harness, press

        # Level 6 native room 17, below the breakable floor in room 4.
        # Exercise the previous exporter's static records even when the
        # installed assets predate that section.
        program = room_assets(6, 16)[0]
        resting_border = {'16': [
            ['back', 3509, 40, 100, 0, 0, [0, 102, 5, 142], 4, 2, -1],
            ['front', 3518, 102, 5, 16, -1, [0, 102, 5, 153], 4, 2, -1],
        ]}
        harness = Harness(6, draw=True)
        scene = harness.scene
        scene.cave_ambience_enabled = False
        scene.present_viewport = lambda: None
        sprite_for = scene.player_sprite

        def marker(*args, **kwargs):
            sprite = sprite_for(*args, **kwargs)
            painted = Image.new('RGBA', sprite.size, 'magenta')
            painted.putalpha(sprite.getchannel('A'))
            return painted

        try:
            with patch.dict(program, border_redraw=resting_border), patch.object(scene, 'player_sprite', marker):
                scene.jump_to_room(16, row=0, x=111, facing=1, redraw=False)
                harness.tick(3)
                press(harness, 'up', True)
                observations = []
                for tick in range(12):
                    if tick == 2:
                        press(harness, 'up', False)
                    harness.tick()
                    if scene.action in (78, 79):
                        above = scene.level_map.tile(16, 2, -1).kind
                        strip = scene.screenshot_viewport.crop((1, 0, 511, 5)).convert('RGB')
                        pixels = sum(count for count, color in strip.getcolors(2550) if color == (255, 0, 255))
                        observations.append((scene.action, above, pixels))
                self.assertEqual(observations, [(78, 15, 0), (79, 0, 42)])
        finally:
            harness.close()


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

    def begin_room8_descent(self, modifier='shift'):
        scene = self.scene
        scene.load_level(6)
        scene.peaceful = True
        scene.jump_to_room(7, 1, 245, 1)
        scene.in_animation_tick = True
        scene.shift_held = scene.down_held = True
        self.assertTrue(scene.start_native_descent())
        scene.set_key_state('down', False)
        if modifier == 'ctrl':
            scene.set_key_state('ctrl', True)
            scene.set_key_state('shift', False)
        return scene

    def test_room8_swing_hides_the_turban_above_the_native_clip_top(self):
        from PIL import ImageChops
        from tests.test_terrain import RooftopSceneTests
        from pop2.scene_prototype import ROOM_ORIGIN_X

        scene = self.begin_room8_descent()
        seen = set()
        for _ in range(50):
            RooftopSceneTests.tick(self)
            if scene.sequence_state.animation_state != 2 or not 87 <= scene.action <= 99:
                continue
            scenery = scene.room_cache[7].flattened().convert('RGB')
            viewport = scene.native_viewport.convert('RGB')
            with self.subTest(pose=scene.action):
                # Original ClipChar raises the top to245 here. In particular
                # pose87's blue pixels at viewport(222,236..239) must vanish.
                self.assertEqual(viewport.crop((221 + ROOM_ORIGIN_X, 221,
                                                 260 + ROOM_ORIGIN_X, 245)).tobytes(),
                                 scenery.crop((221, 221, 260, 245)).tobytes())
                self.assertIsNotNone(ImageChops.difference(
                    viewport.crop((221 + ROOM_ORIGIN_X, 245, 260 + ROOM_ORIGIN_X, 320)),
                    scenery.crop((221, 245, 260, 320))).getbbox())
            seen.add(scene.action)
        self.assertEqual(seen, set(range(87, 100)))

    def test_room8_grip_expiry_falls_without_catching_the_same_ledge_again(self):
        from unittest.mock import patch
        from tests.test_terrain import RooftopSceneTests

        for modifier in ('shift', 'ctrl'):
            with self.subTest(modifier=modifier):
                scene = self.begin_room8_descent(modifier)
                expired, catches, release = False, [], []
                with patch.object(scene, 'render'):
                    for _ in range(80):
                        RooftopSceneTests.tick(self)
                        state = scene.sequence_state
                        expired |= state.sequence_mode == 11
                        if scene.action == 80:
                            catches.append((scene.room_id, scene.player_x))
                        if state.source_sequence_id == 99 and state.animation_state == 3:
                            release.append(scene.action)
                self.assertTrue(expired)
                self.assertEqual(catches, [])
                # SEQS99's three mode-3 poses81 are release motion. CheckFloor
                # 5:1254-1268 cannot call Catch during those frames.
                self.assertEqual(release, [81, 81, 81])
                self.assertFalse(scene.native_ledge or scene.terrain_motion.falling)
                self.assertEqual((scene.room_id, scene.terrain_motion.row), (3, 2))
                self.assertTrue(scene.terrain_motion.dead)


if __name__ == '__main__':
    unittest.main()
