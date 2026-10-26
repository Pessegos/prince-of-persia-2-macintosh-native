import unittest

from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_distance import distance_reference
from tools.probe_temple_gate_hanging import actor_fixture


class TempleGateDistanceTests(unittest.TestCase):
    def query(self, *, facing=-1, kind=0, source=9, foreground=1, back=False,
              height=74, room=1, view=1, neighbors=(0,) * 6, edges=(500, 530)):
        actor = bytearray(actor_fixture(1, 1, 4, facing, 0))
        for offset, value in ((8, kind), (40, source), (42, 20), (46, 20 + height)):
            put_actor(actor, offset, value)
        return distance_reference(bytes(actor), foreground, room, 4, edges, view, neighbors,
                                  back=back)

    def test_face_and_back_exchange_sides_with_facing(self):
        self.assertEqual(self.query(), dict(distance=17, anchor=433))
        self.assertEqual(self.query(back=True), dict(distance=-57, anchor=433))
        self.assertEqual(self.query(facing=0), dict(distance=-57, anchor=433))
        self.assertEqual(self.query(facing=0, back=True), dict(distance=17, anchor=433))

    def test_gate_admission_short_circuits_only_the_face_distance(self):
        self.assertEqual(self.query(foreground=184), dict(distance=-1, anchor=73))
        self.assertEqual(self.query(foreground=184, back=True), dict(distance=-57, anchor=433))

    def test_a_shorter_visible_body_can_pass_the_same_gate(self):
        self.assertEqual(self.query(foreground=100, height=34)['distance'], -1)
        self.assertEqual(self.query(foreground=100, height=74)['distance'], 17)

    def test_kind_one_and_source68_skip_face_geometry_without_changing_the_anchor(self):
        for kwargs in ({'kind': 1}, {'source': 68}):
            self.assertEqual(self.query(**kwargs), dict(distance=-1, anchor=73))
            self.assertEqual(self.query(back=True, **kwargs), dict(distance=-57, anchor=433))

    def test_foreground_high_bits_do_not_make_a_closed_gate_open(self):
        self.assertEqual(self.query(foreground=0x8100), self.query(foreground=0))

    def test_left_and_right_neighbor_columns_use_adjusted_coordinates(self):
        self.assertEqual(self.query(room=2, neighbors=(2, 3, 4, 5, 6, 7)),
                         dict(distance=527, anchor=-77))
        self.assertEqual(self.query(room=2, neighbors=(5, 6, 7, 2, 3, 4)),
                         dict(distance=-493, anchor=943))

    def test_same_room_precedes_neighbors_and_left_precedes_right(self):
        self.assertEqual(self.query(view=2, room=2, neighbors=(2,) * 6), self.query())
        self.assertEqual(self.query(room=2, neighbors=(2,) * 6)['anchor'], -77)

    def test_an_unrelated_room_keeps_the_column_anchor(self):
        self.assertEqual(self.query(room=2), self.query())

    def test_subtraction_wraps_as_a_signed_word(self):
        self.assertEqual(self.query(edges=(-32768, 32767)), dict(distance=32285, anchor=433))
        self.assertEqual(self.query(edges=(-32768, 32767), back=True),
                         dict(distance=-32294, anchor=433))

    def test_out_of_table_gate_columns_are_rejected_by_the_reference(self):
        actor = actor_fixture(1, 1, 4, -1, 0)
        with self.assertRaises(ValueError):
            distance_reference(actor, 1, 1, -1, (500, 530), 1, (0,) * 6)
