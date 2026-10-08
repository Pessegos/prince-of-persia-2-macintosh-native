import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import wave

import numpy as np

from pop2.audio import AudioEngine
from pop2.audio_formats import digitized_sound, mohawk_resources
from pop2.mac_resources import get_data_fork
from pop2.paths import ASSET_DIR
from tests.test_audio import TimedPlayback
import tests.test_terrain as terrain_tests


@unittest.skipUnless((ASSET_DIR / "audio" / "manifest.json").is_file(),
                     "Original audio has not been imported")
class ImportedAudioTests(unittest.TestCase):
    def test_fresh_import_and_launcher_work_without_sibling_research_folders(self):
        project = Path(__file__).resolve().parents[1]
        image = project.parent / "pop2.hfs"
        if not image.is_file():
            self.skipTest("Original disk image is unavailable")
        with tempfile.TemporaryDirectory() as directory:
            fresh = Path(directory)
            for name in ("pop2", "tools", "vendor"):
                shutil.copytree(project / name, fresh / name,
                                ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copy2(project / "run_game.py", fresh / "run_game.py")
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            env["SDL_AUDIODRIVER"] = "dummy"
            for arguments in (
                ["-m", "tools.extract_assets", str(image)],
                ["run_game.py", "--check"],
                ["-c", "from unittest.mock import patch; import tkinter as tk; "
                 "from pop2.audio import AudioEngine; from pop2.scene_prototype import ScenePrototype; "
                 "root=tk.Tk(); root.withdraw(); audio=AudioEngine(); "
                 "context=patch('pop2.window_controls.tk.Tk', return_value=root); context.start(); "
                 "scene=ScenePrototype(peaceful=True, audio=audio); "
                 "assert audio.effect_busy and audio.music_busy; "
                 "root.after(300, root.quit); root.mainloop(); "
                 "assert scene.native_viewport.getbbox() is not None; "
                 "audio.close(); root.destroy(); context.stop()"],
                ["-c", "from unittest.mock import patch; import tkinter as tk; "
                 "from pop2.audio import AudioEngine; from pop2.scene_prototype import ScenePrototype; "
                 "root=tk.Tk(); root.withdraw(); audio=AudioEngine(); "
                 "context=patch('pop2.window_controls.tk.Tk', return_value=root); context.start(); "
                 "scene=ScenePrototype(peaceful=True, audio=audio, with_intro=True); "
                 "assert scene.intro is not None and audio.music_busy; "
                 "root.after(300, root.quit); root.mainloop(); "
                 "assert scene.intro.time > 0 and scene.native_viewport.getbbox() is not None; "
                 "scene.set_paused(True); before=scene.intro.time; scene.advance_animation(); "
                 "assert scene.intro.time == before and audio.paused; scene.set_paused(False); "
                 "scene.finish_intro(); assert scene.opening.active and audio.effect_busy; "
                 "audio.close(); root.destroy(); context.stop()"],
            ):
                result = subprocess.run([sys.executable, *arguments], cwd=fresh, env=env,
                                        capture_output=True, text=True, timeout=120)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((fresh / "assets" / "audio" / "cue-43.wav").is_file())
            self.assertFalse((fresh / "assets" / "Prince of Persia 2").exists())

    def test_all_prepared_cues_are_nonempty_pcm_with_headroom(self):
        audio = AudioEngine(playback=object())
        for cue, item in audio.cues.items():
            if not item.get("file"):
                continue
            with self.subTest(cue=cue), wave.open(str(ASSET_DIR / "audio" / item["file"])) as reader:
                self.assertEqual(reader.getsampwidth(), 2)
                self.assertGreater(reader.getframerate(), 0)
                samples = np.frombuffer(reader.readframes(reader.getnframes()), dtype="<i2")
                self.assertGreater(len(samples), 0)
                self.assertGreater(np.abs(samples.astype(np.int32)).max(), 0)
                self.assertLess(np.abs(samples.astype(np.int32)).max(), 32767)
                if item["kind"] == "midi":
                    duration = len(samples) / reader.getnchannels() / reader.getframerate()
                    self.assertAlmostEqual(duration, item["playback_duration"])
                    self.assertLessEqual(abs(duration - item["duration"]), 0.5)

    def test_rooftop_pool_and_native_death_mapping_are_imported(self):
        audio = AudioEngine(playback=object())
        self.assertEqual(audio.manifest["ambient"][5],
                         {"starts": [40], "counts": [3], "combat_group": -1})
        self.assertEqual([audio.cues[cue]["name"].strip() for cue in range(40, 44)],
                         ["RoofA.mmf", "RoofB.mmf", "RoofC.mmf", "RoofD.mmf"])
        self.assertEqual(audio.manifest["death_cues"][14:16], [38, 39])

    def test_digital_samples_are_the_original_waveform_not_filtered(self):
        image_path = Path(__file__).resolve().parents[2] / "pop2.hfs"
        if not image_path.is_file():
            self.skipTest("Original disk image is unavailable")
        image = image_path.read_bytes()
        archives = {name: mohawk_resources(get_data_fork(image, name))["snd "]
                    for name in ("DigiSnd.dat", "NISDIGI.dat")}
        audio = AudioEngine(playback=object())
        for cue, item in audio.cues.items():
            if item["kind"] != "pcm" or not item.get("file"):
                continue
            with self.subTest(cue=cue):
                archive = archives[item.get("source_archive", "DigiSnd.dat")]
                source = digitized_sound(archive[item.get("resource_id", 9752 + cue)])
                with wave.open(str(ASSET_DIR / "audio" / item["file"])) as reader:
                    actual = np.frombuffer(reader.readframes(reader.getnframes()), dtype="<i2")
                    expected = (np.frombuffer(source.pcm, dtype=np.uint8).astype(np.int16) - 128) * 64
                    np.testing.assert_array_equal(actual, expected)
                    self.assertEqual((reader.getframerate(), reader.getnchannels()),
                                     (source.rate, source.channels))


@unittest.skipUnless((ASSET_DIR / "audio" / "manifest.json").is_file(),
                     "Original audio has not been imported")
class SceneAudioTests(unittest.TestCase):
    def setUp(self):
        terrain_tests.RooftopSceneTests.setUp(self)
        self.scene.audio = AudioEngine(playback=object())
        self.backend = TimedPlayback(self.scene.audio.cues)
        self.scene.audio.playback = Mock(wraps=self.backend)
        self.scene.peaceful = True

    def tick(self, count=1):
        for _ in range(count):
            interval = self.scene.current_animation_interval_ms() / 1000
            self.now += interval
            self.backend.advance(interval)
            with patch("pop2.scene_prototype.time.perf_counter", return_value=self.now):
                self.scene.advance_animation()

    def effects(self):
        return [call.args[1] for call in self.scene.audio.playback.play.call_args_list
                if call.args[0] == "effect"]

    def test_window_escape_plays_glass_and_landing_without_buffered_events(self):
        self.scene.audio.add_sound = Mock(wraps=self.scene.audio.add_sound)
        self.scene.restart_opening()
        self.assertIn(36, self.effects())
        self.tick(25)
        self.scene.audio.add_sound.assert_any_call(296, 0)
        # The longer, higher-priority glass sample must not be cut by footsteps.
        self.assertEqual(self.effects(), [36])
        self.assertFalse(self.scene.sequence_state.sound_events)

    def test_running_uses_sequence_footsteps_and_pause_freezes_both_buses(self):
        scene = self.scene
        scene.jump_to_room(1, row=1, x=400, facing=0)
        scene.horizontal_key(None, -1, True)
        self.tick(12)
        self.assertTrue({294, 295}.intersection(self.effects()))
        scene.set_paused(True)
        before = self.backend.remaining.copy()
        self.tick(30)
        self.assertEqual(self.backend.remaining, before)
        scene.set_paused(False)
        self.tick()
        self.assertNotEqual(self.backend.remaining, before)

    def test_focus_loss_pauses_simulation_and_both_buses_until_explicit_resume(self):
        scene = self.scene
        scene.jump_to_room(1, row=1, x=400, facing=0)
        scene.dev_key_press(SimpleNamespace(keysym="Left", state=0))
        scene.horizontal_key(None, -1, True)
        self.tick(12)
        scene.sequence_state.sound_events.append(14)
        scene.advance_audio()
        with patch.object(scene.root, "after_idle", return_value="focus-pause"):
            scene.focus_out(SimpleNamespace(widget=scene.root))
        with patch.object(scene.root, "focus_get", return_value=None):
            scene.pause_if_unfocused()
        self.assertTrue(scene.paused)
        self.assertTrue(scene.audio.paused)
        self.assertFalse(scene.window_keys_down)
        self.assertFalse(scene.held_directions)
        before_audio = self.backend.remaining.copy()
        before_frame = scene.sequence_state.__dict__.copy()
        self.tick(30)
        self.assertEqual(self.backend.remaining, before_audio)
        self.assertEqual(scene.sequence_state.__dict__, before_frame)
        with patch.object(scene.root, "focus_get", return_value=scene.canvas):
            scene.pause_if_unfocused()
        self.assertTrue(scene.paused)
        scene.dev_key_press(SimpleNamespace(keysym="a", char="a", state=0))
        self.assertFalse(scene.paused)
        self.assertFalse(scene.audio.paused)

    def test_drawing_sword_plays_once_at_the_start_of_the_action(self):
        scene = self.scene
        scene.jump_to_room(1, row=1, x=300, facing=0)
        scene.start_sword_action("sword_draw")
        self.assertEqual(self.effects(), [14])
        self.tick(10)
        self.assertEqual(self.effects(), [14])

    def test_empty_sword_attack_sounds_at_the_strike_pose_not_the_windup(self):
        scene = self.scene
        scene.jump_to_room(1, row=1, x=300, facing=0)
        scene.sword_drawn = True
        scene.start_sword_action("sword_attack")
        self.assertEqual(scene.sequence_state.action, 151)
        self.assertEqual(self.effects(), [])
        self.tick(2)
        self.assertEqual(scene.sequence_state.action, 153)
        self.assertEqual(self.effects(), [])
        self.tick()
        self.assertEqual(scene.sequence_state.action, 154)
        self.assertEqual(self.effects(), [11])
        self.tick(5)
        self.assertEqual(self.effects(), [11])

    def test_attack_after_block_uses_the_same_strike_sound_and_block_alone_is_silent(self):
        scene = self.scene
        scene.jump_to_room(1, row=1, x=300, facing=0)
        scene.sword_drawn = True
        scene.start_sword_action("sword_block")
        self.tick(12)
        self.assertEqual(self.effects(), [])
        scene.start_sword_action("sword_attack", sequence_id=66)
        self.assertEqual(scene.sequence_state.action, 162)
        self.tick(2)
        self.assertEqual(scene.sequence_state.action, 153)
        self.assertEqual(self.effects(), [])
        self.tick()
        self.assertEqual(scene.sequence_state.action, 154)
        self.assertEqual(self.effects(), [11])

    def test_sword_contacts_keep_priority_over_the_empty_swing_sound(self):
        scene = self.scene
        for cue in (10, 12, 31):
            with self.subTest(cue=cue):
                scene.jump_to_room(1, row=1, x=300, facing=0)
                scene.sequence_state.action = 154
                scene.sequence_state.sound_events.append(cue)
                scene.advance_audio()
                self.assertEqual(self.effects()[-1], cue)
                self.assertNotIn(11, self.effects())

    def test_guard_swing_needs_a_valid_target_and_is_drained_in_peaceful_mode(self):
        scene = self.scene
        scene.jump_to_room(1, row=1, x=400, facing=0)
        guard = scene.combat.guard
        guard.sword_drawn = True
        guard.state.action = 154
        guard.state.animation_state = 1
        scene.combat.player.targetable = True
        scene.advance_audio()
        self.assertEqual(self.effects(), [])
        self.assertFalse(guard.state.sound_events)
        scene.peaceful = False
        scene.combat.player.targetable = False
        scene.advance_audio()
        self.assertEqual(self.effects(), [])
        scene.combat.player.targetable = True
        scene.advance_audio()
        self.assertEqual(self.effects(), [11])

    def test_fatal_ground_impact_stops_the_scream_and_plays_the_death_impact(self):
        scene = self.scene
        scene.jump_to_room(1, row=1, x=300, facing=0)
        scene.audio.add_sound(8)
        scene.audio.flush()
        scene.physics.select(scene.sequence_runtime, 12)
        scene.sequence_state.current_y = -1
        scene.sequence_state.vertical_velocity = 63
        scene.terrain_motion.falling = True
        scene.advance_terrain(scene.player_x)
        scene.advance_audio()
        self.assertFalse(scene.combat.player.alive)
        self.assertEqual(self.effects(), [8, 7])
        scene.audio.playback.stop.assert_any_call("effect")
        self.assertFalse(scene.sequence_state.sound_events)

    def test_surviving_a_hard_landing_uses_the_hurt_impact_not_the_death_sound(self):
        scene = self.scene
        scene.jump_to_room(1, row=1, x=300, facing=0)
        scene.physics.select(scene.sequence_runtime, 12)
        scene.sequence_state.current_y = -1
        scene.sequence_state.vertical_velocity = 50
        scene.terrain_motion.falling = True
        scene.advance_terrain(scene.player_x)
        scene.advance_audio()
        self.assertEqual(scene.combat.player.life, 2)
        self.assertEqual(self.effects(), [13])

    def test_warp_stops_existing_effects_and_catch_plays_the_native_cue(self):
        scene = self.scene
        scene.restart_opening()
        scene.jump_to_room(1, row=1, x=400, facing=0)
        self.assertEqual(self.backend.remaining["effect"], 0)
        scene._begin_native_ledge(15)
        self.assertIn(9, self.effects())
        scene.audio.playback.stop.assert_any_call("music")

    def test_long_fall_screams_once_except_in_the_original_harbor_rooms(self):
        scene = self.scene
        for room, row, expected in ((3, 1, True), (14, 0, False), (15, 2, False), (18, 2, False)):
            with self.subTest(room=room):
                scene.jump_to_room(room, row=row, x=300, facing=0)
                scene.physics.select(scene.sequence_runtime, 23)
                scene.sequence_state.current_y = -200
                scene.sequence_state.vertical_velocity = 59
                scene.terrain_motion.falling = True
                scene.sequence_state.sound_events.clear()
                scene.advance_terrain(scene.player_x)
                self.assertEqual(8 in scene.sequence_state.sound_events, expected)
                scene.sequence_state.sound_events.clear()
                scene.advance_terrain(scene.player_x)
                self.assertNotIn(8, scene.sequence_state.sound_events)
