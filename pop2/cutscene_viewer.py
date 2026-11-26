"""Isolated story replay: private players and audio channels over a paused game."""

from dataclasses import dataclass
import logging
import math
import time
from tkinter import TclError

from PIL import Image

from pop2.cutscenes import CHAPTERS, CutsceneCollection, chapter_available, chapter_range
from pop2.playback_preview import PlaybackPreviews


LOG = logging.getLogger(__name__)


class ReplayAudio:
    """Borrow decoded sounds, never the paused game's channels or audio state."""

    def __init__(self, engine, enabled=True):
        self.playback = self
        self.channels = {}
        self.mixer = None
        self.enabled = enabled
        backend = getattr(engine, 'playback', None)
        mixer = getattr(backend, 'mixer', None)
        if mixer is None or not mixer.get_init():
            return
        count = mixer.get_num_channels()
        if not isinstance(count, int):  # Window-free/audio test backends.
            return
        self.mixer, self.first_channel = mixer, count
        self.sounds = backend.sounds
        mixer.set_num_channels(count + 2)
        self.channels = {bus: mixer.Channel(count + index) for index, bus in enumerate(('music', 'effect'))}

    def play_intro(self, resource_id, kind, offset=0):
        if not self.channels or not self.enabled:
            return
        from pop2.audio import scene_sound_key

        key = scene_sound_key(resource_id, kind)
        sound = self.sounds[key if key in self.sounds else resource_id]
        if offset:
            rate, bits, channels = self.mixer.get_init()
            start = int(max(0, offset) * rate) * (abs(bits) // 8) * channels
            remaining = sound.get_raw()[start:]
            if not remaining:
                self.stop('music' if kind == 0 else 'effect')
                return
            sound = self.mixer.Sound(buffer=remaining)
        self.channels['music' if kind == 0 else 'effect'].play(sound)

    def stop(self, bus):
        if bus in self.channels:
            self.channels[bus].stop()

    def pause(self, paused):
        for channel in self.channels.values():
            (channel.pause if paused else channel.unpause)()

    def close(self):
        channels, self.channels = self.channels, {}
        if self.mixer is not None and self.mixer.get_init():
            for channel in channels.values():
                channel.stop()
            if self.mixer.get_num_channels() == self.first_channel + 2:
                self.mixer.set_num_channels(self.first_channel)


@dataclass
class CutsceneReplay:
    chapter: object
    player: object
    audio: object
    last_at: float
    paused: bool = False
    started_at: float = 0.0


def chapter_player(chapter, assets, audio=None, *, ambience=None):
    from pop2.intro import IntroPlayer, game_song

    music = None
    if chapter.key == 'carpet':
        # In the campaign FlyinRug starts before NISCarpet and its markers
        # pace the film. A standalone replay starts that same song itself.
        from pop2.carpet import OPEN_SONG

        song = game_song(OPEN_SONG)
        # The preceding in-game ride owns the song's lead-in. Begin at its
        # first film marker so a standalone viewer does not show that wait
        # over a black, newly constructed display.
        elapsed = song['markers']['a']
        music = OPEN_SONG, elapsed, song
        if audio is not None:
            audio.play_intro(OPEN_SONG, 0, offset=elapsed)
    start, end = chapter_range(chapter, assets.program)
    player = IntroPlayer(assets, None if start else audio, music, ambience=ambience)
    if start:
        # Reconstruct palette/animation and cue clocks silently; resume only
        # sounds still active at this chapter boundary, on private channels.
        player.seek_operation(start)
        player.audio = audio
        if audio is not None:
            for kind, (cue, began, duration) in player.playing.items():
                elapsed = player.time - began
                if elapsed < duration:
                    audio.play_intro(cue, kind, offset=elapsed)
    if end is not None:
        player.operations = player.operations[:end]
    return player


class ChapterPreviews(PlaybackPreviews):
    frame_sizes = frozenset(((510, 384), (1024, 576)))

    def snapshot(self, index, players=None):
        from pop2.intro import IntroAssets
        from pop2.cutscene_covers import COVER_SHOTS, selected_cover

        chapter = CHAPTERS[index]
        stage = chapter.program.removesuffix('.json')
        if stage not in self.assets:
            self.assets[stage] = IntroAssets(self.directory, program_name=chapter.program)
        player = chapter_player(chapter, self.assets[stage])
        if chapter.key in COVER_SHOTS:
            return selected_cover(player, chapter.key)
        if chapter.key == 'opening':
            first_text = next(i for i, operation in enumerate(player.operations)
                              if operation['op'] == 'text' and operation['args'][1])
            player.seek_operation(first_text)
        player.advance(chapter.preview_seconds)
        return player.frame().crop((0, 0, 510, 384)).convert('RGB')


OPENING_ORDER = ('opening', 'opening_titles', 'opening_story')
CHAPTER_BY_KEY = {chapter.key: chapter for chapter in CHAPTERS}


class CutsceneControls:
    def init_cutscene_viewer(self):
        self.cutscene_collection = CutsceneCollection()
        self.cutscene_fresh = set()   # chapters unlocked by playing them since the viewer was last open
        self.cutscene_campaign_active = True
        self.cutscene_replay = None
        self.cutscene_after_id = None
        self.cutscene_gallery_after_id = None
        self.cutscene_watch = None   # (chapter key, its player) while a campaign scene plays

    def mark_cutscene_seen(self, key):
        if not getattr(self, 'cutscene_campaign_active', True):
            return
        collection = getattr(self, 'cutscene_collection', None)
        if collection is None:
            collection = self.cutscene_collection = CutsceneCollection()
        before = set(collection.seen)
        collection.unlock_through(key)
        if not hasattr(self, 'cutscene_fresh'):
            self.cutscene_fresh = set()
        # Only a chapter this play opens is revealed. The introduction that
        # follows the victory replays the opening of a collection that already
        # holds it: revealing its chapters again showed them locked.
        self.cutscene_fresh |= (collection.seen - before) - collection.revealed

    def watch_cutscene(self, key):
        """A chapter begins in the campaign: it is unlocked at once, and the
        viewer reveals it the next time it opens. The opening is one program in
        three chapters, so each of them is unlocked as it begins: the first
        version unlocked all three as the introduction began. Unlocking a scene
        only once it had ended was tried and rejected by the user: the happy
        ending, last of all, would then appear only in the game that follows."""
        self.update_cutscene_watch()
        self.cutscene_watch = None
        if key not in OPENING_ORDER:
            self.mark_cutscene_seen(key)
            return
        self.cutscene_watch = key, getattr(self, 'intro', None)
        self.update_cutscene_watch()

    def watch_story_scene(self, program_name):
        chapter = next((chapter for chapter in CHAPTERS if chapter.program == program_name), None)
        if chapter is not None:
            self.watch_cutscene(chapter.key)

    def reset_cutscene_tracking(self):
        """Drop the previous campaign's playing chapter and pending reveals."""
        self.cutscene_watch = None
        self.cutscene_fresh = set()

    def update_cutscene_watch(self):
        """Unlock each of the opening's chapters that has begun; the ones a skip
        passes over count as well, as a loaded save always has all three."""
        watch = getattr(self, 'cutscene_watch', None)
        if watch is None:
            return
        key, player = watch
        order = OPENING_ORDER[OPENING_ORDER.index(key):]
        playing = (player is not None and getattr(self, 'intro', None) is player
                   and not getattr(player, 'done', False))
        if not playing:
            self.cutscene_watch = None
            for chapter in order:
                self.mark_cutscene_seen(chapter)
            return
        program = {'operations': player.operations}
        for chapter in order:
            start = chapter_range(CHAPTER_BY_KEY[chapter], program)[0]
            if start and player.position <= start:   # not begun yet
                self.cutscene_watch = chapter, player
                return
            self.mark_cutscene_seen(chapter)
        self.cutscene_watch = None

    def open_cutscene_viewer(self, *, developer=False):
        from pop2.cutscene_gallery import CutsceneGallery

        if self.game_menu is None:
            self.open_game_menu(render=False)
        self.dispose_screenshot_gallery()
        self.cancel_cutscene_gallery_tick()
        self.game_menu.show_page('cutscenes')
        self.game_menu.return_to_menu = True
        # The covers, cards and text drawn last time are kept for the next opening.
        caches = getattr(self, 'cutscene_viewer_caches', None)
        if caches is None:
            caches = self.cutscene_viewer_caches = {'text_cache': {}, 'image_cache': {}, 'card_cache': {}}
        gallery = self.game_menu.cutscene_viewer = CutsceneGallery(
            self.cutscene_collection, self.cutscene_preview, developer=developer, **caches)
        gallery.select_latest()   # a reveal below selects its first chapter instead
        self.pause_resume_keys.update(self.window_keys_down)
        # Warm the source thumbnails before scrolling begins: loading a newly
        # exposed story program must not stall the moving shelf. Locked
        # chapters need theirs too, for the veiled blocks they show.
        for index, chapter in enumerate(CHAPTERS):
            if chapter_available(chapter):
                try:
                    self.cutscene_preview(index)
                except (OSError, ValueError, KeyError, RuntimeError):
                    pass  # The card and replay action provide the import error.
        self.update_cutscene_watch()
        fresh = getattr(self, 'cutscene_fresh', set())
        # Reveal only chapters present in the current collection.
        fresh &= self.cutscene_collection.seen
        if not developer and fresh:
            gallery.begin_reveal(index for index, chapter in enumerate(CHAPTERS) if chapter.key in fresh)
            self.cutscene_collection.revealed |= fresh
            fresh.clear()
        self.take_cutscene_shelf(gallery)
        self.redraw_menu()   # from F1, over the game's picture kept under the menu
        self.cutscene_viewer_ground = self.screenshot_viewport, gallery.background_cache
        if gallery.reveal:
            self.schedule_cutscene_gallery()

    def take_cutscene_shelf(self, gallery):
        """Give a viewer just opened the page's ground and its shelf of cards as they were
        drawn last while the menu was open (by F1's warm-up or a viewer left for F1): at
        3440x1440 they took about 45 ms to draw. Their keys say what they were drawn for:
        a viewer that differs draws its own. A shelf on which chapters are being revealed
        is the viewer's own, drawn with the veils it reveals."""
        ground = getattr(self, 'cutscene_viewer_ground', None)
        if ground is not None and ground[0] is self.screenshot_viewport:
            gallery.background_cache = ground[1]
        if not gallery.reveal:
            gallery.grid_cache = getattr(self, 'cutscene_viewer_shelf', None)

    def keep_cutscene_shelf(self, gallery):
        """Remember the viewer's shelf once no chapter on it is being revealed."""
        if gallery.grid_cache is not None and not gallery.reveal and not gallery.reveal_drawn:
            self.cutscene_viewer_shelf = gallery.grid_cache

    def prepare_cutscene_shelf_photo(self):
        """The photo of the shelf the viewer would show now, made with the pixels Tk prepares
        for the window (about 40 ms at 3440x1440), so that the viewer shows it at once."""
        from PIL import ImageTk
        from pop2.window_controls import photo_holder

        shelf = getattr(self, 'cutscene_viewer_shelf', None)
        kept = getattr(self, '_cutscene_gallery_grid_photo', None)
        if shelf is None or kept is not None and kept[0] is shelf[1]:
            return
        photo = ImageTk.PhotoImage(shelf[1])
        self.drop_cutscene_shelf_holder()
        self._cutscene_gallery_grid_photo = shelf[1], photo
        self._cutscene_shelf_holder = photo_holder(self.canvas, photo)

    def drop_cutscene_shelf_holder(self):
        holder = getattr(self, '_cutscene_shelf_holder', None)
        self._cutscene_shelf_holder = None
        if holder is not None:
            try:
                holder.destroy()
            except TclError:
                pass

    def active_cutscene_gallery(self):
        menu = getattr(self, 'game_menu', None)
        if menu is not None and menu.page == 'cutscenes' and self.cutscene_replay is None:
            return menu.cutscene_viewer
        return None

    def redraw_cutscene_gallery(self):
        self.present_viewport()
        self.schedule_cutscene_gallery()

    def cancel_cutscene_gallery_tick(self):
        pending = getattr(self, 'cutscene_gallery_after_id', None)
        self.cutscene_gallery_after_id = None
        if pending is not None:
            try:
                self.root.after_cancel(pending)
            except TclError:
                pass

    def schedule_cutscene_gallery(self):
        from pop2.display_refresh import window_refresh_rate
        from pop2.menu_animation import MenuFrameClock

        gallery = self.active_cutscene_gallery()
        if gallery is None or getattr(self, 'cutscene_gallery_after_id', None) is not None:
            return
        previous = time.perf_counter()
        clock = MenuFrameClock(previous, refresh_hz=window_refresh_rate(self.root))
        monitor_check = previous + 1

        def tick():
            nonlocal previous, monitor_check
            self.cutscene_gallery_after_id = None
            if self.active_cutscene_gallery() is not gallery:
                return
            now = time.perf_counter()
            if now >= monitor_check:
                clock.refresh_hz = window_refresh_rate(self.root)
                monitor_check = now + 1
            moving = gallery.advance(now - previous)
            previous = now
            if gallery.reveal_cue:
                gallery.reveal_cue = False
                self.play_menu_sound('reveal')
            self.present_viewport()
            if moving:
                def painted():
                    self.cutscene_gallery_after_id = None
                    if self.active_cutscene_gallery() is not gallery:
                        return
                    finished = time.perf_counter()
                    self.cutscene_gallery_after_id = self.root.after(clock.delay(finished, finished - now), tick)

                # Tk paints canvas items in idle handlers queued by present().
                # Include that work in the budget; a hidden photo update alone
                # does not measure the visible window's GDI rendering cost.
                self.cutscene_gallery_after_id = self.root.after_idle(painted)

        self.cutscene_gallery_after_id = self.root.after(clock.delay(previous), tick)

    def cutscene_gallery_frame(self, size, *, capture=False):
        from copy import copy

        gallery = self.active_cutscene_gallery()
        if capture:
            # An export size must not change live hit boxes, hover or a drag.
            gallery = copy(gallery)
            for name in ('text_cache', 'image_cache', 'card_cache'):
                setattr(gallery, name, getattr(gallery, name).copy())
            gallery.grid_in_place = False   # the live viewer's shelf is not its to draw over
        frame = self.draw_screenshot_notice(gallery.draw(self.cutscene_gallery_source(size, keep=not capture),
            self.ui_font, visible=True, background_key=id(self.screenshot_viewport)), visible=True, uniform=True)
        return frame if frame.mode == 'RGB' else frame.convert('RGB')

    def cutscene_gallery_source(self, size, keep=True):
        """The picture the viewer's page is drawn over: the game's, as the window shows it,
        in a window-sized black picture."""
        from pop2.game_ui import fit_viewport

        cached = getattr(self, '_cutscene_gallery_source', None)
        if cached is not None and cached[0] is self.screenshot_viewport and cached[1] == size:
            return cached[2]
        source = Image.new('RGBA', size, '#080808')
        fitted, origin = fit_viewport(*size)
        source.paste(self.screenshot_viewport.crop((1, 0, 511, 384)).resize(
            fitted, Image.Resampling.NEAREST), origin)
        if keep:
            self._cutscene_gallery_source = self.screenshot_viewport, size, source
        return source

    def present_cutscene_gallery(self, size, position):
        from PIL import ImageTk
        from pop2.cutscene_strip import CutsceneStrip
        from pop2.window_controls import put_patch

        gallery = self.active_cutscene_gallery()
        if gallery is None:
            if getattr(self, 'game_menu', None) is not None and getattr(self, 'cutscene_replay', None) is None:
                self.park_cutscene_gallery()
            else:
                self.release_cutscene_gallery()
            return False
        previous = getattr(self, '_cutscene_gallery_frame', None)

        def appearance():
            return (id(self.screenshot_viewport), id(self.ui_font), gallery.index, gallery.focus,
                    gallery.error, gallery.collection.error, frozenset(gallery.collection.seen),
                    gallery.developer, gallery.chapters, getattr(self, 'screenshot_toast', None))

        # A reveal changes one card on every frame: bring the cached grid up to
        # date here, and below copy just those cards into the retained photo.
        gallery.refresh_reveal(self.ui_font, size[1] / 384, size[1] / 384)
        look = appearance()
        shown = (previous is not None and previous[0] is gallery and previous[1].size == size
                 and previous[2] is self.image_ref and getattr(self, 'screenshot_toast', None) is None
                 and gallery.background_cache is not None and gallery.grid_cache is not None)
        fast = (shown and previous[5] == look and previous[3][0] == gallery.background_cache[0]
                and previous[4][3] == gallery.grid_cache[0])
        message = None
        if shown and not fast and previous[5][:2] + previous[5][4:] == look[:2] + look[4:]:
            # Only the selection moved: the shelf is drawn over at the card reached and the one
            # left, and so is its photo below, and the page's photo only where its message
            # changed. Under the strip, the page's photo is not seen (as while it scrolls).
            gallery.prepare(self.cutscene_gallery_source(size), self.ui_font, visible=True,
                            background_key=id(self.screenshot_viewport))
            redrawn = gallery.ground_redrawn
            if previous[3][0] == gallery.background_cache[0]:
                fast = True
            elif redrawn is not None and redrawn[0] == previous[3][0]:
                fast, message = True, redrawn[1]
        # Stable scroll frames use only retained Tk pixels. Rebuilding the
        # complete PIL viewport here spent most of the animation's frame budget.
        frame = None if fast else self.cutscene_gallery_frame(size)
        state = gallery.background_cache[0], getattr(self, 'screenshot_toast', None)
        sx = sy = size[1] / 384
        moving = (round(gallery.display_scroll * sx), gallery.scroll_target > 0,
                  gallery.scroll_target < gallery.max_scroll, gallery.grid_cache[0], gallery.display_scroll)
        grid_photo = getattr(self, '_cutscene_gallery_grid_photo', None)
        patches = gallery.take_reveal_patches()
        strip = getattr(self, '_cutscene_gallery_strip', None)
        if strip is None:
            strip = self._cutscene_gallery_strip = CutsceneStrip(self)
        if grid_photo is None or grid_photo[0] is not gallery.grid_cache[1]:
            grid_photo = self._cutscene_gallery_grid_photo = (
                gallery.grid_cache[1], ImageTk.PhotoImage(gallery.grid_cache[1]))
            strip.clear_overlays()   # the new photo already shows every card as it is
        else:
            for x, y, card, revealing in patches:
                if revealing:
                    # A card still being revealed is shown over the strip until it settles.
                    strip.overlay((x, y), card)
                    continue
                put_patch(grid_photo[1], card, x, y)
                strip.drop_overlay((x, y))
        if (previous is not None and previous[0] is gallery and previous[1].size == size
                and previous[2] is self.image_ref):
            if fast:
                if message is not None:
                    put_patch(self.image_ref, gallery.background_cache[1].crop(message), *message[:2])
                # The shelf shown (moving[3]) does not change the scroll's controls.
                if previous[4][:3] + previous[4][4:] != moving[:3] + moving[4:]:
                    regions = [gallery.TRACK]
                    if previous[4][1:3] != moving[1:3]:
                        regions += [gallery.PREVIOUS, gallery.NEXT]
                    for rect in regions:
                        region = (round((rect[0] - 1) * sx), round(rect[1] * sy),
                                  round((rect[2] - 1) * sx) + 1, round(rect[3] * sy) + 1)
                        pixels = gallery.background_cache[1].crop(region)
                        gallery.draw_scroll_controls(pixels, sx, sy, ox=1, origin=region[:2])
                        put_patch(self.image_ref, pixels, *region[:2])
            else:
                # Resize, toast and error changes are infrequent. Repaint
                # their complete frame; the parent photo can predate a scroll.
                self.image_ref.paste(frame)
        else:
            # The page's photo is not written where the strip lies over it, or, new, stays
            # blank there: Tk prepares only the rest for the window.
            self.show_photo(frame, position, hidden=None if getattr(self, 'screenshot_toast', None) else (
                round((gallery.STRIP[0] - 1) * sx), round(gallery.STRIP[1] * sy),
                round((gallery.STRIP[2] - 1) * sx), round(gallery.STRIP[3] * sy)))
        item = self.canvas.find_all()[0]
        if tuple(self.canvas.coords(item)) != tuple(position):
            # Even identical "coords" assignments invalidate the whole Tk
            # item. Leave the large static background alone while scrolling.
            self.canvas.coords(item, *position)
        if getattr(self, 'screenshot_toast', None) is not None:
            # Toasts can overlap the strip; the full renderer owns that frame.
            strip.hide()
        else:
            region = (round((gallery.STRIP[0] - 1) * sx) + position[0],
                      round(gallery.STRIP[1] * sy) + position[1],
                      round((gallery.STRIP[2] - 1) * sx) + position[0],
                      round(gallery.STRIP[3] * sy) + position[1])
            strip.show(region, grid_photo[1], moving[0] + round(gallery.GRID_PADDING * sx))
            strip.highlight(gallery.hover_border(sx))
        self._cutscene_gallery_frame = (gallery, previous[1] if fast else frame,
                                       self.image_ref, state, moving, appearance())
        self.keep_cutscene_shelf(gallery)
        return True

    def park_cutscene_gallery(self):
        """The menu shows another page: the viewer's strip is hidden, and kept with the photo
        of its shelf for the viewer opened again while the menu is open."""
        strip = getattr(self, '_cutscene_gallery_strip', None)
        if strip is not None:
            strip.hide()
        self._cutscene_gallery_frame = None

    def release_cutscene_gallery(self):
        """Take the viewer's strip off the window and drop the pictures kept for it."""
        self.dispose_cutscene_strip()
        self.drop_cutscene_shelf_holder()
        self._cutscene_gallery_frame = None
        self._cutscene_gallery_source = None
        self._cutscene_gallery_grid_photo = None
        self.cutscene_viewer_ground = self.cutscene_viewer_shelf = None

    def dispose_cutscene_strip(self):
        strip = getattr(self, '_cutscene_gallery_strip', None)
        self._cutscene_gallery_strip = None
        if strip is not None:
            try:
                strip.close()
            except TclError:
                pass  # Root destruction may already have destroyed its children.

    def cutscene_preview_provider(self):
        from pop2.playback_navigation import PlaybackPart

        provider = getattr(self, '_cutscene_previews', None)
        if provider is None:
            parts = tuple(PlaybackPart(chapter.title, chapter.program.removesuffix('.json'),
                                       round(chapter.preview_seconds * 1000))
                          for chapter in CHAPTERS)
            provider = self._cutscene_previews = ChapterPreviews(
                self.resources, parts, None, self.preview_fingerprint(), namespace='cutscene-covers-v1')
        return provider

    def cutscene_preview(self, index):
        return self.cutscene_preview_provider().group((index,))[index]

    def start_cutscene_replay(self):
        from pop2.intro import IntroAssets

        gallery = self.game_menu.cutscene_viewer
        if not gallery.unlocked:
            return
        chapter = gallery.chapter
        audio = None
        try:
            provider = self.cutscene_preview_provider()
            stage = chapter.program.removesuffix('.json')
            if stage not in provider.assets:
                provider.assets[stage] = IntroAssets(program_name=chapter.program)
            audio = ReplayAudio(self.audio, getattr(self, 'sound_enabled', True))
            player = chapter_player(chapter, provider.assets[stage], audio,
                                    ambience=lambda: getattr(self, 'cave_ambience_enabled', False))
        except (OSError, ValueError, KeyError, RuntimeError):
            if audio is not None:
                audio.close()
            LOG.exception('Could not open cutscene %s', chapter.key)
            gallery.error = 'Could not play this cutscene. Try importing the game again.'
            self.render()
            return
        self.cancel_cutscene_gallery_tick()
        now = time.perf_counter()
        self.cutscene_replay = CutsceneReplay(chapter, player, audio, now, started_at=now)
        self.pause_resume_keys.update(self.window_keys_down)
        self.render()
        self.schedule_cutscene_replay()

    def schedule_cutscene_replay(self):
        replay = getattr(self, 'cutscene_replay', None)
        if replay is None or replay.paused or self.cutscene_after_id is not None:
            return
        delay = max(1, min(50, math.ceil(replay.player.next_update_delay() * 1000)))
        self.cutscene_after_id = self.root.after(delay, self.advance_cutscene_replay)

    def advance_cutscene_replay(self):
        self.cutscene_after_id = None
        replay = self.cutscene_replay
        if replay is None or replay.paused:
            return
        now = time.perf_counter()
        try:
            replay.player.advance(max(0, now - replay.last_at))
            replay.last_at = now
            if replay.player.done:
                self.stop_cutscene_replay()
                return
            self.render()
            self.schedule_cutscene_replay()
        except (OSError, ValueError, KeyError, RuntimeError):
            LOG.exception('Could not finish cutscene %s', replay.chapter.key)
            self.stop_cutscene_replay()
            self.game_menu.cutscene_viewer.error = 'Could not finish this cutscene. Try importing the game again.'
            self.render()

    def cancel_cutscene_tick(self):
        pending = getattr(self, 'cutscene_after_id', None)
        self.cutscene_after_id = None
        if pending is not None:
            try:
                self.root.after_cancel(pending)
            except TclError:
                pass

    def pause_cutscene_replay(self, paused):
        replay = getattr(self, 'cutscene_replay', None)
        if replay is None or replay.paused == paused:
            return
        replay.paused = paused
        replay.audio.pause(paused)
        self.cancel_cutscene_tick()
        if not paused:
            replay.last_at = time.perf_counter()
            self.schedule_cutscene_replay()
        self.render()

    def stop_cutscene_replay(self, render=True):
        replay = getattr(self, 'cutscene_replay', None)
        self.cancel_cutscene_tick()
        self.cutscene_replay = None
        if replay is not None:
            replay.audio.close()
        self.pause_resume_keys.update(self.window_keys_down)
        if render:
            self.render()

    def destroy_cutscene_viewer(self, event):
        if event.widget is self.root:
            self.dispose_cutscene_strip()
            self.cancel_cutscene_gallery_tick()
            self.stop_cutscene_replay(render=False)

    def cutscene_replay_key(self, event, repeated, alt):
        if getattr(self, 'cutscene_replay', None) is None:
            return False
        if not repeated:
            if event.keysym == 'Return' and alt:
                self.toggle_fullscreen()
            elif event.keysym == 'Escape':
                self.pause_cutscene_replay(not self.cutscene_replay.paused)
            elif event.keysym in ('space', 'BackSpace', 'F1'):
                self.stop_cutscene_replay()
        return True

    def render_cutscene_replay(self):
        replay = getattr(self, 'cutscene_replay', None)
        if replay is None:
            return False
        viewport = Image.new('RGBA', (512, 384), 'black')
        viewport.paste(replay.player.frame().crop((0, 0, 510, 384)), (1, 0))
        self.screenshot_viewport = viewport.copy()
        if replay.paused:
            viewport = self.draw_cutscene_pause(viewport)
        self.native_viewport = self.draw_screenshot_notice(viewport)
        self.present_viewport()
        return True
