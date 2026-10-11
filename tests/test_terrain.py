import random
import struct
import tkinter as tk
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops, ImageOps, ImageTk

from pop2.animation_data import parse_frame_records, sequence_words
from pop2.combat import GuardSpawn, opponent_distance
from pop2.mac_input import StepBoundary
from pop2.render_opening import build_opening_room, load_resource_file
from pop2.scene_prototype import BufferedCommand, ScenePrototype
from pop2.sequence_runtime import SequenceRuntime, SequenceState
from pop2.terrain import (LevelMap, RooftopPhysics, TerrainMotion, character_column,
                     character_row, floor_y, floor_contact_x)


class TerrainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prince = load_resource_file("Prince.rsrc")
        cls.level = prince["LEVL"][2000]["data"]
        cls.map = LevelMap(cls.level)
        cls.sequences = {key: sequence_words(value["data"])
                         for key, value in prince["SEQS"].items()}
        cls.frames = parse_frame_records(load_resource_file("Kid.rsrc")["FRAM"][25001]["data"])

    def runtime(self, sequence=2, x=450, facing=1):
        runtime = SequenceRuntime(self.sequences, SequenceState(
            sequence, current_x=x, target_x=x, facing=facing, actor_type=0, level_kind=5))
        runtime.next_frame()
        return runtime

    def test_original_links_and_neighbor_tiles(self):
        self.assertEqual(self.map.neighbor(3, "left"), 1)
        self.assertEqual(self.map.neighbor(1, "right"), 3)
        self.assertEqual(self.map.neighbor(1, "left"), 2)
        self.assertIsNone(self.map.neighbor(3, "down"))
        self.assertEqual(self.map.tile(3, -1, 1), self.map.tile(1, 9, 1))
        self.assertEqual(self.map.tile(3, 10, 1), self.map.tile(4, 0, 1))
        self.assertIsNone(self.map.tile(3, 8, 3).room)

    def test_source_floor_and_row_coordinates(self):
        self.assertEqual([floor_y(i) for i in range(3)], [106, 226, 346])
        self.assertEqual([character_row(y) for y in (5, 6, 124, 125, 226, 365)],
                         [-1, 0, 0, 1, 1, 3])

    def test_undefined_rooftop_cells_are_air_not_supporting_walls(self):
        for room, column, row in ((18, -1, 2), (3, 8, 3), (18, -1, 0)):
            with self.subTest(room=room, column=column, row=row):
                tile = self.map.tile(room, column, row)
                self.assertIsNone(tile.room)
                self.assertEqual(tile.kind, 0)
                self.assertFalse(self.map.supports(room, column, row))

    def test_wall_hang_mode_six_skips_ordinary_wall_reselection_but_not_gate(self):
        from pop2.terrain import Tile

        for mode in (2, 6):
            for kind in (20, 4, 0):
                for facing in (0, 1):
                    with self.subTest(mode=mode, kind=kind, facing=facing):
                        state = SequenceState(25, action=92, animation_state=mode,
                                              target_x=427, facing=facing)
                        with patch.object(self.map, "tile", return_value=Tile(kind)):
                            self.assertEqual(self.map.wall_supported_hang(
                                3, 2, state, self.frames[92]),
                                (kind == 20 and mode != 6) or (kind == 4 and not facing))

    def test_contact_foot_depends_on_pose_and_facing(self):
        self.assertEqual(floor_contact_x(323, 0, self.frames[38]), 339)
        self.assertEqual(floor_contact_x(323, 1, self.frames[38]), 307)
        self.assertEqual(floor_contact_x(160, 0, self.frames[44]), 174)

    def test_fatal_hit_fall_uses_space_behind_and_six_pixel_threshold_both_sides(self):
        from dataclasses import replace
        from pop2.terrain import Tile

        record = replace(self.frames[171], offset_x=0, aux=0)
        for facing in (0, 1):
            for room in (0, 3, 9):
                for current, behind, distance, expected in (
                        (1, 1, 20, None), (1, 20, 20, None), (1, 0, 5, None),
                        (1, 0, 6, -57), (1, 0, 20, -43), (0, 1, 20, 8)):
                    with self.subTest(facing=facing, room=room, current=current,
                                      behind=behind, distance=distance):
                        x = 227 + (50 - distance if facing else distance)
                        state = SequenceState(227, action=171, target_x=x, facing=facing)
                        column = character_column(x)
                        with patch.object(self.map, "tile", side_effect=lambda r, c, y:
                                          Tile(current if c == column else behind)):
                            self.assertEqual(self.map.fatal_hit_fall_offset(
                                room, 1, state, record), expected)

    def test_fatal_hit_fall_preserves_native_special_actor_exclusions(self):
        from pop2.terrain import Tile

        with patch.object(self.map, "tile", return_value=Tile(0)):
            for actor_type in (6, 7, 8, 11):
                state = SequenceState(227, action=171, target_x=250, actor_type=actor_type)
                self.assertIsNone(self.map.fatal_hit_fall_offset(3, 1, state, self.frames[171]))

    def test_fatal_guard_hit_checks_cached_column_after_the_predeath_displacement(self):
        from pop2.combat import guard_frame_index

        frames = parse_frame_records(load_resource_file("Guard.rsrc")["FRAM"][750]["data"])
        record = frames[guard_frame_index(170)]
        state = SequenceState(227, action=170, target_x=145, facing=0, actor_type=2)
        column = character_column(floor_contact_x(state.target_x, state.facing, record))
        self.assertEqual(self.map.fatal_hit_fall_offset(0, 1, state, record), -18)
        state.target_x += 10
        self.assertIsNone(self.map.fatal_hit_fall_offset(0, 1, state, record, column))

    def test_shift_clearance_uses_links_not_screen_edges(self):
        self.assertGreaterEqual(self.map.step_clearance(3, 1, 25, -1), 42)
        self.assertEqual(self.map.step_clearance(3, 1, 395, 1), 13)
        self.assertGreaterEqual(self.map.step_clearance(1, 1, 490, 1), 42)

    def test_running_jump_uses_native_takeoff_alignment_and_late_rejection(self):
        for room, facing, x, offset in ((2, 0, 400, 0), (2, 0, 331, -5),
                                        (2, 0, 340, -14), (2, 0, 308, 18), (2, 0, 307, None),
                                        (0, 1, 125, 2), (0, 1, 140, -13),
                                        (0, 1, 145, -18), (0, 1, 146, None)):
            with self.subTest(room=room, facing=facing, x=x):
                state = SequenceState(202, action=9, target_x=x, facing=facing, actor_type=0)
                self.assertEqual(self.map.run_jump_offset(room, 1, state), offset)

    def test_run_jump_tile_predicate_matches_is_advancable_id(self):
        for kind, fg, allowed in ((1, 0, True), (11, 0, True), (23, 0, True), (24, 0, True),
                                  (4, 104, True), (4, 103, False), (0, 0, False),
                                  (12, 0, False), (13, 0, False), (15, 0, False),
                                  (20, 0, False), (26, 0, False)):
            with self.subTest(kind=kind, fg=fg):
                level = bytearray(self.level)
                tile = 16  # First forward tile from x=400, facing left, in native room 3.
                struct.pack_into(">H", level, 2 * 60 + tile * 2, kind)
                struct.pack_into(">H", level, 0x780 + 2 * 120 + tile * 4, fg)
                state = SequenceState(202, action=9, target_x=400, facing=0, actor_type=0)
                self.assertEqual(LevelMap(level).run_jump_offset(2, 1, state),
                                 0 if allowed else None)

    def test_player_step_measures_the_original_support_foot(self):
        for x, distance in ((395, 37), (411, 21), (428, 4)):
            with self.subTest(x=x):
                state = self.runtime(x=x).state
                boundary = self.map.step_boundary(3, 1, state, self.frames[15],
                                                 (x - 15, 147, x + 4, 226))
                self.assertEqual(boundary, StepBoundary(distance, 0, 0))

    def test_player_step_clear_floor_and_linked_floor_use_native_default(self):
        for room, x, facing in ((3, 250, 1), (3, 25, 0), (1, 490, 1)):
            with self.subTest(room=room, x=x):
                state = self.runtime(x=x, facing=facing).state
                boundary = self.map.step_boundary(room, 1, state, self.frames[15],
                                                 (x - 15, 147, x + 4, 226))
                self.assertEqual(boundary, StepBoundary(42, 2, 1))

    def test_step_uses_source_distances_for_loose_floor_and_special_tiles(self):
        for kind in (11, 12, 13, 6):
            with self.subTest(kind=kind):
                level = bytearray(self.level)
                struct.pack_into(">H", level, 3 * 60 + 18 * 2, kind)
                state = self.runtime(x=428).state
                boundary = LevelMap(level).step_boundary(
                    3, 1, state, self.frames[15], (409, 147, 428, 226))
                # Type 12 uses its own barrier offset and the exclusive body edge.
                self.assertEqual(boundary, StepBoundary(9, 1, 12) if kind == 12
                                 else StepBoundary(3 if kind == 6 else 4, 0, kind))

    def test_asymmetric_ledge_step_distances_depend_on_side_and_current_tile(self):
        for kind, facing, expected in ((23, 1, 42), (24, 0, 64)):
            level = bytearray(self.level)
            state = self.runtime(x=408, facing=facing).state
            column = 7
            ahead = column + (1 if facing else -1)
            struct.pack_into(">H", level, 3 * 60 + (10 + ahead) * 2, kind)
            boundary = LevelMap(level).step_boundary(
                3, 1, state, self.frames[15], (389, 147, 412, 226))
            self.assertEqual(boundary.clearance, expected)
            struct.pack_into(">H", level, 3 * 60 + (10 + column) * 2, kind)
            boundary = LevelMap(level).step_boundary(
                3, 1, state, self.frames[15], (389, 147, 412, 226))
            self.assertEqual(boundary.clearance, expected - 51)

    def test_ledge_checks_facing_and_actual_gaps(self):
        self.assertEqual(self.map.ledge(3, 1, 405, 1), 408)
        self.assertIsNone(self.map.ledge(3, 1, 405, 0))
        self.assertIsNone(self.map.ledge(3, 1, 10, 0))
        self.assertEqual(self.map.ledge(0, 1, 309, 0), 306)

    def test_combat_turn_uses_native_foot_distance_and_draw_allowance(self):
        state = SequenceState(55, action=207, target_x=405, facing=1)
        # DoTurn: immediate gap, distance 21 + draw allowance 51, reserve 84.
        self.assertEqual(self.map.combat_turn_offset(3, 1, state, self.frames[207]), -12)
        state.target_x = 390
        self.assertEqual(self.map.combat_turn_offset(3, 1, state, self.frames[207]), 0)
        state.target_x = 385
        state.action = 158
        # First tile supported, second tile empty: add one tile to distance.
        self.assertEqual(self.map.combat_turn_offset(3, 1, state, self.frames[158]), -13)

    def test_combat_turn_clear_floor_and_linked_neighbor_need_no_adjustment(self):
        for room, x, facing in ((3, 250, 1), (3, 25, 0), (1, 490, 1)):
            with self.subTest(room=room, x=x, facing=facing):
                state = SequenceState(227, action=158, target_x=x, facing=facing)
                self.assertEqual(self.map.combat_turn_offset(room, 1, state, self.frames[158]), 0)

    def test_combat_turn_left_gap_and_hurt_sequence_allowance(self):
        state = SequenceState(227, action=158, target_x=300, facing=0)
        self.assertEqual(self.map.combat_turn_offset(2, 1, state, self.frames[158]), -36)
        state.sequence_id, state.action, state.target_x, state.facing = 94, 207, 405, 1
        # Hurt sequence 94 uses 22 instead of the drawing pose's 51.
        self.assertEqual(self.map.combat_turn_offset(3, 1, state, self.frames[207]), -41)

    def test_drawing_sword_reserves_native_distance_before_an_immediate_gap(self):
        state = SequenceState(2, action=15, target_x=411, facing=1)
        self.assertEqual(self.map.combat_draw_offset(
            3, 1, state, self.frames[15], (407, 147, 429, 226)), -35)
        state.target_x = 300
        state.facing = 0
        self.assertEqual(self.map.combat_draw_offset(
            2, 1, state, self.frames[15], (296, 147, 318, 226)), -32)

    def test_drawing_sword_does_not_adjust_clear_floor_or_already_missing_support(self):
        for room, x, facing in ((3, 250, 1), (3, 25, 0), (1, 490, 1), (3, 450, 1)):
            with self.subTest(room=room, x=x, facing=facing):
                state = SequenceState(2, action=15, target_x=x, facing=facing)
                self.assertEqual(self.map.combat_draw_offset(
                    room, 1, state, self.frames[15], (x - 4, 147, x + 18, 226)), 0)

    def test_ledge_release_distinguishes_wall_floor_and_free_air_both_facings(self):
        from pop2.terrain import Tile

        cases = ((20, 1, 11, -23), (20, 0, 23, -23), (0, 1, 11, -12),
                 (1, 0, 11, 10), (1, 1, 11, 0), (0, 0, 23, 0),
                 (20, 6, 11, -23), (6, 20, 11, 10), (0, 6, 23, 0))
        for facing in (0, 1):
            state = SequenceState(25, action=91, target_x=225, facing=facing)
            column = character_column(floor_contact_x(225, facing, self.frames[91]))
            for current, behind, sequence, offset in cases:
                with self.subTest(facing=facing, current=current, behind=behind):
                    def tile(_room, col, _row):
                        return Tile(current if col == column else behind)
                    with patch.object(self.map, "tile", side_effect=tile):
                        self.assertEqual(self.map.release_ledge(9, 1, state, self.frames[91]),
                                         (sequence, offset * (1 if facing else -1)))

    def test_cut_preserves_sequence_cursor_and_velocities(self):
        physics, motion = RooftopPhysics(self.map), TerrainMotion(3, 1)
        runtime = self.runtime(202, x=-22, facing=0)
        runtime.state.horizontal_velocity = 8
        snapshot = (runtime.state.sequence_id, runtime.state.cursor, runtime.state.action)
        self.assertTrue(physics.cut_horizontal(motion, runtime.state, (-28, 162, -2, 226)))
        self.assertEqual(motion.room, 1)
        self.assertEqual(runtime.state.target_x, -22 + 510)
        self.assertEqual(runtime.state.horizontal_velocity, 8)
        self.assertEqual((runtime.state.sequence_id, runtime.state.cursor, runtime.state.action), snapshot)

    def test_right_cut_and_missing_link(self):
        physics, motion = RooftopPhysics(self.map), TerrainMotion(1, 1)
        runtime = self.runtime(x=512)
        self.assertTrue(physics.cut_horizontal(motion, runtime.state, (498, 162, 526, 226)))
        self.assertEqual((motion.room, runtime.state.target_x), (3, 2))
        motion.room = 4
        runtime.state.target_x = 512
        self.assertFalse(physics.cut_horizontal(motion, runtime.state, (498, 162, 526, 226)))

    def test_left_cut_uses_facing_and_exclusive_native_bounds(self):
        cases = ((0, (-16, 160, 14, 226), True),
                 (0, (-15, 160, 15, 226), False),
                 (1, (-40, 160, -2, 226), True),
                 (1, (-39, 160, -1, 226), False),
                 (1, (-18, 160, 20, 226), False))
        for facing, bounds, allowed in cases:
            with self.subTest(facing=facing, bounds=bounds):
                motion = TerrainMotion(3, 1)
                runtime = self.runtime(202, x=-10, facing=facing)
                self.assertEqual(RooftopPhysics(self.map).cut_horizontal(
                    motion, runtime.state, bounds), allowed)
                self.assertEqual(motion.room, 1 if allowed else 3)

    def test_horizontal_cut_respects_source_pose_and_state_exclusions(self):
        physics = RooftopPhysics(self.map)
        for action in (*range(110, 120), *range(135, 163), *range(166, 169)):
            motion = TerrainMotion(3, 1)
            state = SequenceState(2, action=action, target_x=550, facing=1)
            self.assertFalse(physics.cut_horizontal(motion, state, (535, 150, 570, 226)))
        state = SequenceState(2, action=15, animation_state=7, target_x=550, facing=1)
        self.assertFalse(physics.cut_horizontal(TerrainMotion(3, 1), state, (535, 150, 570, 226)))

    def test_right_cut_uses_exclusive_native_edge(self):
        for right, allowed in ((523, False), (524, True)):
            motion = TerrainMotion(3, 1)
            runtime = self.runtime(202, x=510, facing=1)
            self.assertEqual(RooftopPhysics(self.map).cut_horizontal(
                motion, runtime.state, (490, 150, right, 226)), allowed)

    def test_airborne_frame_does_not_test_floor(self):
        physics, motion = RooftopPhysics(self.map), TerrainMotion(3, 1)
        runtime = self.runtime(4)
        runtime.state.action = 42
        runtime.state.current_y = -28
        events = physics.advance(motion, runtime, 450, (434, 132, 474, 198),
                                 frame_flags=self.frames[42].aux)
        self.assertFalse(motion.falling)
        self.assertFalse(events)
        self.assertEqual(runtime.state.current_y, -28)

    def test_ground_frame_starts_fall_over_gap(self):
        physics, motion = RooftopPhysics(self.map), TerrainMotion(3, 1)
        runtime = self.runtime()
        events = physics.advance(motion, runtime, 450, (435, 162, 465, 226),
                                 frame_flags=self.frames[15].aux)
        self.assertEqual([e.kind for e in events], ["fall"])
        self.assertTrue(motion.falling)
        self.assertEqual(motion.row, 2)
        self.assertEqual(runtime.state.action, 102)

    def test_retreat_fall_uses_native_corner_alignment_before_first_pose(self):
        for action, x in ((158, 416), (157, 427)):
            with self.subTest(action=action):
                runtime = self.runtime(227, x=x, facing=0)
                runtime.state.action = action
                runtime.state.horizontal_velocity = -2
                motion = TerrainMotion(3, 1)
                RooftopPhysics(self.map, self.frames).start_fall(motion, runtime)
                self.assertEqual((motion.row, runtime.state.sequence_id,
                                  runtime.state.action), (2, 81, 102))
                self.assertEqual(runtime.state.target_x, 425 if action == 158 else 438)
                self.assertEqual(runtime.state.current_x, runtime.state.target_x)
                self.assertEqual(runtime.state.current_y, -107)
                self.assertEqual(runtime.state.horizontal_velocity, -2)

    def test_fall_alignment_preserves_source_thresholds_and_cached_column(self):
        for x, expected in ((422, 425), (423, 423)):
            with self.subTest(x=x):
                state = SequenceState(227, action=158, target_x=x,
                                      current_y=-120, facing=0)
                self.map.align_fall(3, 2, state, self.frames[158])
                self.assertEqual(state.target_x, expected)
                self.assertEqual(state.current_y, -106)
        for x, expected in ((449, 452), (450, 450)):
            with self.subTest(x=x):
                state = SequenceState(2, action=15, target_x=x,
                                      current_y=-120, facing=1)
                self.map.align_fall(3, 2, state, self.frames[15])
                self.assertEqual(state.target_x, expected)
                self.assertEqual(state.current_y, -120)

    def test_clear_unarmed_fall_keeps_original_sequence_and_arc(self):
        runtime = self.runtime(x=470)
        runtime.state.action = 127
        motion = TerrainMotion(3, 1)
        RooftopPhysics(self.map, self.frames).start_fall(motion, runtime)
        self.assertEqual((runtime.state.sequence_id, runtime.state.action), (214, 102))
        self.assertEqual((runtime.state.target_x, runtime.state.current_y), (470, -115))

    def test_fall_below_viewport_does_not_cut_sideways_into_another_room(self):
        for x, facing, bounds in ((550, 1, (520, 530, 553, 600)),
                                  (-20, 0, (-24, 530, -2, 600))):
            with self.subTest(facing=facing):
                runtime = self.runtime(12, x=x, facing=facing)
                runtime.state.current_y = 14
                motion = TerrainMotion(3, 4, falling=True)
                self.assertFalse(RooftopPhysics(self.map).cut_horizontal(
                    motion, runtime.state, bounds))
                self.assertEqual((motion.room, runtime.state.target_x), (3, x))

    def test_void_cut_waits_for_source_height_threshold(self):
        for y, allowed in ((509, True), (510, False)):
            with self.subTest(y=y):
                runtime = self.runtime(12, x=540)
                runtime.state.current_y = y - floor_y(3)
                motion = TerrainMotion(3, 3, falling=True)
                self.assertEqual(RooftopPhysics(self.map).cut_horizontal(
                    motion, runtime.state, (509, y - 69, 542, y)), allowed)

    def test_fall_cut_checks_neighbor_entry_row_and_first_pose_exception(self):
        level = bytearray(self.level)
        # Make only room 5's row-2 entry solid, with row 1 still open.
        struct.pack_into(">H", level, 4 * 60 + 20 * 2, 20)
        physics = RooftopPhysics(LevelMap(level))
        for action, allowed in ((102, True), (106, False)):
            with self.subTest(action=action):
                runtime = self.runtime(12, x=540)
                runtime.state.action = action
                runtime.state.current_y = -30
                motion = TerrainMotion(3, 2, falling=True)
                self.assertEqual(physics.cut_horizontal(
                    motion, runtime.state, (509, 247, 542, 316)), allowed)

    def test_matching_open_neighbor_still_accepts_airborne_exit(self):
        runtime = self.runtime(12, x=540)
        runtime.state.current_y = -30
        motion = TerrainMotion(3, 2, falling=True)
        self.assertTrue(RooftopPhysics(self.map).cut_horizontal(
            motion, runtime.state, (509, 247, 542, 316)))
        self.assertEqual((motion.room, runtime.state.target_x), (4, 30))

    def test_linked_down_exit_takes_priority_at_440_without_height_margin(self):
        level = bytearray(self.level)
        struct.pack_into(">H", level, 0x2080 + 3 * 8 + 6, 2)
        runtime = self.runtime(12, x=540)
        runtime.state.current_y = 440 - floor_y(3)
        motion = TerrainMotion(3, 3, falling=True)
        self.assertFalse(RooftopPhysics(LevelMap(level)).cut_horizontal(
            motion, runtime.state, (509, 371, 542, 440)))
        self.assertEqual(motion.room, 3)

    def test_native_fall_gravity_and_void_death(self):
        physics, motion = RooftopPhysics(self.map), TerrainMotion(3, 1)
        runtime = self.runtime()
        physics.advance(motion, runtime, 450, (435, 162, 465, 226))
        speeds = []
        for _ in range(35):
            old_x = runtime.state.target_x
            runtime.next_frame()
            physics.advance(motion, runtime, old_x, (old_x, 200, old_x, 250), frame_flags=0)
            speeds.append(runtime.state.vertical_velocity)
            if motion.dead:
                break
        self.assertTrue(motion.dead)
        self.assertIn(63, speeds)
        self.assertEqual(runtime.state.action, 185)
        self.assertEqual(floor_y(motion.row) + runtime.state.current_y, 730)
        self.assertEqual(runtime.state.sound_events.count(7), 1)

    def test_landing_velocity_thresholds_and_damage(self):
        for velocity, sequence, damage, dead in ((12, 17, 0, False), (49, 17, 0, False),
                                                (50, 20, 1, False), (62, 20, 1, False),
                                                (63, 22, 0, True)):
            with self.subTest(velocity=velocity):
                runtime = self.runtime(12, x=250)
                runtime.state.current_y = -1
                runtime.state.vertical_velocity = velocity - 6
                motion = TerrainMotion(1, 1, falling=True)
                events = RooftopPhysics(self.map).advance(motion, runtime, 250, (235, 160, 265, 225))
                self.assertEqual(runtime.state.sequence_id, sequence)
                self.assertEqual(events[-1].damage, damage)
                self.assertEqual(motion.dead, dead)
                self.assertEqual(runtime.state.vertical_velocity, 0)
                cue = 7 if dead else 13 if damage else 296
                self.assertEqual(runtime.state.sound_events.count(cue), 1)

    def test_armed_soft_landing_uses_original_sequence(self):
        runtime = self.runtime(12, x=250)
        runtime.state.current_y = -1
        motion = TerrainMotion(1, 1, falling=True)
        RooftopPhysics(self.map).advance(motion, runtime, 250, (240, 160, 260, 225), sword_drawn=True)
        self.assertEqual((runtime.state.sequence_id, runtime.state.action), (63, 229))

    def test_grounded_sword_wall_response_distinguishes_front_from_back_both_facings(self):
        for facing in (0, 1):
            for front in (False, True):
                with self.subTest(facing=facing, front=front):
                    runtime = self.runtime(56, x=250, facing=facing)
                    direction = 1 if facing else -1
                    corrected = runtime.state.target_x + 5 * direction * (-1 if front else 1)
                    motion = TerrainMotion(1, 1)
                    with patch.object(self.map, "wall_correction", return_value=corrected):
                        events = RooftopPhysics(self.map).advance(
                            motion, runtime, 250, (225, 160, 275, 228), sword_drawn=True,
                            frame_record=self.frames[runtime.state.action], cut_enabled=False)
                    self.assertEqual(runtime.state.sequence_id, 64 if front else 65)
                    self.assertEqual(events[0].kind, "wall")
                    self.assertFalse(motion.falling)
                    self.assertEqual(runtime.state.horizontal_velocity, 0)
                    self.assertEqual(10 in runtime.state.sound_events, front)

    def test_unarmed_wall_bump_does_not_request_sword_contact(self):
        for action, sequence in ((7, 47), (40, 46)):
            with self.subTest(action=action):
                runtime = self.runtime(x=250)
                runtime.state.action = action
                runtime.state.sound_events.clear()
                motion = TerrainMotion(1, 1)
                with patch.object(self.map, "wall_correction", return_value=245):
                    events = RooftopPhysics(self.map).advance(
                        motion, runtime, 250, (240, 160, 260, 226), cut_enabled=False)
                self.assertEqual(runtime.state.sequence_id, sequence)
                self.assertEqual(events[0].kind, "wall")
                self.assertNotIn(10, runtime.state.sound_events)

    def test_wall_sweep_cannot_tunnel_through_tile(self):
        # Room 5 row 1 has a full wall from column 5.
        corrected = self.map.wall_correction(4, 230, 340, (322, 165, 356, 226))
        self.assertEqual(corrected, 340 + 280 - 356 - 1)
        self.assertLess(corrected, 280)

    def test_unarmed_grounded_wall_check_ignores_only_the_rear_side(self):
        old_left = (232, 150, 255, 226)
        old_right = (250, 150, 273, 226)
        for facing in (None, 0, 1):
            with self.subTest(facing=facing):
                self.assertEqual(self.map.wall_correction(
                    9, 245, 237, (224, 150, 254, 226), old_left, facing),
                    237 if facing == 1 else 238)
                self.assertEqual(self.map.wall_correction(
                    4, 263, 270, (257, 150, 280, 226), old_right, facing),
                    270 if facing == 0 else 269)

    def test_wall_touch_is_not_an_overlap_at_native_exclusive_barrier_edges(self):
        # GetColDetData 4:53b8-53ca only marks a strict edge overlap.
        old = (232, 150, 255, 226)
        self.assertEqual(self.map.wall_correction(
            9, 245, 238, (225, 150, 255, 226), old), 238)
        self.assertEqual(self.map.wall_correction(
            9, 245, 237, (224, 150, 254, 226), old), 238)
        old = (250, 150, 273, 226)
        self.assertEqual(self.map.wall_correction(
            4, 263, 269, (256, 150, 279, 226), old), 269)
        self.assertEqual(self.map.wall_correction(
            4, 263, 270, (257, 150, 280, 226), old), 269)

    def test_wall_sweep_uses_previous_sprite_bounds_not_a_translated_new_pose(self):
        old = (226, 150, 257, 226)
        new = (215, 152, 254, 226)
        # The new sprite extends farther left relative to its anchor. Using
        # new.left - dx would put the previous edge inside the wall already.
        self.assertEqual(self.map.wall_correction(9, 228, 218, new, old), 228)
        # Pose changes can cross a barrier even without anchor displacement.
        self.assertEqual(self.map.wall_correction(9, 228, 228, new, old), 238)

    def test_wall_sweep_recovers_existing_landing_overlap_but_allows_moving_out(self):
        old = (222, 148, 239, 226)
        inward = (218, 150, 240, 226)
        self.assertEqual(self.map.wall_correction(9, 226, 223, inward, old), 230)
        outward = (226, 148, 243, 226)
        self.assertEqual(self.map.wall_correction(9, 226, 230, outward, old), 230)

    def test_falling_drift_also_checks_walls_after_velocity_motion(self):
        runtime = self.runtime(12, x=250)
        runtime.state.horizontal_velocity = 24
        runtime.state.current_y = 20
        motion = TerrainMotion(4, 0, falling=True)
        events = RooftopPhysics(self.map).advance(motion, runtime, 250, (238, 90, 263, 126))
        self.assertLess(runtime.state.target_x, 274)
        self.assertEqual(runtime.state.horizontal_velocity, 0)
        self.assertIn("wall", [event.kind for event in events])

    def test_vertical_cut_rebases_365_pixel_clip(self):
        runtime = self.runtime(12, x=150)
        runtime.state.current_y = -1
        motion = TerrainMotion(6, 2, falling=True)
        events = RooftopPhysics(self.map).advance(motion, runtime, 150, (140, 280, 160, 345))
        self.assertEqual((motion.room, motion.row), (3, 0))
        self.assertEqual(floor_y(motion.row) + runtime.state.current_y, -14)
        self.assertEqual([event.kind for event in events], ["room"])

    def test_rooms_without_initial_guards_are_valid(self):
        self.assertEqual(GuardSpawn.all_from_level(self.level, 2), [])
        guards = GuardSpawn.all_from_level(self.level, 1)
        self.assertEqual(len(guards), 1)
        self.assertEqual((guards[0].x, guards[0].row, guards[0].life), (200, 1, 1))

    def test_flat_ground_does_not_rewrite_validated_animation_arcs(self):
        for sequence in (3, 4, 28, 26, 42, 55, 75, 62, 56):
            with self.subTest(sequence=sequence):
                reference = self.runtime(sequence, x=150)
                tested = self.runtime(sequence, x=150)
                motion = TerrainMotion(1, 1)
                physics = RooftopPhysics(self.map)
                for _ in range(15):
                    old_x = tested.state.target_x
                    a, b = reference.next_frame(), tested.next_frame()
                    physics.advance(motion, tested, old_x,
                                    (b.target_x - 10, 150, b.target_x + 10, 226),
                                    frame_record=self.frames[b.action])
                    self.assertEqual((tested.state.action, tested.state.current_y, tested.state.target_x),
                                     (a.action, a.current_y, a.target_x))
                    self.assertFalse(motion.falling)


class RooftopSceneTests(unittest.TestCase):
    def setUp(self):
        original_tk = tk.Tk

        def hidden_root():
            root = original_tk()
            root.withdraw()
            return root

        with patch("pop2.window_controls.tk.Tk", hidden_root):
            self.scene = ScenePrototype()
        self.scene.root.after_cancel(self.scene.animation_after_id)
        self.scene.animation_after_id = None
        self.scene.schedule_next_animation = lambda: None
        self.scene.combat.rng = random.Random(1)
        self.addCleanup(self.scene.root.destroy)
        self.now = 100

    def tick(self, count=1):
        for _ in range(count):
            self.now += 0.101
            with patch("pop2.scene_prototype.time.perf_counter", return_value=self.now):
                self.scene.advance_animation()

    def place(self, room, row, x, facing=0):
        scene = self.scene
        scene.clear_keys(None)
        scene.opening.active = False
        scene.sequence_state.current_x = scene.sequence_state.target_x = scene.player_x = x
        scene.sequence_state.current_y = 0
        scene.sequence_state.facing = facing
        scene.sequence_state.vertical_velocity = scene.sequence_state.horizontal_velocity = 0
        scene.sequence_state.sequence_id = 2
        scene.sequence_state.cursor = 0
        scene.sequence_runtime.next_frame()
        scene.action = scene.sequence_state.action
        scene.room_id = scene.terrain_motion.room = room
        scene.terrain_motion.row = row
        scene.terrain_motion.falling = scene.terrain_motion.dead = False
        if room not in scene.room_cache:
            scene.room_cache[room] = build_opening_room(include_curtain=False, room_id=room)
        room_art = scene.room_cache[room]
        scene.background, scene.foreground = room_art.background, room_art.foreground
        scene.combat.enter_room(room, row)

    def test_opening_is_unchanged_with_terrain_enabled(self):
        self.tick(19)
        self.assertFalse(self.scene.opening.active)
        self.assertEqual((self.scene.action, self.scene.player_x), (15, 411))
        self.assertEqual((self.scene.terrain_motion.room, self.scene.terrain_motion.row), (3, 1))
        self.tick(3)
        self.assertFalse(self.scene.terrain_motion.falling)

    def test_idle_window_escape_takes_three_stabs_without_premature_fall(self):
        scene = self.scene
        life_changes = []
        for _ in range(300):
            life = scene.combat.player.life
            self.tick()
            if scene.combat.player.life != life:
                life_changes.append(scene.combat.player.life)
            self.assertEqual(scene.terrain_motion.falling, not scene.combat.player.alive)
            if scene.combat.player.life == 1:
                self.assertEqual(scene.sequence_state.facing, 0)
            if not scene.combat.player.alive:
                break
        self.assertEqual(life_changes, [2, 1, 0])

    def test_parry_at_initial_edge_recoils_and_falls_without_losing_health(self):
        from pop2.combat import select_sequence

        scene = self.scene
        self.place(3, 1, 411, facing=0)
        scene.sword_drawn = scene.combat.player.sword_drawn = True
        scene.start_sequence(62)
        scene.sequence_runtime.next_frame()
        scene.sequence_runtime.next_frame()
        self.assertEqual(scene.sequence_state.action, 150)
        guard = scene.combat.guard
        guard.state.current_x = guard.state.target_x = 351
        guard.state.facing, guard.alert_mode, guard.sword_drawn = 1, 3, True
        select_sequence(guard, 58)
        guard.runtime.next_frame()
        guard.state.action = 153
        scene.action, scene.player_x = scene.sequence_state.action, scene.sequence_state.target_x
        events = scene.combat.resolve_contacts()
        self.assertEqual([(e.kind, e.actor) for e in events], [("parry", "player")])
        scene.up_held = True
        scene.pending_action = BufferedCommand("sword_block")
        self.tick(3)
        self.assertTrue(scene.terrain_motion.falling)
        self.assertFalse(scene.terrain_motion.hit_fall)
        self.assertEqual(scene.combat.player.life, 3)
        self.assertFalse(scene.sword_drawn)

    def test_parry_on_supported_roof_recoils_but_does_not_invent_a_fall(self):
        scene = self.scene
        self.place(3, 1, 300, facing=0)
        scene.peaceful = True
        scene.sword_drawn = scene.combat.player.sword_drawn = True
        scene.start_sequence(62)
        scene.sequence_runtime.next_frame()
        scene.sequence_runtime.next_frame()
        scene.sequence_state.action = scene.action = 161
        before = scene.sequence_state.target_x
        self.tick(3)
        self.assertEqual(scene.player_x, before + 25)
        self.assertFalse(scene.terrain_motion.falling)
        self.assertEqual(scene.combat.player.life, 3)

    def test_parry_counter_is_not_replaced_by_recoil_in_the_animation_tick(self):
        scene = self.scene
        self.place(3, 1, 300, facing=0)
        scene.peaceful = True
        scene.sword_drawn = scene.combat.player.sword_drawn = True
        scene.start_sequence(62)
        scene.sequence_runtime.next_frame()
        scene.sequence_runtime.next_frame()
        scene.sequence_state.action = scene.action = 161
        before = scene.sequence_state.target_x
        scene.player_x = before
        scene.set_key_state("ctrl", True)
        self.tick()
        self.assertEqual(scene.sequence_state.source_sequence_id, 66)
        self.assertEqual(scene.action, 162)
        self.assertEqual(scene.player_x, before + 6)
        self.assertFalse(scene.terrain_motion.falling)

    def test_sword_retreat_fall_can_catch_initial_roof_with_shift(self):
        scene = self.scene
        scene.peaceful = True
        scene.jump_to_room(scene.level_map.start_room, 1, 390, facing=0)
        scene.sword_drawn = scene.combat.player.sword_drawn = True
        scene.sequence_state.sequence_id, scene.sequence_state.cursor = 227, 0
        scene.sequence_runtime.next_frame()
        scene.horizontal_key(None, 1, True)
        fell = False
        for _ in range(30):
            if scene.terrain_motion.falling:
                fell = True
                self.assertFalse(scene.sword_drawn)
                self.assertFalse(scene.combat.player.sword_drawn)
                scene.set_key_state("shift", True)
            self.tick()
            if scene.ledge_hanging:
                break
        self.assertTrue(fell)
        self.assertTrue(scene.ledge_hanging)
        self.assertEqual(scene.action, 80)
        self.assertFalse(scene.terrain_motion.falling)
        self.assertTrue(scene.combat.player.alive)

    def test_f2_first_screen_uses_settled_curtain(self):
        scene = self.scene
        scene.jump_to_screen("1")
        self.assertEqual(scene.opening.curtain_frame, 8)
        after_jump = scene.native_viewport.crop((220, 30, 350, 140)).tobytes()
        scene.restart_opening()
        self.tick(19)
        self.assertEqual(scene.opening.curtain_frame, 8)
        self.assertEqual(scene.native_viewport.crop((220, 30, 350, 140)).tobytes(), after_jump)

    def test_shift_step_reaches_original_right_edge_without_lifting_actor(self):
        self.place(3, 1, 411, 1)
        scene = self.scene
        scene.shift_held = True
        scene.horizontal_key(None, 1, True)
        scene.horizontal_key(None, 1, False)
        self.tick(13)
        self.assertEqual((scene.player_x, scene.action, scene.sequence_state.current_y), (428, 15, 0))
        self.assertFalse(scene.terrain_motion.falling)

    def test_edge_warning_plays_native_probe_and_returns_without_a_step_or_fall(self):
        self.place(3, 1, 428, 1)
        scene = self.scene
        scene.shift_held = True
        scene.horizontal_key(None, 1, True)
        frames = []
        for _ in range(11):
            frames.append((scene.action, scene.player_x, scene.frames[scene.action].offset_y))
            self.assertFalse(scene.terrain_motion.falling)
            self.tick()
        self.assertEqual([f[0] for f in frames], [121, 122, 123, 124, 125, 126, 86, 116, 117, 118, 119])
        self.assertEqual([f[1] for f in frames], [428, 428, 431, 438, 443, 448, 441, 428, 428, 428, 428])
        self.assertEqual(frames[2][2], -1)
        self.tick(15)
        self.assertEqual((scene.action, scene.player_x), (15, 428))
        self.assertFalse(scene.terrain_motion.falling)
        self.assertFalse(scene.step_cautious)

    def test_second_shift_attempt_after_warning_steps_over_edge(self):
        self.place(3, 1, 428, 1)
        scene = self.scene
        scene.shift_held = True
        scene.horizontal_key(None, 1, True)
        scene.horizontal_key(None, 1, False)
        self.tick(12)
        scene.horizontal_key(None, 1, True)
        scene.horizontal_key(None, 1, False)
        self.assertEqual(scene.sequence_state.sequence_id, 42)
        self.tick(12)
        self.assertTrue(scene.terrain_motion.falling)
        for _ in range(30):
            self.tick()
            self.assertEqual(scene.room_id, 3)
        self.assertTrue(scene.terrain_motion.dead)
        self.assertEqual(scene.combat.player.life, 0)

    def test_armed_retreat_clears_roof_corner_and_stays_in_room_until_death(self):
        self.place(3, 1, 400)
        scene = self.scene
        scene.combat.guards.clear()
        scene.combat.guard = None
        scene.combat.generation_points.clear()
        scene.sword_drawn = True
        scene.start_sequence(227)
        scene.sequence_runtime.next_frame()
        scene.action = scene.sequence_state.action
        scene.horizontal_key(None, 1, True)
        for _ in range(25):
            self.tick()
            if scene.terrain_motion.falling:
                break
        self.assertTrue(scene.terrain_motion.falling)
        self.assertEqual((scene.action, scene.player_x, scene.sequence_state.current_y),
                         (102, 425, -107))
        self.tick(4)
        self.assertEqual((scene.action, scene.player_x), (106, 451))
        self.assertGreater(scene.player_bounds()[0], 431)
        for _ in range(25):
            self.tick()
            self.assertEqual(scene.room_id, 3)
        self.assertTrue(scene.terrain_motion.dead)

    def test_grounded_body_keeps_its_floor_parapet_occlusion(self):
        self.tick(19)
        self.place(3, 1, 380)
        scene = self.scene
        scene.combat.guards.clear()
        scene.combat.guard = None
        scene.combat.generation_points.clear()
        scene.render()
        image = ImageTk.getimage(scene.image_ref).resize((510, 384), Image.Resampling.NEAREST)
        sprite = scene.player_sprite()
        left, top, _right, _bottom = scene.player_bounds()
        room = scene.room_cache[scene.room_id]
        scenery = Image.alpha_composite(room.background, room.foreground)
        checked = 0
        for y in range(sprite.height):
            for x in range(sprite.width):
                px, py = left + x, top + y
                if sprite.getpixel((x, y))[3] == 255 and room.actor_occlusion[1].getpixel((px, py)) == 255:
                    self.assertEqual(image.getpixel((px, py)), scenery.getpixel((px, py)))
                    checked += 1
        self.assertGreater(checked, 10)

    def test_falling_body_is_not_erased_by_the_upper_roof_foreground(self):
        self.tick(19)
        self.place(3, 1, 400)
        scene = self.scene
        scene.combat.guards.clear()
        scene.combat.guard = None
        scene.combat.generation_points.clear()
        scene.sword_drawn = True
        scene.start_sequence(227)
        scene.sequence_runtime.next_frame()
        scene.action = scene.sequence_state.action
        scene.horizontal_key(None, 1, True)
        self.tick(2)
        self.assertEqual((scene.action, scene.terrain_motion.row), (102, 2))
        scene.render()
        image = ImageTk.getimage(scene.image_ref).resize((510, 384), Image.Resampling.NEAREST)
        sprite = scene.player_sprite()
        if scene.sequence_state.facing:
            sprite = ImageOps.mirror(sprite)
        left, top, _right, _bottom = scene.player_bounds()
        room = scene.room_cache[scene.room_id]
        restored = ImageChops.subtract(room.foreground.getchannel("A"), room.actor_occlusion[2])
        checked = 0
        for y in range(sprite.height):
            for x in range(sprite.width):
                px, py = left + x, top + y
                color = sprite.getpixel((x, y))
                if color[3] == 255 and restored.getpixel((px, py)) == 255:
                    self.assertEqual(image.getpixel((px, py)), color)
                    checked += 1
        self.assertGreater(checked, 10)

    def test_reinforcement_stops_after_sword_retreat_fall_and_death(self):
        self.tick(19)
        self.place(3, 1, 380)
        scene = self.scene
        encounter = scene.combat
        encounter.guards[0].life = 0
        encounter.world_frame = 1
        encounter.generation_points[0].countdown = 0
        encounter.generate_opponents()
        incoming = encounter.guards[1]
        scene.sword_drawn = True
        scene.start_sequence(227)
        scene.sequence_runtime.next_frame()
        scene.action = scene.sequence_state.action
        with patch("pop2.scene_prototype.time.perf_counter", return_value=self.now):
            scene.horizontal_key(None, 1, True)
        self.tick(80)
        self.assertTrue(scene.terrain_motion.dead)
        self.assertEqual(scene.room_id, 3)
        self.assertEqual((incoming.state.sequence_id, incoming.state.action), (77, 166))
        x = incoming.state.target_x
        self.tick(20)
        self.assertEqual((incoming.state.target_x, incoming.state.action), (x, 166))

    def test_window_reset_after_fall_restores_supported_opening_position(self):
        self.place(3, 1, 450, 1)
        self.tick(30)
        self.assertTrue(self.scene.terrain_motion.dead)
        self.scene.restart_opening()
        self.tick(19)
        self.assertEqual((self.scene.action, self.scene.player_x), (15, 411))
        self.assertEqual((self.scene.sequence_state.current_y,
                          self.scene.sequence_state.horizontal_velocity,
                          self.scene.sequence_state.vertical_velocity), (0, 0, 0))
        self.assertFalse(self.scene.terrain_motion.falling)

    def test_edge_warning_accepts_one_queued_jump_without_idle_gap(self):
        self.place(3, 1, 428, 1)
        scene = self.scene
        scene.shift_held = True
        scene.horizontal_key(None, 1, True)
        scene.horizontal_key(None, 1, False)
        self.tick(5)
        scene.shift_held = False
        scene.pending_action = BufferedCommand("jump", 1)
        self.tick(6)
        self.assertEqual((scene.sequence_state.sequence_id, scene.action), (3, 16))
        self.assertFalse(scene.terrain_motion.falling)
        self.assertIsNone(scene.pending_action)

    def test_secret_guard_palette_persists_on_revisit(self):
        self.place(4, 0, 300, 1)
        guard = self.scene.combat.guard
        self.assertEqual(guard.palette_variant, 3)
        self.place(3, 1, 300, 1)
        self.assertEqual(self.scene.combat.guard.palette_variant, 1)
        self.place(4, 0, 300, 1)
        self.assertIs(self.scene.combat.guard, guard)
        self.assertEqual(guard.palette_variant, 3)

    def test_ctrl_after_opening_turns_toward_guard_without_falling(self):
        scene = self.scene
        self.tick(19)
        scene.set_key_state("ctrl", True)
        scene.set_key_state("ctrl", False)
        self.assertEqual((scene.action, scene.player_x), (207, 370))
        poses = []
        for _ in range(12):
            self.tick()
            poses.append(scene.action)
            self.assertFalse(scene.terrain_motion.falling)
            self.assertFalse(scene.terrain_motion.dead)
        self.assertEqual(poses[:9], [177, 178, 211, 213, 212, 171, 160, 157, 158])
        self.assertEqual(scene.sequence_state.facing, 0)
        self.assertTrue(scene.sword_drawn)
        self.assertEqual(scene.combat.player.life, 3)
        self.assertEqual(scene.terrain_motion.row, 1)

    def test_opening_hurt_turn_uses_native_recovery_offset_and_preserves_three_hits(self):
        scene = self.scene
        for seed in (1, 2):
            with self.subTest(seed=seed), patch.object(scene, "render"):
                scene.restart_opening()
                scene.combat.rng.seed = seed
                lives, turn_x = [], None
                previous = 3
                for _ in range(300):
                    self.tick()
                    life = scene.combat.player.life
                    if life != previous:
                        lives.append(life)
                        previous = life
                    if scene.action == 177 and turn_x is None:
                        turn_x = scene.player_x
                    if not scene.combat.player.alive:
                        break
                    self.assertFalse(scene.terrain_motion.falling)
                self.assertEqual(lives, [2, 1, 0])
                self.assertEqual(turn_x, 385)
                self.assertTrue(scene.terrain_motion.falling)
                self.assertEqual((scene.sequence_state.sequence_id, scene.action), (81, 102))
                self.assertEqual(scene.terrain_motion.row, 2)

    def test_enemy_hit_fall_cannot_catch_even_with_shift_held(self):
        scene = self.scene
        for facing, x in ((0, 404), (1, 420)):
            with self.subTest(facing=facing), patch.object(scene, "render"):
                scene.jump_to_room(3, row=1, x=x, facing=facing)
                scene.set_peaceful(True)
                scene.sword_drawn = scene.combat.player.sword_drawn = True
                scene.start_sequence(227)
                scene.sequence_runtime.next_frame()
                scene.combat.guard.state.facing = 1
                scene.combat._hurt("player", scene.combat.player, scene.combat.guard)
                scene.set_key_state("shift", True)
                fell = False
                for _ in range(30):
                    self.tick()
                    if scene.terrain_motion.falling:
                        if not fell:
                            self.assertEqual(scene.combat.player.life, 2)
                        fell = True
                        self.assertTrue(scene.terrain_motion.hit_fall)
                    self.assertFalse(scene.ledge_hanging)
                    if scene.terrain_motion.dead:
                        break
                self.assertTrue(fell)

    def test_dead_actor_cannot_catch_a_ledge_in_the_shared_fall_loop(self):
        scene = self.scene
        self.place(3, 2, 451, 0)
        scene.set_peaceful(True)
        scene.terrain_motion.falling = True
        scene.combat.player.life = 0
        scene.start_sequence(12)
        scene.sequence_state.current_y = -44
        scene.sequence_state.vertical_velocity = 22
        scene.shift_held = True
        self.tick()
        self.assertFalse(scene.ledge_hanging)
        self.assertTrue(scene.terrain_motion.falling)

    def test_repeated_sword_retreat_from_opening_can_catch_the_right_edge(self):
        scene = self.scene
        for delay in (0, 1, 3):
            with self.subTest(delay=delay), patch.object(scene, "render"):
                scene.set_peaceful(True)
                scene.jump_to_screen("1")
                scene.horizontal_key(None, -1, True)
                scene.horizontal_key(None, -1, False)
                self.tick(10)
                scene.set_key_state("ctrl", True)
                self.tick(10)
                scene.set_key_state("ctrl", False)
                self.assertTrue(scene.sword_drawn)
                scene.horizontal_key(None, 1, True)
                for _ in range(12):
                    self.tick()
                    if scene.terrain_motion.falling:
                        break
                self.assertTrue(scene.terrain_motion.falling)
                self.assertFalse(scene.terrain_motion.hit_fall)
                self.assertFalse(scene.sword_drawn)
                self.tick(delay)
                scene.set_key_state("shift", True)
                for _ in range(12):
                    self.tick()
                    if scene.ledge_hanging:
                        break
                self.assertTrue(scene.ledge_hanging)
                self.assertEqual((scene.sequence_state.sequence_id, scene.player_x), (15, 423))
                self.assertFalse(scene.terrain_motion.falling)

    def test_armed_auto_turn_at_both_gap_sides_preserves_queued_attack(self):
        scene = self.scene
        guard = scene.combat.guard
        for room, x, facing, guard_x in ((3, 410, 1, 200), (2, 300, 0, 450)):
            with self.subTest(room=room, facing=facing):
                self.place(room, 1, x, facing)
                scene.sword_drawn = True
                scene.start_sequence(227)
                scene.sequence_runtime.next_frame()
                scene.action = scene.sequence_state.action
                guard.room, guard.row = room, 1
                guard.state.target_x = guard_x
                guard.alert_mode = 3
                guard.sword_drawn = True
                scene.combat.guards = [guard]
                scene.combat.guard = guard
                command = BufferedCommand("sword_attack")
                scene.pending_action = command
                poses = []
                with patch.object(scene.combat, "step", return_value=[]):
                    for _ in range(9):
                        self.tick()
                        poses.append(scene.action)
                        self.assertFalse(scene.terrain_motion.falling)
                        self.assertFalse(scene.terrain_motion.dead)
                self.assertEqual(poses, [177, 178, 211, 213, 212, 171, 160, 157, 151])
                self.assertEqual(scene.sequence_state.facing, 1 - facing)
                self.assertIsNone(scene.pending_action)
                self.assertEqual(scene.combat.player.life, 3)

    def test_running_left_enters_next_room_and_keeps_run(self):
        self.place(3, 1, 30)
        scene = self.scene
        scene.combat.guards.clear()
        scene.combat.guard = None
        scene.combat.generation_points.clear()
        scene.combat.player.life = 2
        scene.horizontal_key(None, -1, True)
        for _ in range(15):
            self.tick()
            if scene.room_id == 1:
                break
        self.assertEqual(scene.room_id, 1)
        self.assertTrue(scene.run_active)
        self.assertEqual(scene.horizontal_input, -1)
        self.assertEqual(scene.combat.player.life, 2)
        self.assertEqual(len(scene.combat.guards), 1)
        self.assertEqual(scene.combat.guards[0].room, 1)
        self.assertGreater(scene.player_x, 450)
        scene.render()
        image = ImageTk.getimage(scene.image_ref)
        self.assertEqual(image.size, (1020, 768))
        self.assertGreater(len(image.getcolors(image.width * image.height)), 50)

    def test_room_revisit_keeps_defeated_guards_and_generation_state(self):
        scene = self.scene
        guards = scene.combat.guards
        guards[0].life = 0
        point = scene.combat.generation_points[0]
        point.remaining = 0
        scene.combat.player.life = 2
        scene.combat.enter_room(1, 1)
        scene.combat.guards[0].life = 0
        scene.combat.enter_room(3, 1)
        self.assertIs(scene.combat.guards, guards)
        self.assertEqual(scene.combat.guards[0].life, 0)
        self.assertIs(scene.combat.generation_points[0], point)
        self.assertEqual(point.remaining, 0)
        self.assertEqual(scene.combat.player.life, 2)
        scene.combat.enter_room(1, 1)
        self.assertEqual(scene.combat.guards[0].life, 0)

    def test_empty_room_allows_sword_and_render_without_target(self):
        self.place(2, 1, 300)
        self.assertIsNone(self.scene.combat.guard)
        self.scene.set_key_state("ctrl", True)
        self.tick(12)
        self.scene.set_key_state("ctrl", False)
        self.scene.render()
        self.assertTrue(self.scene.sword_drawn)
        self.assertEqual(self.scene.combat.player.life, 3)

    def test_gap_fall_cannot_be_cancelled_with_jump_or_sword(self):
        self.place(3, 1, 450, facing=1)
        self.tick()
        self.assertTrue(self.scene.terrain_motion.falling)
        self.scene.up_key(None)
        self.scene.set_key_state("ctrl", True)
        self.tick(35)
        self.assertTrue(self.scene.terrain_motion.dead)
        self.assertEqual(self.scene.combat.player.life, 0)
        self.assertEqual(self.scene.action, 185)

    def test_reset_restores_first_room_and_full_health(self):
        self.place(1, 1, 300)
        self.scene.combat.player.life = 1
        self.scene.restart_opening()
        self.assertEqual(self.scene.room_id, 3)
        self.assertTrue(self.scene.opening.active)
        self.assertEqual(self.scene.combat.player.life, 3)
        self.assertEqual(set(self.scene.combat.room_encounters), {3})
        self.assertFalse(self.scene.terrain_motion.dead)
        self.tick(19)
        self.assertEqual((self.scene.action, self.scene.player_x), (15, 411))

    def test_running_jump_clears_the_next_rooftop_gap(self):
        self.place(2, 1, 360)
        scene = self.scene
        scene.horizontal_input = -1
        scene.held_directions = [-1]
        scene.in_animation_tick = True
        scene.sequence_state.action = 7
        scene.dispatch_jump(BufferedCommand("jump", -1, running=True))
        self.tick(11)
        self.assertFalse(scene.terrain_motion.falling)
        self.assertEqual(scene.terrain_motion.row, 1)
        self.assertLess(scene.player_x, 176)
        self.assertEqual(scene.sequence_state.current_y, 0)

    def test_standing_jump_can_still_enter_right_secret_room(self):
        self.place(3, 1, 428, 1)
        scene = self.scene
        scene.combat.guards.clear()
        scene.combat.guard = None
        scene.combat.generation_points.clear()
        scene.horizontal_input = 1
        scene.held_directions = [1]
        scene.in_animation_tick = True
        scene.dispatch_jump(BufferedCommand("jump", 1))
        self.tick(10)
        self.assertEqual(scene.room_id, 4)
        self.assertEqual((scene.sequence_state.sequence_id, scene.action), (3, 25))
        self.assertFalse(scene.terrain_motion.falling)
        self.assertEqual(scene.combat.guard.palette_variant, 3)
        # The original bug reversed this cut on the following jump pose.
        for _ in range(30):
            self.tick()
            self.assertEqual(scene.room_id, 4)
        self.assertTrue(scene.terrain_motion.dead)

    def test_standing_jump_fails_wide_gap_but_running_jump_crosses(self):
        scene = self.scene
        self.place(0, 1, 385)
        scene.horizontal_input = -1
        scene.held_directions = [-1]
        scene.in_animation_tick = True
        scene.dispatch_jump(BufferedCommand("jump", -1))
        for _ in range(19):
            self.tick()
            if scene.terrain_motion.falling:
                break
        self.assertTrue(scene.terrain_motion.falling)
        self.place(0, 1, 385)
        scene.horizontal_input = -1
        scene.held_directions = [-1]
        scene.in_animation_tick = True
        scene.sequence_state.action = 7
        scene.dispatch_jump(BufferedCommand("jump", -1, running=True))
        self.tick(11)
        self.assertFalse(scene.terrain_motion.falling)
        self.assertLess(scene.player_x, 176)

    def test_actual_right_transition_returns_to_opening_without_replay(self):
        self.place(1, 1, 500, facing=1)
        scene = self.scene
        scene.combat.guards.clear()
        scene.combat.guard = None
        scene.combat.generation_points.clear()
        scene.horizontal_key(None, 1, True)
        for _ in range(12):
            self.tick()
            if scene.room_id == 3:
                break
        self.assertEqual(scene.room_id, 3)
        self.assertFalse(scene.opening.active)
        self.assertTrue(scene.run_active)
        self.assertLess(scene.player_x, 30)

    def test_ledge_hold_and_release_use_real_terrain(self):
        self.place(3, 1, 408, facing=0)
        scene = self.scene
        scene.shift_held = scene.down_held = True
        scene.in_animation_tick = True
        self.assertTrue(scene.start_ledge_hang())
        self.assertEqual(scene.sequence_state.sequence_id, 68)
        self.tick(11)
        self.assertTrue(scene.ledge_hanging)
        self.assertFalse(scene.terrain_motion.falling)
        self.assertEqual(scene.sequence_state.sequence_id, 25)
        self.assertEqual(scene.terrain_motion.row, 2)
        scene.shift_held = False
        self.tick()
        self.assertFalse(scene.ledge_hanging)
        self.assertTrue(scene.terrain_motion.falling)
        self.tick(30)
        self.assertTrue(scene.terrain_motion.dead)

    def test_edge_return_finishes_on_floor_instead_of_floating(self):
        self.place(3, 1, 408, facing=0)
        scene = self.scene
        scene.shift_held = scene.down_held = True
        scene.in_animation_tick = True
        self.assertTrue(scene.start_ledge_hang())
        self.tick(10)
        scene.down_held = False
        scene.up_key(None)
        self.tick(18)
        self.assertFalse(scene.ledge_hanging)
        self.assertFalse(scene.ledge_climbing)
        self.assertFalse(scene.terrain_motion.falling)
        self.assertEqual(scene.sequence_state.current_y, 0)
        self.assertEqual(scene.combat.player.life, 3)

    def test_complete_opening_combat_and_first_room_exit(self):
        scene = self.scene
        with patch("pop2.scene_prototype.time.perf_counter", side_effect=lambda: self.now):
            self.tick(19)
            scene.horizontal_key(None, -1, True)
            scene.horizontal_key(None, -1, False)
            self.tick(8)
            scene.set_key_state("ctrl", True)
            scene.set_key_state("ctrl", False)
            self.tick(8)
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
                    scene.set_key_state("ctrl", True)
                    scene.set_key_state("ctrl", False)
                self.tick()
                if len(c.guards) == 2 and not any(g.alive for g in c.guards):
                    break
            self.assertEqual(len(c.guards), 2)
            self.assertFalse(any(g.alive for g in c.guards))
            self.assertEqual(c.player.life, 3)
            self.assertFalse(scene.terrain_motion.falling)
            scene.clear_keys(None)
            self.tick(10)
            scene.set_key_state("down", True)
            scene.set_key_state("down", False)
            self.tick(25)
            self.assertFalse(scene.sword_drawn)
            scene.horizontal_key(None, -1, True)
            for _ in range(30):
                self.tick()
                if scene.room_id == 1:
                    break
            self.assertEqual(scene.room_id, 1)
            self.assertEqual(c.player.life, 3)
            self.assertEqual(len(c.guards), 1)
            self.assertEqual(c.guards[0].life, 1)


if __name__ == "__main__":
    unittest.main()
