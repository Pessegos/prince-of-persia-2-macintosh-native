import json
import subprocess
import sys
import textwrap
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

from pop2.game_ui import VISIBLE_VIEWPORT
from pop2.intro import MAC_TICKS_PER_SECOND
from pop2.paths import ASSET_DIR


@unittest.skipUnless((ASSET_DIR / "intro.json").is_file(), "Imported intro resources required")
class IntroSchedulingTests(unittest.TestCase):
    def test_expensive_intro_frames_do_not_starve_tk_idle_redraws(self):
        result = subprocess.run([sys.executable, "-c", textwrap.dedent("""
            import json
            import time
            import tkinter as tk
            from types import SimpleNamespace
            from pop2.scene_prototype import ScenePrototype

            scene = ScenePrototype.__new__(ScenePrototype)
            scene.root = tk.Tk()
            scene.root.withdraw()
            scene.root.update_idletasks()
            scene.paused = scene.level_complete = False
            scene.animation_after_id = None
            scene.intro = SimpleNamespace(revision=0, done=False, next_update_delay=lambda: 1 / 60)
            scene.intro.advance = lambda _dt: setattr(scene.intro, "revision", scene.intro.revision + 1)
            # Model a fullscreen upload exceeding the transition's 16.7 ms budget.
            scene.render = lambda: time.sleep(.025)
            scene.last_intro_at = scene.next_animation_at = time.perf_counter()
            redraws = []

            def probe():
                scene.root.after_idle(lambda: redraws.append(time.perf_counter()))
                scene.root.after(10, probe)

            probe()
            scene.schedule_next_animation()
            scene.root.after(600, scene.root.quit)
            scene.root.mainloop()
            for timer in scene.root.tk.call("after", "info"):
                scene.root.after_cancel(timer)
            scene.root.destroy()
            print(json.dumps({"redraws": len(redraws), "frames": scene.intro.revision}))
        """)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertGreaterEqual(data["redraws"], 5)
        self.assertGreater(data["frames"], 5)


@unittest.skipUnless((ASSET_DIR / "intro.json").is_file(), "Imported intro resources required")
class OriginalTitleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pop2.intro import IntroAssets

        cls.assets = IntroAssets()

    def title_player(self):
        from pop2.intro import IntroPlayer

        intro = IntroPlayer(self.assets)
        while intro.transition is None or intro.transition[0] != "title":
            if intro.done:
                self.fail("Original scene program did not reach the title")
            intro.advance(1 / 60)
        return intro

    def test_original_script_deadline_is_preserved_despite_continuous_cloud_motion(self):
        from pop2.intro import ScriptAnimation

        script = ScriptAnimation(self.assets.title_script)
        script.advance(float("inf"))
        self.assertEqual((script.next_tick, script.interval), (1000, 5))
        intro = self.title_player()
        start = intro.transition[1]
        self.assertAlmostEqual(intro.wait_until - start, 1020 / MAC_TICKS_PER_SECOND)
        intro.advance(intro.wait_until - intro.time)
        self.assertFalse(intro.title_animation.done)
        self.assertEqual(intro.transition[0], "fade")
        self.assertAlmostEqual(intro.transition[1] - start, 1020 / MAC_TICKS_PER_SECOND)

    def test_blue_sky_background_is_at_top_not_below_the_moving_clouds(self):
        intro = self.title_player()
        expected = self.assets.title_shapes[25365].getpixel((128, 29))
        self.assertEqual(intro.title_background.getpixel((300, 10)), expected)
        self.assertEqual(self.assets.title_palette[expected], (0, 74, 206))
        self.assertEqual(intro.title_background.getpixel((300, 350)), 160)

    def test_title_clock_is_independent_of_host_frame_step_size(self):
        direct = self.title_player()
        incremental = self.title_player()
        direct.advance(13)
        for _ in range(13 * 60):
            incremental.advance(1 / 60)
        self.assertEqual(direct.title_animation.layers, incremental.title_animation.layers)
        self.assertEqual(direct.frame().tobytes(), incremental.frame().tobytes())

    def test_original_title_clock_uses_macintosh_vertical_blank_rate(self):
        intro = self.title_player()
        start = intro.transition[1]
        intro.advance(start + 15 - intro.time)
        # 60.14742 Hz has reached one more five-tick frame than nominal 60 Hz.
        self.assertEqual(intro.title_animation.next_tick, 905)

    def test_original_cloud_script_repeats_without_a_visible_seam(self):
        intro = self.title_player()
        frames = []
        for frame in range(200):
            intro.draw_title(frame * 5, 0)
            frames.append(intro.display.tobytes())
        self.assertEqual(frames[:100], frames[100:])
        intro.draw_title(1000, 0)
        self.assertEqual(intro.display.tobytes(), frames[0])

    def test_clouds_change_in_both_fades_and_keep_the_original_music_deadlines(self):
        intro = self.title_player()
        start = intro.transition[1]
        intro.advance(start + 10 / MAC_TICKS_PER_SECOND - intro.time)
        initial = intro.display.tobytes()
        intro.advance(5 / MAC_TICKS_PER_SECOND)
        self.assertNotEqual(intro.display.tobytes(), initial)
        intro.advance(intro.wait_until - intro.time)
        self.assertEqual(intro.transition[0], "fade")
        deadline = intro.wait_until
        final = intro.display.tobytes()
        intro.advance(5 / MAC_TICKS_PER_SECOND)
        self.assertNotEqual(intro.display.tobytes(), final)
        self.assertEqual(intro.wait_until, deadline)
        self.assertAlmostEqual(deadline - start, 1120 / MAC_TICKS_PER_SECOND)


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

    def test_unchanged_intro_does_not_represent_the_same_viewport(self):
        scene = self.scene
        scene.intro = SimpleNamespace(revision=5, done=False, advance=lambda _dt: None)
        scene.last_intro_at = time.perf_counter()
        with patch.object(scene, "render") as render:
            scene.advance_animation()
        render.assert_not_called()

    def test_changed_intro_frame_is_presented(self):
        scene = self.scene

        def advance(_dt):
            scene.intro.revision += 1

        scene.intro = SimpleNamespace(revision=5, done=False, advance=advance)
        scene.last_intro_at = time.perf_counter()
        with patch.object(scene, "render") as render:
            scene.advance_animation()
        render.assert_called_once_with()

    def test_title_deadline_subtracts_time_spent_rendering(self):
        scene = self.scene
        scene.intro = SimpleNamespace(next_update_delay=lambda: .1)
        scene.last_intro_at = 1000
        with patch("pop2.scene_prototype.time.perf_counter", return_value=1000.03), \
                patch.object(scene.root, "after", return_value="measured") as after:
            self.scene_class.schedule_next_animation(scene)
        self.assertAlmostEqual(scene.next_animation_at, 1000.1)
        self.assertIn(after.call_args.args[0], (70, 71))
        self.assertEqual(scene.animation_after_id, "measured")
        scene.animation_after_id = None

    def test_overdue_intro_frame_yields_to_window_redraws(self):
        scene = self.scene
        scene.intro = SimpleNamespace(next_update_delay=lambda: .1)
        scene.last_intro_at = 1000
        with patch("pop2.scene_prototype.time.perf_counter", return_value=1000.2), \
                patch.object(scene.root, "after", return_value="measured") as after:
            self.scene_class.schedule_next_animation(scene)
        self.assertEqual(after.call_args.args[0], 1)
        scene.animation_after_id = None

    def test_alt_f4_reaches_close_callback_from_fullscreen_intro(self):
        for paused in (False, True):
            with self.subTest(paused=paused):
                result = subprocess.run([sys.executable, "-c", textwrap.dedent("""
                    import json
                    import sys
                    import tkinter as tk
                    from pop2.scene_prototype import ScenePrototype

                    scene = ScenePrototype(with_intro=True)
                    scene.root.after_cancel(scene.animation_after_id)
                    scene.animation_after_id = None
                    scene.schedule_next_animation = lambda: None
                    scene.root.update()
                    scene.toggle_fullscreen()
                    scene.root.update()
                    scene.set_paused(sys.argv[1] == "True")
                    scene.canvas.focus_force()
                    scene.root.update()
                    scene.canvas.event_generate("<Alt-KeyPress-F4>")
                    try:
                        closed = not scene.root.winfo_exists()
                    except tk.TclError:
                        closed = True
                    if not closed:
                        scene.root.destroy()
                    print(json.dumps({"closed": closed}))
                """), str(paused)], capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertTrue(json.loads(result.stdout)["closed"])

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
