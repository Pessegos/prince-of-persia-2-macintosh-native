import random
import unittest
from unittest.mock import patch

from PIL import Image, ImageOps

from pop2.animation_data import parse_frame_records, sequence_words
from pop2.combat import (
    CombatEncounter, GuardSpawn, contact_allowed, guard_frame_index,
    opponent_distance, select_sequence, strike_range, PLAYER_COMBAT_TURN_SEQUENCE,
    FATAL_STAB_SEQUENCES,
)
from pop2.combat_art import GuardArtwork, HealthArtwork, HitArtwork
from pop2.render_opening import decode_ctbl, load_resource_file, VIEWPORT_WIDTH, VIEWPORT_HEIGHT
from pop2.scene_prototype import BufferedCommand, sword_palette_for_level
from pop2.sequence_runtime import SequenceRuntime, SequenceState
import tests.test_animation_data as animation_tests


class GuardCombatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prince = load_resource_file("Prince.rsrc")
        cls.kid = load_resource_file("Kid.rsrc")
        cls.guard_resource = load_resource_file("Guard.rsrc")
        cls.sequences = {i: sequence_words(r["data"])
                         for i, r in cls.prince["SEQS"].items()}
        cls.spawn = GuardSpawn.from_level(cls.prince["LEVL"][2000]["data"], 3)

    def encounter(self, player_x=260, guard_x=200, player_facing=0):
        runtime = SequenceRuntime(self.sequences, SequenceState(
            227, action=171, current_x=player_x, target_x=player_x,
            facing=player_facing, actor_type=0, level_kind=5, animation_state=1))
        combat = CombatEncounter(runtime, self.sequences, self.spawn, 408, random.Random(1))
        combat.player.sword_drawn = True
        combat.guard.sword_drawn = True
        combat.guard.alert_mode = 3
        select_sequence(combat.guard, 227)
        combat.guard.runtime.next_frame()
        combat.guard.state.target_x = combat.guard.state.current_x = guard_x
        return combat

    def scene(self):
        fixture = animation_tests.AnimationDataTests()
        fixture.sequences = self.sequences
        fixture.prince, fixture.kid = self.prince, self.kid
        scene = fixture.sword_scene()
        scene.start_tile = 2
        scene.combat = CombatEncounter(scene.sequence_runtime, self.sequences, self.spawn, 408)
        return scene

    def test_guard_generator_decodes_actual_first_room(self):
        self.assertEqual(self.spawn, GuardSpawn(3, 1, 149, 1, 0, 77, 1, alternate_row=0))

    def test_native_jump_bump_distance_boundaries_both_directions(self):
        for facing in (0, 1):
            for sequence, distance, expected in ((3, 24, True), (3, 25, False),
                                                 (4, 62, True), (4, 63, False)):
                with self.subTest(facing=facing, sequence=sequence, distance=distance):
                    c = self.encounter()
                    state = c.player.state
                    c.player.sword_drawn = False
                    state.facing = facing
                    c.guard.state.facing = 1 - facing
                    # Both native standing and running jumps use mode 1.
                    # FrameAdv excludes actor type 1, not animation mode 1.
                    state.animation_state = 1
                    state.sequence_id = sequence
                    state.action = 40
                    state.target_x = state.current_x = 200
                    state.current_y = -30
                    c.guard.state.target_x = 200 + (distance - 21) * (1 if facing else -1)
                    self.assertEqual(c.choose_player_bump(), expected)
                    if expected:
                        self.assertEqual(state.sequence_id, 46)
                        self.assertEqual(state.action, 102)
                        self.assertEqual(state.current_y, -7)
                        self.assertFalse(c.choose_player_bump())
                    else:
                        self.assertEqual(state.sequence_id, sequence)

    def test_body_collision_does_not_replace_unavailable_or_ineligible_states(self):
        for condition in ("armed", "same_facing", "dead_guard", "airborne_guard",
                          "falling_fast", "different_floor", "scripted_jump", "not_alert",
                          "excluded_actor"):
            with self.subTest(condition=condition):
                c = self.encounter(player_x=200, guard_x=221, player_facing=1)
                c.guard.state.facing = 0
                c.player.sword_drawn = False
                c.player.state.animation_state = 0
                c.player.state.sequence_id, c.player.state.action = 4, 40
                if condition == "armed":
                    c.player.sword_drawn = True
                elif condition == "same_facing":
                    c.guard.state.facing = 1
                elif condition == "dead_guard":
                    c.guard.life = 0
                elif condition == "airborne_guard":
                    c.guard.state.animation_state = 4
                elif condition == "falling_fast":
                    c.player.state.vertical_velocity = 59
                elif condition == "different_floor":
                    c.guard.row = 0
                elif condition == "scripted_jump":
                    c.guard.selected_sequence = 110
                elif condition == "not_alert":
                    c.guard.alert_mode = 1
                elif condition == "excluded_actor":
                    c.player.state.actor_type = 1
                self.assertFalse(c.choose_player_bump())
                self.assertEqual(c.player.state.sequence_id, 4)

    def test_standing_jump_cannot_skip_contact_interval_in_one_frame(self):
        for facing in (0, 1):
            with self.subTest(facing=facing):
                c = self.encounter()
                direction = 1 if facing else -1
                state = c.player.state
                c.player.sword_drawn = False
                state.facing = facing
                c.guard.state.facing = 1 - facing
                state.sequence_id, state.action = 3, 25
                state.target_x = state.current_x = 200 + 49 * direction
                c.guard.state.target_x = 200 + 15 * direction
                self.assertFalse(c.choose_player_bump())
                self.assertTrue(c.choose_player_bump(old_x=200))
                self.assertEqual((state.sequence_id, state.action), (46, 102))
                self.assertEqual(state.target_x, c.guard.state.target_x + 2 * direction)

    def test_jump_sweep_does_not_invent_contact_outside_native_interval(self):
        for facing in (0, 1):
            for condition in ("too_far", "behind", "moving_away", "armed", "ordinary_run"):
                with self.subTest(facing=facing, condition=condition):
                    c = self.encounter()
                    direction = 1 if facing else -1
                    state = c.player.state
                    c.player.sword_drawn = condition == "armed"
                    state.facing = facing
                    c.guard.state.facing = 1 - facing
                    state.sequence_id, state.action = (1, 8) if condition == "ordinary_run" else (3, 25)
                    state.target_x = state.current_x = 200 + 49 * direction
                    gap = {"too_far": 100, "behind": -40}.get(condition, 15)
                    c.guard.state.target_x = 200 + gap * direction
                    old_x = 200 + 80 * direction if condition == "moving_away" else 200
                    self.assertFalse(c.choose_player_bump(old_x))

    def test_secret_guard_palette_is_the_generator_variant_not_its_skill(self):
        spawn = GuardSpawn.from_level(self.prince["LEVL"][2000]["data"], 4)
        self.assertEqual((spawn.palette_variant, spawn.skill, spawn.life), (3, 1, 3))

    def test_guard_sprite_cache_keeps_palette_variants_separate(self):
        art = GuardArtwork(self.guard_resource, self.prince["SHAP"],
                           int.from_bytes(self.prince["SHPL"][1000]["data"][:2], "big"),
                           sword_palette_for_level(self.prince, 5))
        state = SequenceState(227, action=171, target_x=100, facing=0)
        images = []
        for variant in (1, 3, 1):
            image = Image.new("RGBA", (200, 240))
            art.draw(image, state, 226, variant)
            images.append(image)
        self.assertEqual(images[0].tobytes(), images[2].tobytes())
        self.assertNotEqual(images[0].tobytes(), images[1].tobytes())
        colors = {color for _count, color in images[1].getcolors(images[1].width * images[1].height)}
        self.assertIn((84, 21, 30, 255), colors)
        self.assertIn((255, 245, 176, 255), colors)

    def test_zero_generator_health_uses_source_default_three(self):
        level = bytearray(self.prince["LEVL"][2000]["data"])
        offset = 0x20E6 + 4 * 0xC0 + 2 + 26
        level[offset:offset + 2] = b"\x00\x00"
        self.assertEqual(GuardSpawn.from_level(level, 3).life, 3)

    def test_distance_uses_source_facing_correction_both_directions(self):
        c = self.encounter()
        self.assertEqual(opponent_distance(c.player, c.guard), 81)
        self.assertEqual(opponent_distance(c.guard, c.player), 81)
        c.player.state.facing = 1
        self.assertEqual(opponent_distance(c.player, c.guard), -60)
        self.assertEqual(opponent_distance(c.guard, c.player), 60)

    def test_distance_rejects_another_room_or_floor(self):
        c = self.encounter()
        c.guard.row = 2
        self.assertEqual(opponent_distance(c.player, c.guard), 999)
        self.assertFalse(contact_allowed(c.player, c.guard))
        c.guard.row = 1
        c.guard.room = 2
        self.assertEqual(opponent_distance(c.player, c.guard), 999)

    def test_strike_ranges_match_armed_unarmed_and_behind_branches(self):
        c = self.encounter()
        self.assertEqual(strike_range(c.player, c.guard), (61, 99))
        self.assertEqual(strike_range(c.guard, c.player), (61, 99))
        # CODE:6 0x5d08/0x5d16 test the sword flag, not animation state.
        for mode in (0, 1, 5, 10):
            c.player.state.animation_state = mode
            for armed in (False, True):
                c.player.sword_drawn = armed
                c.player.state.facing = 0
                self.assertEqual(strike_range(c.guard, c.player),
                                 (61 if armed else 35, 99))
                c.player.state.facing = 1
                self.assertEqual(strike_range(c.guard, c.player),
                                 (45, 85) if armed else (42, 83))
        c.guard.sword_drawn = False
        self.assertEqual(strike_range(c.player, c.guard), (61, 99))
        c.guard.alert_mode = 0
        self.assertEqual(strike_range(c.player, c.guard), (46, 99))

    def test_only_contact_pose_154_deals_damage(self):
        for action in (151, 152, 153, 155, 156, 157):
            c = self.encounter()
            c.player.state.action = action
            self.assertEqual(c.resolve_contacts(), [])
            self.assertEqual(c.guard.life, 1)
        c.player.state.action = 154
        self.assertEqual([(e.kind, e.actor) for e in c.resolve_contacts()], [("death", "guard")])

    def test_damage_range_boundaries_are_inclusive(self):
        for distance, hit in ((60, False), (61, True), (99, True), (100, False)):
            c = self.encounter(player_x=200 + distance - 21)
            c.player.state.action = 154
            c.resolve_contacts()
            self.assertEqual(c.guard.alive, not hit, distance)

    def test_attack_behind_facing_does_not_hit(self):
        c = self.encounter(player_facing=1)
        c.player.state.action = 154
        self.assertEqual(c.resolve_contacts(), [])

    def test_player_auto_turn_uses_native_sword_sequence_both_directions(self):
        for facing, x in ((1, 260), (0, 140)):
            c = self.encounter(player_x=x, player_facing=facing)
            self.assertTrue(c.choose_player_turn())
            self.assertEqual(c.player.state.sequence_id, PLAYER_COMBAT_TURN_SEQUENCE)
            self.assertEqual(c.player.state.facing, facing)
            poses = []
            for _ in range(9):
                c.player.runtime.next_frame()
                poses.append(c.player.state.action)
            self.assertEqual(poses, [177, 178, 211, 213, 212, 171, 160, 157, 158])
            self.assertEqual(c.player.state.facing, 1 - facing)
            self.assertEqual(c.player.state.target_x, x + (23 if facing else -23))
            self.assertEqual(c.player.state.sequence_id, 227)

    def test_auto_turn_leaves_front_and_close_overlap_alone(self):
        for x, facing, turns in ((140, 1, False), (200, 1, False),
                                  (215, 1, False), (216, 1, True)):
            c = self.encounter(player_x=x, player_facing=facing)
            self.assertEqual(c.choose_player_turn(), turns, (x, facing))

    def test_auto_turn_rejects_unavailable_or_unengaged_target(self):
        for field, value in (("life", 0), ("targetable", False),
                             ("alert_mode", 0), ("row", 2), ("room", 2)):
            c = self.encounter(player_facing=1)
            setattr(c.guard, field, value)
            self.assertFalse(c.choose_player_turn(), field)

    def test_auto_turn_preserves_protected_player_animations(self):
        for field, value in (("life", 0), ("targetable", False),
                             ("sword_drawn", False)):
            c = self.encounter(player_facing=1)
            setattr(c.player, field, value)
            self.assertFalse(c.choose_player_turn(), field)
        for mode in (2, 3, 4, 5, 8, 9, 10):
            c = self.encounter(player_facing=1)
            c.player.recovering = True
            c.player.state.animation_state = mode
            self.assertFalse(c.choose_player_turn(), mode)

    def test_ready_hurt_recovery_waits_for_an_engaged_opponent(self):
        c = self.encounter(player_facing=1)
        c.player.recovering = True
        c.guard.alert_mode = 1
        c.player.state.sequence_id = 205
        c.player.state.action = 156
        c.player.state.animation_state = 0
        self.assertFalse(c.choose_player_turn())
        c.guard.alert_mode = 2
        self.assertTrue(c.choose_player_turn())
        self.assertEqual(c.player.state.sequence_id, PLAYER_COMBAT_TURN_SEQUENCE)

    def test_auto_turn_uses_combat_control_state_not_a_generic_idle_check(self):
        c = self.encounter(player_facing=1)
        select_sequence(c.player, 56)
        c.player.runtime.next_frame()
        self.assertEqual(c.player.state.animation_state, 1)
        self.assertTrue(c.choose_player_turn())
        self.assertEqual(c.player.state.sequence_id, 127)

    def test_drawing_sword_while_facing_away_then_turning(self):
        scene = self.scene()
        scene.sequence_state.facing = 1
        scene.player_x = scene.sequence_state.target_x = 350
        scene.combat.guard.alert_mode = 3
        scene.combat.guard.sword_drawn = True
        with patch.object(scene.combat, "step", return_value=[]):
            scene.set_key_state("ctrl", True)
            scene.set_key_state("ctrl", False)
            self.assertEqual(scene.action, 207)
            scene.advance_animation()
            self.assertEqual(scene.action, 177)
            self.assertEqual(scene.sequence_state.facing, 0)
            self.assertAlmostEqual(scene.current_animation_interval_ms(), 100)

    def test_auto_turn_retains_one_buffered_attack_and_no_idle_pause(self):
        scene = self.scene()
        scene.sword_drawn = True
        scene.sequence_state.facing = 1
        scene.player_x = scene.sequence_state.target_x = 350
        scene.combat.guard.alert_mode = 3
        scene.combat.guard.sword_drawn = True
        scene.start_sequence(227)
        scene.sequence_runtime.next_frame()
        command = BufferedCommand("sword_attack")
        scene.pending_action = command
        with patch.object(scene.combat, "step", return_value=[]):
            scene.advance_animation()
            self.assertEqual(scene.action, 177)
            self.assertIs(scene.pending_action, command)
            poses = [scene.action]
            for _ in range(8):
                scene.advance_animation()
                poses.append(scene.action)
        self.assertEqual(poses, [177, 178, 211, 213, 212, 171, 160, 157, 151])
        self.assertIsNone(scene.pending_action)

    def test_sheathing_does_not_start_an_automatic_turn(self):
        scene = self.scene()
        scene.sword_drawn = scene.sword_sheathing = True
        scene.sequence_state.facing = 1
        scene.combat.guard.alert_mode = 3
        scene.start_sequence(92)
        scene.sequence_runtime.next_frame()
        self.assertFalse(scene.resume_combat_turn())

    def test_airborne_hanging_and_opening_targets_are_not_hit(self):
        for y, targetable, mode in ((-15, True, 1), (80, True, 1), (0, False, 1), (0, True, 8)):
            c = self.encounter()
            c.guard.state.action = 154
            c.player.state.current_y = y
            c.player.targetable = targetable
            c.player.state.animation_state = mode
            self.assertEqual(c.resolve_contacts(), [])
            self.assertEqual(c.player.life, 3)
        c = self.encounter()
        c.guard.state.action = 154
        c.player.state.current_y = -14
        self.assertEqual(c.resolve_contacts()[0].kind, "hit")

    def test_one_hit_per_swing_even_with_extra_key_callbacks(self):
        c = self.encounter()
        c.guard.state.action = 154
        c.resolve_contacts()
        for _ in range(12):
            c.resolve_contacts()
        self.assertEqual(c.player.life, 2)

    def test_new_swing_can_hit_after_recovery(self):
        c = self.encounter()
        c.guard.state.action = 154
        c.resolve_contacts()
        while c.player.recovering:
            c.advance_player_recovery()
        c.guard.state.action = 152
        c.resolve_contacts()
        c.guard.state.target_x = c.player.state.target_x - 60
        c.guard.state.action = 154
        c.resolve_contacts()
        self.assertEqual(c.player.life, 1)

    def test_block_intercepts_153_and_154_without_health_loss(self):
        for action in (153, 154):
            c = self.encounter()
            c.guard.state.action = action
            c.player.state.action = 150
            events = c.resolve_contacts()
            self.assertEqual([(e.kind, e.actor) for e in events], [("parry", "player")])
            self.assertEqual(c.player.life, 3)
            self.assertEqual(c.guard.state.sequence_id, 69)
            self.assertEqual(c.guard.state.action, 167)
            self.assertEqual(c.player.state.action, 161)
            self.assertEqual(c.parry_timer, 4)

    def test_successful_player_parry_recoils_nine_pixels_before_retreat(self):
        for facing in (0, 1):
            with self.subTest(facing=facing):
                scene = self.scene()
                scene.sword_drawn = True
                scene.in_animation_tick = True
                state = scene.sequence_state
                state.facing, state.action = facing, 161
                state.current_x = state.target_x = scene.player_x = 260
                scene.pending_action = BufferedCommand("sword_block")
                self.assertTrue(scene.resume_sword_parry_recoil())
                self.assertEqual(state.target_x, 269 if facing == 0 else 251)
                self.assertEqual(state.source_sequence_id, 57)
                self.assertEqual(scene.pending_action.kind, "sword_block")
                state.action = 160
                self.assertFalse(scene.resume_sword_parry_recoil())

    def test_player_parry_counter_has_priority_over_forced_retreat(self):
        scene = self.scene()
        scene.sword_drawn = True
        scene.in_animation_tick = True
        state = scene.sequence_state
        state.action = 161
        x = state.target_x
        scene.pending_action = BufferedCommand("sword_attack")
        self.assertFalse(scene.resume_sword_parry_recoil())
        self.assertTrue(scene.resume_sword_attack_after_block())
        self.assertEqual(state.source_sequence_id, 66)
        self.assertEqual(state.target_x, x)
        self.assertIsNone(scene.pending_action)

    def test_uncontacted_block_and_unarmed_pose_do_not_recoil(self):
        scene = self.scene()
        for action, drawn, sheathing in ((150, True, False), (169, True, False),
                                         (161, False, False), (161, True, True)):
            with self.subTest(action=action, drawn=drawn, sheathing=sheathing):
                scene.sequence_state.action = action
                scene.sword_drawn, scene.sword_sheathing = drawn, sheathing
                x = scene.sequence_state.target_x
                self.assertFalse(scene.resume_sword_parry_recoil())
                self.assertEqual(scene.sequence_state.target_x, x)

    def test_block_requires_opposed_facing_and_parry_range(self):
        for distance in (60, 100):
            c = self.encounter(player_x=200 + distance - 21)
            c.guard.state.action = 153
            c.player.state.action = 150
            self.assertEqual(c.resolve_contacts(), [])
        c = self.encounter(player_facing=1)
        c.guard.state.action = 154
        c.player.state.action = 150
        self.assertEqual(c.resolve_contacts()[0].kind, "hit")

    def test_raised_counterattack_pose_is_not_an_active_block(self):
        # CheckStrike 6:59b8-59c6 accepts only 150/161, not counter pose 162.
        for pose, expected in ((150, "parry"), (161, "parry"), (162, "hit")):
            with self.subTest(pose=pose):
                c = self.encounter()
                c.guard.state.action = 154
                c.player.state.action = pose
                events = c.resolve_contacts()
                self.assertEqual(events[0].kind, expected)
                self.assertEqual(c.player.life, 3 if expected == "parry" else 2)

    def test_simultaneous_damage_cancels_player_wound_as_in_check_stab(self):
        for facing, player_x in ((0, 260), (1, 140)):
            for guard_life in (1, 3):
                with self.subTest(facing=facing, guard_life=guard_life):
                    c = self.encounter(player_x=player_x, player_facing=facing)
                    c.guard.state.facing = 1 - facing
                    c.guard.life = c.guard.max_life = guard_life
                    c.guard.state.action = c.player.state.action = 154
                    player_state = vars(c.player.state).copy()
                    events = c.resolve_contacts()
                    kind = "death" if guard_life == 1 else "hit"
                    self.assertEqual([(e.kind, e.actor) for e in events], [(kind, "guard")])
                    self.assertEqual(c.guard.life, guard_life - 1)
                    self.assertEqual(c.player.life, 3)
                    self.assertFalse(c.player.recovering)
                    self.assertEqual(vars(c.player.state), player_state)
                    self.assertEqual(c.guard.state.sequence_id, 85 if guard_life == 1 else 183)

    def test_canceled_simultaneous_hit_does_not_arrive_on_extra_callbacks(self):
        c = self.encounter()
        c.guard.life = c.guard.max_life = 3
        c.guard.state.action = c.player.state.action = 154
        self.assertEqual(c.resolve_contacts()[0].actor, "guard")
        self.assertTrue(c.player.contact_consumed)
        for _ in range(12):
            self.assertEqual(c.resolve_contacts(), [])
        self.assertEqual(c.player.life, 3)
        self.assertEqual(c.guard.life, 2)

    def test_guard_contact_still_hits_when_simultaneous_player_strike_misses(self):
        c = self.encounter()
        c.guard.alert_mode = 0
        c.guard.state.action = c.player.state.action = 154
        # Distance 81 is in the guard's 61-99 range, not the Prince's 83-121.
        self.assertEqual(opponent_distance(c.player, c.guard), 81)
        events = c.resolve_contacts()
        self.assertEqual([(e.kind, e.actor) for e in events], [("hit", "player")])
        self.assertEqual(c.player.life, 2)
        self.assertEqual(c.guard.life, 1)

    def test_guard_contact_still_hits_before_player_damage_pose(self):
        c = self.encounter()
        c.guard.state.action = 154
        c.player.state.action = 153
        events = c.resolve_contacts()
        self.assertEqual([(e.kind, e.actor) for e in events], [("hit", "player")])
        self.assertEqual(c.player.life, 2)
        self.assertEqual(c.guard.life, 1)

    def test_guard_block_still_parries_player_contact_without_damage(self):
        for action in (153, 154):
            with self.subTest(action=action):
                c = self.encounter()
                c.player.state.action = action
                c.guard.state.action = 150
                events = c.resolve_contacts()
                self.assertEqual([(e.kind, e.actor) for e in events], [("parry", "guard")])
                self.assertEqual(c.player.life, 3)
                self.assertEqual(c.guard.life, 1)
                self.assertEqual(c.player.state.sequence_id, 69)
                self.assertEqual(c.player.state.action, 167)
                self.assertEqual(c.guard.state.action, 161)
                self.assertEqual(c.parry_timer, 0)

    def test_guard_death_uses_original_offsets_and_terminal_corpse(self):
        c = self.encounter()
        c.player.state.action = 154
        c.resolve_contacts()
        self.assertEqual(c.guard.state.sequence_id, 85)
        self.assertEqual(c.guard.state.action, 179)
        # Opposed hit -10 (6:52ec), then flat death -17 (6:5524).
        self.assertEqual(c.guard.state.target_x, 173)
        poses = []
        for _ in range(12):
            c.advance_guard()
            poses.append(c.guard.state.action)
        self.assertEqual(poses[:6], [180, 181, 182, 183, 185, 185])
        self.assertEqual(poses[-1], 185)
        self.assertFalse(c.guard.alive)

    def test_player_death_blocks_controls_and_has_no_idle_recovery(self):
        c = self.encounter()
        c.player.life = 1
        c.guard.state.action = 154
        c.resolve_contacts()
        self.assertTrue(c.player.controls_locked)
        for _ in range(12):
            c.advance_player_recovery()
        self.assertEqual(c.player.state.action, 185)
        self.assertFalse(c.player.alive)

    def test_fatal_guard_hit_selects_guard_not_skeleton_death_music(self):
        c = self.encounter()
        c.player.life = 1
        event = c._hurt("player", c.player, c.guard)
        self.assertEqual((event.kind, event.actor, event.death_method),
                         ("death", "player", 14))
        self.assertIsNone(c._hurt("guard", c.guard, c.player).death_method)

    def test_guard_lowers_sword_after_kill_only_at_native_ready_poses(self):
        for action in (158, 170, 171):
            with self.subTest(action=action):
                c = self.encounter()
                c.player.life = 0
                c.guard.state.action = action
                x = c.guard.state.target_x
                c.advance_guard()
                self.assertEqual((c.guard.state.sequence_id, c.guard.state.action), (77, 166))
                self.assertFalse(c.guard.sword_drawn)
                self.assertEqual(c.guard.alert_mode, 0)
                for _ in range(30):
                    c.advance_guard()
                self.assertEqual((c.guard.state.action, c.guard.state.target_x), (166, x))

    def test_guard_finishes_its_attack_before_lowering_sword(self):
        c = self.encounter()
        select_sequence(c.guard, 58)
        c.guard.runtime.next_frame()
        self.assertEqual(c.guard.state.action, 168)
        c.player.life = 0
        poses = []
        for _ in range(15):
            c.advance_guard()
            poses.append(c.guard.state.action)
        self.assertEqual(poses[:5], [151, 152, 153, 154, 155])
        self.assertEqual(poses[-1], 166)
        self.assertFalse(c.guard.sword_drawn)

    def test_unarmed_hit_arms_player_and_recovers_to_sword_guard(self):
        for facing, hurt_sequence in ((0, 74), (1, 94)):
            c = self.encounter(player_facing=facing)
            c.player.sword_drawn = False
            select_sequence(c.player, 2)
            c.player.runtime.next_frame()
            c.guard.state.action = 154
            events = c.resolve_contacts()
            self.assertEqual([(e.kind, e.actor) for e in events], [("hit", "player")])
            self.assertEqual(c.player.life, 2)
            self.assertTrue(c.player.sword_drawn)
            self.assertEqual(c.player.state.sequence_id, hurt_sequence)
            poses = [c.player.state.action]
            for _ in range(10):
                c.advance_player_recovery()
                poses.append(c.player.state.action)
            self.assertEqual(c.player.state.sequence_id, 227)
            self.assertNotIn(15, poses)
            self.assertFalse(c.player.controls_locked)
            self.assertTrue(c.player.sword_drawn)
            if facing:
                self.assertTrue(c.choose_player_turn())

    def test_scene_preserves_auto_armed_mode_across_recovery_and_next_input(self):
        scene = self.scene()
        c = scene.combat
        scene.player_x = scene.sequence_state.target_x = scene.sequence_state.current_x = 260
        c.guard.state.target_x = c.guard.state.current_x = 200
        c.guard.sword_drawn = True
        c.guard.state.action = 154
        scene.pending_action = BufferedCommand("jump")
        with patch.object(c, "advance_guard"):
            scene.advance_combat()
            self.assertTrue(scene.sword_drawn)
            self.assertTrue(c.player.sword_drawn)
            self.assertIsNone(scene.pending_action)
            self.assertAlmostEqual(scene.current_animation_interval_ms(), 100)
            for _ in range(10):
                scene.advance_animation()
            self.assertTrue(scene.sword_drawn)
            self.assertTrue(c.player.sword_drawn)
            self.assertEqual(scene.sequence_state.sequence_id, 227)
            self.assertFalse(scene._combat_controls_locked())
            scene.set_key_state("ctrl", True)
            self.assertEqual(scene.sequence_state.sequence_id, 75)
            self.assertEqual(scene.action, 151)

    def test_native_vulnerable_sequences_are_fatal_only_when_struck(self):
        self.assertEqual(FATAL_STAB_SEQUENCES, {10, 16, 28, 14})
        for sequence in FATAL_STAB_SEQUENCES:
            for life in (1, 2, 3):
                c = self.encounter()
                c.player.sword_drawn = False
                c.player.life = life
                select_sequence(c.player, sequence)
                c.player.runtime.next_frame()
                self.assertEqual(c.player.life, life)
                c.guard.state.action = 154
                events = c.resolve_contacts()
                self.assertEqual([(e.kind, e.actor) for e in events], [("death", "player")])
                self.assertEqual(c.player.life, 0)
                self.assertTrue(c.player.controls_locked)
                self.assertFalse(c.player.sword_drawn)
                self.assertEqual(c.player.state.sequence_id, 85)
                self.assertEqual(c.player.state.action, 179)
                self.assertEqual(c.player.state.animation_state, 10)
                for _ in range(10):
                    c.advance_player_recovery()
                self.assertEqual(c.player.state.action, 185)
                self.assertTrue(c.player.controls_locked)

    def test_horizontal_jumps_and_landing_do_not_inherit_vertical_jump_lethality(self):
        for sequence in (2, 3, 4, 11):
            c = self.encounter()
            c.player.sword_drawn = False
            select_sequence(c.player, sequence)
            c.player.runtime.next_frame()
            c.guard.state.action = 154
            events = c.resolve_contacts()
            self.assertEqual([(e.kind, e.actor) for e in events], [("hit", "player")])
            self.assertEqual(c.player.life, 2)
            self.assertTrue(c.player.sword_drawn)

    def test_vertical_jump_does_not_override_contact_range_or_strike_pose(self):
        for distance, y, action in ((100, 0, 154), (34, 0, 154),
                                    (81, -15, 154), (81, 0, 153)):
            c = self.encounter(player_x=200 + distance - 21)
            c.player.sword_drawn = False
            select_sequence(c.player, 28)
            c.player.runtime.next_frame()
            c.player.state.current_y = y
            c.guard.state.action = action
            self.assertEqual(c.resolve_contacts(), [], (distance, y, action))
            self.assertEqual(c.player.life, 3)
            self.assertFalse(c.player.sword_drawn)

    def test_hurt_or_death_reanchors_player_and_clears_vertical_velocity(self):
        for sequence in (2, 28):
            c = self.encounter()
            c.player.sword_drawn = False
            select_sequence(c.player, sequence)
            c.player.runtime.next_frame()
            c.player.state.current_y = -11
            c.player.state.vertical_velocity = 17
            c.guard.state.action = 154
            c.resolve_contacts()
            self.assertEqual(c.player.state.current_y, 0)
            self.assertEqual(c.player.state.vertical_velocity, 0)

    def test_scene_vertical_jump_hit_empties_hud_and_cannot_resume_held_jump(self):
        scene = self.scene()
        c = scene.combat
        scene.player_x = scene.sequence_state.current_x = scene.sequence_state.target_x = 260
        c.guard.state.current_x = c.guard.state.target_x = 200
        c.guard.sword_drawn = True
        c.guard.state.action = 154
        scene.up_held = scene.jump_repeat_armed = True
        scene.start_sequence(28)
        scene.sequence_runtime.next_frame()
        scene.pending_action = BufferedCommand("jump")
        with patch.object(c, "advance_guard"):
            scene.advance_combat()
            self.assertEqual(c.player.life, 0)
            self.assertFalse(scene.sword_drawn)
            self.assertFalse(scene.up_held)
            self.assertFalse(scene.jump_repeat_armed)
            self.assertIsNone(scene.pending_action)
            for _ in range(15):
                scene.advance_animation()
            self.assertEqual(scene.action, 185)
            self.assertTrue(scene._combat_controls_locked())

    def test_guard_engarde_and_advance_use_guard_not_kid_sequences(self):
        c = self.encounter(player_x=400)
        select_sequence(c.guard, 77)
        c.guard.runtime.next_frame()
        c.guard.sword_drawn = False
        c.advance_guard()
        self.assertTrue(c.guard.sword_drawn)
        self.assertEqual(c.guard.state.target_x, 217)
        self.assertEqual(c.guard.state.action, 158)
        with patch.object(c, "_chance", return_value=True):
            c.advance_guard()
        self.assertEqual(c.guard.state.sequence_id, 86)
        self.assertEqual(c.guard.state.action, 164)

    def test_first_guard_does_not_invent_defence_for_skill_zero(self):
        c = self.encounter()
        c.player.state.action = 152
        c.choose_guard_action()
        self.assertEqual(c.guard.state.sequence_id, 58)

    def test_guard_turn_can_interrupt_a_low_mode_step_but_does_not_restart_itself(self):
        c = self.encounter(player_x=130)
        select_sequence(c.guard, 86)
        c.guard.runtime.next_frame()
        c.choose_guard_action()
        self.assertEqual(c.guard.state.sequence_id, 60)
        c.guard.runtime.next_frame()
        self.assertGreaterEqual(c.guard.state.animation_state, 2)
        cursor = c.guard.state.cursor
        c.choose_guard_action()
        self.assertEqual(c.guard.state.cursor, cursor)
        facing = c.guard.state.facing
        for _ in range(4):
            c.advance_guard()
        self.assertNotEqual(c.guard.state.facing, facing)

    def test_ai_cannot_advance_more_often_from_keyboard_events(self):
        c = self.encounter(player_x=400)
        with patch.object(c, "_chance", return_value=True):
            c.step(0.0, 0.1)
            cursor = c.guard.state.cursor
            for t in (0.01, 0.03, 0.07):
                c.step(t, 0.1)
            self.assertEqual(c.guard.state.cursor, cursor)
            c.step(0.1, 0.1)
            self.assertNotEqual(c.guard.state.cursor, cursor)

    def test_clock_does_not_skip_due_to_tk_millisecond_rounding(self):
        c = self.encounter(player_x=400)
        with patch.object(c, "advance_guard") as advance:
            for i in range(13):
                c.step(round(i / 12, 3), 1 / 12)
            self.assertEqual(advance.call_count, 13)

    def test_guard_stays_on_first_rooftop_support(self):
        c = self.encounter(player_x=509, guard_x=403)
        select_sequence(c.guard, 86)
        for _ in range(3):
            c.advance_guard()
        self.assertLessEqual(c.guard.state.target_x, 408)

    def test_f5_resets_health_corpse_inputs_and_guard_clock(self):
        scene = self.scene()
        scene.combat.guard.life = 0
        scene.combat.player.life = 0
        scene.combat.last_guard_at = 400
        scene.pending_action = BufferedCommand("sword_attack")
        scene.restart_opening()
        self.assertEqual(scene.combat.player.life, 3)
        self.assertEqual(scene.combat.guard.life, 1)
        self.assertEqual(scene.combat.guard.state.target_x, 149)
        self.assertIsNone(scene.combat.last_guard_at)
        self.assertIsNone(scene.pending_action)
        self.assertTrue(scene.opening.active)

    def test_dead_player_cannot_queue_or_start_commands(self):
        scene = self.scene()
        scene.combat.player.life = 0
        scene.set_key_state("ctrl", True)
        scene.horizontal_key(None, -1, True)
        scene.up_key(None)
        self.assertIsNone(scene.pending_action)
        self.assertFalse(scene.sword_drawn)
        self.assertFalse(scene.dispatch_pending_action())

    def test_complete_opening_defence_counterattack_and_guard_defeat(self):
        fixture = animation_tests.AnimationDataTests()
        fixture.sequences = self.sequences
        fixture.prince, fixture.kid = self.prince, self.kid
        scene = fixture.opening_scene()
        scene.combat = CombatEncounter(scene.sequence_runtime, self.sequences,
                                       self.spawn, 408, random.Random(1))
        clock = 0.0

        def tick():
            nonlocal clock
            clock += 0.1 if scene.sword_drawn else 1 / 12
            scene.advance_animation()

        with patch("pop2.scene_prototype.time.perf_counter", side_effect=lambda: clock):
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
            parried = False
            for _ in range(100):
                c = scene.combat
                if scene.action in (158, 170, 171) and scene.sequence_state.sequence_id == 227:
                    if opponent_distance(c.player, c.guard) >= 100:
                        scene.horizontal_key(None, -1, True)
                    else:
                        scene.horizontal_key(None, -1, False)
                        if c.guard.state.action in (152, 153):
                            scene.up_key(None)
                            scene.set_key_state("up", False)
                if scene.action == 161:
                    parried = True
                    scene.set_key_state("ctrl", True)
                    scene.set_key_state("ctrl", False)
                tick()
                if not c.guard.alive:
                    break
            self.assertTrue(parried)
            self.assertFalse(scene.combat.guard.alive)
            self.assertEqual(scene.combat.player.life, 3)
            for _ in range(12):
                tick()
            self.assertEqual(scene.combat.guard.state.action, 185)
            self.assertFalse(scene._combat_controls_locked())

    def test_source_guard_pose_mapping(self):
        self.assertEqual(guard_frame_index(166), 17)
        self.assertEqual(guard_frame_index(154), 5)
        self.assertEqual(guard_frame_index(185), 36)
        self.assertEqual(guard_frame_index(103), 24)

    def test_all_guard_fight_and_death_poses_render_from_original_assets(self):
        art = GuardArtwork(self.guard_resource, self.prince["SHAP"], 1001,
                           sword_palette_for_level(self.prince, 5))
        c = self.encounter()
        for facing in (0, 1):
            c.guard.state.facing = facing
            for action in (*range(150, 175), 179, 180, 181, 182, 183, 185):
                c.guard.state.action = action
                image = Image.new("RGBA", (510, 365))
                art.draw(image, c.guard.state, 226)
                self.assertIsNotNone(image.getbbox(), (facing, action))

    def test_health_hud_uses_original_native_pixel_strip(self):
        from pop2.render_opening import decode_ctbl
        base = int.from_bytes(self.kid["SHPL"][25001]["data"][:2], "big")
        art = HealthArtwork(self.kid, decode_ctbl(self.kid["CTBL"][25001]["data"]), base)
        c = self.encounter()
        viewport = Image.new("RGBA", (VIEWPORT_WIDTH, VIEWPORT_HEIGHT))
        art.draw(viewport, c)
        self.assertIsNone(viewport.crop((0, 0, 512, 368)).getbbox())
        self.assertIsNotNone(viewport.crop((3, 368, 38, 384)).getbbox())
        self.assertIsNotNone(viewport.crop((495, 368, 512, 384)).getbbox())
        c.player.life = 1
        c.guard.life = 0
        viewport = Image.new("RGBA", (512, 384))
        art.draw(viewport, c)
        self.assertIsNone(viewport.crop((495, 368, 512, 384)).getbbox())
        self.assertNotEqual(art.icons[299].tobytes(), art.icons[300].tobytes())

    def hit_art(self):
        base = int.from_bytes(self.kid["SHPL"][25001]["data"][:2], "big")
        return HitArtwork(
            self.kid, decode_ctbl(self.kid["CTBL"][25001]["data"]), base,
            parse_frame_records(self.kid["FRAM"][25001]["data"]),
            parse_frame_records(self.guard_resource["FRAM"][750]["data"]),
        )

    def test_hit_uses_original_burst_pixels_and_native_body_offsets(self):
        art = self.hit_art()
        self.assertEqual(art.sprite.size, (46, 44))
        c = self.encounter()
        for fighter, action, facing, x, y in (
                (c.player, 172, 0, 220, 153), (c.player, 172, 1, 254, 153),
                (c.guard, 172, 0, 172, 162), (c.guard, 172, 1, 182, 162),
                (c.guard, 179, 0, 167, 163), (c.guard, 179, 1, 187, 163)):
            fighter.state.action = action
            fighter.state.facing = facing
            fighter.state.animation_state = 10
            image = Image.new("RGBA", (510, 365))
            art.draw(image, fighter.state, 226)
            expected = Image.new("RGBA", image.size)
            sprite = ImageOps.mirror(art.sprite) if facing else art.sprite
            expected.paste(sprite, (x, y), sprite)
            self.assertEqual(image.tobytes(), expected.tobytes(), (action, facing))

    def test_hurt_and_fatal_hits_show_burst_for_exactly_one_animation_pose(self):
        art = self.hit_art()
        for victim in ("player", "guard"):
            c = self.encounter()
            target = getattr(c, victim)
            attacker = c.guard if victim == "player" else c.player
            attacker.state.action = 154
            c.resolve_contacts()
            image = Image.new("RGBA", (510, 365))
            art.draw(image, target.state, 226)
            self.assertIsNotNone(image.getbbox(), victim)
            # Repaints do not consume the effect or mutate animation state.
            again = Image.new("RGBA", image.size)
            art.draw(again, target.state, 226)
            self.assertEqual(image.tobytes(), again.tobytes())
            target.runtime.next_frame()
            after = Image.new("RGBA", image.size)
            art.draw(after, target.state, 226)
            self.assertIsNone(after.getbbox(), victim)

    def test_misses_and_parries_do_not_draw_blood(self):
        art = self.hit_art()
        for parry in (False, True):
            c = self.encounter(player_x=260 if parry else 350)
            c.player.state.action = 150 if parry else 171
            c.guard.state.action = 154
            c.resolve_contacts()
            image = Image.new("RGBA", (510, 365))
            for fighter in (c.player, c.guard):
                art.draw(image, fighter.state, 226)
            self.assertIsNone(image.getbbox())

    def test_reset_clears_impact_and_engagement_state(self):
        scene = self.scene()
        c = scene.combat
        c.player.state.animation_state = c.guard.state.animation_state = 10
        c.guard.alert_mode = 3
        scene.restart_opening()
        art = self.hit_art()
        image = Image.new("RGBA", (510, 365))
        for fighter in (c.player, c.guard):
            art.draw(image, fighter.state, 226)
        self.assertIsNone(image.getbbox())
        self.assertEqual(c.guard.alert_mode, 0)


if __name__ == "__main__":
    unittest.main()
