"""Level 14's room themes (9:1a90, 9:1d84 and FinlWatchOpps 9:0654)."""

import unittest
from unittest.mock import Mock

from pop2.final_music import CHESS, CRYSTAL, ESCHER, SPIDER, entry_song, watch_song
from pop2.paths import ASSET_DIR


def counts(**rooms):
    return lambda room: rooms.get(f'r{room}', 0)


class RoomThemeTests(unittest.TestCase):
    def test_enter_hooks(self):
        idle = lambda _cue: False
        self.assertEqual([entry_song(room, False, idle, counts()) for room in range(9)],
                         [None, None, SPIDER, CHESS, None, CRYSTAL, None, None, None])
        # Native room 7 needs a5-0x4ff2; native room 8 an opponent and no
        # Escher already playing.
        self.assertEqual(entry_song(6, True, idle, counts()), ESCHER)
        self.assertEqual(entry_song(7, False, idle, counts(r7=1)), ESCHER)
        self.assertIsNone(entry_song(7, False, lambda cue: cue == ESCHER, counts(r7=1)))

    def test_watch_song_and_the_escher_flag(self):
        self.assertEqual([watch_song(room, False, counts(r5=4))[0] for room in range(9)],
                         [None, None, SPIDER, CHESS, CHESS, CRYSTAL, None, ESCHER, None])
        self.assertEqual(watch_song(7, False, counts()), (ESCHER, True, None))
        self.assertEqual(watch_song(6, True, counts()), (ESCHER, True, None))
        # The old reading (room 7 sets the flag, room 8 needs it) is rejected.
        self.assertEqual(watch_song(6, False, counts()), (None, False, None))
        self.assertEqual(watch_song(5, False, counts()), (None, False, CRYSTAL))


INSTALLED = all((ASSET_DIR / name).is_file() for name in ('Final.rsrc', 'final_level14.json'))


@unittest.skipUnless(INSTALLED, 'Imported Macintosh final level required')
class LevelFourteenMusicTests(unittest.TestCase):
    def setUp(self):
        from pop2.environments import environment_for
        from tools.audit_temple_routes import Harness

        self.harness = Harness(14)
        self.scene = self.harness.scene
        self.environment = environment_for(self.scene)
        self.audio = Mock(music_enabled=True, music_busy=False)
        self.audio.song_playing.return_value = False

    def tearDown(self):
        self.harness.close()

    def visit(self, room, row=2, x=200):
        self.scene.jump_to_room(room, row=row, x=x, facing=0)
        self.audio.add_song.reset_mock()
        self.environment.ambient_audio(self.audio, self.scene.terrain_motion)
        return [call.args[0] for call in self.audio.add_song.call_args_list]

    def test_the_mental_rooms_ask_for_their_themes(self):
        self.assertEqual(self.visit(2, x=450), [SPIDER, SPIDER])
        self.assertEqual(self.visit(3), [CHESS, CHESS])
        self.assertEqual(self.visit(4), [CHESS])
        # Room 6's four false Princes keep Crystal going.
        self.assertEqual(self.visit(5, x=100), [CRYSTAL, CRYSTAL])
        self.assertEqual(self.visit(6, x=100), [])
        self.assertEqual(self.visit(7, row=1, x=300), [ESCHER])
        self.assertTrue(self.scene.game.caverns.final_escher)
        self.assertEqual(self.visit(6, x=100), [ESCHER, ESCHER])
        self.assertTrue(all(call.kwargs == {'ambient': True}
                            for call in self.audio.add_song.call_args_list))

    def test_no_new_theme_while_a_song_plays_or_with_music_off(self):
        self.scene.jump_to_room(2, row=2, x=450, facing=0)
        self.audio.music_busy = True
        self.environment.ambient_audio(self.audio, self.scene.terrain_motion)
        self.environment.ambient_audio(self.audio, self.scene.terrain_motion)
        # Only the enter hook's request.
        self.assertEqual([call.args[0] for call in self.audio.add_song.call_args_list], [SPIDER])
        self.audio.add_song.reset_mock()
        self.audio.music_busy, self.audio.music_enabled = False, False
        self.environment.ambient_audio(self.audio, self.scene.terrain_motion)
        self.audio.add_song.assert_not_called()

    def test_the_themes_are_imported(self):
        from pop2.audio import AudioEngine
        from pop2.music_cues import FINAL_SONGS

        audio = AudioEngine(playback=Mock())
        missing = [cue for cue in FINAL_SONGS if not audio.available(cue)]
        if missing:
            self.skipTest(f'this import predates the final level songs {missing}')
        self.assertTrue(all((ASSET_DIR / 'audio' / audio.cues[cue]['file']).is_file()
                            for cue in FINAL_SONGS))


if __name__ == '__main__':
    unittest.main()
