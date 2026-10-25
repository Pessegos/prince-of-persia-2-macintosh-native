import unittest
from unittest.mock import call

from tests import test_audio


class DebrisAudioTests(unittest.TestCase):
    def setUp(self):
        test_audio.CueTests.setUp(self)
        self.audio.mix_effects = True
        self.playback.playing_effects.return_value = ()
        for cue, priority in ((26, 8), (29, 40), (65, 22), (66, 20)):
            self.audio.cues[cue] = {'mode': 1, 'priority': priority, 'file': f'{cue}.wav'}

    def test_same_impact_keeps_debris_without_layering_shooter_launch(self):
        for cues in ((26, 65), (65, 26)):
            with self.subTest(cues=cues):
                self.playback.reset_mock()
                for cue in cues:
                    self.audio.add_sound(cue)
                self.audio.flush()
                self.playback.play_effect.assert_called_once_with(26)

    def test_other_simultaneous_effects_and_shared_door_channel_are_preserved(self):
        for cue in (26, 65, 29, 66, 17, 61, 294):
            self.audio.add_sound(cue)
        self.audio.flush()
        self.assertEqual(self.playback.play_effect.call_args_list,
                         [call(cue) for cue in (26, 29, 66, 61, 294)])
        self.playback.play.assert_called_once_with('mechanism', 17)

    def test_ordinary_shooter_launch_still_plays(self):
        self.audio.add_sound(65)
        self.audio.flush()
        self.playback.play_effect.assert_called_once_with(65)

    def test_separate_already_playing_launch_is_not_interrupted(self):
        self.playback.playing_effects.return_value = (65,)
        self.audio.add_sound(26)
        self.audio.flush()
        self.playback.play_effect.assert_called_once_with(26)
        self.playback.stop_effect.assert_not_called()


if __name__ == '__main__':
    unittest.main()
