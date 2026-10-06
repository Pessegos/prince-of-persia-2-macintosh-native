import unittest
from unittest.mock import patch

from PIL import ImageTk

from game_ui import fit_viewport
from render_opening import ROOM_ORIGIN_X
from scene_prototype import animation_interval_for_frame
import test_terrain


class ViewportTests(unittest.TestCase):
    def test_aspect_fit_centers_without_stretching(self):
        self.assertEqual(fit_viewport(1920, 1080), ((1440, 1080), (240, 0)))
        self.assertEqual(fit_viewport(1280, 720), ((960, 720), (160, 0)))
        self.assertEqual(fit_viewport(800, 900), ((800, 600), (0, 150)))


class GameWindowTests(unittest.TestCase):
    setUp = test_terrain.RooftopSceneTests.setUp
    place = test_terrain.RooftopSceneTests.place
    tick = test_terrain.RooftopSceneTests.tick

    def clear_guards(self):
        self.scene.combat.guards.clear()
        self.scene.combat.guard = None
        self.scene.combat.generation_points.clear()

    def prepare_guard_jump(self, facing, running):
        from combat import select_sequence
        from scene_prototype import BufferedCommand

        scene = self.scene
        scene.combat.reset()
        scene.sword_drawn = False
        x, direction = (210, 1) if facing else (440, -1)
        self.place(1, 1, x, facing)
        self.clear_guards()
        # Move ownership too: otherwise the same NPC ticks twice, in both rooms.
        guard = scene.combat.room_encounters[3][0].pop()
        guard.room, guard.row = 1, 1
        guard.state.target_x = guard.state.current_x = x + 85 * direction
        guard.state.facing = 1 - facing
        guard.alert_mode, guard.sword_drawn = 3, True
        select_sequence(guard, 227)
        guard.runtime.next_frame()
        scene.combat.guards.append(guard)
        scene.combat.guard = guard
        scene.in_animation_tick = True
        if running:
            scene.start_sequence(1)
            scene.sequence_state.action = scene.action = 7
        self.assertTrue(scene.dispatch_jump(BufferedCommand("jump", direction, running=running)))
        return guard, direction

    def test_actual_jumps_are_blocked_by_a_grounded_opposing_guard(self):
        scene = self.scene
        for running in (False, True):
            for facing in (0, 1):
                with self.subTest(running=running, facing=facing):
                    guard, direction = self.prepare_guard_jump(facing, running)
                    with patch.object(scene.combat, "advance_guard"):
                        for _ in range(20):
                            self.tick()
                            self.assertLessEqual((scene.player_x - guard.state.target_x) * direction, 24)
                            if scene.sequence_state.sequence_id in (46, 47):
                                break
                    self.assertIn(scene.sequence_state.sequence_id, (46, 47))
                    self.assertFalse(scene.run_active)
                    self.assertFalse(scene.jump_repeat_armed)
                    self.assertIsNone(scene.pending_action)

    def test_jump_contact_with_live_ai_interrupts_before_passing_the_guard(self):
        scene = self.scene
        for running in (False, True):
            for facing in (0, 1):
                with self.subTest(running=running, facing=facing):
                    guard, direction = self.prepare_guard_jump(facing, running)
                    for _ in range(20):
                        self.tick()
                        self.assertLessEqual((scene.player_x - guard.state.target_x) * direction, 24)
                        interrupted = (scene.sequence_state.sequence_id in (46, 47)
                                       or scene.combat.player.controls_locked)
                        if interrupted:
                            break
                    self.assertTrue(interrupted)

    def test_combat_feet_stay_behind_all_overlapping_parapet_cells(self):
        from PIL import Image, ImageChops
        from render_opening import ROOM_ORIGIN_X, ROOM_WIDTH, ROOM_HEIGHT, add_alpha

        scene = self.scene
        self.place(3, 1, 395, facing=0)
        self.clear_guards()
        scene.opening = None
        room = scene.room_cache[3]
        floor_mask = Image.new("L", (ROOM_WIDTH, ROOM_HEIGHT))
        for piece in room.pieces:
            if piece.row == 1 and piece.kind == 1:
                add_alpha(floor_mask, piece.alpha, piece.x, piece.y)
        for action in (154, 157, 158):
            with self.subTest(action=action):
                scene.sequence_state.action = scene.action = action
                scene.sequence_state.animation_state = 1
                scene.render()
                actual = scene.native_viewport.crop(
                    (ROOM_ORIGIN_X, 0, ROOM_ORIGIN_X + ROOM_WIDTH, ROOM_HEIGHT))
                difference = ImageChops.difference(actual.convert("RGB"), room.flattened().convert("RGB"))
                self.assertIsNone(ImageChops.multiply(difference.convert("L"), floor_mask).getbbox())
                self.assertIsNotNone(difference.getbbox())

    def test_escape_pauses_both_actors_and_keeps_the_native_pause_text(self):
        scene = self.scene
        self.tick(19)
        before = (scene.action, scene.player_x, scene.combat.world_frame,
                  scene.combat.guard.state.action)
        with patch("scene_prototype.time.perf_counter", return_value=100):
            scene.escape_key()
        self.assertTrue(scene.paused)
        scene.escape_key()
        self.assertTrue(scene.paused)
        scene.horizontal_key(None, 1, True)
        scene.set_key_state("ctrl", True)
        self.tick(10)
        self.assertEqual(before, (scene.action, scene.player_x, scene.combat.world_frame,
                                 scene.combat.guard.state.action))
        self.assertEqual(scene.pause_text.height, 16)
        self.assertGreater(scene.pause_text.width, 50)
        image = ImageTk.getimage(scene.image_ref)
        colors = {color for _count, color in image.getcolors(image.width * image.height)}
        self.assertIn((255, 255, 85, 255), colors)
        last_guard_at = scene.combat.last_guard_at
        scene.escape_release()
        with patch("scene_prototype.time.perf_counter", return_value=120):
            scene.escape_key()
        self.assertFalse(scene.paused)
        self.assertEqual(scene.combat.last_guard_at, last_guard_at + 20)

    def test_fullscreen_remembers_normal_and_maximized_state(self):
        scene = self.scene
        for state in ("normal", "zoomed"):
            with self.subTest(state=state):
                scene.fullscreen = False
                with patch.object(scene.root, "state", return_value=state) as state_call, \
                        patch.object(scene.root, "geometry", return_value="900x700+30+40") as geometry, \
                        patch.object(scene.root, "attributes") as attributes:
                    scene.toggle_fullscreen()
                    self.assertTrue(scene.fullscreen)
                    self.assertEqual(scene.canvas.cget("cursor"), "none")
                    scene.toggle_fullscreen()
                    self.assertFalse(scene.fullscreen)
                    self.assertEqual(scene.canvas.cget("cursor"), "")
                    self.assertEqual(attributes.call_args_list[0].args, ("-fullscreen", True))
                    self.assertEqual(attributes.call_args_list[1].args, ("-fullscreen", False))
                    state_call.assert_called_with(state)
                    self.assertEqual(geometry.call_count, 2 if state == "normal" else 1)

    def test_screen_labels_do_not_render_other_rooms(self):
        scene = self.scene
        cached_rooms = set(scene.room_cache)
        with patch("scene_prototype.build_opening_room") as build:
            self.assertEqual(scene.screen_label(2), "3")
            self.assertEqual(tuple(scene.dev_screens()),
                             ("1", "2", "3", "4", "5", "6", "7", "Secret (right)"))
            build.assert_not_called()
        self.assertEqual(set(scene.room_cache), cached_rooms)

    def test_development_jump_resets_state_without_replaying_the_opening(self):
        scene = self.scene
        scene.combat.player.life = 1
        scene.sword_drawn = True
        scene.terrain_motion.falling = True
        scene.jump_to_room(9, row=1, x=240, facing=0)
        self.assertEqual((scene.room_id, scene.terrain_motion.row, scene.player_x), (9, 1, 240))
        self.assertFalse(scene.opening.active)
        self.assertEqual(scene.opening.phase, "done")
        self.assertFalse(scene.sword_drawn)
        self.assertFalse(scene.terrain_motion.falling)
        self.assertEqual(scene.combat.player.life, 3)
        self.assertIn(9, scene.dev_rooms())

    def test_invalid_development_jump_does_not_destroy_the_current_game(self):
        scene = self.scene
        snapshot = (scene.room_id, scene.player_x, scene.combat.guard)
        with self.assertRaises(ValueError):
            scene.jump_to_room(9, x=999)
        self.assertEqual(snapshot, (scene.room_id, scene.player_x, scene.combat.guard))

    def test_live_opponent_selects_native_short_sheath(self):
        scene = self.scene
        self.tick(19)
        scene.in_animation_tick = True
        scene.sword_drawn = True
        scene.start_sword_action("sword_sheathe")
        self.assertEqual(scene.sequence_state.sequence_id, 93)
        self.assertEqual(animation_interval_for_frame(93, 234), 100)
        self.assertAlmostEqual(animation_interval_for_frame(93, 236), 1000 / 12)
        scene.combat.guard.life = 0
        scene.start_sword_action("sword_sheathe")
        self.assertEqual(scene.sequence_state.sequence_id, 92)

    def test_peaceful_keeps_terrain_and_freezes_guards_without_erasing_them(self):
        scene = self.scene
        scene.jump_to_screen("1")
        guard = scene.combat.guard
        snapshot = guard.state.__dict__.copy()
        world_frame = scene.combat.world_frame
        with patch.object(scene.combat, "step", side_effect=AssertionError("AI in peaceful")), \
                patch.object(scene.combat, "choose_player_bump", side_effect=AssertionError("NPC contact")):
            scene.set_peaceful(True)
            self.tick(20)
        self.assertEqual(guard.state.__dict__, snapshot)
        self.assertGreater(scene.combat.world_frame, world_frame)
        self.assertIsNotNone(scene.physics)
        self.assertEqual(scene.combat.player.life, 3)
        scene.jump_to_screen("5")
        self.assertTrue(scene.peaceful)
        scene.jump_to_room(9, row=1, x=240, facing=0)
        scene.set_key_state("up", True)
        self.tick(40)
        self.assertEqual(scene.terrain_motion.row, 0)
        self.assertFalse(scene.terrain_motion.falling)
        scene.set_peaceful(False)
        self.assertFalse(scene.peaceful)

    def test_peaceful_hides_guards_hit_art_and_opponent_meter_only(self):
        scene = self.scene
        scene.jump_to_screen("1")
        with patch.object(scene.guard_art, "draw") as guard, \
                patch.object(scene.hit_art, "draw") as hit, \
                patch.object(scene.health_art, "draw", wraps=scene.health_art.draw) as health:
            scene.set_peaceful(True)
            guard.assert_not_called()
            self.assertEqual(hit.call_count, 1)
            health.assert_called_once_with(scene.native_viewport, scene.combat, show_opponent=False)
            self.assertIsNotNone(scene.native_viewport.crop((0, 368, 42, 384)).convert("RGB").getbbox())
            self.assertIsNone(scene.native_viewport.crop((455, 368, 512, 384)).convert("RGB").getbbox())
        before = (scene.room_id, scene.player_x, scene.terrain_motion.row)
        original = scene.combat.guard
        scene.set_peaceful(False)
        self.assertEqual(before, (scene.room_id, scene.player_x, scene.terrain_motion.row))
        self.assertIs(scene.combat.guard, original)

    def test_peaceful_does_not_choose_short_sheath_or_auto_rotate_toward_hidden_guard(self):
        scene = self.scene
        scene.jump_to_screen("1")
        scene.set_peaceful(True)
        scene.sword_drawn = True
        scene.in_animation_tick = True
        scene.start_sword_action("sword_sheathe")
        self.assertEqual(scene.sequence_state.sequence_id, 92)
        with patch.object(scene.combat, "choose_player_turn", side_effect=AssertionError("auto turn")):
            self.assertFalse(scene.resume_combat_turn())

    def test_development_menu_can_toggle_peaceful_without_teleporting(self):
        scene = self.scene
        scene.jump_to_screen("3")
        before = (scene.room_id, scene.player_x, scene.combat.guard)
        scene.open_dev_mode()
        scene.dev_menu.focus = 1
        scene.apply_dev_action(scene.dev_menu.key("space"))
        self.assertTrue(scene.peaceful)
        scene.close_dev_mode()
        self.assertEqual(before, (scene.room_id, scene.player_x, scene.combat.guard))
        self.assertFalse(scene.paused)

    def test_retreat_then_sheath_at_junction_completes_without_rear_wall_bump(self):
        from dataclasses import replace
        from sequence_runtime import SequenceRuntime

        scene = self.scene
        scene.jump_to_room(9, row=1, x=286, facing=1)
        scene.set_peaceful(True)
        scene.advance_animation_now = lambda: None
        scene.set_key_state("ctrl", True)
        self.tick(12)
        scene.set_key_state("ctrl", False)
        scene.horizontal_key(None, -1, True)
        for _ in range(31):
            self.tick()
            self.assertGreaterEqual(scene.player_bounds()[0], 225)
        scene.horizontal_key(None, -1, False)
        self.tick(3)
        scene.set_key_state("down", True)
        reference = SequenceRuntime(scene.sequences, replace(scene.sequence_state))
        self.assertTrue(scene.sword_sheathing)
        self.assertFalse(scene.sword_drawn)
        for _ in range(19):
            expected = reference.next_frame()
            self.tick()
            self.assertEqual((scene.sequence_state.sequence_id, scene.action, scene.player_x),
                             (expected.sequence_id, expected.action, expected.target_x))
            self.assertFalse(scene.sword_drawn)
            self.assertFalse(scene.terrain_motion.falling)
        self.assertFalse(scene.sword_sheathing)
        self.assertEqual(scene.action, 15)
        scene.set_key_state("down", False)
        anchor = scene.player_x
        scene.horizontal_key(None, 1, True)
        self.tick(8)
        self.assertGreater(scene.player_x, anchor)
        self.assertFalse(scene.sword_sheathing)
        self.assertFalse(scene.combat.player.controls_locked)
        self.assertIsNone(scene.pending_action)

    def test_repeated_standing_turns_at_wall_preserve_all_native_poses_and_position(self):
        from dataclasses import replace
        from sequence_runtime import SequenceRuntime

        scene = self.scene
        scene.jump_to_room(9, row=1, x=233, facing=0)
        scene.set_peaceful(True)
        scene.advance_animation_now = lambda: None
        for turn in range(6):
            direction = 1 if turn % 2 == 0 else -1
            scene.horizontal_key(None, direction, True)
            scene.horizontal_key(None, direction, False)
            reference = SequenceRuntime(scene.sequences, replace(scene.sequence_state))
            actions = []
            for _ in range(9):
                expected = reference.next_frame()
                self.tick()
                actions.append(scene.action)
                self.assertEqual((scene.sequence_state.sequence_id, scene.action, scene.player_x),
                                 (expected.sequence_id, expected.action, expected.target_x))
                self.assertFalse(scene.terrain_motion.falling)
            self.assertEqual(actions, [*range(45, 53), 15])
            self.assertEqual(scene.player_x, 242 if direction > 0 else 233)
        self.assertEqual(scene.player_x, 233)

    def test_draw_facing_a_solid_wall_reserves_native_space_and_finishes_both_sides(self):
        from dataclasses import replace
        from sequence_runtime import SequenceRuntime

        scene = self.scene
        for room, row, x, facing in ((9, 1, 233, 0), (20, 0, 272, 1)):
            with self.subTest(facing=facing):
                scene.jump_to_room(room, row=row, x=x, facing=facing)
                scene.set_peaceful(True)
                scene.in_animation_tick = True
                scene.set_key_state("ctrl", True)
                scene.set_key_state("ctrl", False)
                self.assertEqual(scene.player_x, x - 52 * (1 if facing else -1))
                reference = SequenceRuntime(scene.sequences, replace(scene.sequence_state))
                actions = []
                for _ in range(7):
                    expected = reference.next_frame()
                    self.tick()
                    actions.append(scene.action)
                    self.assertEqual((scene.sequence_state.sequence_id, scene.action, scene.player_x),
                                     (expected.sequence_id, expected.action, expected.target_x))
                    self.assertTrue(scene.sword_drawn)
                    self.assertFalse(scene.terrain_motion.falling)
                self.assertEqual(actions, [207, 208, 209, 210, 158, 170, 171])

    def test_releasing_wall_supported_hang_uses_full_native_floor_return(self):
        from dataclasses import replace
        from sequence_runtime import SequenceRuntime

        scene = self.scene
        scene.jump_to_room(9, row=1, x=240, facing=0)
        scene.set_peaceful(True)
        scene.advance_animation_now = lambda: None
        scene.set_key_state("shift", True)
        scene.up_key(None)
        scene.set_key_state("up", False)
        self.tick(24)
        self.assertEqual((scene.sequence_state.sequence_id, scene.action), (25, 91))
        state = replace(scene.sequence_state, sequence_id=11, cursor=0,
                        current_x=248, target_x=248, sequence_mode=0)
        reference = SequenceRuntime(scene.sequences, state)
        scene.set_key_state("shift", False)
        actions = []
        for _ in range(7):
            expected = reference.next_frame()
            self.tick()
            actions.append(scene.action)
            self.assertEqual((scene.sequence_state.sequence_id, scene.action, scene.player_x,
                              scene.sequence_state.current_y),
                             (expected.sequence_id, expected.action, expected.target_x,
                              expected.current_y))
            self.assertFalse(scene.terrain_motion.falling)
            self.assertFalse(scene.native_ledge)
        self.assertEqual(actions, [81, 82, 83, 84, 85, 15, 15])
        scene.horizontal_key(None, 1, True)
        self.tick(12)
        self.assertGreater(scene.player_x, 245)

    def test_wall_bump_cannot_replay_the_same_jump_on_up_release_or_hold(self):
        scene = self.scene
        scene.advance_animation_now = lambda: None
        for room, row, x, facing in ((9, 1, 233, 0), (20, 0, 272, 1)):
            direction = 1 if facing else -1
            for up_first in (False, True):
                for release_tick in (1, 3, 6, 10, None):
                    with self.subTest(facing=facing, up_first=up_first, release=release_tick):
                        scene.jump_to_room(room, row=row, x=x, facing=facing)
                        scene.set_peaceful(True)
                        if up_first:
                            scene.up_key(None)
                            scene.horizontal_key(None, direction, True)
                        else:
                            scene.horizontal_key(None, direction, True)
                            scene.up_key(None)
                        collided = False
                        for tick in range(20):
                            if tick == release_tick:
                                scene.set_key_state("up", False)
                                scene.horizontal_key(None, direction, False)
                            self.tick()
                            sequence = scene.sequence_state.sequence_id
                            if collided:
                                self.assertNotIn(sequence, (3, 4, 28))
                                self.assertIsNone(scene.pending_action)
                            collided |= sequence == 47
                            self.assertFalse(scene.terrain_motion.falling)
                        self.assertTrue(collided)
                        self.assertEqual(scene.action, 15)
                        self.assertFalse(scene.jump_repeat_armed)
                        # A genuinely new chord remains usable after the bump.
                        scene.set_key_state("up", False)
                        scene.horizontal_key(None, direction, False)
                        scene.up_key(None)
                        scene.horizontal_key(None, direction, True)
                        self.assertEqual(scene.sequence_state.sequence_id, 3)

    def test_near_wall_forward_tap_uses_native_short_step_without_shift(self):
        scene = self.scene
        for room, row, x, direction in ((9, 1, 245, -1), (20, 0, 255, 1)):
            with self.subTest(direction=direction):
                scene.jump_to_room(room, row=row, x=x, facing=int(direction > 0))
                scene.set_peaceful(True)
                scene.advance_animation_now = lambda: None
                boundary = scene.level_map.step_boundary(
                    room, row, scene.sequence_state, scene.frames[15], scene.player_bounds())
                self.assertEqual(boundary.barrier_type, 1)
                self.assertLess(boundary.clearance, 27)
                scene.horizontal_key(None, direction, True)
                scene.horizontal_key(None, direction, False)
                self.assertFalse(scene.shift_held)
                self.assertFalse(scene.run_active)
                self.assertNotIn(scene.sequence_state.sequence_id, (1, 200))
                self.tick(20)
                self.assertEqual(scene.action, 15)
                self.assertFalse(scene.terrain_motion.falling)

    def test_auto_step_only_applies_inside_native_27_pixel_solid_barrier_threshold(self):
        from mac_input import StepBoundary
        from scene_prototype import BufferedCommand

        scene = self.scene
        for clearance, barrier, expected in ((26, 1, True), (27, 1, False), (2, 0, False), (26, 2, False)):
            with self.subTest(clearance=clearance, barrier=barrier):
                scene.jump_to_room(1, row=1, x=300, facing=1)
                scene.advance_animation_now = lambda: None
                with patch.object(scene.level_map, "step_boundary", return_value=StepBoundary(clearance, barrier, 20)):
                    scene.dispatch_horizontal_action(BufferedCommand("horizontal", 1, "run"))
                self.assertEqual(scene.run_active, not expected)

    def test_near_wall_short_steps_finish_without_spurious_bumps_both_directions(self):
        scene = self.scene
        for room, row, direction, end_x in ((9, 1, -1, 233), (20, 0, 1, 272)):
            for clearance in range(5, 27):
                x = end_x - direction * (clearance - 4)
                with self.subTest(direction=direction, clearance=clearance):
                    scene.jump_to_room(room, row=row, x=x, facing=int(direction > 0))
                    scene.set_peaceful(True)
                    scene.in_animation_tick = True
                    boundary = scene.level_map.step_boundary(
                        room, row, scene.sequence_state, scene.frames[15], scene.player_bounds())
                    self.assertEqual((boundary.clearance, boundary.barrier_type), (clearance, 1))
                    scene.horizontal_key(None, direction, True)
                    scene.horizontal_key(None, direction, False)
                    previous_x = scene.player_x
                    for _ in range(16):
                        self.tick()
                        self.assertNotIn(scene.sequence_state.sequence_id, (1, 200, 45, 46, 47))
                        self.assertGreaterEqual((scene.player_x - previous_x) * direction, 0)
                        if direction < 0:
                            self.assertGreaterEqual(scene.player_bounds()[0], 225)
                        else:
                            self.assertLess(scene.player_bounds()[2], 280)
                        self.assertFalse(scene.terrain_motion.falling)
                        previous_x = scene.player_x
                    self.assertEqual((scene.player_x, scene.action), (end_x, 15))
                    self.assertFalse(scene.shift_held)
                    self.assertIsNone(scene.pending_action)

    def test_screen_five_repeated_taps_match_native_short_step_and_actual_bump(self):
        scene = self.scene
        scene.jump_to_room(9, row=1, x=248, facing=0)
        scene.set_peaceful(True)
        scene.in_animation_tick = True
        for expected_sequence, expected_x in ((33, 233), (42, 245), (32, 233), (42, 245)):
            scene.horizontal_key(None, -1, True)
            scene.horizontal_key(None, -1, False)
            self.assertEqual(scene.sequence_state.sequence_id, expected_sequence)
            for _ in range(16):
                self.tick()
                self.assertGreaterEqual(scene.player_bounds()[0], 225)
                self.assertFalse(scene.terrain_motion.falling)
            self.assertEqual((scene.action, scene.player_x), (15, expected_x))
            self.assertIsNone(scene.pending_action)

    def test_screen_five_crouch_tap_reaches_low_pose_before_native_rise_bump(self):
        scene = self.scene
        scene.jump_to_room(9, row=1, x=248, facing=0)
        scene.set_peaceful(True)
        scene.in_animation_tick = True
        scene.set_key_state("down", True)
        scene.set_key_state("down", False)
        frames = []
        for _ in range(9):
            self.tick()
            frames.append((scene.sequence_state.sequence_id, scene.action, scene.player_x))
            self.assertGreaterEqual(scene.player_bounds()[0], 225)
            self.assertFalse(scene.terrain_motion.falling)
        # Video 22.27.53.32: 107 -> 108 -> 109 -> 110 -> 111, then wall bump.
        self.assertEqual(frames, [(50, 107, 245), (50, 108, 239), (117, 109, 232),
                                  (49, 110, 229), (49, 111, 227), (47, 50, 242),
                                  (47, 51, 242), (47, 52, 242), (2, 15, 242)])
        self.assertIsNone(scene.pending_action)

    def test_screen_five_held_crouch_keeps_low_pose_and_release_remains_controllable(self):
        scene = self.scene
        scene.jump_to_room(9, row=1, x=248, facing=0)
        scene.set_peaceful(True)
        scene.in_animation_tick = True
        scene.set_key_state("down", True)
        self.tick(3)
        for _ in range(24):
            self.tick()
            self.assertEqual((scene.sequence_state.sequence_id, scene.action, scene.player_x),
                             (117, 109, 232))
            self.assertFalse(scene.terrain_motion.falling)
        scene.set_key_state("down", False)
        self.tick()
        self.assertEqual((scene.sequence_state.sequence_id, scene.action), (49, 110))
        self.tick(8)
        self.assertEqual((scene.action, scene.player_x), (15, 242))
        scene.horizontal_key(None, 1, True)
        self.tick(10)
        self.assertGreater(scene.player_x, 242)
        self.assertFalse(scene.terrain_motion.falling)

    def test_screen_five_crouch_tap_against_wall_does_not_flash_lower_pose(self):
        scene = self.scene
        scene.jump_to_room(9, row=1, x=233, facing=0)
        scene.set_peaceful(True)
        scene.in_animation_tick = True
        scene.set_key_state("down", True)
        scene.set_key_state("down", False)
        frames = []
        for _ in range(4):
            self.tick()
            frames.append((scene.sequence_state.sequence_id, scene.action, scene.player_x))
        self.assertEqual(frames, [(47, 50, 247), (47, 51, 247), (47, 52, 247), (2, 15, 247)])
        self.assertIsNone(scene.pending_action)

    def test_development_menu_teleports_without_a_live_input_or_pause_backlog(self):
        scene = self.scene
        for paused in (False, True):
            scene.set_paused(paused)
            scene.open_dev_mode()
            self.assertTrue(scene.paused)
            self.assertEqual(scene.dev_menu.screens,
                             ("1", "2", "3", "4", "5", "6", "7", "Secret (right)"))
            scene.dev_menu.select(4)
            scene.apply_dev_action("go")
            self.assertIsNone(scene.dev_menu)
            self.assertEqual(scene.paused, paused)
            self.assertEqual((scene.room_id, scene.player_x, scene.terrain_motion.row), (9, 495, 1))

    def test_screen_selection_uses_route_order_and_the_entry_floor(self):
        scene = self.scene
        for label, room, row, x, facing in (("1", 3, 1, 411, 1), ("2", 1, 1, 495, 0),
                                           ("3", 2, 1, 495, 0), ("4", 0, 1, 495, 0),
                                           ("5", 9, 1, 495, 0), ("6", 10, 0, 495, 0),
                                           ("7", 11, 1, 495, 0), ("Secret (right)", 4, 0, 285, 1)):
            with self.subTest(screen=label):
                scene.jump_to_screen(label)
                self.clear_guards()
                self.tick(3)
                self.assertEqual((scene.room_id, scene.terrain_motion.row, scene.player_x,
                                  scene.sequence_state.facing), (room, row, x, facing))
                self.assertFalse(scene.terrain_motion.falling)

    def test_pause_ink_is_vertically_centered_in_the_native_hud(self):
        scene = self.scene
        scene.set_paused(True)
        image = scene.native_viewport
        yellow = [(x, y) for y in range(365, 384) for x in range(120, 390)
                  if image.getpixel((x, y))[:3] == (255, 255, 85)]
        self.assertEqual((min(y for x, y in yellow), max(y for x, y in yellow)), (369, 379))

    def test_direction_pressed_during_sheathing_starts_run_without_an_idle_frame(self):
        scene = self.scene
        scene.jump_to_screen("2")
        self.clear_guards()
        scene.in_animation_tick = True
        scene.sword_drawn = True
        scene.start_sword_action("sword_sheathe")
        scene.horizontal_key(None, -1, True)
        self.assertEqual(scene.pending_action.kind, "horizontal")
        actions = []
        for _ in range(25):
            self.tick()
            actions.append(scene.action)
            if not scene.sword_sheathing:
                break
        self.assertFalse(scene.sword_drawn)
        self.assertTrue(scene.run_active)
        self.assertNotIn(15, actions)
        self.assertNotIn(51, actions)
        self.assertNotIn(52, actions)

    def test_consecutive_running_jumps_cross_both_rooftop_gaps(self):
        scene = self.scene
        scene.jump_to_screen("3")
        self.clear_guards()
        scene.in_animation_tick = True
        scene.horizontal_key(None, -1, True)
        jumps = 0
        landed = []
        previous_sequence = scene.sequence_state.sequence_id
        for _ in range(100):
            if not jumps and scene.player_x < 345:
                scene.up_key(None)
                jumps = 1
            elif jumps == 1 and scene.room_id == 0 and scene.player_x < 385:
                scene.up_key(None)
                jumps = 2
            self.tick()
            if scene.sequence_state.sequence_id == 4 and scene.up_held:
                scene.set_key_state("up", False)
            if scene.action == 44 and previous_sequence == 4:
                landed.append((scene.room_id, scene.terrain_motion.row))
                self.assertFalse(scene.terrain_motion.falling)
            previous_sequence = scene.sequence_state.sequence_id
            self.assertFalse(scene.terrain_motion.dead)
            if len(landed) == 2:
                break
        self.assertEqual(landed, [(2, 1), (0, 1)])

    def test_sheathing_resumes_a_previously_held_direction(self):
        scene = self.scene
        scene.jump_to_screen("2")
        self.clear_guards()
        scene.sword_drawn = True
        scene.held_directions = [-1]
        scene.sample_keyboard()
        scene.in_animation_tick = True
        scene.start_sword_action("sword_sheathe")
        for _ in range(25):
            self.tick()
            if not scene.sword_sheathing:
                break
        self.assertTrue(scene.run_active)
        self.assertFalse(scene.sword_drawn)
        self.assertEqual(scene.action, 1)

    def test_buffered_running_jump_matches_held_repeat_with_real_rooftop_physics(self):
        scene = self.scene

        def replay(facing, queued_pose=None, held=False):
            direction = 1 if facing else -1
            scene.jump_to_room(1, row=1, x=120 if facing else 430, facing=facing)
            scene.peaceful = True
            self.clear_guards()
            scene.in_animation_tick = True
            scene.horizontal_key(None, direction, True)
            for _ in range(20):
                self.tick()
                if scene.action == 7:
                    break
            self.assertEqual(scene.action, 7)
            scene.up_key(None)
            self.tick()
            self.assertEqual((scene.sequence_state.sequence_id, scene.action), (4, 34))
            if queued_pose is not None:
                scene.set_key_state("up", False)
            trace = []
            queued = False
            for index in range(13):
                if (not queued and queued_pose == scene.action
                        and scene.sequence_state.sequence_id == 4):
                    scene.up_key(None)
                    queued = True
                    if not held:
                        scene.set_key_state("up", False)
                trace.append((scene.room_id, scene.terrain_motion.row,
                              scene.sequence_state.sequence_id, scene.action,
                              scene.player_x, scene.sequence_state.current_y))
                self.assertFalse(scene.terrain_motion.falling)
                self.assertFalse(scene.terrain_motion.dead)
                if index < 12:
                    self.tick()
            self.assertEqual([frame[3] for frame in trace], [*range(34, 45), 7, 34])
            self.assertIsNone(scene.pending_action)
            return trace

        for facing in (0, 1):
            baseline = replay(facing)
            for pose in (34, 38, 41, 44):
                for held in (False, True):
                    with self.subTest(facing=facing, pose=pose, held=held):
                        self.assertEqual(replay(facing, pose, held), baseline)

    def test_short_sheath_keeps_its_native_poses_before_buffered_run(self):
        scene = self.scene
        scene.jump_to_screen("2")
        self.clear_guards()
        scene.sword_drawn = True
        scene.in_animation_tick = True
        scene.start_sword_action("sword_sheathe", sequence_id=93)
        scene.horizontal_key(None, -1, True)
        actions = []
        for _ in range(10):
            self.tick()
            actions.append(scene.action)
            if not scene.sword_sheathing:
                break
        self.assertEqual(actions, [234, 236, 238, 240, 134, 1])
        self.assertTrue(scene.run_active)

    def test_long_sheath_resumes_held_run_at_native_pose_48(self):
        scene = self.scene
        self.place(1, 1, 320, facing=0)
        self.clear_guards()
        scene.sword_drawn = True
        scene.in_animation_tick = True
        scene.start_sword_action("sword_sheathe", sequence_id=92)
        scene.horizontal_key(None, -1, True)
        actions = []
        for _ in range(25):
            self.tick()
            actions.append(scene.action)
            if not scene.sword_sheathing:
                break
        self.assertEqual(actions, [*range(233, 241), 133, 133, 134, 134, 134, 48, 1])
        self.assertTrue(scene.run_active)
        self.assertFalse(scene.sword_drawn)
        self.assertEqual(scene.player_x, 320 + 10 + 9 + 2 - 3)

    def test_direction_released_during_sheath_is_not_relatched_from_old_hold(self):
        scene = self.scene
        scene.jump_to_screen("2")
        self.clear_guards()
        scene.sword_drawn = True
        scene.held_directions = [-1]
        scene.sample_keyboard()
        scene.in_animation_tick = True
        scene.start_sword_action("sword_sheathe")
        self.tick(5)
        scene.horizontal_key(None, -1, False)
        self.tick(20)
        self.assertFalse(scene.run_active)
        self.assertEqual(scene.action, 15)

    def test_building_climb_works_after_running_to_the_wall(self):
        scene = self.scene
        scene.jump_to_screen("5")
        self.clear_guards()
        scene.in_animation_tick = True
        scene.horizontal_key(None, -1, True)
        self.tick(60)
        scene.horizontal_key(None, -1, False)
        self.tick(15)
        scene.shift_held = True
        scene.up_key(None)
        scene.start_jump_if_needed()
        actions = [scene.action]
        for _ in range(35):
            self.tick()
            actions.append(scene.action)
        self.assertIn(67, actions)
        self.assertIn(135, actions)
        self.assertEqual(scene.terrain_motion.row, 0)
        self.assertFalse(scene.terrain_motion.falling)
        self.assertFalse(scene.terrain_motion.dead)

    def test_building_junction_remains_a_solid_lower_floor_after_a_running_bump(self):
        scene = self.scene
        scene.jump_to_room(9, row=1, x=300, facing=0)
        self.clear_guards()
        scene.horizontal_key(None, -1, True)
        actions = []
        for _ in range(80):
            self.tick()
            actions.append(scene.action)
            self.assertEqual((scene.room_id, scene.terrain_motion.row), (9, 1))
            self.assertEqual(scene.sequence_state.current_y, 0)
            self.assertFalse(scene.terrain_motion.falling)
            self.assertGreaterEqual(scene.player_bounds()[0], 225)
        self.assertIn(50, actions)
        self.assertNotIn(102, actions)
        scene.horizontal_key(None, -1, False)
        self.tick(10)
        self.assertEqual((scene.room_id, scene.terrain_motion.row), (9, 1))
        self.assertEqual(scene.sequence_state.current_y, 0)
        self.assertFalse(scene.terrain_motion.falling)
        self.assertFalse(scene.terrain_motion.dead)

    def test_junction_climbs_with_up_alone_after_a_solid_wall_bump(self):
        scene = self.scene
        scene.jump_to_room(9, row=1, x=300, facing=0)
        self.clear_guards()
        scene.horizontal_key(None, -1, True)
        self.tick(30)
        scene.horizontal_key(None, -1, False)
        self.tick(10)
        scene.set_key_state("up", True)
        actions = []
        for _ in range(40):
            self.tick()
            actions.append(scene.action)
            self.assertFalse(scene.terrain_motion.falling)
            self.assertFalse(scene.terrain_motion.dead)
        self.assertIn(135, actions)
        self.assertEqual(scene.terrain_motion.row, 0)

    def test_wall_supported_hang_settles_without_swinging_or_timing_out(self):
        scene = self.scene
        self.place(3, 1, 408, facing=0)
        self.clear_guards()
        scene.shift_held = True
        scene.in_animation_tick = True
        self.assertTrue(scene.start_native_descent())
        settling = []
        for _ in range(20):
            self.tick()
            if scene.sequence_state.sequence_id == 25:
                settling.append(scene.action)
        self.assertEqual(settling[:6], [92, 93, 93, 92, 92, 91])
        self.assertEqual((scene.sequence_state.sequence_id, scene.action), (25, 91))
        anchor = scene.player_x
        settled_image = scene.native_viewport.tobytes()
        for _ in range(65):
            self.tick()
            self.assertTrue(scene.native_ledge)
            self.assertFalse(scene.terrain_motion.falling)
            self.assertEqual((scene.sequence_state.sequence_id, scene.action, scene.player_x),
                             (25, 91, anchor))
            self.assertEqual(scene.native_viewport.tobytes(), settled_image)

    def test_wall_supported_catches_play_native_settle_in_both_directions(self):
        from scene_prototype import BufferedCommand

        scene = self.scene
        scene.advance_animation_now = lambda: None
        scene.set_peaceful(True)
        for room, x, facing, direction in ((2, 140, 1, 1), (0, 345, 0, -1)):
            with self.subTest(facing=facing):
                scene.jump_to_room(room, 1, x, facing=facing)
                scene.in_animation_tick = True
                scene.shift_held = True
                scene.dispatch_jump(BufferedCommand("jump", direction))
                settling = []
                for _ in range(45):
                    self.tick()
                    if scene.sequence_state.sequence_id == 25:
                        settling.append(scene.action)
                self.assertEqual(settling[:6], [92, 93, 93, 92, 92, 91])
                self.assertEqual(set(settling[6:]), {91})
                self.assertTrue(scene.native_ledge)
                self.assertFalse(scene.terrain_motion.falling)
                self.assertEqual(scene.sequence_state.sequence_mode, 0)

    def test_free_air_hang_still_times_out_at_the_original_sequence_mode(self):
        scene = self.scene
        self.place(3, 2, 75, facing=0)
        self.clear_guards()
        scene.shift_held = True
        scene.in_animation_tick = True
        scene._begin_native_ledge(9)
        self.tick(40)
        self.assertTrue(scene.native_ledge)
        for _ in range(20):
            self.tick()
            if not scene.native_ledge:
                break
        self.assertFalse(scene.native_ledge)
        self.assertTrue(scene.terrain_motion.falling)

    def test_up_alone_climbs_a_wall_supported_hang_before_shift_release(self):
        scene = self.scene
        self.place(3, 1, 408, facing=0)
        self.clear_guards()
        scene.shift_held = True
        scene.in_animation_tick = True
        scene.start_native_descent()
        self.tick(20)
        scene.shift_held = False
        scene.up_held = True
        for _ in range(25):
            self.tick()
            if not scene.native_ledge:
                break
        scene.up_held = False
        self.assertEqual((scene.terrain_motion.row, scene.action), (1, 15))
        self.assertFalse(scene.terrain_motion.falling)
        self.assertFalse(scene.native_ledge)

    def test_building_junction_uses_real_upper_ledge_and_climb_rows(self):
        scene = self.scene
        scene.jump_to_room(9, row=1, x=240, facing=0)
        self.clear_guards()
        scene.in_animation_tick = True
        scene.up_held = True
        scene.shift_held = False
        self.assertTrue(scene.start_upper_ledge_jump())
        actions = []
        for _ in range(33):
            self.tick()
            actions.append(scene.action)
        self.assertEqual(actions[:15], [*range(67, 81), 91])
        self.assertEqual(actions[15:22], [*range(135, 142)])
        self.assertEqual((scene.terrain_motion.row, scene.action), (0, 15))
        self.assertFalse(scene.native_ledge)
        self.assertFalse(scene.terrain_motion.falling)
        scene.shift_held = scene.up_held = False
        self.tick(3)
        self.assertFalse(scene.terrain_motion.falling)

    def test_real_junction_climb_hides_head_and_arm_but_not_body_on_shaded_side(self):
        scene = self.scene
        scene.jump_to_room(9, row=1, x=240, facing=0)
        self.clear_guards()
        scene.set_key_state("up", True)
        for _ in range(25):
            self.tick()
            if scene.action == 140:
                break
        self.assertEqual(scene.action, 140)
        self.assertEqual(scene.terrain_motion.row, 1)
        left, top, _, _ = scene.player_bounds()
        sprite = scene.player_sprite()
        scenery = scene.room_cache[9].flattened()
        for point in ((205, 86), (212, 104)):
            x, y = point
            self.assertEqual(sprite.getpixel((x - left, y - top))[3], 255)
            self.assertEqual(scene.native_viewport.getpixel((x + ROOM_ORIGIN_X, y)),
                             scenery.getpixel(point))
        for x, y in ((232, 117), (233, 126)):
            color = sprite.getpixel((x - left, y - top))
            self.assertEqual(color[3], 255)
            self.assertEqual(scene.native_viewport.getpixel((x + ROOM_ORIGIN_X, y)), color)

    def test_shift_catch_needs_a_real_ledge_and_respects_grip_delay(self):
        scene = self.scene
        scene.jump_to_room(9, row=1, x=250, facing=0)
        self.clear_guards()
        state = scene.sequence_state
        state.current_y = -24
        state.action = 106
        self.assertTrue(scene.level_map.catch_ledge(9, 1, state, scene.frames[106]))
        scene.player_x = state.target_x
        scene.in_animation_tick = True
        scene._begin_native_ledge(15)
        scene.shift_held = scene.up_held = True
        self.tick(12)
        self.assertFalse(scene.ledge_climbing)
        self.tick(2)
        self.assertTrue(scene.ledge_climbing)
        self.place(3, 1, 300, facing=1)
        state.action, state.current_y = 106, -24
        self.assertFalse(scene.level_map.catch_ledge(3, 1, state, scene.frames[106]))

    def test_jump_across_gap_catches_and_climbs_only_the_real_landing_edge(self):
        from scene_prototype import BufferedCommand

        scene = self.scene
        self.place(0, 1, 345, facing=0)
        self.clear_guards()
        scene.in_animation_tick = True
        scene.shift_held = True
        scene.dispatch_jump(BufferedCommand("jump", -1))
        for _ in range(25):
            self.tick()
            if scene.native_ledge:
                break
        self.assertTrue(scene.native_ledge)
        self.assertEqual(scene.sequence_state.sequence_id, 15)
        self.assertEqual(scene.terrain_motion.row, 2)
        self.assertFalse(scene.terrain_motion.falling)
        scene.up_key(None)
        self.tick(35)
        self.assertEqual(scene.terrain_motion.row, 1)
        self.assertFalse(scene.native_ledge)
        self.assertFalse(scene.terrain_motion.falling)

    def test_right_facing_gap_catch_hides_body_behind_near_facade_like_mac_video(self):
        from PIL import ImageChops, ImageOps
        from scene_prototype import BufferedCommand
        from render_opening import ROOM_ORIGIN_X

        scene = self.scene
        self.place(0, 1, 170, facing=1)
        self.clear_guards()
        scene.in_animation_tick = True
        scene.shift_held = True
        scene.dispatch_jump(BufferedCommand("jump", 1))
        for _ in range(25):
            self.tick()
            if scene.native_ledge:
                break
        self.assertTrue(scene.native_ledge)
        self.tick(20)
        self.assertEqual((scene.action, scene.sequence_state.sequence_id), (91, 25))
        sprite = ImageOps.mirror(scene.player_sprite())
        left, top, right, bottom = scene.player_bounds()
        room = scene.room_cache[0]
        scenery = room.flattened()
        restored = 0
        for y in range(sprite.height):
            for x in range(sprite.width):
                px, py = left + x, top + y
                color = sprite.getpixel((x, y))
                if color[3] == 255 and py > 245:
                    self.assertEqual(scene.native_viewport.getpixel((px + ROOM_ORIGIN_X, py)),
                                     scenery.getpixel((px, py)))
                    restored += 1
        self.assertGreater(restored, 100)
        difference = ImageChops.difference(scene.native_viewport.crop(
            (ROOM_ORIGIN_X, 0, ROOM_ORIGIN_X + 510, 365)).convert("RGB"), scenery.convert("RGB"))
        outside = difference.copy()
        outside.paste(0, (left, top, right + 1, bottom + 1))
        self.assertIsNone(outside.getbbox())

    def test_jump_to_near_facade_keeps_occlusion_before_the_catch(self):
        from PIL import Image, ImageChops
        from render_opening import ROOM_WIDTH, ROOM_HEIGHT, add_alpha

        scene = self.scene
        scene.advance_animation_now = lambda: None
        scene.set_peaceful(True)
        for room_id, start_x in ((2, 140), (0, 170)):
            for offset in (-4, 0, 4):
                for shift_at in (0, 12, None):
                    with self.subTest(room=room_id, offset=offset, shift_at=shift_at):
                        scene.jump_to_room(room_id, row=1, x=start_x + offset, facing=1)
                        scene.in_animation_tick = True
                        if shift_at == 0:
                            scene.set_key_state("shift", True)
                        # Use both real key handlers, not a fabricated caught pose.
                        scene.up_key(None)
                        scene.horizontal_key(None, 1, True)
                        room = scene.room_cache[room_id]
                        facade = Image.new("L", (ROOM_WIDTH, ROOM_HEIGHT))
                        for piece in room.pieces:
                            if piece.row == 1 and (piece.kind == 1 or piece.decoration):
                                add_alpha(facade, piece.alpha, piece.x, piece.y)
                            elif piece.row == 2 and piece.kind == 20:
                                add_alpha(facade, piece.alpha, piece.x, piece.y)
                        falling_poses, caught_poses, climb_poses = set(), set(), set()
                        for frame in range(50):
                            if frame == 2:
                                scene.set_key_state("up", False)
                                scene.horizontal_key(None, 1, False)
                            if frame == shift_at:
                                scene.set_key_state("shift", True)
                            if frame == 30 and scene.native_ledge:
                                scene.up_key(None)
                            if scene.ledge_climbing:
                                scene.set_key_state("up", False)
                            self.tick()
                            if scene.terrain_motion.falling and scene.action in range(102, 107):
                                falling_poses.add(scene.action)
                            if scene.native_ledge:
                                if 135 <= scene.action < 149:
                                    climb_poses.add(scene.action)
                                else:
                                    caught_poses.add(scene.action)
                            actual = scene.native_viewport.crop(
                                (ROOM_ORIGIN_X, 0, ROOM_ORIGIN_X + ROOM_WIDTH, ROOM_HEIGHT))
                            difference = ImageChops.difference(actual.convert("RGB"),
                                                              room.flattened().convert("RGB"))
                            with self.subTest(frame=frame, pose=scene.action):
                                self.assertIsNone(ImageChops.multiply(
                                    difference.convert("L"), facade).getbbox())
                        self.assertEqual(falling_poses, set(range(102, 107)))
                        if shift_at is not None:
                            self.assertTrue({80, 91, 92}.issubset(caught_poses))
                            self.assertEqual(climb_poses, set(range(135, 149)))
                            self.assertEqual(scene.terrain_motion.row, 1)
                            self.assertFalse(scene.terrain_motion.falling)
                        else:
                            self.assertFalse(caught_poses)
                            self.assertFalse(climb_poses)
                            self.assertTrue(scene.terrain_motion.dead)

    def test_near_facade_stays_in_front_through_every_catch_and_climb_pose(self):
        from PIL import Image, ImageChops
        from render_opening import ROOM_WIDTH, ROOM_HEIGHT, add_alpha
        from scene_prototype import BufferedCommand

        scene = self.scene
        scene.advance_animation_now = lambda: None
        scene.set_peaceful(True)
        for room_id, start_x in ((2, 140), (0, 170)):
            with self.subTest(room=room_id):
                scene.jump_to_room(room_id, row=1, x=start_x, facing=1)
                scene.in_animation_tick = True
                scene.shift_held = True
                scene.dispatch_jump(BufferedCommand("jump", 1))
                for _ in range(30):
                    self.tick()
                    if scene.native_ledge:
                        break
                self.assertTrue(scene.native_ledge)
                self.tick(20)
                self.assertEqual(scene.action, 91)
                room = scene.room_cache[room_id]
                facade = Image.new("L", (ROOM_WIDTH, ROOM_HEIGHT))
                for piece in room.pieces:
                    if piece.row == 1 and (piece.kind == 1 or piece.decoration):
                        add_alpha(facade, piece.alpha, piece.x, piece.y)
                    elif piece.row == 2 and piece.kind == 20:
                        add_alpha(facade, piece.alpha, piece.x, piece.y)
                poses = set()
                scene.up_held = True
                for _ in range(35):
                    self.tick()
                    if 135 <= scene.action < 149:
                        poses.add(scene.action)
                        actual = scene.native_viewport.crop(
                            (ROOM_ORIGIN_X, 0, ROOM_ORIGIN_X + ROOM_WIDTH, ROOM_HEIGHT))
                        difference = ImageChops.difference(actual.convert("RGB"),
                                                          room.flattened().convert("RGB"))
                        with self.subTest(room=room_id, pose=scene.action):
                            self.assertIsNone(ImageChops.multiply(
                                difference.convert("L"), facade).getbbox())
                            if scene.action >= 138:
                                self.assertIsNotNone(difference.getbbox())
                    if not scene.native_ledge:
                        break
                self.assertEqual(poses, set(range(135, 149)))
                self.assertEqual(scene.terrain_motion.row, 1)
                self.assertFalse(scene.terrain_motion.falling)

    def test_releasing_upper_jump_cannot_leave_a_shift_step_inside_the_junction(self):
        scene = self.scene
        for released_after in (1, 3, 9, 14):
            with self.subTest(released_after=released_after):
                scene.jump_to_room(9, row=1, x=240, facing=0)
                self.clear_guards()
                scene.set_key_state("up", True)
                self.tick(released_after)
                scene.set_key_state("up", False)
                self.tick(45)
                self.assertFalse(scene.native_ledge)
                self.assertFalse(scene.terrain_motion.falling)
                self.assertEqual((scene.room_id, scene.terrain_motion.row), (9, 1))
                scene.set_key_state("shift", True)
                scene.horizontal_key(None, -1, True)
                for _ in range(70):
                    self.tick()
                    self.assertGreaterEqual(scene.player_bounds()[0], 225)
                    self.assertFalse(scene.terrain_motion.falling)
                scene.clear_keys(None)

    def test_near_facade_stays_in_front_during_descent_and_reclimb(self):
        from PIL import Image, ImageChops
        from render_opening import ROOM_WIDTH, ROOM_HEIGHT, add_alpha

        scene = self.scene
        scene.advance_animation_now = lambda: None
        scene.set_peaceful(True)
        for room_id, x in ((2, 304), (0, 355)):
            with self.subTest(room=room_id):
                scene.jump_to_room(room_id, row=1, x=x, facing=1)
                scene.in_animation_tick = True
                scene.shift_held = True
                self.assertTrue(scene.start_native_descent())
                room = scene.room_cache[room_id]
                facade = Image.new("L", (ROOM_WIDTH, ROOM_HEIGHT))
                for piece in room.pieces:
                    if piece.row == 1 and (piece.kind == 1 or piece.decoration):
                        add_alpha(facade, piece.alpha, piece.x, piece.y)
                    elif piece.row == 2 and piece.kind == 20:
                        add_alpha(facade, piece.alpha, piece.x, piece.y)
                for climbing in (False, True):
                    scene.up_held = climbing
                    poses = set()
                    for _ in range(40):
                        self.tick()
                        if 135 <= scene.action < 149:
                            poses.add(scene.action)
                            actual = scene.native_viewport.crop(
                                (ROOM_ORIGIN_X, 0, ROOM_ORIGIN_X + ROOM_WIDTH, ROOM_HEIGHT))
                            difference = ImageChops.difference(actual.convert("RGB"),
                                                              room.flattened().convert("RGB"))
                            with self.subTest(room=room_id, climbing=climbing, pose=scene.action):
                                self.assertIsNone(ImageChops.multiply(
                                    difference.convert("L"), facade).getbbox())
                        if (scene.action == 15 if climbing else
                                scene.sequence_state.sequence_id == 25 and scene.action == 91):
                            break
                    # Native SEQS:68 deliberately omits five climb poses.
                    expected = (set(range(135, 149)) if climbing else
                                {148, 145, 144, 143, 142, 141, 140, 138, 136})
                    self.assertEqual(poses, expected)
                    self.assertFalse(scene.terrain_motion.falling)
                    self.assertEqual(scene.terrain_motion.row, 1 if climbing else 2)

    def test_right_facing_catch_on_third_screen_stays_at_the_roof_edge(self):
        from scene_prototype import BufferedCommand

        scene = self.scene
        self.place(2, 1, 140, facing=1)
        self.clear_guards()
        scene.in_animation_tick = True
        scene.shift_held = True
        scene.dispatch_jump(BufferedCommand("jump", 1))
        for _ in range(25):
            self.tick()
            if scene.native_ledge:
                break
        self.assertTrue(scene.native_ledge)
        self.assertEqual((scene.action, scene.player_x, scene.terrain_motion.row), (80, 285, 2))
        self.tick(20)
        self.assertEqual((scene.action, scene.player_x), (91, 281))
        scene.up_held = True
        for _ in range(30):
            self.tick()
            if not scene.native_ledge:
                break
        scene.up_held = False
        self.assertEqual(scene.terrain_motion.row, 1)
        self.assertFalse(scene.terrain_motion.falling)
        self.assertLess(scene.player_x, 340)

    def test_hanging_does_not_queue_unrelated_horizontal_or_delayed_jump_inputs(self):
        scene = self.scene
        self.place(3, 1, 408, facing=0)
        self.clear_guards()
        scene.shift_held = True
        scene.in_animation_tick = True
        scene.start_native_descent()
        scene.horizontal_key(None, -1, True)
        self.assertIsNone(scene.pending_action)
        scene.up_held = True
        scene.start_jump_if_needed()
        self.assertEqual(scene.sequence_state.sequence_id, 68)
        self.assertIsNone(scene.pending_action)

    def test_upper_guard_uses_generator_alternate_floor_and_lands_to_pursue(self):
        scene = self.scene
        scene.jump_to_room(9, row=1, x=450, facing=1)
        scene.combat.guard.life = 0
        source_guard = scene.combat.guard
        generated = None
        jumped = False
        for _ in range(60):
            self.tick()
            generated = next((guard for guard in scene.combat.guards
                              if guard is not source_guard), generated)
            if generated is not None:
                jumped |= generated.state.sequence_id == 100
                if jumped and generated.row == 1 and not generated.terrain_motion.falling:
                    break
        self.assertIsNotNone(generated)
        self.assertEqual(generated.alternate_row, 1)
        self.assertTrue(jumped)
        self.assertEqual(generated.row, 1)
        self.assertFalse(generated.terrain_motion.falling)
        self.assertTrue(generated.alive)
