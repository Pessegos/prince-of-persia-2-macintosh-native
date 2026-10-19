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

    def test_inert_bones_never_awaken_or_display_105_lives(self):
        for room in (3, 5):
            game, combat, actor = self.encounter(room)
            combat.player.state.target_x = actor.state.target_x + 51
            self.tick(combat, 200)
            self.assertEqual((actor.life, actor.state.action, actor.skeleton.phase),
                             (0, 206, 'dormant'))
            self.assertIsNone(combat.health_opponent())

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
            self.assertFalse(actor.alive)
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
        combat.enter_room(16, 1)
        self.assertIs(combat.health_opponent(), actor)
        self.assert_enemy_meter(combat, 3)
        combat.enter_room(18, 2)
        self.assertIn(actor, combat.active_guards())
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

    def test_meter_prefers_same_floor_but_falls_back_without_combat_music(self):
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
        self.assertIs(combat.health_opponent(), actor)
        self.assert_enemy_meter(combat, 3)
        self.assertFalse(combat.opponent_to_fight())

    def test_meter_chooses_nearest_living_actor_using_side_room_coordinates(self):
        from dataclasses import replace

        _, combat, actor = self.encounter(14)
        self.tick(combat, 100)
        combat.enter_room(16, 2)
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

    def test_room_revisit_keeps_the_existing_skeleton_state(self):
        game, combat, actor = self.encounter()
        self.tick(combat, 100)
        actor.life = 2
        combat.enter_room(0, 2)
        combat.enter_room(10, 2)
        self.assertIs(combat.guards[0], actor)
        self.assertEqual(actor.life, 2)


if __name__ == '__main__':
    unittest.main()
