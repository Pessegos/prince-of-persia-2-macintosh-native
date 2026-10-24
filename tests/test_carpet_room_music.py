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

    def test_finished_theme_can_repeat_without_picking_an_unrelated_ambient(self):
        self.audio.playback.advance(40)
        self.scene.advance_audio()
        self.assertEqual(self.audio.current_music, 114)
        self.assertTrue(self.audio.song_playing(114))

    def test_ambient_switch_stops_theme_and_reenabling_it_resumes_room_theme(self):
        self.audio.set_music_enabled(False)
        self.scene.advance_audio()
        self.assertFalse(self.audio.music_busy)
        self.audio.set_music_enabled(True)
        self.scene.advance_audio()
        self.assertTrue(self.audio.song_playing(114))

    def test_foreground_carpet_song_is_never_replaced_by_the_room_theme(self):
        self.audio.add_song(115)
        self.audio.flush()
        self.scene.advance_audio()
        self.assertEqual(self.audio.current_music, 115)
        self.assertFalse(self.audio.current_music_ambient)

    def test_entering_from_another_exploration_song_switches_to_rugroom(self):
        self.audio.add_song(73, ambient=True)
        self.audio.flush()
        self.scene.advance_audio()
        self.assertEqual(self.audio.current_music, 114)

    def test_unused_theme_does_not_restart_after_the_carpet_is_underway(self):
        self.scene.game.caverns.carpet.counter = 1
        self.audio.reset()
        self.scene.advance_audio()
        self.assertFalse(self.audio.music_busy)


if __name__ == '__main__':
    unittest.main()
