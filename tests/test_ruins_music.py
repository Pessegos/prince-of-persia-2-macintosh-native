import unittest
from unittest.mock import patch

from pop2.audio import AudioEngine
from pop2.paths import ASSET_DIR
from tests.test_audio import TimedPlayback


@unittest.skipUnless(all((ASSET_DIR / name).is_file() for name in (
    'ruins_level6.json', 'audio/manifest.json')), 'Imported ruins and audio required')
class RuinsMusicTests(unittest.TestCase):
    def setUp(self):
        from tests.test_level6 import LevelSixSceneryTests

        LevelSixSceneryTests.setUp(self)
        self.audio = self.scene.audio = AudioEngine(playback=object())
        self.playback = self.audio.playback = TimedPlayback(self.audio.cues)
        self.audio.configure_level(self.scene.game.level.data)
        self.scene.advance_audio()
        self.cue = self.audio.current_music
        self.assertIn(self.cue, range(139, 171))
        self.playback.advance(1)

    def enter_ruins(self):
        from tests.test_level6 import LevelSixSceneryTests

        # Walk through CutChar, then exercise the first door-entry frames.
        LevelSixSceneryTests.tick(self, 4)
        self.scene.horizontal_key(None, -1, True)
        for _ in range(25):
            LevelSixSceneryTests.tick(self)
            if self.scene.room_id != 26:
                break
        self.scene.horizontal_key(None, -1, False)
        self.assertEqual(self.scene.room_id, 2)
        LevelSixSceneryTests.tick(self, 5)

    def test_cliff_entry_keeps_the_same_song_position_and_ambient_group(self):
        remaining = self.playback.remaining['music']
        group = self.audio.current_music_group
        clock = self.audio.music_clock
        with patch.object(self.playback, 'play', wraps=self.playback.play) as play:
            with patch.object(self.playback, 'stop', wraps=self.playback.stop) as stop:
                self.enter_ruins()
        self.assertEqual(self.audio.current_music, self.cue)
        self.assertEqual(self.playback.remaining['music'], remaining)
        self.assertIs(self.audio.music_clock, clock)
        self.assertTrue(self.audio.current_music_ambient)
        self.assertEqual(self.audio.current_music_group, group)
        self.assertFalse(any(c.args[0] == 'music' for c in play.call_args_list))
        self.assertFalse(any(c.args[0] == 'music' for c in stop.call_args_list))
        # It must remain ambient, so combat can still replace it.
        self.audio.ambient(2, 2, 4, fighting=True)
        self.audio.flush()
        self.assertIn(self.audio.current_music, range(171, 175))
        self.assertEqual(self.audio.current_music_group, 2)

    def test_finished_cliff_song_can_start_the_next_ambient_song(self):
        self.playback.advance(1000)
        self.enter_ruins()
        self.assertNotEqual(self.audio.current_music, self.cue)
        self.assertTrue(self.audio.current_music_ambient)
        self.assertTrue(self.audio.music_busy)

    def test_foreground_song_survives_entry_and_still_blocks_ambient(self):
        self.audio.add_song(185)
        self.audio.flush()
        self.playback.advance(.5)
        remaining = self.playback.remaining['music']
        self.enter_ruins()
        self.assertEqual(self.audio.current_music, 185)
        self.assertFalse(self.audio.current_music_ambient)
        self.assertEqual(self.playback.remaining['music'], remaining)

    def test_developer_warp_and_restart_still_stop_the_old_song(self):
        self.enter_ruins()
        with patch.object(self.playback, 'stop', wraps=self.playback.stop) as stop:
            self.scene.jump_to_room(2, 2, 226, 1)
        stop.assert_any_call('music')
        self.scene.load_level(6)
        self.assertIsNone(self.audio.current_music)
        self.assertFalse(self.audio.music_busy)
