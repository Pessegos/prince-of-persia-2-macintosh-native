import copy
import random
import unittest
from unittest.mock import patch

from PIL import Image

from combat import CombatEncounter, GuardSpawn, opponent_distance, select_sequence
from combat_art import GuardArtwork
from enemy_profiles import ENEMY_DATA, HIT_PAUSE
from opponent_generation import OpponentGenerationPoint, character_column, tile_kind
from render_opening import load_resource_file
from scene_prototype import sword_palette_for_level
from sequence_runtime import SequenceState
import test_animation_data as animation_tests
import test_combat as combat_tests


class OpponentGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        combat_tests.GuardCombatTests.setUpClass()
        cls.sequences = combat_tests.GuardCombatTests.sequences
        cls.level = combat_tests.GuardCombatTests.prince["LEVL"][2000]["data"]
        cls.spawn = GuardSpawn.from_level(cls.level, 3)

    def encounter(self, first_alive=False):
        fixture = combat_tests.GuardCombatTests()
        fixture.sequences, fixture.spawn = self.sequences, self.spawn
        encounter = fixture.encounter()
        encounter.level = self.level
        encounter.generation_points = OpponentGenerationPoint.from_level(self.level, 3)
        if not first_alive:
            encounter.guard.life = 0
            select_sequence(encounter.guard, 85)
            for _ in range(10):
                encounter.guard.runtime.next_frame()
        return encounter

    def second_guard(self, encounter, x=140):
        guard = copy.deepcopy(encounter.guards[0])
        guard.life = guard.max_life = 1
        guard.state.current_x = guard.state.target_x = x
        guard.sword_drawn = True
        guard.recovering = guard.contact_consumed = False
        guard.alert_mode = 3
        select_sequence(guard, 227)
        guard.runtime.next_frame()
        encounter.guards.append(guard)
        return guard

    def test_first_room_generation_point_is_native_not_initial_generator(self):
        point, = OpponentGenerationPoint.from_level(self.level, 3)
        self.assertEqual(point, OpponentGenerationPoint(3, 0, 0, 1, 0, 5, 5, 1, 1, 1, -1, -127))
        self.assertEqual((point.x, point.facing, point.life), (-102, 1, 1))
        self.assertEqual(ENEMY_DATA["generation_native_x"],
                         [105, 156, 207, 258, 309, 360, 615, 666, 717, 768])

    def test_column_boundaries_use_original_signed_division(self):
        self.assertEqual([character_column(x) for x in (-102, 0, 149, 175, 176, 260, 408)],
                         [-3, -1, 2, 2, 3, 4, 7])

    def test_floor_lookup_follows_original_left_room_link(self):
        self.assertEqual(tile_kind(self.level, 3, -3, 1), 1)
        self.assertEqual(tile_kind(self.level, 3, 7, 1), 1)
        self.assertEqual(tile_kind(self.level, 3, 8, 1), 0)

    def test_initial_living_guard_between_point_and_prince_blocks_countdown(self):
        c = self.encounter(first_alive=True)
        point = c.generation_points[0]
        for frame in range(120):
            self.assertFalse(point.advance(c.player, c.guards, frame, self.level))
        self.assertEqual((point.countdown, point.remaining), (5, 1))

    def test_dead_first_guard_does_not_block_generation(self):
        c = self.encounter()
        point = c.generation_points[0]
        self.assertFalse(point.eligible(c.player, c.guards, 0, self.level))
        self.assertTrue(point.eligible(c.player, c.guards, 1, self.level))

    def test_living_guard_on_other_side_is_not_an_invented_death_gate(self):
        c = self.encounter(first_alive=True)
        c.guard.state.target_x = c.guard.state.current_x = 350
        self.assertTrue(c.generation_points[0].eligible(c.player, c.guards, 1, self.level))

    def test_native_player_distance_gate_is_more_than_two_columns(self):
        c = self.encounter()
        for x, eligible in ((175, False), (176, True)):
            c.player.state.target_x = x
            self.assertEqual(c.generation_points[0].eligible(c.player, c.guards, 1, self.level),
                             eligible)

    def test_dead_wrong_room_wrong_row_special_actor_and_exhausted_point_rejected(self):
        for field, value in (("life", 0), ("room", 2), ("row", 0)):
            c = self.encounter()
            setattr(c.player, field, value)
            self.assertFalse(c.generation_points[0].eligible(c.player, c.guards, 1, self.level))
        c = self.encounter()
        c.player.state.actor_type = 1
        self.assertFalse(c.generation_points[0].eligible(c.player, c.guards, 1, self.level))
        c.player.state.actor_type = 0
        c.generation_points[0].remaining = 0
        self.assertFalse(c.generation_points[0].eligible(c.player, c.guards, 1, self.level))

    def test_native_five_record_limit_includes_corpses(self):
        c = self.encounter()
        c.guards.extend(copy.deepcopy(c.guard) for _ in range(4))
        self.assertFalse(c.generation_points[0].eligible(c.player, c.guards, 1, self.level))

    def test_spawn_counts_only_eligible_world_frames_and_preserves_corpse(self):
        c = self.encounter()
        corpse = c.guard
        corpse_state = (corpse.state.action, corpse.state.target_x, corpse.state.facing)
        for frame in range(8):
            c.step(frame / 10, 0.1)
            self.assertEqual(len(c.guards), 1, frame)
        c.step(0.8, 0.1)
        incoming = c.guards[1]
        self.assertEqual((incoming.state.action, incoming.state.target_x), (187, -102))
        self.assertEqual((incoming.skill, incoming.life, incoming.max_life, incoming.state.facing),
                         (0, 1, 1, 1))
        self.assertIs(c.guard, incoming)
        self.assertIs(c.guards[0], corpse)
        self.assertEqual((corpse.state.action, corpse.state.target_x, corpse.state.facing), corpse_state)
        self.assertFalse(incoming.contact_consumed)
        self.assertEqual(c.generation_points[0].remaining, 0)
        for frame in range(9, 150):
            c.step(frame / 10, 0.1)
        self.assertEqual(len(c.guards), 2)

    def test_repeated_key_callbacks_do_not_accelerate_generation_clock(self):
        c = self.encounter()
        c.step(0, 0.1)
        for _ in range(100):
            c.step(0, 0.1)
        self.assertEqual(c.world_frame, 1)
        self.assertEqual(c.generation_points[0].countdown, 5)
        c.step(0.1, 0.1)
        self.assertEqual(c.generation_points[0].countdown, 4)

    def test_native_entry_run_brake_and_draw_without_teleport(self):
        c = self.encounter()
        c.world_frame = 1
        c.generation_points[0].countdown = 0
        c.generate_opponents()
        second = c.guards[1]
        poses, positions = [], []
        for _ in range(70):
            poses.append(second.state.action)
            positions.append(second.state.target_x)
            c.update_guard_alerts()
            c.advance_guard()
            if second.sword_drawn:
                break
        self.assertEqual(poses[:6], [186, 187, 188, 189, 190, 191])
        self.assertEqual(positions[:6], [-102, -102, -102, -102, -74, -74])
        self.assertIn(199, poses)
        self.assertEqual(poses[-3:], [200, 201, 166])
        self.assertEqual(second.selected_sequence, 90)
        self.assertIsNone(second.entry_x)
        self.assertTrue(all(b >= a for a, b in zip(positions, positions[1:])))
        self.assertEqual(c.player.life, 3)

    def test_unarmed_brake_only_odd_running_poses_and_native_distance_gate(self):
        for pose in (186, 187, 188, 189, 190, 191, 192, 193, 194, 196, 198):
            c = self.encounter()
            second = self.second_guard(c, x=200)
            second.sword_drawn = False
            second.state.action = pose
            c._choose_unarmed_guard_action(second)
            self.assertEqual(second.state.sequence_id, 227, pose)
        for distance, brakes in ((178, True), (179, False)):
            c = self.encounter()
            second = self.second_guard(c, x=260 - distance)
            second.sword_drawn = False
            second.state.action = 195
            c._choose_unarmed_guard_action(second)
            self.assertEqual(second.state.sequence_id == 101, brakes, distance)

    def test_incoming_guard_brakes_when_player_leaves_its_floor_or_dies(self):
        for field, value in (("row", 2), ("room", 1), ("life", 0)):
            with self.subTest(field=field):
                c = self.encounter()
                c.world_frame = 1
                c.generation_points[0].countdown = 0
                c.generate_opponents()
                guard = c.guards[1]
                setattr(c.player, field, value)
                poses, positions = [], []
                for _ in range(100):
                    c.update_guard_alerts()
                    c.advance_guard()
                    poses.append(guard.state.action)
                    positions.append(guard.state.target_x)
                self.assertIn(200, poses)
                self.assertIn(201, poses)
                self.assertEqual(poses[-10:], [166] * 10)
                self.assertEqual(len(set(positions[-10:])), 1)
                self.assertEqual(guard.alert_mode, 0)
                self.assertFalse(guard.sword_drawn)

    def test_nearest_each_side_engages_others_wait_and_dead_do_not_obstruct(self):
        c = self.encounter(first_alive=True)
        left = self.second_guard(c, x=100)
        right = self.second_guard(c, x=320)
        c.update_guard_alerts()
        self.assertEqual([g.alert_mode for g in c.guards], [3, 2, 3])
        c.guards[0].life = 0
        c.update_guard_alerts()
        self.assertEqual([g.alert_mode for g in c.guards], [0, 3, 3])
        self.assertIsNot(c.guard, left)
        c.refresh_target()
        self.assertIs(c.guard, right)

    def test_same_facing_run_spacing_exception_still_checks_passed_player(self):
        for raw_distance, brakes in ((50, True), (51, False)):
            c = self.encounter()
            second = self.second_guard(c, x=260 - raw_distance)
            second.sword_drawn = False
            second.state.action = 195
            c.player.state.action, c.player.state.facing = 8, 1
            c._choose_unarmed_guard_action(second)
            self.assertEqual(second.selected_sequence == 101, brakes, raw_distance)
        c = self.encounter()
        second = self.second_guard(c, x=350)
        second.sword_drawn = False
        second.state.action = 195
        c.player.state.action, c.player.state.facing = 8, 1
        c._choose_unarmed_guard_action(second)
        self.assertEqual(second.selected_sequence, 101)

    def test_original_opening_poses_disable_guard_engagement(self):
        for action in range(217, 226):
            c = self.encounter(first_alive=True)
            c.player.state.action = action
            c.update_guard_alerts()
            self.assertEqual(c.guard.alert_mode, 0, action)

    def test_waiting_guard_never_uses_engaged_attack_ai(self):
        c = self.encounter(first_alive=True)
        second = self.second_guard(c, x=140)
        c.update_guard_alerts()
        self.assertEqual(second.alert_mode, 2)
        with patch.object(c, "decide_guard_intent", side_effect=AssertionError("waiting attack")):
            c.choose_guard_action(second)
        self.assertEqual(second.selected_sequence, 57)

    def test_living_opposing_target_retained_same_facing_target_reselected(self):
        c = self.encounter(first_alive=True)
        original = c.guard
        closer = self.second_guard(c, x=240)
        c.refresh_target()
        self.assertIs(c.guard, original)
        c.player.state.facing = 1
        c.refresh_target()
        self.assertIs(c.guard, closer)

    def test_waiting_guard_far_advance_uses_original_step_gate(self):
        for pose, expected in ((171, 86), (152, 227)):
            c = self.encounter(first_alive=True)
            c.guard.state.target_x = c.guard.state.current_x = 200
            second = self.second_guard(c, x=50)
            second.state.action = pose
            second.alert_mode = 2
            c.choose_guard_action(second)
            self.assertEqual(second.selected_sequence, expected)

    def test_generated_guard_can_resume_native_run_behind_running_prince(self):
        c = self.encounter(first_alive=True)
        second = self.second_guard(c, x=50)
        second.generation_flags = -1
        second.alert_mode = 2
        c.player.state.facing = 1
        c.player.state.action = 8
        c.choose_guard_action(second)
        self.assertEqual((second.selected_sequence, second.sword_drawn, second.alert_mode),
                         (84, False, 0))

    def test_profiles_and_hit_pause_belong_to_individual_guard(self):
        c = self.encounter(first_alive=True)
        second = self.second_guard(c)
        second.skill, second.life = 5, 3
        with patch.object(c.rng, "randrange", return_value=100):
            table = [0] * 12
            table[5] = 101
            self.assertFalse(c._chance(table, c.guards[0]))
            self.assertTrue(c._chance(table, second))
        c._hurt("guard", second, c.player)
        self.assertEqual(c.attack_pause, HIT_PAUSE[5])
        self.assertEqual(c.guards[0].life, 1)

    def test_player_can_hit_two_npcs_but_cannot_receive_two_wounds_in_one_cycle(self):
        c = self.encounter(first_alive=True)
        first = c.guard
        second = self.second_guard(c, x=195)
        first.life = second.life = 3
        c.player.state.action = 154
        events = c.resolve_contacts()
        self.assertEqual([e.actor for e in events], ["guard", "guard"])
        self.assertEqual((first.life, second.life, c.player.life), (2, 2, 3))
        c = self.encounter(first_alive=True)
        first = c.guard
        second = self.second_guard(c, x=195)
        first.state.action = second.state.action = 154
        c.resolve_contacts()
        self.assertEqual(c.player.life, 2)

    def test_second_guard_trade_uses_native_npc_hit_priority(self):
        c = self.encounter()
        second = self.second_guard(c, x=200)
        c.refresh_target()
        c.player.state.action = second.state.action = 154
        events = c.resolve_contacts()
        self.assertEqual([(e.kind, e.actor) for e in events], [("death", "guard")])
        self.assertEqual(c.player.life, 3)
        self.assertFalse(second.alive)

    def test_reset_removes_reinforcement_and_restores_native_point(self):
        c = self.encounter()
        self.second_guard(c)
        c.generation_points[0].remaining = 0
        c.world_frame = 90
        c.reset()
        self.assertEqual(len(c.guards), 1)
        self.assertIs(c.guard, c.guards[0])
        self.assertEqual((c.guard.life, c.guard.state.target_x, c.world_frame), (1, 149, 0))
        self.assertEqual((c.generation_points[0].countdown, c.generation_points[0].remaining), (5, 1))

    def test_every_entry_pose_renders_from_original_guard_assets(self):
        prince = combat_tests.GuardCombatTests.prince
        art = GuardArtwork(load_resource_file("Guard.rsrc"), prince["SHAP"], 1001,
                           sword_palette_for_level(prince, 5))
        for facing in (0, 1):
            state = SequenceState(84, current_x=100, target_x=100, facing=facing, actor_type=2)
            for pose in range(186, 202):
                state.action = pose
                image = Image.new("RGBA", (510, 365))
                art.draw(image, state, 226)
                self.assertIsNotNone(image.getbbox(), (facing, pose))

    def test_complete_input_driven_opening_and_two_defeated_guards(self):
        fixture = animation_tests.AnimationDataTests()
        fixture.sequences = self.sequences
        scene = fixture.opening_scene()
        scene.combat = CombatEncounter(scene.sequence_runtime, self.sequences,
                                       self.spawn, 408, random.Random(1), self.level)
        first = scene.combat.guard
        clock, parries = 0.0, 0

        def tick():
            nonlocal clock
            clock += 0.1 if scene.sword_drawn else 1 / 12
            scene.advance_animation()

        with patch("scene_prototype.time.perf_counter", side_effect=lambda: clock):
            for _ in range(30):
                if not scene.opening.active:
                    break
                tick()
            self.assertFalse(scene.opening.active)
            scene.horizontal_key(None, -1, True)
            scene.horizontal_key(None, -1, False)
            for _ in range(8):
                tick()
            scene.set_key_state("ctrl", True)
            scene.set_key_state("ctrl", False)
            for _ in range(8):
                tick()
            for _ in range(350):
                c = scene.combat
                if scene.action in (158, 170, 171) and scene.sequence_state.sequence_id == 227:
                    if c.guard.alive and opponent_distance(c.player, c.guard) >= 100:
                        scene.horizontal_key(None, -1, True)
                    else:
                        scene.horizontal_key(None, -1, False)
                        if c.guard.alive and c.guard.state.action in (152, 153):
                            scene.up_key(None)
                            scene.set_key_state("up", False)
                if scene.action == 161:
                    parries += 1
                    scene.set_key_state("ctrl", True)
                    scene.set_key_state("ctrl", False)
                tick()
                if len(c.guards) == 2 and not any(g.alive for g in c.guards):
                    break
            self.assertGreaterEqual(parries, 2)
            self.assertEqual(len(c.guards), 2)
            self.assertFalse(any(g.alive for g in c.guards))
            self.assertEqual(c.player.life, 3)
            self.assertIs(c.guards[0], first)
            for _ in range(12):
                tick()
            self.assertEqual([g.state.action for g in c.guards], [185, 228])
            self.assertFalse(scene._combat_controls_locked())
            scene.restart_opening()
            self.assertEqual(len(c.guards), 1)
            self.assertEqual(c.generation_points[0].remaining, 1)


if __name__ == "__main__":
    unittest.main()
