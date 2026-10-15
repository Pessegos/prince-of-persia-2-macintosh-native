import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import mido

from tools.extract_attract import RecordedSimulation, extract_credits_music, jump_targets


class AttractExtractionTests(unittest.TestCase):
    def test_recording_hooks_cover_services_and_traps_without_overlapping_device_ranges(self):
        resources = {'CODE': {0: {'data': b''},
                              4: {'data': bytes.fromhex('4e71 a029 a123 a8a8')},
                              8: {'data': bytes.fromhex('a029 a8a8')}}}
        ranges = RecordedSimulation.hook_ranges(resources)
        self.assertEqual(len(ranges), len(set(ranges)))
        for address in (0x40002, 0x40006, 0x43098, RecordedSimulation.SECT_RECT, 0x80000, 0x80002):
            with self.subTest(address=address):
                self.assertEqual(sum(start <= address <= end for start, end in ranges), 1)
        for address in (0x40000, 0x40004):
            self.assertFalse(any(start <= address <= end for start, end in ranges))

    def test_jump_table_is_recovered_from_application_not_research_files(self):
        code = struct.pack(">4I4H", 0x1000, 0x6000, 8, 0x20, 12, 0x3f3c, 1, 0xa9f0)
        self.assertEqual(jump_targets(code, {1: {"data": bytes(32)}}), [(0x22, 0x10010)])

    def test_invalid_jump_table_is_rejected(self):
        valid = struct.pack(">4I4H", 0x1000, 0x6000, 8, 0x20, 12, 0x3f3c, 1, 0xa9f0)
        for code in (b"", valid[:-1], valid[:-2] + b"\0\0"):
            with self.subTest(code=code), self.assertRaises(ValueError):
                jump_targets(code, {1: {"data": bytes(32)}})
        with self.assertRaises(ValueError):
            jump_targets(valid, {1: {"data": bytes(12)}})

    def test_credits_music_uses_original_archive_and_preserves_manifest(self):
        midi = mido.MidiFile()
        midi.tracks.append(mido.MidiTrack([mido.MetaMessage("end_of_track", time=480)]))
        stream = io.BytesIO()
        midi.save(file=stream)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            audio = path / "audio"
            audio.mkdir()
            manifest = audio / "manifest.json"
            manifest.write_text(json.dumps({"schema": 1, "cues": {"40": {"file": "roof.wav"}}}))
            with (
                patch("tools.extract_attract.get_data_fork", return_value=b"archive") as fork,
                patch("tools.extract_attract.mohawk_resources", return_value={"MIDI": {10019: stream.getvalue()}}),
                patch("tools.extract_attract.render_midi", return_value=.75) as render,
            ):
                extract_credits_music(b"image", path)
            fork.assert_called_once_with(b"image", "MIDISnd.dat")
            render.assert_called_once_with(audio, "credits-10019.mid", "credits-10019.wav")
            result = json.loads(manifest.read_text())
            self.assertEqual(result["cues"]["40"], {"file": "roof.wav"})
            self.assertEqual(result["cues"]["10019"]["duration"], .5)
            self.assertEqual(result["cues"]["10019"]["playback_duration"], .75)


if __name__ == "__main__":
    unittest.main()
