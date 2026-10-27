"""SDL effect mixing with coalesced stone-mechanism voices."""

import json
import os
from pathlib import Path
import random
import struct
import time

from pop2.paths import ASSET_DIR
from pop2.audio_duck import PcmGateDuck
from pop2.audio_release import PcmRelease, seamless_loop
from pop2.audio_loop import PcmSustain, gate_loop_bounds
from pop2.ui_audio import menu_pcm
from pop2.mechanism_audio import GateVoice


GATE_SLAM_DELAY = 11 / 60
MECHANISM_CUES = frozenset((17, 18, 20))


def scene_sound_key(resource_id, kind):
    return f"scene-{kind}-{resource_id}"


class MixerPlayback:
    def __init__(self, directory, cues, mix_mechanisms=False, split_mechanisms=False):
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        from pygame import mixer

        self.mixer = mixer
        try:
            mixer.init(frequency=48000, size=-16, channels=2, buffer=512)
        except mixer.error as error:
            raise RuntimeError(f"Cannot open the sound device. Check Windows audio settings: {error}") from error
        mixer.set_num_channels(8 if split_mechanisms else 6)
        self.channels = {"effect": mixer.Channel(0), "music": mixer.Channel(1)}
        self.effect_channels = []
        self.effect_channel_ids = {}
        self.effects = {}
        self.effect_volume = 1.0
        self.gate_bus = "mechanism" if mix_mechanisms else "effect"
        if mix_mechanisms:
            self.channels["mechanism"] = mixer.Channel(5)
        self.gate_tail = mixer.Channel(2)
        self.effect_channel, self.tail_channel = (5 if mix_mechanisms else 0), 2
        self.closing_voice = None
        if split_mechanisms:
            self.channels['closing'] = mixer.Channel(6)
            self.closing_voice = GateVoice(mixer.Channel(7), 6, 7)
        rate, _bits, channels = mixer.get_init()
        self.ui_channels = {kind: mixer.Channel(index) for index, kind in enumerate(('hover', 'click'), 3)}
        self.ui_sounds = {kind: mixer.Sound(buffer=menu_pcm(kind, rate, channels)) for kind in self.ui_channels}
        self.sounds = {cue: mixer.Sound(str(Path(directory) / item["file"]))
                       for cue, item in cues.items() if item.get("file")}
        if 20 in self.sounds:
            # Sample-clock delay: independent of the slower gameplay tick,
            # and automatically paused/cancelled with the effect channel.
            rate, bits, channels = mixer.get_init()
            silence = bytes(round(rate * GATE_SLAM_DELAY) * (abs(bits) // 8) * channels)
            self.sounds[20] = mixer.Sound(buffer=silence + self.sounds[20].get_raw())
        self.gate_release = PcmRelease(mixer) if 17 in self.sounds and 18 in self.sounds else None
        self.gate_duck = (PcmGateDuck(mixer) if mix_mechanisms
                          and 17 in self.sounds and 26 in self.sounds else None)
        self.gate_sustain = None
        if self.gate_release is not None:
            rate, _bits, channels = mixer.get_init()
            original = self.sounds[17]
            self.gate_lifetime = max(1, round(original.get_length() * 1000))
            bounds = gate_loop_bounds(Path(directory) / cues[17]['file'], cues[17], rate)
            if bounds is not None:
                self.gate_sustain = PcmSustain(
                    self.gate_release.library, original.get_raw(), channels, *bounds)
            else:
                self.sounds[17] = mixer.Sound(buffer=seamless_loop(
                    original.get_raw(), channels, rate * 12 // 1000))

    def _gate_voice(self, bus):
        if bus == getattr(self, 'gate_bus', 'effect'):
            return self
        if bus == 'closing':
            return getattr(self, 'closing_voice', None)
        return None

    def _gate_tails(self):
        yield self.gate_tail
        if getattr(self, 'closing_voice', None) is not None:
            yield self.closing_voice.gate_tail

    def sustain_gate(self, bus=None):
        bus = bus or getattr(self, 'gate_bus', 'effect')
        voice = self._gate_voice(bus)
        channel = self.channels[bus]
        if (self.gate_release is not None and channel.get_busy()
                and channel.get_sound() is self.sounds[17]):
            # Renew only while the controller still requests movement. A lost
            # stop cue must not leave an infinite stone sound behind.
            self.gate_release.expire(voice.effect_channel, self.gate_lifetime)

    def release_gate(self, bus):
        voice = self._gate_voice(bus)
        if self.gate_release is not None:
            self.gate_release.start(voice.effect_channel)
        else:
            self.channels[bus].stop()

    def play(self, bus, cue, offset=0):
        sound = self.sounds[cue]
        voice = self._gate_voice(bus)
        if offset:
            rate, bits, channels = self.mixer.get_init()
            frame_size = abs(bits) // 8 * channels
            start = int(max(0, offset) * rate) * frame_size
            remaining = sound.get_raw()[start:]
            if not remaining:
                self.stop(bus)
                return
            sound = self.mixer.Sound(buffer=remaining)
        if (voice is not None and cue in (18, 20) and self.channels[bus].get_busy()
                and self.channels[bus].get_sound() is self.sounds.get(17)):
            # Fade PCM samples, not SDL's stepped per-buffer channel volume.
            voice.gate_tail.stop()
            voice.gate_tail.set_volume(self.channels[bus].get_volume())
            self.gate_release.start(voice.effect_channel)
            self.channels[bus], voice.gate_tail = voice.gate_tail, self.channels[bus]
            voice.effect_channel, voice.tail_channel = voice.tail_channel, voice.effect_channel
        elif voice is not None:
            voice.gate_tail.stop()
        if voice is not None and self.gate_release is not None:
            self.gate_release.cancel(voice.effect_channel)
        if voice is not None and cue == 17 and not offset and self.gate_release is not None:
            if getattr(self, 'gate_sustain', None) is not None:
                # Inactive channels retain registered SDL effects when started.
                # The sustain callback runs before subsequent duck/release effects.
                self.channels[bus].stop()
                self.gate_sustain.start(voice.effect_channel)
            self.channels[bus].play(sound, loops=-1)
            self.sustain_gate(bus)
        else:
            self.channels[bus].play(sound)
        if voice is not None and cue == 17 and self.gate_duck is not None:
            self.gate_duck.watch(voice.effect_channel, 'gate')

    def busy(self, bus):
        return self.channels[bus].get_busy()

    def playing_effects(self):
        for cue, channel in tuple(self.effects.items()):
            if not channel.get_busy():
                del self.effects[cue]
        return tuple(self.effects)

    def play_effect(self, cue):
        self.playing_effects()
        if cue in self.effects:
            return
        channel = next((item for item in self.effect_channels if not item.get_busy()), None)
        if channel is None:
            index = self.mixer.get_num_channels()
            self.mixer.set_num_channels(index + 1)
            channel = self.mixer.Channel(index)
            self.effect_channels.append(channel)
            self.effect_channel_ids[channel] = index
        channel.set_volume(self.effect_volume)
        channel.play(self.sounds[cue])
        self.effects[cue] = channel
        if cue == 26 and self.gate_duck is not None:
            self.gate_duck.watch(self.effect_channel_ids[channel], 'impact')

    def stop_effect(self, cue):
        channel = self.effects.pop(cue, None)
        if channel is not None:
            channel.stop()

    def play_ui(self, kind):
        if kind == 'hover' and any(channel.get_busy() for channel in self.ui_channels.values()):
            return
        if not self.ui_channels[kind].get_busy():
            self.ui_channels[kind].play(self.ui_sounds[kind])

    def stop_ui(self):
        for channel in self.ui_channels.values():
            channel.stop()

    def stop(self, bus):
        self.channels[bus].stop()
        if bus == 'effect':
            for cue in tuple(self.effects):
                self.stop_effect(cue)
        voice = self._gate_voice(bus)
        if voice is not None:
            voice.gate_tail.stop()
            if self.gate_release is not None:
                self.gate_release.cancel(voice.effect_channel)
                self.gate_release.cancel(voice.tail_channel)

    def set_volume(self, bus, volume):
        self.channels[bus].set_volume(volume)
        if bus == 'effect':
            self.effect_volume = volume
            for channel in self.effect_channels:
                channel.set_volume(volume)
        voice = self._gate_voice(bus)
        if voice is not None:
            voice.gate_tail.set_volume(volume)
            if not volume:
                voice.gate_tail.stop()

    def pause(self, paused):
        for channel in (*self.channels.values(), *self._gate_tails(), *self.effect_channels):
            (channel.pause if paused else channel.unpause)()

    def close(self):
        self.stop_ui()
        for channel in (*self.channels.values(), *self._gate_tails(), *self.effect_channels):
            channel.stop()
        self.effects.clear()
        if self.gate_duck is not None:
            self.gate_duck.close()
        if getattr(self, 'gate_sustain', None) is not None:
            self.gate_sustain.close()
        if self.gate_release is not None:
            for bus in self.channels:
                voice = self._gate_voice(bus)
                if voice is not None:
                    self.gate_release.cancel(voice.effect_channel)
                    self.gate_release.cancel(voice.tail_channel)
        self.mixer.quit()


class AudioEngine:
    def __init__(self, directory=ASSET_DIR / "audio", playback=None, rng=None,
                 *, mix_mechanisms=True, mix_effects=None, split_mechanisms=None):
        directory = Path(directory)
        self.manifest = json.loads((directory / "manifest.json").read_text(encoding="ascii"))
        if self.manifest.get("schema") != 1:
            raise ValueError("Game audio needs to be imported again")
        self.cues = {int(key): value for key, value in self.manifest["cues"].items()}
        self.scene_cues = self.manifest.get("scene_cues", {})
        self.mix_mechanisms = mix_mechanisms
        self.mix_effects = mix_mechanisms if mix_effects is None else mix_effects
        self.split_mechanisms = (self.mix_mechanisms and self.mix_effects
                                 if split_mechanisms is None else
                                 bool(split_mechanisms and self.mix_mechanisms))
        self.gate_events = None
        self.pending_effects = {}
        self.stopped_effects = set()
        self.effect_buses = ("effect", "mechanism") if mix_mechanisms else ("effect",)
        if self.split_mechanisms:
            self.effect_buses += ('closing',)
        self.playback = playback or MixerPlayback(
            directory, {**self.cues, **self.scene_cues}, mix_mechanisms=mix_mechanisms,
            split_mechanisms=self.split_mechanisms)
        self.rng = rng or random.Random()
        self.current_effect = self.current_music = None
        self.pending_effect = self.pending_song = None
        self.current_mechanism = self.pending_mechanism = None
        self.current_closing = self.pending_closing = None
        self.paused = False
        self.sound_enabled = self.music_enabled = True
        self.current_music_ambient = self.pending_song_ambient = False
        self.current_music_group = self.pending_music_group = None
        self.level_music = None
        self.room_song_scope = None
        self.room_song_requested = False
        self.last_ui_hover_at = float('-inf')

    def play_ui(self, kind):
        if not self.sound_enabled:
            return
        now = time.perf_counter()
        if kind == 'hover':
            if now - self.last_ui_hover_at < 0.18:
                return
            self.last_ui_hover_at = now
        elif kind == 'click':
            self.last_ui_hover_at = now
        play = getattr(self.playback, 'play_ui', None)
        if play is not None:
            play(kind)

    def configure_level(self, level):
        self.level_music = {'bank': struct.unpack_from('>h', level, 0x2186)[0],
                            'groups': struct.unpack_from('>960h', level, 0x424a)}

    def available(self, cue):
        return cue in self.cues and bool(self.cues[cue].get("file"))

    def play_intro(self, resource_id, kind, offset=0):
        banked = scene_sound_key(resource_id, kind)
        cue = banked if banked in self.scene_cues else resource_id
        metadata = self.scene_cues.get(banked) if cue == banked else self.cues.get(cue)
        if not metadata or not metadata.get('file'):
            raise ValueError(f"Intro audio {resource_id} is missing; import the game again")
        bus = "music" if kind == 0 else "effect"
        if kind == 0:
            self.current_music = resource_id
            self.current_music_ambient = False
            self.pending_song = None
        else:
            if self.mix_effects:
                self.pending_effects.clear()
                self.playback.stop('effect')
            self.current_effect = resource_id
            self.pending_effect = None
        if offset:
            self.playback.play(bus, cue, offset=offset)
        else:
            self.playback.play(bus, cue)
        if self.paused:
            self.playback.pause(True)

    def add_sound(self, cue, actor_type=0):
        # Distinct effects mix; repeated cues coalesce. Mechanisms and the
        # comparison mode retain AddSound 5:4d84: smaller priorities win.
        if not self.available(cue) or (actor_type == 1 and cue in (0, 294, 295, 300)):
            return
        if self.mix_effects and cue not in MECHANISM_CUES:
            self.pending_effects[cue] = None
            return
        bus = "mechanism" if self.mix_mechanisms and cue in MECHANISM_CUES else "effect"
        pending = getattr(self, f"pending_{bus}")
        if pending is None or self.cues[cue]["priority"] <= self.cues[pending]["priority"]:
            setattr(self, f"pending_{bus}", cue)

    def add_song(self, cue, ambient=False):
        # AddSong 5:4d58 retains the first request in the current game frame.
        if self.pending_song is None and self.available(cue):
            self.pending_song = cue
            self.pending_song_ambient = ambient
            self.pending_music_group = None

    def room_song(self, location, cue=None):
        """Request a theme once per room visit and stop it on departure."""
        scope = (location, cue)
        if self.room_song_scope != scope:
            previous = self.room_song_scope[1] if self.room_song_scope is not None else None
            if previous is not None:
                if self.pending_song == previous:
                    self.pending_song = None
                    self.pending_song_ambient = False
                    self.pending_music_group = None
                if self.current_music == previous:
                    self.playback.stop('music')
                    self.current_music = None
                    self.current_music_ambient = False
                    self.current_music_group = None
            self.room_song_scope = scope
            self.room_song_requested = False
        if cue is not None and not self.room_song_requested and self.music_enabled:
            self.room_song_requested = True
            self.add_song(cue, ambient=True)

    def drain(self, state, audible=True, *, gate_events=None):
        attributed = self.split_mechanisms and gate_events is not None
        if attributed:
            if self.gate_events is None:
                self.gate_events = []
            if audible:
                self.gate_events.extend(event for event in gate_events
                                        if event.cue not in self.stopped_effects)
        for cue in state.sound_events:
            # A landing can stop the scream before its queued frame is drained.
            if (audible and cue not in self.stopped_effects
                    and not (attributed and cue in MECHANISM_CUES)):
                self.add_sound(cue, state.actor_type)
        state.sound_events.clear()

    @property
    def effect_busy(self):
        return (bool(self.pending_effects) or bool(self.gate_events)
                or any(self._effect_busy(bus) for bus in self.effect_buses)
                or self.mix_effects and bool(self.playback.playing_effects()))

    def _effect_busy(self, bus):
        return getattr(self, f"pending_{bus}") is not None or self.playback.busy(bus)

    def sound_playing(self, cue):
        return (cue in self.pending_effects
                or any(event.cue == cue for event in self.gate_events or ())
                or self.mix_effects and cue in self.playback.playing_effects()
                or any(getattr(self, f"pending_{bus}") == cue or
                       (getattr(self, f"current_{bus}") == cue and self.playback.busy(bus))
                       for bus in self.effect_buses))

    def song_playing(self, cue):
        return (self.pending_song == cue or
                (self.current_music == cue and self.playback.busy("music")))

    @property
    def music_busy(self):
        return self.pending_song is not None or self.playback.busy("music")

    def death_ready(self):
        if self.mix_effects and any(cue not in (272, 17, 192) for cue in
                                    (*self.pending_effects, *self.playback.playing_effects())):
            return False
        return all(getattr(self, f"current_{bus}") in (272, 17, 192)
                   or not self._effect_busy(bus) for bus in self.effect_buses)

    def death_song(self, method):
        self.add_song(self.manifest["death_cues"][method])

    def stop_sound(self, cue):
        self.stopped_effects.add(cue)
        self.pending_effects.pop(cue, None)
        if self.mix_effects:
            self.playback.stop_effect(cue)
        for bus in self.effect_buses:
            if getattr(self, f"pending_{bus}") == cue:
                setattr(self, f"pending_{bus}", None)
            if getattr(self, f"current_{bus}") == cue:
                self.playback.stop(bus)
                setattr(self, f"current_{bus}", None)

    def flush(self):
        if self.paused:
            return
        if self.gate_events is not None:
            self._prepare_gate_events()
        if self.mix_effects:
            # An empty swing and its contact are one event, not two layers.
            if any(cue in self.pending_effects for cue in (10, 12, 31)):
                self.pending_effects.pop(11, None)
            # Debris landing on a shooter plate is one impact. Keep its break
            # sound instead of stacking the trap's launch transient over it.
            if 26 in self.pending_effects:
                self.pending_effects.pop(65, None)
            playing = set(self.playback.playing_effects())
            for cue in self.pending_effects:
                if cue not in playing:
                    self.playback.play_effect(cue)
            self.pending_effects.clear()
        for bus in self.effect_buses:
            cue = getattr(self, f"pending_{bus}")
            setattr(self, f"pending_{bus}", None)
            if cue is None:
                continue
            current = getattr(self, f"current_{bus}")
            interrupt = not self.playback.busy(bus) or current is None
            if current is not None and not interrupt:
                rule = self.cues[current]
                interrupt = ((rule["mode"] == 2 or (rule["mode"] == 1 and cue != current))
                             and self.cues[cue]["priority"] <= rule["priority"])
            if interrupt:
                self.playback.play(bus, cue)
                setattr(self, f"current_{bus}", cue)
            elif cue == current == 17:
                sustain = getattr(self.playback, "sustain_gate", None)
                if sustain is not None:
                    sustain(bus) if bus == 'closing' else sustain()
        if self.pending_song is not None:
            self.current_music = self.pending_song
            self.current_music_ambient = self.pending_song_ambient
            self.current_music_group = self.pending_music_group
            self.pending_song = None
            self.pending_song_ambient = False
            self.playback.play("music", self.current_music)
            self.music_clock = [time.monotonic(), 0.0]
        self.stopped_effects.clear()

    def _prepare_gate_events(self):
        # Keep the native cue list untouched. Attribute before coalescing so
        # one gate's stop cannot discard another gate's movement in this tick.
        sources = {}
        for event in self.gate_events:
            previous = sources.get(event.source)
            if previous is None or previous.cue != 20:
                sources[event.source] = event
        self.gate_events = None
        for bus, opening in (('mechanism', True), ('closing', False)):
            cues = {event.cue for event in sources.values() if event.opening == opening}
            cue = next((item for item in (20, 17, 18) if item in cues), None)
            setattr(self, f'pending_{bus}', cue)
            if cue is None and getattr(self, f'current_{bus}') == 17:
                if self.playback.busy(bus):
                    release = getattr(self.playback, 'release_gate', None)
                    if release is not None:
                        release(bus)
                    else:
                        self.playback.stop(bus)
                setattr(self, f'current_{bus}', None)

    def ambient(self, room, row, column, fighting=False, alive=True, special=None,
                *, special_when_idle=False):
        if not self.music_enabled or not alive:
            return
        level = self.level_music or self.manifest["level_one"]
        bank = self.manifest["ambient"][level["bank"]]
        # PlayAmbient 5:4fd0-4ff4 disables combat selection for bank 5.
        fighting = fighting and bank["combat_group"] != -1
        if special is not None and (fighting or special_when_idle):
            # SpecialMusic 5:5388 replaces the combat group with one song,
            # e.g. BrgFight (119) on level five's bridge (5:5398-53bc).
            if self.music_busy and (self.current_music == special or self.pending_song is not None
                                    or not self.current_music_ambient):
                return
            self.add_song(special, ambient=True)
            if self.pending_song == special:
                self.pending_music_group = bank["combat_group"] if fighting else None
            return
        group = (bank["combat_group"] if fighting else
                 level["groups"][room * 30 + row * 10 + column]
                 if 0 <= room < 32 and 0 <= row < 3 and 0 <= column < 10 else 0)
        if not 0 <= group < len(bank["starts"]):
            return
        if self.music_busy:
            # TimeForNewAmbient 5:557e-5634 changes between exploration and
            # combat groups, but never interrupts a foreground song.
            combat = bank['combat_group']
            if (not self.current_music_ambient or self.pending_song is not None
                    or self.current_music_group is None or combat < 0
                    or (self.current_music_group >= combat) == (group >= combat)):
                return
        first, count = bank["starts"][group], bank["counts"][group]
        # Rnd 17:6e06 is inclusive. PlayAmbient 5:50c2 skips a repeat by
        # advancing one song, wrapping at the last index rather than rerolling.
        cue = first + self.rng.randrange(count + 1)
        if cue == self.current_music:
            cue = first if cue == first + count else cue + 1
        self.add_song(cue, ambient=True)
        if self.pending_song == cue:
            self.pending_music_group = group

    def set_sound_enabled(self, enabled):
        self.sound_enabled = bool(enabled)
        if not self.sound_enabled:
            stop = getattr(self.playback, 'stop_ui', None)
            if stop is not None:
                stop()
        # Keep the cue clock running while muted: death/retry waits on playback.
        for bus in (*getattr(self, 'effect_buses', ('effect',)), "music"):
            self.playback.set_volume(bus, 1.0 if self.sound_enabled else 0.0)

    def set_music_enabled(self, enabled):
        self.music_enabled = bool(enabled)
        if not self.music_enabled:
            if self.pending_song_ambient:
                self.pending_song = None
                self.pending_song_ambient = False
            if self.current_music_ambient:
                self.playback.stop("music")
                self.current_music = None
                self.current_music_ambient = False

    def pause(self, paused):
        clock = getattr(self, 'music_clock', None)
        if clock is not None and paused != self.paused:
            # [start of the running span, seconds played before it]
            if paused:
                clock[1] += time.monotonic() - clock[0]
                clock[0] = None
            else:
                clock[0] = time.monotonic()
        self.paused = paused
        self.playback.pause(paused)

    def music_elapsed(self):
        """Seconds the current game song has played, or None."""
        clock = getattr(self, 'music_clock', None)
        if clock is None or not self.playback.busy("music"):
            return None
        return clock[1] + (time.monotonic() - clock[0] if clock[0] is not None else 0)

    def reset(self, keep_music=False):
        """Stop every sound; with `keep_music`, the playing song continues."""
        self.room_song_scope = None
        self.room_song_requested = False
        for bus in self.effect_buses:
            self.playback.stop(bus)
        if not keep_music:
            self.playback.stop("music")
            self.current_music = None
        self.current_effect = None
        self.pending_effect = self.pending_song = None
        self.current_mechanism = self.pending_mechanism = None
        self.current_closing = self.pending_closing = None
        self.gate_events = None
        self.pending_effects.clear()
        self.stopped_effects.clear()
        self.current_music_ambient = self.pending_song_ambient = False
        self.current_music_group = self.pending_music_group = None

    def close(self):
        self.reset()
        self.playback.close()
