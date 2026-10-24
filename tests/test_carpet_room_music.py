import unittest
from unittest.mock import Mock

from pop2.audio import AudioEngine
from tests.test_audio import TimedPlayback


class CarpetRoomMusicTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        self.scene.load_level(5)
        self.scene.peaceful = True
        audio = AudioEngine(playback=object())
        audio.playback = TimedPlayback(audio.cues)
        audio.playback.play = Mock(wraps=audio.playback.play)
        audio.configure_level(self.scene.level_map.level)
        self.scene.audio = self.audio = audio
        self.scene.jump_to_room(2, 0, 445, 1)

    def test_room_three_starts_its_own_theme_instead_of_random_cavern_music(self):
        self.assertEqual(self.audio.current_music, 114)
        self.assertTrue(self.audio.current_music_ambient)

    def test_playing_theme_is_not_restarted_by_subsequent_frames(self):
        self.audio.playback.play.reset_mock()
        for _ in range(10):
            self.scene.advance_audio()
        self.audio.playback.play.assert_not_called()

    def test_finished_theme_returns_to_cavern_ambient_without_replaying_rugroom(self):
        self.audio.playback.advance(40)
        self.audio.playback.play.reset_mock()
        for _ in range(10):
            self.scene.advance_audio()
        self.assertTrue(self.audio.music_busy)
        self.audio.playback.play.assert_called_once()
        cue = self.audio.playback.play.call_args.args[1]
        self.assertNotEqual(cue, 114)
        self.assertTrue(self.audio.current_music_ambient)
        group = self.audio.current_music_group
        bank = self.audio.manifest['ambient'][self.audio.level_music['bank']]
        self.assertIn(cue, range(bank['starts'][group], bank['starts'][group] + bank['counts'][group] + 1))

    def test_ambient_switch_does_not_rearm_the_used_room_entry_cue(self):
        self.audio.set_music_enabled(False)
        self.scene.advance_audio()
        self.assertFalse(self.audio.music_busy)
        self.audio.set_music_enabled(True)
        self.scene.advance_audio()
        self.assertTrue(self.audio.music_busy)
        self.assertNotEqual(self.audio.current_music, 114)

    def test_foreground_carpet_song_is_never_replaced_by_the_room_theme(self):
        self.audio.add_song(115)
        self.audio.flush()
        self.scene.advance_audio()
        self.assertEqual(self.audio.current_music, 115)
        self.assertFalse(self.audio.current_music_ambient)

    def test_entering_from_another_exploration_song_switches_to_rugroom(self):
        self.leave_room()
        self.audio.add_song(73, ambient=True)
        self.audio.flush()
        self.scene.game.place(2, 0, 445, 1)
        self.scene.advance_audio()
        self.assertEqual(self.audio.current_music, 114)

    def leave_room(self):
        # Do not warp/reset audio: exercise a normal room change at its audio phase.
        self.scene.game.place(3, 0, 445, 1)
        self.scene.advance_audio()

    def test_leaving_the_room_stops_its_theme_without_an_audio_reset(self):
        self.audio.playback.stop = Mock(wraps=self.audio.playback.stop)
        self.leave_room()
        self.assertFalse(self.audio.song_playing(114))
        self.audio.playback.stop.assert_called_with('music')

    def test_reentering_the_room_plays_the_theme_once_again(self):
        self.audio.playback.advance(40)
        self.leave_room()
        self.scene.game.place(2, 0, 445, 1)
        self.scene.advance_audio()
        self.assertTrue(self.audio.song_playing(114))

    def test_leaving_does_not_stop_the_carpet_travel_song(self):
        self.audio.add_song(115)
        self.audio.flush()
        self.leave_room()
        self.assertTrue(self.audio.song_playing(115))

    def test_foreground_event_completion_does_not_replay_the_room_theme(self):
        self.audio.add_song(24)
        self.audio.flush()
        self.audio.playback.advance(40)
        self.scene.advance_audio()
        self.assertFalse(self.audio.song_playing(114))

    def test_unused_theme_does_not_restart_after_the_carpet_is_underway(self):
        self.scene.game.caverns.carpet.counter = 1
        self.audio.reset()
        self.scene.advance_audio()
        self.assertFalse(self.audio.song_playing(114))


if __name__ == '__main__':
    unittest.main()
