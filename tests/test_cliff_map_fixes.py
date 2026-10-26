"""Regressions for F3 room admission/capture and the ruins cliff entry/fall."""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from pop2.paths import ASSET_DIR
from pop2.screenshots import ScreenshotSettings


@unittest.skipUnless((ASSET_DIR / 'ruins_level6.json').is_file(), 'Imported ruins required')
class CliffMapTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.tick(self, count)

    def test_every_displayed_cavern_and_ruins_room_accepts_a_map_warp(self):
        from pop2.development_map import room_positions

        s = self.scene
        with patch.object(s, 'render'):
            for number in range(3, 10):
                s.load_level(number)
                positions = room_positions(s.level_map)
                for label, room in s.dev_screens().items():
                    if room not in positions:
                        continue
                    with self.subTest(level=number, screen=label):
                        s.jump_to_screen(label)
                        self.assertEqual(s.room_id, room)
                        self.assertGreater(s.combat.player.life, 0)

    def test_air_only_map_room_can_be_inspected_without_inventing_a_floor(self):
        s = self.scene
        with patch.object(s, 'render'), patch.object(s, 'advance_audio'):
            s.load_level(6)
            s.jump_to_screen('Room 15')
            self.assertFalse(s.level_map.supports(s.room_id, 5, s.terrain_motion.row))
            self.tick(4)
            self.assertTrue(s.terrain_motion.falling)

    def test_ui_map_capture_uses_same_detail_layer_as_window_at_export_size(self):
        s = self.scene
        s.load_level(8)
        s.open_dev_mode()
        s.apply_dev_action(s.dev_menu.activate())
        menu = s.dev_menu
        self.assertTrue(menu.map_enabled)
        with TemporaryDirectory() as directory, patch.object(s, 'show_screenshot_toast'):
            for scale in (1, 2, 4):
                with self.subTest(scale=scale):
                    s.screenshot_settings = ScreenshotSettings(Path(directory), scale)
                    low = s.native_viewport.crop((1, 0, 511, 384)).resize(
                        (510 * scale, 384 * scale), Image.Resampling.NEAREST)
                    expected = menu.present_map(low.copy(), s.ui_font).convert('RGB')
                    path = s.capture_screenshot(include_ui=True)
                    with Image.open(path) as actual:
                        self.assertEqual(actual.size, expected.size)
                        self.assertTrue(actual.tobytes() == expected.tobytes())
                        if scale > 1:
                            self.assertTrue(actual.tobytes() != low.convert('RGB').tobytes())
                    clean = s.capture_screenshot()
                    with Image.open(clean) as actual:
                        expected_clean = s.screenshot_viewport.crop((1, 0, 511, 384)).resize(
                            actual.size, Image.Resampling.NEAREST).convert('RGB')
                        self.assertTrue(actual.tobytes() == expected_clean.tobytes())

    def test_cliff_exit_closure_reaches_the_closing_audio_lane_once(self):
        from pop2.audio import AudioEngine
        from pop2.mechanism_audio import GateSound

        s = self.scene
        s.load_level(6)
        audio = AudioEngine(ASSET_DIR / 'audio', playback=Mock(split_mechanisms=True))
        heard = []

        def drain():
            events = tuple(s.game.caverns.plates.gate_sounds)
            heard.extend(events)
            s.game.caverns.plates.gate_sounds.clear()
            audio.drain(s.sequence_state, gate_events=events)

        with patch.object(s, 'render'), patch.object(s, 'advance_audio', side_effect=drain):
            self.tick(4)
            self.assertEqual(heard, [])
            s.horizontal_key(SimpleNamespace(keysym='Left', state=0), -1, True)
            for _ in range(30):
                self.tick()
                if s.room_id != 26:
                    s.horizontal_key(SimpleNamespace(keysym='Left', state=0), -1, False)
                    self.tick(4)
                    break
        self.assertEqual(s.room_id, 2)
        self.assertEqual(heard, [GateSound(20, False, (2, 24))])
        self.assertTrue(any(event.cue == 20 and not event.opening for event in audio.gate_events))

    def test_running_jump_off_cliff_keeps_forward_arc_and_scream_without_impact(self):
        from pop2.audio import AudioEngine
        from tests.test_audio import TimedPlayback

        s = self.scene
        with patch.object(s, 'render'), patch.object(s, 'advance_audio'):
            s.load_level(6)
            audio = AudioEngine(playback=object())
            audio.playback = TimedPlayback(audio.cues)
            s.audio = audio
            self.tick(4)
            s.horizontal_key(SimpleNamespace(keysym='Right', state=0), 1, True)
            self.tick(6)
            s.up_key(SimpleNamespace(keysym='Up', state=0))
            positions, cues = [], []
            for _ in range(50):
                self.tick()
                positions.append(s.sequence_state.target_x)
                cues.extend(s.sequence_state.sound_events)
                audio.drain(s.sequence_state, gate_events=())
                audio.flush()
                if s.terrain_motion.dead:
                    break
            self.assertTrue(s.terrain_motion.dead)
            self.assertEqual(positions, sorted(positions))
            self.assertGreater(positions[-1], 480)
            self.assertEqual(cues.count(8), 1)
            self.assertNotIn(7, cues)
            self.assertTrue(audio.sound_playing(8))
            self.assertFalse(audio.death_ready())
            # The imported scream plays to its actual end; death/retry must
            # not silence it or start the death song over it.
            audio.playback.advance(audio.cues[8]['duration'] - .01)
            self.assertFalse(audio.death_ready())
            audio.playback.advance(.02)
            self.assertTrue(audio.death_ready())
