import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from pop2.desert import BeachScene
from pop2.level_transition import LevelExit
from pop2.paths import ASSET_DIR
from pop2.playback_navigation import ending_parts, playback_groups
from tests.test_intro import player


class LevelExitTests(unittest.TestCase):
    def test_silent_exit_uses_imported_duration_and_does_not_count_negative_time(self):
        exit = LevelExit(32, 7)
        self.assertFalse(exit.advance(-1))
        self.assertFalse(exit.advance(6.99))
        self.assertTrue(exit.advance(0.01))

    def test_audible_exit_waits_for_its_song_not_previous_ambient_music(self):
        audio = SimpleNamespace(available=lambda cue: cue == 32,
                                current_music=40, music_busy=False, death_ready=lambda: True)
        exit = LevelExit(32, 7)
        self.assertFalse(exit.advance(8, audio))
        audio.current_music, audio.music_busy = 32, True
        self.assertFalse(exit.advance(8, audio))
        audio.music_busy = False
        self.assertTrue(exit.advance(0, audio))

    def test_exit_also_waits_for_the_pending_effect_gate(self):
        audio = SimpleNamespace(available=lambda cue: True, current_music=32,
                                music_busy=False, death_ready=lambda: False)
        exit = LevelExit(32, 7)
        self.assertFalse(exit.advance(7, audio))
        audio.death_ready = lambda: True
        self.assertTrue(exit.advance(0, audio))

    def test_missing_playback_cue_does_not_freeze_a_silent_exit(self):
        audio = SimpleNamespace(available=lambda cue: False)
        self.assertTrue(LevelExit(32, 7).advance(7, audio))

    def test_fade_in_both_restores_the_two_loaded_palettes(self):
        p = player(("wait", 1))
        p.loaded = {1: {1: (120, 80, 20)}, 2: {2: (20, 30, 40)}}
        p.execute("fade_in_both", [0x40001])
        p.advance(p.wait_until)
        self.assertEqual(p.palette[1:3], [(120, 80, 20), (20, 30, 40)])

    def test_voyage_navigation_keeps_four_scenes_and_arrival_in_one_group(self):
        assets = SimpleNamespace(program={"operations": [
            {"op": "sound", "args": [28100, 0]},
            *({"op": "palette", "args": [index, 2, 0]} for index in (28002, 28004, 28002, 28008)),
        ]})
        parts = ending_parts(assets)
        self.assertEqual([part.index for part in parts], [0, 1, 2, 4, 2])
        self.assertEqual([part.stage for part in parts], ["ending"] * 4 + ["level"])
        self.assertEqual(len(playback_groups(parts)), 1)
        self.assertEqual(playback_groups(parts)[0].label, "After Level 1")


def beach_resources():
    header = bytearray(30)
    struct.pack_into(">2H", header, 0, 8, 4075)
    struct.pack_into(">H", header, 28, 4)
    records = b"".join(struct.pack(">16h", index, 1, int(index != 0),
                                  11 if index else 0, 16 if index else 0, *([0] * 11))
                       for index in range(4))
    shape = lambda color: struct.pack(">HhhH", 0, 1, 1, 1) + bytes(4) + bytes([color])
    return {"CUST": {4025: {"data": header + records}},
            "CTBL": {3500: {"data": b"\0\4" + b"\x0a\0\0\1\x14\0\0\2\x1e\0\0\3\x28\0\0\4"}},
            "SHAP": {4075 + i: {"data": shape(i + 1)} for i in range(4)}}


class BeachSceneTests(unittest.TestCase):
    def test_custom_records_use_bottom_coordinates_and_native_six_step_cycle(self):
        beach = BeachScene.read(beach_resources(), 1)
        reds = [beach.draw(beach.room.background.copy(), i).getpixel((1, 0))[0]
                for i in range(8)]
        self.assertEqual(reds, [20, 20, 30, 30, 40, 40, 20, 20])
        self.assertEqual(beach.room.background.getpixel((0, 0)), (10, 0, 0, 255))
        self.assertFalse(beach.room.actor_mask(1).getbbox())

    def test_truncated_and_unsupported_scenes_are_rejected(self):
        for data in (b"", bytes(30), beach_resources()["CUST"][4025]["data"][:-1]):
            resources = beach_resources()
            resources["CUST"][4025]["data"] = data
            with self.subTest(data=data[:4]), self.assertRaises(ValueError):
                BeachScene.read(resources, 1)


@unittest.skipUnless((ASSET_DIR / "ending.json").is_file() and
                     (ASSET_DIR / "Desert.rsrc").is_file(), "Imported voyage resources required")
class OriginalEndingTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)

    def test_boat_keeps_sailing_during_exit_music_then_starts_voyage_once(self):
        scene = self.scene
        scene.jump_to_room(18, 2, 80, facing=0)
        scene.harbor.ship_active, scene.harbor.ship_frame = True, 40
        scene.sequence_state.action = scene.action = 0
        scene.sequence_state.sequence_events.append((-16, ()))
        scene.advance_level_events()
        self.assertTrue(scene.game.complete)
        self.assertEqual(scene.game.exit.song, 32)
        before = scene.harbor.ship_frame
        scene.advance_animation()
        self.assertEqual(scene.harbor.ship_frame, before + 1)
        self.assertIsNone(scene.intro)
        for _ in range(100):
            scene.advance_animation()
            if scene.intro is not None:
                break
        self.assertEqual(scene.attract_stage, "ending")
        self.assertFalse(scene.game.complete)
        self.assertIsNone(scene.game.exit)

    def test_pause_does_not_advance_ship_or_exit_clock(self):
        scene = self.scene
        scene.game.exit, scene.game.complete = LevelExit(32, 7), True
        scene.paused = True
        before = scene.harbor.ship_frame
        scene.advance_animation()
        self.assertEqual((scene.game.exit.elapsed, scene.harbor.ship_frame), (0, before))

    def test_voyage_uses_native_operations_and_initial_capital(self):
        from pop2.intro import IntroAssets, IntroPlayer

        assets = IntroAssets(program_name="ending.json")
        ops = assets.program["operations"]
        self.assertEqual(len(ops), 129)
        self.assertIn({"op": "fade_in_both", "args": [0x40001], "pc": 0xde4}, ops)
        self.assertEqual(next(o["args"] for o in ops if o["op"] == "text" and o["args"][1]),
                         [28000, 1, 25005, 133, -9])
        quick, regular = IntroPlayer(assets), IntroPlayer(assets)
        quick.advance(100)
        for _ in range(6000):
            regular.advance(1 / 60)
            if regular.done:
                break
        self.assertTrue(quick.done and regular.done)
        self.assertAlmostEqual(quick.time, regular.time, places=6)
        self.assertEqual(quick.frame().tobytes(), regular.frame().tobytes())

    def test_voyage_completion_enters_level_two_without_demo_or_roof_state(self):
        scene = self.scene
        scene.combat.player.max_life = 5
        scene.start_ending()
        scene.intro.advance(100)
        scene.finish_attract_stage()
        self.assertEqual((scene.game.level.number, scene.room_id, scene.action), (2, 1, 256))
        self.assertEqual(scene.combat.player.life, 5)
        self.assertIsNone(scene.intro)
        self.assertIsNone(scene.demo)
        self.assertIsNone(scene.opening)
        self.assertIsNone(scene.harbor)
        self.assertIsNone(scene.checkpoint)
        self.assertFalse(scene.game.complete)
        self.assertTrue(scene.game.entry_active)

    def test_skip_voyage_does_not_return_to_level_one_and_suppresses_held_skip(self):
        scene = self.scene
        scene.start_ending()
        scene.window_keys_down.add("space")
        scene.finish_intro()
        self.assertEqual(scene.game.level.number, 2)
        self.assertIn("space", scene.pause_resume_keys)
        self.assertIsNone(scene.intro)

    def test_arrival_finishes_native_sequence_before_accepting_controls(self):
        scene = self.scene
        scene.load_level(2)
        self.assertTrue(scene._combat_controls_locked())
        poses = [scene.action]
        with patch.object(scene, "render"), patch.object(scene.physics, "advance") as physics:
            for _ in range(8):
                scene.advance_animation()
                poses.append(scene.action)
        self.assertEqual(poses, [256, 257, 258, 259, 260, 261, 262, 263, 15])
        physics.assert_not_called()
        self.assertFalse(scene.game.entry_active)
        self.assertFalse(scene._combat_controls_locked())
        self.assertEqual((scene.player_x, scene.player_floor_y()), (247, 226))
        scene.peaceful = True
        for _ in range(10):
            scene.advance_animation()
        self.assertFalse(scene.terrain_motion.falling)
        scene.horizontal_key(None, 1, True)
        for _ in range(8):
            scene.advance_animation()
        self.assertGreater(scene.player_x, 247)

    def test_new_game_and_demo_from_beach_restore_the_level_one_renderer(self):
        scene = self.scene
        scene.load_level(2)
        scene.start_demo()
        self.assertEqual(scene.game.level.number, 1)
        self.assertEqual(scene.attract_stage, "demo")
        scene.new_game()
        self.assertIsNone(scene.demo)
        self.assertTrue(scene.opening.active)

    def test_development_arrival_and_voyage_navigation_build_the_destination_state(self):
        scene = self.scene
        scene.load_ending_assets()
        parts = ending_parts(scene.ending_assets)
        scene.seek_playback_part(parts[1])
        self.assertEqual(scene.attract_stage, "ending")
        self.assertGreater(scene.intro.position, parts[1].index)
        scene.seek_playback_part(parts[-1])
        self.assertEqual((scene.game.level.number, scene.action), (2, 256))
        self.assertIsNone(scene.intro)

    def test_beach_render_is_nonblank_and_has_no_unfilled_plank_rectangle(self):
        scene = self.scene
        scene.load_level(2)
        for _ in range(8):
            scene.advance_animation()
        frame = scene.native_viewport
        self.assertEqual(frame.size, (512, 384))
        self.assertGreater(len(frame.getcolors(512 * 384)), 100)
        self.assertNotEqual(frame.getpixel((420, 300)), (0, 0, 0, 255))
        self.assertNotEqual(frame.getpixel((420, 300)), (255, 255, 255, 255))

    def test_shore_audio_repeats_without_restarting_an_active_wave(self):
        scene = self.scene
        scene.load_level(2)
        scene.audio = Mock()
        scene.audio.current_effect, scene.audio.effect_busy = 51, True
        scene.advance_audio()
        scene.audio.add_sound.assert_not_called()
        scene.audio.effect_busy = False
        scene.advance_audio()
        scene.audio.add_sound.assert_called_once_with(51)
        scene.audio.ambient.assert_not_called()

    def test_beach_dev_jump_replays_arrival_instead_of_using_the_palace_position(self):
        scene = self.scene
        scene.load_level(2)
        scene.jump_to_screen("1")
        self.assertEqual((scene.game.level.number, scene.action, scene.player_x), (2, 256, 277))
        self.assertTrue(scene.game.entry_active)

    def test_demo_labels_and_current_playback_selection_survive_the_level_change(self):
        scene = self.scene
        scene.with_intro = True
        before = [part.label for part in scene.development_parts() if part.stage == "demo"]
        scene.load_level(2)
        parts = scene.development_parts()
        self.assertEqual([part.label for part in parts if part.stage == "demo"], before)
        current = parts[scene.current_playback_part()]
        self.assertEqual((current.stage, current.index), ("level", 2))


if __name__ == "__main__":
    unittest.main()
