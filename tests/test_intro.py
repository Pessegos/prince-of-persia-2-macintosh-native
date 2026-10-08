import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import numpy as np
from PIL import Image

from pop2.intro import (
    IntroPlayer, ScriptAnimation, dissolve_words, fade_ticks, indexed_shape, palette_colors,
    read_program, text_strings,
)


def instruction(opcode, *args):
    return bytes((opcode, 2 + len(args) * 2)) + struct.pack(f">{len(args)}h", *args)


def script(*commands):
    payload = b"".join(commands)
    return struct.pack(">I", len(payload)) + payload


def player(*operations, audio=None, dissolve=None):
    sounds = {"25010": {"duration": 4, "markers": {"a": 1.25}, "kind": 0},
              "27001": {"duration": 2, "markers": {}, "kind": 1}}
    assets = SimpleNamespace(
        program={"operations": [{"op": op, "args": list(args)} for op, *args in operations],
                 "audio": sounds, "dissolve": dissolve},
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

    def test_script_terminator_has_no_extra_frame_interval(self):
        animation = ScriptAnimation(script(instruction(4, 5), instruction(1),
                                           instruction(1), instruction(0)))
        animation.advance(9)
        self.assertFalse(animation.done)
        animation.advance(10)
        self.assertTrue(animation.done)
        self.assertEqual(animation.next_tick, 10)
        animation.advance(100)
        self.assertEqual(animation.next_tick, 10)

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

    def test_dissolve_alternates_word_offsets_per_shuffled_group_in_each_pass(self):
        pattern = {"rect": [2, 4, 4, 12], "order": [3, 0, 2, 1]}
        words = dissolve_words(pattern)
        # Write order verified by executing CODE 15:31ba-3256 on the 68000.
        self.assertEqual(words.tolist(), [[1544, 1545], [1030, 1031], [1540, 1541], [1034, 1035],
                                          [1546, 1547], [1028, 1029], [1542, 1543], [1032, 1033]])

    def test_half_dissolve_does_not_favor_vertical_column_pairs(self):
        words = dissolve_words()
        first_pass = words[:len(words) // 2].ravel()
        columns = first_pass % 512
        self.assertEqual(np.bincount(columns % 4).tolist(), [11040] * 4)
        self.assertEqual(len(np.unique(words)), 384 * 230)
        self.assertTrue(np.all(words[:, 1] == words[:, 0] + 1))

    def test_invalid_dissolve_permutation_is_rejected(self):
        for order in ([0, 0, 2, 3], [0, 1, 2, 4], [0, 1, 2], [0, 1, 2, 3.0]):
            with self.subTest(order=order), self.assertRaises(ValueError):
                dissolve_words({"rect": [2, 4, 4, 12], "order": order})


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

    def test_dissolve_keeps_pixels_outside_the_scene_and_finishes_both_word_passes(self):
        p = player(("fill", 2, [0, 0, 384, 512]), ("copy", [0, 0, 384, 512]),
                   ("fill", 3, [0, 0, 384, 512]), ("dissolve", 60),
                   dissolve={"rect": [2, 4, 4, 12], "order": [3, 0, 2, 1]})
        p.advance(1 / 8)
        self.assertEqual([p.display.getpixel((x, 3)) for x in range(4, 12)],
                         [2, 2, 2, 2, 3, 3, 2, 2])
        p.advance(3 / 8)
        self.assertEqual([p.display.getpixel((x, 3)) for x in range(4, 12)],
                         [3, 3, 2, 2, 3, 3, 2, 2])
        self.assertEqual([p.display.getpixel((x, 2)) for x in range(4, 12)],
                         [2, 2, 3, 3, 2, 2, 3, 3])
        p.advance(.5)
        self.assertEqual(p.display.crop((4, 2, 12, 4)).tobytes(), bytes([3]) * 16)
        self.assertEqual(p.display.getpixel((0, 0)), 2)
        self.assertTrue(p.done)

    def test_story_text_uses_original_baselines_and_horizontal_shadow_passes(self):
        p = player(("wait", 60))
        glyph = Image.new("RGBA", (2, 23))
        glyph.putpixel((0, 0), (255, 255, 255, 255))
        p.assets.font = SimpleNamespace(height=23, ascent=15, text=lambda _: glyph)
        p.assets.strings = {1: ["a\ra", "a"]}
        p.assets.shapes[25002] = Image.new("L", (512, 87), 15)
        p.text(1, 1, 0, 0, 0)
        for y in (321, 344):
            self.assertEqual([p.display.getpixel((x, y)) for x in range(259, 263)], [14, 3, 15, 255])
            self.assertEqual(p.display.getpixel((259, y + 1)), 15)
        self.assertEqual(p.palette[255], (0, 0, 0))
        p.text(1, 2, 1, 0, 0)
        self.assertEqual(p.display.getpixel((259, 333)), 14)
        self.assertEqual(p.display.getpixel((9, 327)), 1)
        self.assertEqual(p.display.getpixel((6, 327)), 15)

    def test_fill_rectangles_are_half_open(self):
        p = player(("fill", 2, [0, 0, 1, 1]), ("copy", [0, 0, 384, 512]), ("wait", 1))
        self.assertEqual(p.display.getpixel((0, 0)), 2)
        self.assertEqual(p.display.getpixel((1, 0)), 1)

    def test_second_story_palette_cannot_recolor_black_text_shadow(self):
        p = player(("wait", 60))
        glyph = Image.new("RGBA", (2, 23))
        glyph.putpixel((0, 0), (255, 255, 255, 255))
        p.assets.font = SimpleNamespace(height=23, ascent=15, text=lambda _: glyph)
        p.assets.strings = {1: ["a\ra"]}
        p.assets.shapes[25002] = Image.new("L", (512, 87), 15)
        p.assets.palettes[2] = {3: (202, 89, 15), 14: (245, 220, 140),
                               254: (23, 76, 148), 255: (189, 239, 87)}
        p.execute("palette", [2, 66, 0])
        p.text(1, 1, 0, 0, 0)
        frame = p.frame()
        for y in (321, 344):
            self.assertEqual(frame.getpixel((259, y)), (245, 220, 140, 255))
            self.assertEqual(frame.getpixel((260, y)), (202, 89, 15, 255))
            self.assertEqual(frame.getpixel((262, y)), (0, 0, 0, 255))
        self.assertEqual(p.assets.palettes[2][255], (189, 239, 87))

    def test_palette_fades_and_brightness_preserve_reserved_display_black(self):
        for operation, args in (("brightness", [2, 50]), ("fade", [2, True, 0x40001]),
                                ("flash", [255, 189, 239, 87, 1])):
            with self.subTest(operation=operation):
                p = player(("wait", 60))
                p.assets.palettes[2] = {254: (23, 76, 148), 255: (189, 239, 87)}
                p.execute("palette", [2, 66, 0])
                p.display.putpixel((0, 0), 255)
                p.display.putpixel((1, 0), 254)
                p.execute(operation, args)
                if p.transition is not None:
                    p.advance(p.transition[2] / 2)
                self.assertEqual(p.frame().getpixel((0, 0)), (0, 0, 0, 255))
                self.assertNotEqual(p.frame().getpixel((1, 0)), (0, 0, 0, 255))

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


class TitlePlaybackTests(unittest.TestCase):
    def setUp(self):
        self.p = player(("sound", 25010, 0), ("wait", 60))
        self.p.sounds["25010"]["markers"].update(e=0, f=.05, g=.1, h=.3, i=10)
        self.p.assets.title_script = script(
            instruction(4, 6), instruction(5, 1, 1), instruction(1),
            instruction(6, 1, 10, 0), instruction(1), instruction(0))
        self.p.assets.title_shapes = {key: Image.new("L", (1, 1), 1) for key in
                                      (25001, 25360, 25361, 25365, 25373, 25374)}
        self.p.assets.title_palette = {1: (120, 80, 20), 160: (255, 255, 255)}
        self.p.assets.program["title_rects"] = [[152, 52, 179, 458], [129, 87, 179, 423]]

    def test_title_ends_at_script_terminator_before_later_music_cue(self):
        p = self.p
        p.start_title()
        animation = p.title_animation
        self.assertAlmostEqual(p.wait_until, 31 / 60)
        p.advance(.1)
        self.assertFalse(animation.done)
        self.assertEqual(p.display.getpixel((10, 0)), 1)
        p.advance(25 / 60)
        self.assertTrue(p.done)
        self.assertTrue(animation.done)
        self.assertIs(p.title_animation, animation)
        self.assertEqual(p.display.getpixel((10, 0)), 1)
        self.assertEqual(p.display.getpixel((0, 0)), 160)
        self.assertAlmostEqual(p.time, 31 / 60)

    def test_second_frame_fade_freezes_script_then_resumes_one_frame(self):
        p = self.p
        p.assets.title_script = script(
            instruction(4, 5), instruction(6, 1, 0, 0), instruction(1),
            instruction(6, 1, 1, 0), instruction(1),
            instruction(6, 1, 2, 0), instruction(1),
            instruction(6, 1, 3, 0), instruction(1), instruction(0))
        p.start_title()
        p.advance(5 / 60)
        self.assertEqual(p.title_animation.layers[0][1], 1)
        self.assertEqual(p.palette[160], (0, 0, 0))
        p.advance(20 / 60)
        self.assertEqual(p.title_animation.layers[0][1], 1)
        self.assertEqual(p.palette[160], (204, 204, 204))
        p.advance(5 / 60)
        self.assertEqual(p.title_animation.layers[0][1], 2)
        self.assertEqual(p.palette[160], (255, 255, 255))
        p.advance(5 / 60)
        self.assertEqual(p.title_animation.layers[0][1], 3)

    def test_title_still_stops_early_if_music_end_marker_arrives_first(self):
        p = self.p
        p.sounds["25010"]["markers"]["i"] = .05
        p.start_title()
        p.advance(1)
        self.assertTrue(p.done)
        self.assertFalse(p.title_animation.done)
        self.assertAlmostEqual(p.time, .05)

    def test_title_background_keeps_signed_original_cloud_coordinates(self):
        p = self.p
        p.assets.title_shapes[25365] = Image.new("L", (325, 150), 2)
        p.assets.title_shapes[25360] = Image.new("L", (283, 111), 3)
        p.assets.title_shapes[25361] = Image.new("L", (256, 158), 4)
        p.start_title()
        self.assertEqual(p.title_background.getpixel((300, 10)), 2)
        self.assertEqual(p.title_background.getpixel((0, 58)), 4)
        self.assertEqual(p.title_background.getpixel((0, 220)), 3)
        self.assertEqual(p.title_background.getpixel((400, 250)), 3)
        self.assertEqual(p.title_background.getpixel((100, 300)), 4)
        self.assertEqual(p.title_background.getpixel((300, 350)), 160)


if __name__ == "__main__":
    unittest.main()
