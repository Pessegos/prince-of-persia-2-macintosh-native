"""Isolated reproductions of the November ruins playtest reports."""

import unittest
from unittest.mock import patch
from types import SimpleNamespace

from PIL import Image, ImageOps

from pop2.paths import ASSET_DIR


class UnloadedRuinsContactTests(unittest.TestCase):
    def test_record_column_truncates_negative_x_and_contact_has_a_velocity_window(self):
        from pop2.loose_floors import FallingFloor, floor_hits_ruins_record
        from pop2.sequence_runtime import SequenceState

        actor = SimpleNamespace(room=0, row=1, alive=True,
            state=SequenceState(130, target_x=-106),
            ruins=SimpleNamespace(kind=6, removed=False))
        # Native X101 -> (101-229)/51 = -2 with signed long division.
        block = FallingFloor(0, -2, 1, 170, 8, 3)
        self.assertTrue(floor_hits_ruins_record(block, actor))
        block.column = -3
        self.assertFalse(floor_hits_ruins_record(block, actor))
        block.column = -2
        for bottom, expected in ((169, False), (170, True), (201, True), (202, False)):
            block.y = bottom  # row1 floor226 -57 =169; velocity window32.
            self.assertEqual(floor_hits_ruins_record(block, actor), expected)
        block.y, block.velocity = 170, 0
        self.assertFalse(floor_hits_ruins_record(block, actor))


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

    def test_room_eight_jump_survives_shelves_striking_a_moving_scythe(self):
        from pop2.caverns import cavern_scene_signature
        from pop2.scythes import SCYTHE_STATES

        scene = self.scene
        scene.load_level(7)
        scene.jump_to_room(7, 1, 180, 0)
        scene.god_mode = scene.peaceful = True
        scene.set_key_state('up', True)
        # A real standing jump shakes all three shelves onto the active trap.
        # Keep level-event scenery updates live: the earlier test only called
        # render(), which never refreshed the loose-floor scene signature.
        with patch.object(scene, 'render'), patch.object(scene, 'advance_audio'):
            self.tick(40)
        loose = scene.game.caverns.loose
        self.assertEqual([loose.tiles[7, cell][0] for cell in (2, 3, 4)], [0, 0, 0])
        self.assertEqual([loose.tiles[7, cell][1] & 0x20 for cell in (12, 13)], [32, 32])
        self.assertEqual(scene.combat.player.life, scene.combat.player.max_life)
        program = scene.level_renderer.cavern_program
        # Both halves have independent static-debris slots. Neither animated
        # phase nor blood flags may affect that slot, before or after impact.
        for debris in (0, 32):
            for phase in SCYTHE_STATES:
                for cell, kind in ((12, 12), (13, 13)):
                    loose.tiles[7, cell] = kind, phase | debris
                signature = cavern_scene_signature(program, 7, scene.game.caverns)
                self.assertEqual(signature[3:5], str(int(bool(debris))) * 2)
                scene.level_renderer.enter_room(7, scene.game.caverns)

    def test_room_nine_slab_recovery_unlocks_after_bumping_the_column(self):
        scene = self.scene
        scene.load_level(9)
        scene.jump_to_room(8, 1, 172, 0)
        scene.peaceful = True
        scene.set_key_state('shift', True)
        scene.set_key_state('down', True)
        poses = []
        with patch.object(scene, 'render'), patch.object(scene, 'advance_audio'):
            for tick in range(55):
                if tick == 7:
                    scene.set_key_state('down', False)
                if tick == 10:
                    scene.set_key_state('shift', False)
                if tick == 11:
                    scene.set_key_state('shift', True)
                if tick == 30:
                    scene.set_key_state('shift', False)
                self.tick()
                poses.append((scene.sequence_state.source_sequence_id,
                              scene.combat.player.recovering))
            self.assertIn((52, True), poses)
            self.assertIn((47, True), poses)
            self.assertEqual((scene.room_id, scene.terrain_motion.row), (8, 2))
            self.assertEqual(scene.level_map.tile(8, 2, 2).kind, 14)
            self.assertEqual(scene.combat.player.life, 2)
            self.assertEqual(scene.action, 15)
            self.assertFalse(scene.combat.player.recovering)
            self.assertFalse(scene._combat_controls_locked())
            # Actual controls must work after the collision, not just a
            # synthetic flag reset. Up starts the real climb by the column.
            scene.set_key_state('up', True)
            self.tick(3)
            self.assertEqual(scene.sequence_state.source_sequence_id, 24)
            self.assertTrue(scene.native_ledge)
            self.assertNotEqual(scene.action, 15)

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

    def test_throne_keeps_floor_sword_and_old_drawn_sword_until_physical_pickup(self):
        from pop2.environments import environment_for

        scene = self.scene
        scene.load_level(8)
        scene.peaceful = True
        scene.jump_to_room(8, 2, 267, 1)
        self.assertEqual(scene.level_map.tile(8, 5, 2).kind, 22)
        self.assertEqual(scene.sword_set(), 2)
        environment_for(scene).wake_from_vision()
        # The native logical word changes for checkpoint/exit admission,
        # but the loaded sword artwork does not reload until TryPickUp.
        self.assertEqual(scene.game.sword_type, 1)
        self.assertEqual(scene.level_map.tile(8, 5, 2).kind, 22)
        self.assertEqual(scene.sword_set(), 2)
        with patch.object(scene, 'render'), patch.object(scene, 'advance_audio'):
            self.tick(40)
            scene.set_key_state('ctrl', True)
            self.tick()
            scene.set_key_state('ctrl', False)
            self.tick(20)
        self.assertTrue(scene.sword_drawn)
        self.assertEqual(scene.sword_set(), 2)
        self.assertEqual(scene.level_map.tile(8, 5, 2).kind, 22)
        # Return to the floor item and take it through ordinary held Shift,
        # including the crouch/pickup sequence, rather than calling take_sword.
        scene.jump_to_room(8, 2, 267, 1, reset_guards=False)
        with patch.object(scene, 'render'), patch.object(scene, 'advance_audio'):
            scene.set_key_state('shift', True)
            self.tick(20)
            scene.set_key_state('shift', False)
        self.assertEqual(scene.level_map.tile(8, 5, 2).kind, 1)
        self.assertEqual(scene.sword_set(), 1)
        scene.jump_to_room(7, 2, 200, 0, reset_guards=False)
        scene.jump_to_room(8, 2, 267, 1, reset_guards=False)
        self.assertEqual(scene.level_map.tile(8, 5, 2).kind, 1)
        self.assertEqual(scene.sword_set(), 1)
        scene.restart_opening(play_sound=False, redraw=False)
        self.assertEqual((scene.game.sword_type, scene.sword_set()), (2, 2))
        self.assertEqual(scene.level_map.tile(8, 5, 2).kind, 22)

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
        # SetupHit3:0bc2-0bc4 keeps palette base16 (Kid CTBL25004),
        # even when3:0c04 selects the Head shape library. Head CTBL750
        # would incorrectly make the orange centre pink/purple.
        burst = decode_shap(art.shapes[art.base + 127]['data'], scene.palette)
        colors = {rgba for _count, rgba in burst.getcolors()}
        self.assertIn((220, 141, 70, 255), colors)
        self.assertNotIn((168, 46, 117, 255), colors)
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

    def test_room_two_tunnel_stops_crawling_at_the_wall_with_left_still_held(self):
        scene = self.scene
        scene.load_level(8)
        scene.peaceful = True
        scene.jump_to_room(1, 2, 310, 0)
        scene.start_sequence(121)
        scene.sequence_runtime.next_frame()
        scene.action = scene.sequence_state.action
        scene.in_animation_tick = True
        scene.horizontal_key(None, -1, True)
        scene.in_animation_tick = False
        with patch.object(scene, 'render'), patch.object(scene, 'advance_audio'):
            self.tick(50)
            stopped = scene.sequence_state.target_x
            self.assertLess(stopped, 310)
            for _ in range(30):
                self.tick()
                self.assertEqual((scene.sequence_state.target_x, scene.sequence_state.action),
                                 (stopped, 251))
            scene.in_animation_tick = True
            scene.horizontal_key(None, -1, False)
            scene.horizontal_key(None, 1, True)
            scene.in_animation_tick = False
            self.tick(15)
        self.assertGreater(scene.sequence_state.target_x, stopped)

    def test_level_seven_room_twenty_eight_imports_its_head_without_duplication(self):
        scene = self.scene
        scene.load_level(7)
        scene.jump_to_room(27, 0, 300, 0)
        brain = scene.combat.ruins
        heads = [actor for actor in scene.combat.visible_ruins() if actor.state.actor_type in (7, 8)]
        self.assertEqual(len(heads), 1)
        head = heads[0]
        self.assertEqual((head.room, head.state.target_x), (27, 47))
        scene.jump_to_room(19, 1, 200, 0, reset_guards=False)
        self.assertEqual((head.room, head.state.target_x), (19, 557))
        self.assertFalse(any(actor is head for actor in brain.actors(27)))
        scene.jump_to_room(27, 0, 300, 0, reset_guards=False)
        self.assertTrue(any(actor is head for actor in scene.combat.visible_ruins()))
        self.assertEqual(sum(actor is head for actors in brain.rooms.values() for actor in actors), 1)

    def test_level_nine_room_twelve_imports_its_serpent_and_preserves_its_death(self):
        scene = self.scene
        scene.load_level(9)
        scene.jump_to_room(11, 2, 350, 0)
        actors = scene.combat.visible_ruins()
        self.assertEqual(len(actors), 1)
        serpent = actors[0]
        self.assertEqual((serpent.room, serpent.state.actor_type, serpent.state.target_x), (11, 11, 98))
        serpent.life = 0
        scene.combat.ruins.jump(serpent, 174)
        serpent.runtime.next_frame()
        scene.jump_to_room(12, 2, 300, 0, reset_guards=False)
        scene.jump_to_room(11, 2, 350, 0, reset_guards=False)
        self.assertIn(serpent, scene.combat.visible_ruins())
        self.assertEqual(serpent.life, 0)
        self.assertFalse(any(actor.alive for actor in scene.combat.visible_ruins()))

    def test_room_five_loose_floor_kills_room_nine_head_while_prince_stays_upstairs(self):
        scene = self.scene
        scene.load_level(7)
        scene.peaceful = False
        scene.jump_to_room(4, 2, 330, 0)
        scene.in_animation_tick = True
        scene.set_key_state('shift', True)
        scene.set_key_state('down', True)
        scene.in_animation_tick = False
        with patch.object(scene, 'render'), patch.object(scene, 'advance_audio'):
            # Actual initial descent and climb from the supplied recording.
            for tick in range(36):
                if tick == 9:
                    scene.set_key_state('down', False)
                elif tick == 16:
                    scene.set_key_state('up', True)
                elif tick == 18:
                    scene.set_key_state('up', False)
                self.tick()
            scene.clear_keys(None)
            self.assertEqual(scene.room_id, 4)
            head, = scene.combat.ruins.actors(8)
            self.assertTrue(head.alive)
            self.assertEqual(int((head.state.target_x - 22) / 51), 3)
            # Force only the later upper slab collapse; neither head position
            # nor its controller/timers are supplied or held constant.
            scene.game.caverns.loose.trigger(scene.level_map.tile(4, 3, 2), force=True)
            self.tick(25)
        self.assertEqual(scene.room_id, 4)
        self.assertTrue(head.ruins.removed)
        self.assertEqual(head.life, 0)
        scene.jump_to_room(8, 0, 150, 0, reset_guards=False)
        self.assertNotIn(head, scene.combat.visible_ruins())
