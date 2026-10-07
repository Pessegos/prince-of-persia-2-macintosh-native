import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import wave

import mido
import numpy as np

from tools.extract_audio import audio_tables, render_midi


class AudioTableTests(unittest.TestCase):
    def test_rooftop_pool_has_one_group_not_three_adjacent_tables(self):
        data = bytearray(0x5000)
        base = len(data)
        for cue in range(301):
            struct.pack_into(">4h", data, base - 0x40a0 + cue * 8, 0, 0, 0, -1)
        struct.pack_into(">4h", data, base - 0x40a0 + 40 * 8, 0, 1, 0, 0)
        struct.pack_into(">i", data, base - 0x40fe + 5 * 4, -0x4126)
        struct.pack_into(">i", data, base - 0x40e2 + 5 * 4, -0x4124)
        struct.pack_into(">3h", data, base - 0x4126, 40, 3, 73)
        struct.pack_into(">h", data, base - 0x40c6 + 5 * 2, -1)
        with patch("tools.extract_audio.expand_a5_data", return_value=bytes(data)):
            manifest = audio_tables({})
        self.assertEqual(manifest["ambient"][5],
                         {"starts": [40], "counts": [3], "combat_group": -1})
        self.assertEqual(manifest["cues"],
                         {"40": {"mode": 0, "priority": 1, "kind": "midi"}})


class MidiRenderingTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.synth = self.directory / "synth"
        self.synth.mkdir()
        (self.synth / "smssynth.exe").touch()
        song = mido.MidiFile(ticks_per_beat=96)
        song.tracks.append(mido.MidiTrack([
            mido.MetaMessage("set_tempo", tempo=666667),
            mido.Message("program_change", program=12),
            mido.Message("note_on", note=60, velocity=83, time=1),
            mido.Message("note_off", note=60, time=95),
            mido.MetaMessage("set_tempo", tempo=600001),
            mido.Message("note_on", note=64, velocity=91, time=7),
            mido.Message("note_off", note=64, time=89),
        ]))
        song.save(self.directory / "original.mid")
        self.samples = np.array((0, 1, -1, 0.125), dtype="<f4")

    def synthesize(self, arguments, **kwargs):
        self.assertEqual(kwargs["cwd"], self.directory)
        synth_path = Path(kwargs["env"]["PATH"].split(os.pathsep)[0])
        self.assertTrue(synth_path.samefile(self.synth))
        self.assertNotIn("--silent", arguments)
        payload = self.samples.tobytes()
        fmt = struct.pack("<HHIIHH", 3, 2, 48000, 384000, 8, 32)
        # Reproduce upstream's doubled length fields, not its actual payload.
        data = b"RIFF" + struct.pack("<I", 36 + len(payload) * 2) + b"WAVE"
        data += b"fmt " + struct.pack("<I", 16) + fmt
        data += b"data" + struct.pack("<I", len(payload) * 2) + payload
        (self.directory / "synthesis.wav").write_bytes(data)
        return Mock(returncode=0)

    def render(self):
        with patch("tools.extract_audio.subprocess.run", side_effect=self.synthesize):
            return render_midi(self.directory, "original.mid", "song.wav", self.synth)

    def test_midi_retiming_preserves_absolute_events_and_velocities(self):
        self.render()

        def events(path):
            elapsed, result = 0, []
            for message in mido.MidiFile(path):
                elapsed += message.time
                if not message.is_meta:
                    result.append((elapsed, message.copy(time=0)))
            return result

        original = events(self.directory / "original.mid")
        playback = events(self.directory / "playback.mid")
        self.assertEqual(len(original), len(playback))
        for (before, source), (after, result) in zip(original, playback):
            self.assertEqual(source, result)
            self.assertLessEqual(abs(before - after), 0.0005)

    def test_actual_float_payload_becomes_pcm_without_clipping_or_normalization(self):
        duration = self.render()
        with wave.open(str(self.directory / "song.wav")) as reader:
            self.assertEqual(reader.getparams()[:4], (2, 2, 48000, 2))
            actual = np.frombuffer(reader.readframes(2), dtype="<i2")
            np.testing.assert_array_equal(actual, (0, 8191, -8191, 1024))
        self.assertEqual(duration, 2 / 48000)
        self.assertFalse((self.directory / "synthesis.wav").exists())

    def test_nonfinite_or_unexpected_levels_are_rejected_before_pcm_conversion(self):
        for value in (float("nan"), float("inf"), 4.1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.samples[0] = value
                self.render()
        self.assertFalse((self.directory / "song.wav").exists())

    def test_missing_renderer_and_timeout_have_actionable_errors(self):
        with self.assertRaisesRegex(ValueError, "bundled MIDI renderer"):
            render_midi(self.directory, "original.mid", "song.wav", self.directory)
        with (patch("tools.extract_audio.subprocess.run",
                    side_effect=subprocess.TimeoutExpired("smssynth", 120)),
              self.assertRaisesRegex(ValueError, "timed out")):
            render_midi(self.directory, "original.mid", "song.wav", self.synth)
