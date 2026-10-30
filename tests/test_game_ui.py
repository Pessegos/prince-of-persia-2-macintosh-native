import unittest
from unittest.mock import patch

from PIL import ImageTk

from pop2.game_ui import fit_viewport
from pop2.render_opening import ROOM_ORIGIN_X
from pop2.scene_prototype import IDLE_SEQUENCE, animation_interval_for_frame
import tests.test_terrain as test_terrain


class ViewportTests(unittest.TestCase):
    def test_aspect_fit_centers_without_stretching(self):
        self.assertEqual(fit_viewport(1920, 1080), ((1434, 1080), (243, 0)))
        self.assertEqual(fit_viewport(1280, 720), ((956, 720), (162, 0)))
        self.assertEqual(fit_viewport(800, 900), ((800, 602), (0, 149)))
        self.assertEqual(fit_viewport(3440, 1440), ((1912, 1440), (764, 0)))
        self.assertEqual(fit_viewport(2560, 1070), ((1421, 1070), (569, 0)))
        self.assertEqual(fit_viewport(1020, 768), ((1020, 768), (0, 0)))


class GameWindowTests(unittest.TestCase):
    setUp = test_terrain.RooftopSceneTests.setUp
    place = test_terrain.RooftopSceneTests.place
    tick = test_terrain.RooftopSceneTests.tick

    def control_key(self, key, pressed=True):
        from types import SimpleNamespace

        scene = self.scene
        event = SimpleNamespace(keysym=key, state=0, char="")
        result = (scene.dev_key_press if pressed else scene.dev_key_release)(event)
        if result is None:
            if key in ("Left", "Right"):
                scene.horizontal_key(event, -1 if key == "Left" else 1, pressed)
            elif key == "Up" and pressed:
                scene.up_key(event)
            elif key == "Escape":
                (scene.escape_key if pressed else scene.escape_release)(event)
            else:
                name = key.lower().split('_')[0]
                scene.set_key_state("ctrl" if name == "control" else name, pressed)
        return result

    def test_live_prince_and_health_art_use_the_original_rooftop_palette(self):
        from pop2.render_opening import decode_ctbl, decode_shap

        scene = self.scene
        expected = decode_ctbl(scene.kid["CTBL"][25005]["data"])
        self.assertEqual(scene.sequence_state.level_kind, 5)
        self.assertEqual(scene.palette, expected)
        self.assertEqual(scene.palette[5], (17, 17, 28, 255))
        self.assertEqual(scene.palette[7], (220, 128, 48, 255))
        sprite = scene.player_sprite()
        colors = {color for _count, color in sprite.getcolors(sprite.width * sprite.height)}
        self.assertIn((17, 17, 28, 255), colors)
        self.assertNotIn((46, 46, 48, 255), colors)
        for index, icon in scene.health_art.icons.items():
            original = decode_shap(scene.kid["SHAP"][scene.first_shape_id + index]["data"], expected)
            self.assertEqual(icon.tobytes(), original.tobytes())

    def clear_guards(self):
        self.scene.combat.guards.clear()
        self.scene.combat.guard = None
        self.scene.combat.generation_points.clear()

    def prepare_guard_jump(self, facing, running):
        from pop2.combat import select_sequence
        from pop2.scene_prototype import BufferedCommand

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
        from pop2.render_opening import ROOM_ORIGIN_X, ROOM_WIDTH, ROOM_HEIGHT, add_alpha

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
        with patch("pop2.scene_prototype.time.perf_counter", return_value=100):
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
        self.assertIn((253, 255, 168, 255), colors)
        pause_colors = {color for _count, color in scene.pause_text.getcolors() if color[3]}
        restart_colors = {color for _count, color in scene.restart_text.getcolors() if color[3]}
        self.assertEqual(pause_colors, restart_colors)
        last_guard_at = scene.combat.last_guard_at
        scene.escape_release()
        with patch("pop2.scene_prototype.time.perf_counter", return_value=120):
            scene.escape_key()
        self.assertFalse(scene.paused)
        self.assertEqual(scene.combat.last_guard_at, last_guard_at + 20)

    def test_horizontal_resume_hold_starts_moving_without_a_second_press(self):
        from types import SimpleNamespace

        scene = self.scene
        for direction, key in ((-1, "Left"), (1, "Right")):
            with self.subTest(direction=direction):
                scene.jump_to_room(9, row=1, x=320, facing=int(direction > 0))
                self.clear_guards()
                scene.set_paused(True)
                x = scene.player_x
                event = SimpleNamespace(keysym=key, state=0, char="")
                self.assertIsNone(scene.dev_key_press(event))
                # Tk forwards the same event to the ordinary root binding.
                scene.horizontal_key(event, direction, True)
                self.assertFalse(scene.paused)
                self.assertEqual(scene.held_directions, [direction])
                self.tick(6)
                self.assertGreater((scene.player_x - x) * direction, 20)
                self.assertIsNone(scene.dev_key_press(event))
                scene.horizontal_key(event, direction, True)
                self.assertEqual(scene.held_directions, [direction])
                self.assertIsNone(scene.dev_key_release(event))
                scene.horizontal_key(event, direction, False)
                self.assertEqual(scene.held_directions, [])

    def test_pause_resume_horizontal_jump_chord_works_in_both_key_orders(self):
        scene = self.scene
        for facing, arrow in ((0, "Left"), (1, "Right")):
            for up_first in (False, True):
                with self.subTest(facing=facing, up_first=up_first):
                    scene.jump_to_room(9, row=1, x=330, facing=facing)
                    self.clear_guards()
                    scene.set_paused(True)
                    keys = ("Up", arrow) if up_first else (arrow, "Up")
                    self.assertIsNone(self.control_key(keys[0]))
                    self.assertIsNone(self.control_key(keys[1]))
                    scene.start_jump_if_needed()
                    self.assertFalse(scene.paused)
                    self.assertEqual(scene.sequence_state.sequence_id, 3)
                    self.assertEqual(scene.up_held, True)
                    self.assertEqual(scene.horizontal_input, 1 if facing else -1)
                    self.control_key("Up", False)
                    self.control_key(arrow, False)

    def test_up_resume_can_hold_repeat_and_release_without_an_extra_jump(self):
        scene = self.scene
        scene.jump_to_room(9, row=1, x=330, facing=1)
        self.clear_guards()
        scene.set_paused(True)
        self.control_key("Up")
        scene.start_jump_if_needed()
        starts = 0
        for _ in range(90):
            self.tick()
            starts += scene.action == 67
        self.assertGreaterEqual(starts, 2)
        self.assertTrue(scene.up_held)
        self.control_key("Up", False)
        for _ in range(40):
            self.tick()
        self.assertEqual(scene.action, 15)
        self.assertFalse(scene.jump_repeat_armed)

    def test_up_already_held_before_escape_pause_keeps_its_repeat_state(self):
        scene = self.scene
        scene.jump_to_room(9, row=1, x=330, facing=1)
        self.clear_guards()
        self.control_key("Up")
        scene.start_jump_if_needed()
        self.tick(6)
        before = (scene.action, scene.jump_started_for_press, scene.jump_repeat_armed)
        self.control_key("Escape")
        self.control_key("Escape", False)
        self.assertEqual(self.control_key("Up"), "break")
        self.tick(5)
        self.assertTrue(scene.paused)
        self.assertEqual((scene.action, scene.jump_started_for_press, scene.jump_repeat_armed), before)
        self.control_key("Escape")
        self.control_key("Escape", False)
        starts = 0
        for _ in range(90):
            self.tick()
            starts += scene.action == 67
        self.assertGreaterEqual(starts, 2)
        self.control_key("Up", False)
        self.assertFalse(scene.up_held)

    def test_paused_modifier_pair_remains_held_until_both_keys_are_released(self):
        scene = self.scene
        scene.jump_to_room(9, row=1, x=330, facing=1)
        self.clear_guards()
        scene.set_paused(True)
        self.control_key("Shift_L")
        self.control_key("Shift_R")
        self.control_key("Shift_L", False)
        self.assertTrue(scene.shift_held)
        self.control_key("Shift_R", False)
        self.assertFalse(scene.shift_held)
        self.assertTrue(scene.paused)

    def test_down_resume_can_descend_a_real_ledge_with_paused_shift_held(self):
        scene = self.scene
        scene.jump_to_room(9, row=0, x=214, facing=0)
        self.clear_guards()
        scene.set_paused(True)
        self.assertEqual(self.control_key("Shift_L"), "break")
        self.assertTrue(scene.paused)
        self.assertTrue(scene.shift_held)
        self.assertIsNone(self.control_key("Down"))
        self.assertTrue(scene.native_ledge)
        self.assertTrue(scene.down_held)
        self.tick(25)
        self.assertTrue(scene.ledge_hanging)
        self.assertFalse(scene.terrain_motion.falling)

    def test_pause_keeps_a_held_ledge_and_tracks_shift_release_or_repress(self):
        from pop2.scene_prototype import BufferedCommand

        scene = self.scene
        for release_shift, repress_shift in ((False, False), (True, False), (True, True)):
            with self.subTest(release_shift=release_shift, repress_shift=repress_shift):
                scene.jump_to_room(2, row=1, x=140, facing=1)
                self.clear_guards()
                state = scene.sequence_state
                scene.in_animation_tick = True
                self.control_key("Shift_L")
                scene.dispatch_jump(BufferedCommand("jump", 1))
                for _ in range(50):
                    self.tick()
                    if scene.sequence_state.sequence_id == 25 and scene.action == 91:
                        break
                self.assertTrue(scene.ledge_hanging)
                frozen = state.__dict__.copy()
                self.control_key("Escape")
                self.control_key("Escape", False)
                self.assertTrue(scene.paused)
                if release_shift:
                    self.control_key("Shift_L", False)
                if repress_shift:
                    self.control_key("Shift_L")
                self.tick(5)
                self.assertEqual(state.__dict__, frozen)
                self.control_key("Escape")
                self.control_key("Escape", False)
                self.assertFalse(scene.paused)
                self.tick(2)
                if release_shift and not repress_shift:
                    self.assertFalse(scene.native_ledge)
                    self.assertTrue(scene.terrain_motion.falling)
                else:
                    self.assertTrue(scene.native_ledge)
                    self.assertFalse(scene.terrain_motion.falling)
                    self.assertTrue(scene.shift_held)
                    self.control_key("Shift_L", False)
                    self.assertFalse(scene.shift_held)
                    self.tick(2)
                    self.assertTrue(scene.terrain_motion.falling)

    def test_release_during_pause_does_not_restore_stale_run_or_up_holds(self):
        scene = self.scene
        scene.jump_to_room(9, row=1, x=330, facing=1)
        self.clear_guards()
        self.control_key("Right")
        scene.step_warning_direction = 1
        scene.set_paused(True)
        self.control_key("Right", False)
        self.assertEqual(scene.step_warning_direction, 0)
        self.control_key("Shift_L")
        self.control_key("Control_L")
        self.control_key("Control_L", False)
        self.control_key("Escape")
        self.control_key("Escape", False)
        self.assertEqual(scene.horizontal_input, 0)
        self.assertFalse(scene.ctrl_held)
        self.assertFalse(scene.up_held)
        self.tick(20)
        self.assertFalse(scene.run_active)

    def test_ctrl_held_during_pause_is_buffered_only_after_explicit_resume(self):
        scene = self.scene
        scene.jump_to_room(9, row=1, x=330, facing=1)
        self.clear_guards()
        scene.set_paused(True)
        frozen = scene.sequence_state.__dict__.copy()
        self.assertEqual(self.control_key("Control_L"), "break")
        self.assertEqual(scene.sequence_state.__dict__, frozen)
        self.assertTrue(scene.paused)
        self.control_key("Escape")
        self.control_key("Escape", False)
        self.tick()
        self.assertEqual(scene.sequence_state.sequence_id, 55)
        self.assertTrue(scene.sword_drawn)

    def test_focus_loss_during_pause_discards_the_frozen_holds(self):
        from types import SimpleNamespace

        scene = self.scene
        scene.jump_to_room(9, row=1, x=330, facing=1)
        self.clear_guards()
        self.control_key("Right")
        scene.set_paused(True)
        scene.clear_keys(SimpleNamespace())
        self.assertFalse(scene.shift_held)
        self.assertEqual(scene.window_keys_down, set())
        self.control_key("Escape")
        self.control_key("Escape", False)
        self.tick(20)
        self.assertFalse(scene.run_active)
        self.assertEqual(scene.horizontal_input, 0)

    def test_held_up_after_junction_climb_starts_another_jump(self):
        scene = self.scene
        scene.jump_to_room(9, row=1, x=240, facing=0)
        self.clear_guards()
        scene.in_animation_tick = True
        scene.up_held = True
        scene.start_jump()
        self.assertTrue(scene.native_ledge)
        for _ in range(40):
            self.tick()
            if not scene.native_ledge:
                break
        self.assertEqual((scene.action, scene.terrain_motion.row), (15, 0))
        self.assertTrue(scene.jump_repeat_armed)
        self.tick()
        self.assertIn(scene.sequence_state.sequence_id, (14, 24, 28))
        self.assertEqual(scene.action, 67)
        self.assertTrue(scene.up_held)

    def test_rooftop_drift_then_released_run_chord_has_no_standing_jump_break(self):
        scene = self.scene
        traces = []
        for up_first in (False, True):
            with self.subTest(up_first=up_first):
                scene.jump_to_room(3, row=1, x=245, facing=1)
                scene.set_peaceful(True)
                scene.in_animation_tick = True
                scene.horizontal_key(None, 1, True)
                self.tick(7)
                self.assertEqual(scene.action, 7)
                scene.horizontal_key(None, 1, False)
                scene.horizontal_key(None, -1, True)
                self.tick()
                self.assertEqual(scene.action, 53)
                self.tick(3)
                scene.horizontal_key(None, -1, False)
                self.tick(4)
                self.assertEqual((scene.sequence_state.sequence_id, scene.action), (6, 60))
                self.assertEqual(scene.queue_grace_remaining_ms, 0)
                if up_first:
                    scene.up_key(None)
                    scene.horizontal_key(None, -1, True)
                else:
                    scene.horizontal_key(None, -1, True)
                    scene.up_key(None)
                trace = []
                for _ in range(20):
                    previous_x = scene.player_x
                    self.tick()
                    trace.append((scene.action, scene.player_x, scene.sequence_state.facing))
                    self.assertEqual(scene.room_id, 3)
                    self.assertFalse(scene.terrain_motion.falling)
                    self.assertNotEqual(scene.sequence_state.sequence_id, 3)
                    if scene.sequence_state.sequence_id == 4:
                        self.assertEqual((scene.action, scene.player_x), (34, previous_x))
                        break
                else:
                    self.fail("Recorded rooftop chord did not reach running takeoff")
                self.assertEqual([action for action, x, face in trace], [61, 62, 63, 64, 65, 13, 34])
                traces.append(trace)
        self.assertEqual(traces[0], traces[1])

    def test_rooftop_repress_during_drift_matches_continuously_held_run(self):
        scene = self.scene
        traces = []
        for released in (False, True):
            scene.jump_to_room(3, row=1, x=245, facing=1)
            scene.set_peaceful(True)
            scene.in_animation_tick = True
            scene.horizontal_key(None, 1, True)
            self.tick(7)
            scene.horizontal_key(None, 1, False)
            scene.horizontal_key(None, -1, True)
            self.tick()
            self.assertEqual(scene.action, 53)
            if released:
                scene.horizontal_key(None, -1, False)
            self.tick(5)
            self.assertEqual(scene.action, 58)
            if released:
                scene.horizontal_key(None, -1, True)
            trace = []
            for _ in range(15):
                self.tick()
                self.assertEqual(scene.room_id, 3)
                self.assertFalse(scene.terrain_motion.falling)
                trace.append((scene.sequence_state.sequence_id, scene.action,
                              scene.player_x, scene.sequence_state.facing))
            traces.append(trace)
        self.assertEqual(traces[0], traces[1])
        self.assertEqual([pose for seq, pose, x, face in traces[1]],
                         [59, 60, 61, 62, 63, 64, 65, 13, 14, 7, 8, 9, 10, 11, 12])

    def test_releasing_up_during_or_immediately_after_climb_does_not_jump(self):
        scene = self.scene
        for release_during in (False, True):
            with self.subTest(release_during=release_during):
                scene.jump_to_room(9, row=1, x=240, facing=0)
                self.clear_guards()
                scene.in_animation_tick = True
                scene.up_held = True
                scene.start_jump()
                for _ in range(40):
                    self.tick()
                    if release_during and scene.ledge_climbing and scene.up_held:
                        scene.set_key_state("up", False)
                    if not scene.native_ledge:
                        break
                self.assertEqual(scene.action, 15)
                if not release_during:
                    scene.set_key_state("up", False)
                self.tick(20)
                self.assertEqual((scene.action, scene.terrain_motion.row), (15, 0))
                self.assertFalse(scene.jump_repeat_armed)

    def test_held_up_chains_real_cavern_ledges_across_the_upper_room_link(self):
        scene = self.scene
        scene.load_level(3)
        scene.peaceful = True
        scene.jump_to_room(3, row=1, x=429, facing=0)
        scene.in_animation_tick = True
        scene.up_held = scene.shift_held = True
        scene.start_jump()
        finished = []
        for _ in range(75):
            climbing = scene.native_ledge
            self.tick()
            if climbing and not scene.native_ledge:
                self.assertEqual(scene.action, 15)
                finished.append((scene.room_id, scene.terrain_motion.row, scene.player_x))
                if len(finished) == 2:
                    break
        self.assertEqual(finished, [(3, 0, 418), (0, 2, 367)])
        scene.set_key_state("up", False)
        self.tick(20)
        self.assertEqual((scene.action, scene.room_id, scene.terrain_motion.row,
                          scene.player_x), (15, 0, 2, 367))
        self.assertFalse(scene.native_ledge)
        self.assertFalse(scene.terrain_motion.falling)

    def test_cavern_entry_accepts_horizontal_holds_through_every_turn_pose(self):
        scene = self.scene
        with patch.object(scene, 'render'):
            for direction in (-1, 1):
                for delay in range(8):
                    with self.subTest(direction=direction, delay=delay):
                        scene.load_level(3)
                        scene.peaceful = True
                        scene.in_animation_tick = True
                        self.tick(delay)
                        scene.horizontal_key(None, direction, True)
                        for _ in range(14):
                            if scene.run_active:
                                break
                            self.tick()
                        self.assertTrue(scene.run_active)
                        self.assertEqual(scene.run_direction, direction)
                        self.assertFalse(scene.native_ledge)

    def test_alt_restart_preserves_live_horizontal_holds(self):
        from types import SimpleNamespace

        scene = self.scene
        with patch.object(scene, 'render'):
            for direction, key in ((-1, 'Left'), (1, 'Right')):
                with self.subTest(direction=direction):
                    scene.load_level(3)
                    scene.peaceful = True
                    scene.jump_to_room(0, row=1, x=234, facing=int(direction > 0))
                    self.control_key(key)
                    self.tick(2)
                    event = SimpleNamespace(keysym='r', state=0x20000, char='r')
                    self.assertEqual(scene.dev_key_press(event), 'break')
                    scene.dev_key_release(event)
                    self.assertFalse(scene.paused)
                    self.assertEqual(scene.held_directions, [direction])
                    self.assertNotIn(key, scene.pause_resume_keys)
                    self.assertFalse(scene.sword_drawn)
                    for _ in range(14):
                        if scene.run_active:
                            break
                        self.tick()
                    self.assertTrue(scene.run_active)
                    self.assertEqual(scene.run_direction, direction)
                    self.control_key(key, False)
                    self.assertEqual(scene.horizontal_input, 0)

    def test_alt_restart_preserves_modifiers_and_vertical_chords(self):
        from types import SimpleNamespace

        scene = self.scene
        with patch.object(scene, 'render'):
            for modifier in ('Up', 'Shift_L'):
                with self.subTest(modifier=modifier):
                    scene.load_level(3)
                    scene.peaceful = True
                    self.control_key(modifier)
                    self.control_key('Right')
                    event = SimpleNamespace(keysym='r', state=0x20000, char='r')
                    scene.dev_key_press(event)
                    scene.dev_key_release(event)
                    self.assertEqual(scene.held_directions, [1])
                    self.assertTrue(scene.up_held if modifier == 'Up' else scene.shift_held)
                    self.assertNotIn(modifier, scene.pause_resume_keys)
                    # The restart's SEQS 5 starts with a zeroed bank (4:3e70):
                    # the live holds are bank requests, not a host slot.
                    self.assertEqual(scene.directional_input.right, -1)
                    for _ in range(10):
                        self.tick()
                        if scene.sequence_state.sequence_id != 5:
                            break
                    if modifier == 'Up':
                        self.assertEqual(scene.sequence_state.sequence_id, 3)
                    else:
                        self.assertIn(scene.sequence_state.sequence_id, range(29, 43))
                    self.control_key(modifier, False)
                    self.control_key('Right', False)

    def test_alt_restart_from_a_menu_does_not_restore_held_menu_keys(self):
        from types import SimpleNamespace

        scene = self.scene
        scene.load_level(3)
        scene.peaceful = True
        self.control_key('Right')
        scene.open_game_menu()
        event = SimpleNamespace(keysym='r', state=0x20000, char='r')
        scene.dev_key_press(event)
        scene.dev_key_release(event)
        self.assertEqual(scene.held_directions, [])
        self.assertIn('Right', scene.pause_resume_keys)
        self.tick(12)
        self.assertFalse(scene.run_active)

    def test_alt_restart_after_death_does_not_restore_the_old_movement_hold(self):
        from types import SimpleNamespace

        scene = self.scene
        scene.load_level(3)
        self.control_key('Right')
        scene.combat.player.life = 0
        scene.death.begin(0)
        event = SimpleNamespace(keysym='r', state=0x20000, char='r')
        scene.dev_key_press(event)
        scene.dev_key_release(event)
        self.assertEqual(scene.held_directions, [])
        self.assertIn('Right', scene.pause_resume_keys)
        self.assertTrue(scene.combat.player.alive)

    def test_inputs_during_climb_wait_for_the_floor_and_do_not_leave_controls_protected(self):
        scene = self.scene
        with patch.object(scene, 'render'):
            for facing in (0, 1):
                for kind in ('turn', 'sword', 'sword_held', 'crouch', 'jump'):
                    with self.subTest(facing=facing, kind=kind):
                        scene.load_level(3)
                        scene.peaceful = True
                        scene.jump_to_room(0, row=2, x=80 if facing else 330, facing=facing)
                        scene.in_animation_tick = True
                        scene.up_held = True
                        scene.start_jump()
                        for _ in range(35):
                            self.tick()
                            if scene.ledge_climbing:
                                break
                        self.assertTrue(scene.ledge_climbing)
                        scene.set_key_state('up', False)
                        action = scene.action
                        if kind == 'turn':
                            scene.set_key_state('shift', False)
                            direction = -1 if facing else 1
                            scene.horizontal_key(None, direction, True)
                            scene.horizontal_key(None, direction, False)
                        elif kind == 'jump':
                            scene.up_key(None)
                            scene.set_key_state('up', False)
                        else:
                            key = 'ctrl' if kind.startswith('sword') else 'down'
                            scene.set_key_state(key, True)
                            if kind != 'sword_held':
                                scene.set_key_state(key, False)
                        # The native ledge now owns one directional bank,
                        # including protected-climb taps. Ctrl still draws
                        # only if held through the standing gate.
                        if kind == 'turn':
                            self.assertLess(scene.directional_input.remap(
                                facing_right=bool(facing)).right, 0)
                        elif kind in ('crouch', 'jump'):
                            self.assertLess(getattr(scene.directional_input,
                                                    'down' if kind == 'crouch' else 'up'), 0)
                        self.assertEqual(scene.action, action)
                        for _ in range(30):
                            self.tick()
                            if not scene.ledge_climbing:
                                break
                        self.assertFalse(scene.ledge_climbing)
                        if kind.startswith('sword'):
                            # The climb has a standing tail after releasing
                            # its ledge state. Let that reach the draw gate.
                            for _ in range(12):
                                if scene.sword_drawn or (kind == 'sword' and scene.action == 15):
                                    break
                                self.tick()
                        if kind == 'jump':
                            self.assertIn(scene.sequence_state.sequence_id, (14, 24, 28))
                            self.assertEqual(scene.native_ledge, scene.sequence_state.sequence_id == 24)
                        else:
                            self.assertEqual(scene.native_ledge, kind == 'crouch')
                            self.assertEqual(scene.ledge_hanging, kind == 'crouch')
                            self.assertEqual(scene.sequence_state.sequence_id,
                                             {'turn': 5, 'sword': IDLE_SEQUENCE, 'sword_held': 55,
                                              'crouch': 68}[kind])
                        self.assertEqual(scene.terrain_motion.row, 1)
                        if kind == 'sword':
                            self.tick(10)
                            self.assertFalse(scene.sword_drawn)
                            scene.set_key_state('ctrl', True)
                            self.assertEqual(scene.sequence_state.sequence_id, 55)

    def test_cavern_swing_release_lands_on_the_intermediate_platform_in_both_room_routes(self):
        scene = self.scene
        with patch.object(scene, 'render'):
            for room, row, x, destination, floor in ((4, 2, 240, 5, 1), (17, 1, 445, 19, 0)):
                with self.subTest(room=room):
                    scene.load_level(3)
                    scene.peaceful = True
                    scene.jump_to_room(room, row=row, x=x, facing=1)
                    scene.in_animation_tick = True
                    scene.set_key_state('down', True)
                    scene.set_key_state('down', False)
                    poses = []
                    for _ in range(35):
                        self.tick()
                        poses.append(scene.sequence_state.sequence_id)
                        if scene.action == 15 and not scene.native_ledge and not scene.terrain_motion.falling:
                            break
                    self.assertIn(99, poses)
                    self.assertEqual((scene.room_id, scene.terrain_motion.row, scene.action),
                                     (destination, floor, 15))
                    self.assertFalse(scene.terrain_motion.falling or scene.terrain_motion.dead)
                    self.tick(5)
                    self.assertEqual((scene.room_id, scene.terrain_motion.row), (destination, floor))

    def test_cavern_run_jump_bump_discards_an_up_tap_but_climbs_on_a_held_up(self):
        # SEQS 46 -> 49 is mode 5 through pose 116 (6:0576-059c clears the
        # bank): a tap made there is gone, a held Up is fresh afterwards.
        scene = self.scene
        with patch.object(scene, 'render'):
            for queue_pose in (102, 107, 108, 109, 110, 111):
                for held in (False, True):
                    with self.subTest(queue_pose=queue_pose, held=held):
                        scene.load_level(3)
                        scene.peaceful = True
                        scene.jump_to_room(20, row=1, x=120, facing=0)
                        scene.in_animation_tick = True
                        scene.horizontal_key(None, -1, True)
                        for _ in range(12):
                            self.tick()
                            if scene.action == 7:
                                break
                        scene.up_key(None)
                        self.tick()
                        scene.set_key_state('up', False)
                        for _ in range(25):
                            if scene.room_id == 25 and scene.action == queue_pose:
                                break
                            self.tick()
                        self.assertEqual((scene.room_id, scene.action), (25, queue_pose))
                        scene.horizontal_key(None, -1, False)
                        scene.up_key(None)
                        if not held:
                            scene.set_key_state('up', False)
                        poses = []
                        for _ in range(45):
                            self.tick()
                            poses.append(scene.action)
                            if scene.ledge_climbing:
                                scene.set_key_state('up', False)
                            if 135 in poses and not scene.native_ledge:
                                break
                        self.assertEqual(67 in poses, held)
                        self.assertEqual(135 in poses, held)
                        self.assertEqual((scene.room_id, scene.terrain_motion.row, scene.action),
                                         (25, 0 if held else 1, 15))
                        scene.set_key_state('up', False)
                        self.assertFalse(scene.terrain_motion.falling or scene.native_ledge)

    def test_releasing_the_arrow_of_a_run_chord_during_pause_acts_as_without_pause(self):
        # The running bank's release rule (brake, then jump up) applies to a
        # release made while paused too; the old host producer latched a bare
        # Up there and the run took off as a running jump (SEQS 4).
        scene = self.scene

        def trace(up_pose, paused):
            scene.load_level(3)
            scene.peaceful = True
            scene.jump_to_room(20, row=1, x=250, facing=0)
            scene.in_animation_tick = True
            scene.horizontal_key(None, -1, True)
            for _ in range(30):
                self.tick()
                if scene.action == up_pose:
                    break
            self.assertEqual(scene.action, up_pose)
            scene.up_key(None)
            if paused:
                scene.set_paused(True)
            scene.horizontal_key(None, -1, False)
            if paused:
                scene.set_paused(False)
            sequences = []
            for _ in range(30):
                self.tick()
                if not sequences or sequences[-1] != scene.sequence_state.sequence_id:
                    sequences.append(scene.sequence_state.sequence_id)
            return sequences, scene.action, scene.room_id

        with patch.object(scene, 'render'):
            for up_pose in (5, 8, 9, 10, 12, 13):
                with self.subTest(up_pose=up_pose):
                    live = trace(up_pose, False)
                    self.assertNotIn(4, live[0])
                    self.assertIn(13, live[0])
                    self.assertEqual(trace(up_pose, True), live)

    def test_run_jump_keeps_held_up_when_only_horizontal_is_released(self):
        scene = self.scene
        with patch.object(scene, 'render'):
            for release_pose in (34, 39, 40, 102, 107, 108, 109, 110, 111, 50, 51, 52):
                for paused_release in (False, True):
                    with self.subTest(release_pose=release_pose, paused_release=paused_release):
                        scene.load_level(3)
                        scene.peaceful = True
                        scene.jump_to_room(20, row=1, x=120, facing=0)
                        scene.in_animation_tick = True
                        scene.horizontal_key(None, -1, True)
                        for _ in range(12):
                            self.tick()
                            if scene.action == 7:
                                break
                        scene.up_key(None)
                        for _ in range(40):
                            self.tick()
                            if scene.action == release_pose:
                                break
                        self.assertEqual(scene.action, release_pose)
                        before = (scene.sequence_state.sequence_id, scene.action, scene.player_x)
                        if paused_release:
                            scene.set_paused(True)
                        scene.horizontal_key(None, -1, False)
                        self.assertEqual((scene.sequence_state.sequence_id, scene.action,
                                          scene.player_x), before)
                        if scene.sequence_state.sequence_id in (3, 4):
                            self.assertLess(scene.directional_input.up, 0)
                            self.assertTrue(scene.airborne_vertical_followup)
                        if paused_release:
                            scene.set_paused(False)
                        poses = []
                        for _ in range(65):
                            self.tick()
                            poses.append(scene.action)
                            if scene.ledge_climbing:
                                scene.set_key_state('up', False)
                            if 135 in poses and not scene.native_ledge:
                                break
                        self.assertIn(67, poses)
                        self.assertIn(135, poses)
                        self.assertEqual((scene.room_id, scene.terrain_motion.row, scene.action),
                                         (25, 0, 15))
                        self.assertFalse(scene.terrain_motion.falling or scene.native_ledge)

    def test_cavern_room_21_dev_warp_starts_on_the_lower_floor(self):
        scene = self.scene
        with patch.object(scene, 'render'):
            scene.load_level(3)
            scene.peaceful = True
            scene.jump_to_screen('Room 21')
            self.assertEqual((scene.room_id, scene.terrain_motion.row, scene.player_x),
                             (20, 2, 387))
            self.tick(5)
            self.assertFalse(scene.terrain_motion.dead or scene.terrain_motion.falling)
            scene.horizontal_key(None, -1, True)
            self.tick(4)
            self.assertLess(scene.player_x, 387)

    def test_standing_jump_keeps_held_up_for_the_wall_climb_in_both_facings(self):
        scene = self.scene
        with patch.object(scene, 'render'):
            for room, row, x, facing, destination in ((20, 1, 60, 0, 25), (0, 2, 80, 1, 0)):
                for release_pose in (16, 19, 22, 50, 51, 52):
                    for paused_release in (False, True):
                        with self.subTest(facing=facing, pose=release_pose, paused=paused_release):
                            scene.load_level(3)
                            scene.peaceful = True
                            scene.jump_to_room(room, row=row, x=x, facing=facing)
                            scene.in_animation_tick = True
                            direction = 1 if facing else -1
                            scene.up_key(None)
                            scene.horizontal_key(None, direction, True)
                            for _ in range(25):
                                self.tick()
                                if scene.action == release_pose:
                                    break
                            self.assertEqual(scene.action, release_pose)
                            if paused_release:
                                scene.set_paused(True)
                            scene.horizontal_key(None, direction, False)
                            if scene.sequence_state.sequence_id in (3, 4):
                                self.assertLess(scene.directional_input.up, 0)
                                self.assertTrue(scene.airborne_vertical_followup)
                            if paused_release:
                                scene.set_paused(False)
                            poses = []
                            for _ in range(65):
                                self.tick()
                                poses.append(scene.action)
                                if scene.ledge_climbing:
                                    scene.set_key_state('up', False)
                                if 135 in poses and not scene.native_ledge:
                                    break
                            self.assertIn(67, poses)
                            self.assertIn(135, poses)
                            self.assertEqual((scene.room_id, scene.terrain_motion.row, scene.action),
                                             (destination, row - 1, 15))
                            self.assertFalse(scene.terrain_motion.falling or scene.native_ledge)

    def test_run_wall_contact_keeps_a_climb_requested_before_or_during_the_bump(self):
        scene = self.scene
        with patch.object(scene, 'render'):
            for room, row, x, facing in ((25, 1, 480, 0), (0, 2, 50, 1)):
                for queue_pose in (6, 50, 51, 52):
                    with self.subTest(facing=facing, pose=queue_pose):
                        scene.load_level(3)
                        scene.peaceful = True
                        scene.jump_to_room(room, row=row, x=x, facing=facing)
                        scene.in_animation_tick = True
                        direction = 1 if facing else -1
                        scene.horizontal_key(None, direction, True)
                        for _ in range(25):
                            self.tick()
                            if scene.action == queue_pose:
                                break
                        self.assertEqual(scene.action, queue_pose)
                        scene.up_key(None)
                        scene.horizontal_key(None, direction, False)
                        if queue_pose == 6:
                            self.assertLess(scene.directional_input.up, 0)
                            self.assertTrue(scene.run_vertical_followup)
                        poses = []
                        for _ in range(65):
                            self.tick()
                            poses.append(scene.action)
                            if scene.ledge_climbing:
                                scene.set_key_state('up', False)
                            if 135 in poses and not scene.native_ledge:
                                break
                        self.assertIn(67, poses)
                        self.assertIn(135, poses)
                        self.assertEqual((scene.room_id, scene.terrain_motion.row, scene.action),
                                         (room, row - 1, 15))
                        self.assertFalse(scene.terrain_motion.falling or scene.native_ledge)

    def test_climb_releases_the_old_up_chord_into_the_still_held_run(self):
        scene = self.scene
        with patch.object(scene, 'render'):
            for facing in (0, 1):
                direction = 1 if facing else -1
                for release_pose in (135, 138, 141, 148):
                    for paused_release in (False, True):
                        with self.subTest(facing=facing, release_pose=release_pose,
                                          paused_release=paused_release):
                            scene.load_level(3)
                            scene.peaceful = True
                            scene.jump_to_room(0, row=2, x=80 if facing else 330, facing=facing)
                            scene.in_animation_tick = True
                            scene.up_key(None)
                            scene.start_jump_if_needed()
                            for _ in range(45):
                                self.tick()
                                if scene.ledge_climbing and scene.action == release_pose:
                                    break
                            self.assertTrue(scene.ledge_climbing)
                            self.assertEqual(scene.action, release_pose)
                            scene.horizontal_key(None, direction, True)
                            self.assertLess(scene.directional_input.up, 0)
                            self.assertLess(getattr(scene.directional_input,
                                                    'right' if direction > 0 else 'left'), 0)
                            if paused_release:
                                scene.set_paused(True)
                            scene.set_key_state('up', False)
                            if paused_release:
                                scene.set_paused(False)
                            for _ in range(25):
                                self.tick()
                                if not scene.ledge_climbing:
                                    break
                            self.assertTrue(scene.run_active)
                            self.assertEqual(scene.run_direction, direction)
                            self.assertEqual(scene.action, 1)
                            self.assertFalse(scene.native_ledge)

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
        with patch("pop2.level_rendering.build_opening_room") as build:
            self.assertEqual(scene.screen_label(2), "3")
            self.assertEqual(tuple(scene.dev_screens()),
                             ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "Secret (right)"))
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
            health.assert_called_once_with(scene.native_viewport, scene.combat, show_opponent=False,
                                           player_life=scene.combat.player.life)
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
        from pop2.sequence_runtime import SequenceRuntime

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
        # A held Down would crouch at 51 after the mode-5 clear at pose 50.
        scene.set_key_state("down", False)
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
        anchor = scene.player_x
        scene.horizontal_key(None, 1, True)
        self.tick(8)
        self.assertGreater(scene.player_x, anchor)
        self.assertFalse(scene.sword_sheathing)
        self.assertFalse(scene.combat.player.controls_locked)

    def test_repeated_standing_turns_at_wall_preserve_all_native_poses_and_position(self):
        from dataclasses import replace
        from pop2.sequence_runtime import SequenceRuntime

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
        from pop2.sequence_runtime import SequenceRuntime

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
                for _ in range(9):
                    expected = reference.next_frame()
                    if expected.action == 158 and expected.sequence_id == 227 and 157 not in actions:
                        # The first ready pose extends the collider by AFRM X - 3.
                        # Native Collide corrects four pixels, then selects SEQS:64.
                        reference.state.target_x -= 4 * (1 if facing else -1)
                        reference.state.select(64)
                        expected = reference.next_frame()
                    self.tick()
                    actions.append(scene.action)
                    self.assertEqual((scene.sequence_state.sequence_id, scene.action, scene.player_x),
                                     (expected.sequence_id, expected.action, expected.target_x))
                    self.assertTrue(scene.sword_drawn)
                    self.assertFalse(scene.terrain_motion.falling)
                self.assertEqual(actions, [207, 208, 209, 210, 157, 160, 158, 170, 171])
                self.assertEqual(scene.player_x, x - 38 * (1 if facing else -1))

    def test_releasing_wall_supported_hang_uses_full_native_floor_return(self):
        from dataclasses import replace
        from pop2.sequence_runtime import SequenceRuntime

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

    def test_wall_bump_repeats_a_jump_only_while_its_keys_stay_held(self):
        # The wall stop (47, poses 50-52) is mode 5: ClearControls (6:0576)
        # zeroes the consumed takeoff keys, so keys released before it ends
        # never replay, while keys still held are fresh at its end and jump
        # again (4:3e84 sampling), as on the Macintosh.
        scene = self.scene
        scene.advance_animation_now = lambda: None
        for room, row, x, facing in ((9, 1, 233, 0), (20, 0, 272, 1)):
            direction = 1 if facing else -1
            for up_first in (False, True):
                for release_tick in (1, 3, None):
                    with self.subTest(facing=facing, up_first=up_first, release=release_tick):
                        scene.jump_to_room(room, row=row, x=x, facing=facing)
                        scene.set_peaceful(True)
                        if up_first:
                            scene.up_key(None)
                            scene.horizontal_key(None, direction, True)
                        else:
                            scene.horizontal_key(None, direction, True)
                            scene.up_key(None)
                        collided = replayed = False
                        for tick in range(20):
                            if tick == release_tick:
                                scene.set_key_state("up", False)
                                scene.horizontal_key(None, direction, False)
                            self.tick()
                            sequence = scene.sequence_state.sequence_id
                            if collided:
                                replayed |= sequence in (3, 4, 28)
                            collided |= sequence == 47
                            self.assertFalse(scene.terrain_motion.falling)
                        self.assertTrue(collided)
                        self.assertEqual(replayed, release_tick is None)
                        if release_tick is None:
                            scene.set_key_state("up", False)
                            scene.horizontal_key(None, direction, False)
                            for _ in range(20):
                                self.tick()
                                if scene.action == 15:
                                    break
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
        from pop2.mac_input import StepBoundary
        from pop2.scene_prototype import BufferedCommand

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

    def test_development_menu_teleports_without_a_live_input_or_pause_backlog(self):
        scene = self.scene
        for paused in (False, True):
            scene.set_paused(paused)
            scene.open_dev_mode()
            self.assertTrue(scene.paused)
            self.assertEqual(scene.dev_menu.screens,
                             ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "Secret (right)"))
            scene.dev_menu.focus = 4
            scene.dev_menu.select(4)
            scene.apply_dev_action("go")
            self.assertIsNone(scene.dev_menu)
            self.assertEqual(scene.paused, paused)
            self.assertEqual((scene.room_id, scene.player_x, scene.terrain_motion.row), (9, 489, 1))

    def test_screen_selection_uses_route_order_and_the_entry_floor(self):
        scene = self.scene
        for label, room, row, x, facing in (("1", 3, 1, 411, 1), ("2", 1, 1, 489, 0),
                                           ("3", 2, 1, 489, 0), ("4", 0, 1, 489, 0),
                                           ("5", 9, 1, 489, 0), ("6", 10, 0, 489, 0),
                                           ("7", 11, 1, 489, 0), ("Secret (right)", 4, 0, 285, 1)):
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
                  if image.getpixel((x, y))[:3] == (253, 255, 168)]
        self.assertEqual((min(y for x, y in yellow), max(y for x, y in yellow)), (369, 379))

    def test_run_stop_turn_and_descend_matches_native_positions(self):
        scene = self.scene
        scene.peaceful = True
        for origin, stopped, turned, sequence in ((468, 339, 348, 68),
                                                  (495, 366, 375, 50)):
            for release_tick in range(7, 11):
                with self.subTest(origin=origin, release_tick=release_tick):
                    scene.jump_to_room(11, row=1, x=origin, facing=0)
                    scene.horizontal_key(None, -1, True)
                    self.tick(release_tick)
                    self.assertEqual(scene.action, release_tick + 1)
                    scene.horizontal_key(None, -1, False)
                    self.tick(20)
                    self.assertEqual((scene.action, scene.player_x), (15, stopped))
                    self.assertFalse(scene.terrain_motion.falling)
                    scene.horizontal_key(None, 1, True)
                    scene.horizontal_key(None, 1, False)
                    self.tick(10)
                    self.assertEqual((scene.action, scene.player_x), (15, turned))
                    scene.set_key_state("down", True)
                    self.assertEqual(scene.sequence_state.sequence_id, sequence)

    def test_dev_entry_allows_multiple_run_release_poses_before_descending(self):
        scene = self.scene
        scene.peaceful = True
        for release_tick in range(7, 11):
            with self.subTest(release_tick=release_tick):
                scene.jump_to_screen("7")
                scene.horizontal_key(None, -1, True)
                self.tick(release_tick)
                scene.horizontal_key(None, -1, False)
                self.tick(20)
                self.assertEqual((scene.action, scene.player_x), (15, 360))
                scene.horizontal_key(None, 1, True)
                scene.horizontal_key(None, 1, False)
                self.tick(10)
                self.assertEqual((scene.action, scene.player_x), (15, 369))
                scene.set_key_state("down", True)
                self.assertEqual(scene.sequence_state.sequence_id, 68)

    def test_run_release_after_the_last_safe_foot_does_not_clamp_to_the_ledge(self):
        scene = self.scene
        scene.peaceful = True
        scene.jump_to_screen("7")
        scene.horizontal_key(None, -1, True)
        self.tick(11)
        self.assertEqual(scene.action, 12)
        scene.horizontal_key(None, -1, False)
        for _ in range(12):
            self.tick()
            if scene.terrain_motion.falling:
                break
        self.assertTrue(scene.terrain_motion.falling)

    def test_direction_pressed_during_sheathing_starts_run_without_an_idle_frame(self):
        scene = self.scene
        scene.jump_to_screen("2")
        self.clear_guards()
        scene.in_animation_tick = True
        scene.sword_drawn = True
        scene.start_sword_action("sword_sheathe")
        scene.horizontal_key(None, -1, True)
        # The press is a bank request (PutSwordAway shares the bank), not a slot.
        self.assertEqual(scene.directional_input.left, -1)
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

    def test_standing_jump_chords_keep_the_same_rooftop_motion_in_both_key_orders(self):
        scene = self.scene
        scene.peaceful = True
        for facing in (0, 1):
            for up_first in (False, True):
                with self.subTest(facing=facing, up_first=up_first):
                    scene.jump_to_room(1, row=1, x=250, facing=facing)
                    self.clear_guards()
                    direction = 1 if facing else -1
                    with patch("pop2.scene_prototype.time.perf_counter", return_value=100):
                        if up_first:
                            scene.up_key(None)
                        else:
                            scene.horizontal_key(None, direction, True)
                            self.assertEqual(scene.action, 1)
                    delay = 0.02 if up_first else 0.08
                    with patch("pop2.scene_prototype.time.perf_counter",
                               return_value=100 + delay):
                        if up_first:
                            scene.horizontal_key(None, direction, True)
                        else:
                            scene.up_key(None)
                    self.assertEqual((scene.sequence_state.sequence_id, scene.action), (3, 16))
                    self.assertEqual(scene.player_x, 250 + 4 * direction)
                    scene.set_key_state("up", False)
                    scene.horizontal_key(None, direction, False)
                    actions = [scene.action]
                    for _ in range(25):
                        self.tick()
                        actions.append(scene.action)
                        self.assertFalse(scene.terrain_motion.dead)
                        self.assertFalse(scene.terrain_motion.falling)
                        if scene.sequence_state.sequence_id == 2:
                            break
                    self.assertEqual(actions, [*range(16, 34), 15])
                    self.assertEqual((scene.room_id, scene.terrain_motion.row), (1, 1))

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

    def test_running_jump_landing_resamples_held_up_with_real_rooftop_physics(self):
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
            if queued_pose is not None or not held:
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
            self.assertEqual([frame[3] for frame in trace], [*range(34, 45), 7, 34 if held else 8])
            return trace

        for facing in (0, 1):
            for held in (False, True):
                baseline = replay(facing, held=held)
                for pose in (34, 38, 41, 44):
                    with self.subTest(facing=facing, pose=pose, held=held):
                        self.assertEqual(replay(facing, pose, held), baseline)

    def test_opposite_arrow_during_running_jump_obeys_landing_reset_on_real_rooftop(self):
        scene = self.scene
        for held in (False, True):
            with self.subTest(held=held):
                scene.jump_to_room(1, row=1, x=120, facing=1)
                scene.peaceful = True
                self.clear_guards()
                scene.in_animation_tick = True
                scene.horizontal_key(None, 1, True)
                for _ in range(20):
                    self.tick()
                    if scene.action == 7:
                        break
                self.assertEqual(scene.action, 7)
                scene.up_key(None)
                self.tick(7)
                self.assertEqual((scene.sequence_state.sequence_id, scene.action), (4, 40))
                before = (scene.player_x, scene.sequence_state.current_y, scene.action)
                scene.horizontal_key(None, -1, True)
                if not held:
                    scene.set_key_state("up", False)
                    scene.horizontal_key(None, 1, False)
                    scene.horizontal_key(None, -1, False)
                self.assertEqual(
                    (scene.player_x, scene.sequence_state.current_y, scene.action), before
                )
                actions = [scene.action]
                for _ in range(6):
                    self.tick()
                    actions.append(scene.action)
                    self.assertFalse(scene.terrain_motion.falling)
                    self.assertFalse(scene.terrain_motion.dead)
                self.assertEqual(actions, [40, 41, 42, 43, 44, 7, 53])
                self.assertEqual(scene.sequence_state.sequence_id, 6 if held else 13)
                self.assertEqual(scene.sequence_state.current_y, 0)
                if not held:
                    self.tick(12)
                    self.assertEqual((scene.action, scene.sequence_state.facing), (15, 1))

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

    def test_direction_held_into_the_sheath_is_a_request_after_put_sword_away(self):
        # PutSwordAway 6:2598 calls ClearControls (0), so a direction held
        # when the sheathe starts is fresh at the next sample; released
        # mid-sheathe it stays pending. Forward reaches the pose-48 run gate;
        # Backward waits for 50-52, and pose 50 (mode 5) clears it.
        for direction, runs in ((-1, True), (1, False)):
            with self.subTest(direction=direction):
                scene = self.scene
                scene.jump_to_screen("2")
                self.clear_guards()
                self.assertEqual(scene.sequence_state.facing, 0)
                scene.sword_drawn = True
                scene.held_directions = [direction]
                scene.sample_keyboard()
                scene.in_animation_tick = True
                scene.start_sword_action("sword_sheathe", sequence_id=92)
                self.tick(5)
                scene.horizontal_key(None, direction, False)
                sequences = []
                for _ in range(40):
                    self.tick()
                    sequences.append(scene.sequence_state.source_sequence_id)
                self.assertEqual(43 in sequences, runs)
                self.assertNotIn(5, sequences)
                self.assertEqual(scene.action, 15)
                self.assertFalse(scene.sword_sheathing)

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

    def test_queued_vertical_jump_brakes_before_aligning_a_building_climb(self):
        scene = self.scene
        scene.jump_to_room(9, row=1, x=480, facing=0)
        scene.set_peaceful(True)
        scene.in_animation_tick = True
        scene.horizontal_key(None, -1, True)
        self.tick(20)
        scene.horizontal_key(None, -1, False)
        scene.up_key(None)
        scene.start_jump_if_needed()
        poses = []
        for _ in range(48):
            self.tick()
            state = scene.sequence_state
            poses.append((state.sequence_id, state.action, state.target_x))
            if scene.ledge_climbing:
                scene.set_key_state("up", False)
        self.assertIn((13, 53, 247), poses)
        self.assertIn((47, 50, 249), poses)
        self.assertIn((24, 67, 246), poses)
        self.assertIn((10, 140, 225), poses)
        self.assertEqual((scene.terrain_motion.row, scene.action, scene.player_x), (0, 15, 214))
        self.assertFalse(scene.terrain_motion.falling)
        self.assertFalse(scene.native_ledge)

    def test_quick_run_to_climb_matches_settled_climb_across_input_phases(self):
        scene = self.scene
        scene.set_peaceful(True)
        render = scene.render
        with patch.object(scene, "render"):
            scene.jump_to_room(9, row=1, x=240, facing=0)
            scene.in_animation_tick = True
            scene.up_held = True
            scene.start_upper_ledge_jump()
            reference = []
            reference_image = None
            for _ in range(40):
                self.tick()
                if scene.ledge_climbing:
                    scene.set_key_state("up", False)
                if scene.native_ledge:
                    state = scene.sequence_state
                    reference.append((state.sequence_id, state.action, state.target_x,
                                      state.current_y, scene.terrain_motion.row))
                    if state.action == 140:
                        render()
                        reference_image = scene.native_viewport.tobytes()
            self.assertIsNotNone(reference_image)
            for run_ticks in range(17, 23):
                for delay in range(3):
                    with self.subTest(run_ticks=run_ticks, delay=delay):
                        scene.jump_to_room(9, row=1, x=480, facing=0)
                        scene.in_animation_tick = True
                        scene.horizontal_key(None, -1, True)
                        self.tick(run_ticks)
                        scene.horizontal_key(None, -1, False)
                        self.tick(delay)
                        scene.up_key(None)
                        scene.start_jump_if_needed()
                        actual = []
                        for _ in range(48):
                            self.tick()
                            if scene.ledge_climbing:
                                scene.set_key_state("up", False)
                            if scene.native_ledge:
                                state = scene.sequence_state
                                actual.append((state.sequence_id, state.action, state.target_x,
                                               state.current_y, scene.terrain_motion.row))
                                if state.action == 140:
                                    render()
                                    self.assertEqual(scene.native_viewport.tobytes(), reference_image)
                        self.assertEqual(actual, reference)
                        self.assertEqual((scene.terrain_motion.row, scene.action), (0, 15))
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
        from pop2.scene_prototype import BufferedCommand

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
        from pop2.scene_prototype import BufferedCommand

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
        from pop2.scene_prototype import BufferedCommand
        from pop2.render_opening import ROOM_ORIGIN_X

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
        from pop2.render_opening import ROOM_WIDTH, ROOM_HEIGHT, add_alpha

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
                        # Native Move/Catch replaces pose 106 with the caught
                        # pose in the same frame when Shift is held.
                        self.assertEqual(falling_poses, set(range(
                            102, 106 if shift_at is not None else 107)))
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
        from pop2.render_opening import ROOM_WIDTH, ROOM_HEIGHT, add_alpha
        from pop2.scene_prototype import BufferedCommand

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
        from pop2.render_opening import ROOM_WIDTH, ROOM_HEIGHT, add_alpha

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
        from pop2.scene_prototype import BufferedCommand

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
        scene.up_held = True
        scene.start_jump_if_needed()
        self.assertEqual(scene.sequence_state.sequence_id, 68)

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
