import base64
from io import BytesIO
import json
import os
from pathlib import Path
import random
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from pop2.game_session import GameSession
from pop2.rebirth import RebirthSnapshot
from pop2.save_game import (SaveGameError, capture, decode_preview, encode_preview,
                           read_save, write_save)
from pop2.save_slots import SaveBrowser, SaveSlot, list_slots
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
                             ('copy_verified', 1), ('preview', 'invalid base64'),
                             ('name', ''), ('name', 'x' * 49), ('name', 'bad\nname'),
                             ('preview_at_resume', 'yes')):
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
        self.assertEqual(preview.size, (510, 365))
        self.assertEqual(preview.getcolors(), [(510 * 365, (255, 0, 0))])

    def test_preview_preserves_every_original_scene_pixel_and_legacy_previews_still_load(self):
        frame = Image.frombytes('RGB', (512, 384), random.Random(17).randbytes(512 * 384 * 3))
        expected = frame.crop((1, 0, 511, 365))
        preview = decode_preview(encode_preview(frame))
        self.assertEqual(preview.tobytes(), expected.tobytes())
        legacy = expected.resize((224, 160), Image.Resampling.NEAREST)
        output = BytesIO()
        legacy.save(output, format='PNG')
        decoded = decode_preview(base64.b64encode(output.getvalue()).decode('ascii'))
        self.assertEqual(decoded.size, (224, 160))
        self.assertEqual(decoded.tobytes(), legacy.tobytes())

    def test_preview_decoder_rejects_unbounded_or_unexpected_image_dimensions(self):
        for size in ((510, 384), (1020, 730), (223, 160), (0x1000, 1)):
            with self.subTest(size=size):
                output = BytesIO()
                Image.new('RGB', size).save(output, format='PNG')
                with self.assertRaises(SaveGameError):
                    decode_preview(base64.b64encode(output.getvalue()).decode('ascii'))
        with self.assertRaises(SaveGameError):
            decode_preview('A' * (1024 * 1024 + 1))


class SaveBrowserTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.folder = Path(self.directory.name)
        self.slots = list_slots(self.folder)

    def test_empty_directory_has_no_placeholder_slots_and_one_new_save_action(self):
        self.assertEqual(self.slots, ())
        self.assertEqual(len(SaveBrowser(self.slots, 'save').items), 0)
        self.assertEqual(SaveBrowser(self.slots, 'save').hit(350, 340), 29)
        self.assertFalse(SaveBrowser(self.slots).primary_enabled)
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_selection_is_not_an_accidental_load_and_keyboard_scrolls_without_pages(self):
        slots = tuple(SaveSlot(self.folder / str(i), f'Journey {i}', True) for i in range(20))
        menu = SaveBrowser(slots)
        rect = menu.row_rect(2)
        self.assertEqual(menu.click(rect[0] + 2, rect[1] + 2), 'changed')
        self.assertEqual(menu.selected, 2)
        self.assertEqual(menu.key('Return'), 'changed')
        self.assertEqual(menu.confirmation, 'load')
        menu.key('Escape')
        menu.selected = 0
        menu.key('Up')
        self.assertEqual(menu.selected, 0)
        menu.key('Next')
        self.assertEqual(menu.selected, 5)
        self.assertGreater(menu.scroll_target, 0)
        self.assertEqual(menu.scroll, 0)
        menu.animate(1 / 60)
        self.assertGreater(menu.scroll, 0)
        self.assertLess(menu.scroll, menu.scroll_target)

    def test_load_empty_disabled_and_overwrite_delete_load_require_confirmation(self):
        menu = SaveBrowser(self.slots)
        self.assertFalse(menu.primary_enabled)
        self.assertEqual(menu.key('Return'), 'changed')
        path = self.folder / 'slot-01.pop2save'
        path.write_text(json.dumps({'format': 'pop2-macintosh-native-save', 'version': 2, 'level': 3,
                                   'resume': {'checkpoint': None, 'max_life': 4}}))
        menu.slots = list_slots(self.folder)
        for action in ('load', 'save', 'delete'):
            menu.mode = 'save' if action == 'save' else 'load'
            menu.selected = 0
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
        (self.folder / 'broken.pop2save').write_text('corrupt')
        slots = list_slots(self.folder)
        self.assertEqual(len(slots), 2)
        self.assertTrue(any(slot.resume == 'Legacy save' for slot in slots))
        broken = next(i for i, slot in enumerate(slots) if slot.error)
        menu = SaveBrowser(slots)
        menu.selected = broken
        self.assertFalse(menu.primary_enabled)
        menu.key('Delete')
        self.assertEqual(menu.confirmation, 'delete')

    def test_hover_never_changes_selected_slot_or_performs_file_io(self):
        menu = SaveBrowser(tuple(SaveSlot(self.folder / str(i), str(i), True) for i in range(8)))
        rect = menu.row_rect(4)
        with patch('pop2.save_slots.read_document', side_effect=AssertionError('hover IO')):
            self.assertTrue(menu.hover(rect[0] + 2, rect[1] + 2))
        self.assertEqual(menu.selected, 0)
        self.assertEqual(menu.focus, 104)

    def test_load_tab_selects_most_recent_valid_save_when_current_slot_is_empty(self):
        document = {'format': 'pop2-macintosh-native-save', 'version': 2, 'level': 3,
                    'resume': {'checkpoint': None, 'max_life': 3}}
        for index, modified in ((0, 1000), (1, 2000)):
            path = self.folder / f'save-{index}.pop2save'
            path.write_text(json.dumps(document))
            os.utime(path, (modified, modified))
        menu = SaveBrowser(list_slots(self.folder), 'save', selected=2)
        menu.switch('load')
        self.assertEqual(menu.selected, 0)
        self.assertEqual(menu.entry.path.name, 'save-1.pop2save')

    def test_new_save_requires_a_name_and_cancel_never_creates_files(self):
        menu = SaveBrowser((), 'save')
        menu.key('Return')
        self.assertEqual(menu.editing, 'create')
        menu.key('a', control=True)
        menu.key('x', char='Adventure')
        self.assertEqual(menu.draft, 'Adventure')
        menu.key('Left')
        menu.key('BackSpace')
        self.assertEqual(menu.draft, 'Adventue')
        menu.key('a', control=True)
        menu.key('x', char='  ')
        self.assertEqual(menu.key('Return'), 'changed')
        menu.key('Escape')
        self.assertIsNone(menu.editing)
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_new_save_action_opens_name_editor_on_single_click(self):
        menu = SaveBrowser((), 'save')
        left, top, _right, _bottom = menu.FOOTER[3]
        menu.click(left + 3, top + 3)
        self.assertEqual(menu.editing, 'create')

    def test_cancel_button_keeps_its_meaning_with_enter_and_space(self):
        for key in ('Return', 'space'):
            with self.subTest(key=key):
                menu = SaveBrowser((), 'save')
                menu.edit_name('create')
                menu.key('Tab')
                self.assertEqual(menu.focus, 30)
                self.assertEqual(menu.key(key), 'changed')
                self.assertIsNone(menu.editing)

    def test_name_input_limits_length_and_hover_does_not_steal_keyboard_focus(self):
        menu = SaveBrowser((), 'save')
        menu.edit_name('create')
        menu.key('x', char='A' * 100)
        self.assertEqual(len(menu.draft), 48)
        menu.hover(300, 230)
        self.assertEqual(menu.focus, 32)
        menu.key('a', control=True)
        menu.key('x', char='My\njourney\t')
        self.assertEqual(menu.draft, 'Myjourney')
        self.assertEqual(menu.key('Return'), 'slot_create')

    def test_wheel_is_smooth_bounded_and_does_not_select_or_write_saves(self):
        menu = SaveBrowser(tuple(SaveSlot(self.folder / str(i), str(i), True) for i in range(30)))
        self.assertTrue(menu.wheel(3))
        self.assertEqual(menu.selected, 0)
        self.assertEqual(menu.scroll, 0)
        for _ in range(120):
            menu.animate(1 / 60)
        self.assertEqual(menu.scroll, menu.scroll_target)
        menu.wheel(10000)
        self.assertEqual(menu.scroll_target, menu.max_scroll)
        menu.wheel(-10000)
        self.assertEqual(menu.scroll_target, 0)
        menu.edit_name('rename')
        self.assertFalse(menu.wheel(1))

    def test_scroll_motion_is_frame_rate_independent_and_starts_gently(self):
        entries = tuple(SaveSlot(self.folder / str(i), str(i), True) for i in range(30))
        slow, fast = SaveBrowser(entries), SaveBrowser(entries)
        slow.wheel(3)
        fast.wheel(3)
        slow.animate(1 / 60)
        self.assertLess(slow.scroll, slow.scroll_target * 0.1)
        for _ in range(29):
            slow.animate(1 / 60)
        for _ in range(120):
            fast.animate(1 / 240)
        self.assertAlmostEqual(slow.scroll, fast.scroll, places=8)
        self.assertAlmostEqual(slow.scroll_velocity, fast.scroll_velocity, places=8)

    def test_preview_and_font_work_are_cached_across_dialog_typing(self):
        font = SimpleNamespace(glyphs=dict.fromkeys(range(128)), text=Mock(side_effect=lambda value, color:
            Image.new('RGBA', (max(1, len(value)) * 7, 11), color)))
        provider = Mock(return_value=Image.new('RGB', (510, 365), 'blue'))
        current = SaveSlot(self.folder, 'Current', document={'test': True})
        browser = SaveBrowser((), 'save', current=current, preview_provider=provider)
        source = Image.new('RGBA', (1536, 1152), '#0d1117')
        browser.draw(source, font, background_key=1)
        provider.assert_called_once()
        calls = font.text.call_count
        browser.draw(source, font, background_key=1)
        self.assertEqual(font.text.call_count, calls)
        browser.edit_name('create')
        browser.draw(source, font, background_key=1)
        browser.edit_text('x', 'Another name')
        browser.draw(source, font, background_key=1)
        provider.assert_called_once()
        self.assertEqual(len(browser.modal_cache), 1)
        self.assertLessEqual(len(browser.text_cache), 256)

    def test_old_instant_resume_preview_is_not_trusted_after_entry_preview_update(self):
        path = self.folder / 'old.pop2save'
        path.write_text(json.dumps({'format': 'pop2-macintosh-native-save', 'version': 2,
            'level': 3, 'preview_at_resume': True, 'preview': encode_preview(Image.new('RGB', (512, 384), 'red')),
            'resume': {'checkpoint': None, 'max_life': 3}}))
        self.assertIsNone(list_slots(self.folder)[0].preview)

    def test_cached_scroll_frames_match_full_redraws_at_multiple_sizes(self):
        font = SimpleNamespace(glyphs=dict.fromkeys(range(128)), text=lambda value, color:
            Image.new('RGBA', (max(1, len(value)) * 7, 11), color))
        entries = tuple(SaveSlot(self.folder / str(i), f'Save {i}', True, level=i % 3 + 1,
                                date='20 Oct 2026  12:00') for i in range(20))
        browser = SaveBrowser(entries)
        for size in ((512, 384), (1434, 1080)):
            source = Image.new('RGBA', size, '#0d1117')
            browser.draw(source, font)
            for scroll in (17.3, 114.5, browser.max_scroll, 0):
                with self.subTest(size=size, scroll=scroll):
                    browser.scroll = scroll
                    cached = browser.draw(source, font)
                    browser.list_base_cache.clear()
                    full = browser.draw(source, font)
                    self.assertEqual(cached.tobytes(), full.tobytes())

    def test_clear_actions_current_marker_and_complete_wrapped_name(self):
        words = []
        def glyphs(value, color):
            words.append(value)
            return Image.new('RGBA', (max(1, len(value)) * 10, 11), color)

        font = SimpleNamespace(glyphs=dict.fromkeys(range(128)), text=glyphs)
        name = 'Beyond the gate and into the lower caverns'
        slot = SaveSlot(self.folder / 'journey.pop2save', name, True, level=3,
                        resume='Checkpoint', date='20 Oct 2026  12:00')
        browser = SaveBrowser((slot,), 'save', active_path=slot.path)
        source = Image.new('RGBA', (512, 384), '#0d1117')
        marked = browser.draw(source, font)
        self.assertIn('Overwrite', words)
        self.assertIn('New save', words)
        self.assertNotIn('Save game', words)
        self.assertIn('Current', words)
        self.assertIn('Resumes at checkpoint', words)
        self.assertIn('Beyond the gate and', words)
        self.assertIn('into the lower caverns', words)
        browser.active_path = None
        unmarked = browser.draw(source, font)
        browser.list_base_cache.clear()
        full = browser.draw(source, font)
        self.assertEqual(unmarked.tobytes(), full.tobytes())
        self.assertNotEqual(marked.tobytes(), unmarked.tobytes())

    def test_names_come_from_metadata_and_do_not_change_file_paths(self):
        path = self.folder / 'slot-01.pop2save'
        path.write_text(json.dumps({'format': 'pop2-macintosh-native-save', 'version': 2,
            'level': 3, 'name': 'Caverns - second try', 'resume': {'checkpoint': None, 'max_life': 3}}))
        slot, = list_slots(self.folder)
        self.assertEqual(slot.name, 'Caverns - second try')
        self.assertEqual(slot.path, path)
        self.assertIsNone(slot.preview)

    def test_browser_renders_source_pixels_and_controls_directly_at_output_resolution(self):
        def glyphs(value, color):
            image = Image.new('RGBA', (len(value) * 7, 11))
            for x in range(0, image.width, 2):
                image.paste(color, (x, 0, x + 1, 11))
            return image

        font = SimpleNamespace(glyphs=dict.fromkeys(range(128)), text=glyphs)
        preview = Image.frombytes('RGB', (510, 365), random.Random(31).randbytes(510 * 365 * 3))
        current = SaveSlot(self.folder / 'new.pop2save', 'New save', level=1, resume='Level start', preview=preview)
        browser = SaveBrowser(self.slots, 'save', current=current)
        for visible, size in ((False, (512, 384)), (False, (1536, 1152)),
                              (True, (1434, 1080)), (True, (1020, 768))):
            with self.subTest(visible=visible, size=size):
                source = Image.new('RGBA', size, '#0d1117')
                before = source.tobytes()
                frame = browser.draw(source, font, visible=visible)
                self.assertEqual(source.tobytes(), before)
                sx, sy = size[0] / (510 if visible else 512), size[1] / 384
                left, top, right, bottom = browser.PREVIEW
                rect = (round((left + 1 - visible) * sx), round((top + 1) * sy),
                        round((right - 1 - visible) * sx), round((bottom - 1) * sy))
                expected = preview.resize((rect[2] - rect[0], rect[3] - rect[1]), Image.Resampling.NEAREST)
                self.assertEqual(frame.crop(rect).convert('RGB').tobytes(), expected.tobytes())
                self.assertEqual(frame.getpixel((round((28 - visible) * sx), round(16 * sy))),
                                 (133, 133, 133, 255))
                browser.confirmation = 'save'
                confirmed = browser.draw(source, font, visible=visible)
                self.assertEqual(confirmed.getpixel((round((80 - visible) * sx), round(121 * sy))),
                                 (133, 133, 133, 255))
                browser.confirmation = None


if __name__ == '__main__':
    unittest.main()
