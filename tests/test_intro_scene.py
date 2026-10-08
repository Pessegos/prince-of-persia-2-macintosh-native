import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

from pop2.game_ui import VISIBLE_VIEWPORT
from pop2.paths import ASSET_DIR


@unittest.skipUnless((ASSET_DIR / "intro.json").is_file(), "Imported intro resources required")
class IntroSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pop2.scene_prototype import ScenePrototype

        cls.scene_class = ScenePrototype

    def setUp(self):
        self.scene = self.scene_class(with_intro=True)
        self.scene.root.withdraw()
        self.scene.root.after_cancel(self.scene.animation_after_id)
        self.scene.animation_after_id = None
        self.scene.schedule_next_animation = lambda: None
        self.addCleanup(self.scene.root.destroy)

    def key(self, keysym, state=0):
        return self.scene.dev_key_press(SimpleNamespace(keysym=keysym, state=state, char=keysym))

    def test_intro_does_not_advance_gameplay_or_accept_movement_input(self):
        scene = self.scene
        before = dict(scene.sequence_state.__dict__)
        self.assertEqual(self.key("Right"), "break")
        self.assertFalse(scene.held_directions)
        scene.last_intro_at = time.perf_counter() - .05
        scene.advance_animation()
        self.assertEqual(scene.sequence_state.__dict__, before)
        self.assertEqual(scene.native_viewport.size, (512, 384))

    def test_pause_freezes_intro_and_resume_resets_its_clock(self):
        scene = self.scene
        scene.intro.advance(2)
        scene.set_paused(True)
        before = scene.intro.time
        scene.advance_animation()
        self.assertEqual(scene.intro.time, before)
        with patch("pop2.window_controls.time.perf_counter", return_value=1000):
            scene.set_paused(False)
        self.assertEqual(scene.last_intro_at, 1000)
        self.assertEqual(scene.intro.time, before)

    def test_complete_intro_frame_is_aligned_with_visible_game_rectangle(self):
        source = Image.new("RGBA", (512, 384), (20, 40, 60, 255))
        source.paste((255, 0, 0, 255), (510, 0, 512, 384))
        source.putpixel((0, 0), (0, 255, 0, 255))
        with patch.object(self.scene.intro, "frame", return_value=source):
            self.scene.render()
        visible = self.scene.native_viewport.crop(VISIBLE_VIEWPORT)
        self.assertEqual(visible.size, (510, 384))
        self.assertEqual(visible.tobytes(), source.crop((0, 0, 510, 384)).tobytes())

    def test_space_skip_does_not_leak_into_level_input(self):
        scene = self.scene
        self.key("space")
        self.assertIsNone(scene.intro)
        self.assertTrue(scene.opening.active)
        self.assertIn("space", scene.pause_resume_keys)
        self.assertFalse(scene.up_held)

    def test_f2_warp_leaves_intro_and_establishes_normal_checkpoint(self):
        scene = self.scene
        scene.jump_to_screen("9")
        self.assertIsNone(scene.intro)
        self.assertIsNotNone(scene.checkpoint)
        self.assertEqual(scene.screen_label(scene.room_id), "9")

    def test_new_game_replays_intro_and_clears_checkpoint(self):
        scene = self.scene
        scene.jump_to_screen("9")
        scene.apply_game_action("new_game")
        self.assertIsNotNone(scene.intro)
        self.assertIsNone(scene.checkpoint)
        self.assertFalse(scene.paused)

    def test_end_game_returns_to_intro_even_from_completed_level(self):
        scene = self.scene
        scene.intro = None
        scene.level_complete = True
        scene.apply_game_action("end")
        self.assertIsNotNone(scene.intro)
        self.assertFalse(scene.level_complete)

    def test_complete_original_scene_program_reaches_window_escape(self):
        scene = self.scene
        saw_title = False
        for _ in range(15000):
            scene.intro.advance(1 / 60)
            saw_title |= scene.intro.title_animation is not None
            if scene.intro.done:
                break
        else:
            self.fail("Intro did not finish")
        self.assertTrue(saw_title)
        self.assertGreater(scene.intro.time, 180)
        self.assertLess(scene.intro.time, 210)
        scene.finish_intro()
        self.assertIsNone(scene.intro)
        self.assertTrue(scene.opening.active)


if __name__ == "__main__":
    unittest.main()
