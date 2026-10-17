"""Native cue arbitration with SDL playback, independent of animation timing."""

import json
import os
from pathlib import Path
import random
import struct

from pop2.paths import ASSET_DIR
from pop2.audio_release import PcmRelease, seamless_loop


class MixerPlayback:
    def __init__(self, directory, cues):
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        from pygame import mixer

        self.mixer = mixer
        try:
            mixer.init(frequency=48000, size=-16, channels=2, buffer=512)
        except mixer.error as error:
            raise RuntimeError(f"Cannot open the sound device. Check Windows audio settings: {error}") from error
        mixer.set_num_channels(3)
        self.channels = {"effect": mixer.Channel(0), "music": mixer.Channel(1)}
        self.gate_tail = mixer.Channel(2)
        self.effect_channel, self.tail_channel = 0, 2
        self.sounds = {cue: mixer.Sound(str(Path(directory) / item["file"]))
                       for cue, item in cues.items() if item.get("file")}
        self.gate_release = PcmRelease(mixer) if 17 in self.sounds and 18 in self.sounds else None
        if self.gate_release is not None:
            rate, _bits, channels = mixer.get_init()
            original = self.sounds[17]
            self.gate_lifetime = max(1, round(original.get_length() * 1000))
            self.sounds[17] = mixer.Sound(buffer=seamless_loop(
                original.get_raw(), channels, rate * 12 // 1000))

    def sustain_gate(self):
        channel = self.channels["effect"]
        if (self.gate_release is not None and channel.get_busy()
                and channel.get_sound() is self.sounds[17]):
            # Renew only while the controller still requests movement. A lost
            # stop cue must not leave an infinite stone sound behind.
            self.gate_release.expire(self.effect_channel, self.gate_lifetime)

    def play(self, bus, cue, offset=0):
        sound = self.sounds[cue]
        if offset:
            rate, bits, channels = self.mixer.get_init()
            frame_size = abs(bits) // 8 * channels
            start = int(max(0, offset) * rate) * frame_size
            remaining = sound.get_raw()[start:]
            if not remaining:
                self.stop(bus)
                return
            sound = self.mixer.Sound(buffer=remaining)
        if (bus == "effect" and cue == 18 and self.channels[bus].get_busy()
                and self.channels[bus].get_sound() is self.sounds.get(17)):
            # Fade PCM samples, not SDL's stepped per-buffer channel volume.
            self.gate_tail.stop()
            self.gate_tail.set_volume(self.channels[bus].get_volume())
            self.gate_release.start(self.effect_channel)
            self.channels[bus], self.gate_tail = self.gate_tail, self.channels[bus]
            self.effect_channel, self.tail_channel = self.tail_channel, self.effect_channel
        elif bus == "effect":
            self.gate_tail.stop()
        if bus == "effect" and self.gate_release is not None:
            self.gate_release.cancel(self.effect_channel)
        if bus == "effect" and cue == 17 and not offset and self.gate_release is not None:
            self.channels[bus].play(sound, loops=-1)
            self.sustain_gate()
        else:
            self.channels[bus].play(sound)

    def busy(self, bus):
        return self.channels[bus].get_busy()

    def stop(self, bus):
        self.channels[bus].stop()
        if bus == "effect":
            self.gate_tail.stop()
            if self.gate_release is not None:
                self.gate_release.cancel(self.effect_channel)
                self.gate_release.cancel(self.tail_channel)

    def set_volume(self, bus, volume):
        self.channels[bus].set_volume(volume)
        if bus == "effect":
            self.gate_tail.set_volume(volume)
            if not volume:
                self.gate_tail.stop()

    def pause(self, paused):
        for channel in (*self.channels.values(), self.gate_tail):
            (channel.pause if paused else channel.unpause)()

    def close(self):
        for channel in (*self.channels.values(), self.gate_tail):
            channel.stop()
        if self.gate_release is not None:
            self.gate_release.cancel(self.effect_channel)
            self.gate_release.cancel(self.tail_channel)
        self.mixer.quit()


class AudioEngine:
    def __init__(self, directory=ASSET_DIR / "audio", playback=None, rng=None):
        directory = Path(directory)
        self.manifest = json.loads((directory / "manifest.json").read_text(encoding="ascii"))
        if self.manifest.get("schema") != 1:
            raise ValueError("Game audio needs to be imported again")
        self.cues = {int(key): value for key, value in self.manifest["cues"].items()}
        self.playback = playback or MixerPlayback(directory, self.cues)
        self.rng = rng or random.Random()
        self.current_effect = self.current_music = None
        self.pending_effect = self.pending_song = None
        self.paused = False
        self.sound_enabled = self.music_enabled = True
        self.current_music_ambient = self.pending_song_ambient = False
        self.current_music_group = self.pending_music_group = None
        self.level_music = None

    def configure_level(self, level):
        self.level_music = {'bank': struct.unpack_from('>h', level, 0x2186)[0],
                            'groups': struct.unpack_from('>960h', level, 0x424a)}

    def available(self, cue):
        return cue in self.cues and bool(self.cues[cue].get("file"))

    def play_intro(self, resource_id, kind, offset=0):
        if not self.available(resource_id):
            raise ValueError(f"Intro audio {resource_id} is missing; import the game again")
        bus = "music" if kind == 0 else "effect"
        if kind == 0:
            self.current_music = resource_id
            self.current_music_ambient = False
            self.pending_song = None
        else:
            self.current_effect = resource_id
            self.pending_effect = None
        if offset:
            self.playback.play(bus, resource_id, offset=offset)
        else:
            self.playback.play(bus, resource_id)
        if self.paused:
            self.playback.pause(True)

    def add_sound(self, cue, actor_type=0):
        # AddSound 5:4d84: one pending effect; smaller priorities win.
        if not self.available(cue) or (actor_type == 1 and cue in (0, 294, 295, 300)):
            return
        if (self.pending_effect is None
                or self.cues[cue]["priority"] <= self.cues[self.pending_effect]["priority"]):
            self.pending_effect = cue

    def add_song(self, cue, ambient=False):
        # AddSong 5:4d58 retains the first request in the current game frame.
        if self.pending_song is None and self.available(cue):
            self.pending_song = cue
            self.pending_song_ambient = ambient
            self.pending_music_group = None

    def drain(self, state, audible=True):
        for cue in state.sound_events:
            if audible:
                self.add_sound(cue, state.actor_type)
        state.sound_events.clear()

    @property
    def effect_busy(self):
        return self.pending_effect is not None or self.playback.busy("effect")

    def sound_playing(self, cue):
        return (self.pending_effect == cue or
                (self.current_effect == cue and self.playback.busy("effect")))

    def song_playing(self, cue):
        return (self.pending_song == cue or
                (self.current_music == cue and self.playback.busy("music")))

    @property
    def music_busy(self):
        return self.pending_song is not None or self.playback.busy("music")

    def death_ready(self):
        return self.current_effect in (272, 17, 192) or not self.effect_busy

    def death_song(self, method):
        self.add_song(self.manifest["death_cues"][method])

    def stop_sound(self, cue):
        if self.pending_effect == cue:
            self.pending_effect = None
        if self.current_effect == cue:
            self.playback.stop("effect")
            self.current_effect = None

    def flush(self):
        if self.paused:
            return
        cue = self.pending_effect
        self.pending_effect = None
        if cue is not None:
            current = self.current_effect
            interrupt = not self.playback.busy("effect") or current is None
            if current is not None and not interrupt:
                rule = self.cues[current]
                interrupt = ((rule["mode"] == 2 or (rule["mode"] == 1 and cue != current))
                             and self.cues[cue]["priority"] <= rule["priority"])
            if interrupt:
                self.playback.play("effect", cue)
                self.current_effect = cue
            elif cue == current == 17:
                sustain = getattr(self.playback, "sustain_gate", None)
                if sustain is not None:
                    sustain()
        if self.pending_song is not None:
            self.current_music = self.pending_song
            self.current_music_ambient = self.pending_song_ambient
            self.current_music_group = self.pending_music_group
            self.pending_song = None
            self.pending_song_ambient = False
            self.playback.play("music", self.current_music)

    def ambient(self, room, row, column, fighting=False, alive=True):
        if not self.music_enabled or not alive:
            return
        level = self.level_music or self.manifest["level_one"]
        bank = self.manifest["ambient"][level["bank"]]
        # PlayAmbient 5:4fd0-4ff4 disables combat selection for bank 5.
        fighting = fighting and bank["combat_group"] != -1
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
        # Keep the cue clock running while muted: death/retry waits on playback.
        for bus in ("effect", "music"):
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
        self.paused = paused
        self.playback.pause(paused)

    def reset(self):
        self.playback.stop("effect")
        self.playback.stop("music")
        self.current_effect = self.current_music = None
        self.pending_effect = self.pending_song = None
        self.current_music_ambient = self.pending_song_ambient = False
        self.current_music_group = self.pending_music_group = None

    def close(self):
        self.reset()
        self.playback.close()
