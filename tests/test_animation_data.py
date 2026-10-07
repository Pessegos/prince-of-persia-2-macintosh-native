import struct
import unittest
from unittest.mock import patch

from pop2.animation_data import (
    parse_aframe_records,
    parse_frame_records,
    sequence_words,
    shape_id_for_action,
)
from pop2.control_mapping import (
    IDLE_SEQUENCE,
    RUN_CYCLE_SEQUENCE,
    RUN_JUMP_SEQUENCE,
    RUN_START_SEQUENCE,
    RUN_STOP_SEQUENCE,
    RUNNING_DRIFT_SEQUENCE,
    RUNNING_TURN_SEQUENCE,
    SHIFT_STEP_SEQUENCE,
    STANDING_TURN_SEQUENCE,
    JUMP_FORWARD_SEQUENCE,
    JUMP_VERTICAL_SEQUENCE,
    CROUCH_LOWER_SEQUENCE,
    CROUCH_STANDING_LOWER_SEQUENCE,
    CROUCH_HOLD_SEQUENCE,
    CROUCH_STEP_SEQUENCE,
    CROUCH_RISE_SEQUENCE,
    LEDGE_APPROACH_SEQUENCE,
    LEDGE_FALL_SEQUENCE,
    LEDGE_HANG_SEQUENCE,
    SWORD_DRAW_SEQUENCE,
    SWORD_ADVANCE_SEQUENCE,
    SWORD_RETREAT_SEQUENCE,
    SWORD_GUARD_SEQUENCE,
    SWORD_ATTACK_SEQUENCE,
    SWORD_BLOCK_SEQUENCE,
    SWORD_BLOCK_ATTACK_SEQUENCE,
    SWORD_SHEATHE_SEQUENCE,
    jump_sequence_for_input,
    movement_sequence_for_key,
)
from pop2.mac_input import KeyboardFrame, StepPlan, plan_step, read_keyboard
from pop2.opening_animation import OpeningEscape
from pop2.rebirth import DeathState
from pop2.render_opening import load_resource_file
from pop2.sequence_runtime import (
    SequenceRuntime,
    SequenceState,
    UnsupportedSequenceOpcode,
)
from pop2.scene_prototype import (
    ANIMATION_FPS,
    ANIMATION_INTERVAL_MS,
    BufferedCommand,
    ScenePrototype,
    sword_palette_for_level,
    TAP_RELEASE_ACTION,
    next_animation_deadline,
)


class DummyStatus:
    def set(self, value):
        self.value = value


class DummyRoot:
    def __init__(self):
        self.cancelled = []
        self.scheduled = []

    def after_cancel(self, callback_id):
        self.cancelled.append(callback_id)

    def after(self, delay_ms, callback):
        callback_id = f"after-{len(self.scheduled) + 1}"
        self.scheduled.append((delay_ms, callback))
        return callback_id


class AnimationDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kid = load_resource_file("Kid.rsrc")
        cls.prince = load_resource_file("Prince.rsrc")
        cls.sequences = {
            resource_id: sequence_words(resource["data"])
            for resource_id, resource in cls.prince["SEQS"].items()
        }

    def runtime(self, sequence_id, facing=0, x=116):
        return SequenceRuntime(
            self.sequences,
            SequenceState(
                sequence_id=sequence_id,
                current_x=x,
                target_x=x,
                facing=facing,
                actor_type=0,
                level_kind=5,
            ),
        )

    def scene(self, sequence_id=2, facing=0, running=False):
        scene = ScenePrototype.__new__(ScenePrototype)
        scene.sequences = self.sequences
        scene.sequence_state = SequenceState(
            sequence_id=sequence_id,
            current_x=116,
            target_x=116,
            facing=facing,
            actor_type=0,
            level_kind=5,
        )
        scene.sequence_runtime = SequenceRuntime(scene.sequences, scene.sequence_state)
        scene.player_x = 116
        scene.held_directions = []
        scene.pending_action = None
        scene.run_cycle_boundary_pending = False
        scene.horizontal_input = 0
        scene.up_held = False
        scene.jump_started_for_press = False
        scene.jump_repeat_armed = False
        scene.run_start_x = None
        scene.shift_held = False
        scene.down_held = False
        scene.ctrl_held = False
        scene.sword_drawn = False
        scene.sword_sheathing = False
        scene.down_sheathe_consumed = False
        scene.ledge_test_active = False
        scene.ledge_action_consumed = False
        scene.ledge_hanging = False
        scene.ledge_climbing = False
        scene.ledge_climb_requested = False
        scene.native_ledge = False
        scene.ledge_grip_delay = 0
        scene.right_platform_edge_x = 408
        scene.run_active = running
        scene.run_direction = -1 if running else 0
        scene.run_stop_requested = False
        scene.in_animation_tick = False
        scene.paused = False
        scene.death = DeathState()
        scene.checkpoint = None
        scene.checkpoints = ()
        scene.level_complete = False
        scene.dev_menu = None
        scene.pause_resume_keys = set()
        scene.window_keys_down = set()
        scene.combat = None
        scene.status = DummyStatus()
        return scene

    def sword_scene(self):
        scene = self.scene()
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None
        return scene

    def running_jump_scene(self, facing=1):
        direction = 1 if facing else -1
        scene = self.sword_scene()
        scene.sequence_state.facing = facing
        scene.start_sequence(RUN_CYCLE_SEQUENCE)
        scene.run_active = True
        scene.run_direction = direction
        scene.held_directions = [direction]
        scene.sample_keyboard()
        scene.up_key(None)
        scene.advance_animation()
        scene.advance_animation()
        self.assertEqual((scene.sequence_state.sequence_id, scene.action), (4, 34))
        return scene

    def guarded_sword_scene(self, facing=0):
        scene = self.sword_scene()
        scene.sword_drawn = True
        scene.sequence_state.facing = facing
        scene.start_sequence(SWORD_GUARD_SEQUENCE)
        scene.advance_animation()
        return scene

    def opening_scene(self):
        scene = self.sword_scene()
        scene.start_tile = 2
        scene.opening = OpeningEscape(scene.sequence_runtime, scene.start_tile)
        scene.action = scene.sequence_state.action
        scene.player_x = scene.sequence_state.target_x
        return scene

    def test_opening_cannot_be_replaced_by_movement_or_sword_input(self):
        scene = self.opening_scene()
        snapshot = vars(scene.sequence_state).copy()
        scene.horizontal_key(None, -1, True)
        scene.up_key(None)
        scene.set_key_state("down", True)
        scene.set_key_state("shift", True)
        scene.set_key_state("ctrl", True)
        scene.set_key_state("up", False)
        self.assertEqual(vars(scene.sequence_state), snapshot)
        self.assertIsNone(scene.pending_action)
        self.assertFalse(scene.sword_drawn)

    def test_opening_hands_control_back_to_existing_idle_and_turn(self):
        scene = self.opening_scene()
        for _ in range(19):
            scene.advance_animation()
        self.assertFalse(scene.opening.active)
        self.assertEqual((scene.action, scene.player_x), (15, 411))
        scene.advance_animation()
        self.assertEqual((scene.action, scene.player_x), (15, 411))
        scene.horizontal_key(None, -1, True)
        self.assertEqual(scene.sequence_state.sequence_id, STANDING_TURN_SEQUENCE)
        self.assertEqual(scene.action, 45)

    def test_arrow_held_during_opening_is_read_after_landing(self):
        scene = self.opening_scene()
        scene.horizontal_key(None, -1, True)
        for _ in range(20):
            scene.advance_animation()
        self.assertFalse(scene.opening.active)
        self.assertEqual(scene.action, 45)
        self.assertEqual(scene.sequence_state.sequence_id, STANDING_TURN_SEQUENCE)

    def test_replay_clears_combat_input_and_resets_animation_deadline(self):
        scene = self.guarded_sword_scene()
        scene.start_tile = 2
        scene.held_directions = [-1]
        scene.ctrl_held = True
        scene.pending_action = BufferedCommand("sword_attack")
        scene.restart_opening()
        self.assertTrue(scene.opening.active)
        self.assertEqual((scene.action, scene.player_x), (43, 324))
        self.assertFalse(scene.sword_drawn)
        self.assertFalse(scene.ctrl_held)
        self.assertEqual(scene.held_directions, [])
        self.assertIsNone(scene.pending_action)
        self.assertEqual(len(scene.root.cancelled), 1)

    def test_animation_timer_compensates_for_frame_render_time(self):
        deadline, delay = next_animation_deadline(10.0, 10.013, interval_ms=100)

        self.assertAlmostEqual(deadline, 10.1)
        self.assertEqual(delay, 87)

    def test_animation_timer_skips_overdue_deadlines_without_accumulating_drift(self):
        deadline, delay = next_animation_deadline(10.0, 10.106, interval_ms=100)

        self.assertAlmostEqual(deadline, 10.2)
        self.assertEqual(delay, 94)

    def test_action_uses_original_fram_shape_index(self):
        first_shape_id, _ = struct.unpack_from(
            ">HH", self.kid["SHPL"][25001]["data"], 0
        )
        records = parse_frame_records(self.kid["FRAM"][25001]["data"])

        self.assertEqual(first_shape_id, 25002)
        self.assertIsNone(shape_id_for_action(records, first_shape_id, 0))
        self.assertEqual(shape_id_for_action(records, first_shape_id, 1), 25002)
        self.assertEqual(shape_id_for_action(records, first_shape_id, 2), 25003)

    def test_original_frame_resource_has_fixed_records(self):
        records = parse_frame_records(self.kid["FRAM"][25001]["data"])

        self.assertEqual(len(records), 352)
        self.assertEqual(records[1].shape_index, 0)
        self.assertEqual(records[1].afrm_index, 0)

    def test_original_attachment_frame_resource_has_fixed_records(self):
        records = parse_aframe_records(self.kid["AFRM"][25001]["data"])

        self.assertEqual(len(records), 110)
        self.assertEqual(records[0], (0, -1, 0, 0))
        self.assertEqual(records[1], (1, 38, -4, -44))

    def test_original_opening_sequence_updates_target_x(self):
        runtime = self.runtime(1, facing=1)
        frames = [runtime.next_frame() for _ in range(8)]

        self.assertEqual([frame.action for frame in frames], list(range(1, 9)))
        self.assertEqual(
            [frame.target_x for frame in frames],
            [119, 120, 124, 133, 143, 150, 163, 173],
        )
        self.assertEqual(runtime.state.sequence_id, 201)
        self.assertEqual(runtime.state.animation_state, 1)

    def test_horizontal_mapping_uses_original_orientation_and_sequences(self):
        self.assertEqual(movement_sequence_for_key(-1, facing=0), RUN_START_SEQUENCE)
        self.assertEqual(movement_sequence_for_key(1, facing=1), RUN_START_SEQUENCE)
        self.assertEqual(
            movement_sequence_for_key(-1, facing=0, shift_pressed=True),
            SHIFT_STEP_SEQUENCE,
        )
        self.assertEqual(
            movement_sequence_for_key(1, facing=1, running=True), RUN_CYCLE_SEQUENCE
        )
        self.assertEqual(movement_sequence_for_key(1, facing=0), RUN_START_SEQUENCE)
        self.assertEqual(
            movement_sequence_for_key(1, facing=0, running=True),
            RUNNING_DRIFT_SEQUENCE,
        )

    def test_original_keyboard_sampling_prioritizes_up_and_left(self):
        self.assertEqual(
            read_keyboard([-1, 1], True, True, True),
            KeyboardFrame(horizontal=-1, vertical=-1, shift=True),
        )
        self.assertEqual(
            read_keyboard([1], False, True, False),
            KeyboardFrame(horizontal=1, vertical=1, shift=False),
        )

    def test_releasing_priority_direction_exposes_other_held_direction(self):
        scene = self.scene(facing=0)
        scene.horizontal_key(None, -1, True)
        scene.horizontal_key(None, 1, True)
        self.assertEqual(scene.horizontal_input, -1)
        self.assertIsNone(scene.pending_action)

        scene.horizontal_key(None, -1, False)

        self.assertEqual(scene.horizontal_input, 1)
        self.assertEqual(scene.pending_action, BufferedCommand("horizontal", 1, "turn"))

    def test_original_step_distance_selects_short_sequences_and_remainder(self):
        self.assertEqual(plan_step(46), StepPlan(42, 0))
        self.assertEqual(plan_step(18), StepPlan(32, 2))
        self.assertEqual(plan_step(8), StepPlan(29, 1))
        self.assertEqual(plan_step(5), StepPlan(None, 1))
        self.assertIsNone(plan_step(4))

    def test_every_short_step_sequence_matches_selected_distance(self):
        for clearance in range(5, 47):
            with self.subTest(clearance=clearance):
                step = plan_step(clearance)
                start_x = 116 + step.pre_offset
                if step.sequence_id is None:
                    self.assertEqual(start_x - 116, clearance - 4)
                    continue
                runtime = self.runtime(step.sequence_id, facing=1, x=start_x)
                while runtime.state.sequence_id != IDLE_SEQUENCE:
                    runtime.next_frame()
                self.assertEqual(
                    runtime.state.target_x - 116, min(clearance - 4, 42)
                )

    def test_shift_step_near_rooftop_edge_uses_original_short_sequence(self):
        scene = self.scene(facing=1)
        scene.player_x = 390
        scene.sequence_state.current_x = 390
        scene.sequence_state.target_x = 390
        scene.shift_held = True

        scene.horizontal_key(None, 1, True)

        self.assertEqual(scene.sequence_state.sequence_id, 32)
        self.assertEqual(scene.player_x, 392)
        while scene.sequence_state.sequence_id != IDLE_SEQUENCE:
            frame = scene.sequence_runtime.next_frame()
            scene.player_x = scene._clamp_rooftop_x(frame.target_x, frame.sequence_id)
        self.assertEqual(scene.player_x, 404)

    def test_held_shift_step_repeats_only_after_previous_step_finishes(self):
        scene = self.scene(facing=1)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None
        scene.shift_held = True
        scene.horizontal_key(None, 1, True)
        self.assertEqual(scene.action, 121)

        for _ in range(12):
            scene.advance_animation()
        self.assertEqual(scene.action, 15)
        self.assertEqual(scene.player_x, 158)

        scene.advance_animation()
        self.assertEqual(scene.action, 121)
        self.assertEqual(scene.sequence_state.sequence_id, SHIFT_STEP_SEQUENCE)

        scene.horizontal_key(None, 1, False)
        for _ in range(12):
            scene.advance_animation()
        self.assertEqual(scene.action, 15)
        scene.advance_animation()
        self.assertEqual(scene.action, 15)

    def test_arrow_tap_plays_native_start_run_and_stop_phases(self):
        scene = self.scene(facing=1)

        scene.horizontal_key(None, 1, True)
        self.assertEqual(scene.sequence_state.sequence_id, RUN_START_SEQUENCE)
        self.assertTrue(scene.run_active)

        scene.horizontal_key(None, 1, False)
        self.assertTrue(scene.run_stop_requested)
        frames = []
        while True:
            scene.prepare_next_sequence()
            frame = scene.sequence_runtime.next_frame()
            frames.append(frame)
            scene.player_x = frame.target_x
            if frame.sequence_id == IDLE_SEQUENCE:
                break

        self.assertEqual(
            [frame.action for frame in frames],
            [*range(1, 9), 53, 54, 55, 56, 49, 50, 51, 52, 15],
        )
        self.assertEqual(frames[-1].target_x, 206)
        self.assertFalse(scene.run_active)

    def test_arrow_press_shows_its_first_pose_immediately(self):
        scene = self.scene(facing=1)
        scene.root = DummyRoot()
        scene.animation_after_id = "pending-tick"
        scene.next_animation_at = 0
        scene.render = lambda: None

        scene.horizontal_key(None, 1, True)

        self.assertEqual(scene.sequence_state.sequence_id, RUN_START_SEQUENCE)
        self.assertEqual(scene.action, 1)
        self.assertEqual(scene.sequence_state.cursor, 5)
        self.assertEqual(scene.root.cancelled, ["pending-tick"])
        self.assertEqual(len(scene.root.scheduled), 1)

    def test_shift_press_starts_one_full_step_without_waiting_for_release(self):
        scene = self.scene(facing=1)
        scene.root = DummyRoot()
        scene.animation_after_id = "pending-tick"
        scene.next_animation_at = 0
        scene.render = lambda: None
        scene.shift_held = True

        scene.horizontal_key(None, 1, True)
        self.assertEqual(scene.sequence_state.sequence_id, SHIFT_STEP_SEQUENCE)
        self.assertEqual(scene.action, 121)
        self.assertEqual(scene.sequence_state.cursor, 3)
        self.assertEqual(scene.root.cancelled, ["pending-tick"])
        self.assertEqual(len(scene.root.scheduled), 1)
        self.assertFalse(scene.run_active)

        scene.horizontal_key(None, 1, False)
        self.assertEqual(scene.sequence_state.sequence_id, SHIFT_STEP_SEQUENCE)

    def test_standing_reversal_plays_original_turn_animation(self):
        scene = self.scene(facing=0)
        scene.root = DummyRoot()
        scene.animation_after_id = "pending-tick"
        scene.next_animation_at = 0
        scene.render = lambda: None

        scene.horizontal_key(None, 1, True)

        self.assertEqual(scene.sequence_state.sequence_id, STANDING_TURN_SEQUENCE)
        self.assertEqual(scene.sequence_state.facing, 1)
        self.assertEqual(scene.action, 45)
        self.assertFalse(scene.run_active)
        self.assertEqual(scene.status.value, "Standing turn: original SEQS:5")
        self.assertEqual(scene.root.cancelled, ["pending-tick"])
        self.assertEqual(len(scene.root.scheduled), 1)

    def test_held_opposite_direction_turns_before_stop_reaches_idle(self):
        scene = self.scene(sequence_id=RUN_STOP_SEQUENCE, facing=1)
        scene.root = DummyRoot()
        scene.next_animation_at = 0
        scene.render = lambda: None

        scene.horizontal_key(None, -1, True)
        actions = []
        for _ in range(20):
            scene.advance_animation()
            actions.append(scene.action)

        self.assertEqual(
            actions,
            [53, 54, 55, 56, 49, 50,
             45, 46, 47, 48, *range(1, 11)],
        )
        self.assertEqual(scene.sequence_state.facing, 0)
        self.assertTrue(scene.run_active)
        self.assertEqual(scene.run_direction, -1)

    def test_opposite_direction_pressed_at_stop_pose_50_turns_next_frame(self):
        scene = self.scene(sequence_id=RUN_STOP_SEQUENCE, facing=1)
        scene.root = DummyRoot()
        scene.next_animation_at = 0
        scene.render = lambda: None

        for _ in range(6):
            scene.advance_animation()
        self.assertEqual(scene.action, 50)

        scene.horizontal_key(None, -1, True)
        scene.advance_animation()

        self.assertEqual(scene.action, 45)
        self.assertEqual(scene.sequence_state.sequence_id, STANDING_TURN_SEQUENCE)
        self.assertEqual(scene.sequence_state.facing, 0)

    def test_same_direction_during_stop_resumes_without_idle(self):
        scene = self.scene(sequence_id=RUN_STOP_SEQUENCE, facing=1)
        scene.root = DummyRoot()
        scene.next_animation_at = 0
        scene.render = lambda: None

        scene.horizontal_key(None, 1, True)
        actions = []
        for _ in range(8):
            scene.advance_animation()
            actions.append(scene.action)

        self.assertEqual(actions, [53, 54, 55, 56, 49, 50, 1, 2])
        self.assertEqual(scene.sequence_state.sequence_id, RUN_START_SEQUENCE)
        self.assertEqual(scene.sequence_state.facing, 1)
        self.assertTrue(scene.run_active)

    def test_tapped_direction_during_stop_starts_one_buffered_run(self):
        scene = self.scene(sequence_id=RUN_STOP_SEQUENCE, facing=1)
        scene.root = DummyRoot()
        scene.next_animation_at = 0
        scene.render = lambda: None

        scene.horizontal_key(None, 1, True)
        scene.horizontal_key(None, 1, False)
        actions = []
        for _ in range(9):
            scene.advance_animation()
            actions.append(scene.action)

        self.assertEqual(actions, [53, 54, 55, 56, 49, 50, 1, 2, 3])
        self.assertTrue(scene.run_active)
        self.assertTrue(scene.run_stop_requested)
        self.assertIsNone(scene.pending_action)

        for _ in range(30):
            if scene.sequence_state.sequence_id == IDLE_SEQUENCE:
                break
            scene.advance_animation()
        self.assertEqual(scene.sequence_state.sequence_id, IDLE_SEQUENCE)
        self.assertFalse(scene.run_active)
        scene.advance_animation()
        self.assertEqual(scene.action, 15)

    def test_queued_opposite_direction_drifts_then_runs_without_resting(self):
        scene = self.scene(facing=1)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None

        scene.horizontal_key(None, 1, True)
        scene.horizontal_key(None, 1, False)
        scene.horizontal_key(None, -1, True)
        actions = [scene.action]
        sequence_ids = [scene.sequence_state.sequence_id]
        for _ in range(18):
            scene.advance_animation()
            actions.append(scene.action)
            sequence_ids.append(scene.sequence_state.sequence_id)

        self.assertEqual(
            actions,
            [1, 2, 3, 4, *range(53, 66), 13, 14],
        )
        self.assertNotIn(RUN_STOP_SEQUENCE, sequence_ids)
        self.assertNotIn(IDLE_SEQUENCE, sequence_ids)
        self.assertEqual(scene.sequence_state.facing, 0)
        self.assertTrue(scene.run_active)
        self.assertEqual(scene.run_direction, -1)

    def test_opposite_direction_at_tap_release_pose_enters_drift(self):
        scene = self.scene(facing=1)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None

        scene.horizontal_key(None, 1, True)
        for _ in range(7):
            scene.advance_animation()
        self.assertEqual(scene.action, TAP_RELEASE_ACTION)

        scene.horizontal_key(None, 1, False)
        scene.horizontal_key(None, -1, True)
        scene.advance_animation()

        self.assertEqual(scene.action, 53)
        self.assertEqual(scene.sequence_state.sequence_id, RUNNING_DRIFT_SEQUENCE)
        self.assertEqual(scene.sequence_state.facing, 1)
        self.assertNotEqual(scene.sequence_state.sequence_id, RUN_STOP_SEQUENCE)
        for _ in range(12):
            scene.advance_animation()
        self.assertEqual(scene.action, 65)
        self.assertEqual(scene.sequence_state.facing, 1)
        scene.advance_animation()
        self.assertEqual(scene.action, 13)
        self.assertEqual(scene.sequence_state.sequence_id, 202)
        self.assertEqual(scene.sequence_state.facing, 0)

    def test_releasing_opposite_direction_during_turn_cancels_followup_run(self):
        scene = self.scene(facing=1)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None

        scene.horizontal_key(None, -1, True)
        self.assertEqual(scene.action, 45)
        self.assertIsNone(scene.pending_action)
        scene.horizontal_key(None, -1, False)
        self.assertIsNone(scene.pending_action)

        for _ in range(12):
            scene.advance_animation()

        self.assertEqual(scene.sequence_state.facing, 0)
        self.assertEqual(scene.action, 15)
        self.assertFalse(scene.run_active)

    def test_held_direction_resumes_running_after_turn_action_48(self):
        scene = self.scene(facing=0)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None

        scene.horizontal_key(None, 1, True)
        actions = [scene.action]
        for _ in range(4):
            scene.advance_animation()
            actions.append(scene.action)

        self.assertEqual(actions, [45, 46, 47, 48, 1])
        self.assertEqual(scene.sequence_state.sequence_id, RUN_START_SEQUENCE)
        self.assertTrue(scene.run_active)
        self.assertIsNone(scene.pending_action)

    def test_released_direction_finishes_standing_turn_without_run(self):
        scene = self.scene(facing=0)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None

        scene.horizontal_key(None, 1, True)
        scene.horizontal_key(None, 1, False)
        actions = [scene.action]
        for _ in range(8):
            scene.advance_animation()
            actions.append(scene.action)

        self.assertEqual(actions, [*range(45, 53), 15])
        self.assertFalse(scene.run_active)

    def test_running_reversal_begins_from_run_action_4(self):
        scene = self.scene(sequence_id=RUN_START_SEQUENCE, facing=0, running=True)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None
        scene.held_directions = [-1]

        for _ in range(2):
            scene.advance_animation()
        scene.horizontal_key(None, -1, False)
        scene.horizontal_key(None, 1, True)

        self.assertEqual(scene.pending_action.mode, "turn")
        scene.advance_animation()
        self.assertEqual(scene.action, 3)
        scene.advance_animation()
        self.assertEqual(scene.action, 4)
        scene.advance_animation()

        self.assertEqual(scene.sequence_state.sequence_id, RUNNING_DRIFT_SEQUENCE)
        self.assertEqual(scene.action, 53)
        self.assertEqual(scene.sequence_state.facing, 0)
        self.assertTrue(scene.run_active)
        self.assertEqual(scene.run_direction, 1)
        self.assertIsNone(scene.pending_action)

    def test_jump_during_a_single_run_cycle_is_buffered_as_running_jump(self):
        scene = self.scene(facing=1)
        scene.horizontal_key(None, 1, True)
        scene.up_held = True

        scene.start_jump()

        self.assertEqual(scene.sequence_state.sequence_id, RUN_START_SEQUENCE)
        self.assertEqual(scene.pending_action.kind, "jump")
        self.assertTrue(scene.pending_action.running)
        while True:
            frame = scene.sequence_runtime.next_frame()
            if frame.sequence_id == 202 and frame.action == 14:
                break
        self.assertTrue(scene.prepare_next_sequence(run_cycle_boundary=True))
        self.assertEqual(scene.sequence_state.sequence_id, RUN_JUMP_SEQUENCE)

    def test_jump_shows_its_first_pose_immediately(self):
        scene = self.scene(facing=1)
        scene.root = DummyRoot()
        scene.animation_after_id = "pending-tick"
        scene.next_animation_at = 0
        scene.render = lambda: None
        scene.up_held = True

        scene.start_jump()

        self.assertEqual(scene.sequence_state.sequence_id, JUMP_VERTICAL_SEQUENCE)
        self.assertEqual(scene.action, 67)
        self.assertEqual(scene.sequence_state.cursor, 3)
        self.assertEqual(scene.root.cancelled, ["pending-tick"])

    def test_jump_during_run_cycle_uses_original_running_jump(self):
        scene = self.scene(sequence_id=RUN_CYCLE_SEQUENCE, facing=1, running=True)
        scene.held_directions = [1]
        scene.horizontal_input = 1
        scene.up_held = True

        scene.start_jump()

        self.assertEqual(scene.sequence_state.sequence_id, RUN_CYCLE_SEQUENCE)
        self.assertEqual(scene.pending_action.kind, "jump")
        for _ in range(8):
            scene.sequence_runtime.next_frame()
        self.assertTrue(scene.prepare_next_sequence(run_cycle_boundary=True))
        self.assertEqual(scene.sequence_state.sequence_id, RUN_JUMP_SEQUENCE)

    def test_running_jump_begins_at_first_eligible_run_pose_and_resumes_running(self):
        scene = self.scene(sequence_id=RUN_CYCLE_SEQUENCE, facing=1, running=True)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None
        scene.run_direction = 1
        scene.held_directions = [1]
        scene.horizontal_input = 1
        scene.up_held = True

        scene.start_jump()
        self.assertEqual(scene.pending_action, BufferedCommand("jump", 1, running=True))
        scene.advance_animation()
        self.assertEqual(scene.action, 7)
        scene.advance_animation()
        self.assertEqual((scene.sequence_state.sequence_id, scene.action), (4, 34))
        self.assertTrue(scene.run_active)
        self.assertEqual(scene.run_direction, 1)
        self.assertIsNone(scene.pending_action)

        for _ in range(11):
            scene.advance_animation()
        self.assertEqual((scene.sequence_state.sequence_id, scene.action), (201, 7))
        self.assertTrue(scene.run_active)
        self.assertEqual(scene.sequence_state.current_y, 0)

    def test_holding_up_and_run_direction_repeats_running_jump_after_landing(self):
        for facing, direction in ((0, -1), (1, 1)):
            with self.subTest(facing=facing):
                scene = self.scene(sequence_id=RUN_CYCLE_SEQUENCE, facing=facing, running=True)
                scene.root = DummyRoot()
                scene.animation_after_id = None
                scene.next_animation_at = 0
                scene.render = lambda: None
                scene.run_direction = direction
                scene.held_directions = [direction]
                scene.horizontal_input = direction
                scene.up_held = True

                scene.start_jump()
                scene.advance_animation()
                scene.advance_animation()
                actions = [scene.action]
                for _ in range(24):
                    scene.advance_animation()
                    actions.append(scene.action)

                self.assertEqual(actions, [*range(34, 45), 7] * 2 + [34])
                self.assertEqual(scene.sequence_state.sequence_id, RUN_JUMP_SEQUENCE)
                self.assertTrue(scene.run_active)
                self.assertEqual(scene.run_direction, direction)

    def test_releasing_up_during_running_jump_prevents_repetition(self):
        scene = self.scene(sequence_id=RUN_CYCLE_SEQUENCE, facing=1, running=True)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None
        scene.run_direction = 1
        scene.held_directions = [1]
        scene.horizontal_input = 1
        scene.up_held = True
        scene.start_jump()
        scene.advance_animation()
        scene.advance_animation()
        scene.set_key_state("up", False)

        actions = [scene.action]
        for _ in range(12):
            scene.advance_animation()
            actions.append(scene.action)

        self.assertEqual(actions, [*range(34, 45), 7, 8])
        self.assertEqual(scene.sequence_state.sequence_id, RUN_CYCLE_SEQUENCE)
        self.assertTrue(scene.run_active)

    def test_opposite_arrow_with_held_up_during_running_jump_keeps_running_context(self):
        for facing in (0, 1):
            direction = 1 if facing else -1
            for pose in range(34, 45):
                with self.subTest(facing=facing, pose=pose):
                    scene = self.running_jump_scene(facing)
                    for _ in range(pose - 34):
                        scene.advance_animation()
                    before = vars(scene.sequence_state).copy()
                    scene.horizontal_key(None, -direction, True)
                    self.assertEqual(vars(scene.sequence_state), before)
                    if facing:
                        self.assertEqual(
                            scene.pending_action, BufferedCommand("jump", -1, running=True)
                        )
                    else:
                        # ReadKeyboard gives Left priority over Right.
                        self.assertIsNone(scene.pending_action)
                    actions = [scene.action]
                    for _ in range(46 - pose):
                        scene.advance_animation()
                        actions.append(scene.action)
                    self.assertEqual(
                        actions, [*range(pose, 45), 7, 53 if facing else 34]
                    )
                    self.assertEqual(
                        scene.sequence_state.sequence_id,
                        RUNNING_DRIFT_SEQUENCE if facing else RUN_JUMP_SEQUENCE,
                    )
                    self.assertIsNone(scene.pending_action)

    def test_releasing_left_before_running_jump_lands_restores_right_up_chord(self):
        for pose in range(34, 45):
            with self.subTest(pose=pose):
                scene = self.running_jump_scene()
                for _ in range(pose - 34):
                    scene.advance_animation()
                before = vars(scene.sequence_state).copy()
                scene.horizontal_key(None, -1, True)
                scene.horizontal_key(None, -1, False)
                self.assertEqual(vars(scene.sequence_state), before)
                self.assertEqual(
                    scene.pending_action, BufferedCommand("jump", 1, running=True)
                )
                actions = [scene.action]
                for _ in range(46 - pose):
                    scene.advance_animation()
                    actions.append(scene.action)
                self.assertEqual(actions, [*range(pose, 45), 7, 34])
                self.assertIsNone(scene.pending_action)

    def test_fresh_opposite_jump_chord_uses_first_legal_running_reversal_pose(self):
        for up_first in (False, True):
            with self.subTest(up_first=up_first):
                scene = self.sword_scene()
                scene.sequence_state.facing = 1
                scene.start_sequence(RUN_CYCLE_SEQUENCE)
                scene.run_active = True
                scene.run_direction = 1
                scene.held_directions = [1]
                scene.sample_keyboard()
                scene.advance_animation()
                self.assertEqual(scene.action, 7)
                if up_first:
                    scene.up_key(None)
                    scene.horizontal_key(None, -1, True)
                else:
                    scene.horizontal_key(None, -1, True)
                    scene.up_key(None)
                scene.advance_animation()
                self.assertEqual(
                    (scene.sequence_state.sequence_id, scene.action), (6, 53)
                )
                self.assertIsNone(scene.pending_action)

    def test_up_repressed_during_running_jump_must_remain_held_past_landing_reset(self):
        for facing, direction in ((0, -1), (1, 1)):
            for pose in range(34, 45):
                for held in (False, True):
                    with self.subTest(facing=facing, pose=pose, held=held):
                        scene = self.scene(
                            sequence_id=RUN_CYCLE_SEQUENCE, facing=facing, running=True
                        )
                        scene.root = DummyRoot()
                        scene.animation_after_id = None
                        scene.next_animation_at = 0
                        scene.render = lambda: None
                        scene.run_direction = direction
                        scene.held_directions = [direction]
                        scene.horizontal_input = direction
                        scene.up_key(None)
                        scene.advance_animation()
                        scene.advance_animation()
                        self.assertEqual((scene.sequence_state.sequence_id, scene.action), (4, 34))
                        scene.set_key_state("up", False)
                        for _ in range(pose - 34):
                            scene.advance_animation()

                        before = vars(scene.sequence_state).copy()
                        scene.up_key(None)
                        self.assertEqual(vars(scene.sequence_state), before)
                        self.assertEqual(
                            scene.pending_action, BufferedCommand("jump", direction, running=True)
                        )
                        if not held:
                            scene.set_key_state("up", False)
                        actions = [scene.action]
                        for _ in range(46 - pose):
                            scene.advance_animation()
                            actions.append(scene.action)

                        self.assertEqual(actions, [*range(pose, 45), 7, 34 if held else 8])
                        self.assertEqual(
                            scene.sequence_state.sequence_id,
                            RUN_JUMP_SEQUENCE if held else RUN_CYCLE_SEQUENCE,
                        )
                        self.assertIsNone(scene.pending_action)
                        self.assertTrue(scene.run_active)

    def test_running_jump_discards_released_opposite_chord_at_final_landing_pose(self):
        for pose in range(34, 45):
            with self.subTest(pose=pose):
                scene = self.running_jump_scene()
                for _ in range(pose - 34):
                    scene.advance_animation()
                scene.horizontal_key(None, -1, True)
                scene.set_key_state("up", False)
                scene.horizontal_key(None, 1, False)
                scene.horizontal_key(None, -1, False)
                self.assertIsNotNone(scene.pending_action)
                actions = [scene.action]
                for _ in range(46 - pose):
                    scene.advance_animation()
                    actions.append(scene.action)
                self.assertEqual(actions, [*range(pose, 45), 7, 53])
                self.assertEqual(scene.sequence_state.sequence_id, RUN_STOP_SEQUENCE)
                self.assertIsNone(scene.pending_action)
                for _ in range(12):
                    scene.advance_animation()
                self.assertEqual((scene.action, scene.sequence_state.facing), (15, 1))

    def test_running_jump_landing_clears_directional_requests_but_not_ctrl(self):
        for command in (
            BufferedCommand("jump", -1, running=True),
            BufferedCommand("horizontal", -1, "turn"),
            BufferedCommand("crouch"),
            BufferedCommand("crawl", 1),
            BufferedCommand("sword_draw"),
        ):
            with self.subTest(command=command):
                scene = self.running_jump_scene()
                for _ in range(10):
                    scene.advance_animation()
                self.assertEqual(scene.action, 44)
                scene.pending_action = command
                scene.update_running_jump_controls()
                self.assertEqual(
                    scene.pending_action, command if command.kind == "sword_draw" else None
                )
                self.assertEqual(scene.held_directions, [1])
                self.assertTrue(scene.up_held)
                self.assertEqual((scene.action, scene.sequence_state.current_y), (44, 0))

    def test_releasing_up_at_landing_prevents_next_running_jump(self):
        scene = self.scene(sequence_id=RUN_CYCLE_SEQUENCE, facing=1, running=True)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None
        scene.run_direction = 1
        scene.held_directions = [1]
        scene.horizontal_input = 1
        scene.up_held = True
        scene.start_jump()
        for _ in range(13):
            scene.advance_animation()
        self.assertEqual((scene.sequence_state.sequence_id, scene.action), (201, 7))

        scene.set_key_state("up", False)
        scene.advance_animation()

        self.assertEqual((scene.sequence_state.sequence_id, scene.action), (201, 8))

    def test_releasing_direction_during_running_jump_stops_after_landing(self):
        scene = self.scene(sequence_id=RUN_CYCLE_SEQUENCE, facing=1, running=True)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None
        scene.run_direction = 1
        scene.held_directions = [1]
        scene.horizontal_input = 1
        scene.up_held = True
        scene.start_jump()
        scene.advance_animation()
        scene.advance_animation()

        scene.horizontal_key(None, 1, False)
        self.assertTrue(scene.run_stop_requested)
        actions = [scene.action]
        for _ in range(11):
            scene.advance_animation()
            actions.append(scene.action)
        self.assertEqual(actions, [*range(34, 45), 7])
        self.assertEqual(actions.count(34), 1)
        self.assertEqual(scene.sequence_state.current_y, 0)
        scene.advance_animation()
        self.assertEqual(scene.sequence_state.sequence_id, RUN_STOP_SEQUENCE)
        self.assertEqual(scene.action, 53)
        scene.advance_animation()
        self.assertEqual(scene.action, 54)

    def test_running_jump_on_cycle_boundary_keeps_its_first_pose(self):
        scene = self.scene(sequence_id=202, facing=1, running=True)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None
        scene.sequence_state.action = 14
        scene.run_cycle_boundary_pending = True
        scene.pending_action = BufferedCommand("jump", 1, running=True)
        scene.run_stop_requested = True

        scene.advance_animation()

        self.assertEqual((scene.sequence_state.sequence_id, scene.action), (4, 34))
        self.assertTrue(scene.run_active)
        self.assertTrue(scene.run_stop_requested)

    def test_run_stops_at_the_end_of_the_current_run_cycle(self):
        scene = self.scene(sequence_id=RUN_CYCLE_SEQUENCE, running=True)
        scene.run_stop_requested = True
        for _ in range(8):
            scene.sequence_runtime.next_frame()

        self.assertEqual(scene.sequence_state.sequence_id, 202)
        self.assertTrue(scene.prepare_next_sequence(run_cycle_boundary=True))

        self.assertEqual(scene.sequence_state.sequence_id, RUN_STOP_SEQUENCE)
        self.assertFalse(scene.run_active)
        self.assertEqual(
            [scene.sequence_runtime.next_frame().action for _ in range(9)],
            [53, 54, 55, 56, 49, 50, 51, 52, 15],
        )

    def test_running_reversal_at_cycle_boundary_keeps_first_drift_pose(self):
        scene = self.scene(sequence_id=RUN_CYCLE_SEQUENCE, facing=0, running=True)
        scene.run_direction = -1
        for _ in range(8):
            scene.sequence_runtime.next_frame()
        scene.player_x = scene.sequence_state.target_x
        scene.run_cycle_boundary_pending = True
        scene.pending_action = BufferedCommand("horizontal", 1, "turn")
        scene.held_directions = [1]
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None

        boundary_x = scene.sequence_state.target_x
        scene.advance_animation()

        self.assertEqual(scene.sequence_state.sequence_id, RUNNING_DRIFT_SEQUENCE)
        self.assertEqual(scene.sequence_state.facing, 0)
        self.assertEqual(scene.action, 53)
        self.assertEqual(scene.player_x, boundary_x - 2)
        self.assertFalse(scene.run_cycle_boundary_pending)

    def test_queued_reverse_turn_branches_after_action_50(self):
        scene = self.scene(facing=0)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None
        scene.horizontal_key(None, 1, True)
        self.assertEqual(scene.action, 45)
        scene.horizontal_key(None, 1, False)
        scene.horizontal_key(None, -1, True)
        self.assertEqual(scene.pending_action, BufferedCommand("horizontal", -1, "turn"))

        actions = [scene.action]
        for _ in range(6):
            scene.advance_animation()
            actions.append(scene.action)

        self.assertEqual(actions, [45, 46, 47, 48, 49, 50, 45])
        self.assertEqual(scene.sequence_state.sequence_id, STANDING_TURN_SEQUENCE)
        self.assertEqual(scene.sequence_state.facing, 0)
        self.assertIsNone(scene.pending_action)

        scene.horizontal_key(None, -1, False)
        scene.horizontal_key(None, 1, True)
        next_actions = [scene.action]
        for _ in range(6):
            scene.advance_animation()
            next_actions.append(scene.action)
        self.assertEqual(next_actions, [45, 46, 47, 48, 49, 50, 45])
        self.assertEqual(scene.sequence_state.facing, 1)
        self.assertIsNone(scene.pending_action)

    def test_latest_horizontal_input_replaces_only_the_buffered_command(self):
        scene = self.scene(facing=1)
        scene.shift_held = True
        scene.horizontal_key(None, 1, True)
        self.assertEqual(scene.sequence_state.sequence_id, SHIFT_STEP_SEQUENCE)
        cursor = scene.sequence_state.cursor

        scene.horizontal_key(None, 1, False)
        scene.horizontal_key(None, -1, True)

        self.assertEqual(scene.sequence_state.sequence_id, SHIFT_STEP_SEQUENCE)
        self.assertEqual(scene.sequence_state.cursor, cursor)
        self.assertEqual(scene.pending_action, BufferedCommand("horizontal", -1, "step"))

    def test_jump_waits_for_full_step_and_landing_sequences(self):
        scene = self.scene(facing=1)
        scene.shift_held = True
        scene.horizontal_key(None, 1, True)
        scene.up_held = True
        scene.start_jump()

        self.assertEqual(scene.sequence_state.sequence_id, SHIFT_STEP_SEQUENCE)
        self.assertEqual(scene.pending_action.kind, "jump")
        while scene.sequence_state.sequence_id != 2:
            scene.sequence_runtime.next_frame()
        self.assertTrue(scene.prepare_next_sequence())
        self.assertEqual(scene.sequence_state.sequence_id, JUMP_FORWARD_SEQUENCE)

        for _ in range(18):
            scene.sequence_runtime.next_frame()
        self.assertEqual(scene.sequence_state.sequence_id, JUMP_FORWARD_SEQUENCE)
        self.assertFalse(scene._is_resting())
        scene.sequence_runtime.next_frame()
        self.assertEqual(scene.sequence_state.sequence_id, IDLE_SEQUENCE)

    def test_jump_mapping_rejects_opposite_chords_and_keeps_running_jump(self):
        self.assertEqual(jump_sequence_for_input(0, facing=0), JUMP_VERTICAL_SEQUENCE)
        self.assertEqual(jump_sequence_for_input(-1, facing=0), JUMP_FORWARD_SEQUENCE)
        self.assertEqual(jump_sequence_for_input(-1, facing=0, running=True), 4)
        with self.assertRaises(ValueError):
            jump_sequence_for_input(1, facing=0)
        with self.assertRaises(ValueError):
            jump_sequence_for_input(1, facing=0, running=True)
        with self.assertRaises(ValueError):
            jump_sequence_for_input(2, facing=0)

    def test_vertical_jump_uses_original_arc_and_returns_to_idle(self):
        runtime = self.runtime(JUMP_VERTICAL_SEQUENCE, facing=1)
        frames = []
        while runtime.state.sequence_id != 2:
            frames.append(runtime.next_frame())

        self.assertEqual(
            [frame.action for frame in frames[:11]], list(range(67, 78))
        )
        self.assertEqual(frames[-1].action, 15)
        self.assertEqual(runtime.state.current_y, 0)
        self.assertEqual(runtime.state.sequence_events, [(-19, ())])

    def test_vertical_jump_can_be_repeated_after_landing(self):
        scene = self.scene(facing=1)
        for _ in range(2):
            scene.up_held = True
            scene.start_jump()
            self.assertEqual(scene.sequence_state.sequence_id, JUMP_VERTICAL_SEQUENCE)
            while scene.sequence_state.sequence_id != 2:
                scene.sequence_runtime.next_frame()
            scene.up_held = False

    def test_held_up_repeats_vertical_jump_only_after_landing(self):
        scene = self.scene(facing=1)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None
        scene.up_held = True
        scene.start_jump_if_needed()

        actions = [scene.action]
        for _ in range(40):
            scene.advance_animation()
            actions.append(scene.action)
            if actions.count(67) == 2:
                break

        self.assertEqual(actions[0], 67)
        self.assertEqual(actions[-2:], [85, 67])
        self.assertNotIn(15, actions)
        self.assertEqual(scene.sequence_state.sequence_id, JUMP_VERTICAL_SEQUENCE)
        self.assertTrue(scene.jump_started_for_press)

        scene.set_key_state("up", False)
        while scene.sequence_state.sequence_id != IDLE_SEQUENCE:
            scene.advance_animation()
        scene.advance_animation()
        self.assertEqual(scene.action, 15)

    def test_standing_horizontal_jump_works_in_either_key_order(self):
        for up_first in (False, True):
            with self.subTest(up_first=up_first):
                scene = self.scene(facing=0)
                scene.root = DummyRoot()
                scene.animation_after_id = None
                scene.next_animation_at = 0
                scene.render = lambda: None

                if up_first:
                    scene.up_key(None)
                    scene.horizontal_key(None, -1, True)
                else:
                    scene.horizontal_key(None, -1, True)
                    self.assertEqual(scene.action, 1)
                    scene.up_key(None)

                self.assertEqual(scene.sequence_state.sequence_id, JUMP_FORWARD_SEQUENCE)
                self.assertEqual(scene.action, 16)
                self.assertEqual(scene.player_x, 112)
                self.assertFalse(scene.run_active)
                self.assertIsNone(scene.pending_action)
                scene.set_key_state("up", False)
                actions = [scene.action]
                while scene.sequence_state.sequence_id != IDLE_SEQUENCE:
                    scene.advance_animation()
                    actions.append(scene.action)
                self.assertEqual(actions, [*range(16, 34), 15])
                self.assertNotIn(160, actions)

    def test_held_horizontal_jump_repeats_and_release_keeps_explicit_queue(self):
        scene = self.scene(facing=1)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None
        scene.up_key(None)
        scene.horizontal_key(None, 1, True)

        self.assertEqual(scene.sequence_state.sequence_id, JUMP_FORWARD_SEQUENCE)
        actions = [scene.action]
        for _ in range(30):
            scene.advance_animation()
            actions.append(scene.action)
            if actions.count(16) == 2:
                break
        self.assertEqual(scene.sequence_state.sequence_id, JUMP_FORWARD_SEQUENCE)
        self.assertEqual(actions[-2:], [33, 16])
        self.assertNotIn(15, actions)

        scene.pending_action = BufferedCommand("jump", 1)
        scene.set_key_state("up", False)
        self.assertEqual(scene.pending_action, BufferedCommand("jump", 1))

    def test_turn_then_horizontal_jump_tap_is_buffered_as_one_command(self):
        for up_first in (False, True):
            with self.subTest(up_first=up_first):
                scene = self.scene(facing=1)
                scene.root = DummyRoot()
                scene.animation_after_id = None
                scene.next_animation_at = 0
                scene.render = lambda: None

                scene.horizontal_key(None, -1, True)
                self.assertEqual(scene.action, 45)
                if up_first:
                    scene.horizontal_key(None, -1, False)
                    scene.up_key(None)
                    self.assertEqual(scene.pending_action, BufferedCommand("jump"))
                    scene.horizontal_key(None, -1, True)
                else:
                    scene.advance_animation()
                    scene.up_key(None)

                self.assertEqual(scene.pending_action, BufferedCommand("jump", -1))
                scene.set_key_state("up", False)
                scene.horizontal_key(None, -1, False)
                self.assertEqual(scene.pending_action, BufferedCommand("jump", -1))

                actions = [scene.action]
                for _ in range(6 if up_first else 5):
                    scene.advance_animation()
                    actions.append(scene.action)

                self.assertEqual(
                    actions, [*range(45 if up_first else 46, 51), 16]
                )
                self.assertEqual(scene.sequence_state.sequence_id, JUMP_FORWARD_SEQUENCE)
                self.assertIsNone(scene.pending_action)

    def test_jump_queued_late_in_turn_skips_final_turn_pose(self):
        scene = self.scene(facing=1)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None

        scene.horizontal_key(None, -1, True)
        scene.horizontal_key(None, -1, False)
        for _ in range(6):
            scene.advance_animation()
        self.assertEqual(scene.action, 51)

        scene.up_key(None)
        scene.horizontal_key(None, -1, True)
        scene.advance_animation()

        self.assertEqual(scene.action, 16)
        self.assertEqual(scene.sequence_state.sequence_id, JUMP_FORWARD_SEQUENCE)
        self.assertIsNone(scene.pending_action)

    def test_opposite_jump_chord_from_rest_only_turns(self):
        for facing in (0, 1):
            for up_first in (False, True):
                with self.subTest(facing=facing, up_first=up_first):
                    scene = self.scene(facing=facing)
                    scene.root = DummyRoot()
                    scene.animation_after_id = None
                    scene.next_animation_at = 0
                    scene.render = lambda: None
                    opposite = 1 if facing == 0 else -1

                    if up_first:
                        scene.up_key(None)
                        scene.horizontal_key(None, opposite, True)
                    else:
                        scene.horizontal_key(None, opposite, True)
                        scene.up_key(None)

                    self.assertEqual(scene.sequence_state.sequence_id, STANDING_TURN_SEQUENCE)
                    self.assertEqual(scene.action, 45)
                    self.assertIsNone(scene.pending_action)

                    actions = [scene.action]
                    for _ in range(16):
                        scene.advance_animation()
                        actions.append(scene.action)
                    self.assertEqual(actions[:8], list(range(45, 53)))
                    self.assertNotIn(67, actions)
                    self.assertNotIn(16, actions)
                    self.assertEqual(scene.action, 15)
                    self.assertEqual(scene.sequence_state.facing, 1 - facing)
                    self.assertIsNone(scene.pending_action)

    def test_opposite_jump_chord_during_run_uses_drift(self):
        for up_first in (False, True):
            with self.subTest(up_first=up_first):
                scene = self.scene(sequence_id=RUN_CYCLE_SEQUENCE, facing=1, running=True)
                scene.root = DummyRoot()
                scene.animation_after_id = None
                scene.next_animation_at = 0
                scene.render = lambda: None
                scene.run_direction = 1
                scene.held_directions = [1]
                scene.sample_keyboard()
                if up_first:
                    scene.up_key(None)
                    scene.horizontal_key(None, -1, True)
                else:
                    scene.horizontal_key(None, -1, True)
                    scene.up_key(None)

                self.assertEqual(
                    scene.pending_action, BufferedCommand("jump", -1, running=True)
                )
                self.assertTrue(scene.dispatch_pending_action(was_running=True))
                self.assertEqual(scene.sequence_state.sequence_id, RUNNING_DRIFT_SEQUENCE)
                self.assertEqual(scene.action, 53)
                self.assertIsNone(scene.pending_action)

    def test_opposite_chord_during_first_run_pose_turns_from_start_position(self):
        scene = self.scene(facing=1)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None

        scene.horizontal_key(None, 1, True)
        start_x = scene.run_start_x
        scene.horizontal_key(None, -1, True)
        scene.up_key(None)

        self.assertEqual(scene.sequence_state.sequence_id, STANDING_TURN_SEQUENCE)
        self.assertEqual(scene.action, 45)
        self.assertEqual(scene.player_x, start_x - 12)
        self.assertIsNone(scene.run_start_x)
        self.assertIsNone(scene.pending_action)

    def test_up_tap_during_turn_is_buffered_even_if_released_before_delay(self):
        scene = self.scene(facing=1)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None
        scene.horizontal_key(None, -1, True)
        scene.horizontal_key(None, -1, False)

        scene.up_key(None)
        scene.set_key_state("up", False)

        self.assertEqual(scene.pending_action, BufferedCommand("jump"))
        for _ in range(8):
            scene.advance_animation()
        self.assertEqual(scene.sequence_state.sequence_id, JUMP_VERTICAL_SEQUENCE)
        self.assertEqual(scene.action, 67)

    def test_short_up_tap_from_idle_still_starts_one_jump(self):
        scene = self.scene(facing=1)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None

        scene.up_key(None)
        scene.set_key_state("up", False)

        self.assertEqual(scene.sequence_state.sequence_id, JUMP_VERTICAL_SEQUENCE)
        self.assertEqual(scene.action, 67)
        self.assertFalse(scene.up_held)
        self.assertIsNone(scene.pending_action)

    def test_tapped_chord_during_step_starts_forward_jump_at_step_end(self):
        scene = self.scene(facing=1)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None
        scene.shift_held = True
        scene.horizontal_key(None, 1, True)
        self.assertEqual(scene.action, 121)

        scene.up_key(None)
        self.assertEqual(scene.pending_action, BufferedCommand("jump", 1))
        scene.set_key_state("up", False)
        scene.horizontal_key(None, 1, False)
        scene.shift_held = False

        actions = [scene.action]
        for _ in range(12):
            scene.advance_animation()
            actions.append(scene.action)

        self.assertEqual(actions, [*range(121, 133), 16])
        self.assertEqual(scene.sequence_state.sequence_id, JUMP_FORWARD_SEQUENCE)
        self.assertIsNone(scene.pending_action)

    def test_tapped_turn_during_jump_starts_without_idle_pose(self):
        scene = self.scene(facing=1)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None
        scene.up_key(None)
        scene.horizontal_key(None, 1, True)
        scene.set_key_state("up", False)
        scene.horizontal_key(None, 1, False)
        self.assertEqual(scene.action, 16)

        scene.horizontal_key(None, -1, True)
        scene.horizontal_key(None, -1, False)
        self.assertEqual(scene.pending_action, BufferedCommand("horizontal", -1, "turn"))

        actions = [scene.action]
        for _ in range(18):
            scene.advance_animation()
            actions.append(scene.action)

        self.assertEqual(actions, [*range(16, 34), 45])
        self.assertEqual(scene.sequence_state.sequence_id, STANDING_TURN_SEQUENCE)
        self.assertIsNone(scene.pending_action)

    def test_opposite_jump_chord_during_jump_only_turns_after_landing(self):
        for up_first in (False, True):
            with self.subTest(up_first=up_first):
                scene = self.scene(facing=1)
                scene.root = DummyRoot()
                scene.animation_after_id = None
                scene.next_animation_at = 0
                scene.render = lambda: None

                scene.up_key(None)
                scene.horizontal_key(None, 1, True)
                scene.set_key_state("up", False)
                scene.horizontal_key(None, 1, False)
                self.assertEqual(scene.action, 16)

                for _ in range(5):
                    scene.advance_animation()
                if up_first:
                    scene.up_key(None)
                    scene.horizontal_key(None, -1, True)
                else:
                    scene.horizontal_key(None, -1, True)
                    scene.up_key(None)
                self.assertEqual(scene.pending_action, BufferedCommand("jump", -1))
                scene.set_key_state("up", False)
                scene.horizontal_key(None, -1, False)

                actions = [scene.action]
                for _ in range(13):
                    scene.advance_animation()
                    actions.append(scene.action)

                self.assertEqual(actions, [*range(21, 34), 45])
                self.assertEqual(scene.sequence_state.sequence_id, STANDING_TURN_SEQUENCE)
                self.assertIsNone(scene.pending_action)
                for _ in range(16):
                    scene.advance_animation()
                self.assertEqual(scene.action, 15)
                self.assertEqual(scene.sequence_state.facing, 0)
                self.assertIsNone(scene.pending_action)

    def test_held_opposite_jump_chord_does_not_jump_after_turn(self):
        scene = self.scene(facing=1)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None

        scene.up_key(None)
        scene.horizontal_key(None, 1, True)
        scene.set_key_state("up", False)
        scene.horizontal_key(None, 1, False)
        for _ in range(5):
            scene.advance_animation()
        scene.up_key(None)
        scene.horizontal_key(None, -1, True)

        actions = []
        for _ in range(36):
            scene.advance_animation()
            actions.append(scene.action)

        self.assertEqual(actions.count(45), 1)
        self.assertNotIn(67, actions)
        self.assertNotIn(16, actions)
        self.assertEqual(scene.sequence_state.facing, 0)
        self.assertEqual(scene.action, 15)
        self.assertIsNone(scene.pending_action)

        scene.set_key_state("up", False)
        scene.horizontal_key(None, -1, False)
        scene.up_key(None)
        scene.horizontal_key(None, -1, True)
        self.assertEqual(scene.sequence_state.sequence_id, JUMP_FORWARD_SEQUENCE)
        self.assertEqual(scene.action, 16)

    def test_latest_jump_chord_replaces_opposite_chord_before_landing(self):
        scene = self.scene(facing=1)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None

        scene.up_key(None)
        scene.horizontal_key(None, 1, True)
        scene.set_key_state("up", False)
        scene.horizontal_key(None, 1, False)
        for _ in range(5):
            scene.advance_animation()
        scene.up_key(None)
        scene.horizontal_key(None, -1, True)
        scene.set_key_state("up", False)
        scene.horizontal_key(None, -1, False)
        scene.up_key(None)
        scene.horizontal_key(None, 1, True)
        scene.set_key_state("up", False)
        scene.horizontal_key(None, 1, False)

        self.assertEqual(scene.pending_action, BufferedCommand("jump", 1))
        for _ in range(13):
            scene.advance_animation()
        self.assertEqual(scene.sequence_state.sequence_id, JUMP_FORWARD_SEQUENCE)
        self.assertEqual(scene.action, 16)
        self.assertEqual(scene.sequence_state.facing, 1)
        self.assertIsNone(scene.pending_action)

    def test_finished_jump_clears_repeat_state_without_pending_command(self):
        scene = self.scene(facing=1)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None

        scene.up_key(None)
        scene.horizontal_key(None, 1, True)
        scene.set_key_state("up", False)
        scene.horizontal_key(None, 1, False)
        for _ in range(18):
            scene.advance_animation()

        self.assertEqual(scene.action, 15)
        self.assertFalse(scene.jump_repeat_armed)
        self.assertIsNone(scene.pending_action)

    def test_latest_command_replaces_older_chord_in_single_buffer(self):
        scene = self.scene(facing=1)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None
        scene.shift_held = True
        scene.horizontal_key(None, 1, True)
        scene.shift_held = False

        scene.up_key(None)
        self.assertEqual(scene.pending_action, BufferedCommand("jump", 1))
        scene.set_key_state("up", False)
        scene.horizontal_key(None, 1, False)
        scene.horizontal_key(None, -1, True)
        scene.horizontal_key(None, -1, False)

        self.assertEqual(scene.pending_action, BufferedCommand("horizontal", -1, "turn"))
        for _ in range(12):
            scene.advance_animation()
        self.assertEqual(scene.sequence_state.sequence_id, STANDING_TURN_SEQUENCE)
        self.assertEqual(scene.action, 45)

    def test_forward_and_back_jumps_finish_the_original_landing_sequences(self):
        for sequence_id in (JUMP_FORWARD_SEQUENCE, 16):
            with self.subTest(sequence_id=sequence_id):
                runtime = self.runtime(sequence_id, facing=1)
                frames = []
                while runtime.state.sequence_id != 2:
                    frames.append(runtime.next_frame())

                self.assertEqual(frames[0].action, 16 if sequence_id == JUMP_FORWARD_SEQUENCE else 67)
                self.assertEqual(frames[-1].action, 15)
                self.assertEqual(runtime.state.current_y, 0)
                if sequence_id == 16:
                    self.assertIn((-19, ()), runtime.state.sequence_events)

    def test_down_tap_plays_full_lower_and_rise_without_idle_gap(self):
        scene = self.scene()
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None

        scene.set_key_state("down", True)
        scene.set_key_state("down", False)
        actions = [scene.action]
        for _ in range(13):
            scene.advance_animation()
            actions.append(scene.action)

        self.assertEqual(actions, [107, 108, 109, *range(110, 120), 15])
        self.assertEqual(scene.sequence_state.sequence_id, IDLE_SEQUENCE)

    def test_held_down_waits_low_then_rises_on_release(self):
        scene = self.scene()
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None

        scene.set_key_state("down", True)
        self.assertEqual(scene.sequence_state.sequence_id, CROUCH_STANDING_LOWER_SEQUENCE)
        for _ in range(10):
            scene.advance_animation()
        self.assertEqual(scene.sequence_state.sequence_id, CROUCH_HOLD_SEQUENCE)
        self.assertEqual(scene.action, 109)
        held_x = scene.player_x
        for _ in range(12):
            scene.advance_animation()
            self.assertEqual((scene.action, scene.player_x), (109, held_x))

        scene.set_key_state("down", False)
        actions = []
        for _ in range(10):
            scene.advance_animation()
            actions.append(scene.action)
        self.assertEqual(actions, list(range(110, 120)))
        self.assertEqual(scene.sequence_state.sequence_id, CROUCH_RISE_SEQUENCE)

    def test_crouch_direction_tap_finishes_one_step_and_stays_low(self):
        scene = self.scene()
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None

        scene.set_key_state("down", True)
        for _ in range(4):
            scene.advance_animation()
        scene.horizontal_key(None, -1, True)
        self.assertEqual(scene.action, 110)
        scene.horizontal_key(None, -1, False)
        actions = []
        for _ in range(4):
            scene.advance_animation()
            actions.append(scene.action)
        self.assertEqual(actions, [111, 112, 108, 109])
        self.assertEqual(scene.sequence_state.sequence_id, CROUCH_HOLD_SEQUENCE)
        for _ in range(6):
            scene.advance_animation()
            self.assertEqual(scene.action, 109)

    def test_held_crouch_direction_repeats_whole_steps(self):
        scene = self.scene()
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None

        scene.set_key_state("down", True)
        scene.horizontal_key(None, -1, True)
        actions = [scene.action]
        for _ in range(15):
            scene.advance_animation()
            actions.append(scene.action)
        self.assertEqual(
            actions,
            [107, 108, 109, 110, 111, 112, 108, 109,
             110, 111, 112, 108, 109, 110, 111, 112],
        )
        self.assertEqual(scene.sequence_state.sequence_id, CROUCH_STEP_SEQUENCE)

        scene.horizontal_key(None, -1, False)
        scene.set_key_state("down", False)
        actions = []
        for _ in range(14):
            scene.advance_animation()
            actions.append(scene.action)
        self.assertEqual(actions, [108, 109, *range(110, 120), 15, 15])
        self.assertEqual(scene.sequence_state.sequence_id, IDLE_SEQUENCE)

    def test_crouch_step_tap_during_descent_is_queued(self):
        scene = self.scene()
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None

        scene.set_key_state("down", True)
        scene.horizontal_key(None, -1, True)
        scene.horizontal_key(None, -1, False)
        self.assertEqual(scene.pending_action, BufferedCommand("crawl", -1))
        for _ in range(3):
            scene.advance_animation()
        self.assertEqual(scene.sequence_state.sequence_id, CROUCH_STEP_SEQUENCE)
        self.assertEqual(scene.action, 110)
        self.assertEqual(scene.sequence_state.sequence_id, CROUCH_STEP_SEQUENCE)

    def test_down_during_run_start_waits_until_action_four(self):
        scene = self.scene(facing=0)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None

        scene.horizontal_key(None, -1, True)
        scene.set_key_state("down", True)
        scene.set_key_state("down", False)
        self.assertEqual(scene.pending_action, BufferedCommand("crouch"))
        self.assertFalse(scene.run_stop_requested)

        actions = [scene.action]
        for _ in range(4):
            scene.advance_animation()
            actions.append(scene.action)
        self.assertEqual(actions, [1, 2, 3, 4, 107])
        self.assertEqual(scene.sequence_state.sequence_id, CROUCH_LOWER_SEQUENCE)
        self.assertFalse(scene.run_active)

    def test_down_during_run_skips_the_stopping_sequence(self):
        scene = self.scene(sequence_id=RUN_CYCLE_SEQUENCE, facing=0, running=True)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None
        scene.run_direction = -1
        scene.held_directions = [-1]
        scene.horizontal_input = -1
        scene.advance_animation()
        self.assertEqual(scene.action, 7)

        scene.set_key_state("down", True)
        self.assertEqual(scene.action, 7)
        scene.advance_animation()

        self.assertEqual(scene.action, 107)
        self.assertEqual(scene.sequence_state.sequence_id, CROUCH_LOWER_SEQUENCE)
        self.assertFalse(scene.run_active)
        self.assertFalse(scene.run_stop_requested)

        actions = [scene.action]
        for _ in range(14):
            scene.advance_animation()
            actions.append(scene.action)
        self.assertEqual(
            actions,
            [107, 108, 109, 110, 111, 112, 108, 109,
             110, 111, 112, 108, 109, 110, 111],
        )

    def test_releasing_direction_at_run_pose_seven_stops_before_crouch(self):
        scene = self.scene(sequence_id=RUN_CYCLE_SEQUENCE, facing=0, running=True)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None
        scene.run_direction = -1
        scene.held_directions = [-1]
        scene.horizontal_input = -1
        scene.advance_animation()
        self.assertEqual(scene.action, 7)

        scene.horizontal_key(None, -1, False)
        scene.set_key_state("down", True)
        scene.advance_animation()

        self.assertEqual(scene.sequence_state.sequence_id, RUN_STOP_SEQUENCE)
        self.assertEqual(scene.action, 53)
        self.assertEqual(scene.pending_action, BufferedCommand("crouch"))

    def test_down_during_run_stop_enters_crouch_before_idle(self):
        scene = self.scene(sequence_id=RUN_STOP_SEQUENCE, facing=0)
        scene.root = DummyRoot()
        scene.animation_after_id = None
        scene.next_animation_at = 0
        scene.render = lambda: None
        for _ in range(6):
            scene.advance_animation()
        self.assertEqual(scene.action, 50)

        scene.set_key_state("down", True)
        scene.advance_animation()

        self.assertEqual(scene.action, 107)
        self.assertEqual(scene.sequence_state.sequence_id, CROUCH_STANDING_LOWER_SEQUENCE)

    def test_standing_crouch_uses_native_sixteen_pixel_lower_both_directions(self):
        self.assertEqual(self.sequences[CROUCH_STANDING_LOWER_SEQUENCE],
                         (-7, 1, -5, 3, 107, -5, 6, 108, -5, 7, -1, 117))
        for facing, direction in ((0, -1), (1, 1)):
            with self.subTest(facing=facing):
                scene = self.sword_scene()
                scene.sequence_state.facing = facing
                start_x = scene.player_x
                scene.set_key_state("down", True)
                frames = [(scene.action, scene.player_x - start_x)]
                for _ in range(2):
                    scene.advance_animation()
                    frames.append((scene.action, scene.player_x - start_x))
                self.assertEqual(frames, [(107, direction * 3), (108, direction * 9),
                                          (109, direction * 16)])
                self.assertEqual(scene.sequence_state.sequence_id, CROUCH_HOLD_SEQUENCE)

    def test_running_crouch_release_uses_first_low_pose_without_extra_hold(self):
        scene = self.sword_scene()
        scene.start_sequence(RUN_CYCLE_SEQUENCE)
        scene.run_active = True
        scene.run_direction = -1
        scene.held_directions = [-1]
        scene.horizontal_input = -1
        scene.advance_animation()
        start_x = scene.player_x
        scene.set_key_state("down", True)
        scene.set_key_state("down", False)
        frames = []
        for _ in range(4):
            scene.advance_animation()
            frames.append((scene.action, scene.player_x - start_x))
        self.assertEqual(frames, [(107, -2), (108, -10), (109, -21), (110, -24)])

    def test_rooftop_hang_still_works_in_either_shift_down_order(self):
        for down_first in (False, True):
            with self.subTest(down_first=down_first):
                scene = self.scene(facing=1)
                scene.root = DummyRoot()
                scene.animation_after_id = None
                scene.next_animation_at = 0
                scene.render = lambda: None
                scene.player_x = scene.right_platform_edge_x
                scene.sequence_state.current_x = scene.player_x
                scene.sequence_state.target_x = scene.player_x

                if down_first:
                    scene.set_key_state("down", True)
                    scene.set_key_state("shift", True)
                else:
                    scene.set_key_state("shift", True)
                    scene.set_key_state("down", True)

                self.assertTrue(scene.ledge_hanging)
                self.assertEqual(scene.sequence_state.sequence_id, LEDGE_FALL_SEQUENCE)
                self.assertEqual(scene.action, 102)

    def test_rooftop_edge_hang_and_climb_use_original_sequences(self):
        scene = self.scene(facing=1)
        scene.player_x = scene.right_platform_edge_x
        scene.sequence_state.current_x = scene.player_x
        scene.sequence_state.target_x = scene.player_x
        scene.down_held = True
        scene.shift_held = True

        scene.update_ledge_test_state()

        self.assertTrue(scene.ledge_hanging)
        self.assertEqual(scene.sequence_state.sequence_id, LEDGE_APPROACH_SEQUENCE)
        hang_actions = []
        hang_sequence_ids = []
        while scene.sequence_state.sequence_id != LEDGE_HANG_SEQUENCE:
            frame = scene.sequence_runtime.next_frame()
            hang_actions.append(frame.action)
            hang_sequence_ids.append(frame.sequence_id)
        hang_actions.append(scene.sequence_runtime.next_frame().action)
        self.assertEqual(hang_actions, [102, 103, 104, 105, 106, 106, 106])
        self.assertIn(LEDGE_FALL_SEQUENCE, hang_sequence_ids)
        self.assertIn((-10, (228,)), scene.sequence_state.sequence_events)

        scene.start_ledge_climb()
        climb_actions = []
        while scene.sequence_state.sequence_id != 2:
            climb_actions.append(scene.sequence_runtime.next_frame().action)
        self.assertEqual(climb_actions, [102, 107, 108, 109, *range(110, 120), 15])

    def test_opening_room_edge_is_read_from_the_original_level_tiles(self):
        level = self.prince["LEVL"][2000]["data"]

        edge_x = ScenePrototype._right_platform_edge(level, room_id=3, start_x=2)

        self.assertEqual(edge_x, 8 * 51)

    def test_running_jump_plays_takeoff_arc_and_landing(self):
        runtime = self.runtime(RUN_JUMP_SEQUENCE, facing=0, x=350)
        frames = [runtime.next_frame() for _ in range(11)]

        self.assertEqual([frame.action for frame in frames], list(range(34, 45)))
        self.assertEqual([frame.current_y for frame in frames], [0] * 6 + [-6, -26, -28, -7, 0])
        self.assertEqual(frames[-1].target_x, 125)
        frame = runtime.next_frame()
        self.assertEqual((frame.sequence_id, frame.action), (201, 7))

    def test_original_step_sequences_apply_their_distinct_offsets(self):
        cases = ((38, 0, 86), (32, 0, 104), (38, 1, 146), (32, 1, 128))
        for sequence_id, facing, expected_x in cases:
            with self.subTest(sequence_id=sequence_id, facing=facing):
                runtime = self.runtime(sequence_id, facing=facing)
                for _ in range(12):
                    runtime.next_frame()
                self.assertEqual(runtime.state.target_x, expected_x)

    def test_shift_step_matches_original_sequence_42_at_configured_frame_rate(self):
        runtime = self.runtime(SHIFT_STEP_SEQUENCE, facing=1)
        frames = [runtime.next_frame() for _ in range(13)]

        self.assertEqual(SHIFT_STEP_SEQUENCE, 42)
        self.assertEqual(ANIMATION_FPS, 12)
        self.assertAlmostEqual(ANIMATION_INTERVAL_MS, 1000 / 12)
        self.assertAlmostEqual(1000 / ANIMATION_INTERVAL_MS, 12)
        self.assertAlmostEqual(12 * ANIMATION_INTERVAL_MS / 1000, 1.0)
        self.assertEqual(
            [frame.action for frame in frames],
            [121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 15],
        )
        self.assertEqual(frames[11].target_x, 158)
        self.assertEqual(frames[12].sequence_id, 2)

    def test_running_cycle_loops_through_original_201_and_202_sequences(self):
        runtime = self.runtime(RUN_CYCLE_SEQUENCE, facing=1)
        frames = [runtime.next_frame() for _ in range(10)]

        self.assertEqual([frame.action for frame in frames[:8]], list(range(7, 15)))
        self.assertEqual(runtime.state.sequence_id, RUN_CYCLE_SEQUENCE)
        self.assertEqual(runtime.state.target_x, 219)

    def test_maximum_run_stride_uses_left_and_right_signs(self):
        left = self.runtime(42, facing=0)
        left_frames = [left.next_frame() for _ in range(12)]
        self.assertEqual([frame.action for frame in left_frames], list(range(121, 133)))
        self.assertEqual(left.state.target_x, 74)

        right = self.runtime(42, facing=1)
        for _ in range(12):
            right.next_frame()
        self.assertEqual(right.state.target_x, 158)

    def test_turn_animation_toggles_original_left_facing_to_right(self):
        runtime = self.runtime(STANDING_TURN_SEQUENCE, facing=0)
        frames = [runtime.next_frame() for _ in range(8)]

        self.assertEqual([frame.action for frame in frames], list(range(45, 53)))
        self.assertEqual(runtime.state.facing, 1)
        self.assertEqual(runtime.state.target_x, 125)
        self.assertEqual(runtime.next_frame().action, 15)
        self.assertEqual(runtime.state.sequence_id, 2)

    def test_original_running_drift_plays_every_pose_then_reverses(self):
        for facing in (0, 1):
            with self.subTest(facing=facing):
                runtime = self.runtime(RUNNING_DRIFT_SEQUENCE, facing=facing)
                frames = [runtime.next_frame() for _ in range(13)]

                self.assertEqual([frame.action for frame in frames], list(range(53, 66)))
                self.assertEqual([frame.sequence_id for frame in frames], [6] * 13)
                self.assertEqual(runtime.state.facing, facing)
                self.assertEqual(frames[0].target_x, 116 + (2 if facing else -2))
                self.assertEqual(ANIMATION_FPS, 12)

                next_frame = runtime.next_frame()
                self.assertEqual((next_frame.sequence_id, next_frame.action), (202, 13))
                self.assertEqual(runtime.state.facing, 1 - facing)

    def test_standing_turn_to_run_uses_original_sequence_43(self):
        runtime = self.runtime(RUNNING_TURN_SEQUENCE, facing=1)
        first = runtime.next_frame()

        self.assertEqual(first.sequence_id, 1)
        self.assertEqual(first.action, 1)
        self.assertEqual(runtime.state.facing, 1)
        self.assertEqual(first.target_x, 117)

    def test_forward_jump_uses_original_sequence_and_motion(self):
        runtime = self.runtime(JUMP_FORWARD_SEQUENCE, facing=1)
        frames = [runtime.next_frame() for _ in range(19)]

        self.assertEqual([frame.action for frame in frames], [*range(16, 34), 15])
        self.assertEqual(frames[8].current_y, -7)
        self.assertEqual(frames[9].current_y, -13)
        self.assertEqual(runtime.state.target_x, 281)
        self.assertEqual(runtime.state.current_y, 0)

    def test_running_jump_moves_in_facing_direction(self):
        for facing, expected_x in ((0, 125), (1, 575)):
            with self.subTest(facing=facing):
                runtime = self.runtime(RUN_JUMP_SEQUENCE, facing=facing, x=350)
                frames = [runtime.next_frame() for _ in range(11)]

                self.assertEqual(frames[-1].target_x, expected_x)
                self.assertEqual(runtime.state.current_y, 0)
                self.assertEqual(runtime.state.facing, facing)

    def test_vertical_sequence_opcode_updates_y(self):
        runtime = SequenceRuntime(
            {1: (-6, -4, 5)},
            SequenceState(sequence_id=1),
        )

        frame = runtime.next_frame()

        self.assertEqual(frame.action, 5)
        self.assertEqual(frame.current_y, -4)

    def test_opening_callback_records_sound_and_player_flag(self):
        runtime = self.runtime(1, facing=1)
        frames = [runtime.next_frame() for _ in range(11)]

        self.assertEqual([frame.action for frame in frames[-3:]], [9, 10, 11])
        self.assertEqual(runtime.state.target_x, 212)
        self.assertEqual(runtime.state.callback_counter, 1)
        self.assertEqual(runtime.state.callback_flag, 1)
        self.assertEqual(runtime.state.sound_events, [0x127])

    def test_level_kind_one_callback_does_not_schedule_sound(self):
        runtime = SequenceRuntime(
            {1: (-15, 1, 3)},
            SequenceState(sequence_id=1, actor_type=0, level_kind=1),
        )

        frame = runtime.next_frame()

        self.assertEqual(frame.action, 3)
        self.assertEqual(runtime.state.callback_counter, 1)
        self.assertEqual(runtime.state.callback_flag, 1)
        self.assertEqual(runtime.state.sound_events, [])

    def test_unimplemented_original_callback_stops_instead_of_being_ignored(self):
        runtime = SequenceRuntime(
            {1: (-15, 1, 3)},
            SequenceState(sequence_id=1),
        )

        with self.assertRaises(UnsupportedSequenceOpcode) as error:
            runtime.next_frame()

        self.assertEqual(error.exception.opcode, -15)

    def test_unknown_original_opcode_stops_instead_of_being_ignored(self):
        runtime = SequenceRuntime({1: (-999,)}, SequenceState(sequence_id=1))

        with self.assertRaises(UnsupportedSequenceOpcode):
            runtime.next_frame()

    def test_sword_sequences_match_original_capture_pose_order(self):
        expectations = (
            (SWORD_DRAW_SEQUENCE, [207, 208, 209, 210, 158]),
            (SWORD_ADVANCE_SEQUENCE, [163, 164, 165, 158]),
            (SWORD_RETREAT_SEQUENCE, [160, 157, 158]),
            (SWORD_ATTACK_SEQUENCE, [151, 152, 153, 154, 155, 156, 157, 158]),
            (SWORD_BLOCK_SEQUENCE, [169, 150, 158]),
            (SWORD_BLOCK_ATTACK_SEQUENCE, [162, 152, 153, 154, 155, 156, 157, 158]),
            (SWORD_SHEATHE_SEQUENCE, [
                *range(233, 241), 133, 133, 134, 134, 134,
                48, 49, 50, 51, 52, 15,
            ]),
        )
        for sequence_id, actions in expectations:
            with self.subTest(sequence_id=sequence_id):
                runtime = self.runtime(sequence_id)
                self.assertEqual(
                    [runtime.next_frame().action for _ in actions], actions
                )

    def test_attack_holds_each_pose_for_six_ticks_before_returning_to_guard(self):
        scene = self.sword_scene()
        scene.sword_drawn = True
        scene.start_sequence(SWORD_GUARD_SEQUENCE)
        with patch("pop2.scene_prototype.time.perf_counter") as clock:
            clock.return_value = 10.0
            scene.set_key_state("ctrl", True)
            self.assertEqual(scene.action, 151)
            self.assertEqual(scene.root.scheduled[-1][0], 100)
            for action in (152, 153, 154, 155, 156, 157, 158):
                clock.return_value = scene.next_animation_at
                scene.advance_animation()
                self.assertEqual(scene.action, action)
                self.assertEqual(scene.root.scheduled[-1][0], 100)
            self.assertAlmostEqual(clock.return_value - 10.0, 0.7)

    def test_drawing_and_sheathing_change_cadence_after_the_first_pose(self):
        scene = self.sword_scene()
        with patch("pop2.scene_prototype.time.perf_counter") as clock:
            clock.return_value = 10.0
            scene.set_key_state("ctrl", True)
            scene.set_key_state("ctrl", False)
            self.assertEqual(scene.action, 207)
            self.assertEqual(scene.root.scheduled[-1][0], 83)
            for action in (208, 209, 210, 158):
                clock.return_value = scene.next_animation_at
                scene.advance_animation()
                self.assertEqual(scene.action, action)
                self.assertEqual(scene.root.scheduled[-1][0], 100)

            clock.return_value = 12.0
            scene.up_key(None)
            scene.set_key_state("up", False)
            self.assertEqual(scene.action, 169)
            self.assertEqual(scene.root.scheduled[-1][0], 100)
            clock.return_value = scene.next_animation_at
            scene.advance_animation()
            self.assertEqual(scene.action, 150)
            self.assertEqual(scene.root.scheduled[-1][0], 100)
            clock.return_value = scene.next_animation_at
            scene.advance_animation()

            clock.return_value = 13.0
            scene.set_key_state("down", True)
            self.assertEqual(scene.action, 233)
            self.assertEqual(scene.root.scheduled[-1][0], 100)
            clock.return_value = scene.next_animation_at
            scene.advance_animation()
            self.assertEqual(scene.action, 234)
            self.assertEqual(scene.root.scheduled[-1][0], 83)

    def test_draw_attack_block_and_sheathe_inputs_use_sword_poses(self):
        scene = self.sword_scene()

        scene.set_key_state("ctrl", True)
        self.assertEqual(scene.action, 207)
        self.assertTrue(scene.sword_drawn)
        scene.set_key_state("ctrl", True)
        self.assertEqual(scene.action, 207)
        scene.set_key_state("ctrl", False)
        for _ in range(4):
            scene.advance_animation()
        self.assertEqual(scene.action, 158)
        self.assertEqual(scene.sequence_state.sequence_id, SWORD_GUARD_SEQUENCE)

        scene.set_key_state("ctrl", True)
        self.assertEqual(scene.action, 151)
        scene.set_key_state("ctrl", False)
        for _ in range(7):
            scene.advance_animation()
        self.assertEqual(scene.action, 158)

        scene.up_key(None)
        self.assertEqual(scene.action, 169)
        scene.set_key_state("up", False)
        scene.advance_animation()
        self.assertEqual(scene.action, 150)
        scene.advance_animation()
        self.assertEqual(scene.action, 158)
        self.assertFalse(scene.jump_started_for_press)

        scene.set_key_state("down", True)
        self.assertEqual(scene.action, 233)
        for _ in range(24):
            scene.advance_animation()
            if scene.action == 15:
                break
        self.assertEqual(scene.action, 15)
        self.assertFalse(scene.sword_drawn)
        scene.advance_animation()
        self.assertEqual(scene.action, 15)
        scene.set_key_state("down", False)

    def test_block_then_queued_attack_uses_original_transition_and_offsets(self):
        for facing in (0, 1):
            for attack_pose in (169, 150):
                for held in (False, True):
                    with self.subTest(facing=facing, attack_pose=attack_pose, held=held):
                        scene = self.sword_scene()
                        scene.sequence_state.facing = facing
                        scene.sword_drawn = True
                        scene.start_sequence(SWORD_GUARD_SEQUENCE)
                        scene.advance_animation()
                        start_x = scene.player_x
                        sign = 1 if facing else -1
                        scene.up_key(None)
                        frames = [(scene.action, scene.player_x)]
                        if not held:
                            scene.set_key_state("up", False)
                        if attack_pose == 150:
                            scene.advance_animation()
                            frames.append((scene.action, scene.player_x))
                        scene.set_key_state("ctrl", True)
                        if not held:
                            scene.set_key_state("ctrl", False)
                        self.assertEqual(scene.action, attack_pose)
                        self.assertEqual(scene.pending_action, BufferedCommand("sword_attack"))
                        while len(frames) < 10:
                            scene.advance_animation()
                            frames.append((scene.action, scene.player_x))
                        self.assertEqual(
                            [action for action, _ in frames],
                            [169, 150, 162, 152, 153, 154, 155, 156, 157, 158],
                        )
                        self.assertEqual(
                            [x for _, x in frames],
                            [start_x + sign * dx for dx in (1, 2, -4, 0, 0, 0, 0, 0, 0, 0)],
                        )
                        self.assertIsNone(scene.pending_action)
                        for expected in (170, 171, 171):
                            scene.advance_animation()
                            self.assertEqual(scene.action, expected)

    def test_block_attack_waits_for_tick_and_preserves_combat_cadence(self):
        scene = self.sword_scene()
        scene.sword_drawn = True
        scene.start_sequence(SWORD_GUARD_SEQUENCE)
        scene.advance_animation()
        with patch("pop2.scene_prototype.time.perf_counter") as clock:
            clock.return_value = 10.0
            scene.up_key(None)
            self.assertEqual(scene.action, 169)
            clock.return_value = 10.05
            deadline = scene.next_animation_at
            scene.set_key_state("ctrl", True)
            self.assertEqual(scene.action, 169)
            self.assertEqual(scene.next_animation_at, deadline)
            for action in (150, 162, 152, 153, 154, 155, 156, 157, 158):
                clock.return_value = scene.next_animation_at
                scene.advance_animation()
                self.assertEqual(scene.action, action)
                self.assertEqual(scene.root.scheduled[-1][0], 100)
            self.assertAlmostEqual(clock.return_value - 10.0, 0.9)

    def test_attack_after_block_has_finished_is_a_normal_attack(self):
        scene = self.sword_scene()
        scene.sword_drawn = True
        scene.start_sequence(SWORD_GUARD_SEQUENCE)
        scene.advance_animation()
        start_x = scene.player_x
        scene.up_key(None)
        scene.set_key_state("up", False)
        scene.advance_animation()
        scene.advance_animation()
        self.assertEqual(scene.action, 158)
        self.assertEqual(scene.player_x, start_x)
        scene.set_key_state("ctrl", True)
        self.assertEqual(scene.action, 151)
        self.assertEqual(scene.sequence_state.sequence_id, SWORD_ATTACK_SEQUENCE)

    def test_sheathe_queued_during_block_does_not_start_a_counterattack(self):
        scene = self.sword_scene()
        scene.sword_drawn = True
        scene.start_sequence(SWORD_GUARD_SEQUENCE)
        scene.advance_animation()
        start_x = scene.player_x
        scene.up_key(None)
        scene.set_key_state("up", False)
        scene.set_key_state("down", True)
        scene.advance_animation()
        self.assertEqual(scene.action, 150)
        scene.advance_animation()
        self.assertEqual(scene.action, 233)
        self.assertEqual(scene.sequence_state.sequence_id, SWORD_SHEATHE_SEQUENCE)
        self.assertEqual(scene.player_x, start_x + 10)
        self.assertIsNone(scene.pending_action)

    def test_attack_pressed_during_draw_waits_for_draw_to_finish(self):
        scene = self.sword_scene()
        scene.set_key_state("ctrl", True)
        scene.set_key_state("ctrl", False)
        scene.set_key_state("ctrl", True)
        scene.set_key_state("ctrl", False)

        self.assertEqual(scene.pending_action, BufferedCommand("sword_attack"))
        for action in (208, 209, 210, 151):
            scene.advance_animation()
            self.assertEqual(scene.action, action)
        self.assertIsNone(scene.pending_action)

    def test_sword_step_tap_preserves_facing_and_source_offsets(self):
        for facing in (0, 1):
            sign = 1 if facing else -1
            for direction in (-1, 1):
                with self.subTest(facing=facing, direction=direction):
                    scene = self.guarded_sword_scene(facing)
                    start_x = scene.player_x
                    forward = direction == sign
                    actions = [163, 164, 165, 158] if forward else [160, 157, 158]
                    offsets = [-1, 2, 16, 18] if forward else [0, -16, -16]
                    scene.horizontal_key(None, direction, True)
                    scene.horizontal_key(None, direction, False)
                    frames = [(scene.action, scene.player_x)]
                    for _ in actions[1:]:
                        scene.advance_animation()
                        frames.append((scene.action, scene.player_x))
                    self.assertEqual([action for action, _ in frames], actions)
                    self.assertEqual([x for _, x in frames], [start_x + sign * dx for dx in offsets])
                    self.assertEqual(scene.sequence_state.facing, facing)
                    self.assertTrue(scene.sword_drawn)
                    self.assertIsNone(scene.pending_action)
                    for expected in (170, 171, 171):
                        scene.advance_animation()
                        self.assertEqual(scene.action, expected)

    def test_held_sword_steps_repeat_at_original_guard_boundary_and_cadence(self):
        for facing in (0, 1):
            sign = 1 if facing else -1
            for direction in (-1, 1):
                with self.subTest(facing=facing, direction=direction):
                    scene = self.guarded_sword_scene(facing)
                    start_x = scene.player_x
                    forward = direction == sign
                    cycle = [163, 164, 165, 158] if forward else [160, 157, 158]
                    with patch("pop2.scene_prototype.time.perf_counter") as clock:
                        clock.return_value = 10.0
                        scene.horizontal_key(None, direction, True)
                        actions = [scene.action]
                        for _ in range(len(cycle) * 3 - 1):
                            clock.return_value = scene.next_animation_at
                            scene.advance_animation()
                            actions.append(scene.action)
                            self.assertEqual(scene.root.scheduled[-1][0], 100)
                        self.assertEqual(actions, cycle * 3)
                        self.assertAlmostEqual(clock.return_value - 10.0, (len(actions) - 1) * 0.1)
                    self.assertEqual(scene.player_x, start_x + sign * (54 if forward else -48))
                    self.assertEqual(scene.sequence_state.facing, facing)
                    scene.horizontal_key(None, direction, False)
                    scene.advance_animation()
                    self.assertEqual(scene.action, 170)

    def test_queued_sword_reversal_finishes_step_then_retreats_without_turning(self):
        scene = self.guarded_sword_scene(facing=1)
        start_x = scene.player_x
        scene.horizontal_key(None, 1, True)
        scene.horizontal_key(None, 1, False)
        scene.horizontal_key(None, -1, True)
        scene.horizontal_key(None, -1, False)
        self.assertEqual(scene.action, 163)
        self.assertEqual(scene.pending_action, BufferedCommand("sword_retreat"))
        for action in (164, 165, 158, 160, 157, 158):
            scene.advance_animation()
            self.assertEqual(scene.action, action)
        self.assertEqual(scene.player_x, start_x + 2)
        self.assertEqual(scene.sequence_state.facing, 1)
        self.assertIsNone(scene.pending_action)

    def test_sword_step_queued_during_draw_waits_for_first_guard_pose(self):
        scene = self.sword_scene()
        scene.sequence_state.facing = 1
        scene.set_key_state("ctrl", True)
        scene.set_key_state("ctrl", False)
        scene.horizontal_key(None, 1, True)
        scene.horizontal_key(None, 1, False)
        self.assertEqual(scene.action, 207)
        for action in (208, 209, 210, 158, 163, 164, 165, 158):
            scene.advance_animation()
            self.assertEqual(scene.action, action)
        self.assertIsNone(scene.pending_action)

    def test_attack_and_block_queue_branch_on_last_advance_pose(self):
        for kind, first_action in (("sword_attack", 151), ("sword_block", 169)):
            with self.subTest(kind=kind):
                scene = self.guarded_sword_scene(facing=1)
                start_x = scene.player_x
                scene.horizontal_key(None, 1, True)
                if kind == "sword_attack":
                    scene.set_key_state("ctrl", True)
                    scene.set_key_state("ctrl", False)
                else:
                    scene.up_key(None)
                    scene.set_key_state("up", False)
                # OS key repeat must not overwrite the buffered combat command.
                scene.horizontal_key(None, 1, True)
                self.assertEqual(scene.pending_action, BufferedCommand(kind))
                for action in (164, 165, first_action):
                    scene.advance_animation()
                    self.assertEqual(scene.action, action)
                self.assertEqual(scene.player_x, start_x + (16 if kind == "sword_attack" else 17))
                self.assertIsNone(scene.pending_action)

    def test_block_after_retreat_waits_for_guard_while_attack_can_chain(self):
        for kind, expected in (("sword_attack", [157, 151]), ("sword_block", [157, 158, 169])):
            with self.subTest(kind=kind):
                scene = self.guarded_sword_scene(facing=1)
                start_x = scene.player_x
                scene.horizontal_key(None, -1, True)
                scene.horizontal_key(None, -1, False)
                if kind == "sword_attack":
                    scene.set_key_state("ctrl", True)
                else:
                    scene.up_key(None)
                for action in expected:
                    scene.advance_animation()
                    self.assertEqual(scene.action, action)
                self.assertEqual(scene.player_x, start_x - (16 if kind == "sword_attack" else 15))
                self.assertIsNone(scene.pending_action)

    def test_latest_sword_step_command_replaces_only_buffered_command(self):
        scene = self.guarded_sword_scene(facing=1)
        scene.horizontal_key(None, 1, True)
        scene.horizontal_key(None, 1, False)
        scene.set_key_state("ctrl", True)
        scene.set_key_state("ctrl", False)
        scene.horizontal_key(None, -1, True)
        scene.horizontal_key(None, -1, False)
        self.assertEqual(scene.pending_action, BufferedCommand("sword_retreat"))
        for action in (164, 165, 158, 160, 157, 158, 170, 171):
            scene.advance_animation()
            self.assertEqual(scene.action, action)
        self.assertIsNone(scene.pending_action)

    def test_held_sword_direction_resumes_after_attack_and_focus_loss_stops_it(self):
        scene = self.guarded_sword_scene(facing=1)
        scene.set_key_state("ctrl", True)
        scene.set_key_state("ctrl", False)
        scene.horizontal_key(None, 1, True)
        for action in (152, 153, 154, 155, 156, 157, 158, 163):
            scene.advance_animation()
            self.assertEqual(scene.action, action)
        scene.clear_keys(None)
        for action in (164, 165, 158, 170, 171):
            scene.advance_animation()
            self.assertEqual(scene.action, action)
        self.assertEqual(scene.horizontal_input, 0)
        self.assertIsNone(scene.pending_action)

    def test_sword_attachment_uses_original_frame_resource(self):
        scene = self.sword_scene()
        scene.frames = parse_frame_records(self.kid["FRAM"][25001]["data"])
        scene.attachment_frames = parse_aframe_records(
            self.kid["AFRM"][25001]["data"]
        )
        scene.sword_shapes = self.prince["SHAP"]
        scene.first_sword_shape_id = 1001
        scene.sword_palette = sword_palette_for_level(self.prince, 5)
        scene.sword_sprite_cache = {}
        scene.action = 158

        sword, dx, dy = scene.sword_sprite()

        self.assertEqual((dx, dy), (22, -38))
        self.assertEqual(sword.size, (26, 14))
        self.assertEqual(set(scene.sword_palette), set(range(240, 251)))
        self.assertEqual(scene.sword_palette[240], (245, 255, 226, 255))
        colors = {color for _count, color in sword.getcolors(sword.width * sword.height)}
        self.assertNotIn((255, 0, 255, 255), colors)


if __name__ == "__main__":
    unittest.main()
