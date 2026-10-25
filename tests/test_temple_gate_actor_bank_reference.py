import struct
import unittest

from tools.probe_temple_gate_actor_bank import bank_layouts, bank_reference
from tools.probe_temple_gate_actor_clip import clip_reference, put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_plate_release import initial_state
from tools.probe_temple_slide_rock_update import actor_word


class TempleGateActorBankTests(unittest.TestCase):
    def state(self, records=None, position=3):
        level = bytearray(0x49ca)
        struct.pack_into('>H', level, 2 * 60 + 2 * 2, 4)
        struct.pack_into('>2H', level, 0x780 + 2 * 120 + 2 * 4, position, 12345)
        actor = bytearray(actor_fixture(3, 1, 2, -1, 2))
        for field, value in ((4, 400), (10, 91), (28, -1), (30, 3), (34, 0), (36, 3), (38, 9), (40, 9)):
            put_actor(actor, field, value)
        return dict(initial_state(level, ((2, 3, 1, 4),) if records is None else records),
                    prince=bytes(actor), working=bytes(range(62)))

    def test_full_bank_is_visited_in_order_before_all_finished_records_are_removed(self):
        state = self.state(bank_layouts(3, 2, 1)['full20'])
        result = bank_reference(state)
        self.assertEqual(result['trobs'], ())
        self.assertEqual([e[1] for e in result['events'] if e[0] == 'visit'], list(range(20)))
        self.assertTrue(all(struct.unpack_from('>h', result['trob_storage'], i * 8 + 4)[0] == -1
                            for i in range(20)))
        self.assertEqual(actor_word(result['prince'], 38), 47)

    def test_stable_compaction_keeps_the_gate_and_retains_unused_tail_bytes(self):
        state = self.state(bank_layouts(3, 2, 2)['erase-before'] + ((2, 3, 1, 1),), position=80)
        result = bank_reference(state)
        self.assertEqual(result['trobs'], ((2, 3, 2, 4),))
        self.assertEqual(struct.unpack_from('>4h', result['trob_storage']), (2, 3, 2, 4))
        self.assertEqual(result['trob_storage'][24:], state['trob_storage'][24:])
        self.assertEqual(result['prince'], state['prince'])

    def test_duplicate_stopping_records_can_select_twice_before_the_actor_is_animated(self):
        result = bank_reference(self.state(bank_layouts(3, 2, 1)['duplicate-gate']))
        self.assertEqual(result['events'].count(('jump_seq', 47)), 2)
        self.assertEqual(actor_word(result['prince'], 16), 2)
        self.assertEqual(result['trobs'], ())

    def test_actor_first_and_bank_first_have_different_first_update_results(self):
        clips = {9: (-7, 2, 91, -1, 210), 210: (90,), 47: (-7, 5, -5, -16, 50)}
        state = self.state()
        actor_first = clip_reference(state['prince'], clips)['actor']
        actor_first = bank_reference(dict(state, prince=actor_first, working=actor_first))['prince']
        bank_first = clip_reference(bank_reference(state)['prince'], clips)['actor']
        self.assertEqual(tuple(actor_word(actor_first, i) for i in (4, 10, 16, 36, 38)), (400, 90, 2, 0, 47))
        self.assertEqual(tuple(actor_word(bank_first, i) for i in (4, 10, 16, 36, 38)), (416, 50, 5, 5, 47))

    def test_fast_close_leaves_actor_unchanged_but_removes_its_record(self):
        state = self.state(((2, 3, 4, 4),), position=60)
        result = bank_reference(state)
        self.assertEqual((result['prince'], result['working']), (state['prince'], state['working']))
        self.assertIn(('audio', 29), result['events'])
        self.assertNotIn(('jump_seq', 47), result['events'])
        self.assertEqual(result['trobs'], ())

    def test_empty_bank_preserves_storage_scratch_and_actors(self):
        state = self.state(())
        self.assertEqual(bank_reference(state), state)

    def test_gate_tail_and_raw_kind_are_preserved_in_the_object_scratch(self):
        result = bank_reference(self.state())
        self.assertEqual(struct.unpack('>3H', result['os']), (0, 12345, 4))
        self.assertEqual(result['scratch'], (2, 3, -1, 4))

    def test_uncovered_record_kinds_and_overflow_are_rejected(self):
        with self.assertRaises(ValueError):
            bank_reference(self.state(((2, 3, 1, 5),)))
        state = self.state()
        state['trobs'] *= 21
        with self.assertRaises(ValueError):
            bank_reference(state)


if __name__ == '__main__':
    unittest.main()
