import json
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops

from pop2.cavern_state import CavernState
from pop2.caverns import draw_cavern_darts, pressure_drawing_commands
from pop2.darts import Dart, dart_death
from pop2.paths import ASSET_DIR
from pop2.sequence_runtime import SequenceState
from pop2.terrain import LevelMap, TerrainMotion


class DartTests(unittest.TestCase):
    def setUp(self):
        self.level = bytearray(0x49ca)
        struct.pack_into('>H', self.level, 0x2186, 3)
        self.caverns = CavernState()
        self.terrain = LevelMap(self.level)
        self.terrain.caverns = self.caverns
        self.darts = self.caverns.plates.darts
        self.state = SequenceState(2, action=15, actor_type=0, facing=1)
        self.set_tile(13, 34, 1)
        self.set_tile(12, 33, 0x200)
        struct.pack_into('>5h', self.level, 0x168a, 1, 12, 0, -3, -3)

    def set_tile(self, cell, kind, foreground=0):
        struct.pack_into('>H', self.level, cell * 2, kind)
        struct.pack_into('>H', self.level, 0x780 + cell * 4, foreground)

    def press(self):
        return self.caverns.plates.push(self.terrain, self.terrain.tile(0, 3, 1))

    def advance(self):
        cues = self.darts.advance(self.terrain, 0, (100, 150, 120, 226), self.state)
        return cues + self.caverns.plates.advance(self.terrain)

    def test_fresh_button_fires_at_the_native_position_and_opens_the_mouth_immediately(self):
        self.assertEqual(self.press(), (27, 65))
        self.assertEqual(self.darts.projectiles, [Dart(0, 142, 215, 1)])
        self.assertEqual(self.terrain.tile(0, 2, 1).foreground, 0x201)

    def test_six_update_cooldown_preserves_decoration_and_requires_button_release(self):
        self.press()
        phases = []
        for _ in range(10):
            self.advance()
            self.assertEqual(self.press(), ())
            phases.append(self.terrain.tile(0, 2, 1).foreground)
        self.assertEqual(phases, [514, 515, 516, 517, 518, 512, 512, 512, 512, 512])
        for _ in range(5):
            self.advance()
        self.assertEqual(self.press(), (27, 65))
        self.assertEqual(self.darts.projectiles[-1], Dart(0, 142, 215, 1))

    def test_release_before_mouth_is_ready_does_not_bypass_the_cooldown(self):
        self.press()
        for _ in range(5):
            self.advance()
        self.assertEqual(self.press(), (27,))
        self.advance()
        self.assertEqual(self.press(), ())
        self.assertEqual(len(self.darts.projectiles), 1)

    def test_native_velocity_is_constant_and_crossing_solid_ceiling_removes_the_stone(self):
        self.set_tile(5, 1)
        self.press()
        trace = []
        for _ in range(5):
            cues = self.advance()
            dart = self.darts.projectiles[0]
            trace.append((dart.x, dart.y, dart.row, dart.dy, cues))
        self.assertEqual(trace, [(169, 196, 1, -19, ()), (196, 177, 1, -19, ()),
                                 (223, 158, 1, -19, ()), (250, 139, 1, -19, ()),
                                 (277, 120, 0, -3, (67,))])
        self.advance()
        self.assertEqual(self.darts.projectiles, [])

    def test_column_crossing_hits_a_wall_but_does_not_hit_the_floor_below(self):
        self.set_tile(13, 20)
        self.darts.spawn(0, 12)
        self.assertEqual(self.advance(), (67,))
        self.assertEqual(self.darts.projectiles[0].dy, -3)

    def test_gate_uses_native_opening_clearance(self):
        self.set_tile(13, 4, 0)
        self.darts.spawn(0, 12)
        self.assertEqual(self.advance(), (67,))
        self.darts.projectiles.clear()
        self.set_tile(13, 4, 184)
        self.darts.spawn(0, 12)
        self.assertEqual(self.advance(), ())
        self.assertEqual(self.darts.projectiles[0].dy, -19)

    def test_room_boundary_rebases_only_the_visible_incoming_neighbors(self):
        struct.pack_into('>4H', self.level, 0x2080, 2, 3, 0, 0)
        self.darts.projectiles = [Dart(1, 500, 200, 1)]
        self.advance()
        dart = self.darts.projectiles[0]
        self.assertEqual((dart.room, dart.x, dart.y, dart.dy), (0, 17, 181, -19))
        self.darts.projectiles = [Dart(0, 500, 200, 1)]
        self.assertEqual(self.advance(), ())
        self.assertEqual((self.darts.projectiles[0].x, self.darts.projectiles[0].dy), (500, -3))

    def test_leaving_an_unlinked_viewport_has_one_impact_sound(self):
        self.darts.projectiles = [Dart(0, 500, 200, 1)]
        self.assertEqual(self.advance(), (67,))
        self.assertEqual(self.advance(), ())
        self.assertEqual(self.darts.projectiles, [])

    def test_swept_hit_catches_a_fast_projectile_that_already_passed_the_body(self):
        dart = Dart(0, 142, 196, 1)
        self.assertTrue(dart.hits((140, 190, 150, 220)))
        self.assertFalse(dart.hits((140, 190, 150, 210)))
        self.assertFalse(dart.hits((140, 100, 150, 130)))

    def test_a_hit_consumes_only_that_projectile_and_checks_the_actor_room(self):
        first, second = Dart(0, 100, 200, 1), Dart(1, 100, 200, 1)
        self.darts.projectiles = [first, second]
        self.assertEqual(self.darts.contacts(0, self.state, (100, 150, 140, 226)), (first,))
        self.assertEqual((first.dy, second.dy), (-1, -19))
        self.assertEqual(self.darts.contacts(0, self.state, (100, 150, 140, 226)), ())

    def test_only_sequence_79_crouch_is_exempt_from_hit_testing(self):
        for sequence, action, immune in ((79, 108, True), (79, 112, True),
                                         (79, 113, False), (117, 109, False)):
            with self.subTest(sequence=sequence, action=action):
                self.state.select(sequence)
                self.state.action = action
                self.darts.projectiles = [Dart(0, 100, 200, 1)]
                self.assertEqual(bool(self.darts.contacts(0, self.state, (100, 150, 140, 226))),
                                 not immune)

    def test_consumed_projectiles_keep_native_active_bank_indexing(self):
        self.darts.projectiles = [Dart(0, 100, 200, 1) for _ in range(3)]
        self.assertEqual(len(self.darts.contacts(0, self.state, (100, 150, 140, 226))), 2)
        self.assertEqual([dart.dy for dart in self.darts.projectiles], [-1, -19, -1])

    def test_fatal_hit_selects_supported_death_or_ledge_fall(self):
        record = SimpleNamespace(offset_x=0, aux=0)
        self.state.target_x = 180
        self.set_tile(12, 1)
        self.assertEqual(dart_death(self.terrain, TerrainMotion(0, 1), self.state, record), (85, 0))
        self.set_tile(12, 0)
        self.assertEqual(dart_death(self.terrain, TerrainMotion(0, 1), self.state, record),
                         (18, -17))

    def test_projectile_banks_are_per_session(self):
        self.darts.spawn(0, 12)
        self.assertEqual(CavernState().plates.darts.projectiles, [])

    def test_flying_projectile_uses_shape_3594_at_its_inclusive_bottom_anchor(self):
        sprite = Image.new('RGBA', (5, 5), (255, 128, 0, 255))
        sprite.putpixel((0, 0), (0, 0, 0, 0))
        self.darts.projectiles = [Dart(0, 142, 196, 1), Dart(1, 160, 177, 1),
                                 Dart(0, 180, 158, 1, dy=-3), Dart(0, 200, 139, 1, dy=-1)]
        frame = Image.new('RGBA', (510, 365), (30, 20, 10, 255))
        expected = frame.copy()
        expected.paste(sprite, (142, 192), sprite)
        with patch('pop2.caverns.cavern_assets', return_value=(None, {}, {}, {})), \
                patch('pop2.caverns.cavern_command_sprite', return_value=sprite) as decode:
            self.assertIs(draw_cavern_darts(frame, 0, self.caverns), frame)
        decode.assert_called_once_with(['back', 3594, 142, 196, 16], {}, {}, {})
        self.assertIsNone(ImageChops.difference(frame, expected).convert('RGB').getbbox())
        self.assertEqual(self.darts.projectiles[0], Dart(0, 142, 196, 1))

    def test_shooter_mouth_replaces_only_its_native_slot_and_recomputes_the_clip(self):
        command = ['front', 3591, 127, 234, 16, 1, [228, 127, 234, 135], 4, 2, 1]
        record = {'kind': 33, 'foreground': 512, 'commands': [('front', 3591, 4, 2, 1)]}
        resources = {'SHAP': {3593: {'data': struct.pack('>4H', 0, 0, 5, 3)}}}
        self.assertEqual(pressure_drawing_commands([command], [record], (1,), resources),
                         [['front', 3593, 127, 234, 16, 1, [231, 127, 234, 132], 4, 2, 1]])
        self.assertEqual(command[1], 3591)


@unittest.skipUnless((ASSET_DIR / 'caverns_entry.json').is_file(), 'Imported game resources required')
class ImportedDartTests(unittest.TestCase):
    def test_projectile_pixels_match_native_one_based_shpl_lookup_not_the_mouth(self):
        from pop2.render_opening import decode_shap, load_resource_file
        from pop2.caverns import cavern_assets

        resources = load_resource_file('Caverns.rsrc')
        first, count = struct.unpack('>2H', resources['SHPL'][3500]['data'])
        self.assertGreaterEqual(count, 94)
        shape = first + 94 - 1
        self.assertEqual(shape, 3594)
        palette = cavern_assets()[2]
        sprite = decode_shap(resources['SHAP'][shape]['data'], palette)
        self.assertEqual(sprite.size, (5, 5))
        self.assertTrue(any(r > 200 and g > 80 and b < 50 and a
                            for _, (r, g, b, a) in sprite.getcolors()))
        state = CavernState()
        state.plates.darts.projectiles = [Dart(0, 142, 196, 1)]
        expected = Image.new('RGBA', (510, 365), (30, 20, 10, 255))
        frame = expected.copy()
        expected.paste(sprite, (142, 192), sprite)
        draw_cavern_darts(frame, 0, state)
        self.assertIsNone(ImageChops.difference(frame, expected).convert('RGB').getbbox())

    def test_running_over_both_buttons_fires_and_hits_without_an_animation_break(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.peaceful = True
        scene.load_level(3)
        scene.jump_to_room(15, row=1, x=60, facing=1)
        scene.horizontal_key(None, 1, True)
        flashes = 0
        for _ in range(34):
            RooftopSceneTests.tick(self)
            flashes += scene.sequence_state.hit_flash
            self.assertTrue(scene.combat.player.alive)
            self.assertLess(scene.action, 15)
        self.assertEqual(flashes, 2)
        self.assertEqual(scene.combat.player.life, 1)
        self.assertGreater(scene.player_x, 400)

    def test_all_nine_real_trap_buttons_fire_their_linked_shooter(self):
        from pop2.render_opening import load_resource_file

        level = load_resource_file('Prince.rsrc')['LEVL'][2002]['data']
        terrain = LevelMap(level)
        count = 0
        for room in range(32):
            for cell in range(30):
                caverns = CavernState()
                terrain.caverns = caverns
                tile = terrain.tile(room, cell % 10, cell // 10)
                if tile.kind != 34:
                    continue
                cues = caverns.plates.push(terrain, tile)
                for dart in caverns.plates.darts.projectiles:
                    count += 1
                    self.assertIn(65, cues)
                    self.assertEqual(dart.room, room)
                    self.assertEqual(terrain.tile(room, dart.x // 51, dart.row).kind, 33)
        self.assertEqual(count, 9)

    def test_export_binds_every_shooter_without_changing_other_scenery_slots(self):
        program = json.loads((ASSET_DIR / 'caverns_entry.json').read_text(encoding='ascii'))
        shooters = [r for room in program['pressure_plates']['rooms'].values()
                    for r in room if r['kind'] == 33]
        self.assertEqual(len(shooters), 9)
        self.assertEqual({tuple(key[:2]) for r in shooters for key in r['commands']},
                         {('front', 3591)})

    def test_scene_hit_does_not_interrupt_movement_and_pause_and_restart_clear_state(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.peaceful = True
        scene.load_level(3)
        scene.jump_to_room(15, row=1, x=190, facing=1)
        plates = scene.game.caverns.plates
        scene.start_sequence(1)
        before = scene.sequence_state.sequence_id, scene.sequence_state.cursor, scene.player_x
        plates.darts.projectiles = [Dart(15, 175, 195, 1) for _ in range(3)]
        scene.check_cavern_darts()
        self.assertEqual(scene.combat.player.life, 2)
        self.assertEqual(before, (scene.sequence_state.sequence_id,
                                 scene.sequence_state.cursor, scene.player_x))
        self.assertTrue(scene.sequence_state.hit_flash)
        self.assertEqual(scene.sequence_state.sound_events[-2:], [29, 66])
        plates.darts.spawn(15, 12)
        scene.set_paused(True)
        RooftopSceneTests.tick(self, 4)
        self.assertEqual(plates.darts.projectiles[-1], Dart(15, 142, 215, 1))
        scene.set_paused(False)
        scene.advance_cavern_floors()
        self.assertFalse(scene.sequence_state.hit_flash)
        scene.restart_level()
        self.assertEqual(scene.game.caverns.plates.darts.projectiles, [])

    def test_scene_last_life_uses_native_death_and_retry(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.peaceful = True
        scene.load_level(3)
        scene.jump_to_room(15, row=1, x=250, facing=1)
        scene.combat.player.life = 1
        scene.game.caverns.plates.darts.projectiles = [Dart(15, 235, 195, 1)]
        scene.check_cavern_darts()
        self.assertEqual(scene.combat.player.life, 0)
        self.assertEqual(scene.sequence_state.source_sequence_id, 85)
        self.assertEqual(scene.death.method, 0)
        self.assertEqual(scene.death.music_method, 0)
        RooftopSceneTests.tick(self, 50)
        self.assertTrue(scene.death.can_restart)

    def test_fatal_ledge_hit_keeps_falling_physics_until_landing(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.peaceful = True
        scene.load_level(3)
        scene.jump_to_room(15, row=1, x=200, facing=1)
        for x in range(150, 250):
            scene.sequence_state.target_x = scene.sequence_state.current_x = scene.player_x = x
            if dart_death(scene.level_map, scene.terrain_motion, scene.sequence_state,
                          scene.frames[scene.action])[0] == 18:
                break
        else:
            self.fail('No native ledge-fall position found')
        scene.combat.player.life = 1
        scene.game.caverns.plates.darts.projectiles = [Dart(15, x - 15, 195, 1)]
        scene.check_cavern_darts()
        self.assertEqual(scene.sequence_state.source_sequence_id, 18)
        self.assertTrue(scene.terrain_motion.falling)
        self.assertFalse(scene.terrain_motion.dead)
        RooftopSceneTests.tick(self, 65)
        self.assertTrue(scene.terrain_motion.dead)
        self.assertTrue(scene.death.can_restart)


if __name__ == '__main__':
    unittest.main()
