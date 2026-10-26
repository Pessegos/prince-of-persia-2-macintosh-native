"""Terminal jump presentation must preserve stone occlusion and gameplay."""

from dataclasses import asdict, replace
import random
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import ImageChops

from pop2.jump_descent import capture_jump_end, descent_drawing
from pop2.paths import ASSET_DIR
from pop2.sequence_runtime import SequenceState
from pop2.terrain import TerrainMotion, floor_y


class TerminalJumpPoseTests(unittest.TestCase):
    def test_pre_alignment_pose_is_rebased_for_drawing_without_moving_the_actor(self):
        state = SequenceState(4, action=44, actor_type=0, level_kind=3,
                              target_x=202, current_x=202, animation_state=1)
        motion = TerrainMotion(18, 2)
        previous = capture_jump_end(motion, state)
        state.target_x, state.current_y, state.action = 217, -100, 102
        state.select(21)
        motion.row, motion.falling = 3, True
        before = asdict(state), asdict(motion)
        drawn = descent_drawing(previous, motion, state)
        self.assertEqual((drawn.action, drawn.target_x, drawn.current_y), (44, 202, -120))
        self.assertEqual(floor_y(motion.row) + drawn.current_y, floor_y(2))
        self.assertEqual((asdict(state), asdict(motion)), before)
        self.assertIsNone(descent_drawing(previous, motion, replace(state, action=103)))
        self.assertIsNone(descent_drawing(previous, replace(motion, room=21), state))
        self.assertIsNone(descent_drawing(previous, replace(motion, falling=False), state))

    def test_ordinary_jumps_other_falls_enemies_and_ruins_keep_their_drawing(self):
        state = SequenceState(4, action=44, actor_type=0, level_kind=3)
        motion = TerrainMotion(18, 2)
        for changes in ({'actor_type': 2}, {'level_kind': 4}, {'action': 43}, {'sequence_id': 1}):
            with self.subTest(changes=changes):
                self.assertIsNone(capture_jump_end(motion, replace(state, **changes)))
        self.assertIsNone(capture_jump_end(replace(motion, row=1), state))
        self.assertIsNone(capture_jump_end(replace(motion, dead=True), state))


@unittest.skipUnless((ASSET_DIR / 'caverns_entry.json').is_file(), 'Imported caverns required')
class TerminalJumpSceneTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.tick(self, count)

    def test_room19_terminal_pose_preserves_the_wall_pixels_and_the_native_motion(self):
        s, traces, images = self.scene, [], []
        draw = s.render
        for improved in (False, True):
            random.seed(491)
            trace = []
            with patch.object(s, 'render'), patch.object(s, 'advance_audio'):
                s.load_level(3)
                s.jump_to_room(16, 2, 440, 1)
                s.horizontal_key(SimpleNamespace(keysym='Right', state=0), 1, True)
                self.tick(2)
                s.up_key(SimpleNamespace(keysym='Up', state=0))
                for _ in range(38):
                    self.tick()
                    state, motion = s.sequence_state, s.terrain_motion
                    if state.action == 102 and motion.room == 18:
                        self.assertIsNotNone(s.jump_descent_frame)
                        self.assertEqual(s.jump_descent_frame.action, 44)
                        if improved:
                            draw()
                        else:
                            with patch.object(s, 'jump_descent_frame', None):
                                draw()
                        images.append(s.screenshot_viewport.crop((1, 0, 511, 365)).convert('RGB'))
                        wall = s.foreground.getchannel('A').copy()
                    elif state.action == 103 and motion.room == 18:
                        self.assertIsNone(s.jump_descent_frame)
                    trace.append((asdict(state), asdict(motion), s.combat.player.life))
            traces.append(trace)
        self.assertEqual(traces[0], traces[1])
        self.assertEqual(len(images), 2)
        difference = ImageChops.difference(*images).convert('L')
        self.assertIsNotNone(difference.getbbox())
        # The rejected experiment removed the stone mask. Even one changed
        # opaque wall pixel fails this regression; the sprite stays behind it.
        self.assertIsNone(ImageChops.multiply(difference, wall).getbbox())
        self.assertGreater(sum(difference.histogram()[1:]), 30)
        self.assertEqual(s.room_id, 21)
        self.assertEqual(s.combat.player.life, 2)  # Unchanged unassisted fall damage.

    def test_dev_warp_and_level_reload_clear_the_ephemeral_drawing_pose(self):
        s = self.scene
        with patch.object(s, 'render'):
            s.jump_descent_frame = object()
            s.load_level(3)
            self.assertIsNone(s.jump_descent_frame)
            s.jump_descent_frame = object()
            s.jump_to_room(18, 2, 80, 1)
            self.assertIsNone(s.jump_descent_frame)
