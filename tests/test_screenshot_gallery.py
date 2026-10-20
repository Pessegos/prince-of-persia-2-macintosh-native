from pathlib import Path
from tempfile import TemporaryDirectory
from threading import get_ident
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

from pop2.screenshot_gallery import GalleryReads, ScreenshotGallery, read_capture, scan_captures
from pop2.screenshots import ScreenshotSettings


class ScreenshotGalleryTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.folder = Path(directory.name)
        self.galleries = []

    def gallery(self, folder=None):
        gallery = ScreenshotGallery(folder or self.folder)
        self.galleries.append(gallery)
        self.addCleanup(gallery.close)
        self.drain(gallery)
        return gallery

    def drain(self, gallery):
        deadline = time.monotonic() + 5
        while gallery.reads.pending:
            gallery.poll()
            if time.monotonic() >= deadline:
                self.fail('Gallery reads did not finish')
            time.sleep(0.001)
        gallery.poll()

    def png(self, name='capture.png', color='red', size=(510, 384)):
        path = self.folder / name
        Image.new('RGB', size, color).save(path)
        return path

    @staticmethod
    def font():
        return SimpleNamespace(glyphs=dict.fromkeys(range(256)),
            text=lambda value, color='#eeeeee': Image.new('RGBA', (max(1, len(value)) * 8, 12), color))

    def test_scanning_is_newest_first_png_only_and_never_creates_a_folder(self):
        first = self.png('one.png')
        second = self.png('two.PNG')
        (self.folder / 'ignore.txt').write_text('Not a PNG')
        entries = scan_captures(self.folder)
        self.assertEqual({entry.path for entry in entries}, {first, second})
        self.assertEqual([entry.modified for entry in entries], sorted((item.modified for item in entries), reverse=True))
        missing = self.folder / 'missing'
        gallery = self.gallery(missing)
        self.assertEqual(gallery.entries, ())
        self.assertFalse(missing.exists())

    def test_reading_png_preserves_pixels_and_rejects_corrupt_or_oversized_files(self):
        path = self.png()
        entry, = scan_captures(self.folder)
        image, size = read_capture(entry)
        self.assertEqual(size, (510, 384))
        self.assertEqual(image.getpixel((100, 100)), (255, 0, 0))
        path.write_text('broken')
        with self.assertRaises(OSError):
            read_capture(entry)

    def test_worker_runs_off_main_thread_and_close_does_not_wait_for_tk(self):
        reads = GalleryReads()
        self.addCleanup(reads.close)
        key = ('test', 1)
        reads.request(key, get_ident)
        deadline = time.monotonic() + 5
        while key not in reads.cache and time.monotonic() < deadline:
            reads.poll()
            time.sleep(0.001)
        self.assertNotEqual(reads.cache[key].value, get_ident())
        reads.close()
        self.assertIsNone(reads.request(('test', 2), lambda: self.fail('Closed worker ran a task')))

    def test_hover_has_no_filesystem_reads_and_drawing_reuses_decoded_images(self):
        self.png()
        gallery = self.gallery()
        source, font = Image.new('RGBA', (512, 384), 'blue'), self.font()
        with patch('pop2.screenshot_gallery.read_capture', wraps=read_capture) as decode:
            gallery.draw(source, font)
            self.drain(gallery)
            ready = gallery.draw(source, font)
            self.assertEqual(decode.call_count, 1)
            with patch('pop2.screenshot_gallery.os.scandir', side_effect=AssertionError('Hover read disk')):
                for index in range(20):
                    gallery.hover(90, 55)
                    gallery.hover(130, 350)
                    gallery.draw(source, font)
            self.assertEqual(decode.call_count, 1)
        self.assertEqual(ready.size, source.size)
        self.assertEqual(source.getpixel((0, 0)), (0, 0, 255, 255))

    def test_gallery_navigation_scroll_is_smooth_and_does_not_delete_on_selection(self):
        for i in range(12):
            self.png(f'{i}.png', size=(20, 20))
        gallery = self.gallery()
        gallery.key('Next')
        self.assertEqual(gallery.selected, 3)
        self.assertEqual(gallery.scroll, 0)
        gallery.animate(1 / 60)
        self.assertGreater(gallery.scroll, 0)
        self.assertLess(gallery.scroll, gallery.scroll_target)
        for _ in range(120):
            gallery.animate(1 / 60)
        self.assertAlmostEqual(gallery.scroll, gallery.scroll_target)
        self.assertEqual(len(list(self.folder.glob('*.png'))), 12)
        gallery.key('Delete')
        self.assertTrue(gallery.deleting)
        self.assertEqual(gallery.focus, 60)
        gallery.key('Return')
        self.assertFalse(gallery.deleting)
        self.assertEqual(len(list(self.folder.glob('*.png'))), 12)

    def test_delete_requires_confirmation_and_refuses_a_changed_file(self):
        path = self.png()
        gallery = self.gallery()
        gallery.key('Delete')
        gallery.key('Right')
        self.assertEqual(gallery.key('Return'), 'gallery_delete')
        path.write_text('Changed after the library opened')
        gallery.delete_capture()
        self.drain(gallery)
        self.assertTrue(path.exists())
        self.assertIn('Could not delete', gallery.error)
        gallery.key('Delete')
        gallery.delete_capture()
        self.drain(gallery)
        self.assertFalse(path.exists())

    def test_folder_picker_cancel_never_changes_destination_or_creates_paths(self):
        gallery = self.gallery()
        gallery.choose_folder()
        gallery.draft = str(self.folder / 'new' / 'nested')
        gallery.key('Escape')
        self.assertEqual(gallery.folder, self.folder)
        self.assertFalse(gallery.choosing)
        self.assertFalse((self.folder / 'new').exists())

    def test_confirmation_keeps_its_target_if_a_new_capture_arrives(self):
        original = self.png('original.png')
        gallery = self.gallery()
        gallery.key('Delete')
        new = self.png('new.png', color='blue')
        gallery.refresh(new)
        self.drain(gallery)
        self.assertEqual(gallery.entry.path, new)
        self.assertEqual(gallery.delete_target.path, original)
        gallery.delete_capture()
        self.drain(gallery)
        self.assertFalse(original.exists())
        self.assertTrue(new.exists())

    def test_thumbnail_queue_cannot_block_folder_or_delete_commands(self):
        reads = GalleryReads()
        self.addCleanup(reads.close)
        reads.thread = object()
        reads.pending.update(('image', i) for i in range(12))
        reads.request(('image', 13), lambda: None)
        self.assertNotIn(('image', 13), reads.pending)
        reads.request(('commit', 1), lambda: None, -20)
        self.assertIn(('commit', 1), reads.pending)

    def test_folder_scrollbar_never_navigates_or_scrolls_on_hover(self):
        for i in range(20):
            (self.folder / f'Folder {i:02}').mkdir()
        gallery = self.gallery()
        gallery.choose_folder()
        self.drain(gallery)
        gallery.hover(445, 275)
        self.assertEqual(gallery.folder_offset, 0)
        gallery.click(445, 275)
        self.assertGreater(gallery.folder_offset, 0)
        self.assertEqual(gallery.browsing, self.folder)
        gallery.wheel(-100)
        self.assertEqual(gallery.folder_offset, 0)

    def test_modal_cache_matches_fresh_draw_after_path_edits_and_folder_updates(self):
        self.png()
        gallery = self.gallery()
        gallery.choose_folder()
        self.drain(gallery)
        font, source = self.font(), Image.new('RGBA', (1434, 1080), '#0d1117')
        gallery.draw(source, font, visible=True)
        self.drain(gallery)
        gallery.draw(source, font, visible=True)
        gallery.edit_text('x', 'another folder')
        cached = gallery.draw(source, font, visible=True)
        gallery.modal_cache.clear()
        fresh = gallery.draw(source, font, visible=True)
        self.assertEqual(cached.tobytes(), fresh.tobytes())

    def test_explicit_folder_confirmation_creates_and_remembers_destination(self):
        gallery = self.gallery()
        gallery.choose_folder()
        destination = self.folder / 'new' / 'screenshots'
        gallery.draft = str(destination)
        gallery.focus = 46
        self.assertEqual(gallery.activate(), 'gallery_folder')
        with patch.object(ScreenshotSettings, 'save') as save:
            gallery.commit_folder()
            self.drain(gallery)
        save.assert_called_once_with()
        self.assertTrue(destination.is_dir())
        self.assertEqual(gallery.folder, destination.resolve())
        self.assertEqual(gallery.committed_folder, destination.resolve())
        self.assertFalse(gallery.choosing)

    def test_folder_failure_keeps_original_destination_and_inline_error(self):
        gallery = self.gallery()
        gallery.choose_folder()
        gallery.draft = str(self.folder / 'another')
        with patch.object(ScreenshotSettings, 'save', side_effect=PermissionError()):
            gallery.commit_folder()
            self.drain(gallery)
        self.assertEqual(gallery.folder, self.folder)
        self.assertTrue(gallery.choosing)
        self.assertIn('Could not use', gallery.folder_error)

    def test_folder_navigation_and_path_editing_include_selection_and_spaces(self):
        child = self.folder / 'My Screenshots'
        child.mkdir()
        gallery = self.gallery()
        gallery.choose_folder()
        self.drain(gallery)
        self.assertEqual(gallery.folders, (child,))
        gallery.focus = 1000
        gallery.activate()
        self.drain(gallery)
        self.assertEqual(gallery.browsing, child)
        gallery.focus = 40
        gallery.key('a', control=True)
        gallery.edit_text('', 'another folder')
        self.assertEqual(gallery.path_value(), child / 'another folder')
        gallery.focus = 43
        gallery.activate()
        self.assertEqual(gallery.browsing, self.folder)

    def test_controls_and_images_render_at_native_and_high_window_resolutions(self):
        self.png(size=(510, 384))
        gallery = self.gallery()
        font = self.font()
        gallery.draw(Image.new('RGBA', (512, 384)), font)
        self.drain(gallery)
        for visible, size in ((False, (512, 384)), (True, (1434, 1080)), (True, (800, 602))):
            for state in ('library', 'folders', 'delete'):
                with self.subTest(size=size, state=state):
                    gallery.choosing = state == 'folders'
                    gallery.deleting = state == 'delete'
                    frame = gallery.draw(Image.new('RGBA', size), font, visible=visible)
                    self.assertEqual(frame.size, size)
                    self.assertLessEqual(len(gallery.text_cache), 256)
                    self.assertLessEqual(len(gallery.image_cache), 16)


if __name__ == '__main__':
    unittest.main()
