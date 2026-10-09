import struct
import unittest

from pop2.recorded_game import RecordedControls, RecordedGame, RecordedPlayback


def recording(blocks, last_frame=10, tail=b""):
    payload = b"".join(struct.pack(">2H", frame, len(commands))
                       + b"".join(struct.pack(">2H", *command) for command in commands)
                       + b"\0" * 4 for frame, commands in blocks)
    return struct.pack(">3H", 1, last_frame, len(payload)) + payload + tail


class RecordedGameTests(unittest.TestCase):
    def test_decodes_facing_relative_control_latches(self):
        self.assertEqual(RecordedControls.unpack(0), RecordedControls(-1, -1, -1, -1, -2))
        self.assertEqual(RecordedControls.unpack(0x5510), RecordedControls())
        self.assertEqual(RecordedControls.unpack(0x5618), RecordedControls(0, 0, 0, 1, 1))

    def test_low_three_bits_are_not_keyboard_controls(self):
        self.assertEqual(RecordedControls.unpack(0x5510), RecordedControls.unpack(0x5517))

    def test_playback_retains_each_actors_last_commands(self):
        game = RecordedGame.read(recording([(0, [(5, 0x5510)]), (2, [(0, 0x5618)])], 3))
        playback = RecordedPlayback(game)
        self.assertEqual(playback.advance()[5], RecordedControls())
        self.assertEqual(playback.advance()[0], RecordedControls.unpack(0))
        self.assertEqual(playback.advance()[0], RecordedControls.unpack(0x5618))
        self.assertEqual(playback.controls[5], RecordedControls())
        playback.advance()
        self.assertFalse(playback.done)
        playback.advance()
        self.assertTrue(playback.done)

    def test_unused_resource_tail_is_not_played(self):
        game = RecordedGame.read(recording([(0, [(5, 0x5510)])], tail=b"old take"))
        self.assertEqual(len(game.frames), 1)

    def test_invalid_headers_are_rejected(self):
        for data in (b"", b"\0" * 5, struct.pack(">3H", 0, 10, 0), struct.pack(">3H", 1, 10, 8)):
            with self.subTest(data=data), self.assertRaises(ValueError):
                RecordedGame.read(data)

    def test_invalid_blocks_are_rejected(self):
        for blocks in ([(11, [])], [(2, []), (2, [])], [(3, []), (2, [])],
                       [(0, [(6, 0)])], [(0, [(5, 0), (5, 1)])]):
            with self.subTest(blocks=blocks), self.assertRaises(ValueError):
                RecordedGame.read(recording(blocks))

    def test_truncated_block_does_not_read_into_unused_tail(self):
        data = recording([(0, [(5, 0x5510)])])
        data = data[:4] + struct.pack(">H", 11) + data[6:]
        with self.assertRaises(ValueError):
            RecordedGame.read(data)
