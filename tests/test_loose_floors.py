import struct
import unittest
from types import SimpleNamespace

from pop2.cavern_state import CavernState
from pop2.caverns import cavern_scene_signature
from pop2.loose_floors import FallingFloor, floor_hits_actor, rubble_tile
from pop2.paths import ASSET_DIR
from pop2.sequence_runtime import SequenceState, SequenceRuntime
from pop2.terrain import LevelMap, TerrainMotion
from tools.extract_caverns import loose_floor_cells


class LooseFloorTests(unittest.TestCase):
    def setUp(self):
        level = bytearray(0x49ca)
        for room in range(32):
            for cell in range(30):
                struct.pack_into('>H', level, room * 60 + cell * 2, 20)
        struct.pack_into('>H', level, 0x2186, 3)
        struct.pack_into('>H', level, 0x218a, 3)
        struct.pack_into('>H', level, 0x2198, 1)
        struct.pack_into('>H', level, 0x2086, 4)
        self.terrain = LevelMap(level)
        self.terrain.caverns = CavernState()
        self.loose = self.terrain.caverns.loose
        self.set_tile(0, 7, 11, 0x1100)
        self.set_tile(0, 17, 0, 0xa00)
        self.set_tile(0, 27, 0)
        self.set_tile(3, 7, 1, 1)
        self.state = SequenceState(2, action=15, facing=1, target_x=383,
                                   animation_state=0, actor_type=0)
        self.motion = TerrainMotion(0, 0)
        self.record = SimpleNamespace(offset_x=0, aux=0x40)

    def set_tile(self, room, cell, kind, foreground=0):
        struct.pack_into('>H', self.terrain.level, room * 60 + cell * 2, kind)
        struct.pack_into('>H', self.terrain.level, 0x780 + room * 120 + cell * 4, foreground)

    def tick(self):
        result = self.loose.advance_falling(self.terrain)
        self.loose.advance_tiles(self.terrain)
        return result

    def test_native_twelve_phase_collapse_preserves_floor_until_detachment(self):
        self.assertEqual(self.loose.press(self.terrain, self.motion, self.state, self.record), (28,))
        for phase in range(1, 12):
            self.tick()
            tile = self.terrain.tile(0, 7, 0)
            self.assertEqual((tile.kind, tile.foreground), (11, 0x1100 + phase))
            self.assertTrue(self.terrain.supports(0, 7, 0))
        self.tick()
        self.assertEqual(self.terrain.tile(0, 7, 0).kind, 0)
        self.assertEqual(self.terrain.tile(0, 7, 0).foreground, 0x103)
        self.assertFalse(self.terrain.supports(0, 7, 0))
        self.assertEqual(self.loose.falling, [FallingFloor(0, 7, 0, 143)])

    def test_native_falling_positions_and_lower_room_impact(self):
        # Executed CODE:5 FrameAdv order (MakeRubble, then AnimTrobs),
        # original level-three loose floor at room 1, column 7, row 0.
        self.loose.trigger(self.terrain.tile(0, 7, 0))
        for _ in range(12):
            self.tick()
        expected = ((0, 151, 8, 1), (0, 167, 16, 1), (0, 191, 24, 1),
                    (0, 223, 32, 1), (0, 263, 40, 2), (0, 311, 48, 2),
                    (3, 2, 56, 0), (3, 66, 64, 0))
        for room, y, velocity, row in expected:
            sounds, _blocks = self.tick()
            self.assertEqual(sounds, ())
            block = self.loose.falling[0]
            self.assertEqual((block.room, block.y, block.velocity, block.row), (room, y, velocity, row))
        sounds, _blocks = self.tick()
        self.assertEqual(sounds, (26,))
        self.assertEqual(self.loose.falling, [])
        tile = self.terrain.tile(3, 7, 0)
        self.assertEqual((tile.kind, tile.foreground), (14, 1))

    def test_repeated_foot_contact_does_not_restart_the_phase(self):
        self.loose.trigger(self.terrain.tile(0, 7, 0))
        for _ in range(7):
            self.tick()
            self.loose.press(self.terrain, self.motion, self.state, self.record)
        self.assertEqual(self.terrain.tile(0, 7, 0).foreground & 15, 7)

    def test_force_contact_detaches_on_the_next_trob_update(self):
        self.loose.trigger(self.terrain.tile(0, 7, 0), force=True)
        self.assertEqual(self.terrain.tile(0, 7, 0).foreground & 15, 11)
        self.tick()
        self.assertEqual(self.terrain.tile(0, 7, 0).kind, 0)

    def test_falling_contact_preserves_the_actor_velocity_in_the_slab(self):
        self.loose.trigger(self.terrain.tile(0, 7, 0), force=40)
        self.tick()
        self.assertEqual(self.loose.falling[0].velocity, 40)
        self.tick()
        self.assertEqual((self.loose.falling[0].y, self.loose.falling[0].velocity), (191, 48))

    def test_ordinary_guard_pressure_uses_the_same_floor_controller(self):
        self.state.actor_type = 2
        self.assertEqual(self.loose.press(self.terrain, self.motion, self.state, self.record), (28,))
        self.assertIn((0, 7), self.loose.active)

    def test_airborne_pose_without_foot_contact_does_not_press(self):
        self.record.aux = 0
        self.assertEqual(self.loose.press(self.terrain, self.motion, self.state, self.record), ())
        self.state.animation_state = 3
        self.record.aux = 0x40
        self.assertEqual(self.loose.press(self.terrain, self.motion, self.state, self.record), ())
        self.assertEqual(self.loose.active, {})

    def test_catch_pose_presses_the_loose_floor_above_across_room_links(self):
        struct.pack_into('>H', self.terrain.level, 0x2084, 32)
        self.set_tile(31, 27, 11)
        self.state.action = 79
        self.state.current_y = -80
        self.assertEqual(self.loose.press(self.terrain, self.motion, self.state, self.record), (28,))
        self.assertIn((31, 27), self.loose.active)

    def test_pressure_requires_the_native_eleven_pixel_height_tolerance(self):
        self.state.current_y = -12
        self.assertEqual(self.loose.press(self.terrain, self.motion, self.state, self.record), ())
        self.state.current_y = -11
        self.assertEqual(self.loose.press(self.terrain, self.motion, self.state, self.record), (28,))

    def test_warning_shake_stops_at_four_phases_and_third_shake_falls(self):
        for warning in (1, 2):
            self.assertEqual(self.loose.shake_row(self.terrain, 0, 0), (28,))
            for _ in range(4):
                self.tick()
            self.assertEqual(self.loose.active, {})
            self.assertEqual(self.terrain.tile(0, 7, 0).foreground, 0x1100 | warning << 4)
        self.loose.shake_row(self.terrain, 0, 0)
        for _ in range(12):
            self.tick()
        self.assertEqual(self.terrain.tile(0, 7, 0).kind, 0)

    def test_ordinary_foot_contact_converts_a_warning_into_a_collapse(self):
        self.loose.shake_row(self.terrain, 0, 0)
        self.tick()
        self.assertTrue(self.terrain.tile(0, 7, 0).foreground & 0x40)
        self.loose.press(self.terrain, self.motion, self.state, self.record)
        for _ in range(11):
            self.tick()
        self.assertEqual(self.terrain.tile(0, 7, 0).kind, 0)

    def test_both_adjacent_loose_floors_advance_independently(self):
        self.set_tile(0, 8, 11)
        for column in (7, 8):
            self.loose.trigger(self.terrain.tile(0, column, 0))
        for _ in range(12):
            self.tick()
        self.assertEqual([block.column for block in self.loose.falling], [7, 8])
        self.assertEqual([self.terrain.tile(0, col, 0).kind for col in (7, 8)], [0, 0])

    def test_slab_strikes_another_loose_floor_and_splits_without_double_advancing(self):
        self.set_tile(0, 17, 11)
        self.loose.falling.append(FallingFloor(0, 7, 1, 230, 24))
        self.tick()
        self.assertEqual(self.terrain.tile(0, 7, 1).kind, 0)
        self.assertEqual([(block.y, block.velocity, block.row) for block in self.loose.falling],
                         [(262, 16, 2), (268, 16, 2)])

    def test_void_fall_expires_without_creating_a_fake_room(self):
        self.loose.falling.append(FallingFloor(None, 7, 0, 390, 64))
        sounds, _blocks = self.tick()
        self.assertEqual((sounds, self.loose.falling), ((), []))

    def test_native_impact_tile_classification(self):
        for before, after in (((1, 0xa00), (14, 0xa00)), ((10, 0x30), (14, 0)),
                              ((19, 0x102), (32, 0x102)), ((20, 7), (20, 7)),
                              ((12, 1), (12, 0x21)), ((34, 2), (14, 0)), ((33, 3), (14, 0))):
            self.assertEqual(rubble_tile(*before), after)

    def test_actor_hit_uses_head_height_and_supporting_foot_column(self):
        block = FallingFloor(0, 7, 0, 49)
        self.assertFalse(floor_hits_actor(block, self.motion, self.state, self.record))
        block.y = 50
        self.assertTrue(floor_hits_actor(block, self.motion, self.state, self.record))
        self.state.target_x += 51
        self.assertFalse(floor_hits_actor(block, self.motion, self.state, self.record))
        self.state.target_x -= 51
        self.assertFalse(floor_hits_actor(block, self.motion, self.state, self.record, alive=False))

    def test_export_identifies_loose_and_impact_cells_from_links(self):
        cells = loose_floor_cells(self.terrain)
        self.assertEqual(set(cells), {(0, 7), (3, 7)})
        self.assertEqual(cells[0, 7][2], (0, 0x103))
        self.assertEqual(cells[3, 7], ((1, 1), (14, 1)))

    def test_detachment_clears_native_decoration_below_the_floor(self):
        self.loose.trigger(self.terrain.tile(0, 7, 0), force=True)
        self.tick()
        self.assertEqual(self.terrain.tile(0, 7, 1).foreground, 0)
        self.assertIn((0, 7), self.loose.cleared)

    def test_render_signature_normalizes_native_shake_phases_and_removal(self):
        program = {'loose_floors': {'shifts': [0, 1, 0, 1, 1, 0, 0, 0, 1, 0, 1, 0, 0],
                                   'cells': {'0:7': [[11, 0x1100], [11, 0x1101], [0, 0x103]]},
                                   'rooms': {'0': {'cells': [[0, 7]]}}}}
        for value, expected in ((0x1100, '0'), (0x1101, '1'), (0x1102, '0'), (0x1108, '1')):
            self.loose.tiles[0, 7] = 11, value
            self.assertEqual(cavern_scene_signature(program, 0, self.terrain.caverns), expected)
        self.loose.tiles[0, 7] = 0, 0x103
        self.assertEqual(cavern_scene_signature(program, 0, self.terrain.caverns), '2')

    def test_native_shake_sequence_operations_retain_request_direction(self):
        state = SequenceState(1)
        runtime = SequenceRuntime({1: (-20, 79, -19, 15)}, state)
        runtime.next_frame()
        runtime.next_frame()
        self.assertEqual(state.sequence_events, [(-20, ()), (-19, ())])


@unittest.skipUnless((ASSET_DIR / 'caverns_entry.json').is_file(), 'Imported game resources required')
class ImportedLooseFloorTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests
        RooftopSceneTests.setUp(self)
        self.scene.load_level(3)
        self.scene.peaceful = True
        self.scene.jump_to_room(0, row=0, x=225, facing=1)

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests
        RooftopSceneTests.tick(self, count)

    def test_player_standing_on_the_slab_falls_when_it_disappears(self):
        scene = self.scene
        record = scene.frames[15]
        x = 383 - (record.offset_x - (record.aux & 0x3f))
        scene.jump_to_room(0, row=0, x=x, facing=1)
        self.tick()
        self.assertIn((0, 7), scene.game.caverns.loose.active)
        self.tick(12)
        self.assertEqual(scene.level_map.tile(0, 7, 0).kind, 0)
        self.assertTrue(scene.terrain_motion.falling)
        self.assertEqual(scene.game.caverns.loose.falling[0].y, 143)

    def test_room_drawing_and_actor_climb_redraw_change_after_collapse(self):
        scene = self.scene
        before = scene.level_renderer.room(0, scene.game.caverns)
        loose = scene.game.caverns.loose
        loose.trigger(scene.level_map.tile(0, 7, 0), force=True)
        loose.advance_tiles(scene.level_map)
        after = scene.level_renderer.room(0, scene.game.caverns)
        self.assertNotEqual(before.background.tobytes(), after.background.tobytes())
        self.assertNotEqual(before.climb_redraw.get((137, 7, 0)), after.climb_redraw.get((137, 7, 0)))
        scene.game.restart()
        scene.game.caverns.configure_entry(scene.level_renderer.cavern_program.get('entry_exit'))
        reset = scene.level_renderer.room(0, scene.game.caverns)
        self.assertEqual(before.background.tobytes(), reset.background.tobytes())

    def test_falling_slab_moves_while_the_player_is_in_another_room(self):
        scene = self.scene
        loose = scene.game.caverns.loose
        loose.trigger(scene.level_map.tile(0, 7, 0), force=True)
        scene.jump_to_room(4, row=1, x=100, facing=1)
        self.tick(10)
        self.assertEqual(scene.level_map.tile(3, 7, 0).kind, 14)

    def test_crush_loses_one_life_and_finishes_recovery(self):
        scene = self.scene
        record = scene.frames[15]
        x = 434 - (record.offset_x - (record.aux & 0x3f))
        scene.jump_to_room(0, row=0, x=x, facing=1)
        scene.game.caverns.loose.falling.append(FallingFloor(0, 8, 0, 60, 16))
        life = scene.combat.player.life
        self.tick()
        self.assertEqual(scene.combat.player.life, life - 1)
        self.assertTrue(scene.combat.player.recovering)
        self.tick(40)
        self.assertFalse(scene.combat.player.recovering)

    def test_pause_freezes_both_shaking_and_falling_floors(self):
        scene = self.scene
        loose = scene.game.caverns.loose
        loose.trigger(scene.level_map.tile(0, 7, 0))
        loose.falling.append(FallingFloor(0, 8, 1, 170, 16))
        phase = loose.tiles.copy()
        scene.paused = True
        self.tick(5)
        self.assertEqual(loose.tiles, phase)
        self.assertEqual(loose.falling, [FallingFloor(0, 8, 1, 170, 16)])
        scene.paused = False
        self.tick()
        self.assertNotEqual(loose.tiles, phase)
        self.assertEqual(loose.falling[0].y, 194)

    def test_every_original_loose_floor_has_shaken_removed_and_landed_scenery(self):
        scene = self.scene
        program = scene.level_renderer.cavern_program
        cells = loose_floor_cells(LevelMap(scene.game.level.data))
        sources = [key for key, choices in cells.items() if choices[0][0] == 11]
        self.assertEqual(len(sources), 15)
        for room, cell in sources:
            with self.subTest(room=room, cell=cell):
                caverns = CavernState()
                caverns.configure_entry(program.get('entry_exit'))
                terrain = LevelMap(scene.game.level.data)
                terrain.caverns = caverns
                caverns.loose.trigger(terrain.tile(room, cell % 10, cell // 10))
                for phase in range(30):
                    caverns.loose.advance_falling(terrain)
                    caverns.loose.advance_tiles(terrain)
                    if phase not in (0, 11, 29):
                        continue
                    for visible_room, metadata in program['loose_floors']['rooms'].items():
                        if not set(map(tuple, metadata['cells'])) & caverns.loose.tiles.keys():
                            continue
                        art = scene.level_renderer.room(int(visible_room), caverns)
                        self.assertEqual(art.background.size, (510, 365))
                        self.assertTrue(art.background.getbbox())
