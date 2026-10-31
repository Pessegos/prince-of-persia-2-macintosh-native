import struct
import unittest

from pop2.render_opening import decode_shap, unpack_shape_lz


class ShapeLzTests(unittest.TestCase):
    def packed(self, body, size):
        header = struct.pack('>HhhH', 0x0500 | 0xb000, 4, 4, 1) + bytes(4)
        return header + struct.pack('>I', size) + body

    def test_literals_and_a_ring_match_follow_unpack_lz_17_3aa8(self):
        # Flag byte 0b0111: three literals then a match; a match of
        # ((b1 << 8 | b2) & 0x3ff) = 958 (the first literal) with length
        # (b1 >> 2) + 3 = 3 repeats "abc".
        body = bytes((0b00000111,)) + b'abc' + bytes((0x03, 0xbe))
        unpacked = unpack_shape_lz(self.packed(body, 12 + 6))
        self.assertEqual(unpacked[12:], b'abcabc')
        self.assertEqual(struct.unpack_from('>H', unpacked)[0], 0xb100)

    def test_a_packed_row_rle_shape_decodes(self):
        # Two RLE rows of 4 pixels (size word 2: repeat token, colour).
        rows = struct.pack('>H', 2) + bytes((0x83, 5)) + struct.pack('>H', 2) + bytes((0x83, 6))
        body = bytes((0xff,)) + rows[:8] + bytes((0xff,)) + rows[8:]
        data = self.packed(body, 12 + len(rows))
        data = data[:6] + struct.pack('>H', 2) + data[8:]
        image = decode_shap(data, {5: (1, 2, 3, 255), 6: (4, 5, 6, 255)})
        self.assertEqual(image.size, (4, 2))
        self.assertEqual(image.getpixel((0, 1)), (4, 5, 6, 255))


if __name__ == '__main__':
    unittest.main()
