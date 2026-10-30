import json
import struct
from types import SimpleNamespace
import unittest

from pop2.cavern_state import CavernState
from pop2.caverns import cavern_pressure_signature, pressure_drawing_commands
from pop2.paths import ASSET_DIR
from pop2.pressure_plates import PressurePlates
from pop2.sequence_runtime import SequenceState
from pop2.terrain import LevelMap, TerrainMotion
from pop2.environments import environment_for


class PressurePlateTests(unittest.TestCase):
    def setUp(self):
        self.level = bytearray(0x49ca)
        struct.pack_into('>H', self.level, 0x2186, 3)
        struct.pack_into('>H', self.level, 0x218a, 3)
        self.caverns = CavernState()
        self.plates = self.caverns.plates
        self.terrain = LevelMap(self.level)
        self.terrain.caverns = self.caverns
        self.set_tile(0, 14, 34, 1)
        self.set_tile(0, 15, 4, 0x300)
        self.set_link(1, 1, 15)

    def set_tile(self, room, cell, kind, foreground):
        struct.pack_into('>H', self.level, room * 60 + cell * 2, kind)
        struct.pack_into('>H', self.level, 0x780 + room * 120 + cell * 4, foreground)

    def set_link(self, index, room, cell, timer=0, previous=-3, following=-3):
        struct.pack_into('>5h', self.level, 0x1680 + index * 10,
                         room, cell, timer, previous, following)

    def push(self):
        return self.plates.push(self.terrain, self.terrain.tile(0, 4, 1))

    def test_button_click_depresses_the_plate_before_its_five_tick_release(self):
        self.assertEqual(self.push(), (27,))
        self.assertEqual(self.plates.active, {(0, 14): 1, (0, 15): 2})
        self.assertEqual(self.terrain.tile(0, 4, 1).foreground, 0x2001)
        for remaining in (4, 3, 2, 1):
            self.plates.advance(self.terrain)
            self.assertEqual(self.plates.timer(self.terrain, 1), remaining)
            self.assertTrue(self.terrain.tile(0, 4, 1).foreground & 0x2000)
        self.plates.advance(self.terrain)
        self.assertEqual(self.plates.timer(self.terrain, 1), 0)
        self.assertFalse(self.terrain.tile(0, 4, 1).foreground & 0x2000)

    def test_gate_opens_waits_and_closes_with_native_phases_and_sounds(self):
        self.push()
        trace = []
        for tick in range(146):
            cues = self.plates.advance(self.terrain)
            trace.append((self.terrain.tile(0, 5, 1).foreground & 255,
                          self.plates.active.get((0, 15)), cues))
        self.assertEqual(trace[0], (4, 2, (17,)))
        self.assertEqual(trace[44], (180, 2, (17,)))
        self.assertEqual(trace[45], (237, 0, (18,)))
        self.assertEqual(trace[98], (184, 0, ()))
        self.assertEqual(trace[99], (183, 1, (17,)))
        self.assertEqual(trace[-1], (0, None, (18,)))
        self.assertEqual(self.terrain.tile(0, 5, 1).foreground, 0x300)

    def test_iron_gates_outside_the_caverns_use_their_own_sounds(self):
        # ATMGate/StopGate test LEVL 0x2186: environment 4 (ruins) selects
        # 272-275, and a rising iron gate asks for 272 every eighth pixel.
        struct.pack_into('>H', self.level, 0x2186, 4)
        self.push()
        trace = []
        for tick in range(146):
            cues = self.plates.advance(self.terrain)
            trace.append((self.terrain.tile(0, 5, 1).foreground & 255,
                          self.plates.active.get((0, 15)), cues))
        self.assertEqual(trace[0], (4, 2, ()))
        self.assertEqual(trace[1], (8, 2, (272,)))
        self.assertEqual(trace[44], (180, 2, ()))
        self.assertEqual(trace[43], (176, 2, (272,)))
        self.assertEqual(trace[45], (237, 0, (273,)))
        self.assertEqual(trace[99], (183, 1, (272,)))
        self.assertEqual(trace[-1], (0, None, (274,)))
        self.assertFalse({17, 18, 20} & {cue for *_, cues in trace for cue in cues})

    def test_iron_gate_slam_and_full_open_stop(self):
        struct.pack_into('>H', self.level, 0x2186, 4)
        self.plates.foreground[0, 15] = 0x300 | 10
        self.plates.active[0, 15] = 4
        record = SimpleNamespace(offset_x=0, aux=0)
        state = SequenceState(2, action=15, target_x=100, facing=1)
        self.assertEqual(self.plates.advance(self.terrain, state, TerrainMotion(0, 1), record), (275,))
        self.plates.foreground[0, 15] = 0x300 | 184
        self.plates.active[0, 15] = 3
        self.assertEqual(self.plates.advance(self.terrain), (274,))

    def test_holding_keeps_the_gate_open_without_repeated_plate_clicks(self):
        self.push()
        for tick in range(200):
            self.plates.advance(self.terrain)
            self.assertEqual(self.push(), ())
            if tick >= 45:
                self.assertEqual(self.terrain.tile(0, 5, 1).foreground & 255, 237)
        self.assertEqual(self.plates.timer(self.terrain, 1), 5)

    def test_closing_gate_tracks_crush_poses_and_stops_with_the_native_clearance(self):
        state = SequenceState(118, action=264, target_x=310, facing=1)
        motion = TerrainMotion(0, 1, dead=True)
        record = SimpleNamespace(offset_x=0, aux=0)
        self.plates.foreground[0, 15] = 0x300 | 88
        self.plates.active[0, 15] = 1
        for phase in (87, 86, 85):
            self.assertEqual(self.plates.advance(self.terrain, state, motion, record), (17,))
            self.assertEqual(self.terrain.tile(0, 5, 1).foreground & 255, phase)
        state.action = 265
        self.plates.advance(self.terrain, state, motion, record)
        self.assertEqual(self.terrain.tile(0, 5, 1).foreground & 255, 56)
        state.action = 266
        self.plates.advance(self.terrain, state, motion, record)
        self.assertEqual(self.terrain.tile(0, 5, 1).foreground & 255, 52)
        self.assertNotIn((0, 15), self.plates.active)
        self.assertEqual(self.plates.stopped_sounds, [17])

    def test_fast_gate_stops_at_fifty_six_only_for_nearby_crush_sequence(self):
        record = SimpleNamespace(offset_x=0, aux=0)
        for sequence, row, x, expected in ((118, 1, 310, 56), (2, 1, 310, 0),
                                           (118, 2, 310, 0), (118, 1, 100, 0)):
            self.plates.foreground[0, 15] = 0x300 | 40
            self.plates.active[0, 15] = 4
            state = SequenceState(sequence, action=264, target_x=x, facing=1)
            self.assertEqual(self.plates.advance(self.terrain, state, TerrainMotion(0, row), record), (20,))
            self.assertEqual(self.terrain.tile(0, 5, 1).foreground & 255, expected)
            self.assertNotIn((0, 15), self.plates.active)

    def test_crush_sequence_final_slam_closes_to_forty_eight_and_stops_once(self):
        record = SimpleNamespace(offset_x=0, aux=0)
        state = SequenceState(118, action=264, sequence_mode=3,
                              target_x=5 * 51 + 35, facing=1)
        motion = TerrainMotion(0, 1, dead=True)
        self.plates.foreground[0, 15] = 0x300 | 82
        self.plates.active[0, 15] = 1
        self.assertEqual(self.plates.advance(self.terrain, state, motion, record), (17, 20, 18))
        self.assertEqual(self.plates.foreground[0, 15], 0x300 | 48)
        self.assertNotIn((0, 15), self.plates.active)
        for action in (265, 266, 266):
            state.action, state.sequence_mode = action, 0
            self.assertEqual(self.plates.advance(self.terrain, state, motion, record), ())
            self.assertEqual(self.plates.foreground[0, 15], 0x300 | 48)

    def test_slow_crush_contact_is_narrower_than_fast_close_proximity(self):
        record = SimpleNamespace(offset_x=0, aux=0)
        state = SequenceState(118, action=264, sequence_mode=3, facing=1)
        motion = TerrainMotion(0, 1, dead=True)
        for column, expected in ((4, 48), (5, 48), (6, 78), (7, 78)):
            with self.subTest(column=column):
                state.target_x = column * 51 + 35
                self.plates.foreground[0, 15] = 0x300 | 82
                self.plates.active[0, 15] = 1
                cues = self.plates.advance(self.terrain, state, motion, record)
                self.assertEqual(self.plates.foreground[0, 15] & 255, expected)
                self.assertEqual(cues, (17, 20, 18) if expected == 48 else (17,))

    def test_slow_crush_contact_rebases_horizontal_neighbors_not_distant_rooms(self):
        struct.pack_into('>H', self.level, 0x2080, 2)
        struct.pack_into('>H', self.level, 0x2082, 3)
        record = SimpleNamespace(offset_x=0, aux=0)
        state = SequenceState(118, action=264, sequence_mode=3, facing=1)
        motion = TerrainMotion(0, 1, dead=True)
        for room, cell, column, expected in ((1, 19, -1, True), (1, 19, -2, True),
                                            (1, 19, 0, False), (2, 10, 10, True),
                                            (2, 10, 9, True), (2, 10, 11, False),
                                            (3, 15, 5, False)):
            with self.subTest(room=room, cell=cell, column=column):
                state.target_x = column * 51 + 35
                self.assertEqual(self.plates.crushing_body_under_gate(
                    self.terrain, (room, cell), state, motion, record), expected)

    def test_gate_closing_on_fingers_sounds_once_in_both_native_hanging_modes(self):
        record = SimpleNamespace(offset_x=0, aux=0)
        for mode in (2, 6):
            for facing in (0, 1):
                for column in (5, 6):
                    for phase, position, expected in ((1, 4, (18, 29)), (4, 40, (29, 20))):
                        with self.subTest(mode=mode, facing=facing, column=column, phase=phase):
                            state = SequenceState(25, action=91, animation_state=mode,
                                                  target_x=column * 51 + 35, facing=facing)
                            motion = TerrainMotion(0, 2)
                            before = vars(state).copy(), vars(motion).copy()
                            self.plates.foreground[0, 15] = 0x300 | position
                            self.plates.active[0, 15] = phase
                            self.assertEqual(self.plates.advance(self.terrain, state, motion, record),
                                             expected)
                            self.assertEqual(self.terrain.tile(0, 5, 1).foreground, 0x300)
                            self.assertNotIn((0, 15), self.plates.active)
                            self.assertEqual(self.plates.advance(self.terrain, state, motion, record), ())
                            self.assertEqual((vars(state), vars(motion)), before)

    def test_finger_contact_uses_native_room_mode_and_supporting_foot_cell(self):
        record = SimpleNamespace(offset_x=0, aux=0)
        state = SequenceState(25, animation_state=6, target_x=5 * 51 + 35)
        for room in (0, 1):
            for row in (0, 1, 2, 3):
                for column in range(10):
                    for mode in range(10):
                        state.target_x = column * 51 + 35
                        state.animation_state = mode
                        motion = TerrainMotion(room, row)
                        self.assertEqual(self.plates.fingers_under_gate((0, 15), state, motion, record),
                                         room == 0 and row == 2 and column in (5, 6) and mode in (2, 6))
        state.animation_state = 6
        state.target_x = 4 * 51 + 35
        self.assertFalse(self.plates.fingers_under_gate((0, 15), state, TerrainMotion(0, 2), record))
        record.offset_x = 51
        state.facing = 1
        self.assertTrue(self.plates.fingers_under_gate((0, 15), state, TerrainMotion(0, 2), record))
        for missing in ((None, TerrainMotion(0, 2), record), (state, None, record),
                        (state, TerrainMotion(0, 2), None)):
            self.assertFalse(self.plates.fingers_under_gate((0, 15), *missing))

    def test_gate_does_not_hurt_fingers_before_finishing_or_when_opening(self):
        record = SimpleNamespace(offset_x=0, aux=0)
        state = SequenceState(25, animation_state=6, target_x=5 * 51 + 35)
        motion = TerrainMotion(0, 2)
        for phase, position, expected in ((1, 8, (17,)), (4, 80, ()),
                                           (2, 180, (18,)), (3, 180, (18,)), (0, 255, (18,))):
            with self.subTest(phase=phase, position=position):
                self.plates.foreground[0, 15] = 0x300 | position
                self.plates.active[0, 15] = phase
                self.assertEqual(self.plates.advance(self.terrain, state, motion, record), expected)

    def test_crushing_proximity_crosses_horizontal_room_links_but_not_vertical_ones(self):
        struct.pack_into('>H', self.level, 0x2080, 2)
        struct.pack_into('>H', self.level, 0x2082, 3)
        record = SimpleNamespace(offset_x=0, aux=0)
        state = SequenceState(118, action=264, target_x=20, facing=1)
        motion = TerrainMotion(0, 1)
        self.assertTrue(self.plates.squashing_player(self.terrain, (1, 19), state, motion, record))
        self.assertFalse(self.plates.squashing_player(self.terrain, (1, 29), state, motion, record))
        state.target_x = 525
        self.assertTrue(self.plates.squashing_player(self.terrain, (2, 10), state, motion, record))

    def test_rearmed_reverse_plate_closes_an_open_gate_and_cannot_reopen_while_held(self):
        self.push()
        for _ in range(46):
            self.plates.advance(self.terrain)
        self.assertEqual(self.push(), (27,))
        self.assertEqual(self.plates.active[(0, 15)], 4)
        self.assertEqual(self.terrain.tile(0, 5, 1).foreground & 255, 184)
        phases = []
        for _ in range(5):
            cues = self.plates.advance(self.terrain)
            self.push()
            phases.append(self.terrain.tile(0, 5, 1).foreground & 255)
        self.assertEqual(phases, [124, 44, 0, 0, 0])
        self.assertEqual(cues, ())

    def test_links_cross_rooms_and_walk_the_full_original_chain(self):
        self.set_tile(1, 29, 4, 0x200)
        self.set_link(1, 1, 15, following=2)
        self.set_link(2, 2, 29, previous=1)
        self.push()
        self.assertEqual(self.plates.triggered, [(4, 0, 15, 34), (4, 1, 29, 34)])
        self.plates.advance(self.terrain)
        self.assertEqual(self.terrain.tile(1, 9, 2).foreground, 0x204)

    def test_all_three_effect_destinations_are_resolved_without_invented_room_rules(self):
        for kind in (4, 33, 17):
            with self.subTest(kind=kind):
                self.set_tile(0, 15, kind, 0)
                self.push()
                self.assertEqual(self.plates.triggered[-1], (kind, 0, 15, 34))

    def test_unused_links_do_not_target_a_different_room(self):
        self.set_link(1, -2, -1)
        self.push()
        self.assertEqual(self.plates.triggered, [])
        self.assertNotIn((0, 15), self.plates.active)

    def test_bad_chains_fail_explicitly_instead_of_looping(self):
        self.set_link(1, 1, 15, following=1)
        with self.assertRaisesRegex(ValueError, 'Cyclic'):
            self.push()

    def test_supporting_foot_and_animation_flags_control_contact(self):
        record = SimpleNamespace(offset_x=0, aux=0x40)
        state = SequenceState(2, target_x=250, action=15, facing=1,
                              actor_type=0, animation_state=0)
        motion = TerrainMotion(0, 1)
        self.assertEqual(self.plates.press(self.terrain, motion, state, record), (27,))
        for mode in (2, 3, 4, 6, 9):
            state.animation_state = mode
            self.assertEqual(self.plates.press(self.terrain, motion, state, record), ())
        state.animation_state = 0
        record.aux = 0
        self.assertEqual(self.plates.press(self.terrain, motion, state, record), ())

    def test_stone_impact_holds_the_button_and_opens_the_gate_permanently(self):
        self.assertEqual(self.plates.impact(self.terrain, 0, 14, 34), ())
        self.assertEqual(self.plates.timer(self.terrain, 1), 31)
        for _ in range(200):
            self.plates.advance(self.terrain)
        self.assertEqual(self.terrain.tile(0, 5, 1).foreground & 255, 255)
        self.assertNotIn((0, 15), self.plates.active)


class CaveBarsTests(unittest.TestCase):
    """TriggerCaveBars 8:1672 and the bars animation 8:1508 (level five, room 3)."""

    def setUp(self):
        PressurePlateTests.setUp(self)
        self.set_tile(0, 15, 27, 0)

    def set_tile(self, room, cell, kind, foreground):
        PressurePlateTests.set_tile(self, room, cell, kind, foreground)

    def set_link(self, *arguments):
        PressurePlateTests.set_link(self, *arguments)

    def run_bars(self, frames):
        trace = []
        for _ in range(frames):
            cues = self.plates.advance(self.terrain)
            trace.append((self.terrain.tile(0, 5, 1).foreground & 7, cues))
        return trace

    def test_a_fresh_press_opens_closed_bars_and_the_next_closes_open_bars(self):
        PressurePlateTests.push(self)
        self.assertEqual(self.plates.active[0, 15], 0)
        self.assertEqual(self.run_bars(4), [(1, (282,)), (2, ()), (3, ()), (3, ())])
        self.assertNotIn((0, 15), self.plates.active)
        self.run_bars(5)
        self.assertFalse(self.terrain.tile(0, 4, 1).foreground & 0x2000)
        PressurePlateTests.push(self)
        self.assertEqual(self.plates.active[0, 15], 1)
        self.assertEqual(self.run_bars(4), [(2, (284,)), (1, ()), (0, ()), (0, ())])

    def test_held_plates_and_moving_bars_are_ignored(self):
        self.plates.trigger(self.terrain, 1, 34, depressed=True)
        self.assertEqual(self.plates.active, {})
        self.plates.foreground[0, 15] = 2
        self.plates.trigger(self.terrain, 1, 34)
        self.assertEqual(self.plates.active, {})


class LevelFiveRoomSevenGateTests(unittest.TestCase):
    """ATMGate 5:4396-43bc: level five's room-7 gate never starts closing."""

    def gate(self, level_number, room):
        PressurePlateTests.setUp(self)
        struct.pack_into('>H', self.level, 0x218a, level_number)
        PressurePlateTests.set_tile(self, room, 15, 4, 0x300 | 237)
        self.plates.active[room, 15] = 0
        for _ in range(60):
            self.plates.advance(self.terrain)
        return self.terrain.tile(room, 5, 1).foreground & 255

    def set_tile(self, room, cell, kind, foreground):
        PressurePlateTests.set_tile(self, room, cell, kind, foreground)

    def set_link(self, *arguments):
        PressurePlateTests.set_link(self, *arguments)

    def test_a_bridge_skeleton_cannot_open_a_shut_reversible_gate(self):
        # TriggerGateWithRevPlate 8:2d66-2d96: skeleton (actor 4) on a row
        # other than 0 of level five's rooms 7/10/12; the Prince still opens it.
        from pop2.animation_data import FrameRecord
        from pop2.sequence_runtime import SequenceState
        from pop2.terrain import TerrainMotion

        for number, actor_type, opens in ((5, 4, False), (5, 0, True), (4, 4, True)):
            with self.subTest(number=number, actor_type=actor_type):
                PressurePlateTests.setUp(self)
                struct.pack_into('>H', self.level, 0x218a, number)
                self.set_tile(9, 14, 34, 1)
                state = SequenceState(2, action=15, target_x=4 * 51 + 30, actor_type=actor_type)
                self.plates.press(self.terrain, TerrainMotion(9, 1), state, FrameRecord(15, 0, 0, 0, 0, 0x40))
                self.assertEqual((0, 15) in self.plates.active, opens)

    def test_room_seven_gate_holds_open_only_in_level_five(self):
        self.assertEqual(self.gate(5, 6), 237)
        self.assertLess(self.gate(4, 6), 184)
        self.assertLess(self.gate(5, 5), 184)


class PressureDrawingTests(unittest.TestCase):
    def test_cave_bars_draw_the_custom_record_of_their_phase(self):
        command = ['back', 4051, 165, 50, 0, 0, [10, 165, 50, 318], 4, 6, 0]
        record = {'kind': 27, 'foreground': 0, 'room': 2, 'cell': 6,
                  'commands': [('back', 4051, 4, 6, 0)]}
        for phase, shape in enumerate((4051, 4052, 4053, 4064)):
            self.assertEqual(pressure_drawing_commands([command], [record], (phase,), {}),
                             [['back', shape, *command[2:]]])
        state = CavernState()
        state.plates.foreground[2, 6] = 3
        metadata = {'pressure_plates': {'rooms': {'2': [record]}}}
        self.assertEqual(cavern_pressure_signature(metadata, 2, state), (3,))

    def test_gate_moves_its_original_shapes_and_keeps_the_native_top_clip(self):
        command = ['back', 3563, 408, 357, 16, 2, [211, 408, 357, 449], 4, 7, 2]
        record = {'kind': 4, 'foreground': 0x300,
                  'commands': [('back', 3563, 4, 7, 2)]}
        resources = {'SHAP': {3563: {'data': struct.pack('>4H', 0, 0, 41, 146)}}}
        expected = ['back', 3563, 408, 265, 16, 2, [209, 408, 265, 449], 4, 7, 2]
        self.assertEqual(pressure_drawing_commands([command], [record], (46,), resources), [expected])
        self.assertEqual(command[3], 357)

    def test_plate_changes_only_its_shape_and_gate_waits_share_one_visual_phase(self):
        command = ['back', 3554, 206, 365, 16, 2, [335, 206, 365, 295], 4, 4, 2]
        record = {'kind': 34, 'foreground': 1, 'room': 0, 'cell': 14,
                  'commands': [('back', 3554, 4, 4, 2)]}
        rendered = pressure_drawing_commands([command], [record], (1,), {})
        self.assertEqual(rendered[0], [command[0], 3555, *command[2:]])
        repaint = ['front', *command[1:6], [349, 206, 360, 230], *command[7:]]
        self.assertEqual(pressure_drawing_commands([repaint], [record], (1,), {}),
                         [['front', 3555, *repaint[2:]]])
        state = CavernState()
        gate = {'kind': 4, 'foreground': 0, 'room': 0, 'cell': 15}
        metadata = {'pressure_plates': {'rooms': {'0': [gate, record]}}}
        for position in range(184, 256):
            state.plates.foreground[0, 15] = position
            self.assertEqual(cavern_pressure_signature(metadata, 0, state), (46, 0))

    def test_front_gate_keeps_its_cap_above_the_dirty_cell_clip_fixed(self):
        command = ['front', 3562, 283, 358, 16, 2, [238, 283, 358, 306], 4, 5, 2]
        record = {'kind': 4, 'foreground': 0x300,
                  'commands': [('front', 3562, 4, 5, 2)]}
        resources = {'SHAP': {3562: {'data': struct.pack('>4H', 0, 0, 23, 120)}}}
        self.assertEqual(pressure_drawing_commands([command], [record], (0,), resources), [command])
        cap = ['front', 3562, 283, 358, 16, 2, [238, 283, 245, 306], 4, 5, 2]
        for phase in range(1, 47):
            with self.subTest(phase=phase):
                actual = pressure_drawing_commands([command], [record], (phase,), resources)
                self.assertEqual(actual[0], cap)
                self.assertEqual(actual[1][3], 358 - phase * 2)
                self.assertEqual(actual[1][6], [245, 283, 358 - phase * 2, 306])
        self.assertEqual(command[6], [238, 283, 358, 306])

    def test_gate_fragment_uses_the_repaint_row_not_the_source_row(self):
        # A gate below the viewed room is still repainted by visible row 2.
        command = ['front', 3562, 283, 478, 16, 3, [358, 283, 365, 306], 4, 5, 2]
        record = {'kind': 4, 'foreground': 0,
                  'commands': [('front', 3562, 4, 5, 2)]}
        resources = {'SHAP': {3562: {'data': struct.pack('>4H', 0, 0, 23, 120)}}}
        actual = pressure_drawing_commands([command], [record], (46,), resources)
        self.assertEqual(len(actual), 1)
        self.assertEqual(actual[0][6], [329, 283, 365, 306])

    def test_initially_open_front_gate_keeps_its_cap_when_closing_or_opening(self):
        resources = {'SHAP': {3562: {'data': struct.pack('>4H', 0, 0, 23, 120)}}}
        for row in range(3):
            for initial in (1, 16, 46):
                bottom = row * 120 + 118 - initial * 2
                clip = [max(0, row * 120 - 31, bottom - 120), 283, bottom, 306]
                command = ['front', 3562, 283, bottom, 16, row, clip, 4, 5, row]
                record = {'kind': 4, 'foreground': 0x300 | initial * 4,
                          'commands': [('front', 3562, 4, 5, row)]}
                for phase in (0, 4, 27, 46):
                    with self.subTest(row=row, initial=initial, phase=phase):
                        actual = pressure_drawing_commands([command], [record], (phase,), resources)
                        if phase == initial:
                            self.assertEqual(actual, [command])
                            continue
                        self.assertEqual(actual[0][3], bottom)
                        self.assertEqual(actual[0][6], [clip[0], 283, row * 120 + 5, 306])
                        self.assertEqual(actual[1][3], row * 120 + 118 - phase * 2)
                        self.assertEqual(actual[1][6][0], row * 120 + 5)

    def test_front_gate_floor_repaint_does_not_add_a_cap_outside_its_clip(self):
        command = ['front', 3562, 283, 358, 16, 2, [245, 283, 358, 306], 4, 5, 2]
        record = {'kind': 4, 'foreground': 0,
                  'commands': [('front', 3562, 4, 5, 2)]}
        resources = {'SHAP': {3562: {'data': struct.pack('>4H', 0, 0, 23, 120)}}}
        actual = pressure_drawing_commands([command], [record], (46,), resources)
        self.assertEqual(len(actual), 1)
        self.assertEqual(actual[0][6], [245, 283, 266, 306])


@unittest.skipUnless((ASSET_DIR / 'caverns_entry.json').is_file(), 'Imported game resources required')
class ImportedPressurePlateTests(unittest.TestCase):
    @unittest.skipUnless((ASSET_DIR / 'caverns_level4.json').is_file(),
                         'Imported level-four resources required')
    def test_level_four_room_eleven_preserves_the_upper_pillar_during_gate_motion(self):
        from PIL import Image, ImageChops
        from pop2.caverns import cavern_room

        closed = cavern_room(10, pressure_key=(0, 0, 0, 0), animated=True, level_number=4)
        expected = Image.alpha_composite(closed.background, closed.foreground)
        footprint = (283, 215, 306, 245)
        for phase in (1, 4, 16, 27, 46):
            with self.subTest(phase=phase):
                room = cavern_room(10, pressure_key=(0, 0, 0, phase), animated=True, level_number=4)
                actual = Image.alpha_composite(room.background, room.foreground)
                self.assertIsNone(ImageChops.difference(
                    expected.crop(footprint).convert('RGB'),
                    actual.crop(footprint).convert('RGB')).getbbox())
                self.assertIsNotNone(ImageChops.difference(
                    expected.convert('RGB'), actual.convert('RGB')).getbbox())

    def test_all_real_buttons_resolve_to_the_native_object_types(self):
        from pop2.render_opening import load_resource_file

        level = load_resource_file('Prince.rsrc')['LEVL'][2002]['data']
        terrain = LevelMap(level)
        kinds, buttons = set(), 0
        for room in range(32):
            for cell in range(30):
                tile = terrain.tile(room, cell % 10, cell // 10)
                if tile.kind != 34:
                    continue
                buttons += 1
                plates = PressurePlates()
                plates.push(terrain, tile)
                kinds.update(event[0] for event in plates.triggered)
        self.assertEqual(buttons, 27)
        self.assertEqual(kinds, {4, 17, 33})

    def test_import_covers_visible_gate_and_plate_fragments_and_no_other_shapes(self):
        program = json.loads((ASSET_DIR / 'caverns_entry.json').read_text(encoding='ascii'))
        records = [r for room in program['pressure_plates']['rooms'].values() for r in room]
        self.assertEqual(len({(r['room'], r['cell']) for r in records if r['kind'] == 4}), 9)
        self.assertEqual(len({(r['room'], r['cell']) for r in records if r['kind'] == 34}), 27)
        self.assertEqual({(r['room'], r['cell']) for r in records if r['kind'] == 17},
                         {(12, 16), (29, 25)})
        for record in records:
            self.assertTrue(record['commands'])
            for key in record['commands']:
                self.assertIn(key[1], (3554, 3562, 3563, 3566, 3591))
        # Room 4 also shows the top of Room 23's gate at its lower edge.
        self.assertTrue(any((r['room'], r['cell'], r['kind']) == (22, 1, 4)
                            for r in program['pressure_plates']['rooms']['3']))

    def test_scene_pressure_pause_restart_and_live_gate_collision(self):
        from tests.test_terrain import RooftopSceneTests
        from pop2.terrain import stone_gate_blocks

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(3)
        scene.jump_to_room(16, row=1, x=145, facing=1)
        # Use the real idle FRAM supporting-foot offset, not an assumed sprite anchor.
        record = scene.frames[scene.sequence_state.action]
        scene.sequence_state.target_x += (record.aux & 0x3f) - record.offset_x
        scene.advance_level_events()
        plates = scene.game.caverns.plates
        self.assertEqual(plates.active[(16, 27)], 2)
        before = plates.foreground.copy(), plates.active.copy(), plates.timers.copy()
        scene.set_paused(True)
        for _ in range(20):
            scene.advance_animation()
        self.assertEqual((plates.foreground, plates.active, plates.timers), before)
        scene.set_paused(False)
        for _ in range(46):
            environment_for(scene).frame_start()
        gate = scene.level_map.tile(16, 7, 2)
        self.assertFalse(stone_gate_blocks(gate.foreground, (400, 275, 420, 346)))
        scene.restart_level()
        self.assertEqual(scene.game.caverns.plates.active, {})
        # Debris activates plates before this update's gate animation pass.
        scene.game.caverns.loose.plate_events.append((16, 12, 34))
        environment_for(scene).frame_start()
        self.assertEqual(scene.level_map.tile(16, 7, 2).foreground & 255, 4)
        self.assertEqual(scene.game.caverns.plates.active[(16, 27)], 3)
        self.assertEqual(scene.game.caverns.loose.plate_events, [])

    def test_held_run_activates_the_plate_waits_for_clearance_and_crosses_the_gate(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(3)
        scene.jump_to_room(2, row=2, x=250, facing=1)
        scene.horizontal_key(None, 1, True)
        RooftopSceneTests.tick(self)
        self.assertEqual(scene.level_map.tile(2, 5, 2).foreground & 255, 4)
        RooftopSceneTests.tick(self, 19)
        self.assertEqual(scene.room_id, 2)
        self.assertLess(scene.sequence_state.target_x, 295)
        RooftopSceneTests.tick(self, 40)
        self.assertEqual(scene.room_id, 2)
        self.assertGreater(scene.sequence_state.target_x, 327)
        self.assertTrue(scene.combat.player.alive)
        # Historical gate heights must not retain dozens of complete room images.
        self.assertLessEqual(sum(key[0] == 2 for key in scene.level_renderer.cavern_frames), 2)


if __name__ == '__main__':
    unittest.main()
