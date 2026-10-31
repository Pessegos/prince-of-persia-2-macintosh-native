from dataclasses import replace
import hashlib
import os
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pop2.animation_data import sequence_words
from pop2.combat import (
    CombatEncounter, GuardIntent, GuardSpawn, advancable_tile, moving_fight_pose,
    nearest_opponent, select_sequence, strike_range,
    visible_side_opponent,
)
from pop2.enemy_profiles import (
    ENEMY_DATA, PROFILES, ADVANCE_CHANCE, BLOCK_CHANCE, PARRY_BLOCK_CHANCE,
    COUNTER_CHANCE, STRIKE_CHANCE, QuickDrawRandom,
)
from pop2.render_opening import load_resource_file
from tools.extract_enemy_profiles import expand_a5_data, extract
from pop2.sequence_runtime import SequenceRuntime, SequenceState
from pop2.terrain import LevelMap, Tile
from pop2.opponent_generation import character_column


class Rolls:
    def __init__(self, *values):
        self.values = iter(values)
        self.calls = []

    def randrange(self, stop):
        self.calls.append(stop)
        value = next(self.values)
        if not 0 <= value < stop:
            raise AssertionError("Test roll is outside the native range")
        return value


class EnemyDataTests(unittest.TestCase):
    def test_original_tables_are_associated_with_their_call_sites(self):
        self.assertEqual(ADVANCE_CHANCE, (255, 200, 200, 200, 255, 255, 200, 0, 0, 255, 100, 100))
        self.assertEqual(BLOCK_CHANCE, (0, 150, 150, 200, 200, 255, 200, 250, 0, 255, 255, 255))
        self.assertEqual(PARRY_BLOCK_CHANCE, (0, 75, 75, 100, 100, 145, 100, 250, 0, 145, 255, 175))
        self.assertEqual(COUNTER_CHANCE, (0, 0, 0, 5, 5, 175, 20, 10, 0, 255, 255, 150))
        self.assertEqual(STRIKE_CHANCE, (75, 100, 75, 75, 75, 50, 100, 220, 0, 60, 40, 60))
        self.assertEqual(PROFILES[0].hit_pause, 20)

    def test_each_profile_threshold_has_exactly_that_many_successful_rolls(self):
        for profile in PROFILES:
            for name in ("advance", "block", "parry_block", "counter", "strike"):
                threshold = getattr(profile, name)
                self.assertEqual(sum(roll < threshold for roll in range(256)), threshold)

    def test_all_level_generators_are_preserved_without_flattening_special_types(self):
        self.assertEqual(len(ENEMY_DATA["levels"]), 14)
        self.assertEqual(sum(len(l["generators"]) for l in ENEMY_DATA["levels"]), 86)
        self.assertEqual({g["skill"] for l in ENEMY_DATA["levels"]
                          for g in l["generators"]}, set(range(12)))
        cave = next(l for l in ENEMY_DATA["levels"] if l["resource_id"] == 2002)
        self.assertEqual({g["skill"] for g in cave["generators"]}, {0, 2, 3, 5})
        self.assertTrue(all(g["initial_actor_type"] == 4 for g in cave["generators"]))
        temple = next(l for l in ENEMY_DATA["levels"] if l["resource_id"] == 2011)
        special = next(g for g in temple["generators"] if g["room"] == 7)
        self.assertEqual((special["initial_actor_type"], special["initial_sequence"]), (10, 105))
        self.assertEqual({g["initial_actor_type"] for g in temple["generators"]}, {2, 10})
        self.assertTrue(all(len(g["raw_words"]) == 19 for l in ENEMY_DATA["levels"]
                            for g in l["generators"]))

    def test_export_is_reproducible_from_original_resources(self):
        recovery = os.environ.get("POP2_RESEARCH_DIR")
        if not recovery:
            self.skipTest("Set POP2_RESEARCH_DIR to validate against the original resource forks")
        program = Path(recovery) / "resource_forks" / "Prince of Persia 2.bin"
        prince = program.with_name("Prince.rsrc.bin")
        self.assertEqual(extract(program, prince), ENEMY_DATA)
        self.assertEqual(hashlib.sha256(program.read_bytes()).hexdigest(),
                         ENEMY_DATA["sources"]["program_sha256"])

    def test_zero_runs_expand_to_the_code_zero_allocation(self):
        resources = {"DATA": {0: {"data": b"\x12\x34\0\0\x56\x78"}},
                     "ZERO": {0: {"data": b"\0\4"}},
                     "CODE": {0: {"data": struct.pack(">II", 0, 10)}}}
        self.assertEqual(expand_a5_data(resources), b"\x12\x34" + bytes(6) + b"\x56\x78")
        resources["CODE"][0]["data"] = struct.pack(">II", 0, 8)
        with self.assertRaises(ValueError):
            expand_a5_data(resources)

    def test_quickdraw_seed_and_return_words_match_the_rom(self):
        rng = QuickDrawRandom(1)
        for seed in (16807, 282475249, 1622650073, 984943658, 1144108930):
            self.assertEqual(rng.randrange(65536), seed & 0xFFFF)
            self.assertEqual(rng.seed, seed)
        # Verify the ROM's exceptional -32768 return, not just the LCG formula.
        rng = QuickDrawRandom(pow(16807, -1, rng.MODULUS) * 32768 % rng.MODULUS)
        self.assertEqual(rng.randrange(65536), 0)
        self.assertEqual(rng.seed, 32768)

    def test_invalid_random_seed_is_not_silently_reinterpreted(self):
        for seed in (0, -1, 0x7FFFFFFF, 0xFFFFFFFF):
            with self.assertRaises(ValueError):
                QuickDrawRandom(seed)

    def test_seeded_native_rolls_are_reproducible_and_can_return_255(self):
        left, right = QuickDrawRandom(7), QuickDrawRandom(7)
        rolls = [left.randrange(256) for _ in range(4096)]
        self.assertEqual(rolls, [right.randrange(256) for _ in rolls])
        self.assertIn(255, rolls)


class GuardDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prince = load_resource_file("Prince.rsrc")
        cls.sequences = {i: sequence_words(r["data"]) for i, r in cls.prince["SEQS"].items()}
        cls.spawn = GuardSpawn.from_level(cls.prince["LEVL"][2000]["data"], 3)

    def encounter(self, skill=0, distance=81, rolls=(0,), action=171, player_action=171):
        runtime = SequenceRuntime(self.sequences, SequenceState(
            227, action=player_action, current_x=200 + distance - 21,
            target_x=200 + distance - 21, facing=0, actor_type=0,
            level_kind=5, animation_state=1))
        c = CombatEncounter(runtime, self.sequences, replace(self.spawn, skill=skill), 408, Rolls(*rolls))
        c.player.sword_drawn = c.guard.sword_drawn = True
        c.guard.alert_mode = 3
        select_sequence(c.guard, 227)
        c.guard.runtime.next_frame()
        c.guard.state.target_x = c.guard.state.current_x = 200
        c.guard.state.action = action
        return c

    def test_nearest_opponent_compares_height_difference_then_horizontal_distance(self):
        c = self.encounter()
        c.player.row = 1
        c.player.state.target_x = 200
        far = c.guard
        far.row = 1
        far.state.target_x = 80
        near = replace(far, runtime=SequenceRuntime(c.sequences, replace(far.state, target_x=199)))
        for dy, expected in ((79, near), (80, far), (81, far)):
            with self.subTest(dy=dy):
                near.state.current_y = dy
                self.assertIs(nearest_opponent(c.player, [far, near]), expected)
        # The exact-80 tie retains bank order, even when the first is higher.
        near.state.current_y = 80
        self.assertIs(nearest_opponent(c.player, [near, far]), near)
        near.row, near.state.current_y = 0, 120
        self.assertIs(nearest_opponent(c.player, [far, near]), near)

    def test_nearest_opponent_filters_dead_rooms_and_direction_but_not_row(self):
        c = self.encounter()
        c.player.state.target_x = 200
        left = c.guard
        left.state.target_x = 200
        right = replace(left, runtime=SequenceRuntime(c.sequences, replace(left.state, target_x=201)))
        self.assertIs(nearest_opponent(c.player, [right, left]), left)
        self.assertIs(nearest_opponent(c.player, [right, left], -1), left)
        self.assertIs(nearest_opponent(c.player, [right, left], 1), right)
        left.life = 0
        right.room += 1
        self.assertIsNone(nearest_opponent(c.player, [left, right]))
        right.room = c.player.room
        right.row += 1
        self.assertIs(nearest_opponent(c.player, [left, right]), right)

    def test_movement_buckets_include_pose44_but_not45(self):
        for pose in range(60):
            self.assertEqual(moving_fight_pose(pose),
                             1 <= pose <= 14 or 34 <= pose <= 44 or 49 <= pose <= 56)

    def test_side_room_visibility_uses_strict_original_position_boundaries(self):
        self.assertFalse(visible_side_opponent(378, 'left'))
        self.assertTrue(visible_side_opponent(379, 'left'))
        self.assertTrue(visible_side_opponent(123, 'right'))
        self.assertFalse(visible_side_opponent(124, 'right'))

    def runner(self, front=Tile(1), rear=Tile(1), facing=1, pose=195):
        c = self.encounter(distance=300, rolls=())
        c.level = self.prince['LEVL'][2000]['data']
        g = c.guard
        g.sword_drawn = False
        g.state.action, g.state.facing = pose, facing
        c.player.state.target_x = 200 + 300 * (1 if facing else -1)
        c.player.row = g.row
        column = character_column(g.state.target_x)
        step = 1 if facing else -1
        c.terrain = SimpleNamespace(tile=lambda _room, col, _row:
                                    front if col == column + step else rear)
        return c, g

    def test_runner_checks_live_front_obstacle_before_spacing(self):
        for tile, brakes in ((Tile(1), False), (Tile(0), True), (Tile(11), True),
                             (Tile(20), True), (Tile(4, 103), True), (Tile(4, 104), False)):
            for facing in (0, 1):
                with self.subTest(tile=tile, facing=facing):
                    c, g = self.runner(tile, facing=facing)
                    c._choose_unarmed_guard_action(g)
                    self.assertEqual(g.selected_sequence == 101, brakes)
                    if brakes:
                        self.assertEqual(g.alert_mode, 0)

    def test_jump_capable_runner_reaches_takeoff_but_not_through_low_gate(self):
        for flags in (0, 1, 2):
            for edge in (38, 39, 50):
                for tile in (Tile(0), Tile(20), Tile(4, 103)):
                    with self.subTest(flags=flags, edge=edge, tile=tile):
                        c, g = self.runner(tile)
                        g.generation_flags = flags
                        c._guard_front_edge_distance = lambda _guard: edge
                        c._choose_unarmed_guard_action(g)
                        self.assertEqual(g.selected_sequence == 101,
                                         not (flags >= 1 and edge >= 39 and tile.kind != 4))

    def test_alternate_floor_skips_spacing_but_not_passing_death_or_special13(self):
        for condition in ('close', 'passed', 'dead', 'special13'):
            with self.subTest(condition=condition):
                c, g = self.runner()
                c.player.row = g.alternate_row = 0
                c.player.state.target_x = 230 if condition != 'passed' else 100
                if condition == 'dead':
                    c.player.life = 0
                elif condition == 'special13':
                    c.player.state.sequence_mode = 13
                c._choose_unarmed_guard_action(g)
                self.assertEqual(g.selected_sequence == 101, condition != 'close')
                if condition != 'close':
                    self.assertEqual(g.alert_mode, 2 if condition == 'passed' else 0)

    def test_seqs232_minus21_13_reaches_the_special13_brake_and_ambient(self):
        # SEQS:232 word 12 is -21 13: AnimChar 4:2f92 writes the same word
        # (a5-0x5022) that the guard brake and OppToFight 6:23b2 test for 13.
        c, g = self.runner()
        c.player.row = g.alternate_row = 0
        c.player.state.target_x = 230
        state = c.player.state
        state.sequence_id, state.cursor = 232, 12
        SequenceRuntime(self.sequences, state).next_frame()
        self.assertEqual(state.sequence_mode, 13)
        self.assertFalse(c.opponent_to_fight())
        c._choose_unarmed_guard_action(g)
        self.assertEqual((g.selected_sequence, g.alert_mode), (101, 0))

    def test_final_jump_brake_moves_forward12_only_when_rear_cannot_support(self):
        for facing in (0, 1):
            for pose in (195, 212):
                for rear in (Tile(0), Tile(1), Tile(4, 103), Tile(4, 104)):
                    with self.subTest(facing=facing, pose=pose, rear=rear):
                        c, g = self.runner(Tile(4, 103), rear, facing, pose)
                        c._choose_unarmed_guard_action(g)
                        shift = (12 if facing else -12) if pose == 212 and rear in (
                            Tile(0), Tile(4, 103)) else 0
                        self.assertEqual(g.selected_sequence, 101)
                        self.assertEqual((g.state.target_x, g.state.current_x), (200 + shift,) * 2)

    def test_skeleton_resume_uses_its_native_run_sequence(self):
        for actor_type, sequence in ((2, 84), (4, 102)):
            c = self.encounter()
            c.guard.state.actor_type = actor_type
            c._resume_guard_run(c.guard)
            self.assertEqual((c.guard.selected_sequence, c.guard.sword_drawn,
                              c.guard.alert_mode), (sequence, False, 0))
            select_sequence(c.guard, 227)
            c.guard.alert_mode = 1
            c._resume_guard_run(c.guard)
            self.assertEqual(c.guard.selected_sequence, 227)

    def test_unarmed_standing_turn_requires_engagement_and_preserves_sheathing(self):
        for alert in range(4):
            for selected in (77, 101):
                for distance in (-28, -27, -1, 0, 663, 664):
                    with self.subTest(alert=alert, selected=selected, distance=distance):
                        c, g = self.runner()
                        g.state.action = 166
                        g.selected_sequence = selected
                        g.alert_mode = alert
                        c.player.state.facing = g.state.facing
                        c.player.state.target_x = 200 + distance
                        c._choose_unarmed_guard_action(g)
                        if -27 <= distance < 0 and alert >= 2:
                            expected = 90
                        elif distance < -27 and alert == 3 and selected != 77:
                            expected = 80
                        elif 0 <= distance <= 663 and alert:
                            expected = 90
                        else:
                            expected = selected
                        self.assertEqual(g.selected_sequence, expected)

    def test_standing_guard_does_not_draw_or_turn_toward_dead_prince(self):
        for distance in (-40, -10, 50):
            c, g = self.runner()
            g.state.action = 166
            c.player.state.target_x = 200 + distance
            c.player.life = 0
            c._choose_unarmed_guard_action(g)
            self.assertEqual(g.selected_sequence, 227)
            self.assertFalse(g.sword_drawn)

    def test_unarmed_draw_has_native_eight_pixel_unsafe_rear_correction(self):
        for facing in (0, 1):
            for rear in (Tile(0), Tile(1), Tile(4, 103), Tile(4, 104)):
                with self.subTest(facing=facing, rear=rear):
                    c, g = self.runner(rear=rear, facing=facing)
                    g.state.action = 166
                    c.player.state.facing = facing
                    c._choose_unarmed_guard_action(g)
                    shift = (8 if facing else -8) if rear in (Tile(0), Tile(4, 103)) else 0
                    self.assertEqual((g.selected_sequence, g.sword_drawn), (90, True))
                    self.assertEqual((g.state.target_x, g.state.current_x), (200 + shift,) * 2)

    def test_step_noise_turns_waiting_guard_but_does_not_override_close_draw(self):
        for distance, expected in ((-40, 80), (-27, 90), (-6, 90), (100, 227)):
            c, g = self.runner()
            g.state.action, g.alert_mode = 166, 2
            c.player.state.facing = g.state.facing
            c.player.state.target_x = 200 + distance
            c.player.state.callback_flag = 1
            c._choose_unarmed_guard_action(g)
            self.assertEqual(g.selected_sequence, expected, distance)
        c, g = self.runner()
        g.state.action = 166
        c.player.state.callback_flag = 1
        c.choose_guard_action(g)
        self.assertEqual(c.player.state.callback_flag, 0)
        c.choose_guard_action(g)
        self.assertEqual(g.selected_sequence, 90)

    def test_drawing_reserves18_pixels_after_native_rear_correction(self):
        for facing in (0, 1):
            for clearance in (0, 1, 17, 18, 42):
                with self.subTest(facing=facing, clearance=clearance):
                    c, g = self.runner(facing=facing)
                    g.state.action = 166
                    c.guard_art = SimpleNamespace(frames=[None] * 256,
                                                  bounds=lambda *_args: (0, 0, 0, 0))
                    c.terrain.step_boundary = lambda *_args: SimpleNamespace(clearance=clearance)
                    c._choose_unarmed_guard_action(g)
                    shift = (clearance - 18) * (1 if facing else -1) if 0 < clearance < 18 else 0
                    self.assertEqual((g.state.target_x, g.state.current_x), (200 + shift,) * 2)
                    self.assertEqual(g.selected_sequence, 90)

    def test_native_advancable_gate_boundary_and_actor_exceptions(self):
        for actor in (2, 4, 7, 8, 10):
            for foreground in (0, 103, 104, 255, 0x200 | 103, 0x200 | 104):
                with self.subTest(actor=actor, foreground=foreground):
                    self.assertEqual(advancable_tile(Tile(4, foreground), actor),
                                     foreground & 255 >= 104)
            self.assertFalse(advancable_tile(Tile(20), actor))
            self.assertTrue(advancable_tile(Tile(23), actor))
            self.assertEqual(advancable_tile(Tile(11), actor), actor == 10)
            self.assertEqual(advancable_tile(Tile(0), actor), actor in (7, 8, 10))

    def test_close_steps_read_current_gate_state_in_both_directions(self):
        for facing in (0, 1):
            for source in (227, 57):
                for opening in (103, 104):
                    with self.subTest(facing=facing, source=source, opening=opening):
                        c = self.encounter(distance=20, rolls=())
                        c.level = self.prince['LEVL'][2000]['data']
                        c.guard.state.facing = facing
                        c.guard.state.selected_sequence_id = source
                        c.player.state.facing = 1 - facing
                        c.player.state.target_x = 200 + (20 if facing else -20)
                        c.terrain = SimpleNamespace(tile=lambda *_: Tile(4, 0x200 | opening))
                        intent = c.decide_guard_intent()
                        self.assertEqual(intent, GuardIntent(
                            advance=opening == 104 and source == 227,
                            retreat=opening == 104 and source == 57))
                        self.assertEqual(c.rng.calls, [])

    def test_alert_changes_with_gate_height_and_dynamic_floor(self):
        for kind, foreground, expected in ((4, 103, 1), (4, 104, 3),
                                           (0, 0, 1), (20, 0, 0)):
            with self.subTest(kind=kind, foreground=foreground):
                c = self.encounter(distance=160, rolls=())
                c.level = self.prince['LEVL'][2000]['data']
                column = character_column(c.guard.state.target_x) + 1
                c.terrain = LevelMap(c.level)
                c.terrain.tile = lambda _room, col, _row: (
                    Tile(kind, foreground) if col == column else Tile(1))
                c.update_guard_alerts()
                self.assertEqual(c.guard.alert_mode, expected)
                self.assertEqual(c.rng.calls, [])

    def test_raw_level_gate_modifier_is_used_without_a_live_map(self):
        c = self.encounter(rolls=())
        level = bytearray(self.prince['LEVL'][2000]['data'])
        room, row = c.guard.room, c.guard.row
        column = character_column(c.guard.state.target_x) + 1
        struct.pack_into('>H', level, room * 60 + (row * 10 + column) * 2, 4)
        c.level = bytes(level)
        self.assertFalse(c._guard_floor_clear(c.guard, 1, 1))
        struct.pack_into('>H', level, 0x780 + room * 120 + (row * 10 + column) * 4, 104)
        c.level = bytes(level)
        self.assertTrue(c._guard_floor_clear(c.guard, 1, 1))
        self.assertEqual(LevelMap(c.level).tile(room, column, row).foreground, 104)

    def test_nearest_waiting_guard_retreats_from_obstacles_with_safe_rear(self):
        for facing in (0, 1):
            for distance in (50, 51):
                for front, rear, retreat in ((Tile(0), Tile(1), True),
                                              (Tile(11), Tile(1), True),
                                              (Tile(23), Tile(1), True),
                                              (Tile(4, 103), Tile(1), True),
                                              (Tile(4, 104), Tile(1), False),
                                              (Tile(20), Tile(1), False),
                                              (Tile(0), Tile(0), False),
                                              (Tile(0), Tile(4, 103), False),
                                              (Tile(0), Tile(4, 104), True)):
                    with self.subTest(facing=facing, distance=distance, front=front, rear=rear):
                        c = self.encounter(distance=distance, rolls=())
                        c.level = self.prince['LEVL'][2000]['data']
                        c.guard.state.facing = facing
                        c.guard.alert_mode = 1
                        c.player.state.target_x = 200 + (distance if facing else -distance)
                        direction = 1 if facing else -1
                        column = character_column(200)
                        query = column + direction * (1 if distance < 51 else 2)
                        c.terrain = SimpleNamespace(tile=lambda _r, col, _y: (
                            front if col == query else rear))
                        c.choose_guard_action()
                        self.assertEqual(c.guard.selected_sequence, 57 if retreat else 227)
                        self.assertEqual(c.rng.calls, [])

    def test_random_roll_includes_the_upper_bound(self):
        for roll, advances in ((254, True), (255, False)):
            c = self.encounter(distance=140, rolls=(roll,))
            self.assertEqual(c.decide_guard_intent(), GuardIntent(advance=advances))
            self.assertEqual(c.rng.calls, [256])

    def test_first_guard_strikes_at_75_not_255(self):
        for roll, strikes in ((74, True), (75, False), (255, False)):
            c = self.encounter(rolls=(roll,))
            self.assertEqual(c.decide_guard_intent(), GuardIntent(strike=strikes))

    def test_profile_zero_advances_during_player_attack_pause(self):
        for skill, expected in ((0, GuardIntent(advance=True)), (1, GuardIntent())):
            c = self.encounter(skill=skill, distance=140, rolls=(0,))
            c.notify_player_sequence(75)
            self.assertEqual(c.advance_pause, 15)
            self.assertEqual(c.decide_guard_intent(), expected)
            self.assertEqual(c.rng.calls, [256] if skill == 0 else [])

    def test_counterattack_notifies_the_same_advance_pause_as_normal_attack(self):
        c = self.encounter()
        c.notify_player_sequence(66)
        self.assertEqual(c.advance_pause, 15)
        c.notify_player_sequence(62)
        self.assertEqual(c.advance_pause, 15)

    def test_far_and_near_out_of_range_use_original_advance_table(self):
        for distance in (99, 116, 117, 180):
            c = self.encounter(distance=distance, rolls=(255,))
            self.assertEqual(c.decide_guard_intent(), GuardIntent())
            self.assertEqual(c.rng.calls, [256])

    def test_unarmed_in_range_strike_does_not_consume_random_roll(self):
        for distance, strikes in ((35, True), (98, True), (99, False)):
            c = self.encounter(distance=distance, rolls=())
            c.player.sword_drawn = False
            self.assertEqual(c.decide_guard_intent(),
                             GuardIntent(strike=strikes, advance=not strikes))
            self.assertEqual(c.rng.calls, [])

    def test_far_run_and_jump_trigger_anticipating_attack(self):
        for action, distance in ((7, 149), (14, 149), (34, 185), (43, 185)):
            c = self.encounter(distance=distance, player_action=action, rolls=())
            self.assertEqual(c.decide_guard_intent(), GuardIntent(strike=True))
            self.assertEqual(c.rng.calls, [])
        for action, distance in ((7, 150), (14, 150), (34, 186), (43, 186)):
            c = self.encounter(distance=distance, player_action=action, rolls=())
            self.assertEqual(c.decide_guard_intent(), GuardIntent())
            self.assertEqual(c.rng.calls, [])

    def test_anticipating_attack_requires_opposed_facing(self):
        c = self.encounter(distance=149, player_action=7, rolls=(0,))
        c.player.state.facing = c.guard.state.facing
        self.assertEqual(c.decide_guard_intent(), GuardIntent(advance=True))

    def test_recovery_pose_wait_has_no_rng_call(self):
        c = self.encounter(distance=140, player_action=103, rolls=())
        c.player.state.animation_state = 5
        self.assertEqual(c.decide_guard_intent(), GuardIntent())
        self.assertEqual(c.rng.calls, [])

    def test_too_close_only_requests_retreat_at_native_ready_pose(self):
        for action in (158, 170, 171, 165):
            c = self.encounter(distance=60, action=action, rolls=())
            self.assertEqual(c.decide_guard_intent(), GuardIntent(retreat=action == 171))
            self.assertEqual(c.rng.calls, [])

    def test_too_close_native_front_and_back_cell_checks_prevent_voluntary_edge_fall(self):
        c = self.encounter(distance=20, rolls=())
        c.level = self.prince["LEVL"][2000]["data"]
        c.guard.room = c.player.room = 0
        c.guard.row = c.player.row = 1
        # Both roof edges: the guard has a gap behind, but floor in front.
        for facing, x in ((0, 170), (1, 332)):
            for sequence in (227, 57):
                with self.subTest(facing=facing, sequence=sequence):
                    state = c.guard.state
                    state.action, state.facing = 171, facing
                    state.sequence_id, state.selected_sequence_id = 227, sequence
                    state.current_x = state.target_x = x
                    c.player.state.facing = 1 - facing
                    c.player.state.target_x = x + (20 if facing else -20)
                    expected = GuardIntent(advance=True) if sequence != 57 else GuardIntent()
                    self.assertEqual(c.decide_guard_intent(), expected)
        self.assertEqual(c.rng.calls, [])

    def test_retreat_continuation_keeps_the_native_close_spacing_decision(self):
        for source in (57, 104):
            for facing in (0, 1):
                with self.subTest(source=source, facing=facing):
                    c = self.encounter(rolls=())
                    c.level = self.prince["LEVL"][2000]["data"]
                    state = c.guard.state
                    state.facing = facing
                    state.current_x = state.target_x = 300
                    state.selected_sequence_id = source
                    c.player.state.facing = 1 - facing
                    c.player.state.target_x = 300 + (19 if facing else -19)
                    self.assertEqual(c.decide_guard_intent(), GuardIntent(retreat=True))
                    self.assertEqual(c.rng.calls, [])

    def test_post_turn_spacing_uses_native_edge_and_distance_boundaries(self):
        for edge in (25, 26):
            for distance in (43, 44):
                for rear_cells in (1, 2):
                    with self.subTest(edge=edge, distance=distance, rear_cells=rear_cells):
                        c = self.encounter(distance=distance, rolls=())
                        c.level = self.prince["LEVL"][2000]["data"]
                        c.guard.state.selected_sequence_id = 60
                        clear = lambda guard, direction, count: direction == 1 or count <= rear_cells
                        with patch.object(c, "_guard_floor_clear", side_effect=clear), \
                                patch.object(c, "_guard_front_edge_distance", return_value=edge):
                            retreat = edge <= 25 or 61 - distance <= 17 or rear_cells == 2
                            self.assertEqual(c.decide_guard_intent(),
                                             GuardIntent(retreat=retreat, advance=not retreat))
                        self.assertEqual(c.rng.calls, [])

    def test_post_turn_does_not_retreat_into_a_gap_or_away_from_a_zero_distance_target(self):
        for distance, rear_clear, front_clear in ((40, False, True), (0, True, True),
                                                   (40, False, False)):
            with self.subTest(distance=distance, rear_clear=rear_clear, front_clear=front_clear):
                c = self.encounter(rolls=())
                c.level = self.prince["LEVL"][2000]["data"]
                c.guard.state.selected_sequence_id = 60
                c.player.state.facing = c.guard.state.facing
                c.player.state.target_x = c.guard.state.target_x + distance
                clear = lambda guard, direction, count: front_clear if direction == 1 else rear_clear
                with patch.object(c, "_guard_floor_clear", side_effect=clear):
                    self.assertEqual(c.decide_guard_intent(), GuardIntent(advance=front_clear))
                self.assertEqual(c.rng.calls, [])

    def test_guard_turn_uses_animation_mode_not_only_the_ready_pose(self):
        for action in (150, 158, 160, 165, 170, 171):
            for mode in (0, 1, 2, 4, 5, 8):
                with self.subTest(action=action, mode=mode):
                    c = self.encounter(action=action, rolls=())
                    c.player.state.target_x = c.guard.state.target_x - 16
                    c.guard.state.animation_state = mode
                    c.choose_guard_action()
                    self.assertEqual(c.guard.state.source_sequence_id, 60 if mode < 2 else 227)
                    self.assertEqual(c.rng.calls, [])

    def test_too_close_retreat_is_still_possible_when_there_is_floor_behind(self):
        c = self.encounter(distance=20, rolls=())
        c.level = self.prince["LEVL"][2000]["data"]
        c.guard.room = c.player.room = 0
        c.guard.row = c.player.row = 1
        for facing, x in ((1, 170), (0, 332)):
            with self.subTest(facing=facing):
                state = c.guard.state
                state.action, state.facing, state.sequence_id = 171, facing, 227
                state.current_x = state.target_x = x
                c.player.state.facing = 1 - facing
                c.player.state.target_x = x + (20 if facing else -20)
                self.assertEqual(c.decide_guard_intent(), GuardIntent(retreat=True))

    def test_defence_and_strike_rolls_both_happen_in_original_order(self):
        c = self.encounter(skill=1, distance=70, player_action=152, rolls=(149, 99))
        intent = c.decide_guard_intent()
        self.assertEqual(intent, GuardIntent(block=True, strike=True))
        self.assertEqual(c.rng.calls, [256, 256])
        c.apply_guard_intent(intent)
        self.assertEqual(c.guard.state.sequence_id, 58)

    def test_failed_attack_gate_does_not_fall_back_to_block(self):
        c = self.encounter(skill=1, distance=70, player_action=152, action=168, rolls=(0, 0))
        c.apply_guard_intent(c.decide_guard_intent())
        self.assertEqual(c.guard.state.sequence_id, 227)

    def test_parry_window_uses_the_separate_reblock_table(self):
        c = self.encounter(skill=1, distance=70, player_action=152, rolls=(75, 255))
        self.assertTrue(c.decide_guard_intent().block)
        c.rng = Rolls(75, 255)
        c.parry_timer = 4
        self.assertFalse(c.decide_guard_intent().block)

    def test_npc_block_selects_retreat_or_close_block_using_74_boundary(self):
        for distance, sequence in ((73, 246), (74, 57), (81, 57)):
            c = self.encounter(skill=1, distance=distance, player_action=152, rolls=(0, 255))
            c.choose_guard_action()
            self.assertEqual(c.guard.state.sequence_id, sequence)

    def test_late_defence_pose_does_not_invent_a_close_block(self):
        for action in (153, 162):
            c = self.encounter(skill=1, distance=70, player_action=action, rolls=(0, 255))
            c.choose_guard_action()
            self.assertEqual(c.guard.state.sequence_id, 227)

    def test_counter_requires_the_actual_counter_profile(self):
        for skill, sequence in ((1, 227), (5, 66)):
            c = self.encounter(skill=skill, action=150, rolls=(0,))
            c.choose_guard_action()
            self.assertEqual(c.guard.state.sequence_id, sequence)
        c = self.encounter(skill=5, action=161, rolls=(255,))
        c.choose_guard_action()
        self.assertEqual(c.guard.state.sequence_id, 57)

    def test_attack_can_chain_at_last_step_pose_not_only_idle_resource(self):
        for sequence, action in ((86, 165), (57, 157)):
            c = self.encounter(rolls=(0,))
            select_sequence(c.guard, sequence)
            c.guard.state.action = action
            c.choose_guard_action()
            self.assertEqual(c.guard.state.sequence_id, 58)

    def test_defence_can_recover_from_a_blocked_attack(self):
        c = self.encounter(skill=5, distance=70, player_action=152, action=167, rolls=(0, 255))
        c.choose_guard_action()
        self.assertEqual(c.guard.state.sequence_id, 61)

    def test_enemy_block_preparation_suppresses_strike_rng(self):
        for action in (169, 151):
            c = self.encounter(player_action=action, rolls=())
            self.assertEqual(c.decide_guard_intent(), GuardIntent())
            self.assertEqual(c.rng.calls, [])

    def test_hit_pause_prevents_attacks_but_does_not_disable_defence(self):
        c = self.encounter(skill=1, distance=70, player_action=152, rolls=(0,))
        c.attack_pause = 20
        c.choose_guard_action()
        self.assertEqual(c.guard.state.sequence_id, 246)
        self.assertEqual(c.rng.calls, [256])

    def test_far_hit_pause_suppresses_both_pursuit_and_anticipating_attack(self):
        for action in (7, 171):
            c = self.encounter(distance=140, player_action=action, rolls=())
            c.attack_pause = 20
            self.assertEqual(c.decide_guard_intent(), GuardIntent())
            self.assertEqual(c.rng.calls, [])

    def test_unavailable_and_multi_guard_waiting_targets_are_not_invented(self):
        for field, value in (("alert_mode", 1), ("alert_mode", 2),
                             ("life", 0)):
            c = self.encounter(rolls=())
            setattr(c.guard, field, value)
            c.choose_guard_action()
            self.assertEqual(c.guard.state.sequence_id, 227)
            self.assertEqual(c.rng.calls, [])

    def test_contact_protection_does_not_disable_native_guard_decisions(self):
        for distance, expected in ((65, 58), (140, 86)):
            with self.subTest(distance=distance):
                c = self.encounter(distance=distance, player_action=15, rolls=(0,))
                c.player.sword_drawn = False
                c.player.targetable = False
                c.choose_guard_action()
                self.assertEqual(c.guard.state.sequence_id, expected)

    def test_opening_fall_and_landing_use_native_pose_gate_not_contact_protection(self):
        for action, mode, expected in ((43, 1, 86), (103, 3, 86), (106, 4, 86),
                                       (107, 5, 227), (109, 1, 86), (116, 5, 227),
                                       (117, 1, 86), (118, 1, 86)):
            with self.subTest(action=action):
                c = self.encounter(distance=200, player_action=action, rolls=(0,))
                c.player.state.facing = c.guard.state.facing
                c.player.state.animation_state = mode
                c.player.sword_drawn = False
                c.player.targetable = False
                c.choose_guard_action()
                self.assertEqual(c.guard.state.sequence_id, expected)

    def test_guard_hurt_lock_does_not_extend_past_native_interruptible_modes(self):
        for mode, expected in ((0, 58), (1, 58), (2, 183), (5, 183)):
            with self.subTest(mode=mode):
                c = self.encounter(action=165, rolls=(0,))
                c.guard.recovering = True
                select_sequence(c.guard, 183)
                c.guard.state.animation_state = mode
                c.choose_guard_action()
                self.assertEqual(c.guard.state.sequence_id, expected)

    def test_guard_can_attack_unarmed_jump_hang_and_climb_poses(self):
        for action, mode in ((22, 2), (87, 6), (135, 1)):
            c = self.encounter(distance=65, player_action=action, rolls=())
            c.player.sword_drawn = False
            c.player.state.animation_state = mode
            c.choose_guard_action()
            self.assertEqual(c.guard.state.sequence_id, 58)
            self.assertEqual(c.rng.calls, [])

    def test_sheathing_and_damage_set_distinct_source_timers(self):
        c = self.encounter(rolls=())
        c.notify_player_sequence(92)
        self.assertEqual(c.attack_pause, 9)
        c.player.state.action = 154
        c.resolve_contacts()
        self.assertEqual(c.attack_pause, PROFILES[0].hit_pause)
        c.reset()
        self.assertEqual((c.parry_timer, c.advance_pause, c.attack_pause), (0, 0, 0))

    def test_timers_advance_on_ai_tick_not_extra_key_callbacks(self):
        c = self.encounter(distance=140, rolls=(0, 0))
        c.parry_timer, c.advance_pause, c.attack_pause = 4, 15, 9
        c.step(0, 0.1)
        self.assertEqual((c.parry_timer, c.advance_pause, c.attack_pause), (3, 14, 8))
        for t in (0.01, 0.03, 0.07):
            c.step(t, 0.1)
        self.assertEqual((c.parry_timer, c.advance_pause, c.attack_pause), (3, 14, 8))

    def test_shared_timers_decrement_before_each_npc_not_once_per_world_frame(self):
        c = self.encounter(rolls=())
        for life in (3, 0):
            runtime = SequenceRuntime(c.sequences, replace(c.guard.state))
            c.guards.append(replace(c.guard, runtime=runtime, life=life))
        c.parry_timer, c.advance_pause, c.attack_pause = 4, 15, 20
        observed = []
        with patch.object(c, "choose_guard_action", side_effect=lambda guard:
                          observed.append((c.parry_timer, c.advance_pause, c.attack_pause))):
            c.step(0, 0.1)
            for t in (0.01, 0.03, 0.07):
                c.step(t, 0.1)
        self.assertEqual(observed, [(3, 14, 19), (2, 13, 18), (1, 12, 17)])
        self.assertEqual(c.world_frame, 1)

    def test_attack_pause_can_expire_for_a_later_guard_in_the_same_frame(self):
        c = self.encounter(rolls=(0,))
        second = replace(c.guard, runtime=SequenceRuntime(c.sequences, replace(c.guard.state)))
        c.guards.append(second)
        c.attack_pause = 2
        c.advance_guard()
        self.assertEqual(c.guard.state.source_sequence_id, 227)
        self.assertEqual(second.state.source_sequence_id, 58)
        self.assertEqual(c.rng.calls, [256])
        self.assertEqual(c.attack_pause, 0)

    def test_shared_timers_do_not_underflow_or_advance_without_processed_npcs(self):
        c = self.encounter(rolls=())
        c.guard.life = 0
        c.parry_timer, c.advance_pause, c.attack_pause = 1, 0, 2
        c.advance_guard()
        c.advance_guard()
        c.advance_guard()
        self.assertEqual((c.parry_timer, c.advance_pause, c.attack_pause), (0, 0, 0))
        c.guards.clear()
        c.attack_pause = 9
        c.advance_guard()
        self.assertEqual(c.attack_pause, 9)

    def test_fallen_npcs_only_tick_shared_timers_if_they_have_a_lower_room(self):
        from pop2.terrain import floor_y

        for y, lower_room, expected in ((484, None, 8), (485, None, 9), (485, 6, 8)):
            with self.subTest(y=y, lower_room=lower_room):
                c = self.encounter(rolls=())
                c.guard.state.current_y = y - floor_y(c.guard.row)
                c.guard.life = 0
                c.terrain = SimpleNamespace(neighbor=lambda room, direction: lower_room)
                c.attack_pause = 9
                with patch.object(c, "active_guards", return_value=[c.guard]):
                    c.advance_guard()
                self.assertEqual(c.attack_pause, expected)

    def test_turn_and_hurt_phases_cannot_be_replaced_by_attack_input(self):
        for mode in (2, 4, 5, 8, 9, 10):
            c = self.encounter()
            c.guard.state.animation_state = mode
            c.apply_guard_intent(GuardIntent(strike=True))
            self.assertEqual(c.guard.state.sequence_id, 227)

    def test_player_strike_range_uses_engagement_not_sword_flag(self):
        c = self.encounter()
        for armed in (False, True):
            c.guard.sword_drawn = armed
            c.guard.alert_mode = 3
            self.assertEqual(strike_range(c.player, c.guard), (61, 99))
            c.guard.alert_mode = 0
            self.assertEqual(strike_range(c.player, c.guard), (83, 121))


if __name__ == "__main__":
    unittest.main()
