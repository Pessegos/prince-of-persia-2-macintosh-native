"""Prepare the pages reached from F1 while F1 is shown, so that their first opening is quick.

The first opening of the screenshots, saves and Cutscene Viewer pages used to
paint the theme's frame, read the newest screenshots, decode the saves'
previews and fit the chapters' covers. While the F1 menu is open the game is
paused, so this work is done then instead, one small step at a time between
Tk's events: a key pressed meanwhile waits at most one step. It stops as soon
as F1 gives way to another page or the menu closes. It fills the caches those
pages already keep (the theme's frames, SHARED_READS, LAST_SCANS, the saves
read by list_slots and the viewer's covers), and draws the Cutscene Viewer's
page over the paused game and its shelf of cards, with the shelf's photo,
which the viewer opened from this F1 shows as they are (take_cutscene_shelf).
"""

import logging
import time

from PIL import Image

from pop2.game_ui import fit_menu_viewport, fit_viewport

LOG = logging.getLogger(__name__)
FIRST_DELAY_MS = 40   # after F1 has been shown
STEP_DELAY_MS = 1
READ_PATIENCE = 3.0   # seconds to wait for the screenshot reads before giving up


def page_size(width, height, wide):
    """The picture a page is drawn on at the window's resolution, as present_viewport sizes it."""
    return fit_menu_viewport(width, height)[0] if wide else fit_viewport(width, height)[0]


def warm_steps(scene):
    """The warm-up as a generator: each ``next`` does one small piece of work."""
    from pop2 import menu_theme
    from pop2.save_slots import SAVE_DIRECTORY, SaveBrowser, list_slots
    from pop2.screenshot_gallery import ScreenshotGallery

    width, height = scene.canvas.winfo_width(), scene.canvas.winfo_height()
    if width <= 1 or height <= 1:
        return
    font = scene.ui_font
    theme = menu_theme.current()
    done = getattr(scene, 'menu_warm_keys', None)
    if done is None:
        done = scene.menu_warm_keys = set()
    native = Image.new('RGBA', (512, 384), (0, 0, 0, 255))

    # Screenshots: the folder's listing, the newest thumbnails, the selected picture and the lava.
    gallery = ScreenshotGallery(scene.screenshot_settings.folder, scene.screenshot_settings.scale)
    try:
        wide = ScreenshotGallery.wide_layout(width, height)[0]
        source = Image.new('RGBA', page_size(width, height, wide), (0, 0, 0, 255))
        yield
        deadline = time.perf_counter() + READ_PATIENCE
        while gallery.applied_scan != gallery.scan_key and time.perf_counter() < deadline:
            gallery.poll()
            yield
        gallery.draw(source, font, visible=True)     # asks for what the page shows first
        yield
        while gallery.reads.pending and time.perf_counter() < deadline:
            gallery.poll()
            yield
        gallery.poll()
        if ('screenshots', theme.name, source.size) not in done:
            gallery.draw(native, font)                # the page's frame at the game's resolution
            done.add(('screenshots', theme.name, source.size))
            yield
    finally:
        gallery.close()

    # Saves: every save read once, and the page's frames.
    try:
        list_slots(SAVE_DIRECTORY)
    except OSError:
        pass
    yield
    wide = SaveBrowser.wide_layout(width, height)[0]
    size = page_size(width, height, wide)
    if ('saves', theme.name, size) not in done:
        browser = SaveBrowser(())
        browser.draw(Image.new('RGBA', size, (0, 0, 0, 255)), font, visible=True)
        yield
        browser.draw(native, font)
        done.add(('saves', theme.name, size))
        yield

    # The Cutscene Viewer: its chapters' covers fitted to their cards, then its page over this
    # pause's picture, its shelf of cards and the shelf's photo, which the viewer takes up.
    size = fit_menu_viewport(width, height)[0]
    if not hasattr(scene, 'cutscene_preview'):
        return
    from pop2.cutscene_gallery import CutsceneGallery
    from pop2.cutscenes import CHAPTERS, chapter_available

    caches = getattr(scene, 'cutscene_viewer_caches', None)
    if caches is None:
        caches = scene.cutscene_viewer_caches = {'text_cache': {}, 'image_cache': {}, 'card_cache': {}}
    viewer = CutsceneGallery(scene.cutscene_collection, scene.cutscene_preview, **caches)
    if ('cutscenes', theme.name, size) not in done:
        for index, chapter in enumerate(CHAPTERS):
            if chapter_available(chapter):
                try:
                    scene.cutscene_preview(index)
                except (OSError, ValueError, KeyError, RuntimeError):
                    pass
                yield
        viewer.layout(size, visible=True)
        scale = size[1] / 384
        for index in range(len(viewer.chapters)):
            viewer.card_image(index, font, scale, scale)
            yield
    scene.take_cutscene_shelf(viewer)
    viewer.draw(scene.cutscene_gallery_source(size), font, visible=True,
                background_key=id(scene.screenshot_viewport))
    scene.cutscene_viewer_ground = scene.screenshot_viewport, viewer.background_cache
    scene.keep_cutscene_shelf(viewer)
    done.add(('cutscenes', theme.name, size))
    yield
    scene.prepare_cutscene_shelf_photo()


def schedule_menu_warmup(scene):
    """Start the warm-up for the F1 menu just shown; it ends by itself when F1 is left."""
    cancel_menu_warmup(scene)
    menu = scene.game_menu
    steps = warm_steps(scene)

    def step():
        scene.menu_warmup_after_id = None
        if scene.game_menu is not menu or menu.page != 'menu' or not scene.paused:
            steps.close()
            return
        try:
            next(steps)
        except StopIteration:
            return
        except Exception:   # a cache that could not be filled is filled on opening instead
            LOG.debug('Menu warm-up stopped', exc_info=True)
            steps.close()
            return
        scene.menu_warmup_after_id = scene.root.after(STEP_DELAY_MS, step)

    scene.menu_warmup_steps = steps
    scene.menu_warmup_after_id = scene.root.after(FIRST_DELAY_MS, step)


def cancel_menu_warmup(scene):
    pending = getattr(scene, 'menu_warmup_after_id', None)
    scene.menu_warmup_after_id = None
    if pending is not None:
        try:
            scene.root.after_cancel(pending)
        except Exception:
            pass
    steps = getattr(scene, 'menu_warmup_steps', None)
    scene.menu_warmup_steps = None
    if steps is not None:
        steps.close()
