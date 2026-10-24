"""Synthetic caller-mode, link traversal and held-plate state regressions."""

import struct
import unittest

from tests.test_temple_slide_rock_geometry_reference import level_fixture, tile
from tools.probe_temple_slide_rock_admission import (
    apply_chain, apply_object, held_plate_reference, link_chain, object_reference,
)
from tools.probe_temple_slide_rock_geometry import TempleCellReader
from tools.probe_temple_slide_rock_lifecycle import store_bank


def rock(control=-2):
    return (204, 236, 1, 0, control, 6, 1, 204)


def state(bank=()):
    return dict(mob=(11, 13, 17, 19, 23, 29, 31, 37), bank=tuple(bank),
                bank_storage=store_bank(bytes([0xa7]) * 512, bank), object_calls=[], rock_calls=[])


def link(level, index, room, cell, following=-3, timer=0):
    struct.pack_into('>5h', level, 0x1680 + index * 10, room, cell, timer, -3, following)


class TempleSlideRockAdmissionTests(unittest.TestCase):
    def test_mode_five_does_not_create_missing_rock(self):
        result = object_reference(25, 1, 14, 5, ())
        self.assertEqual((result['how'], result['result'], result['bank']), (2, -1, ()))
        self.assertIsNone(result['scratch'])

    def test_other_caller_words_create_a_forced_slide_record(self):
        for mode in (-32768, -1, 0, 1, 2, 4, 6, 34, 32767):
            with self.subTest(mode=mode):
                result = object_reference(25, 1, 14, mode, ())
                self.assertEqual((result['how'], result['result']), (1, -1))
                self.assertEqual(result['bank'], (rock(),))

    def test_mode_five_releases_forced_motion_and_other_modes_reactivate_it(self):
        released = object_reference(25, 1, 14, 5, (rock(),))
        self.assertEqual(released['bank'], (rock(2),))
        forced = object_reference(25, 1, 14, 6, released['bank'])
        self.assertEqual(forced['bank'], (rock(),))
        for mode in (5, 6):
            self.assertEqual(object_reference(25, 1, 14, mode, (rock(100),))['bank'], (rock(100),))

    def test_depressed_source_cache_does_not_change_rock_dispatch(self):
        level = level_fixture()
        results = []
        for flags in (0, 0x2000):
            reader = TempleCellReader(level, 1)
            reader.cache = (6, flags, 0, 1, 0, 0)
            results.append(apply_object(state(), reader, 25, 1, 14, 6))
        self.assertEqual(results[0], results[1])

    def test_unhandled_kind_ignores_even_a_stored_rock_at_the_same_location(self):
        for kind in (0, 1, 5, 6, 24, 26, 43, 0x8019, 65535):
            result = object_reference(kind, 1, 14, 6, (rock(2),))
            self.assertEqual(result['bank'], (rock(2),))
            self.assertIsNone(result['how'])
            self.assertEqual(result['result'], -1)

    def test_negative_return_does_not_stop_link_chain_or_duplicate_same_row(self):
        level = level_fixture()
        for index, cell in enumerate((14, 15, 24)):
            tile(level, 1, cell % 10, cell // 10, 25)
            link(level, index, 1, cell, index + 1 if index < 2 else -3)
        result = apply_chain(state(), TempleCellReader(level, 1), 0, 6)
        self.assertEqual(result['object_calls'], [(25, 1, c, 6) for c in (14, 15, 24)])
        self.assertEqual(result['rock_calls'], [(1, c, 1) for c in (14, 15, 24)])
        self.assertEqual(result['bank'], (rock(), (204, 356, 1, 0, -2, 6, 2, 204)))

    def test_unknown_target_kind_does_not_prevent_the_following_rock(self):
        level = level_fixture()
        tile(level, 1, 4, 1, 1)
        tile(level, 1, 5, 1, 25)
        link(level, 0, 1, 14, 1)
        link(level, 1, 1, 15)
        result = apply_chain(state(), TempleCellReader(level, 1), 0, 6)
        self.assertEqual(result['object_calls'], [(1, 1, 14, 6), (25, 1, 15, 6)])
        self.assertEqual(result['rock_calls'], [(1, 15, 1)])
        self.assertEqual(result['bank'][0][0], 255)

    def plate_fixture(self, kind=6, timer=2):
        level = level_fixture()
        tile(level, 1, 3, 2, kind)
        tile(level, 1, 9, 2, 25)
        struct.pack_into('>H', level, 0x780 + 23 * 4, 4)
        link(level, 4, 1, 29, timer=timer)
        reader = TempleCellReader(level, 1)
        reader.read(1, 3, 2)
        return level, reader

    def test_held_plate_refreshes_timer_and_marks_source_after_target_changes_cache(self):
        initial, reader = self.plate_fixture()
        result, changed = held_plate_reference(state(), reader, 1, 23)
        self.assertEqual(struct.unpack_from('>h', changed, 0x1680 + 4 * 10 + 4)[0], 5)
        self.assertEqual(struct.unpack_from('>H', changed, 0x780 + 23 * 4)[0], 0x2004)
        self.assertEqual(changed[0x780 + 29 * 4:0x780 + 30 * 4], initial[0x780 + 29 * 4:0x780 + 30 * 4])
        self.assertEqual(reader.cache[2:4], (29, 1))
        self.assertEqual(result['bank'], ((459, 356, 1, 0, -2, 6, 2, 459),))

    def test_permanent_plate_keeps_timer_31_and_repeated_presses_reuse_record(self):
        _, reader = self.plate_fixture(timer=31)
        result = state()
        for _ in range(3):
            reader.read(1, 3, 2)
            result, changed = held_plate_reference(result, reader, 1, 23)
            self.assertEqual(len(result['bank']), 1)
            self.assertEqual(struct.unpack_from('>h', changed, 0x1680 + 4 * 10 + 4)[0], 31)

    def test_held_mode_five_plate_marks_source_without_creating_rock(self):
        _, reader = self.plate_fixture(kind=5)
        result, changed = held_plate_reference(state(), reader, 1, 23)
        self.assertEqual(result['bank'], ())
        self.assertEqual(result['rock_calls'], [(1, 29, 2)])
        self.assertEqual(struct.unpack_from('>H', changed, 0x780 + 23 * 4)[0], 0x2004)

    def test_raw_plate_beyond_declared_rooms_is_not_a_live_source(self):
        level = level_fixture()
        struct.pack_into('>H', level, 0x2180, 1)
        tile(level, 2, 4, 0, 6)
        reader = TempleCellReader(level, 2)
        self.assertEqual(reader.read(2, 4, 0), 20)
        with self.assertRaises(ValueError):
            held_plate_reference(state(), reader, 2, 4)

    def test_unassigned_chain_is_empty_and_invalid_links_are_rejected(self):
        level = level_fixture()
        link(level, 0, -2, 0)
        self.assertEqual(link_chain(level, 0), [])
        link(level, 0, 1, 14, 0)
        with self.assertRaises(ValueError):
            link_chain(level, 0)
        link(level, 0, 1, 14, 1)
        link(level, 1, -2, 0)
        with self.assertRaises(ValueError):
            link_chain(level, 0)

    def test_uncovered_mechanisms_and_fresh_press_path_fail_explicitly(self):
        for kind in (4, 17, 27, 33):
            with self.assertRaises(ValueError):
                object_reference(kind, 1, 14, 6, ())
        for mode in (-32769, 32768):
            with self.assertRaises(ValueError):
                object_reference(25, 1, 14, mode, ())
        _, reader = self.plate_fixture(timer=0)
        with self.assertRaises(ValueError):
            held_plate_reference(state(), reader, 1, 23)


if __name__ == '__main__':
    unittest.main()
