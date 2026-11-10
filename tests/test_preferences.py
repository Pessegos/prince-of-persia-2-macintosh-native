"""Menu choices kept from one session to the next."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pop2.paths import ASSET_DIR
from pop2.preferences import Preferences, load_preferences, remember


class PreferencesTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'nested' / 'preferences.json'
        patcher = patch('pop2.preferences.PREFERENCES_PATH', self.path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, text):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(text, encoding='utf-8')

    def test_the_first_session_has_the_defaults(self):
        self.assertEqual(load_preferences(), Preferences())
        self.assertFalse(load_preferences().cave_ambience)

    def test_a_choice_is_there_in_the_next_session(self):
        remember(cave_ambience=True, copy_protection=False, fullscreen=True)
        self.assertEqual(load_preferences(), Preferences(cave_ambience=True,
                                                        copy_protection=False, fullscreen=True))
        remember(cave_ambience=False, fullscreen=False)
        self.assertEqual(load_preferences(), Preferences(copy_protection=False))

    def test_no_partial_file_is_left_behind(self):
        remember(cave_ambience=True)
        self.assertEqual([path.name for path in self.path.parent.iterdir()], ['preferences.json'])

    def test_a_damaged_file_means_the_defaults(self):
        for text in ('{"cave_ambience": tr', '[true]', '', '{"cave_ambience": "yes"}', '{"cave_ambience": 1}'):
            self.write(text)
            self.assertEqual(load_preferences(), Preferences(), text)

    def test_an_unknown_choice_from_another_version_is_ignored(self):
        self.write('{"cave_ambience": true, "from_the_future": 3}')
        self.assertEqual(load_preferences(), Preferences(cave_ambience=True))

    def test_old_preferences_keep_new_settings_at_their_defaults(self):
        self.write('{"cave_ambience": true, "copy_protection": "off", "fullscreen": 1}')
        self.assertEqual(load_preferences(), Preferences(cave_ambience=True))

    def test_a_disk_that_refuses_does_not_stop_the_game(self):
        with patch.object(Path, 'write_text', side_effect=OSError('read only')):
            remember(cave_ambience=True)
        self.assertFalse(load_preferences().cave_ambience)

    @unittest.skipUnless((ASSET_DIR / 'caverns_level4.json').is_file(), 'Imported resources required')
    def test_the_game_starts_with_the_choice_left_in_it(self):
        from tests.test_terrain import RooftopSceneTests

        for choice in (True, False):
            remember(cave_ambience=choice, copy_protection=not choice, fullscreen=choice)
            RooftopSceneTests.setUp(self)
            self.assertIs(self.scene.cave_ambience_enabled, choice)
            self.assertIs(self.scene.copy_protection_enabled, not choice)
            self.assertIs(self.scene.fullscreen, choice)
            if choice:
                self.assertEqual(self.scene.windowed_geometry, '1020x768')
                self.assertEqual(self.scene.windowed_state, 'normal')
                with patch.object(self.scene.root, 'geometry') as geometry:
                    self.scene.toggle_fullscreen()
                geometry.assert_called_once_with('1020x768')
            self.doCleanups()
            self.setUp()


if __name__ == '__main__':
    unittest.main()
