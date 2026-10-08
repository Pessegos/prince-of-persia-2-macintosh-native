import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from PIL import Image

from pop2.intro import (
    IntroPlayer, ScriptAnimation, fade_ticks, indexed_shape, palette_colors,
    read_program, text_strings,
)


def instruction(opcode, *args):
    return bytes((opcode, 2 + len(args) * 2)) + struct.pack(f">{len(args)}h", *args)


def script(*commands):
    payload = b"".join(commands)
    return struct.pack(">I", len(payload)) + payload


def player(*operations, audio=None):
    sounds = {"25010": {"duration": 4, "markers": {"a": 1.25}, "kind": 0},
              "27001": {"duration": 2, "markers": {}, "kind": 1}}
    assets = SimpleNamespace(
        program={"operations": [{"op": op, "args": list(args)} for op, *args in operations],
                 "audio": sounds},
        palettes={1: {1: (120, 80, 20)}},
        shapes={1: Image.frombytes("L", (2, 1), b"\0\1")},
    )
    return IntroPlayer(assets, audio)


class IntroFormatTests(unittest.TestCase):
    def test_raw_shape_preserves_zero_and_discards_stride_padding(self):
        data = struct.pack(">HhhH4x", 0, 4, 2, 1) + b"\0\1\xff\xff"
        self.assertEqual(indexed_shape(data).tobytes(), b"\0\1")

    def test_compressed_shape_decodes_literal_and_repeat_runs(self):
        row = bytes((1, 2, 3, 129, 4))
        data = struct.pack(">HhhH4x", 256, 4, 4, 1) + struct.pack(">H", len(row)) + row + b"\xff\xff"
        self.assertEqual(indexed_shape(data).tobytes(), bytes((2, 3, 4, 4)))

    def test_bad_shape_row_is_rejected(self):
        data = struct.pack(">HhhH4x", 256, 4, 4, 1) + b"\0\2\0\2"
        with self.assertRaises(ValueError):
            indexed_shape(data)

    def test_palette_indices_are_not_assumed_contiguous(self):
        self.assertEqual(palette_colors(b"\0\2\1\2\3\x80\4\5\6\xff"),
                         {128: (1, 2, 3), 255: (4, 5, 6)})

    def test_text_count_is_a_byte_and_strings_are_null_terminated(self):
        self.assertEqual(text_strings(b"\2first\rline\0second\0"), ["first\rline", "second"])
        with self.assertRaises(ValueError):
            text_strings(b"\2one\0")

    def test_animation_layer_shape_position_flags_and_native_ticks(self):
        animation = ScriptAnimation(script(
            instruction(4, 5), instruction(5, 1, 360), instruction(6, 1, -7, 20),
            instruction(7, 1, 0), instruction(1), instruction(6, 1, 9, 30),
            instruction(1), instruction(0),
        ))
        animation.advance(0)
        self.assertEqual(animation.layers[0], [360, -7, 20, 0])
        animation.advance(4)
        self.assertEqual(animation.layers[0][1], -7)
        animation.advance(5)
        self.assertEqual(animation.layers[0][1:3], [9, 30])
        animation.advance(10)
        self.assertTrue(animation.done)

    def test_unknown_opcode_and_invalid_layer_are_rejected(self):
        for command in (instruction(8), instruction(5, 0, 1)):
            with self.subTest(command=command), self.assertRaises(ValueError):
                ScriptAnimation(script(command, instruction(0))).advance(0)

    def test_fade_duration_follows_original_percent_step_and_tick_flags(self):
        self.assertEqual(fade_ticks(0x40001), 25)
        self.assertEqual(fade_ticks(0x90001), 100)
        self.assertEqual(fade_ticks(0x20002), 100)

    def test_program_schema_and_opcode_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intro.json"
            for data in ({"schema": 0}, {"schema": 1, "audio": {}, "operations": []},
                         {"schema": 1, "audio": {}, "operations": [{"op": "unknown", "args": []}]}):
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    read_program(path)


class IntroPlaybackTests(unittest.TestCase):
    def test_cue_and_voice_waits_use_original_audio_clock_without_a_sound_device(self):
        p = player(("sound", 25010, 0), ("cue", 97), ("sound", 27001, 1),
                   ("wait_current", 1), ("wait", 60))
        p.advance(1.24)
        self.assertNotIn(1, p.playing)
        p.advance(.01)
        self.assertEqual(p.playing[1][1], 1.25)
        p.advance(2)
        self.assertFalse(p.done)
        p.advance(1)
        self.assertTrue(p.done)
        self.assertAlmostEqual(p.time, 4.25)

    def test_timers_include_time_spent_in_intervening_transitions(self):
        p = player(("timer", 0, 120), ("dissolve", 30), ("wait_timer", 0))
        p.advance(1.99)
        self.assertFalse(p.done)
        p.advance(.01)
        self.assertTrue(p.done)
        self.assertAlmostEqual(p.time, 2)

    def test_unrelated_sound_wait_does_not_wait_on_replacement(self):
        p = player(("sound", 27001, 1), ("wait_sound", 999, 1))
        self.assertTrue(p.done)
        self.assertEqual(p.time, 0)

    def test_shape_transparency_copy_and_clip(self):
        p = player(("fill", 3, [0, 0, 384, 512]), ("shape", 1, 0, 0, 16),
                   ("clip", [0, 1, 1, 2]), ("shape", 1, 1, 0, 0),
                   ("copy", [0, 0, 384, 512]), ("wait", 1))
        self.assertEqual([p.display.getpixel((x, 0)) for x in range(3)], [3, 0, 3])

    def test_fill_rectangles_are_half_open(self):
        p = player(("fill", 2, [0, 0, 1, 1]), ("copy", [0, 0, 384, 512]), ("wait", 1))
        self.assertEqual(p.display.getpixel((0, 0)), 2)
        self.assertEqual(p.display.getpixel((1, 0)), 1)

    def test_palette_fade_and_cached_render(self):
        p = player(("palette", 1, 69, 0x40001), ("fill", 1, [0, 0, 384, 512]),
                   ("copy", [0, 0, 384, 512]), ("fade", 1, True, 0x40001))
        p.advance(25 / 120)
        self.assertEqual(p.frame().getpixel((0, 0)), (60, 40, 10, 255))
        p.advance(25 / 120)
        self.assertEqual(p.frame().getpixel((0, 0)), (120, 80, 20, 255))

    def test_sound_dispatch_uses_existing_audio_engine(self):
        audio = Mock()
        player(("sound", 27001, 1), audio=audio)
        audio.play_intro.assert_called_once_with(27001, 1)

    def test_flash_uses_native_twenty_steps_and_tick_delay(self):
        p = player(("flash", 15, 168, 17, 2, 3))
        p.advance(.5)
        self.assertFalse(p.done)
        self.assertEqual(p.frame().getpixel((0, 0)), (0, 0, 0, 255))
        self.assertEqual(p.palette[15], (80, 8, 0))
        p.advance(.5)
        self.assertTrue(p.done)
        self.assertAlmostEqual(p.time, 1)
        self.assertEqual(p.palette[15], (0, 0, 0))

    def test_negative_time_is_rejected(self):
        with self.assertRaises(ValueError):
            player(("wait", 60)).advance(-1)


if __name__ == "__main__":
    unittest.main()
