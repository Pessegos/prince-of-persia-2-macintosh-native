from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from pop2.paths import ASSET_DIR


@unittest.skipUnless((ASSET_DIR / 'caverns_level5.json').is_file(), 'Imported cavern resources required')
class SkeletonLavaPersistenceTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        self.scene.render = Mock()

    def lava_entry(self, facing=1, collapsed=False):
        from pop2.combat import guard_frame_index, select_sequence
        from pop2.environments import environment_for
        from pop2.terrain import TerrainMotion, floor_contact_x

        scene = self.scene
        scene.load_level(5)
        scene.jump_to_room(22, 2, 280, 1)
        scene.in_animation_tick = True
        actor = scene.combat.guards[0]
        actor.skeleton.rise(scene.combat, actor)
        actor.skeleton.phase = 'active'
        actor.state.facing = facing
        select_sequence(actor, 227)
        actor.runtime.next_frame()
        if collapsed:
            actor.skeleton.collapse(actor, landing=True, encounter=scene.combat)
            actor.runtime.next_frame()
        frame = scene.guard_art.frames[guard_frame_index(actor.state.action)]
        # The final recoil position inside room23's real pool, without
        # simulating unrelated sword AI/random input leading to that push.
        actor.state.target_x += 405 - floor_contact_x(actor.state.target_x, facing, frame)
        actor.state.current_x = actor.state.target_x
        actor.terrain_motion = TerrainMotion(22, 2)
        environment_for(scene).level_events()
        self.assertEqual((actor.life, actor.skeleton.phase, actor.state.source_sequence_id),
                         (0, 'lava', 115))
        return actor

    def test_lava_sets_the_native_removal_flag_immediately_in_both_facings(self):
        from pop2.opponent_records import removed_on_room_save

        for facing in (0, 1):
            with self.subTest(facing=facing):
                actor = self.lava_entry(facing)
                self.assertEqual(actor.state.sequence_mode, 5)
                self.assertTrue(removed_on_room_save(actor))

    def test_zero_hp_heap_also_sinks_instead_of_becoming_a_revivable_lava_heap(self):
        for facing in (0, 1):
            with self.subTest(facing=facing):
                actor = self.lava_entry(facing, collapsed=True)
                self.assertEqual(actor.state.sequence_mode, 5)
                self.scene.combat.enter_room(1, 2)
                self.scene.combat.enter_room(22, 2)
                self.assertEqual(self.scene.combat.guards, [])

    def test_room_exit_removes_the_lava_skeleton_before_any_possible_revival(self):
        from tests.test_terrain import RooftopSceneTests

        for delay in (0, 2, 12, 140):
            with self.subTest(delay=delay):
                actor = self.lava_entry()
                RooftopSceneTests.tick(self, delay)
                combat = self.scene.combat
                combat.enter_room(1, 2)  # Room23's actual right neighbor.
                self.assertNotIn(actor, combat.room_encounters[22][0])
                for _ in range(3):
                    combat.enter_room(22, 2)
                    self.assertEqual(combat.guards, [])
                    combat.enter_room(1, 2)

    def test_snapshot_in_the_lava_animation_does_not_make_a_reviving_room_record(self):
        from pop2.save_game import capture_snapshot, read_snapshot, write_save

        self.lava_entry()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'lava-snapshot.json'
            write_save(path, capture_snapshot(self.scene.game))
            game, _document = read_snapshot(path, self.scene.resources)
        actor = game.combat.guards[0]
        self.assertEqual((actor.skeleton.phase, actor.state.sequence_mode), ('lava', 5))
        game.combat.enter_room(1, 2)
        self.assertNotIn(actor, game.combat.room_encounters[22][0])
        game.combat.enter_room(22, 2)
        self.assertEqual(game.combat.guards, [])

    def test_terminal_actor_in_the_previous_side_bank_is_not_restored_in_its_own_room(self):
        actor = self.lava_entry()
        combat = self.scene.combat
        # Controlled previous-bank projection: the sinking actor belongs to
        # room23 but was still registered in the visible room2 side bank.
        combat.player.room = 1
        actor.bank_room = 1
        self.assertIn(actor, combat.active_guards())
        combat.enter_room(22, 2)
        self.assertNotIn(actor, combat.guards)
        self.assertNotIn(actor, combat.active_guards())

    def test_a_fresh_level_restart_still_recreates_the_original_skeleton(self):
        self.lava_entry()
        game = self.scene.game
        game.combat.enter_room(1, 2)
        game.combat.enter_room(22, 2)
        self.assertEqual(game.combat.guards, [])
        game.restart()
        game.place(22, 2, 280, 1, reset_guards=False)
        self.assertEqual(len(game.combat.guards), 1)
        self.assertEqual(game.combat.guards[0].state.sequence_mode, 0)
        self.assertIsNotNone(game.combat.guards[0].skeleton)


if __name__ == '__main__':
    unittest.main()
