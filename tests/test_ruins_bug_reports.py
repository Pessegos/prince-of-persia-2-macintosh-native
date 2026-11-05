"""Isolated reproductions of the November ruins playtest reports."""

import unittest

from pop2.paths import ASSET_DIR


@unittest.skipUnless((ASSET_DIR / 'ruins_level9.json').is_file(), 'Imported ruins required')
class RuinsBugReportTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.tick(self, count)

    def test_falling_tile_on_scythe_survives_every_animation_phase(self):
        from pop2.caverns import cavern_scythe_signature
        from pop2.environments import environment_for
        from pop2.loose_floors import FallingFloor
        from pop2.scythes import SCYTHE_STATES

        scene = self.scene
        scene.load_level(7)
        scene.jump_to_room(7, 2, 250, 0)
        scene.peaceful = True
        caverns = scene.game.caverns
        traps = [(c, r) for r in range(3) for c in range(10)
                 if scene.level_map.tile(7, c, r).kind == 13]
        self.assertTrue(traps)
        column, row = traps[0]
        caverns.loose.falling.append(FallingFloor(7, column, row, row * 120 + 115, 8, 3))
        environment_for(scene).frame_start()
        self.assertTrue(scene.level_map.tile(7, column, row).foreground & 0x20)
        key = (7, row * 10 + column)
        caverns.scythes.active.add(key)
        phases = []
        for _ in range(22):
            caverns.scythes.advance(scene.level_map)
            phases.append(scene.level_map.tile(7, column, row).foreground & 0x1f)
            signature = cavern_scythe_signature(scene.level_renderer.cavern_program, 7, caverns)
            self.assertTrue(all(0 <= index < len(SCYTHE_STATES) for index in signature[1]))
            scene.render()
        self.assertEqual(phases[:20], list(range(1, 20)) + [0])
        self.assertNotIn(key, caverns.scythes.active)

    def test_room_seventeen_falling_tile_keeps_ordinary_opener_gate_open(self):
        from pop2.environments import environment_for
        from pop2.loose_floors import FallingFloor

        scene = self.scene
        scene.load_level(8)
        scene.jump_to_room(16, 2, 430, 0)
        caverns = scene.game.caverns
        buttons = [scene.level_map.tile(16, c, r) for r in range(3) for c in range(10)
                   if scene.level_map.tile(16, c, r).kind == 5]
        self.assertTrue(buttons)
        tile = buttons[0]
        index = tile.foreground & 255
        dest_room, dest_cell, *_ = caverns.plates.link(scene.level_map, index)
        caverns.loose.falling.append(FallingFloor(16, tile.column, tile.row,
                                                  tile.row * 120 + 115, 8, 3))
        environment_for(scene).frame_start()
        for _ in range(350):
            caverns.plates.advance(scene.level_map)
        gate = scene.level_map.tile(dest_room - 1, dest_cell % 10, dest_cell // 10)
        self.assertEqual(gate.foreground & 255, 255)
        self.assertEqual(caverns.plates.timer(scene.level_map, index), 31)

    def test_requested_empty_rooms_are_hidden_only_on_the_development_map(self):
        from pop2.development_map import _linked_positions, room_positions

        scene = self.scene
        for number, hidden in ((8, (27, 15, 7)), (9, (23, 22))):
            scene.load_level(number)
            positions = room_positions(scene.level_map)
            original = _linked_positions(scene.level_map, scene.game.level.start_room)
            self.assertEqual(set(original) - set(positions), {room - 1 for room in hidden})
            for room in hidden:
                self.assertNotIn(room - 1, positions)
            self.assertIn(scene.game.level.start_room, positions)
            # Layout and native links remain available to gameplay.
            self.assertEqual(len(scene.game.level.data), len(scene.resources.level(number).data))
