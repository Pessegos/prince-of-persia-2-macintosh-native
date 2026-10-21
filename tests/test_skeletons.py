import random
import unittest
from unittest.mock import patch

from PIL import Image

from pop2.combat import GuardSpawn, select_sequence, strike_range
from pop2.combat_art import GuardArtwork, HealthArtwork
from pop2.game_session import GameResources, GameSession
from pop2.paths import ASSET_DIR
from pop2.render_opening import decode_ctbl, load_resource_file
from pop2.scene_prototype import sword_palette_for_level
from pop2.sequence_runtime import SequenceRuntime, SequenceState
from pop2.terrain import Tile


@unittest.skipUnless((ASSET_DIR / 'Skeleton.rsrc').is_file(), 'Imported skeleton artwork required')
class SkeletonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resources = GameResources.load()
        prince = cls.resources.prince
        cls.art = GuardArtwork(load_resource_file('Skeleton.rsrc'), prince['SHAP'], 1001,
                               sword_palette_for_level(prince, 3))
        kid = cls.resources.kid
        cls.health_art = HealthArtwork(kid, decode_ctbl(kid['CTBL'][25001]['data']),
                                      cls.resources.first_shape_id)

    def encounter(self, room=10):
        game = GameSession.load(self.resources, 3)
        game.place(room, 2, 230, 1)
        combat = game.combat
        combat.rng = random.Random(17)
        combat.guard_art = self.art
        combat.player.sword_drawn = True
        return game, combat, combat.guards[0]

    def tick(self, combat, count=1):
        for _ in range(count):
            combat.update_guard_alerts()
            combat.advance_guard()
            combat.world_frame += 1

    def boundary_encounter(self, side='left', armed=False):
        game, combat, actor = self.encounter(14)
        actor.state.target_x = actor.state.current_x = (473 if side == 'left' else 17)
        combat.enter_room(16 if side == 'left' else 13, 2)
        combat.player.state.target_x = combat.player.state.current_x = (
            40 if side == 'left' else 470)
        combat.player.state.facing = int(side == 'right')
        combat.player.state.action = 171 if armed else 15
        combat.player.sword_drawn = armed
        actor.skeleton.phase = 'active'
        actor.life = actor.max_life
        actor.sword_drawn = actor.targetable = True
        actor.alert_mode = 3
        actor.state.facing = int(side == 'left')
        actor.state.target_x = actor.state.current_x = (473 if side == 'left' else 17)
        select_sequence(actor, 227)
        actor.runtime.next_frame()
        return game, combat, actor

    def test_unarmed_prince_is_hit_across_both_room_edges_without_god_mode(self):
        for side in ('left', 'right'):
            with self.subTest(side=side):
                _, combat, actor = self.boundary_encounter(side)
                self.assertFalse(getattr(combat, 'god_mode', False))
                self.assertNotIn(actor, combat.guards)
                actor.state.action = 154
                position = actor.room, actor.state.target_x, actor.state.current_x
                events = combat.resolve_contacts()
                self.assertEqual([(e.kind, e.actor) for e in events], [('hit', 'player')])
                self.assertEqual(combat.player.life, 2)
                self.assertTrue(combat.player.sword_drawn)
                self.assertTrue(combat.player.recovering)
                self.assertEqual(position, (actor.room, actor.state.target_x, actor.state.current_x))
                self.assertIs(combat.room_encounters[14][0][0], actor)
                self.assertEqual(combat.resolve_contacts(), [])
                self.assertEqual(combat.player.life, 2)

    def test_side_room_contact_preserves_god_mode_protection(self):
        _, combat, actor = self.boundary_encounter()
        combat.god_mode = True
        actor.state.action = 154
        self.assertEqual(combat.resolve_contacts()[0].kind, 'hit')
        self.assertEqual(combat.player.life, 3)
        self.assertTrue(combat.player.recovering)

    def test_prince_can_hit_and_collapse_the_real_side_room_skeleton(self):
        for side in ('left', 'right'):
            with self.subTest(side=side):
                _, combat, actor = self.boundary_encounter(side, armed=True)
                actor.life = 1
                combat.player.state.action = 154
                events = combat.resolve_contacts()
                self.assertEqual([(e.kind, e.actor) for e in events], [('death', 'guard')])
                self.assertEqual((actor.life, actor.room, actor.skeleton.phase),
                                 (0, 14, 'collapsing'))
                self.assertEqual(actor.skeleton.timer, 120)
                self.assertIs(combat.room_encounters[14][0][0], actor)

    def test_side_room_parries_update_real_actors_in_both_directions(self):
        for side in ('left', 'right'):
            for attacker_name in ('player', 'guard'):
                with self.subTest(side=side, attacker=attacker_name):
                    _, combat, actor = self.boundary_encounter(side, armed=True)
                    attacker, defender = ((combat.player, actor) if attacker_name == 'player'
                                          else (actor, combat.player))
                    attacker.state.action, defender.state.action = 154, 150
                    positions = [(f.room, f.state.target_x) for f in (attacker, defender)]
                    positions[0] = (attacker.room, attacker.state.target_x
                                    + (-6 if attacker.state.facing else 6))
                    events = combat.resolve_contacts()
                    self.assertEqual([(e.kind, e.actor) for e in events],
                                     [('parry', 'guard' if attacker_name == 'player' else 'player')])
                    self.assertEqual((attacker.state.sequence_id, defender.state.action), (69, 161))
                    self.assertEqual((actor.life, combat.player.life), (3, 3))
                    self.assertEqual(positions, [(f.room, f.state.target_x)
                                                 for f in (attacker, defender)])

    def test_simultaneous_boundary_hits_keep_prince_priority(self):
        _, combat, actor = self.boundary_encounter(armed=True)
        combat.player.state.action = actor.state.action = 154
        self.assertEqual([(e.kind, e.actor) for e in combat.resolve_contacts()], [('hit', 'guard')])
        self.assertEqual((combat.player.life, actor.life), (3, 2))

    def test_boundary_contact_still_requires_range_floor_and_targetable_actors(self):
        for condition in ('range', 'floor', 'hidden', 'dead', 'unlinked_room'):
            with self.subTest(condition=condition):
                _, combat, actor = self.boundary_encounter()
                actor.state.action = 154
                if condition == 'range':
                    combat.player.state.target_x = 200
                elif condition == 'floor':
                    combat.player.row = 1
                elif condition == 'hidden':
                    actor.targetable = False
                elif condition == 'dead':
                    actor.life = 0
                else:
                    combat.enter_room(0, 2)
                self.assertEqual(combat.resolve_contacts(), [])
                self.assertEqual(combat.player.life, 3)

    def test_late_waking_skeleton_can_hit_prince_waiting_in_room17_entry(self):
        _, combat, actor = self.encounter(14)
        combat.player.state.target_x = combat.player.state.current_x = 300
        self.tick(combat, 10)
        combat.enter_room(16, 2)
        combat.player.state.target_x = combat.player.state.current_x = 40
        combat.player.state.facing, combat.player.state.action = 0, 15
        combat.player.sword_drawn = False
        for _ in range(100):
            self.tick(combat)
            if combat.resolve_contacts():
                break
        self.assertEqual((actor.room, combat.player.room), (14, 16))
        self.assertEqual(combat.player.life, 2)
        self.assertTrue(combat.player.sword_drawn)

    def test_live_boundary_hit_reaches_scene_health_and_sword_state(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(3)
        scene.jump_to_room(14, row=2, x=300, facing=1)
        scene.combat.rng = random.Random(17)
        actor = scene.combat.guards[0]
        with patch.object(scene, 'render'):
            RooftopSceneTests.tick(self, 10)
            scene.jump_to_room(16, row=2, x=40, facing=0, reset_guards=False)
            self.assertFalse(scene.god_mode)
            self.assertFalse(scene.peaceful)
            for _ in range(100):
                RooftopSceneTests.tick(self)
                if scene.combat.player.life < 3:
                    break
        self.assertEqual((actor.room, scene.room_id), (14, 16))
        self.assertEqual(scene.combat.player.life, 2)
        self.assertTrue(scene.sword_drawn)
        self.assertTrue(scene.combat.player.recovering)

    def test_native_generators_preserve_individual_skills_and_life_fields(self):
        level = self.resources.level(3).data
        actual = [spawn for room in range(24) for spawn in GuardSpawn.all_from_level(level, room)]
        self.assertEqual([(s.room + 1, s.actor_type, s.skill, s.life) for s in actual],
                         [(4, 4, 0, 105), (6, 4, 0, 3), (11, 4, 3, 3),
                          (15, 4, 2, 3), (20, 4, 5, 4)])

    def test_skeleton_clearance_follows_live_cavern_gate_opening_and_closing(self):
        game, combat, actor = self.encounter(14)
        actor.room, actor.row = 16, 2
        actor.state.target_x = actor.state.current_x = 330
        actor.state.facing = 1
        self.assertEqual(game.level_map.tile(16, 7, 2).kind, 4)
        for opening, expected in ((0, False), (103, False), (104, True),
                                  (188, True), (103, False)):
            with self.subTest(opening=opening):
                game.caverns.plates.foreground[16, 27] = 0x200 | opening
                self.assertEqual(combat._guard_floor_clear(actor, 1, 1), expected)

    def test_inert_bones_never_awaken_or_display_105_lives(self):
        for room in (3, 5):
            game, combat, actor = self.encounter(room)
            combat.player.state.target_x = actor.state.target_x + 51
            self.tick(combat, 200)
            self.assertEqual((actor.life, actor.state.action, actor.skeleton.phase),
                             (0, 206, 'dormant'))
            self.assertIsNone(combat.health_opponent())

    def test_waking_rejects_native_impassable_tiles_including23(self):
        from types import SimpleNamespace

        _, c, actor = self.encounter(14)
        c.player.state.target_x = actor.state.target_x - 51
        actor.skeleton.timer = 0
        for kind in (0, 9, 11, 12, 13, 15, 20, 23, 24, 26, 27, 47, 49):
            with self.subTest(kind=kind):
                c.terrain = SimpleNamespace(tile=lambda *_args: Tile(kind))
                self.assertFalse(actor.skeleton.can_wake(c, actor))
        c.terrain = SimpleNamespace(tile=lambda *_args: Tile(1))
        self.assertTrue(actor.skeleton.can_wake(c, actor))

    def test_waking_gate_uses_bone_pose_height_not_fixed120_threshold(self):
        from types import SimpleNamespace

        _, c, actor = self.encounter(14)
        actor.state.action = 206
        actor.skeleton.timer = 0
        c.player.state.target_x = actor.state.target_x - 51
        for opening, expected in ((0, False), (47, False), (48, True),
                                  (103, True), (119, True), (120, True)):
            with self.subTest(opening=opening):
                c.terrain = SimpleNamespace(tile=lambda *_args: Tile(4, 0x200 | opening))
                self.assertEqual(actor.skeleton.can_wake(c, actor), expected)

    def test_wake_distance_uses_supporting_feet_and_rejects_shadow(self):
        from types import SimpleNamespace

        _, c, actor = self.encounter(14)
        actor.skeleton.timer = 0
        c.terrain = SimpleNamespace(tile=lambda *_args: Tile(1))
        with patch.object(c, '_supporting_column', side_effect=(5, 0)):
            self.assertFalse(actor.skeleton.can_wake(c, actor))
        with patch.object(c, '_supporting_column', side_effect=(5, 1)):
            self.assertTrue(actor.skeleton.can_wake(c, actor))
        c.player.state.actor_type = 1
        self.assertFalse(actor.skeleton.can_wake(c, actor))

    def test_collapse_edge_alignment_only_faces_right_and_uses_cached_column(self):
        from types import SimpleNamespace

        for facing in (0, 1):
            for kind in (0, 1, 4, 9):
                for distance in (-4, -3, 0, 25, 50):
                    with self.subTest(facing=facing, kind=kind, distance=distance):
                        _, c, actor = self.encounter(14)
                        actor.state.target_x = actor.state.current_x = 300
                        actor.state.facing = facing
                        c.terrain = SimpleNamespace(tile=lambda *_args: Tile(kind))
                        with patch.object(c, '_guard_front_edge_distance', return_value=distance), \
                                patch.object(c, '_guard_tile', return_value=Tile(kind)) as tile:
                            actor.skeleton.collapse(actor, encounter=c, column=8)
                        offset = distance + 3 if facing and kind in (0, 9) and distance >= -3 else 0
                        self.assertEqual((actor.state.target_x, actor.state.current_x), (300 + offset,) * 2)
                        if facing:
                            tile.assert_called_once_with(actor, 7)
                        else:
                            tile.assert_not_called()
                        self.assertEqual((actor.selected_sequence, actor.life, actor.skeleton.timer),
                                         (120, 0, 120))

    def test_landing_collapse_does_not_apply_standing_edge_alignment(self):
        _, c, actor = self.encounter(14)
        actor.state.facing = 1
        x = actor.state.target_x
        with patch.object(c, '_guard_tile', side_effect=AssertionError('landing queried rear')):
            actor.skeleton.collapse(actor, landing=True, encounter=c)
        self.assertEqual((actor.selected_sequence, actor.state.target_x), (112, x))

    def test_noise_consumed_in_adjacent_room_updates_real_player_not_only_view(self):
        _, c, actor = self.boundary_encounter()
        actor.skeleton = None
        actor.sword_drawn = False
        actor.state.action = 166
        c.player.state.callback_flag = 1
        position = c.player.room, c.player.state.target_x
        with c._local_opponents(actor):
            c.choose_guard_action(actor)
        self.assertEqual(c.player.state.callback_flag, 0)
        self.assertEqual((c.player.room, c.player.state.target_x), position)

    def test_waking_clears_original_pending_player_noise(self):
        from types import SimpleNamespace

        _, c, actor = self.encounter(14)
        c.terrain = SimpleNamespace(tile=lambda *_args: Tile(1))
        actor.skeleton.timer = actor.skeleton.shakes = 0
        select_sequence(actor, 119)
        actor.runtime.next_frame()
        c.player.state.target_x = actor.state.target_x - 51
        c.player.state.callback_flag = 1
        actor.skeleton.try_wake(c, actor)
        self.assertEqual(actor.selected_sequence, 88)
        self.assertEqual(c.player.state.callback_flag, 0)

    def test_last_rising_poses_resume_native_decisions_before_idle(self):
        _, c, actor = self.encounter(14)
        actor.life = actor.max_life
        actor.skeleton.phase = 'rising'
        actor.sword_drawn = True
        select_sequence(actor, 88)
        for pose in (206, 184, 182, 179, 178, 177, 176, 173):
            with self.subTest(pose=pose):
                actor.state.action = pose
                self.assertEqual(actor.skeleton.control(c, actor), pose >= 179)

    def assert_enemy_meter(self, combat, life):
        image = Image.new('RGBA', (512, 384))
        self.health_art.draw(image, combat)
        expected = Image.new('RGBA', image.size)
        for index in range(life):
            icon = self.health_art.icons[298]
            expected.paste(icon, (496 - index * 12, 368), icon)
        self.assertEqual(image.crop((256, 368, 512, 384)).tobytes(),
                         expected.crop((256, 368, 512, 384)).tobytes())

    def test_late_wake_shows_health_while_skeleton_is_still_in_previous_room(self):
        _, combat, actor = self.encounter(14)
        combat.player.state.target_x = combat.player.state.current_x = 300
        self.tick(combat, 10)
        self.assertEqual(actor.skeleton.phase, 'dormant')
        self.assertGreater(actor.skeleton.timer, 0)
        self.assert_enemy_meter(combat, 0)
        combat.enter_room(16, 2)
        combat.player.state.target_x = combat.player.state.current_x = 40
        self.assertIsNone(combat.guard)
        self.assert_enemy_meter(combat, 0)
        for _ in range(60):
            self.tick(combat)
            if actor.skeleton.phase == 'rising':
                break
        self.assertEqual(actor.skeleton.phase, 'rising')
        self.assertEqual((combat.player.room, actor.room, actor.life), (16, 14, 3))
        self.assertIs(combat.health_opponent(), actor)
        self.assertIsNone(combat.guard)
        before = actor.state.target_x, actor.state.cursor, actor.skeleton.phase, actor.life
        self.assert_enemy_meter(combat, 3)
        self.assertEqual(before, (actor.state.target_x, actor.state.cursor,
                                  actor.skeleton.phase, actor.life))
        self.tick(combat, 22)
        self.assertEqual(actor.skeleton.phase, 'active')
        self.assertGreater(actor.state.target_x, 381)
        self.assert_enemy_meter(combat, 3)

    def test_live_run_past_skeleton_displays_meter_as_soon_as_it_rises_offscreen(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        s = self.scene
        s.load_level(3)
        s.peaceful = False
        s.combat.rng = random.Random(17)
        s.jump_to_room(14, row=2, x=300, facing=1)
        s.in_animation_tick = True
        actor = s.combat.guards[0]
        s.horizontal_key(None, 1, True)
        with patch.object(s, 'render'):
            for _ in range(30):
                RooftopSceneTests.tick(self)
                if s.room_id == 16:
                    s.horizontal_key(None, 1, False)
                    break
            self.assertEqual(s.room_id, 16)
            # InitOpps clears a reloaded heap's timer before this room's
            # proximity pass; it can already have started rising on the cut.
            self.assertTrue(actor.alive)
            for _ in range(50):
                RooftopSceneTests.tick(self)
                if actor.alive:
                    break
        self.assertEqual((s.room_id, actor.room, actor.skeleton.phase), (16, 14, 'rising'))
        self.assertIsNone(s.combat.guard)
        self.assertIs(s.combat.health_opponent(), actor)
        for life in (3, 2, 1, 0):
            actor.life = life
            s.render()
            expected = Image.new('RGBA', (512, 384), (0, 0, 0, 255))
            for index in range(life):
                icon = s.health_art.icons[298]
                expected.paste(icon, (496 - index * 12, 368), icon)
            self.assertEqual(s.screenshot_viewport.crop((256, 368, 512, 384)).tobytes(),
                             expected.crop((256, 368, 512, 384)).tobytes())

    def test_side_room_meter_tracks_remaining_life_from_both_sides(self):
        for room, x in ((13, 490), (16, 40)):
            with self.subTest(room=room + 1):
                _, combat, actor = self.encounter(14)
                combat.player.state.target_x = actor.state.target_x - 51
                self.tick(combat, 100)
                self.assertEqual(actor.skeleton.phase, 'active')
                actor.state.target_x = actor.state.current_x = (381 if room == 16 else 17)
                combat.enter_room(room, 2)
                combat.player.state.target_x = combat.player.state.current_x = x
                for life in (3, 2, 1, 0):
                    actor.life = life
                    self.assert_enemy_meter(combat, life)

    def test_meter_remains_above_skeleton_but_does_not_follow_to_distant_rooms(self):
        _, combat, actor = self.encounter(14)
        self.tick(combat, 100)
        self.assertEqual(actor.skeleton.phase, 'active')
        actor.pursuing = True
        actor.state.target_x = actor.state.current_x = 400
        combat.enter_room(16, 1)
        self.assertIs(combat.health_opponent(), actor)
        self.assert_enemy_meter(combat, 3)
        combat.enter_room(18, 2)
        self.assertNotIn(actor, combat.active_guards())
        self.assertIsNone(combat.health_opponent())
        self.assert_enemy_meter(combat, 0)

    def test_combat_music_matches_native_modes_rows_and_alert_levels(self):
        _, combat, actor = self.encounter(14)
        actor.life = actor.max_life
        combat.player.state.action = 15
        for row in range(3):
            for mode in range(10):
                for alert in range(4):
                    with self.subTest(row=row, mode=mode, alert=alert):
                        combat.player.row = row
                        combat.player.state.animation_state = mode
                        actor.alert_mode = alert
                        self.assertEqual(combat.opponent_to_fight(),
                                         mode not in (3, 4) and alert > 0)

    def test_combat_music_excludes_native_player_and_opponent_states(self):
        for condition in ('dead_player', 'shadow', 'special13', 'dead_pose',
                          'dead_guard', 'no_alert', 'special_guard'):
            with self.subTest(condition=condition):
                _, combat, actor = self.boundary_encounter()
                if condition == 'dead_player':
                    combat.player.life = 0
                elif condition == 'shadow':
                    combat.player.state.actor_type = 1
                elif condition == 'special13':
                    combat.player.state.special_flag = 13
                elif condition == 'dead_pose':
                    combat.player.state.action = 185
                elif condition == 'dead_guard':
                    actor.life = 0
                elif condition == 'no_alert':
                    actor.alert_mode = 0
                else:
                    actor.state.actor_type = 11
                self.assertFalse(combat.opponent_to_fight())

    def test_meter_uses_vertical_distance_even_without_combat_music(self):
        from dataclasses import replace

        _, combat, actor = self.boundary_encounter()
        other = replace(actor, room=16, row=1, life=1, skeleton=None,
                        runtime=SequenceRuntime(combat.sequences,
                                                replace(actor.state, target_x=40)))
        combat.guards.append(other)
        self.assertIs(combat.health_opponent(), actor)
        combat.player.row = 1
        self.assertIs(combat.health_opponent(), other)
        combat.player.row = 0
        actor.alert_mode = other.alert_mode = 0
        self.assertIs(combat.health_opponent(), other)
        self.assert_enemy_meter(combat, 1)
        self.assertFalse(combat.opponent_to_fight())

    def test_meter_chooses_nearest_living_actor_using_side_room_coordinates(self):
        from dataclasses import replace

        _, combat, actor = self.boundary_encounter(armed=True)
        combat.player.state.target_x = 40
        actor.state.target_x = 381
        state = replace(actor.state, target_x=100, current_x=100)
        other = replace(actor, room=16, life=1, skeleton=None,
                        runtime=SequenceRuntime(combat.sequences, state))
        combat.guards.append(other)
        self.assertIs(combat.health_opponent(), other)
        self.assert_enemy_meter(combat, 1)
        other.state.target_x = 400
        self.assertIs(combat.health_opponent(), actor)
        self.assert_enemy_meter(combat, 3)
        other.state.target_x, other.life = 45, 0
        self.assertIs(combat.health_opponent(), actor)
        hidden = Image.new('RGBA', (512, 384))
        self.health_art.draw(hidden, combat, show_opponent=False)
        self.assertIsNone(hidden.crop((256, 368, 512, 384)).getbbox())

    def test_bone_poses_use_environment_shapes_and_matching_bounds(self):
        from pop2.caverns import cavern_assets
        from pop2.render_opening import decode_shap
        _, resources, palette, _ = cavern_assets()
        base = int.from_bytes(resources['SHPL'][3500]['data'][:2], 'big')
        for action in range(206, 210):
            for facing in (0, 1):
                _, _, actor = self.encounter()
                actor.state.action, actor.state.facing = action, facing
                record = self.art.frames[action - 149]
                expected = decode_shap(resources['SHAP'][base + 109 + record.shape_index]['data'], palette)
                body = self.art.body(actor.state)
                self.assertEqual(body.tobytes(), expected.tobytes())
                self.assertLess(body.height, 24)
                left, top, right, bottom = self.art.bounds(actor.state, 346)
                self.assertEqual((right - left + 1, bottom - top + 1), body.size)

    def test_rising_faces_prince_at_native_midpoint_once(self):
        for side in (-1, 1):
            _, combat, actor = self.encounter()
            combat.player.state.target_x = actor.state.target_x + side * 51
            for _ in range(120):
                self.tick(combat)
                if actor.skeleton.phase == 'rising' and actor.state.action == 182:
                    break
            self.assertEqual((actor.skeleton.phase, actor.state.action), ('rising', 182))
            actor.state.facing = int(side < 0)
            x = actor.state.target_x
            actor.skeleton.control(combat, actor)
            self.assertEqual(actor.state.facing, int(side > 0))
            self.assertEqual(actor.state.target_x, x + side * 16)
            actor.skeleton.control(combat, actor)
            self.assertEqual(actor.state.target_x, x + side * 16)

    def test_skeleton_running_steps_use_original_sound_callback(self):
        state = SequenceState(1, actor_type=4, level_kind=3)
        runtime = SequenceRuntime({1: (-15, 1, 150, -1, 1)}, state)
        runtime.next_frame()
        runtime.next_frame()
        self.assertEqual(state.sound_events, [295, 294])
        self.assertEqual(state.callback_flag, 0)

    def test_nearby_same_floor_awakes_using_original_pose_chain(self):
        game, combat, actor = self.encounter()
        actions = []
        for _ in range(100):
            self.tick(combat)
            actions.append(actor.state.action)
            if actor.skeleton.phase == 'active':
                break
        self.assertEqual(actor.skeleton.phase, 'active')
        self.assertEqual(actor.life, 3)
        self.assertIn(209, actions)
        self.assertIn(176, actions)
        self.assertTrue(actor.sword_drawn)
        self.assertEqual(actor.state.actor_type, 4)

    def test_different_floor_and_dead_prince_do_not_activate_bones(self):
        for dead in (False, True):
            game, combat, actor = self.encounter()
            combat.player.row = 1 if not dead else 2
            combat.player.life = 0 if dead else 3
            self.tick(combat, 80)
            self.assertEqual(actor.skeleton.phase, 'dormant')

    def test_collapse_and_120_tick_recovery_preserve_same_enemy_and_skill(self):
        game, combat, actor = self.encounter(19)
        combat.player.state.target_x = actor.state.target_x - 51
        self.tick(combat, 100)
        self.assertEqual(actor.skeleton.phase, 'active')
        actor.life = 1
        event = combat._hurt('guard', actor, combat.player)
        self.assertEqual((event.kind, actor.state.source_sequence_id), ('death', 120))
        self.assertEqual(actor.skeleton.timer, 120)
        self.tick(combat, 119)
        self.assertEqual(actor.life, 0)
        self.tick(combat, 100)
        self.assertIs(combat.guards[0], actor)
        self.assertEqual(actor.skeleton.phase, 'active')
        self.assertEqual((actor.life, actor.skill), (4, 5))

    def stationary_bones(self, sequence=119, timer=0, shakes=0):
        from types import SimpleNamespace
        from pop2.combat import GuardIntent
        from pop2.enemy_profiles import QuickDrawRandom

        _, combat, actor = self.encounter(14)
        actor.state.target_x = actor.state.current_x = 300
        combat.player.state.target_x = combat.player.state.current_x = 250
        combat.player.state.animation_state = 1
        actor.skeleton.phase = 'dormant'
        actor.skeleton.timer, actor.skeleton.shakes = timer, shakes
        select_sequence(actor, sequence)
        actor.runtime.next_frame()
        actor.state.sound_events.clear()
        combat.terrain = SimpleNamespace(tile=lambda *_args: Tile(1), neighbor=lambda *_args: None)
        combat.rng = QuickDrawRandom(1)
        combat.decide_guard_intent = lambda *_args: GuardIntent()
        combat.apply_guard_intent = lambda *_args: None
        combat._advance_guard_terrain = lambda *_args: None
        return combat, actor

    def test_timer_one_expires_after_proximity_check_not_before_it(self):
        combat, actor = self.stationary_bones(timer=1)
        self.tick(combat)
        self.assertEqual((actor.life, actor.skeleton.timer, actor.selected_sequence), (0, 0, 119))
        self.tick(combat)
        self.assertEqual((actor.life, actor.skeleton.phase, actor.state.action), (3, 'rising', 207))

    def test_shake_roll_precedes_the_same_frames_dead_timer_decrement(self):
        combat, actor = self.stationary_bones(shakes=1)
        self.tick(combat)
        # QuickDraw seed 1: Rnd(30) == 5; 15+5 is decremented by AutoCtrl.
        self.assertEqual((actor.skeleton.shakes, actor.skeleton.timer), (0, 19))
        self.assertEqual((actor.state.source_sequence_id, actor.state.action), (112, 208))
        self.assertEqual(actor.state.sound_events, [61])

    def test_unfinished_shake_advances_without_restarting_when_timer_is_zero(self):
        combat, actor = self.stationary_bones(sequence=112, shakes=1)
        self.assertEqual(actor.state.action, 207)
        self.tick(combat)
        self.assertEqual((actor.skeleton.shakes, actor.skeleton.timer), (0, 19))
        self.assertEqual((actor.state.action, actor.state.cursor), (206, 7))
        self.assertEqual(actor.state.sound_events, [])

    def test_finished_shakes_can_rise_before_waiting_sequence119(self):
        combat, actor = self.stationary_bones(sequence=112)
        combat.attack_pause = 9
        combat.player.state.callback_flag = 1
        self.tick(combat)
        self.assertEqual((actor.selected_sequence, actor.state.action, actor.life), (88, 207, 3))
        self.assertEqual((actor.skeleton.phase, actor.alert_mode), ('rising', 3))
        self.assertTrue(actor.sword_drawn)
        self.assertEqual((combat.attack_pause, combat.player.state.callback_flag), (0, 0))
        self.assertEqual(actor.state.sound_events, [60])

    def test_alive_skeleton_does_not_decrement_dead_recovery_timer(self):
        combat, actor = self.stationary_bones(timer=7)
        actor.life = actor.max_life
        actor.skeleton.phase = 'rising'
        select_sequence(actor, 88)
        actor.state.action = 180
        self.assertTrue(actor.skeleton.control(combat, actor))
        self.assertEqual(actor.skeleton.timer, 7)

    def test_hurt_during_rising_does_not_reapply_rising_midpoint_turn(self):
        combat, actor = self.stationary_bones()
        actor.life = actor.max_life
        actor.skeleton.phase = 'rising'
        select_sequence(actor, 183)
        actor.state.action = 182
        actor.state.facing = 1
        before = actor.state.target_x, actor.state.facing
        self.assertFalse(actor.skeleton.control(combat, actor))
        self.assertEqual((actor.state.target_x, actor.state.facing), before)

    def test_repeated_input_callbacks_do_not_repeat_waking_or_speed_up_recovery(self):
        combat, actor = self.stationary_bones(timer=1)
        combat.step(10, .1)
        snapshot = (actor.state.cursor, actor.skeleton.timer, actor.life)
        for _ in range(20):
            combat.step(10, .1)
            self.assertEqual((actor.state.cursor, actor.skeleton.timer, actor.life), snapshot)
        combat.step(10.1, .1)
        self.assertEqual((actor.state.action, actor.life), (207, 3))

    def test_live_scene_wakes_after_timer_expiry_and_displays_second_rising_pose(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(3)
        scene.jump_to_room(14, row=2, x=300, facing=1)
        actor = scene.combat.guards[0]
        actor.skeleton.timer, actor.skeleton.shakes = 1, 0
        select_sequence(actor, 119)
        actor.runtime.next_frame()
        with patch.object(scene, 'render'):
            RooftopSceneTests.tick(self)
            self.assertEqual((actor.life, actor.skeleton.timer), (0, 0))
            RooftopSceneTests.tick(self)
        self.assertEqual((actor.life, actor.skeleton.phase, actor.state.action), (3, 'rising', 207))
        self.assertIs(scene.combat.health_opponent(), actor)

    def test_room17_loads_nearby_room15_skeleton_without_a_previous_visit(self):
        game = GameSession.load(self.resources, 3)
        combat = game.combat
        self.assertNotIn(14, combat.room_encounters)
        game.place(16, 2, 40, 0)
        combat.guard_art = self.art
        actor, = combat.room_encounters[14][0]
        self.assertEqual((actor.room, actor.state.target_x), (14, 381))
        self.assertIn(actor, combat.active_guards())
        self.tick(combat, 100)
        self.assertTrue(actor.alive)
        self.assertIs(combat.health_opponent(), actor)
        combat.enter_room(14, 2)
        self.assertIs(combat.room_encounters[14][0][0], actor)

    def test_invisible_neighbor_is_not_initialized_by_room_entry(self):
        game = GameSession.load(self.resources, 3)
        game.place(12, 2, 40, 0)
        self.assertNotIn(10, game.combat.room_encounters)

    def test_armed_skeleton_follows_at_native_horizontal_cut_thresholds(self):
        from pop2.terrain import TerrainMotion

        for room, x, follows in ((13, 123, True), (13, 124, False),
                                  (16, 384, False), (16, 385, True)):
            with self.subTest(room=room, x=x):
                _, combat, actor = self.encounter(14)
                actor.life, actor.sword_drawn, actor.skeleton.phase = 2, True, 'active'
                actor.state.target_x = actor.state.current_x = x
                actor.terrain_motion = TerrainMotion(14, 2)
                select_sequence(actor, 227)
                actor.runtime.next_frame()
                pose = actor.state.action, actor.state.sequence_id, actor.state.cursor
                combat.enter_room(room, 2)
                self.assertEqual(actor.room, room if follows else 14)
                expected = x + (510 if room == 13 else -510) if follows else x
                self.assertEqual((actor.state.target_x, actor.state.current_x), (expected, expected))
                reinitialized = room == 16 and x == 384
                self.assertEqual((actor.life, actor.max_life), (0 if reinitialized else 2, 3))
                if follows:
                    self.assertEqual((actor.state.action, actor.state.sequence_id, actor.state.cursor),
                                     (170, 227, pose[2] + 1))
                elif reinitialized:
                    self.assertEqual((actor.skeleton.phase, actor.selected_sequence), ('dormant', 112))
                else:
                    self.assertEqual((actor.state.action, actor.state.sequence_id, actor.state.cursor), pose)
                self.assertEqual(actor.terrain_motion.room, actor.room)
                self.assertEqual(sum(g is actor for guards, _ in combat.room_encounters.values()
                                     for g in guards), 1)

    def test_cut_priority_matches_native_runner_life_sword_and_capacity_gates(self):
        from pop2.combat import opponent_follows_cut

        _, _combat, actor = self.encounter(14)
        actor.state.target_x = 400
        for pose, flags, life, sword, count, inside, follows in (
                (158, 0, 3, True, 4, False, True),
                (158, 0, 3, True, 5, False, False),
                (158, 0, 3, False, 0, False, False),
                (158, 0, 0, True, 0, False, False),
                (158, 0, 0, False, 5, True, True),
                (186, -1, 0, False, 5, False, True),
                (201, 2, 3, False, 0, False, True),
                (201, 0, 3, False, 0, False, False),
                (202, 1, 3, False, 0, False, True),
                (212, 1, 0, False, 0, False, True),
                (212, 2, 3, False, 0, False, False),
                (213, 1, 3, False, 0, False, False)):
            with self.subTest(pose=pose, flags=flags, life=life, sword=sword, count=count):
                actor.state.action, actor.generation_flags = pose, flags
                actor.life, actor.sword_drawn = life, sword
                self.assertEqual(opponent_follows_cut(actor, 'right', count,
                                                      in_destination=inside), follows)

    def test_full_destination_keeps_skeleton_record_instead_of_losing_actor(self):
        from dataclasses import replace

        _, combat, actor = self.encounter(14)
        actor.life, actor.sword_drawn = 2, True
        actor.state.target_x = actor.state.current_x = 400
        select_sequence(actor, 227)
        actor.runtime.next_frame()
        combat._load_room(16)
        residents = combat.room_encounters[16][0]
        for _ in range(5):
            residents.append(replace(actor, room=16, bank_room=None, runtime=SequenceRuntime(
                combat.sequences, SequenceState(119, actor_type=4, action=206, cursor=1,
                                                current_x=250, target_x=250)),
                skeleton=replace(actor.skeleton)))
        combat.enter_room(16, 2)
        self.assertEqual((actor.room, actor.life), (14, 2))
        self.assertNotIn(actor, combat.active_guards())
        self.assertEqual(len(residents), 5)

    def test_dead_skeleton_is_not_carried_merely_for_being_near_the_cut(self):
        _, combat, actor = self.encounter(14)
        actor.state.target_x = actor.state.current_x = 400
        actor.life, actor.sword_drawn = 0, True
        select_sequence(actor, 119)
        actor.runtime.next_frame()
        combat.enter_room(16, 2)
        self.assertEqual(actor.room, 14)
        self.assertIn(actor, combat.active_guards())
        self.assertEqual(actor.bank_room, 16)

    def test_armed_skeleton_cut_rebases_vertical_row_without_restarting_pose(self):
        from types import SimpleNamespace
        from pop2.terrain import TerrainMotion, floor_y

        for direction, row, destination in (('up', -1, 11), ('down', 3, 12)):
            with self.subTest(direction=direction):
                _, combat, actor = self.encounter(10)
                combat.terrain = SimpleNamespace(neighbor=lambda room, side: (
                    destination if room == 10 and side == direction else None))
                del combat.guard_art
                actor.life, actor.sword_drawn, actor.skeleton.phase = 2, True, 'active'
                actor.row = row
                actor.terrain_motion = TerrainMotion(10, row, falling=True)
                select_sequence(actor, 227)
                actor.runtime.next_frame()
                actor.state.current_y = 7
                before = floor_y(row) + 7
                pose = actor.state.sequence_id, actor.state.cursor, actor.state.action
                combat.enter_room(destination, 2 if direction == 'up' else 0)
                self.assertEqual(actor.room, destination)
                self.assertEqual(actor.row, row + (3 if direction == 'up' else -3))
                self.assertEqual(floor_y(actor.row) + actor.state.current_y,
                                 before - 7 + (360 if direction == 'up' else -360))
                self.assertEqual((actor.terrain_motion.room, actor.terrain_motion.row),
                                 (actor.room, actor.row))
                self.assertEqual((actor.life, actor.state.target_x), (2, 353))
                self.assertEqual((actor.state.sequence_id, actor.state.cursor, actor.state.action),
                                 (pose[0], pose[1] + 1, 170))

    def test_unselected_neighbor_bones_and_distant_pursuers_do_not_tick(self):
        from copy import deepcopy

        for room in (16, 0):
            with self.subTest(room=room):
                _, combat, actor = self.encounter(14)
                actor.state.target_x = actor.state.current_x = 300
                actor.skeleton.timer = 99
                actor.pursuing = True
                combat.enter_room(room, 2)
                self.assertNotIn(actor, combat.active_guards())
                before = deepcopy((vars(actor.state), vars(actor.skeleton)))
                self.tick(combat, 30)
                self.assertEqual((vars(actor.state), vars(actor.skeleton)), before)
                self.assertIsNone(combat.health_opponent())

    def test_vertical_cut_reindexes_row_from_absolute_height_during_a_fall(self):
        from types import SimpleNamespace
        from pop2.terrain import TerrainMotion, floor_y

        _, combat, actor = self.encounter(10)
        combat.terrain = SimpleNamespace(neighbor=lambda room, side: (
            12 if room == 10 and side == 'down' else None))
        del combat.guard_art
        actor.life, actor.sword_drawn = 2, True
        actor.row, actor.state.current_y = 2, 100
        actor.terrain_motion = TerrainMotion(10, 2, falling=True)
        actor.state.action, actor.generation_flags = 202, 1
        combat.enter_room(12, 0)
        self.assertEqual((actor.room, actor.row, actor.state.current_y), (12, 0, 0))
        self.assertEqual(floor_y(actor.row) + actor.state.current_y, 106)
        self.assertEqual((actor.terrain_motion.row, actor.terrain_motion.falling), (0, False))

    def test_position_lookup_uses_horizontal_link_when_vertical_corner_link_is_missing(self):
        _, combat, actor = self.encounter(14)
        actor.state.target_x = actor.state.current_x = -100
        actor.row, actor.state.action, actor.state.facing = -1, 158, 0
        before = actor.room, actor.row, actor.state.target_x, actor.state.current_y
        self.assertIsNone(combat.terrain.neighbor(14, 'up'))
        self.assertEqual(combat._position_room(actor), 1)
        self.assertEqual((actor.room, actor.row, actor.state.target_x, actor.state.current_y), before)

    def test_imported_skeleton_keeps_bank_membership_after_leaving_import_region(self):
        _, combat, actor = self.encounter(14)
        select_sequence(actor, 119)
        actor.runtime.next_frame()
        combat.enter_room(16, 2)
        self.assertEqual(actor.bank_room, 16)
        actor.state.target_x = actor.state.current_x = 300
        self.assertIn(actor, combat.active_guards())
        actor.skeleton.timer = 99
        self.tick(combat)
        self.assertEqual(actor.skeleton.timer, 98)
        combat.enter_room(0, 2)
        self.assertNotIn(actor, combat.active_guards())

    def test_non_following_skeleton_record_moves_to_its_physical_side_room(self):
        _, combat, actor = self.encounter(14)
        select_sequence(actor, 112)
        actor.runtime.next_frame()
        actor.state.current_x = actor.state.target_x = 560
        cursor = actor.state.cursor
        combat.enter_room(0, 2)
        self.assertEqual((actor.room, actor.row, actor.state.target_x), (16, 2, 50))
        self.assertNotIn(actor, combat.room_encounters[14][0])
        self.assertIn(actor, combat.room_encounters[16][0])
        self.assertEqual(actor.skeleton.room_record.cursor, cursor)
        self.assertEqual(actor.skeleton.room_record.sequence, 112)
        self.assertEqual(sum(g is actor for guards, _ in combat.room_encounters.values()
                             for g in guards), 1)
        combat.enter_room(16, 2)
        self.assertIs(combat.guards[0], actor)
        self.assertIsNone(actor.skeleton.room_record)
        self.assertNotEqual(actor.state.cursor, cursor)

    def test_non_following_vertical_record_uses365_without_changing_live_carry(self):
        import struct
        from pop2.terrain import LevelMap, TerrainMotion

        _, combat, actor = self.encounter(14)
        level = bytearray(combat.level)
        struct.pack_into('>H', level, 0x2080 + 14 * 8 + 6, 1)
        combat.terrain = LevelMap(level)
        actor.state.current_x = actor.state.target_x = 300
        actor.row, actor.state.current_y = 3, -10
        actor.terrain_motion = TerrainMotion(14, 3, falling=True)
        cursor = actor.state.cursor
        combat.enter_room(2, 1)
        self.assertEqual((actor.room, actor.row, actor.state.target_x, actor.state.current_y),
                         (0, 0, 300, -15))
        self.assertEqual((actor.terrain_motion.room, actor.terrain_motion.row), (0, 0))
        self.assertEqual(actor.skeleton.room_record.cursor, cursor)
        self.assertNotIn(actor, combat.active_guards())

    def test_record_without_a_destination_is_removed_instead_of_reappearing(self):
        import struct
        from pop2.terrain import LevelMap

        _, combat, actor = self.encounter(14)
        level = bytearray(combat.level)
        struct.pack_into('>H', level, 0x2080 + 14 * 8 + 2, 0)
        combat.terrain = LevelMap(level)
        actor.state.current_x = actor.state.target_x = 560
        combat.enter_room(0, 2)
        self.assertFalse(any(g is actor for guards, _ in combat.room_encounters.values() for g in guards))
        combat.enter_room(14, 2)
        self.assertNotIn(actor, combat.active_guards())
        self.assertEqual(combat.guards, [])

    def test_imported_record_normalization_does_not_accumulate_coordinate_drift(self):
        _, combat, actor = self.encounter(14)
        for _ in range(4):
            combat.enter_room(16, 2)
            self.assertIn(actor, combat.active_guards())
            combat.enter_room(0, 2)
            self.assertEqual((actor.room, actor.row, actor.state.target_x), (14, 2, 381))
            combat.enter_room(14, 2)
            self.assertIs(combat.guards[0], actor)

    def test_record_in_row_minus_one_does_not_cut_to_upper_room(self):
        _, combat, actor = self.encounter(14)
        actor.state.current_x = actor.state.target_x = 300
        actor.row, actor.life = -1, 2
        column = combat._supporting_column(actor)
        combat.enter_room(0, 2)
        self.assertEqual((actor.room, actor.row), (14, -1))
        self.assertEqual(actor.skeleton.room_record.cell, -(column + 1))
        self.assertEqual(actor.skeleton.room_record.cursor, 0)
        combat.enter_room(14, 2)
        self.assertEqual(actor.row, -1)

    def test_negative_tenth_cell_reloads_with_native_signed_division(self):
        from pop2.skeleton import SkeletonRoomRecord

        _, combat, actor = self.encounter(14)
        actor.skeleton.room_record = SkeletonRoomRecord(119, 1, 0, False, -10)
        actor.skeleton.restore_room(actor, 0)
        self.assertEqual(actor.row, -2)
        self.assertEqual(actor.state.current_y, 0)

    def test_current_room_bank_precedes_side_imports_and_has_five_slots(self):
        from dataclasses import replace

        _, combat, actor = self.encounter(14)
        combat._load_room(16)
        residents = combat.room_encounters[16][0]
        for index in range(4):
            residents.append(replace(actor, room=16, bank_room=None, runtime=SequenceRuntime(
                combat.sequences, SequenceState(119, actor_type=4, action=206, cursor=1,
                                                current_x=250, target_x=250)),
                skeleton=replace(actor.skeleton)))
        combat.enter_room(16, 2)
        self.assertEqual(combat.active_guards(), residents + [actor])
        self.assertEqual(actor.bank_slot, 4)
        combat.enter_room(0, 2)
        residents.append(replace(residents[0], runtime=SequenceRuntime(
            combat.sequences, SequenceState(119, actor_type=4, action=206, cursor=1,
                                            current_x=250, target_x=250)),
            skeleton=replace(actor.skeleton)))
        combat.enter_room(16, 2)
        self.assertEqual(combat.active_guards(), residents)
        self.assertNotIn(actor, combat.active_guards())

    def test_shake_bones_obeys_marker_pose_row_and_special_flag_without_reset(self):
        for marker in (-1, 0, 1):
            for pose in (206, 207):
                for row in (1, 2):
                    for special in (0, 5):
                        with self.subTest(marker=marker, pose=pose, row=row, special=special):
                            combat, actor = self.stationary_bones(timer=120, shakes=1)
                            actor.skeleton.marker = marker
                            actor.state.action, actor.state.special_flag = pose, special
                            combat.shake_bones(actor.room, row)
                            changes = marker == 0 and pose == 206 and row == 2 and special != 5
                            self.assertEqual(actor.selected_sequence, 112 if changes else 119)
                            self.assertEqual((actor.skeleton.timer, actor.skeleton.shakes), (120, 1))

    def test_row_shake_reaches_visible_side_room_bones_but_not_distant_bones(self):
        _, combat, actor = self.encounter(14)
        actor.skeleton.timer = 120
        combat.enter_room(16, 2)
        select_sequence(actor, 119)
        actor.runtime.next_frame()
        actor.state.target_x = 378
        combat.shake_bones(16, 2)
        self.assertEqual(actor.selected_sequence, 119)
        actor.state.target_x = 379
        combat.shake_bones(16, 2)
        self.assertEqual(actor.selected_sequence, 112)
        self.assertEqual(actor.skeleton.timer, 120)

    def test_player_shake_request_reaches_bones_and_only_last_row_is_used(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(3)
        scene.jump_to_room(14, row=2, x=300, facing=1)
        actor = scene.combat.guards[0]
        actor.skeleton.timer = 120
        for requests, expected in (((-12,), 119), ((-13,), 112), ((-13, -12), 119),
                                   ((-12, -13), 112)):
            with self.subTest(requests=requests):
                select_sequence(actor, 119)
                actor.runtime.next_frame()
                scene.sequence_state.sequence_events = [(opcode, ()) for opcode in requests]
                scene.advance_level_events()
                self.assertEqual(actor.selected_sequence, expected)
                self.assertEqual(actor.skeleton.timer, 120)
                self.assertEqual(scene.game.caverns.loose.shake_events, [])
                self.assertEqual(scene.sequence_state.sequence_events, [])

    def test_falling_floor_impact_shakes_bones_without_resetting_recovery(self):
        from pop2.loose_floors import FallingFloor
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(3)
        scene.jump_to_room(14, row=2, x=300, facing=1)
        actor = scene.combat.guards[0]
        actor.skeleton.timer = 120
        select_sequence(actor, 119)
        actor.runtime.next_frame()
        column = next(col for col in range(10) if scene.level_map.tile(14, col, 2).kind == 1)
        scene.game.caverns.loose.falling = [FallingFloor(14, column, 2, 359)]
        scene.advance_cavern_floors()
        self.assertEqual((actor.selected_sequence, actor.skeleton.timer), (112, 120))
        self.assertEqual(scene.game.caverns.loose.shake_events, [])

    def test_player_has_native_extra_three_pixel_skeleton_strike_range(self):
        game, combat, actor = self.encounter()
        actor.alert_mode = 3
        self.assertEqual(strike_range(combat.player, actor), (61, 102))

    def test_skeleton_returns_to_bones_after_prince_death_counter_reaches_five(self):
        game, combat, actor = self.encounter()
        self.tick(combat, 100)
        self.assertEqual(actor.skeleton.phase, 'active')
        combat.player.life = 0
        combat.player_death_counter = 4
        self.tick(combat)
        self.assertEqual(actor.skeleton.phase, 'active')
        self.assertTrue(actor.sword_drawn)
        self.assertNotEqual(actor.state.source_sequence_id, 77)
        combat.player_death_counter = 5
        self.tick(combat)
        self.assertEqual((actor.skeleton.phase, actor.state.source_sequence_id), ('collapsing', 120))
        self.tick(combat, 200)
        self.assertEqual(actor.skeleton.phase, 'dormant')
        self.assertFalse(actor.alive)

    def test_prince_death_also_interrupts_a_rising_skeleton(self):
        _, combat, actor = self.encounter()
        for _ in range(120):
            self.tick(combat)
            if actor.skeleton.phase == 'rising':
                break
        self.assertEqual(actor.skeleton.phase, 'rising')
        combat.player.life = 0
        combat.player_death_counter = 5
        self.tick(combat)
        self.assertEqual((actor.skeleton.phase, actor.state.source_sequence_id), ('collapsing', 120))

    def test_all_reached_original_frames_draw_without_replacing_artwork(self):
        for room in (10, 14, 19):
            game, combat, actor = self.encounter(room)
            combat.player.state.target_x = actor.state.target_x - 51
            for _ in range(220):
                self.tick(combat)
                canvas = Image.new('RGBA', (510, 384))
                self.art.draw(canvas, actor.state, 346)
                self.assertIsNotNone(canvas.getbbox())
            self.assertEqual(actor.skeleton.phase, 'active')

    def test_room_revisit_reinitializes_living_skeleton_then_wakes_with_full_life(self):
        game, combat, actor = self.encounter()
        self.tick(combat, 100)
        actor.life = 2
        combat.enter_room(0, 2)
        combat.enter_room(10, 2)
        self.assertIs(combat.guards[0], actor)
        self.assertEqual((actor.life, actor.skeleton.phase, actor.selected_sequence), (0, 'dormant', 112))
        self.assertEqual((actor.skeleton.timer, actor.skeleton.shakes), (0, 0))
        self.tick(combat)
        self.assertEqual((actor.life, actor.skeleton.phase), (3, 'rising'))


if __name__ == '__main__':
    unittest.main()
