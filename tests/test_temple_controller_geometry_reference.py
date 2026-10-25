import struct
import unittest

from tools.probe_temple_controller_geometry import geometry_player_reference, left_edge_reference, rock_in_cell_reference
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_plate_release import initial_state
from tools.probe_temple_player_control import PlayerInputs
from tools.probe_temple_slide_rock_update import actor_word
from tools.probe_temple_world_prince import world_reference
from tests.test_temple_player_control_reference import CLIPS


class TempleControllerGeometryTests(unittest.TestCase):
    def state(self, *, column=2, row=1, facing=-1, bank=()):
        level = bytearray(0x49ca)
        for cell in range(60):
            struct.pack_into('>h', level, cell * 2, 1)
        for offset, value in ((0x2180, 2), (0x2186, 2), (0x218a, 10), (0x21a4, 7)):
            struct.pack_into('>h', level, offset, value)
        actor = bytearray(actor_fixture(1, row, column, facing, 2))
        for field, value in ((4, 400), (6, 110), (10, 91), (18, 0), (20, 0), (24, -1), (26, 0),
                (28, -1), (30, 3), (34, 0), (36, 3), (38, 9), (40, 9), (52, 0), (58, -1)):
            put_actor(actor, field, value)
        return dict(initial_state(level, ()), prince=bytes(actor), working=bytes(range(62)), countdown=-2,
                    saved_edges=(11, 13, 17, 19), view=1, exit_flag=1234, result=-2, cooldown=0,
                    input_latches=(0, 0, 0, 0, 0), working_latches=(31, 37, 41, 43, 47), raw_axes=(53, 59, 61),
                    cell_cache=struct.pack('>6h', 0, 0, 0, 0, -32768, -32768),
                    mob_records=bank, frame_width=18, division_remainder=61)

    def rock(self, x=153, *, room=1, row=0, kind=6, mark=0, control=-2):
        return (x, 116, room, mark, control, kind, row, 459)

    def query(self, *, bank=None, column=3, margin=0, facing=-1):
        state = self.state()
        return rock_in_cell_reference(state['level'], (1, 0, column, 1, column, 0),
                                      (self.rock(),) if bank is None else bank, facing, 18, margin)

    def test_empty_bank_is_not_an_obstruction_and_does_not_read_left_edge(self):
        result = self.query(bank=())
        self.assertFalse(result['result'])
        self.assertEqual(result['events'], [('rock_in_cell', 0), ('rock_edge', 0, 1, 0)])
        self.assertIsNone(result['remainder'])

    def test_bank_lookup_skips_wrong_kind_removed_room_and_row(self):
        bank = (self.rock(kind=10), self.rock(mark=-1), self.rock(room=2), self.rock(row=1), self.rock())
        self.assertTrue(self.query(bank=bank)['result'])
        self.assertFalse(self.query(bank=bank[:-1])['result'])

    def test_first_matching_rock_controls_result_not_any_later_match(self):
        far, near = self.rock(306), self.rock(153)
        self.assertFalse(self.query(bank=(far, near))['result'])
        self.assertTrue(self.query(bank=(near, far))['result'])

    def test_control100_is_still_a_live_query_record(self):
        self.assertTrue(self.query(bank=(self.rock(control=100),))['result'])
        self.assertTrue(self.query(bank=(self.rock(mark=1),))['result'])

    def test_right_edge_interval_is_inclusive_and_short_circuits_left(self):
        for x in (148, 199):
            with self.subTest(x=x):
                result = self.query(bank=(self.rock(x),))
                self.assertTrue(result['result'])
                self.assertIsNone(result['remainder'])
                self.assertEqual(len(result['events']), 2)
        self.assertEqual(len(self.query(bank=(self.rock(200),))['events']), 3)

    def test_left_edge_uses_native_column_division_remainder(self):
        result = self.query(bank=(self.rock(200),))
        self.assertEqual(result['events'][-1], ('rock_edge', -1, 1, 0))
        self.assertEqual(result['remainder'], 35)

    def test_left_edge_clipping_uses_raw_wall_or_gate_and_supplied_frame_width(self):
        level = bytearray(self.state()['level'])
        rock = self.rock(200)
        for kind, facing, expected in ((1, -1, 418), (20, -1, 418), (4, -1, 418), (20, 0, 439), (4, 0, 439)):
            with self.subTest(kind=kind, facing=facing):
                struct.pack_into('>h', level, 2 * 2, kind)
                result = left_edge_reference(level, rock, facing, 40)
                self.assertEqual(result['edge'], expected)
                self.assertEqual(result['remainder'], 35)

    def test_release_front_offset_uses_data_table_not_assumed_facing_sign(self):
        for facing, front in ((-1, 3), (0, 1)):
            state = self.state(facing=facing)
            result = geometry_player_reference(state['prince'], CLIPS, PlayerInputs(raw_axes=(0, 0, 0)), state)
            reads = [event for event in result['events'] if event[0] == 'read_cell']
            self.assertEqual(reads, [('read_cell', 1, front, 1), ('read_cell', 1, 2, 1)])

    def test_climb_reads_real_above_cell_and_persists_complete_cache(self):
        state = self.state()
        result = world_reference(state, CLIPS, PlayerInputs(raw_axes=(0, -1, -1)), geometry_player_reference)
        self.assertEqual(struct.unpack('>6h', result['cell_cache']), (1, 0, 2, 1, 2, 0))
        self.assertEqual(actor_word(result['prince'], 40), 10)
        self.assertIn(('rock_in_cell', 0), result['events'])
        self.assertNotIn('bars', [event[0] for event in result['events']])

    def test_real_rock_can_change_climb_from10_to73(self):
        state = self.state(column=3, bank=(self.rock(153),))
        result = world_reference(state, CLIPS, PlayerInputs(raw_axes=(0, -1, -1)), geometry_player_reference)
        self.assertEqual(actor_word(result['prince'], 40), 73)
        self.assertEqual((actor_word(result['prince'], 16), actor_word(result['prince'], 10)), (2, 135))
        self.assertEqual(result['mob_records'], state['mob_records'])

    def test_narrow_gate_shortcut_does_not_query_rock(self):
        state = self.state()
        level = bytearray(state['level'])
        struct.pack_into('>h', level, 2 * 2, 4)
        struct.pack_into('>h', level, 0x780 + 2 * 4, 47)
        state['level'] = bytes(level)
        result = world_reference(state, CLIPS, PlayerInputs(raw_axes=(0, -1, -1)), geometry_player_reference)
        self.assertEqual(actor_word(result['prince'], 40), 73)
        self.assertNotIn('rock_in_cell', [event[0] for event in result['events']])
        self.assertEqual(struct.unpack('>6h', result['cell_cache'])[:2], (4, 47))

    def test_left_neighbor_cell_normalizes_and_saves_its_room_and_column(self):
        state = self.state(column=-1)
        level = bytearray(state['level'])
        struct.pack_into('>h', level, 0x2080, 2)
        state['level'] = bytes(level)
        result = world_reference(state, CLIPS, PlayerInputs(raw_axes=(0, -1, -1)), geometry_player_reference)
        self.assertEqual(struct.unpack('>6h', result['cell_cache']), (1, 0, 9, 2, 9, 0))
        self.assertIn(('rock_edge', 0, 2, 0), result['events'])

    def test_above_room_traversal_queries_rock_in_resolved_room(self):
        state = self.state(row=0)
        level = bytearray(state['level'])
        struct.pack_into('>h', level, 0x2080 + 4, 2)
        state['level'] = bytes(level)
        result = world_reference(state, CLIPS, PlayerInputs(raw_axes=(0, -1, -1)), geometry_player_reference)
        self.assertEqual(struct.unpack('>6h', result['cell_cache']), (1, 0, 22, 2, 2, 2))
        self.assertIn(('rock_edge', 0, 2, 2), result['events'])

    def test_geometry_queries_are_not_eagerly_added_to_release_path(self):
        state = self.state()
        result = world_reference(state, CLIPS, PlayerInputs(raw_axes=(0, 0, 0)), geometry_player_reference)
        self.assertNotIn('above_cell', [event[0] for event in result['events']])
        self.assertNotIn('rock_in_cell', [event[0] for event in result['events']])
        self.assertEqual(struct.unpack('>6h', result['cell_cache']), (1, 0, 12, 1, 2, 1))

    def test_unsupported_static_query_bounds_are_rejected(self):
        with self.assertRaises(ValueError):
            self.query(bank=(self.rock(),) * 31)
        with self.assertRaises(ValueError):
            self.query(facing=1)
        with self.assertRaises(ValueError):
            self.query(margin=52)


if __name__ == '__main__':
    unittest.main()
