"""Isolated story replay: private players and audio channels over a paused game."""

from dataclasses import dataclass
import logging
import math
import time
from tkinter import TclError

from PIL import Image

from pop2.cutscenes import CHAPTERS, CutsceneCollection, chapter_range
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


def chapter_player(chapter, assets, audio=None):
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
    player = IntroPlayer(assets, None if start else audio, music)
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
    def snapshot(self, index, players=None):
        from pop2.intro import IntroAssets

        chapter = CHAPTERS[index]
        stage = chapter.program.removesuffix('.json')
        if stage not in self.assets:
            self.assets[stage] = IntroAssets(self.directory, program_name=chapter.program)
        player = chapter_player(chapter, self.assets[stage])
        if chapter.key == 'opening':
            first_text = next(i for i, operation in enumerate(player.operations)
                              if operation['op'] == 'text' and operation['args'][1])
            player.seek_operation(first_text)
        player.advance(chapter.preview_seconds)
        return player.frame().crop((0, 0, 510, 384)).convert('RGB')


class CutsceneControls:
    def init_cutscene_viewer(self):
        self.cutscene_collection = CutsceneCollection.load()
        self.cutscene_replay = None
        self.cutscene_after_id = None

    def mark_cutscene_seen(self, key):
        collection = getattr(self, 'cutscene_collection', None)
        if collection is None:
            collection = self.cutscene_collection = CutsceneCollection.load()
        collection.unlock(key)

    def mark_story_scene_seen(self, program_name):
        chapter = next((chapter for chapter in CHAPTERS if chapter.program == program_name), None)
        if chapter is not None:
            self.mark_cutscene_seen(chapter.key)

    def open_cutscene_viewer(self):
        from pop2.cutscene_gallery import CutsceneGallery

        if self.game_menu is None:
            self.open_game_menu()
        self.dispose_screenshot_gallery()
        self.game_menu.show_page('cutscenes')
        self.game_menu.return_to_menu = True
        if self.cutscene_collection.error:
            self.cutscene_collection.save()
        self.game_menu.cutscene_viewer = CutsceneGallery(self.cutscene_collection, self.cutscene_preview)
        self.pause_resume_keys.update(self.window_keys_down)
        self.render()

    def cutscene_preview_provider(self):
        from pop2.playback_navigation import PlaybackPart

        provider = getattr(self, '_cutscene_previews', None)
        if provider is None:
            parts = tuple(PlaybackPart(chapter.title, chapter.program.removesuffix('.json'),
                                       round(chapter.preview_seconds * 1000))
                          for chapter in CHAPTERS)
            provider = self._cutscene_previews = ChapterPreviews(
                self.resources, parts, None, self.preview_fingerprint(), namespace='cutscenes-v3')
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
            player = chapter_player(chapter, provider.assets[stage], audio)
        except (OSError, ValueError, KeyError, RuntimeError):
            if audio is not None:
                audio.close()
            LOG.exception('Could not open cutscene %s', chapter.key)
            gallery.error = 'Could not play this cutscene. Try importing the game again.'
            self.render()
            return
        self.cutscene_replay = CutsceneReplay(chapter, player, audio, time.perf_counter())
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
        label = 'Esc: Resume   Space: Back' if replay.paused else 'Esc: Pause   Space: Back'
        text = self.ui_font.text(label, '#eeeeee')
        viewport.paste(text, ((512 - text.width) // 2, 367), text)
        self.native_viewport = self.draw_screenshot_notice(viewport)
        self.present_viewport()
        return True
