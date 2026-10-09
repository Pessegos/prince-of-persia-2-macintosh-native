import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

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

    def test_demo_starts_rooftop_music_after_intro_stops(self):
        from pop2.audio import AudioEngine
        from tests.test_audio import TimedPlayback

        audio = AudioEngine(playback=Mock())
        playback = TimedPlayback(audio.cues)
        playback.play = Mock(wraps=playback.play)
        audio.playback = playback
        self.scene.audio = audio
        self.scene.intro.audio = audio
        self.scene.intro.advance(1000)
        self.assertTrue(self.scene.intro.done)
        self.scene.finish_attract_stage()
        self.assertIn(audio.current_music, (40, 41, 42, 43))
        self.assertTrue(audio.current_music_ambient)
        playback.play.assert_any_call("music", audio.current_music)
        while not self.scene.demo.done:
            interval = self.scene.demo.next_update_delay()
            playback.advance(interval)
            self.scene.demo.advance(interval)
            if self.scene.demo.index < 457:
                self.assertTrue(audio.music_busy)
                self.assertTrue(audio.current_music_ambient)
        songs = [call.args[1] for call in playback.play.call_args_list if call.args[0] == "music"]
        self.assertGreaterEqual(sum(cue in (40, 41, 42, 43) for cue in songs), 2)
        self.assertEqual(audio.current_music, 38)
        self.scene.start_credits()
        self.assertEqual(audio.current_music, 10019)

    def test_demo_respects_ambient_music_toggle(self):
        from pop2.audio import AudioEngine

        playback = Mock()
        playback.busy.return_value = False
        audio = AudioEngine(playback=playback)
        self.scene.audio = audio
        audio.set_music_enabled(False)
        self.scene.start_demo()
        self.assertIsNone(audio.current_music)
        audio.set_music_enabled(True)
        self.scene.demo.advance(self.scene.demo.next_update_delay())
        self.assertIn(audio.current_music, (40, 41, 42, 43))

    def test_f2_and_menu_open_playback_controls_without_live_level_controls(self):
        scene = self.scene
        for start in (lambda: None, scene.start_demo, scene.start_credits):
            start()
            self.assertEqual(self.key("F2"), "break")
            self.assertIsNotNone(scene.dev_menu)
            self.assertEqual(scene.dev_menu.tab, 1)
            self.assertFalse(scene.dev_menu.level_available)
            self.assertTrue(scene.paused)
            before = scene.room_id, scene.player_x, scene.peaceful
            scene.apply_dev_action("go")
            scene.apply_dev_action("peaceful")
            self.assertEqual((scene.room_id, scene.player_x, scene.peaceful), before)
            scene.close_dev_mode()
            self.assertFalse(scene.paused)
            scene.open_game_menu()
            self.assertTrue(next(item.enabled for item in scene.game_menu.items
                                  if item.action == "development"))
            scene.apply_game_action("development")
            self.assertIsNotNone(scene.dev_menu)
            self.assertEqual(scene.dev_menu.tab, 1)
            scene.close_dev_mode()
            scene.dev_key_release(SimpleNamespace(keysym="F2"))

    def test_cutscene_pause_uses_hud_position_without_backing_bar(self):
        scene = self.scene
        expected = scene.native_viewport.copy()
        text = scene.cutscene_pause_text
        ink = text.getbbox()
        position = ((512 - text.width) // 2, 365 + (19 - (ink[3] - ink[1])) // 2 - ink[1])
        expected.paste(text, position, text)
        scene.set_paused(True)
        self.assertEqual(scene.native_viewport.tobytes(), expected.tobytes())

    def test_every_imported_playback_part_can_be_selected_without_live_ai_updates(self):
        scene = self.scene
        live = scene.combat
        parts = scene.development_parts()
        self.assertEqual({part.stage for part in parts}, {"intro", "demo", "credits"})
        for part in parts:
            with self.subTest(part=part.label), patch.object(scene, "render"):
                scene.seek_playback_part(part)
                self.assertEqual(scene.attract_stage, part.stage)
                if part.stage == "demo":
                    self.assertEqual(scene.demo.index, part.index)
                    self.assertIsNot(scene.combat, live)
                else:
                    self.assertIs(scene.combat, live)
                self.assertEqual(parts[scene.current_playback_part()], part)
                self.assertFalse(scene.held_directions)
        scene.finish_intro()
        self.assertIs(scene.combat, live)
        self.assertEqual(scene.combat.player.life, 3)
        self.assertIsNone(scene.intro)
        self.assertIsNone(scene.demo)

    def test_next_part_preserves_explicit_pause_and_consumes_activation_key(self):
        scene = self.scene
        scene.set_paused(True)
        scene.open_dev_mode()
        part = scene.development_parts()[scene.dev_menu.section_index + 1]
        scene.dev_menu.focus = 1
        self.key("Return")
        self.assertIsNone(scene.dev_menu)
        self.assertTrue(scene.paused)
        self.assertEqual(scene.development_parts()[scene.current_playback_part()], part)
        self.assertEqual(self.key("Return"), "break")
        self.assertTrue(scene.paused)

    def test_seeking_does_not_briefly_play_the_destination_stages_initial_cues(self):
        from pop2.audio import AudioEngine

        scene = self.scene
        playback = Mock()
        playback.busy.return_value = False
        scene.audio = AudioEngine(playback=playback)
        parts = scene.development_parts()
        for stage in ("intro", "demo", "credits"):
            part = [part for part in parts if part.stage == stage][-1]
            playback.play.reset_mock()
            with self.subTest(stage=stage), patch.object(scene, "render"):
                scene.seek_playback_part(part)
                calls = playback.play.call_args_list
                self.assertNotIn(("effect", 36), [call.args for call in calls])
                if stage == "intro":
                    active = [cue for cue, start, duration in scene.intro.playing.values()
                              if scene.intro.time - start < duration]
                    self.assertEqual([call.args[1] for call in calls], active)
                else:
                    self.assertEqual(len(calls), 1)
                    self.assertEqual(calls[0].args[0], "music")

    def test_f5_has_no_binding_or_effect(self):
        scene = self.scene
        self.assertEqual(scene.root.bind("<F5>"), "")
        for start in (lambda: None, scene.start_demo, scene.start_credits, scene.finish_intro):
            start()
            before = scene.intro, scene.demo, scene.room_id, scene.player_x, scene.paused
            self.assertEqual(self.key("F5"), "break")
            self.assertEqual((scene.intro, scene.demo, scene.room_id, scene.player_x, scene.paused), before)
            scene.dev_key_release(SimpleNamespace(keysym="F5"))

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
