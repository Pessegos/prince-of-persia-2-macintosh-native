from dataclasses import replace
import struct
import unittest

from tests import test_temple_controller_geometry_reference as geometry_tests
from tests.test_temple_player_control_reference import CLIPS
from tools.probe_temple_controller_geometry import geometry_player_reference
from tools.probe_temple_frame_progression import frame_callback
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_player_control import PlayerInputs
from tools.probe_temple_slide_rock_update import actor_word
from tools.probe_temple_world_bounds import sprite_callback
from tools.probe_temple_sprite_bounds import DEFAULT_RECT
from tools.probe_temple_world_prince import world_reference


class TempleWorldBoundsTests(unittest.TestCase):
    def state(self):
        state = geometry_tests.TempleControllerGeometryTests().state(facing=0)
        level = bytearray(state['level'])
        # Above-left wall forces the rock's left edge to consult body width.
        struct.pack_into('>h', level, 2 * 2, 20)
        state.update(level=bytes(level), mob_records=((203, 116, 1, 0, -2, 6, 0, 459),),
                     frame_metadata=bytes(18), drawing=struct.pack('>10h', -1, 53, 59, -1, 2, 61, 67, 71, 73, 79),
                     bounds=(389, 229, 227, 418, 400, 103, 101), edge_cells=(137, 139, 149, 151),
                     current_edges=(101, 103, 227, 229), bound_events=[])
        return state

    def frames(self, *, second_shape=False):
        frames = bytearray(3520)
        if second_shape:
            struct.pack_into('>5h', frames, 135 * 10, 1, 0, 0, 0, 0)
        return bytes(frames)

    def world(self, *, width=20, second_shape=False, state=None, inputs=None):
        return world_reference(self.state() if state is None else state, CLIPS,
                               PlayerInputs(raw_axes=(0, -1, -1)) if inputs is None else inputs,
                               geometry_player_reference, frame_callback(self.frames(second_shape=second_shape), bytes(8)),
                               sprite_callback({0: (width, 40), 1: (40, 60)}))

    def test_actual_frame_width_changes_climb_choice_at_a_clipped_rock(self):
        narrow, wide = self.world(width=20), self.world(width=40)
        self.assertEqual((actor_word(narrow['prince'], 40), actor_word(wide['prince'], 40)), (73, 10))
        self.assertEqual((narrow['frame_width'], wide['frame_width']), (21, 41))
        self.assertIn(('clip_left',), narrow['events'])
        self.assertIn(('clip_left',), wide['events'])

    def test_saved_edges_come_from_post_animation_frame_not_initial_frame_or_constants(self):
        result = self.world(second_shape=True)
        self.assertEqual(result['saved_edges'], (60, 41, 359, 400))
        self.assertEqual(result['saved_edges'], result['current_edges'])
        self.assertEqual(result['frame_width'], 41)
        self.assertEqual([e for e in result['bound_events'] if e[0] == 'shape_size'],
                         [('shape_size', 0), ('shape_size', 1)])

    def test_final_actor_save_contains_clipped_visual_rectangle(self):
        result = self.world(second_shape=True)
        self.assertEqual(struct.unpack_from('>4h', result['prince'], 42), (51, 153, 111, 193))
        self.assertEqual(result['working'], result['prince'])
        self.assertEqual((actor_word(result['prince'], 6), actor_word(result['prince'], 14)), (110, 1))

    def test_control_queries_occur_after_initial_edges_and_before_second_load(self):
        result = self.world()
        events = [e[0] for e in result['events']]
        edges = [i for i, name in enumerate(events) if name == 'edges']
        self.assertEqual(len(edges), 2)
        self.assertLess(edges[0], events.index('rock_in_cell'))
        self.assertLess(events.index('rock_in_cell'), edges[1])
        self.assertLess(edges[1], events.index('prince_copy'))

    def test_suppressed_animation_saves_only_initial_edges(self):
        inputs = replace(PlayerInputs(raw_axes=(0, -1, -1)), suppress_animation=1)
        result = self.world(second_shape=True, inputs=inputs)
        self.assertEqual(result['saved_edges'], (40, 21, 379, 400))
        self.assertEqual(sum(e[0] == 'shape_size' for e in result['bound_events']), 1)

    def test_missing_size_preserves_edge_canaries_and_resets_visible_rectangle(self):
        state = self.state()
        actor = bytearray(state['prince'])
        put_actor(actor, 10, 91)
        state['frame_metadata'] = bytes(18)
        result = sprite_callback({})(bytes(actor), state)
        self.assertEqual(result['updates']['bounds'], state['bounds'])
        self.assertEqual(result['updates']['frame_width'], 18)
        self.assertEqual(result['updates']['current_edges'], state['current_edges'])
        self.assertEqual(struct.unpack_from('>4h', result['actor'], 42), DEFAULT_RECT)
        self.assertEqual(state['bound_events'], [])


if __name__ == '__main__':
    unittest.main()
