import io
import json
import os
from pathlib import Path
import random
import struct
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import wave

from pop2.audio import AudioEngine, MixerPlayback
from pop2.audio_formats import Sample, digitized_sound, mohawk_resources, standard_sound
from pop2.rebirth import DeathState


class TimedPlayback:
    """Deterministic MIDI event clock; SDL integration tests cover PCM tails."""

    def __init__(self, cues):
        self.cues = cues
        self.remaining = {"effect": 0, "music": 0}
        self.paused = False

    def play(self, bus, cue):
        self.remaining[bus] = self.cues[cue]["duration"]

    def busy(self, bus):
        return self.remaining[bus] > 1e-9

    def advance(self, interval):
        if not self.paused:
            for bus in self.remaining:
                self.remaining[bus] = max(0, self.remaining[bus] - interval)

    def stop(self, bus):
        self.remaining[bus] = 0

    def pause(self, paused):
        self.paused = paused

    def close(self):
        pass


class CueTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.playback = Mock()
        self.busy = {"effect": False, "music": False}
        self.playback.busy.side_effect = self.busy.__getitem__
        cues = {str(i): {"mode": 1, "priority": i, "file": f"{i}.wav"}
                for i in (7, 11, 12, 31, 38, 40, 41, 42, 43, 119, 294, 295, 300)}
        manifest = {"schema": 1, "cues": cues, "death_cues": [38] * 16,
                    "level_one": {"bank": 0, "groups": [0] * 960},
                    "ambient": [{"starts": [40], "counts": [3], "combat_group": -1}]}
        Path(self.directory.name, "manifest.json").write_text(json.dumps(manifest))
        self.audio = AudioEngine(self.directory.name, self.playback, random.Random(1))

    def test_pending_effect_uses_priority_and_current_effect_rejects_lower_priority(self):
        audio = self.audio
        audio.add_sound(294)
        audio.add_sound(12)
        audio.add_sound(31)
        audio.flush()
        self.playback.play.assert_called_once_with("effect", 12)
        self.busy["effect"] = True
        audio.add_sound(294)
        audio.flush()
        self.assertEqual(self.playback.play.call_count, 1)
        self.assertIsNone(audio.pending_effect)

    def test_mode_one_does_not_restart_itself_but_mode_two_can(self):
        audio = self.audio
        audio.add_sound(12)
        audio.flush()
        self.busy["effect"] = True
        audio.add_sound(12)
        audio.flush()
        self.assertEqual(self.playback.play.call_count, 1)
        audio.cues[12]["mode"] = 2
        audio.add_sound(12)
        audio.flush()
        self.assertEqual(self.playback.play.call_count, 2)

    def test_music_keeps_first_pending_request_and_has_a_separate_bus(self):
        self.audio.add_song(40)
        self.audio.add_song(41)
        self.audio.add_sound(12)
        self.audio.flush()
        self.assertEqual(self.audio.current_music, 40)
        self.assertEqual(self.audio.current_effect, 12)
        self.assertEqual(self.playback.play.call_count, 2)

    def test_drain_clears_offscreen_events_without_playing_them_later(self):
        state = SimpleNamespace(sound_events=[294, 12], actor_type=2)
        self.audio.drain(state, audible=False)
        self.audio.flush()
        self.assertEqual(state.sound_events, [])
        self.playback.play.assert_not_called()
        state.sound_events = [294]
        self.audio.drain(state)
        self.audio.flush()
        self.playback.play.assert_called_once_with("effect", 294)

    def test_suppressed_actor_footsteps_do_not_suppress_the_guards(self):
        self.audio.add_sound(294, actor_type=1)
        self.assertIsNone(self.audio.pending_effect)
        self.audio.add_sound(294, actor_type=2)
        self.assertEqual(self.audio.pending_effect, 294)

    def test_ambient_avoids_repeating_and_waits_for_current_song(self):
        audio = self.audio
        audio.current_music = 40
        audio.ambient(3, 1, 8)
        self.assertIn(audio.pending_song, (41, 42, 43))
        audio.flush()
        self.busy["music"] = True
        audio.ambient(6, 1, 5, fighting=True)
        self.assertIsNone(audio.pending_song)
        self.busy["music"] = False
        audio.ambient(6, 1, 5, fighting=True)
        self.assertIn(audio.pending_song, (40, 41, 42, 43))

    def test_ambient_includes_last_song_and_wraps_repeats(self):
        self.audio.rng = Mock()
        self.audio.rng.randrange.return_value = 3
        self.audio.ambient(3, 1, 8)
        self.assertEqual(self.audio.pending_song, 43)
        self.audio.flush()
        self.audio.ambient(3, 1, 8)
        self.assertEqual(self.audio.pending_song, 40)

    def test_dead_player_does_not_restart_ambient_music(self):
        self.audio.ambient(3, 1, 8, alive=False)
        self.assertIsNone(self.audio.pending_song)

    def test_pause_freezes_playback_and_does_not_flush_a_new_cue(self):
        self.audio.add_sound(12)
        self.audio.pause(True)
        self.audio.flush()
        self.playback.play.assert_not_called()
        self.audio.pause(False)
        self.audio.flush()
        self.playback.play.assert_called_once_with("effect", 12)

    def test_reset_cancels_both_current_and_pending_audio(self):
        self.audio.add_sound(12)
        self.audio.add_song(40)
        self.audio.reset()
        self.audio.flush()
        self.playback.play.assert_not_called()
        self.assertIsNone(self.audio.current_music)
        self.assertIsNone(self.audio.current_effect)

    def test_master_mute_changes_both_volumes_without_stopping_the_cue_clock(self):
        self.audio.add_song(38)
        self.audio.flush()
        self.busy["music"] = True
        self.audio.set_sound_enabled(False)
        self.assertFalse(self.audio.sound_enabled)
        self.playback.set_volume.assert_any_call("music", 0.0)
        self.playback.set_volume.assert_any_call("effect", 0.0)
        self.playback.stop.assert_not_called()
        self.assertTrue(self.audio.music_busy)
        self.audio.reset()
        self.assertFalse(self.audio.sound_enabled)
        self.audio.set_sound_enabled(True)
        self.playback.set_volume.assert_any_call("music", 1.0)
        self.playback.set_volume.assert_any_call("effect", 1.0)

    def test_music_toggle_cancels_only_ambient_and_preserves_effects(self):
        self.audio.ambient(3, 1, 8)
        self.audio.add_sound(12)
        self.audio.set_music_enabled(False)
        self.assertIsNone(self.audio.pending_song)
        self.audio.flush()
        self.playback.play.assert_called_once_with("effect", 12)
        self.audio.ambient(3, 1, 8)
        self.assertIsNone(self.audio.pending_song)
        self.audio.reset()
        self.assertFalse(self.audio.music_enabled)
        self.audio.set_music_enabled(True)
        self.audio.ambient(3, 1, 8)
        self.audio.flush()
        self.audio.set_music_enabled(False)
        self.playback.stop.assert_called_with("music")
        self.assertIsNone(self.audio.current_music)

    def test_disabling_ambient_preserves_death_music_current_or_pending(self):
        self.audio.death_song(14)
        self.audio.set_music_enabled(False)
        self.assertEqual(self.audio.pending_song, 38)
        self.audio.flush()
        self.audio.set_music_enabled(False)
        self.playback.stop.assert_not_called()
        self.assertEqual(self.audio.current_music, 38)

    def test_stop_sound_cancels_only_the_matching_current_or_pending_effect(self):
        self.audio.add_sound(12)
        self.audio.flush()
        self.busy["effect"] = True
        self.audio.add_sound(31)
        self.audio.stop_sound(31)
        self.assertIsNone(self.audio.pending_effect)
        self.assertEqual(self.audio.current_effect, 12)
        self.playback.stop.assert_not_called()
        self.audio.stop_sound(12)
        self.playback.stop.assert_called_once_with("effect")
        self.assertIsNone(self.audio.current_effect)

    def test_death_waits_for_real_audio_not_a_literal_duration(self):
        death = DeathState()
        death.begin(14)
        self.busy["effect"] = True
        death.advance(185, 100, self.audio)
        self.assertEqual(death.counter, 0)
        self.busy["effect"] = False
        for _ in range(7):
            death.advance(185, 0, self.audio)
        self.assertTrue(death.can_restart)
        self.assertEqual(self.audio.pending_song, 38)
        death.advance(185, 1000, self.audio)
        self.assertFalse(death.prompt_visible)
        self.audio.flush()
        self.busy["music"] = True
        death.advance(185, 1000, self.audio)
        self.assertFalse(death.prompt_visible)
        self.busy["music"] = False
        death.advance(185, 0, self.audio)
        self.assertTrue(death.prompt_visible)


class FormatTests(unittest.TestCase):
    def test_pcm_wav_preserves_samples_rate_and_channel_count(self):
        sample = Sample(bytes((0, 64, 128, 255)), 11127)
        with wave.open(io.BytesIO(sample.wav())) as reader:
            self.assertEqual((reader.getframerate(), reader.getnchannels()), (11127, 1))
            self.assertEqual(reader.readframes(4), sample.pcm)

    def test_sustain_metadata_is_opt_in_and_does_not_modify_pcm(self):
        sample = Sample(b"\x80" * 8, 22050, loop_start=2, loop_end=7)
        self.assertNotIn(b"smpl", sample.wav())
        self.assertIn(b"smpl", sample.wav(sustain=True))
        with wave.open(io.BytesIO(sample.wav(sustain=True))) as reader:
            self.assertEqual(reader.readframes(8), sample.pcm)

    def test_mohawk_pcm_data_and_truncation(self):
        header = struct.pack(">IHBB", 11025 << 16, 4, 8, 1) + bytes(12)
        chunk = b"Data" + struct.pack(">I", len(header) + 4) + header + b"abcd"
        sample = digitized_sound(chunk)
        self.assertEqual((sample.pcm, sample.rate), (b"abcd", 11025))
        with self.assertRaises(ValueError):
            digitized_sound(chunk[:-1])

    def test_standard_sound_header_and_truncation(self):
        data = struct.pack(">HHHHHI", 2, 0, 1, 0x8051, 0, 14)
        data += struct.pack(">5IBB", 0, 4, 22050 << 16, 0, 0, 0, 67) + b"abcd"
        sample = standard_sound(data)
        self.assertEqual((sample.pcm, sample.base_note), (b"abcd", 67))
        with self.assertRaises(ValueError):
            standard_sound(data[:-1])

    def test_invalid_mohawk_header_and_tables_are_rejected(self):
        for data in (b"", b"MHWK" + bytes(4) + b"RSRC" + bytes(16)):
            with self.assertRaises(ValueError):
                mohawk_resources(data)


class SdlPlaybackTests(unittest.TestCase):
    def test_real_sdl_channels_pause_resume_and_stop_independently(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "sample.wav").write_bytes(Sample(b"\x90" * 800, 8000).wav())
            cues = {1: {"file": "sample.wav"}}
            with patch.dict(os.environ, {"SDL_AUDIODRIVER": "dummy"}):
                playback = MixerPlayback(directory, cues)
                try:
                    # SDL_mixer uses tick zero as its unpaused sentinel.
                    time.sleep(0.02)
                    playback.play("music", 1)
                    playback.play("effect", 1)
                    playback.set_volume("music", 0.0)
                    playback.play("music", 1)
                    self.assertEqual(playback.channels["music"].get_volume(), 0.0)
                    self.assertTrue(playback.busy("music"))
                    self.assertTrue(playback.busy("effect"))
                    playback.pause(True)
                    time.sleep(0.16)
                    self.assertTrue(playback.busy("music"))
                    playback.stop("effect")
                    self.assertFalse(playback.busy("effect"))
                    playback.pause(False)
                    time.sleep(0.16)
                    self.assertFalse(playback.busy("music"))
                finally:
                    playback.close()


if __name__ == "__main__":
    unittest.main()
