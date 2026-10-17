import random
import unittest

from PIL import Image

from pop2.combat import GuardSpawn, strike_range
from pop2.combat_art import GuardArtwork
from pop2.game_session import GameResources, GameSession
from pop2.paths import ASSET_DIR
from pop2.render_opening import load_resource_file
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
