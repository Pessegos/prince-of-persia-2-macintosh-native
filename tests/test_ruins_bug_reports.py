"""Isolated reproductions of the November ruins playtest reports."""

import unittest
from unittest.mock import patch

from PIL import Image, ImageOps

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

    def test_level_eight_exit_opcode_plays_exit_and_loads_nine(self):
        scene = self.scene
        scene.load_level(8)
        scene.game.story.tree_stage = 7
        scene.sequence_state.sequence_events.append((-16, ()))
        scene.advance_level_events()
        self.assertTrue(scene.level_complete)
        self.assertIsNotNone(scene.game.exit)
        self.assertEqual(scene.game.exit.song, 124)
        # Let the actual completion callback consume the finished exit.
        with patch.object(scene.game.exit, 'advance', return_value=True):
            self.tick()
        self.assertEqual(scene.game.level.number, 9)

    def test_waking_with_fathers_sword_removes_the_floor_sword_and_survives_reentry(self):
        from pop2.environments import environment_for

        scene = self.scene
        scene.load_level(8)
        scene.jump_to_room(8, 2, 267, 1)
        self.assertEqual(scene.level_map.tile(8, 5, 2).kind, 22)
        environment_for(scene).wake_from_vision()
        self.assertEqual(scene.game.sword_type, 1)
        self.assertEqual(scene.level_map.tile(8, 5, 2).kind, 1)
        scene.jump_to_room(7, 2, 200, 0, reset_guards=False)
        scene.jump_to_room(8, 2, 267, 1, reset_guards=False)
        self.assertEqual(scene.level_map.tile(8, 5, 2).kind, 1)

    def test_serpent_hit_uses_head_shape_127_at_native_offsets_in_both_facings(self):
        from pop2.combat import actor_frame_index
        from pop2.render_opening import character_sprite_top, decode_shap

        scene = self.scene
        scene.load_level(7)
        scene.jump_to_room(19, 2, 200, 1)
        serpent = scene.combat.visible_ruins()[0]
        scene.combat.ruins.jump(serpent, 173)
        serpent.runtime.next_frame()
        state = serpent.state
        state.animation_state = 10
        art = scene.guard_art.default
        burst = decode_shap(art.shapes[art.base + 127]['data'], art.palettes[1])
        for facing in (0, 1):
            state.facing = facing
            record = art.frames[actor_frame_index(state)]
            expected = Image.new('RGBA', (510, 365))
            sprite = ImageOps.mirror(burst) if facing else burst
            dx = record.offset_x - 12
            x = state.target_x + dx - sprite.width if facing else state.target_x - dx
            y = character_sprite_top(346 + state.current_y + record.offset_y + 7, sprite.height)
            expected.paste(sprite, (x, y), sprite)
            actual = Image.new('RGBA', expected.size)
            scene.hit_art.draw(actual, state, 346)
            self.assertIsNotNone(actual.getbbox())
            self.assertEqual(actual.tobytes(), expected.tobytes())
