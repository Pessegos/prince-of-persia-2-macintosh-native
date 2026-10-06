import unittest
from unittest.mock import Mock, patch

from combat import select_sequence
from opponent_generation import character_column
from terrain import floor_contact_x, floor_y
import test_rooftop_pursuit as pursuit_tests
import test_animation_data as animation_tests
from render_opening import build_opening_room


class GuardDeathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pursuit_tests.RooftopPursuitTests.setUpClass()
        cls.fixture = pursuit_tests.RooftopPursuitTests()

    def encounter(self, room=9, roll=0, facing=0, x=400):
        encounter = self.fixture.encounter(room, player_x=310, facing=1 - facing, running=False)
        guard = self.fixture.runner(encounter, room, x, facing=facing)
        guard.life, guard.sword_drawn, guard.alert_mode = 1, True, 3
        select_sequence(guard, 227)
        guard.runtime.next_frame()
        encounter.rng = Mock()
        encounter.rng.randrange.return_value = roll
        return encounter, guard

    def corpse(self, encounter, x, facing=0, registered=True, pose=185):
        guard = self.fixture.runner(encounter, encounter.player.room, x, facing=facing)
        guard.life, guard.death_registered = 0, registered
        select_sequence(guard, 195 if pose == 228 else 213)
        guard.runtime.next_frame()
        guard.state.action = pose
        return guard

    def test_tumble_flag_is_packed_life_not_movement_flags(self):
        encounter, guard = self.encounter()
        point = encounter.generation_points[0]
        self.assertTrue(point.tumble_enabled)
        point.flags = 0
        self.assertTrue(encounter._opponent_tumble(guard))
        point.life_word &= ~0x80
        point.flags = 0x80
        encounter.rng.reset_mock()
        self.assertFalse(encounter._opponent_tumble(guard))
        encounter.rng.randrange.assert_not_called()

    def test_first_kill_can_tumble_in_middle_of_screen_five(self):
        for roll in range(4):
            with self.subTest(roll=roll):
                encounter, guard = self.encounter(roll=roll)
                self.assertFalse(encounter.terrain.forced_opponent_tumble(
                    guard.room, guard.row, guard.state, encounter.guard_art.frames[9]))
                encounter._hurt("guard", guard, encounter.player)
                self.assertEqual(guard.state.sequence_id, 185 if roll == 0 else 85)
                encounter.rng.randrange.assert_called_once_with(4)

    def test_dead_bank_count_increases_chance_and_does_not_count_newly_struck_actor(self):
        for count in range(4):
            for roll in range(4):
                with self.subTest(count=count, roll=roll):
                    encounter, guard = self.encounter(roll=roll)
                    for n in range(count):
                        self.corpse(encounter, 280 + n * 10)
                    encounter._hurt("guard", guard, encounter.player)
                    self.assertEqual(guard.state.sequence_id, 185 if roll <= count else 85)

    def test_unregistered_death_and_living_guards_do_not_raise_probability(self):
        encounter, guard = self.encounter(roll=1)
        self.corpse(encounter, 280, registered=False, pose=179)
        self.fixture.runner(encounter, 9, 300)
        self.assertFalse(encounter._opponent_tumble(guard))

    def test_overlapping_settled_corpse_overrides_failed_roll(self):
        for pose in (185, 228):
            for same_cell in (True, False):
                with self.subTest(pose=pose, same_cell=same_cell):
                    encounter, guard = self.encounter(roll=3)
                    self.corpse(encounter, 400 if same_cell else 280, pose=pose)
                    self.assertEqual(encounter._opponent_tumble(guard), same_cell)

    def test_same_facing_kill_rejects_random_tumble_after_consuming_roll(self):
        encounter, guard = self.encounter()
        encounter.player.state.facing = guard.state.facing
        self.assertFalse(encounter._opponent_tumble(guard))
        encounter.rng.randrange.assert_called_once_with(4)

    def test_forced_rooftop_tumble_bypasses_probability_and_facing_veto(self):
        encounter, guard = self.encounter(room=15, roll=3)
        encounter.player.state.facing = guard.state.facing
        self.assertTrue(encounter._opponent_tumble(guard))
        encounter.rng.randrange.assert_not_called()

    def test_current_and_rear_native_tile_vetoes(self):
        for rear, kinds in ((False, (3, 8, 4)), (True, (3, 8))):
            for kind in kinds:
                with self.subTest(rear=rear, kind=kind):
                    encounter, guard = self.encounter(facing=1)
                    record = encounter.guard_art.frames[guard.state.action - 149]
                    column = character_column(floor_contact_x(guard.state.target_x, 1, record))
                    tile = encounter.terrain.tile
                    def altered(room, col, row):
                        if col == column - int(rear) and row == guard.row:
                            from terrain import Tile
                            return Tile(kind)
                        return tile(room, col, row)
                    with patch.object(encounter.terrain, "tile", side_effect=altered):
                        self.assertFalse(encounter._opponent_tumble(guard))

    def test_tumble_plays_native_poses_and_gravity_without_roof_collisions(self):
        encounter, guard = self.encounter(x=300)
        encounter._hurt("guard", guard, encounter.player)
        positions, poses = [], []
        for _ in range(12):
            positions.append(floor_y(guard.row) + guard.state.current_y)
            poses.append(guard.state.action)
            self.fixture.tick(encounter)
            self.assertFalse(guard.targetable)
        self.assertEqual(positions, [226, 231, 250, 281, 328, 373, 427, 490, 553, 616, 679, 730])
        self.assertEqual(poses[:9], [213, 214, 215, 216, 217, 218, 217, 218, 217])
        self.assertEqual((guard.room, guard.state.action), (9, 185))
        x = guard.state.target_x
        for _ in range(20):
            self.fixture.tick(encounter)
        self.assertEqual((guard.state.target_x, floor_y(guard.row) + guard.state.current_y), (x, 730))

    def test_flat_corpse_variant_uses_room_slot_parity_without_randomness(self):
        for index in (0, 1):
            with self.subTest(index=index):
                encounter, guard = self.encounter(roll=3)
                if index:
                    corpse = self.corpse(encounter, 280, registered=False)
                    encounter.guards.remove(corpse)
                    encounter.guards.insert(0, corpse)
                encounter.player.state.facing = guard.state.facing
                encounter._hurt("guard", guard, encounter.player)
                encounter.rng.reset_mock()
                for _ in range(12):
                    self.fixture.tick(encounter)
                self.assertEqual(guard.state.action, 228 if index else 185)
                self.assertTrue(guard.death_registered)
                self.assertFalse(guard.terrain_motion.falling)
                encounter.rng.randrange.assert_not_called()

    def test_front_roof_tumble_has_no_normal_foreground_mask(self):
        encounter, guard = self.encounter()
        room = build_opening_room(room_id=9)
        encounter._hurt("guard", guard, encounter.player)
        bounds = encounter.guard_art.bounds(guard.state, floor_y(guard.row))
        record = encounter.guard_art.frames[guard.state.action - 149]
        self.assertIsNone(room.actor_mask(guard.row, bounds[3], guard.state, bounds, record).getbbox())
        guard.state.animation_state = 1
        self.assertIsNotNone(room.actor_mask(guard.row, bounds[3], guard.state, bounds, record).getbbox())


class RunStopDistanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        animation_tests.AnimationDataTests.setUpClass()
        cls.fixture = animation_tests.AnimationDataTests()

    def test_release_at_either_supporting_foot_uses_only_native_stop_displacement(self):
        for facing in (0, 1):
            for pose in (7, 11):
                with self.subTest(facing=facing, pose=pose):
                    scene = self.fixture.sword_scene()
                    scene.sequence_state.facing = facing
                    scene.start_sequence(201)
                    while scene.sequence_state.action != pose:
                        scene.sequence_runtime.next_frame()
                    scene.player_x = scene.sequence_state.target_x = scene.sequence_state.current_x = 200
                    scene.run_active = True
                    scene.run_direction = 1 if facing else -1
                    scene.horizontal_input = scene.run_direction
                    scene.held_directions = [scene.run_direction]
                    scene.horizontal_key(None, scene.run_direction, False)
                    poses = []
                    for _ in range(9):
                        scene.advance_animation()
                        poses.append(scene.action)
                    self.assertEqual(poses, [53, 54, 55, 56, 49, 50, 51, 52, 15])
                    self.assertEqual(scene.player_x, 200 + (33 if facing else -33))
                    stopped_x = scene.player_x
                    for _ in range(10):
                        scene.advance_animation()
                    self.assertEqual(scene.player_x, stopped_x)
                    self.assertFalse(scene.run_active)
                    self.assertIsNone(scene.pending_action)


if __name__ == "__main__":
    unittest.main()
