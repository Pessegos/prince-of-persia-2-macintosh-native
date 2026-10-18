import json
import os
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from pop2.game_session import GameSession
from pop2.rebirth import RebirthSnapshot
from pop2.save_game import (SaveGameError, capture, decode_preview, encode_preview,
                           read_save, write_save)
from pop2.save_slots import SaveBrowser, list_slots
from tests.test_game_session import EmptyEncounter, resources


class SaveEncounter(EmptyEncounter):
    def reset(self):
        super().reset()
        self.player.alive = True
        self.player.runtime = self.runtime


class ProgressSaveTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'slot-01.pop2save'
        self.resources = resources()
        native_load = GameSession.load

        def load(source, number):
            return native_load(source, number, encounter_factory=SaveEncounter)

        self.load = load
        mocked = patch('pop2.save_game.GameSession.load', side_effect=load)
        mocked.start()
        self.addCleanup(mocked.stop)

    def test_progress_restarts_level_with_full_entry_life_and_fresh_motion(self):
        game = self.load(self.resources, 1)
        game.place(18, 2, 450, 0)
        game.runtime.state.current_y = -60
        game.combat.player.max_life, game.combat.player.life = 5, 1
        value = capture(game, {'run_active': True}, True)
        self.assertNotIn('state', value)
        self.assertNotIn('controls', value)
        write_save(self.path, value)
        before = random.getstate()
        restored, metadata = read_save(self.path, self.resources)
        self.assertEqual(random.getstate(), before)
        self.assertEqual(restored.room_id, restored.level.start_room)
        entry = self.load(self.resources, 1).runtime.state
        self.assertEqual(restored.runtime.state.target_x, entry.target_x)
        self.assertEqual((restored.combat.player.life, restored.combat.player.max_life), (5, 5))
        self.assertEqual(restored.runtime.state.current_y, entry.current_y)
        self.assertIs(restored.runtime, restored.combat.player.runtime)
        self.assertTrue(metadata['copy_verified'])

    def test_checkpoint_is_reanchored_and_repeated_retry_snapshot_stays_independent(self):
        game = self.load(self.resources, 1)
        point = game.level.checkpoints[0]
        game.checkpoint = RebirthSnapshot.capture(point, game.combat)
        game.combat.player.max_life = 6
        game.place(21, 2, 480, 0, preserve_checkpoint=True)
        write_save(self.path, capture(game))
        restored, _ = read_save(self.path, self.resources)
        self.assertEqual((restored.room_id, restored.motion.row, restored.runtime.state.target_x),
                         (point.room, point.row, point.x))
        self.assertEqual(restored.combat.player.max_life, 3)
        self.assertEqual(restored.checkpoint.checkpoint, point)
        self.assertIsNot(restored.checkpoint.room_encounters, restored.combat.room_encounters)

    def test_no_checkpoint_level_always_uses_its_entry(self):
        game = self.load(self.resources, 2)
        game.place(18, 1, 480, 1)
        write_save(self.path, capture(game))
        restored, _ = read_save(self.path, self.resources)
        self.assertIsNone(restored.checkpoint)
        self.assertEqual(restored.room_id, restored.level.start_room)

    def test_wrong_originals_invalid_checkpoint_and_progress_are_rejected(self):
        original = capture(self.load(self.resources, 1))
        for field, value in (('level_sha256', 'wrong'), ('version', 999),
                             ('resume', {'checkpoint': 4, 'max_life': 3}),
                             ('resume', {'checkpoint': None, 'max_life': True}),
                             ('copy_verified', 1), ('preview', 'invalid base64')):
            with self.subTest(field=field, value=value):
                data = dict(original, **{field: value})
                write_save(self.path, data)
                before = random.getstate()
                with self.assertRaises(SaveGameError):
                    read_save(self.path, self.resources)
                self.assertEqual(random.getstate(), before)

    def test_thumbnail_has_bounded_dimensions_and_does_not_contain_hud(self):
        frame = Image.new('RGBA', (512, 384), 'red')
        frame.paste('blue', (1, 365, 511, 384))
        preview = decode_preview(encode_preview(frame))
        self.assertEqual(preview.size, (224, 160))
        self.assertEqual(preview.getcolors(), [(224 * 160, (255, 0, 0))])


class SaveBrowserTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.folder = Path(self.directory.name)
        self.slots = list_slots(self.folder)

    def test_empty_directory_has_twelve_slots_without_creating_files(self):
        self.assertEqual(len(self.slots), 12)
        self.assertTrue(all(not slot.exists for slot in self.slots))
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_slot_selection_is_not_an_accidental_save_and_navigation_wraps(self):
        menu = SaveBrowser(self.slots, 'save')
        rect = menu.row_rect(2)
        self.assertEqual(menu.click(rect[0] + 2, rect[1] + 2), 'changed')
        self.assertEqual(menu.selected, 2)
        self.assertEqual(menu.key('Return'), 'slot_save')
        menu.selected = 0
        menu.key('Up')
        self.assertEqual((menu.selected, menu.page), (11, 1))
        menu.key('Right')
        self.assertEqual((menu.selected, menu.page), (0, 0))

    def test_load_empty_disabled_and_overwrite_delete_load_require_confirmation(self):
        menu = SaveBrowser(self.slots)
        self.assertFalse(menu.primary_enabled)
        self.assertEqual(menu.key('Return'), 'changed')
        path = self.slots[0].path
        path.write_text(json.dumps({'format': 'pop2-macintosh-native-save', 'version': 2, 'level': 3,
                                   'resume': {'checkpoint': None, 'max_life': 4}}))
        menu.slots = list_slots(self.folder)
        for action in ('load', 'save', 'delete'):
            menu.mode = 'save' if action == 'save' else 'load'
            menu.focus = 26 if action == 'delete' else 27
            self.assertEqual(menu.activate(), 'changed')
            self.assertEqual(menu.confirmation, action)
            self.assertEqual(menu.focus, 30)
            self.assertEqual(menu.key('Return'), 'changed')
            self.assertIsNone(menu.confirmation)
            menu.focus = 26 if action == 'delete' else 27
            menu.activate()
            menu.key('Right')
            self.assertEqual(menu.key('Return'), 'slot_' + action)
            menu.key('Escape')

    def test_legacy_files_and_corrupt_files_remain_visible_and_can_be_deleted(self):
        (self.folder / 'my old save.pop2save').write_text(json.dumps({
            'format': 'pop2-macintosh-native-save', 'version': 1, 'level': 1}))
        self.slots[0].path.write_text('corrupt')
        slots = list_slots(self.folder)
        self.assertEqual(len(slots), 13)
        self.assertEqual(slots[-1].resume, 'Legacy save')
        self.assertTrue(slots[0].error)
        menu = SaveBrowser(slots)
        self.assertFalse(menu.primary_enabled)
        menu.key('Delete')
        self.assertEqual(menu.confirmation, 'delete')

    def test_hover_never_changes_selected_slot_or_performs_file_io(self):
        menu = SaveBrowser(self.slots)
        rect = menu.row_rect(4)
        with patch('pop2.save_slots.read_document', side_effect=AssertionError('hover IO')):
            self.assertTrue(menu.hover(rect[0] + 2, rect[1] + 2))
        self.assertEqual(menu.selected, 0)
        self.assertEqual(menu.focus, 14)

    def test_load_tab_selects_most_recent_valid_save_when_current_slot_is_empty(self):
        document = {'format': 'pop2-macintosh-native-save', 'version': 2, 'level': 3,
                    'resume': {'checkpoint': None, 'max_life': 3}}
        for index, modified in ((0, 1000), (1, 2000)):
            path = self.slots[index].path
            path.write_text(json.dumps(document))
            os.utime(path, (modified, modified))
        menu = SaveBrowser(list_slots(self.folder), 'save', selected=2)
        menu.switch('load')
        self.assertEqual(menu.selected, 1)


if __name__ == '__main__':
    unittest.main()
