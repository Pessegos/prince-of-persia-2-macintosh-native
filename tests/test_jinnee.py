import unittest

from pop2.jinnee import RUNNING_FLAGS, SEQUENCE, Jinnee
from pop2.paths import ASSET_DIR
from pop2.potions import Potions
from pop2.sequence_runtime import SequenceRuntime, SequenceState
from pop2.terrain import TerrainMotion
from tools.audit_temple_routes import Harness, press, settle


def released(x, facing):
    kid = SequenceState(91, action=109, target_x=x, facing=facing, actor_type=0)
    return Jinnee.released(kid, TerrainMotion(22, 2))


class ReleaseTests(unittest.TestCase):
    def test_the_cloud_opens_85_pixels_ahead_and_he_always_faces_left(self):
        # 4:1da0-1da8 reads DATA -4b98 by the Kid's facing; 4:1e6a sets -1.
        self.assertEqual(released(230, 1).state.target_x, 315)
        self.assertEqual(released(230, 0).state.target_x, 145)
        self.assertEqual(released(230, 1).state.facing, 0)
        self.assertEqual((released(230, 1).motion.room, released(230, 1).motion.row), (22, 2))

    def test_columns_outside_minus_one_to_ten_remove_him(self):
        # 4:1d64. Port column 10 lies just past the room's last one.
        jinnee = released(230, 1)
        self.assertFalse(jinnee.gone)
        jinnee.state.target_x = 51 * 12
        self.assertTrue(jinnee.gone)
        jinnee.state.target_x = -51 * 3
        self.assertTrue(jinnee.gone)

    def test_only_sequence_111s_event_three_releases(self):
        potions, state = Potions(), SequenceState(111, actor_type=0)
        state.sequence_events.append((-14, (2,)))
        potions.consume_events(state, None)
        self.assertFalse(potions.jinnee_released)
        state.sequence_events.append((-14, (3,)))
        potions.consume_events(state, None)
        self.assertTrue(potions.jinnee_released)
        self.assertEqual(state.sequence_events, [])

    def test_the_flask_of_type_six_prompts_instead_of_healing(self):
        # 4:46b2. Before, the port left this flask on the floor.
        potions, state = Potions(), SequenceState(91, actor_type=0)
        potions.held_kind, potions.effect_pending = 6, True
        actor = replace_actor()
        state.sequence_events.append((-14, (1,)))
        potions.consume_events(state, actor)
        self.assertTrue(potions.jinnee_prompt)
        self.assertEqual(state.sound_events, [12])
        self.assertEqual(actor.life, 1)
        self.assertEqual(potions.songs, [])


def replace_actor():
    from types import SimpleNamespace
    return SimpleNamespace(alive=True, life=1, max_life=3)


@unittest.skipUnless((ASSET_DIR / 'Jinnee.rsrc').is_file()
                     and (ASSET_DIR / 'temple_level12.json').is_file(),
                     'Level 12 and Jinnee.rsrc must be imported')
class FlaskRouteTests(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(12)
        self.addCleanup(self.harness.close)
        self.harness.number = 12
        settle(self.harness, 300)
        self.scene = self.harness.scene

    def drink(self, x, facing):
        scene, harness = self.scene, self.harness
        scene.jump_to_room(22, 2, x, facing, redraw=False)
        harness.tick(20)
        press(harness, 'shift', True)
        harness.tick(6)
        press(harness, 'shift', False)

    def test_he_runs_under_the_shut_gate_and_treads_on_the_plate_behind_it(self):
        scene, harness = self.scene, self.harness
        self.drink(194, 1)
        plates = scene.game.caverns.plates
        terrain = scene.level_map
        poses, xs = [], []
        for _ in range(110):
            harness.tick()
            jinnee = scene.game.caverns.jinnee
            if jinnee is not None:
                poses.append(jinnee.state.action)
                xs.append(jinnee.state.target_x)
            if plates.timers.get(169):
                break
        self.assertEqual(terrain.tile(22, 8, 2).kind, 4)
        self.assertEqual(terrain.tile(22, 8, 2).foreground & 255, 0)
        self.assertTrue(plates.timers.get(169))
        self.assertEqual(poses[0], 150)
        self.assertEqual(set(poses) & {163, 164, 165, 166}, {163, 164, 165, 166})
        self.assertEqual(xs, sorted(xs))
        self.assertEqual(scene.game.caverns.potions.tiles[22, 24][0], 1)
        # He runs on past the plate and is removed.
        for _ in range(40):
            harness.tick()
        self.assertIsNone(scene.game.caverns.jinnee)

    def test_he_draws_a_cloud_then_a_small_runner(self):
        scene, harness = self.scene, self.harness
        self.drink(194, 1)
        boxes = []
        from pop2.environments import environment_for
        environment = environment_for(scene)
        for _ in range(40):
            harness.tick()
            for _state, _record, bounds, _row, _layer in environment.jinnee_actors((570, 400)):
                boxes.append(bounds)
        self.assertGreater(max(box[2] - box[0] for box in boxes), 60)
        self.assertLess(boxes[-1][2] - boxes[-1][0], 16)

    def test_the_rules_constants_are_frame_750s(self):
        from pop2.animation_data import parse_frame_records
        from pop2.jinnee import FIRST_POSE
        from pop2.render_opening import load_resource_file

        frames = parse_frame_records(load_resource_file('Jinnee.rsrc')['FRAM'][750]['data'])
        self.assertEqual({pose: frames[pose - FIRST_POSE].aux for pose in RUNNING_FLAGS}, RUNNING_FLAGS)
        words = self.scene.sequence_runtime.sequences
        state = SequenceState(SEQUENCE, actor_type=12)
        runtime = SequenceRuntime(words, state)
        seen = []
        for _ in range(26):
            runtime.next_frame()
            seen.append(state.action)
        self.assertEqual(seen[:13], list(range(150, 163)))
        self.assertEqual(seen[16:20], [163, 164, 165, 166])
