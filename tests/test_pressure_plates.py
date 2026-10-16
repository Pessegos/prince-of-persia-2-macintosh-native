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


class PressureDrawingTests(unittest.TestCase):
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


@unittest.skipUnless((ASSET_DIR / 'caverns_entry.json').is_file(), 'Imported game resources required')
class ImportedPressurePlateTests(unittest.TestCase):
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
            scene.advance_cavern_floors()
        gate = scene.level_map.tile(16, 7, 2)
        self.assertFalse(stone_gate_blocks(gate.foreground, (400, 275, 420, 346)))
        scene.restart_level()
        self.assertEqual(scene.game.caverns.plates.active, {})
        # Debris activates plates before this update's gate animation pass.
        scene.game.caverns.loose.plate_events.append((16, 12, 34))
        scene.advance_cavern_floors()
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
