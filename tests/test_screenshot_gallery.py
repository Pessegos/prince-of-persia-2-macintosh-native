from pathlib import Path
from tempfile import TemporaryDirectory
from threading import get_ident
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

from pop2.screenshot_gallery import GalleryReads, ScreenshotGallery, open_capture_folder, read_capture, scan_captures
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
            self.assertEqual(decode.call_count, 2)
            with patch('pop2.screenshot_gallery.os.scandir', side_effect=AssertionError('Hover read disk')):
                for index in range(20):
                    gallery.hover(90, 55)
                    gallery.hover(130, 350)
                    gallery.draw(source, font)
            self.assertEqual(decode.call_count, 2)
        self.assertEqual(ready.size, source.size)
        self.assertEqual(source.getpixel((0, 0)), (0, 0, 255, 255))

    def test_gallery_navigation_scroll_is_smooth_and_does_not_delete_on_selection(self):
        for i in range(12):
            self.png(f'{i}.png', size=(20, 20))
        gallery = self.gallery()
        gallery.key('Next')
        self.assertEqual(gallery.selected, 6)
        gallery.key('Next')
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
                    self.assertLessEqual(len(gallery.image_cache), 48)

    def test_fixed_grid_hit_testing_and_navigation_keep_selection_visible(self):
        for i in range(40):
            self.png(f'{i}.png', size=(20, 20))
        gallery = self.gallery()
        self.assertEqual(gallery.COLUMNS, 2)
        self.assertEqual(gallery.hit(40, 95), 100)
        self.assertEqual(gallery.hit(120, 95), 101)
        self.assertEqual(gallery.hit(40, 160), 102)
        gallery.selected = 29
        gallery.ensure_visible(immediate=True)
        self.assertLessEqual(len(gallery.visible_indices), 12)
        self.assertIsNone(gallery.hit(250, 30))
        self.assertIsNone(gallery.hit(280, 30))
        self.assertEqual(gallery.selected, 29)
        self.assertLess(gallery.row_rect(29)[1], gallery.LIST[3])
        self.assertGreaterEqual(gallery.row_rect(29)[1], gallery.LIST[1])
        self.assertLessEqual(gallery.scroll, gallery.max_scroll)

    def test_scroll_surface_cache_matches_full_redraw_at_each_resolution(self):
        for i in range(16):
            self.png(f'{i}.png', color=(i * 15, 100, 200), size=(51, 38))
        gallery = self.gallery()
        font = self.font()
        for size, visible in (((512, 384), False), ((1434, 1080), True)):
            source = Image.new('RGBA', size, '#0d1117')
            for offset in (0, 24, 108, 380, 12):
                gallery.scroll = min(offset, gallery.max_scroll)
                gallery.draw(source, font, visible=visible)
                self.drain(gallery)
                cached = gallery.draw(source, font, visible=visible)
                gallery.surface_cache.clear()
                fresh = gallery.draw(source, font, visible=visible)
                self.assertEqual(cached.tobytes(), fresh.tobytes(), (size, offset))

    def test_visible_thumbnails_do_not_thrash_the_preview_cache(self):
        for i in range(12):
            self.png(f'{i}.png', size=(51, 38))
        gallery = self.gallery()
        source, font = Image.new('RGBA', (512, 384)), self.font()
        with patch('pop2.screenshot_gallery.read_capture', wraps=read_capture) as decode:
            for _ in range(4):
                gallery.draw(source, font)
                self.drain(gallery)
            initial = decode.call_count
            self.assertGreater(initial, 6)
            for _ in range(3):
                gallery.scroll = gallery.max_scroll
                gallery.draw(source, font)
                self.drain(gallery)
                gallery.scroll = 0
                gallery.draw(source, font)
                self.drain(gallery)
            self.assertEqual(decode.call_count, 13)

    def test_thumbnail_decode_keeps_original_dimensions_and_fitted_previews_have_no_black_frame(self):
        self.png(size=(2040, 1536))
        entry, = scan_captures(self.folder)
        image, dimensions = read_capture(entry, (510, 384))
        self.assertEqual(image.size, (510, 384))
        self.assertEqual(dimensions, (2040, 1536))
        gallery = self.gallery()
        source, font = Image.new('RGBA', (512, 384)), self.font()
        gallery.draw(source, font)
        self.drain(gallery)
        frame = gallery.draw(source, font)
        self.assertEqual(frame.getpixel((203, 190)), (24, 24, 24, 255))
        self.assertEqual(frame.getpixel((324, 190)), (255, 0, 0, 255))

    def test_image_cache_budgets_and_obsolete_jobs(self):
        reads = GalleryReads()
        self.addCleanup(reads.close)
        for kind, count, quota in (('thumb', 80, 64), ('image', 5, 3)):
            for i in range(count):
                reads.results.put(((kind, i), SimpleNamespace(value=i, error='')))
            reads.poll()
            self.assertEqual(sum(key[0] == kind for key in reads.cache), quota)
        reads.wanted = frozenset()
        reads.request(('thumb', 'obsolete'), lambda: self.fail('Obsolete image decoded'))
        deadline = time.monotonic() + 5
        while reads.pending and time.monotonic() < deadline:
            reads.poll()
            time.sleep(0.001)
        self.assertFalse(reads.pending)
        self.assertNotIn(('thumb', 'obsolete'), reads.cache)

    def test_open_folder_is_explicit_async_and_does_not_change_destination(self):
        gallery = self.gallery()
        caller = get_ident()
        calls = []
        with patch('pop2.screenshot_gallery.open_capture_folder',
                   side_effect=lambda folder: calls.append((folder, get_ident()))), \
                patch.object(ScreenshotSettings, 'save') as save:
            gallery.hover(280, 310)
            self.assertEqual(calls, [])
            gallery.click(280, 310)
            self.drain(gallery)
            self.assertEqual(calls[0][0], self.folder)
            self.assertNotEqual(calls[0][1], caller)
            save.assert_not_called()
        self.assertEqual(gallery.folder, self.folder)
        self.assertEqual(gallery.status, 'Folder opened')
        with patch('pop2.screenshot_gallery.open_capture_folder', side_effect=OSError()):
            gallery.click(280, 310)
            self.drain(gallery)
        self.assertIn('Could not open', gallery.error)

    def test_lava_icon_replaces_placeholder_and_keeps_confirmation_safety(self):
        path = self.png()
        gallery = self.gallery()
        source, font = Image.new('RGBA', (512, 384)), self.font()
        frames = (Image.new('RGBA', (36, 10), '#ff8000'), Image.new('RGBA', (36, 10), '#ffff00'))
        with patch('pop2.screenshot_gallery.lava_delete_frames', return_value=frames):
            gallery.draw(source, font)
            self.drain(gallery)
            frame = gallery.draw(source, font)
        self.assertEqual(frame.getpixel((453, 286)), (255, 128, 0, 255))
        state = gallery.surface_state
        self.assertTrue(gallery.animation_running)
        self.assertTrue(gallery.animate(1 / 12))
        self.assertEqual(gallery.surface_state, state)
        frame = gallery.draw(source, font)
        self.assertEqual(frame.getpixel((453, 286)), (255, 255, 0, 255))
        self.assertLessEqual(len(gallery.icon_cache), 3)
        gallery.hover(453, 286)
        self.assertTrue(path.exists())
        gallery.click(453, 286)
        self.assertTrue(gallery.deleting)
        self.assertFalse(gallery.animation_running)
        self.assertFalse(gallery.animate(1))
        self.assertEqual(gallery.focus, 60)
        self.assertEqual(gallery.delete_target.path, path)
        gallery.key('Return')
        self.assertTrue(path.exists())

    def test_explorer_accepts_unicode_paths_and_never_creates_missing_folders(self):
        folder = self.folder / 'Grava\u00e7\u00f5es de Ecr\u00e3'
        with patch('pop2.screenshot_gallery.sys.platform', 'win32'), \
                patch('pop2.screenshot_gallery.os.startfile', create=True) as start:
            with self.assertRaises(NotADirectoryError):
                open_capture_folder(folder)
            self.assertFalse(folder.exists())
            start.assert_not_called()
            folder.mkdir()
            open_capture_folder(folder)
            start.assert_called_once_with(str(folder))

    def test_lava_frames_use_native_offsets_and_repeat_without_an_extra_hold(self):
        from pop2.lava import LavaPool
        from pop2.screenshot_gallery import lava_delete_frames
        from tests.test_lava import synthetic_tables

        pool = LavaPool(synthetic_tables(), enhanced=True)
        resources = {'SHAP': {shape: {'data': b'fake'} for shape in range(3616, 3622)}}
        records = []
        drawings = pool.drawings
        def record():
            result = drawings()
            records.append(result)
            return result
        lava_delete_frames.cache_clear()
        self.addCleanup(lava_delete_frames.cache_clear)
        with patch('pop2.caverns.cavern_assets', return_value=({'lava': pool.tables}, resources, {}, {})), \
                patch('pop2.lava.LavaPool', return_value=pool), \
                patch.object(pool, 'drawings', side_effect=record), \
                patch('pop2.render_opening.decode_shap', return_value=Image.new('RGBA', (5, 5), '#ff8000')):
            frames = lava_delete_frames()
        self.assertEqual(len(frames), 22)
        self.assertEqual(len({frame.size for frame in frames}), 1)
        for phase in range(22):
            pool.advance()
            self.assertEqual(drawings(), records[phase])
        self.assertIn((3616, 63, -12, False), records[0])

    def test_drag_threshold_cancel_and_drop_elsewhere_never_delete(self):
        path = self.png()
        gallery = self.gallery()
        self.assertTrue(gallery.begin_drag(70, 100))
        self.assertFalse(gallery.move_drag(72, 100))
        gallery.release_drag(72, 100)
        self.assertFalse(gallery.deleting)
        self.assertTrue(gallery.begin_drag(70, 100))
        self.assertTrue(gallery.move_drag(300, 200))
        gallery.release_drag(300, 200)
        self.assertFalse(gallery.deleting)
        self.assertTrue(path.exists())
        gallery.begin_drag(70, 100)
        gallery.move_drag(453, 286)
        self.assertEqual(gallery.key('Escape'), 'changed')
        self.assertFalse(gallery.overlay_active)
        self.assertIsNone(gallery.drag_target)
        self.assertFalse(gallery.deleting)
        self.assertFalse(gallery.begin_drag(250, 150))

    def test_dropping_confirms_original_capture_and_burns_only_after_success(self):
        original = self.png('original.png')
        gallery = self.gallery()
        source, font = Image.new('RGBA', (512, 384)), self.font()
        gallery.draw(source, font)
        self.drain(gallery)
        gallery.begin_drag(70, 100)
        gallery.move_drag(453, 286)
        gallery.release_drag(453, 286)
        self.assertTrue(gallery.deleting)
        self.assertEqual(gallery.focus, 60)
        self.assertTrue(original.exists())
        self.assertIsNone(gallery.burn_seconds)
        new = self.png('new.png', 'blue')
        gallery.refresh(new)
        self.drain(gallery)
        self.assertEqual(gallery.entry.path, new)
        self.assertEqual(gallery.delete_target.path, original)
        gallery.focus = 61
        self.assertEqual(gallery.activate(), 'gallery_delete')
        gallery.delete_capture()
        self.drain(gallery)
        self.assertFalse(original.exists())
        self.assertTrue(new.exists())
        self.assertEqual(gallery.burn_seconds, 0)
        self.assertEqual(gallery.burn_target.path, original)
        self.assertEqual(gallery.burn_image.getpixel((0, 0)), (255, 0, 0))
        for size, visible in (((512, 384), False), ((1434, 1080), True)):
            canvas = Image.new('RGBA', size)
            cached = gallery.draw(canvas, font, visible=visible)
            gallery.surface_cache.clear()
            self.assertEqual(cached.tobytes(), gallery.draw(canvas, font, visible=visible).tobytes())
        gallery.animate(0.66)
        self.assertIsNone(gallery.burn_seconds)
        self.assertFalse(gallery.overlay_active)

    def test_drop_cancel_and_changed_file_do_not_start_burning(self):
        path = self.png()
        gallery = self.gallery()
        for fail in (False, True):
            gallery.begin_drag(70, 100)
            gallery.move_drag(453, 286)
            gallery.release_drag(453, 286)
            if fail:
                path.write_text('Changed after drag started')
                gallery.delete_capture()
                self.drain(gallery)
                self.assertIn('Could not delete', gallery.error)
            else:
                gallery.key('Return')
                self.assertFalse(gallery.delete_from_drop)
            self.assertTrue(path.exists())
            self.assertIsNone(gallery.burn_seconds)

    def test_lava_control_is_borderless_and_highlight_clears_after_pointer_leaves(self):
        self.png()
        gallery = self.gallery()
        source, font = Image.new('RGBA', (512, 384)), self.font()
        frames = (Image.new('RGBA', (36, 10), '#ff8000'),)
        with patch('pop2.screenshot_gallery.lava_delete_frames', return_value=frames):
            gallery.draw(source, font)
            self.drain(gallery)
        idle = gallery.draw(source, font)
        self.assertEqual(idle.getpixel((432, 274)), (24, 24, 24, 255))
        gallery.hover(453, 286)
        hovered = gallery.draw(source, font)
        self.assertEqual(hovered.getpixel((432, 274)), (43, 29, 27, 255))
        gallery.hover(-1, -1)
        self.assertEqual(gallery.focus, 13)
        self.assertEqual(gallery.draw(source, font).getpixel((432, 274)), (24, 24, 24, 255))
        gallery.focus = 100
        gallery.key('Tab')
        self.assertEqual(gallery.focus, 13)
        self.assertEqual(gallery.draw(source, font).getpixel((432, 274)), (43, 29, 27, 255))
        gallery.click(453, 286)
        self.assertTrue(gallery.deleting)
        self.assertEqual(gallery.focus, 60)


if __name__ == '__main__':
    unittest.main()
