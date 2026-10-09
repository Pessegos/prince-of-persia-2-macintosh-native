import random
import struct
import unittest

from PIL import Image

from pop2.animation_data import parse_frame_records, sequence_words
from pop2.combat import CombatEncounter, Fighter, GuardSpawn, select_sequence
from pop2.combat_art import GuardArtwork, HealthArtwork
from pop2.render_opening import decode_ctbl, load_resource_file
from pop2.scene_prototype import sword_palette_for_level
from pop2.sequence_runtime import SequenceRuntime, SequenceState
from pop2.terrain import LevelMap, RooftopPhysics, TerrainMotion, floor_contact_x, floor_y
from pop2.opponent_generation import WALL_TILES, character_column


class RooftopPursuitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prince = load_resource_file("Prince.rsrc")
        cls.kid = load_resource_file("Kid.rsrc")
        cls.level = cls.prince["LEVL"][2000]["data"]
        cls.sequences = {key: sequence_words(value["data"])
                         for key, value in cls.prince["SEQS"].items()}
        cls.art = GuardArtwork(load_resource_file("Guard.rsrc"), cls.prince["SHAP"],
                               1001, sword_palette_for_level(cls.prince, 5))

    def encounter(self, room=2, player_x=50, facing=0, running=True):
        player = SequenceRuntime(self.sequences, SequenceState(
            3 if running else 2, action=7 if running else 15, facing=facing,
            current_x=player_x, target_x=player_x, actor_type=0, level_kind=5))
        encounter = CombatEncounter(player, self.sequences, GuardSpawn.from_level(self.level, 3),
                                    509, level=self.level, rng=random.Random(1))
        encounter.terrain = LevelMap(self.level)
        encounter.guard_art = self.art
        encounter.room_encounters[3][0].clear()
        encounter.enter_room(room, 1)
        encounter.guards.clear()
        return encounter

    def runner(self, encounter, room, x, facing=0, flags=1):
        encounter._load_room(room)
        runtime = SequenceRuntime(self.sequences, SequenceState(
            84, current_x=x, target_x=x, facing=facing, actor_type=2, level_kind=5))
        runtime.next_frame()
        guard = Fighter(runtime, 3, 3, room, 1, generation_flags=flags,
                        selected_sequence=84)
        encounter.room_encounters[room][0].append(guard)
        return guard

    def tick(self, encounter):
        encounter.update_guard_alerts()
        encounter.advance_guard()

    def test_guard_run_jump_uses_all_original_poses_without_a_fall(self):
        for room, x in ((2, 450), (0, 450)):
            with self.subTest(room=room):
                encounter = self.encounter(room)
                guard = self.runner(encounter, room, x)
                poses = []
                for _ in range(25):
                    self.tick(encounter)
                    if guard.state.sequence_id == 100:
                        poses.append(guard.state.action)
                    self.assertFalse(guard.terrain_motion.falling)
                    self.assertTrue(guard.alive)
                self.assertEqual(poses, list(range(202, 213)))
                self.assertLess(guard.state.target_x, 180)

    def test_jump_takeoff_uses_anchor_not_pose_foot_for_13_pixel_scan(self):
        encounter = self.encounter(0)
        guard = self.runner(encounter, 0, 405)
        guard.state.sequence_id, guard.state.action = 208, 192
        encounter._choose_guard_jump(guard)
        self.assertEqual((guard.state.sequence_id, guard.state.target_x), (100, 404))

    def test_guard_jump_also_crosses_gap_to_the_right(self):
        encounter = self.encounter(2, player_x=480, facing=1)
        guard = self.runner(encounter, 2, 50, facing=1)
        poses = []
        for _ in range(40):
            self.tick(encounter)
            if guard.state.sequence_id == 100:
                poses.append(guard.state.action)
            self.assertFalse(guard.terrain_motion.falling)
        self.assertEqual(poses, list(range(202, 213)))
        # The native too-close front-cell branch can continue into the next
        # room after landing. Compare world position, not the rebased anchor.
        world_x = guard.state.target_x + (510 if guard.room == 1 else 0)
        self.assertGreater(world_x, 325)

    def test_generation_flags_are_preserved_for_initial_guards(self):
        level = bytearray(self.level)
        struct.pack_into(">h", level, 0x20e6 + 4 * 192 + 2 + 0x14, 2)
        self.assertEqual(GuardSpawn.from_level(level, 3).generation_flags, 2)

    def test_close_player_pressure_does_not_make_guards_step_back_into_rooftop_gaps(self):
        for facing, x in ((0, 150), (1, 357)):
            with self.subTest(facing=facing):
                encounter = self.encounter(0, player_x=x, running=False)
                guard = self.runner(encounter, 0, x, facing=facing, flags=0)
                guard.sword_drawn = encounter.player.sword_drawn = True
                guard.alert_mode = 3
                guard.state.animation_state = 0
                select_sequence(guard, 227)
                guard.runtime.next_frame()
                advances = 0
                for _ in range(240):
                    # Keep the threat close and in front, without attacks,
                    # knockback or passing through the guard to force a turn.
                    player = encounter.player
                    player.room, player.row = guard.room, guard.row
                    player.state.target_x = guard.state.target_x + (20 if facing else -20)
                    player.state.facing = 1 - facing
                    encounter.choose_guard_action(guard)
                    advances += guard.state.sequence_id == 86
                    old_x = guard.state.target_x
                    old_bounds = self.art.bounds(guard.state, floor_y(guard.row))
                    guard.runtime.next_frame()
                    encounter._advance_guard_terrain(guard, old_x, old_bounds)
                    self.assertFalse(guard.terrain_motion.falling)
                    self.assertFalse(guard.terrain_motion.dead)
                    self.assertTrue(guard.alive)
                self.assertGreater(advances, 10)

    def test_ineligible_guards_do_not_select_a_running_jump(self):
        encounter = self.encounter(2)
        guard = self.runner(encounter, 2, 405, flags=0)
        guard.state.sequence_id, guard.state.action = 208, 192
        encounter.choose_guard_action(guard)
        self.assertNotEqual(guard.state.sequence_id, 100)

    def test_incoming_pursuer_blocks_duplicate_generation_across_room_ownership(self):
        encounter = self.encounter(0, player_x=50, running=False)
        guard = self.runner(encounter, 2, 20)
        guard.pursuing = True
        point = encounter.generation_points[0]
        for frame in range(1, 31):
            encounter.world_frame = frame
            encounter.generate_opponents()
        self.assertEqual(encounter.guards, [])
        self.assertEqual((point.remaining, point.countdown), (2, 8))
        self.assertEqual((guard.room, guard.state.target_x), (2, 20))
        guard.life = 0
        for frame in range(31, 47):
            encounter.world_frame = frame
            encounter.generate_opponents()
        self.assertEqual(len(encounter.guards), 1)
        self.assertEqual(point.remaining, 1)
        successor = encounter.guards[0]
        poses = []
        for _ in range(85):
            self.tick(encounter)
            if successor.state.sequence_id == 100:
                poses.append(successor.state.action)
        self.assertEqual(poses, list(range(202, 213)))
        self.assertTrue(successor.alive)
        self.assertLess(successor.state.target_x, 180)

    def test_returning_to_neighbor_counts_a_reinforcement_before_it_starts_pursuing(self):
        encounter = self.encounter(0, player_x=50, running=False)
        for frame in range(1, 17):
            encounter.world_frame = frame
            encounter.generate_opponents()
        guard = encounter.guards[0]
        self.assertFalse(guard.pursuing)
        self.assertIsNotNone(guard.entry_x)
        encounter.enter_room(2, 1)
        point = encounter.generation_points[0]
        for frame in range(17, 47):
            encounter.world_frame = frame
            encounter.generate_opponents()
        self.assertEqual(encounter.guards, [])
        self.assertEqual((point.remaining, point.countdown), (3, 8))
        self.assertEqual(sum(g.alive for g in encounter.active_guards()), 1)
        guard.life = 0
        for frame in range(47, 64):
            encounter.world_frame = frame
            encounter.generate_opponents()
        self.assertEqual(len(encounter.guards), 1)
        self.assertEqual(point.remaining, 2)

    def test_fatal_hit_at_roof_edge_uses_tumble_and_keeps_falling_after_death(self):
        encounter = self.encounter(0, player_x=50, running=False)
        guard = self.runner(encounter, 0, 145)
        guard.life = 1
        guard.state.action = 170
        encounter.player.state.facing = 1
        event = encounter._hurt("guard", guard, encounter.player)
        self.assertEqual((event.kind, guard.state.sequence_id, guard.state.action),
                         ("death", 185, 213))
        self.assertEqual(guard.state.sound_events, [30])
        self.assertFalse(guard.targetable)
        poses = [guard.state.action]
        heights = [floor_y(guard.row) + guard.state.current_y]
        for _ in range(22):
            self.tick(encounter)
            poses.append(guard.state.action)
            heights.append(floor_y(guard.row) + guard.state.current_y)
            self.assertFalse(guard.alive)
        self.assertEqual(poses[:9], [213, 214, 215, 216, 217, 218, 217, 218, 217])
        self.assertGreater(heights[-1], heights[0] + 300)
        self.assertFalse(any(pose == 185 and height < 365
                             for pose, height in zip(poses, heights)))

    def test_fatal_hit_on_clear_floor_keeps_flat_ground_death(self):
        encounter = self.encounter(0, player_x=50, running=False)
        guard = self.runner(encounter, 0, 90)
        guard.life = 1
        guard.state.action = 170
        encounter._hurt("guard", guard, encounter.player)
        self.assertEqual((guard.state.sequence_id, guard.state.action), (85, 179))
        self.assertFalse(guard.terrain_motion and guard.terrain_motion.falling)

    def test_right_facing_flat_death_moves_back_from_the_sloping_roof(self):
        encounter = self.encounter(2, player_x=250, running=False)
        guard = self.runner(encounter, 2, 172, facing=1)
        guard.life = 1
        guard.state.action = 170
        encounter._hurt("guard", guard, encounter.player)
        self.assertEqual((guard.state.sequence_id, guard.state.action, guard.state.target_x),
                         (85, 179, 129))
        for _ in range(15):
            self.tick(encounter)
        self.assertEqual((guard.state.action, guard.state.target_x), (185, 131))
        self.assertFalse(guard.terrain_motion.falling)
        self.assertEqual(guard.row, 1)

    def test_flat_death_checks_the_first_death_pose_not_the_old_fighting_foot(self):
        encounter = self.encounter(2, player_x=250, running=False)
        guard = self.runner(encounter, 2, 190, facing=1)
        guard.life = 1
        guard.state.action = 170
        encounter._hurt("guard", guard, encounter.player)
        # Native CheckStab probe: scene X 190 -> 127, including the hit's -10.
        self.assertEqual(guard.state.target_x, 127)
        for _ in range(15):
            self.tick(encounter)
        self.assertEqual((guard.state.action, guard.row), (185, 1))
        self.assertFalse(guard.terrain_motion.falling)

    def test_guard_transfers_rooms_once_preserving_identity_and_health(self):
        encounter = self.encounter(2, player_x=300)
        encounter._load_room(1)
        encounter.room_encounters[1][0].clear()
        guard = self.runner(encounter, 1, 15)
        guard.life, guard.palette_variant = 2, 3
        for _ in range(30):
            self.tick(encounter)
            if guard.room == 2:
                break
        self.assertEqual(guard.room, 2)
        self.assertEqual((guard.life, guard.palette_variant), (2, 3))
        self.assertIn(guard, encounter.guards)
        self.assertNotIn(guard, encounter.room_encounters[1][0])
        self.assertEqual(sum(g is guard for guards, _ in encounter.room_encounters.values()
                             for g in guards), 1)
        encounter.enter_room(1, 1)
        encounter.enter_room(2, 1)
        self.assertIn(guard, encounter.guards)

    def test_side_room_projection_is_render_only_and_does_not_teleport_guard(self):
        encounter = self.encounter(2, player_x=300)
        encounter._load_room(1)
        encounter.room_encounters[1][0].clear()
        guard = self.runner(encounter, 1, 5)
        view = next(g for g in encounter.visible_guards() if g.state.sequence_id == 84)
        self.assertEqual((view.room, view.state.target_x), (2, 515))
        self.assertEqual((guard.room, guard.state.target_x), (1, 5))
        image = Image.new("RGBA", (510, 365))
        self.art.draw(image, view.state, floor_y(view.row))
        self.assertIsNotNone(image.getbbox())

    def test_new_reinforcement_keeps_its_spawn_room_until_entry(self):
        encounter = self.encounter(3, player_x=350, running=False)
        guard = self.runner(encounter, 3, -102, facing=1)
        guard.entry_x = -102
        for _ in range(6):
            self.tick(encounter)
            self.assertEqual(guard.room, 3)
        self.assertIsNotNone(guard.entry_x)
        for _ in range(18):
            self.tick(encounter)
        self.assertEqual(guard.room, 3)
        self.assertIsNone(guard.entry_x)
        self.assertEqual(len(encounter.guards), 1)

    def test_player_leaving_floor_still_brakes_incoming_guard(self):
        encounter = self.encounter(2, player_x=50)
        guard = self.runner(encounter, 2, 400)
        guard.state.sequence_id, guard.state.action = 208, 195
        encounter.player.row = 2
        self.tick(encounter)
        self.assertEqual(guard.state.sequence_id, 101)

    def test_pursuer_keeps_simulating_when_player_is_two_screens_ahead(self):
        encounter = self.encounter(3, player_x=100)
        guard = self.runner(encounter, 3, 400)
        self.tick(encounter)
        self.assertTrue(guard.pursuing)
        encounter.enter_room(1, 1)
        encounter.enter_room(2, 1)
        encounter.player.state.target_x = 200
        self.assertIn(guard, encounter.active_guards())
        for _ in range(140):
            self.tick(encounter)
            if guard.room == 2:
                break
        self.assertEqual(guard.room, 2)
        self.assertTrue(guard.alive)

    def test_player_with_one_life_blinks_only_first_bottle_and_stops_when_healed(self):
        encounter = self.encounter()
        art = HealthArtwork(self.kid, decode_ctbl(self.kid["CTBL"][25001]["data"]), 25001)
        def draw(life, phase):
            encounter.player.life, encounter.world_frame = life, phase
            image = Image.new("RGBA", (512, 384), (0, 0, 0, 255))
            art.draw(image, encounter)
            return image
        even, odd = draw(1, 0), draw(1, 1)
        self.assertNotEqual(even.crop((3, 368, 15, 384)).tobytes(),
                            odd.crop((3, 368, 15, 384)).tobytes())
        self.assertEqual(even.crop((15, 368, 512, 384)).tobytes(),
                         odd.crop((15, 368, 512, 384)).tobytes())
        for life in (0, 2, 3):
            self.assertEqual(draw(life, 0).tobytes(), draw(life, 1).tobytes())

    def test_wall_contact_is_corrected_on_both_gap_sides_without_horizontal_motion(self):
        frames = parse_frame_records(self.kid["FRAM"][25001]["data"])
        terrain = LevelMap(self.level)
        for facing, x in ((0, 145), (1, 343)):
            state = SequenceState(12, action=106, target_x=x, current_x=x,
                                  facing=facing, actor_type=0)
            record = frames[state.action]
            old_column = character_column(floor_contact_x(x, facing, record))
            self.assertIn(terrain.tile(0, old_column, 2).kind, WALL_TILES)
            tile = terrain.align_wall(0, 2, state, record)
            self.assertNotIn(tile.kind, WALL_TILES)
            self.assertEqual(state.current_x, state.target_x)

    def test_falling_foot_is_corrected_before_reaching_next_floor(self):
        frames = parse_frame_records(self.kid["FRAM"][25001]["data"])
        terrain = LevelMap(self.level)
        for facing, x in ((0, 145), (1, 343)):
            with self.subTest(facing=facing):
                runtime = SequenceRuntime(self.sequences, SequenceState(
                    12, action=106, target_x=x, current_x=x, current_y=-70,
                    animation_state=4, facing=facing, actor_type=0))
                motion = TerrainMotion(0, 2, falling=True)
                RooftopPhysics(terrain, frames).advance(
                    motion, runtime, x, (x - 10, 200, x + 10, 276))
                self.assertEqual(motion.row, 2)
                self.assertTrue(motion.falling)
                column = character_column(floor_contact_x(runtime.state.target_x,
                                                         facing, frames[106]))
                self.assertNotIn(terrain.tile(0, column, 2).kind, WALL_TILES)

    def test_guard_landing_threshold_uses_npc_death_rule_and_supported_art(self):
        for velocity, alive, sequence in ((49, True, 63), (50, False, 22), (63, False, 22)):
            with self.subTest(velocity=velocity):
                encounter = self.encounter(1)
                guard = self.runner(encounter, 1, 200)
                guard.state.sequence_id, guard.state.action = 12, 106
                guard.state.animation_state = 4
                guard.state.current_y = -1
                guard.state.vertical_velocity = velocity - 6
                guard.terrain_motion = TerrainMotion(1, 1, falling=True)
                encounter._advance_guard_terrain(guard, 200)
                self.assertEqual(guard.alive, alive)
                self.assertEqual(guard.state.sequence_id, sequence)
                image = Image.new("RGBA", (510, 365))
                self.art.draw(image, guard.state, floor_y(guard.row))
                self.assertIsNotNone(image.getbbox())


if __name__ == "__main__":
    unittest.main()
