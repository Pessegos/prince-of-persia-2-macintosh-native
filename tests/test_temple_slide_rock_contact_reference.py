"""Asset-free contact references; clip payloads below are synthetic, not extracted."""

import unittest

from tests.test_temple_slide_rock_geometry_reference import level_fixture, tile
from tools.probe_temple_slide_rock_contact import (
    animate_reference, character_column, contact_actor, contact_reference, contact_update_reference,
)
from tools.probe_temple_slide_rock_geometry import TempleCellReader
from tools.probe_temple_slide_rock_update import actor_word


SYNTHETIC_CLIPS = {
    47: (-7, 5, -5, -3, 1111), 48: (-7, 5, -5, 4, 1112),
    71: (-7, 1, -19, 1113), 93: (-7, 1, -5, -6, 1114),
}


def rock(x=225, control=2):
    return (x, 236, 1, 0, control, 6, 1, 459)


class TempleSlideRockContactTests(unittest.TestCase):
    def contact(self, *, mob=None, actor=None, level=None, clips=None):
        level = level_fixture() if level is None else level
        reader = TempleCellReader(level, 1)
        result = contact_reference(rock() if mob is None else mob,
                                   contact_actor() if actor is None else actor,
                                   22, reader, SYNTHETIC_CLIPS if clips is None else clips)
        return result, reader

    def solid_level(self, kind=4):
        level = level_fixture()
        for row in range(3):
            for col in range(10):
                tile(level, 1, col, row, kind)
        return level

    def test_character_column_preserves_low_word_subtraction_order(self):
        for value, expected in ((21, (-5, -5)), (22, (1280, 48)), (23, (1280, 49)),
                                (24, (1280, 50)), (25, (1281, 0)), (26, (-4, 0)),
                                (207, (-1, 28))):
            self.assertEqual(character_column(value), expected)

    def test_action_five_returns_before_position_geometry_or_animation(self):
        actor = contact_actor(action=5)
        result, reader = self.contact(actor=actor)
        self.assertEqual(result, dict(actor=actor, events=[], death_method=12345, remainder=-1234))
        self.assertEqual(reader.requests, [])

    def test_free_contact_selects_facing_specific_clip_and_runs_first_frame(self):
        for facing, sequence, x, pose in ((0, 47, 445, 1111), (-1, 48, 422, 1112)):
            result, _ = self.contact(actor=contact_actor(facing=facing))
            actor = result['actor']
            self.assertEqual(tuple(actor_word(actor, i) for i in (4, 6, 10, 16, 20)),
                             (x, 226, pose, 5, 0))
            self.assertEqual(tuple(actor_word(actor, i) for i in (36, 38, 40)), (5, sequence, sequence))
            self.assertEqual(result['events'][:3], [('resource', sequence),
                                                   ('animate', sequence, 0), ('sequence', sequence)])

    def test_exact_armed_one_selects_disarm_clip_and_clears_armed_word(self):
        result, _ = self.contact(actor=contact_actor(armed=1))
        self.assertEqual(actor_word(result['actor'], 26), 0)
        self.assertEqual(actor_word(result['actor'], 38), 93)
        self.assertEqual(actor_word(result['actor'], 10), 1114)
        other, _ = self.contact(actor=contact_actor(armed=2))
        self.assertEqual(actor_word(other['actor'], 26), 2)
        self.assertEqual(actor_word(other['actor'], 38), 47)

    def test_nonnegative_alive_word_only_moves_x_without_an_animation_request(self):
        for alive in (0, 1):
            result, _ = self.contact(actor=contact_actor(alive=alive))
            self.assertEqual(actor_word(result['actor'], 4), 436)
            self.assertEqual(tuple(actor_word(result['actor'], i) for i in (6, 10, 16, 20)),
                             (231, 15, 0, 9))
            self.assertEqual(result['events'], [])

    def test_tile_two_snaps_x_but_bypasses_terminal_death_and_animation(self):
        result, _ = self.contact(level=self.solid_level(2), mob=rock(control=100))
        actor = result['actor']
        self.assertEqual(actor_word(actor, 4), 451)
        self.assertEqual(tuple(actor_word(actor, i) for i in (6, 10, 28, 34, 52)),
                         (231, 15, -1, -1, 0))
        self.assertEqual(result['events'], [])

    def test_terminal_solid_contact_sets_dead_pose_and_life_delta_without_jumpseq(self):
        result, _ = self.contact(level=self.solid_level(), mob=rock(control=100))
        actor = result['actor']
        self.assertEqual(tuple(actor_word(actor, i) for i in (10, 28, 30, 34)), (185, 0, 3, -3))
        self.assertEqual(tuple(actor_word(actor, i) for i in (6, 16, 20, 38, 40, 52)),
                         (231, 0, 9, 47, 99, 0))
        self.assertEqual(result['death_method'], 12345)
        self.assertEqual(result['events'], [])

    def test_terminal_contact_preserves_larger_pending_damage_and_does_not_rekill(self):
        result, _ = self.contact(level=self.solid_level(), mob=rock(control=100),
                                 actor=contact_actor(delta=-8))
        self.assertEqual(actor_word(result['actor'], 34), -8)
        result, _ = self.contact(level=self.solid_level(), mob=rock(control=100),
                                 actor=contact_actor(alive=0, delta=-1))
        self.assertEqual(actor_word(result['actor'], 34), -1)

    def test_second_solid_tile_controls_sound_and_death_method_not_clip_selection(self):
        for second, method in ((0, 12345), (4, 13)):
            level = level_fixture()
            tile(level, 1, 3, 1, 4)
            tile(level, 1, 4, 1, second)
            result, reader = self.contact(level=level)
            self.assertEqual(reader.requests, [(1, 3, 1), (1, 4, 1)])
            self.assertEqual(result['death_method'], method)
            self.assertEqual(('sound', 193) in result['events'], second == 4)
            actor = result['actor']
            self.assertEqual(tuple(actor_word(actor, i) for i in (10, 16, 28, 34, 38, 52)),
                             (1113, 1, -1, -1, 71, 4))

    def test_remainder_forty_six_is_excluded_from_death_method_assignment(self):
        for x, method in ((63, 13), (64, 12345), (65, 12345), (68, 12345), (69, 13)):
            result, _ = self.contact(level=self.solid_level(), mob=rock(x=x),
                                     actor=contact_actor(x=x + 235))
            self.assertEqual(result['death_method'], method)
            self.assertEqual(actor_word(result['actor'], 38), 71)

    def test_nonplayer_kind_does_not_set_kid_death_method(self):
        result, _ = self.contact(level=self.solid_level(), actor=contact_actor(actor=4))
        self.assertEqual(result['death_method'], 12345)
        self.assertIn(('sound', 193), result['events'])

    def test_head_kinds_align_y_once_in_formula_even_when_clip_aligns_again(self):
        for kind in (7, 8):
            result, _ = self.contact(level=self.solid_level(), actor=contact_actor(actor=kind))
            self.assertEqual(actor_word(result['actor'], 6), 193)

    def test_missing_lookup_keeps_old_ids_and_pose_but_common_alignment_still_runs(self):
        result, _ = self.contact(level=self.solid_level(), clips={})
        actor = result['actor']
        self.assertEqual(tuple(actor_word(actor, i) for i in (6, 10, 16, 20, 36, 38, 40)),
                         (226, 15, 0, 0, 0, 47, 99))
        self.assertEqual(result['events'][-3:], [('resource', 71), ('animate', 47, 0), ('sequence', 47)])
        self.assertFalse(any(event[0] == 'handle' for event in result['events']))

    def test_contact_inputs_and_level_are_not_modified(self):
        level, actor, mob = self.solid_level(), bytearray(contact_actor()), list(rock())
        before = bytes(level), bytes(actor), mob[:]
        self.contact(level=level, actor=actor, mob=mob)
        self.assertEqual((bytes(level), bytes(actor), mob), before)

    def test_connected_active_crush_then_terminal_death_then_persistence(self):
        reader = TempleCellReader(self.solid_level(), 1)
        mob = (58, 236, 1, 0, -2, 6, 1, 459)
        first = contact_update_reference(mob, contact_actor(x=290), bytes(62), 22, reader,
                                         SYNTHETIC_CLIPS)
        self.assertEqual(first['mob'][3:5], (1, -2))
        self.assertEqual(actor_word(first['prince'], 28), -1)
        self.assertEqual(actor_word(first['prince'], 52), 4)
        self.assertEqual(first['death_method'], 13)
        second = contact_update_reference(first['mob'], first['prince'], first['working'], 22,
                                          reader, SYNTHETIC_CLIPS, death_method=first['death_method'])
        self.assertEqual(second['mob'][3:5], (0, 100))
        self.assertEqual(tuple(actor_word(second['prince'], i) for i in (10, 28, 34)), (185, 0, -3))
        third = contact_update_reference(second['mob'], second['prince'], second['working'], 22,
                                         reader, SYNTHETIC_CLIPS, death_method=second['death_method'])
        self.assertEqual(third['prince'], second['prince'])
        self.assertEqual(third['events'], [])

    def test_unmodeled_actor_conversion_and_vm_opcodes_fail_closed(self):
        with self.assertRaises(ValueError):
            self.contact(actor=contact_actor(actor=1))
        with self.assertRaises(ValueError):
            animate_reference(bytearray(contact_actor()), {47: (-123, 1111)}, [])
        with self.assertRaises(ValueError):
            animate_reference(bytearray(contact_actor()), {47: (-5,)}, [])


if __name__ == '__main__':
    unittest.main()
