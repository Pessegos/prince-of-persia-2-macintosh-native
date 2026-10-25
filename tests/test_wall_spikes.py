import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops

from pop2.cavern_state import CavernState
from pop2.caverns import draw_cavern_spikes
from pop2.paths import ASSET_DIR
from pop2.sequence_runtime import SequenceState
from pop2.terrain import LevelMap, TerrainMotion
from pop2.wall_spikes import WallSpikes, drawing_phase, lethal
from pop2.environments import environment_for


class WallSpikeTests(unittest.TestCase):
    def setUp(self):
        self.level = bytearray(0x49ca)
        struct.pack_into('>H', self.level, 0x2186, 3)
        struct.pack_into('>H', self.level, 24 * 2, 2)
        self.caverns = CavernState()
        self.terrain = LevelMap(self.level)
        self.terrain.caverns = self.caverns
        self.spikes = self.caverns.spikes
        self.motion = TerrainMotion(0, 2)
        self.state = SequenceState(1, action=1, actor_type=0, target_x=292, facing=0)
        self.record = SimpleNamespace(offset_x=0, aux=0)
        self.bounds = 280, 280, 310, 346

    def tile(self):
        return self.terrain.tile(0, 4, 2)

    def approach(self, sword=False):
        self.spikes.approach(self.terrain, self.motion, self.state, self.record, self.bounds, sword)

    def hit(self, alive=True, sword=False):
        return self.spikes.contact(self.terrain, self.motion, self.state, self.record,
                                   self.bounds, alive, sword)

    def test_proximity_starts_the_first_pose_without_immediate_sound(self):
        self.approach()
        self.assertEqual(self.tile().foreground, 1)
        self.assertEqual(self.spikes.active, {(0, 24)})
        self.assertEqual(self.spikes.advance(self.terrain, 0), (282,))
        self.assertEqual(self.tile().foreground, 2)

    def test_full_native_cycle_has_two_outward_poses_fifteen_hold_updates_and_three_return_poses(self):
        self.approach()
        phases, cues = [1], []
        for _ in range(20):
            cues.extend(self.spikes.advance(self.terrain, 0))
            phases.append(self.tile().foreground)
        self.assertEqual(phases, [1, 2, *range(143, 128, -1), 4, 5, 6, 0])
        self.assertEqual(cues, [282, 284])
        self.spikes.advance(self.terrain, 0)
        self.assertEqual(self.tile().foreground, 0)
        self.assertFalse(self.spikes.active)

    def test_staying_near_the_trap_renews_the_hold_but_does_not_repeat_the_attack(self):
        self.approach()
        self.spikes.advance(self.terrain, 0)
        self.spikes.advance(self.terrain, 0)
        for _ in range(30):
            self.spikes.advance(self.terrain, 0)
            self.approach()
            self.assertEqual(self.tile().foreground, 143)
            self.assertIsNone(self.hit())

    def test_proximity_does_not_interrupt_retraction(self):
        self.spikes.foreground[0, 24] = 4
        self.approach()
        self.assertEqual(self.tile().foreground, 4)

    def test_high_jump_does_not_trigger_or_die(self):
        self.state.current_y = -72
        self.approach()
        self.assertEqual(self.tile().foreground, 0)
        self.spikes.foreground[0, 24] = 1
        self.assertIsNone(self.hit())

    def test_mouse_does_not_trigger_or_die_but_skeleton_can_trigger(self):
        self.state.actor_type = 4
        self.approach()
        self.assertEqual(self.tile().foreground, 0)
        self.state.actor_type = 1
        self.approach()
        self.assertEqual(self.tile().foreground, 1)
        self.assertIsNone(self.hit())

    def test_trigger_uses_facing_body_width_and_sword_state(self):
        self.state.target_x = 314
        self.approach()
        self.assertEqual(self.tile().foreground, 0)
        self.state.facing = 1
        self.approach()
        self.assertEqual(self.tile().foreground, 1)
        self.spikes = self.caverns.spikes = WallSpikes()
        self.state.target_x, self.state.facing = 292, 0
        self.approach(sword=True)
        self.assertEqual(self.tile().foreground, 0)

    def test_only_extending_poses_are_lethal_and_blood_is_a_distinct_pose(self):
        self.assertEqual([v for v in range(256) if lethal(v)], [1, 2])
        self.assertEqual([drawing_phase(v) for v in (0, 1, 2, 143, 128, 4, 5, 6, 240)],
                         [0, 1, 2, 3, 3, 4, 5, 6, 7])

    def test_fatal_contact_selects_both_native_deaths_and_latches_blood(self):
        for facing, sequence in ((0, 51), (1, 54)):
            self.state.facing = facing
            self.spikes.foreground[0, 24] = 2
            self.assertEqual(self.hit(), (sequence, 294))
            self.assertEqual(self.tile().foreground, 240)
            self.assertIsNone(self.hit())

    def test_idle_cautious_step_and_dead_poses_are_exempt(self):
        for pose in (15, 121, 125, 132, 185, 242, 243, 266, 271):
            self.state.action = pose
            self.spikes.foreground[0, 24] = 1
            self.assertIsNone(self.hit(), pose)
        self.state.action = 1
        self.assertIsNone(self.hit(alive=False))
        self.state.select(85)
        self.assertIsNone(self.hit())

    def test_horizontal_and_vertical_hit_thresholds_are_not_the_sprite_box(self):
        self.spikes.foreground[0, 24] = 1
        self.bounds = 299, 280, 329, 346
        self.assertIsNone(self.hit())
        self.state.facing = 1
        self.assertEqual(self.hit(), (54, 294))
        self.spikes.foreground[0, 24] = 1
        self.bounds = 293, 280, 323, 346
        self.assertIsNone(self.hit(sword=True))
        self.bounds = 292, 280, 322, 346
        self.assertEqual(self.hit(sword=True), (54, 294))

    def test_bloodied_spikes_stay_extended_and_do_not_retrigger(self):
        self.approach()
        self.hit()
        for _ in range(30):
            self.assertEqual(self.spikes.advance(self.terrain, 0), ())
            self.approach()
            self.assertEqual(self.tile().foreground, 240)

    def test_leaving_the_room_clears_a_live_trap_but_preserves_blood(self):
        self.approach()
        self.spikes.advance(self.terrain, 1)
        self.assertEqual(self.tile().foreground, 0)
        self.assertFalse(self.spikes.active)
        self.approach()
        self.hit()
        self.spikes.advance(self.terrain, 1)
        self.assertEqual(self.tile().foreground, 240)
        self.assertFalse(self.spikes.active)
        self.assertEqual(len(list(self.spikes.drawing_commands(self.terrain, 0))), 1)

    def test_rendering_has_separate_back_and_front_pieces_with_native_offsets(self):
        self.spikes.foreground[0, 24] = 2
        self.assertEqual(list(self.spikes.drawing_commands(self.terrain, 0)),
                         [['back', 3573, 279, 332, 16]])
        self.assertEqual(list(self.spikes.drawing_commands(self.terrain, 0, True)),
                         [['front', 3579, 267, 344, 16]])
        self.assertEqual(list(self.spikes.drawing_commands(self.terrain, 1)), [])

    def test_incoming_left_neighbor_uses_the_native_mob_rebase(self):
        struct.pack_into('>H', self.level, 0x2080, 2)
        self.spikes.foreground[1, 29] = 143
        self.assertEqual(list(self.spikes.drawing_commands(self.terrain, 0)),
                         [['back', 3572, 24, 332, 16]])

    def test_draw_uses_inclusive_bottom_and_keeps_the_other_pass_untouched(self):
        self.spikes.foreground[0, 24] = 2
        sprite = Image.new('RGBA', (4, 3), 'red')
        frame = Image.new('RGBA', (510, 365), 'black')
        expected = frame.copy()
        expected.paste(sprite, (267, 342), sprite)
        with patch('pop2.caverns.cavern_assets', return_value=(None, {}, {}, {})), \
                patch('pop2.caverns.cavern_command_sprite', return_value=sprite) as decode:
            draw_cavern_spikes(frame, 0, self.caverns, self.terrain, front=True)
        decode.assert_called_once_with(['front', 3579, 267, 344, 16], {}, {}, {})
        self.assertIsNone(ImageChops.difference(frame, expected).convert('RGB').getbbox())

    def test_session_state_is_not_shared(self):
        self.approach()
        self.assertEqual(CavernState().spikes, WallSpikes())

    def test_physical_wall_is_not_the_extended_cautious_step_barrier(self):
        # CODE:6 sets c944 only for DoStepFwd's distance query.
        self.assertEqual(self.terrain.wall_correction(
            0, 320, 300, (290, 280, 320, 346), (310, 280, 340, 346), 0, 2), 300)
        self.assertEqual(self.terrain.wall_correction(
            0, 300, 270, (260, 280, 290, 346), (290, 280, 320, 346), 0, 2), 286)

    def test_run_start_distance_does_not_enable_the_cautious_spike_margin(self):
        self.state.action, self.state.target_x = 15, 319
        bounds = 315, 268, 332, 346
        normal = self.terrain.step_boundary(0, 2, self.state, self.record, bounds)
        cautious = self.terrain.step_boundary(0, 2, self.state, self.record, bounds, cautious=True)
        self.assertEqual((normal.clearance, cautious.clearance), (39, 17))
        self.assertGreaterEqual(normal.clearance, 27)
        self.assertLess(cautious.clearance, 27)


@unittest.skipUnless((ASSET_DIR / 'caverns_entry.json').is_file(), 'Imported game resources required')
class ImportedWallSpikeTests(unittest.TestCase):
    def test_level_three_has_the_three_original_wall_spikes(self):
        from pop2.game_session import GameResources

        terrain = LevelMap(GameResources.load().level(3).data)
        self.assertEqual([(room + 1, cell) for room in range(32) for cell in range(30)
                          if terrain.tile(room, cell % 10, cell // 10).kind == 2],
                         [(11, 22), (14, 20), (21, 24)])

    def test_live_run_into_wall_triggers_impalement_and_reaches_the_retry_prompt(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(3)
        scene.peaceful = True
        scene.jump_to_room(20, row=2, x=360, facing=0)
        scene.in_animation_tick = True
        scene.horizontal_key(None, -1, True)
        with patch.object(scene, 'render'):
            for _ in range(55):
                RooftopSceneTests.tick(self)
                if scene.terrain_motion.dead:
                    break
            self.assertTrue(scene.terrain_motion.dead)
            self.assertEqual(scene.sequence_state.source_sequence_id, 51)
            self.assertEqual(scene.game.caverns.spikes.foreground[20, 24], 240)
            self.assertEqual(scene.combat.player.life, 0)
            self.assertEqual(scene.death.method, 4)
            RooftopSceneTests.tick(self, 20)
            self.assertEqual(scene.action, 242)
            self.assertTrue(scene.death.prompt_visible)
        scene.render()
        self.assertIsNotNone(scene.native_viewport.getbbox())

    def test_all_three_traps_kill_a_run_but_allow_the_cautious_approach(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        for room, column in ((10, 2), (13, 0), (20, 4)):
            for cautious in (False, True):
                with self.subTest(room=room + 1, cautious=cautious), patch.object(scene, 'render'):
                    scene.load_level(3)
                    scene.peaceful = True
                    scene.jump_to_room(room, row=2, x=column * 51 + 156, facing=0)
                    scene.in_animation_tick = True
                    scene.shift_held = cautious
                    scene.horizontal_key(None, -1, True)
                    for _ in range(60):
                        RooftopSceneTests.tick(self)
                        if scene.terrain_motion.dead:
                            break
                    self.assertEqual(scene.combat.player.alive, cautious)
                    self.assertEqual(scene.game.caverns.spikes.foreground[room, 20 + column],
                                     143 if cautious else 240)

    def test_fresh_forward_press_already_near_each_trap_runs_into_it_without_a_wall_bump(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        for room, column in ((10, 2), (13, 0), (20, 4)):
            with self.subTest(room=room + 1), patch.object(scene, 'render'):
                scene.load_level(3)
                scene.peaceful = True
                # User's Macintosh recording: idle X=115 relative to the trap,
                # then a fresh Left press with no Shift, rather than a long run.
                scene.jump_to_room(room, row=2, x=column * 51 + 115, facing=0)
                scene.in_animation_tick = True
                scene.horizontal_key(None, -1, True)
                selected = []
                for _ in range(12):
                    RooftopSceneTests.tick(self)
                    selected.append(scene.sequence_state.source_sequence_id)
                    if scene.terrain_motion.dead:
                        break
                self.assertTrue(scene.terrain_motion.dead, selected)
                self.assertEqual(selected[0], 1)
                self.assertFalse(set(selected) & (set(range(29, 45)) | {45, 46, 47}), selected)
                self.assertEqual(scene.action, 186)
                self.assertEqual(scene.player_x, column * 51 + 90)

    def test_shift_still_selects_the_cautious_step_when_starting_near_the_spikes(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(3)
        scene.peaceful = True
        scene.jump_to_room(13, row=2, x=115, facing=0)
        scene.in_animation_tick = True
        scene.shift_held = True
        scene.horizontal_key(None, -1, True)
        with patch.object(scene, 'render'):
            RooftopSceneTests.tick(self)
            self.assertEqual(scene.sequence_state.source_sequence_id, 32)
            RooftopSceneTests.tick(self, 30)
        self.assertTrue(scene.combat.player.alive)

    def test_right_facing_death_turns_to_the_native_pose_and_restart_resets_the_trap(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(3)
        scene.peaceful = True
        scene.jump_to_room(20, row=2, x=300, facing=1)
        scene.physics.select(scene.sequence_runtime, 1)
        scene.action, scene.player_x = scene.sequence_state.action, scene.sequence_state.target_x
        environment_for(scene).check_spikes()
        self.assertEqual((scene.action, scene.sequence_state.source_sequence_id,
                          scene.sequence_state.facing, scene.player_x), (188, 54, 0, 286))
        with patch.object(scene, 'render'):
            RooftopSceneTests.tick(self, 5)
            self.assertEqual(scene.action, 243)
            scene.restart_opening(play_sound=False)
        self.assertEqual(scene.game.caverns.spikes, WallSpikes())

    def test_pause_freezes_the_spike_controller(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(3)
        scene.jump_to_room(20, row=2, x=390, facing=0)
        spikes = scene.game.caverns.spikes
        spikes.trigger(scene.level_map.tile(20, 4, 2))
        scene.paused = True
        RooftopSceneTests.tick(self, 5)
        self.assertEqual(spikes.foreground[20, 24], 1)
        scene.paused = False
        with patch.object(scene, 'render'):
            RooftopSceneTests.tick(self)
        self.assertEqual(spikes.foreground[20, 24], 2)
