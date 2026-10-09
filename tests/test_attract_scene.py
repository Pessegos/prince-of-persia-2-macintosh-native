import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pop2.paths import ASSET_DIR


@unittest.skipUnless((ASSET_DIR / "attract.json").is_file(), "Imported demo resources required")
class AttractSceneTests(unittest.TestCase):
    def setUp(self):
        from pop2.scene_prototype import ScenePrototype

        self.scene = ScenePrototype(with_intro=True)
        self.scene.root.withdraw()
        self.scene.root.after_cancel(self.scene.animation_after_id)
        self.scene.animation_after_id = None
        self.scene.schedule_next_animation = lambda: None
        self.addCleanup(self.scene.root.destroy)

    def key(self, keysym, state=0):
        return self.scene.dev_key_press(SimpleNamespace(keysym=keysym, state=state, char=keysym))

    def test_natural_intro_end_starts_demo_not_a_live_game(self):
        self.scene.finish_attract_stage()
        self.assertIsNone(self.scene.intro)
        self.assertIsNotNone(self.scene.demo)
        self.assertIsNot(self.scene.combat, self.scene.live_combat)
        self.assertEqual(self.scene.attract_stage, "demo")

    def test_demo_credits_intro_cycle(self):
        scene = self.scene
        scene.start_demo()
        scene.last_demo_at = time.perf_counter() - 60
        scene.advance_animation()
        self.assertIsNone(scene.demo)
        self.assertEqual(scene.attract_stage, "credits")
        scene.last_intro_at = time.perf_counter() - 60
        scene.advance_animation()
        self.assertEqual(scene.attract_stage, "intro")
        self.assertIsNotNone(scene.intro)

    def test_any_game_key_starts_clean_game_and_is_consumed(self):
        scene = self.scene
        live = scene.combat
        scene.start_demo()
        scene.demo.index = 460
        scene.apply_demo_frame()
        self.assertEqual(scene.combat.player.life, 0)
        self.assertEqual(self.key("Right"), "break")
        self.assertIs(scene.combat, live)
        self.assertIsNone(scene.demo)
        self.assertIsNone(scene.attract_stage)
        self.assertEqual(scene.combat.player.life, 3)
        self.assertEqual(scene.room_id, scene.level_map.start_room)
        self.assertIsNone(scene.checkpoint)
        self.assertFalse(scene.held_directions)
        self.assertIn("Right", scene.pause_resume_keys)

    def test_credits_can_be_skipped_to_a_clean_game(self):
        self.scene.start_demo()
        self.scene.start_credits()
        self.assertEqual(self.key("a"), "break")
        self.assertIsNone(self.scene.intro)
        self.assertIsNone(self.scene.attract_stage)

    def test_modifiers_and_multimedia_do_not_start_game(self):
        self.scene.start_demo()
        for key in ("Alt_L", "Control_L", "Shift_L", "Caps_Lock", "XF86AudioMute", "Insert"):
            self.key(key)
            self.assertIsNotNone(self.scene.demo, key)
            self.scene.window_keys_down.clear()

    def test_pausing_demo_freezes_clock_and_resume_resets_deadline(self):
        scene = self.scene
        scene.start_demo()
        index = scene.demo.index
        scene.set_paused(True)
        scene.last_demo_at -= 20
        scene.advance_animation()
        self.assertEqual(scene.demo.index, index)
        scene.set_paused(False)
        self.assertLess(time.perf_counter() - scene.last_demo_at, .1)
        scene.advance_animation()
        self.assertEqual(scene.demo.index, index)

    def test_development_jump_restores_live_encounter_and_peaceful_setting(self):
        scene = self.scene
        live = scene.combat
        scene.peaceful = True
        scene.start_demo()
        scene.jump_to_room(scene.level_map.start_room, 1, 400)
        self.assertIs(scene.combat, live)
        self.assertIsNone(scene.demo)
        self.assertTrue(scene.peaceful)

    def test_render_every_demo_frame_without_advancing_live_ai(self):
        scene = self.scene
        scene.start_demo()
        live = scene.live_combat
        original = live.world_frame
        for index in range(len(scene.demo.frames)):
            scene.demo.index = index
            scene.apply_demo_frame()
            scene.render()
        self.assertEqual(live.world_frame, original)
        self.assertEqual(scene.room_id, 9)
        self.assertEqual(scene.combat.player.life, 0)

    def test_fullscreen_presentation_switches_between_demo_and_credits(self):
        scene = self.scene
        scene.start_demo()
        scene.toggle_fullscreen()
        scene.render()
        self.assertIsNone(getattr(scene, "bitmap_presenter", None))
        scene.start_credits()
        scene.intro.advance(2)
        scene.render()
        import sys

        if sys.platform == "win32":
            self.assertIsNotNone(scene.bitmap_presenter)
        scene.finish_attract_stage()
        self.assertEqual(scene.attract_stage, "intro")
        scene.finish_intro()
        self.assertIsNone(scene.bitmap_presenter)
        with patch.object(scene.root, "destroy") as destroy:
            self.assertEqual(self.key("F4", state=0x20000), "break")
            destroy.assert_called_once()
