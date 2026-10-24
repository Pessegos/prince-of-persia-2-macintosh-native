import struct
import unittest

from tests import test_temple_controller_geometry_reference as geometry_tests
from tests.test_temple_player_control_reference import CLIPS
from tools.probe_temple_controller_geometry import geometry_player_reference
from tools.probe_temple_frame_progression import continue_reference, frame_callback
from tools.probe_temple_gate_actor_clip import clip_reference, put_actor
from tools.probe_temple_player_control import PlayerInputs
from tools.probe_temple_slide_rock_update import actor_word
from tools.probe_temple_world_prince import world_reference


class TempleFrameProgressionTests(unittest.TestCase):
    def state(self, *, facing=0, x=400, sequence=10):
        state = geometry_tests.TempleControllerGeometryTests().state(facing=facing)
        actor = bytearray(state['prince'])
        for offset, value in ((4, x), (36, 0), (38, sequence), (40, sequence)):
            put_actor(actor, offset, value)
        state.update(prince=bytes(actor), working=bytes(actor), frame_metadata=bytes(range(18)))
        return state

    def loader(self, *, dx=0):
        frame = struct.pack('>5h', 0, 0, dx, 0, 0)
        return frame_callback(frame * 352, bytes(8))

    def test_real_frame_column_precedes_controller_cell_queries(self):
        state = self.state()
        result = world_reference(state, CLIPS, PlayerInputs(raw_axes=(0, -1, -1)),
                                 geometry_player_reference, self.loader())
        # Anchor400 maps to column3, unlike the fixture's stale column2.
        self.assertIn(('read_cell', 1, 3, 0), result['events'])
        self.assertEqual(actor_word(result['prince'], 12), 3)
        self.assertEqual(result['frame_metadata'], bytes(18))
        self.assertEqual(actor_word(state['prince'], 12), 2)

    def test_frame_after_relative_x_can_change_support_without_copying_saved_actor(self):
        state = self.state(x=420)
        state = continue_reference(state, {}, 'frame', self.loader())
        saved = state['prince']
        clips = {10: (-5, 23, 141)}
        animated = continue_reference(state, clips, 'animate', self.loader())
        framed = continue_reference(animated, clips, 'frame', self.loader())
        self.assertEqual(actor_word(animated['working'], 4), 443)
        self.assertEqual(actor_word(animated['working'], 12), 3)
        self.assertEqual(actor_word(framed['working'], 12), 4)
        self.assertEqual(framed['prince'], saved)
        self.assertEqual(framed['events'], [('frame',)])

    def test_climb_tail_moves_x_y_and_row_then_loads_frame(self):
        state = self.state()
        clips = {10: (-7, 1, 135, 136, 137, 138, 139, 140, -5, 23, -6, -120, -3, 141, -1, 235)}
        for _ in range(7):
            state = continue_reference(state, clips, 'animate', self.loader())
            state = continue_reference(state, clips, 'frame', self.loader())
        self.assertEqual(tuple(actor_word(state['working'], n) for n in (4, 6, 10, 12, 14)),
                         (423, -10, 141, 3, 0))
        self.assertEqual(tuple(actor_word(state['prince'], n) for n in (4, 6, 14)), (400, 110, 1))
        # The next link lies outside the prepared clip domain.
        with self.assertRaises(ValueError):
            continue_reference(state, clips, 'animate', self.loader())

    def test_row_decrement_does_not_consume_the_following_pose(self):
        state = self.state()
        result = clip_reference(state['working'], {10: (-3, 141)}, vertical=True)
        self.assertEqual(tuple(actor_word(result['actor'], n) for n in (10, 14, 36)), (141, 0, 2))

    def test_vertical_opcodes_remain_explicitly_opt_in(self):
        for clip in ((-3, 141), (-6, 11, 81)):
            with self.subTest(clip=clip), self.assertRaises(ValueError):
                clip_reference(self.state()['working'], {10: clip})

    def test_vertical_word_arithmetic_wraps_and_preserves_unrelated_actor_bytes(self):
        actor = bytearray(self.state()['working'])
        put_actor(actor, 6, 32767)
        put_actor(actor, 14, -32768)
        result = clip_reference(actor, {10: (-6, 1, -3, 141)}, vertical=True)['actor']
        self.assertEqual((actor_word(result, 6), actor_word(result, 14)), (-32768, 32767))
        for offset in (0, 2, 4, 8, 12, 16, 28, 30, 38, 40, 58):
            self.assertEqual(actor_word(result, offset), actor_word(actor, offset))

    def test_gate_reaction_links_to_idle_without_replacing_selected_source(self):
        state = self.state(sequence=47)
        clips = {47: (-7, 5, -5, -16, 50, 51, 52, -1, 2), 2: (-7, 0, 15, -1, 2)}
        for _ in range(4):
            state = continue_reference(state, clips, 'animate', self.loader())
        self.assertEqual(tuple(actor_word(state['working'], n) for n in (4, 10, 16, 38, 40)),
                         (384, 15, 0, 2, 47))

    def test_frame_changes_attachment_metadata_but_not_saved_actor_or_events_of_prior_state(self):
        state = self.state()
        state['events'] = [('canary',)]
        result = continue_reference(state, {}, 'frame', frame_callback(bytes(3520), bytes(range(8))))
        self.assertEqual(result['frame_metadata'], bytes(range(8)) + bytes(10))
        self.assertEqual(result['prince'], state['prince'])
        self.assertEqual(state['events'], [('canary',)])

    def test_unrecovered_commands_or_full_world_continuation_are_rejected(self):
        for clip in ((-8, 1, 21), (-6,)):
            with self.subTest(clip=clip), self.assertRaises(ValueError):
                clip_reference(self.state()['working'], {10: clip}, vertical=True)
        with self.assertRaises(ValueError):
            continue_reference(self.state(), {}, 'world', self.loader())


if __name__ == '__main__':
    unittest.main()
