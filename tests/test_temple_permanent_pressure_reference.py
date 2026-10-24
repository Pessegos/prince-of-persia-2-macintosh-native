import struct
import unittest

from tools.probe_temple_permanent_pressure import permanent_pressure_reference


class TemplePermanentPressureTests(unittest.TestCase):
    def fixture(self, index=4, timer=0):
        level = bytearray(0x218c)
        struct.pack_into('>h', level, 0x1680 + index * 10 + 4, timer)
        return level

    def test_timer31_is_visible_before_explicit_push_arguments(self):
        level = self.fixture()
        cache = (6, 0x2004, 23, 1, 3, 2)
        state = permanent_pressure_reference(level, cache)
        self.assertEqual(state['requests'], [((6, 4), 31, cache)])
        self.assertEqual(state['cache'], cache)
        self.assertEqual(struct.unpack_from('>h', state['level'], 0x1680 + 44)[0], 31)
        self.assertEqual(struct.unpack_from('>h', level, 0x1680 + 44)[0], 0)

    def test_only_the_selected_timer_word_changes(self):
        level = self.fixture()
        before = bytes(level)
        after = permanent_pressure_reference(level, (5, 4, 13, 1, 3, 1))['level']
        different = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
        self.assertEqual(different, [0x1680 + 4 * 10 + 5])

    def test_signed_foreground_uses_only_low_byte_at_both_table_edges(self):
        for index in (0, 255):
            level = self.fixture(index, 32767)
            cache = (34, -256 + index, 17, 19, -32768, -32768)
            result = permanent_pressure_reference(level, cache)
            self.assertEqual(result['requests'], [((34, index), 31, cache)])

    def test_the_wrapper_does_not_validate_kind_or_infer_gameplay_admission(self):
        cache = (-1, 4, 17, 19, -32768, -32768)
        self.assertEqual(permanent_pressure_reference(self.fixture(), cache)['requests'], [((-1, 4), 31, cache)])

    def test_existing_timer_values_including31_are_overwritten(self):
        for old in (-32768, -1, 0, 1, 30, 31, 32767):
            result = permanent_pressure_reference(self.fixture(timer=old), (6, 4, 23, 1, 3, 2))
            self.assertEqual(result['requests'][0][1], 31)

    def test_incomplete_link_tables_and_unsigned_cache_words_are_rejected(self):
        with self.assertRaises(ValueError):
            permanent_pressure_reference(bytes(0x207f), (6, 4, 23, 1, 3, 2))
        with self.assertRaises(ValueError):
            permanent_pressure_reference(self.fixture(), (6, 65535, 23, 1, 3, 2))
        with self.assertRaises(ValueError):
            permanent_pressure_reference(self.fixture(), (6, 4))


if __name__ == '__main__':
    unittest.main()
