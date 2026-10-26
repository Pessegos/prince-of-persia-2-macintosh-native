import struct
import unittest

from tools.probe_temple_ground_bump import ground_bump_reference
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_slide_rock_update import actor_word


class TempleGroundBumpTests(unittest.TestCase):
    def query(self, *, facing=0, mode=0, floating=False, available=True, x=460):
        sequences = {2: (-7, 0, 15), 45: (-7, 5, -6, 5, -10, 229, 102), 229: (102,)}
        frames = struct.pack('>5h', 1, 0, 0, 0, 0) * 352
        attachments = bytes(range(8))
        actor = bytearray(actor_fixture(1, 1, 4, facing, mode))
        for offset, value in ((4, x), (6, 226), (10, 15), (18, 5), (20, -4),
                              (28, -1), (30, 3), (36, 0), (38, 2), (40, 2)):
            put_actor(actor, offset, value)
        result = ground_bump_reference(bytes(actor), sequences, frames, attachments,
                                       available=available, floating=floating)
        return result, bytes(actor)

    def test_backoff_is_relative_to_facing(self):
        for facing, x in ((0, 450), (-1, 470)):
            self.assertEqual(actor_word(self.query(facing=facing)[0]['actor'], 4), x)

    def test_mode4_stops_horizontal_motion_without_selecting_or_animating(self):
        result, _ = self.query(mode=4)
        self.assertEqual([actor_word(result['actor'], o) for o in (10, 16, 18, 36, 38, 40)],
                         [15, 4, 0, 0, 2, 2])
        self.assertEqual(result['events'], [('frame',)])

    def test_ordinary_reaction_advances_to_first_pose_and_relative_y(self):
        result, _ = self.query()
        self.assertEqual([actor_word(result['actor'], o) for o in (6, 10, 16, 18, 36, 38, 40)],
                         [231, 102, 5, 5, 7, 45, 45])
        self.assertFalse(any(event[0] == 'audio' for event in result['events']))

    def test_float_link_changes_active_sequence_without_overwriting_selected_source(self):
        result, _ = self.query(floating=True)
        self.assertEqual([actor_word(result['actor'], o) for o in (6, 10, 36, 38, 40)],
                         [231, 102, 1, 229, 45])
        self.assertIn(('sequence', 229), result['events'])
        self.assertEqual(result['events'].count(('handle', 'HSetState')), 2)

    def test_missing_requested_sequence_animates_old_sequence_instead(self):
        result, _ = self.query(available=False, floating=True)
        self.assertEqual([actor_word(result['actor'], o) for o in (6, 10, 16, 36, 38, 40)],
                         [226, 15, 0, 3, 2, 2])
        self.assertIn(('resource', 45), result['events'])
        self.assertIn(('animate', 2, 0), result['events'])
        self.assertNotIn(('sequence', 229), result['events'])

    def test_loadframe_refreshes_supporting_column_after_backoff_and_animation(self):
        result, _ = self.query()
        self.assertEqual(actor_word(result['actor'], 12), 4)
        self.assertEqual(result['remainder'], 16)
        self.assertEqual(len(result['metadata']), 18)
        self.assertEqual(result['events'][-1], ('frame',))

    def test_health_and_vertical_velocity_remain_untouched(self):
        result, actor = self.query()
        for offset in (20, 28, 30, 42, 44, 46, 48):
            self.assertEqual(actor_word(result['actor'], offset), actor_word(actor, offset))
        self.assertEqual(result['mark'], 1)

    def test_backoff_wraps_before_supporting_column_reload(self):
        self.assertEqual(actor_word(self.query(x=-32768)[0]['actor'], 4), 32758)
        self.assertEqual(actor_word(self.query(x=32767, facing=-1)[0]['actor'], 4), -32759)
