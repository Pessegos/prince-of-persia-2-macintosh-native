import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import wave

import mido

from pop2.audio_formats import Sample
import tools.extract_intro as extractor


def coordinator(entry):
    code = bytearray.fromhex(
        "4e56fff8 486efff8 4ead10f2 584f 486efff8 3f3c000f 486dadc2"
    )
    call = entry + len(code)
    code.extend(b"\x4e\xba" + struct.pack(">h", 0xb32 - call - 2))
    code.extend(bytes.fromhex("4fef000a 42a7 3f3c61b2 3f3cffff 4ead0fa2 504f 4e5e 4e75"))
    return code


class IntroExtractionTests(unittest.TestCase):
    def test_cached_dissolve_offsets_recover_order_independent_of_framebuffer_stride(self):
        offsets = [(3 * 528 + 8, 0), (2 * 528 + 4, 0),
                   (3 * 528 + 4, 0), (2 * 528 + 8, 0), (2 * 528 + 4, 0)]
        data = struct.pack(">6h2i", 2, 4, 2, 4, 4, 12, 0, 0)
        data += b"".join(struct.pack(">2I", *pair) for pair in offsets)
        self.assertEqual(extractor.recover_dissolve(data),
                         {"rect": [2, 4, 4, 12], "order": [3, 0, 2, 1]})
        for corrupt in (data[:-1], data[:20] + data[20:28] * 5):
            with self.assertRaises(ValueError):
                extractor.recover_dissolve(corrupt)

    def test_missing_optional_macintosh_dissolve_cache_is_allowed(self):
        with patch.object(extractor, "get_resource_fork", side_effect=FileNotFoundError):
            self.assertIsNone(extractor.extract_dissolve(b"image"))

    def test_original_coordinator_calls_are_recovered_without_macintosh_services(self):
        code = bytearray(0x5100)
        for entry in (0x45c2, 0x4ee8):
            body = coordinator(entry)
            code[entry:entry + len(body)] = body
        forks = {b"program": {"CODE": {15: {"data": bytes(code)}}}, b"nis": {"SHAP": {}}}
        with (
            patch.object(extractor, "parse_resource_fork", side_effect=forks.__getitem__),
            patch.object(extractor, "expand_a5_data", return_value=bytes(0x6000)),
        ):
            operations = extractor.recover_scenes(b"program", b"nis")
        self.assertEqual([item["op"] for item in operations],
                         ["fill", "sound", "title", "fade_both", "fill", "sound"])
        self.assertEqual(operations[0]["args"], [15, [0, 0, 384, 510]])
        self.assertEqual(operations[1]["args"], [25010, 0])
        self.assertGreater(operations[0]["pc"], 0x45c2)

    def test_unrecognized_coordinator_version_fails_explicitly(self):
        forks = {b"program": {"CODE": {15: {"data": bytes(0x5100)}}}, b"nis": {"SHAP": {}}}
        with (
            patch.object(extractor, "parse_resource_fork", side_effect=forks.__getitem__),
            patch.object(extractor, "expand_a5_data", return_value=bytes(0x6000)),
            self.assertRaisesRegex(ValueError, "Unsupported Macintosh opening coordinator"),
        ):
            extractor.recover_scenes(b"program", b"nis")

    def test_audio_import_preserves_markers_and_pcm_headroom(self):
        midi = mido.MidiFile()
        midi.tracks.append(mido.MidiTrack([
            mido.MetaMessage("set_tempo", tempo=500000),
            mido.MetaMessage("cue_marker", text="a", time=480),
            mido.MetaMessage("end_of_track", time=480),
        ]))
        stream = io.BytesIO()
        midi.save(file=stream)
        banks = {b"NISMIDI.dat": {"MIDI": {25010: stream.getvalue()}},
                 b"NISDIGI.dat": {"snd ": {27001: b"voice"}}, b"DigiSnd.dat": {"snd ": {}}}
        operations = [{"op": "sound", "args": [25010, 0]}, {"op": "sound", "args": [27001, 1]}]
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            audio = directory / "audio"
            audio.mkdir()
            (audio / "manifest.json").write_text('{"schema":1,"cues":{}}')
            def render(_directory, _name, output):
                output.write_bytes(Sample(b"\0\0" * 48000, 48000, 1, 2).wav())
                return 1
            with (
                patch.object(extractor, "recover_scenes", return_value=operations),
                patch.object(extractor, "get_data_fork", side_effect=lambda _, name: name.encode()),
                patch.object(extractor, "mohawk_resources", side_effect=banks.__getitem__),
                patch.object(extractor, "digitized_sound", return_value=Sample(bytes((0, 128, 255)), 11025)),
                patch.object(extractor, "render_midi", side_effect=render),
                patch.object(extractor, "parse_resource_fork", return_value={}),
                patch.object(extractor, "expand_a5_data", return_value=bytes(0x6000)),
            ):
                extractor.extract_intro(b"image", b"program", b"nis", directory)
            result = json.loads((directory / "intro.json").read_text())
            self.assertEqual(result["audio"]["25010"]["markers"], {"a": .5})
            cues = json.loads((audio / "manifest.json").read_text())["cues"]
            self.assertEqual(cues["25010"]["kind"], "midi")
            self.assertEqual(cues["25010"]["duration"], 1)
            self.assertEqual(cues["25010"]["playback_duration"], 1)
            self.assertEqual(cues["27001"]["kind"], "pcm")
            self.assertEqual(cues["27001"]["source_archive"], "NISDIGI.dat")
            self.assertEqual(cues["27001"]["resource_id"], 27001)
            with wave.open(str(audio / "intro-27001.wav")) as sound:
                self.assertEqual(sound.getframerate(), 11025)
                self.assertEqual(struct.unpack("<3h", sound.readframes(3)), (-8192, 0, 8128))


if __name__ == "__main__":
    unittest.main()
