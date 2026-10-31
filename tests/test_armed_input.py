"""Original armed request priority and the interim host-buffer bridge."""

from itertools import permutations, product
import unittest


class ArmedSelectorTests(unittest.TestCase):
    def test_request_gate_matches_independent_native_checked_model(self):
        from pop2.mac_input import DirectionalInput
        from pop2.sword_controls import armed_input_request
        from tools.reference_armed_input import on_alert
        from tools.reference_input_bank import InputBank
        for axes, modifier, pose, actor in product(
                product((-1, 0, 1), repeat=4), (-2, -1, 0, 1, 2),
                (15, 150, 151, 157, 158, 161, 165, 167, 168, 169, 170, 171), (0, 1, 7, 8)):
            self.assertEqual(armed_input_request(DirectionalInput(*axes, modifier), pose, actor_type=actor),
                             on_alert(InputBank(*axes, modifier), pose, actor))

    def test_blocked_down_does_not_fall_through_to_lower_priority_input(self):
        from pop2.mac_input import DirectionalInput
        from pop2.sword_controls import armed_input_request
        bank = DirectionalInput(left=-1, up=-1, down=-1)
        self.assertIsNone(armed_input_request(bank, 165))
        self.assertEqual(armed_input_request(bank, 158), 'sheathe')


class ArmedConsumptionTests(unittest.TestCase):
    def test_accepted_requests_consume_like_the_native_checked_bodies(self):
        # tools/probe_armed_consumption.py runs the original bodies; the
        # reference model matches them in 71,280 cases.
        from pop2.mac_input import DirectionalInput
        from pop2.sword_controls import armed_input_request, consume_armed_request
        from tools.reference_armed_input import armed_action
        from tools.reference_input_bank import InputBank
        checked = 0
        for axes, modifier, pose in product(product((-1, 0, 1), repeat=4), (-2, -1, 0, 1, 2),
                                            (150, 151, 157, 158, 161, 165, 167, 168, 169, 170, 171)):
            bank = InputBank(*axes, modifier)
            expected, events = armed_action(bank, pose)
            request = armed_input_request(DirectionalInput(*axes, modifier), pose)
            if not events or request == 'recoil':
                # Refused requests keep every word pending.
                self.assertEqual(expected, bank)
                continue
            self.assertEqual(consume_armed_request(DirectionalInput(*axes, modifier), request).words(),
                             expected.words())
            checked += 1
        self.assertGreater(checked, 1000)

    def test_block_leaves_the_lower_requests_pending(self):
        from pop2.mac_input import DirectionalInput
        from pop2.sword_controls import consume_armed_request
        # DoBlock 6:28d4 writes Up only; the others call ClearControls.
        bank = DirectionalInput(left=-1, right=-1, up=-1)
        self.assertEqual(consume_armed_request(bank, 'block'), DirectionalInput(-1, -1, 1, 0, 0))
        self.assertEqual(consume_armed_request(bank, 'advance'), DirectionalInput(left=1))


class AdvanceSequenceTests(unittest.TestCase):
    def test_level_five_room_nineteen_opponent_selects_the_alternative_advance(self):
        # DoAdvance 6:1e28-1e46: level 5 and the opponent (a5-0x5094 copy)
        # in native room 19 (+0x16) at column 5 (+0xc): SEQS 86, not 56.
        from pop2.sword_controls import advance_sequence
        self.assertEqual(advance_sequence(5, 18, 5), 86)
        for level, room, column in ((5, 18, 4), (5, 17, 5), (4, 18, 5)):
            self.assertIsNone(advance_sequence(level, room, column))


class ArmedBufferSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_animation_data import AnimationDataTests
        AnimationDataTests.setUpClass()
        cls.fixture = AnimationDataTests()

    def during_draw(self, facing=0):
        scene = self.fixture.sword_scene()
        scene.in_animation_tick = True
        scene.sequence_state.facing = facing
        scene.start_sword_action('sword_draw')
        scene.advance_animation()
        scene.queue_grace_remaining_ms = 0
        return scene

    def test_conflicting_armed_requests_have_priority_in_either_arrival_order(self):
        from pop2.scene_prototype import BufferedCommand
        kinds = ('sword_attack', 'sword_sheathe', 'sword_block', 'sword_advance', 'sword_retreat')
        for facing, pair in product((0, 1), permutations(kinds, 2)):
            with self.subTest(facing=facing, pair=pair):
                scene = self.during_draw(facing)
                for kind in pair:
                    # A strike request is the Ctrl word: pending while held.
                    scene.ctrl_held = scene.ctrl_held or kind == 'sword_attack'
                    scene.latch_request(BufferedCommand(kind))
                self.assertEqual(scene.armed_pending().kind, min(pair, key=kinds.index))

    def test_real_key_callbacks_cannot_replace_a_queued_strike_with_other_commands(self):
        # No opponent here: a pending Down would sheathe at once (6:2382,
        # UnengagedSheatheTests covers both cases), so it is not tested here.
        for facing, key in product((0, 1), ('up', 'forward', 'backward')):
            with self.subTest(facing=facing, key=key):
                scene = self.during_draw(facing)
                # Ctrl held until the strike starts (a release cancels it).
                scene.set_key_state('ctrl', True)
                if key == 'up':
                    scene.set_key_state(key, True)
                    scene.set_key_state(key, False)
                else:
                    direction = (1 if facing else -1) * (1 if key == 'forward' else -1)
                    scene.horizontal_key(None, direction, True)
                    scene.horizontal_key(None, direction, False)
                self.assertEqual(scene.armed_pending().kind, 'sword_attack')
                poses = []
                for _ in range(25):
                    scene.advance_animation()
                    poses.append(scene.action)
                    if scene.action == 151:
                        scene.set_key_state('ctrl', False)
                self.assertIn(151, poses)
                self.assertTrue(scene.sword_drawn)
                self.assertFalse(scene.sword_sheathing)

    def test_a_tapped_step_during_an_attack_waits_for_the_guard(self):
        # A released press stays pending (-1) until DoAdvance/DoRetreat
        # admits it at guard pose 158/170/171 (6:1dfc/1d90).
        for facing, forward in product((0, 1), (True, False)):
            with self.subTest(facing=facing, forward=forward):
                scene = self.during_draw(facing)
                for _ in range(6):
                    scene.advance_animation()
                scene.set_key_state('ctrl', True)
                scene.set_key_state('ctrl', False)
                self.assertEqual(scene.action, 151)
                direction = (1 if facing else -1) * (1 if forward else -1)
                scene.horizontal_key(None, direction, True)
                scene.horizontal_key(None, direction, False)
                poses = []
                for _ in range(12):
                    scene.advance_animation()
                    poses.append(scene.action)
                first = 163 if forward else 160
                self.assertIn(first, poses)
                self.assertEqual(poses[poses.index(first) - 1], 158)
                self.assertLess(poses.index(158), poses.index(first))
                self.assertEqual(poses.count(first), 1)

    def test_a_queued_step_is_classified_with_the_facing_at_dispatch(self):
        # The bank stays in keyboard coordinates (4:3d96-3e38): a press made
        # before a turn means Forward or Backward for the facing at the gate.
        scene = self.during_draw(0)
        for _ in range(6):
            scene.advance_animation()
        scene.set_key_state('ctrl', True)
        scene.set_key_state('ctrl', False)
        self.assertEqual(scene.action, 151)
        scene.horizontal_key(None, 1, True)
        scene.horizontal_key(None, 1, False)
        self.assertEqual(scene.armed_pending().kind, 'sword_retreat')
        scene.sequence_state.facing = 1
        self.assertEqual(scene.armed_pending().kind, 'sword_advance')

    def test_releasing_up_held_through_a_hurt_leaves_no_jump_after_sheathing(self):
        # Up pressed while the controls were locked (a hurt) and released
        # with the sword drawn used to queue a jump in the host slot, which
        # then fired once the sword was sheathed.
        scene = self.during_draw(1)
        for _ in range(6):
            scene.advance_animation()
        scene.up_held = True
        scene.jump_started_for_press = False
        scene.set_key_state('up', False)
        scene.set_key_state('down', True)
        scene.set_key_state('down', False)
        sequences = set()
        for _ in range(40):
            scene.advance_animation()
            sequences.add(scene.sequence_state.source_sequence_id)
        self.assertFalse(scene.sword_drawn)
        self.assertFalse(sequences & {3, 4, 17, 18})

    def test_released_ctrl_during_a_strike_does_not_erase_a_queued_block(self):
        scene = self.fixture.guarded_sword_scene()
        scene.in_animation_tick = True
        scene.set_key_state('ctrl', True)
        scene.set_key_state('ctrl', False)
        scene.advance_animation()
        self.assertEqual(scene.action, 151)
        scene.queue_sword_action('sword_block')
        scene.set_key_state('ctrl', True)
        self.assertEqual(scene.armed_pending().kind, 'sword_attack')
        scene.set_key_state('ctrl', False)
        self.assertEqual(scene.armed_pending().kind, 'sword_block')

    def test_a_released_ctrl_tap_before_the_gate_is_cancelled(self):
        # 4:3f38: no modifier held writes 0, even over a pending -2. The
        # port used to keep the strike (host extension, removed 2026-10-31).
        scene = self.during_draw()
        scene.set_key_state('ctrl', True)
        scene.set_key_state('ctrl', False)
        self.assertIsNone(scene.armed_pending())
        poses = []
        for _ in range(12):
            scene.advance_animation()
            poses.append(scene.action)
        self.assertNotIn(151, poses)

    def test_lower_priority_request_does_not_clear_attack_at_first_guard_boundary(self):
        from pop2.scene_prototype import SWORD_GUARD_SEQUENCE
        scene = self.during_draw()
        scene.set_key_state('ctrl', True)
        # JumpSeq has selected guard, but AnimChar has not loaded its pose.
        scene.start_sequence(SWORD_GUARD_SEQUENCE)
        scene.queue_sword_action('sword_sheathe')
        self.assertEqual(scene.armed_pending().kind, 'sword_attack')
        self.assertFalse(scene.sword_sheathing)
        for _ in range(4):
            scene.advance_animation()
            if scene.action == 151:
                break
        self.assertEqual(scene.action, 151)

    def test_down_up_taps_during_draw_select_sheathe_in_either_order(self):
        for order in (('down', 'up'), ('up', 'down')):
            with self.subTest(order=order):
                scene = self.during_draw()
                for key in order:
                    scene.set_key_state(key, True)
                    scene.set_key_state(key, False)
                self.assertEqual(scene.armed_pending().kind, 'sword_sheathe')
                for _ in range(30):
                    scene.advance_animation()
                self.assertFalse(scene.sword_drawn)
                self.assertFalse(scene.sword_sheathing)
                self.assertEqual(scene.action, 15)


class SheatheBankTests(unittest.TestCase):
    """PutSwordAway hands the bank to GenCtrl's standing gates (SEQS 92/93)."""

    @classmethod
    def setUpClass(cls):
        from tests.test_animation_data import AnimationDataTests
        AnimationDataTests.setUpClass()
        cls.fixture = AnimationDataTests()

    def sheathe(self, events, sequence_id, facing=1, ticks=30, down_held=False):
        scene = self.fixture.guarded_sword_scene(facing)
        # down_held: the Down that requested the sheathe is still held.
        scene.down_held = down_held
        scene.start_sword_action('sword_sheathe', sequence_id=sequence_id)
        # ClearControls, then Down=1 (a released Down samples back to 0).
        self.assertEqual(scene.directional_input.words()[:4], (0, 0, 0, int(down_held)))
        trace = []
        for tick in range(ticks):
            for when, key, pressed in events:
                if when == tick:
                    if key in ('left', 'right'):
                        scene.horizontal_key(None, -1 if key == 'left' else 1, pressed)
                    else:
                        scene.set_key_state(key, pressed)
            scene.advance_animation()
            trace.append((scene.sequence_state.source_sequence_id, scene.action))
        return scene, trace

    def test_long_sheath_pose_fifty_discards_taps_made_during_the_sheathe(self):
        # SEQS 92 sets mode 5 for pose 50 (-7 5, 50, -7 1): GenCtrl clears
        # every direction there. The old host slot kept the tap and turned
        # or crouched at 50.
        for facing, key in product((0, 1), ('down', 'backward')):
            with self.subTest(facing=facing, key=key):
                if key == 'backward':
                    key = 'left' if facing else 'right'
                scene, trace = self.sheathe(((5, key, True), (6, key, False)), 92, facing)
                self.assertEqual({sequence for sequence, _ in trace}, {92})
                self.assertEqual(trace[-1], (92, 15))
                self.assertFalse(scene.sword_sheathing)

    def test_long_sheath_held_keys_act_after_the_mode_five_clear(self):
        for facing, key in product((0, 1), ('down', 'backward', 'up')):
            with self.subTest(facing=facing, key=key):
                name = ('left' if facing else 'right') if key == 'backward' else key
                _, trace = self.sheathe(((10, name, True),), 92, facing)
                poses = [action for _, action in trace]
                start = next(index for index, (seq, _) in enumerate(trace) if seq != 92)
                # Pose 51 is the first standing gate after 50 cleared the bank.
                self.assertEqual(poses[start - 1], 51)
                self.assertEqual(trace[start][0], {'down': 50, 'backward': 5, 'up': 28}[key])

    def test_forward_tap_during_long_sheath_runs_from_pose_48(self):
        # GenCtrl 6:062c/1014: a pending Forward at pose 48 turns into SEQS 43.
        for facing in (0, 1):
            with self.subTest(facing=facing):
                key = 'right' if facing else 'left'
                _, trace = self.sheathe(((3, key, True), (4, key, False)), 92, facing)
                start = next(index for index, (seq, _) in enumerate(trace) if seq != 92)
                self.assertEqual((trace[start - 1], trace[start][0]), ((92, 48), 43))

    def test_short_sheath_keeps_down_consumed_and_taps_pending(self):
        # SEQS 93 has no mode-5 pose: the held Down stays consumed (1), a tap
        # made during it acts at the final standing gate.
        _, held = self.sheathe((), 93, down_held=True)
        self.assertEqual({sequence for sequence, _ in held}, {93})
        _, long_held = self.sheathe((), 92, down_held=True)
        self.assertIn(50, {sequence for sequence, _ in long_held})
        _, tapped = self.sheathe(((1, 'down', True), (2, 'down', False)), 93)
        self.assertIn(50, {sequence for sequence, _ in tapped})


class UnengagedSheatheTests(unittest.TestCase):
    """SwordCtrl 6:2236-2274 and 6:2368-2386: with no engaged opponent within
    reach a pending Down calls PutSwordAway at once, at any mode-0/1 pose and
    ahead of a pending attack. Against an engaged opponent OnAlert keeps its
    priority and its guard-pose gate."""

    @classmethod
    def setUpClass(cls):
        from tests.test_combat import GuardCombatTests
        GuardCombatTests.setUpClass()
        cls.fixture = GuardCombatTests()

    def scene(self, alert, guard_x=150, player_x=260):
        from pop2.combat import select_sequence
        from pop2.scene_prototype import SWORD_GUARD_SEQUENCE

        scene = self.fixture.scene()
        guard = scene.combat.guard
        guard.alert_mode = alert
        guard.sword_drawn = True
        select_sequence(guard, 227)
        guard.runtime.next_frame()
        guard.state.target_x = guard.state.current_x = guard_x
        scene.sword_drawn = True
        scene.sequence_state.facing = 0
        scene.player_x = scene.sequence_state.target_x = player_x
        scene.start_sequence(SWORD_GUARD_SEQUENCE)
        scene.advance_animation()
        return scene

    def trace(self, scene, ticks=12):
        """Poses, with 'sheathe' for the first frame of PutSwordAway's SEQS
        92/93 (93 here: OppToFight still finds the living guard)."""
        from unittest.mock import patch

        poses = []
        with patch.object(scene.combat, 'step', return_value=[]):
            for _ in range(ticks):
                scene.advance_animation()
                sheathing = scene.sequence_state.sequence_id in (92, 93)
                poses.append('sheathe' if sheathing and 'sheathe' not in poses
                             else scene.action)
        return poses

    def tap(self, scene, key):
        scene.set_key_state(key, True)
        scene.set_key_state(key, False)

    def test_down_during_a_strike_sheathes_at_once_without_an_engaged_opponent(self):
        from pop2.combat import opponent_distance

        for alert in (0, 1, 2, 3):
            with self.subTest(alert=alert):
                scene = self.scene(alert)
                self.assertLess(opponent_distance(scene.combat.player, scene.combat.guard), 331)
                self.tap(scene, 'ctrl')
                self.assertEqual(scene.action, 151)
                self.tap(scene, 'down')
                poses = self.trace(scene)
                if alert >= 2:
                    # OnAlert admits Down only at the guard poses: the strike
                    # finishes and guard pose 158 sheathes before it is shown.
                    self.assertEqual(poses[:7], [152, 153, 154, 155, 156, 157, 'sheathe'])
                else:
                    self.assertEqual(poses[0], 'sheathe')
                self.assertFalse(scene.sword_drawn)

    def test_down_beats_a_pending_attack_only_without_an_engaged_opponent(self):
        from pop2.scene_prototype import SWORD_STEP_SEQUENCES

        for alert, order in product((0, 3), (('ctrl', 'down'), ('down', 'ctrl'))):
            with self.subTest(alert=alert, order=order):
                scene = self.scene(alert)
                # A retreat step (mode 1) is not a guard pose.
                scene.start_sequence(min(SWORD_STEP_SEQUENCES))
                scene.sequence_runtime.next_frame()
                for key in order:
                    # Ctrl stays held: a released one is no strike (4:3f38).
                    scene.set_key_state(key, True)
                    if key != 'ctrl':
                        scene.set_key_state(key, False)
                poses = self.trace(scene)
                if alert:
                    self.assertIn(151, poses)
                    self.assertTrue(scene.sword_drawn)
                else:
                    self.assertEqual(poses[0], 'sheathe')
                    self.assertNotIn(151, poses)

    def test_down_held_after_a_block_sheathes_after_it_only_when_engaged(self):
        for alert in (0, 3):
            with self.subTest(alert=alert):
                scene = self.scene(alert)
                scene.up_key(None)
                scene.set_key_state('up', False)
                self.assertEqual(scene.action, 169)
                scene.set_key_state('down', True)
                poses = self.trace(scene, 4)
                self.assertNotIn(151, poses)
                self.assertEqual(poses[0], 150 if alert else 'sheathe')
                self.assertIn('sheathe', poses)

    def test_an_engaged_opponent_beyond_reach_ahead_leaves_down_unrouted(self):
        from pop2.combat import opponent_distance

        scene = self.scene(3, guard_x=40, player_x=400)
        self.assertGreaterEqual(opponent_distance(scene.combat.player, scene.combat.guard), 331)
        self.tap(scene, 'ctrl')
        self.tap(scene, 'down')
        self.assertEqual(self.trace(scene)[0], 'sheathe')

    def test_a_loose_floor_routes_by_distance_even_at_alert_zero(self):
        from pop2.terrain import Tile

        for kind in (0, 11, 15):
            with self.subTest(kind=kind):
                scene = self.scene(0)
                scene.combat.terrain = type('Cells', (), {'tile': lambda *_: Tile(kind)})()
                self.assertEqual(scene.combat.player_distance_routed(), kind != 0)
                self.tap(scene, 'ctrl')
                self.tap(scene, 'down')
                poses = self.trace(scene)
                self.assertEqual(poses[0], 'sheathe' if kind == 0 else 152)
