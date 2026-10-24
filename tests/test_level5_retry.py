from copy import deepcopy
import unittest

from pop2.game_session import GameResources, GameSession
from pop2.rebirth import RebirthSnapshot
from pop2.save_game import capture, restore_progress


class LevelFiveCheckpointWorldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resources = GameResources.load()

    def setUp(self):
        self.game = GameSession.load(self.resources, 5)
        self.point = self.game.level.checkpoints[1]

    def checkpoint(self):
        snapshot = RebirthSnapshot.capture(self.point, self.game.combat)
        self.game.checkpoint = snapshot
        return snapshot

    def test_gate_and_button_return_to_checkpoint_state_and_next_press_opens_again(self):
        game = self.game
        snapshot = self.checkpoint()
        source = game.level_map.tile(3, 8, 0)
        game.caverns.plates.push(game.level_map, source)
        game.caverns.plates.foreground[6, 13] = 0x300 | 237
        snapshot.restore_world(game.combat)
        self.assertEqual(game.level_map.tile(6, 3, 1).foreground, 0x300)
        self.assertFalse(game.level_map.tile(3, 8, 0).foreground & 0x2000)
        self.assertEqual(game.caverns.plates.darts.projectiles, [])
        game.caverns.plates.push(game.level_map, game.level_map.tile(3, 8, 0))
        self.assertEqual(game.caverns.plates.active[6, 13], 2)

    def test_bridge_damage_and_banks_restore_without_aliasing_snapshot(self):
        snapshot = self.checkpoint()
        live = self.game.caverns
        for _ in range(2):
            live.bridge.state, live.bridge.counter = 3, 12
            live.bridge.pieces[3] = 2
            live.bridge.planks.append([3, 9])
            live.bridge.wobble[4] = 2
            snapshot.restore_world(self.game.combat)
            self.assertIs(live, self.game.caverns)
            self.assertIs(live, self.game.level_map.caverns)
            self.assertEqual((live.bridge.state, live.bridge.counter, live.bridge.pieces,
                              live.bridge.planks, live.bridge.wobble), (0, 0, {}, [], {}))
        self.assertEqual(snapshot.caverns.bridge.pieces, {})

    def test_changed_world_at_a_later_checkpoint_is_the_new_baseline(self):
        self.game.caverns.plates.foreground[6, 13] = 0x300 | 255
        snapshot = self.checkpoint()
        self.game.caverns.plates.foreground[6, 13] = 0x300
        snapshot.restore_world(self.game.combat)
        self.assertEqual(self.game.level_map.tile(6, 3, 1).foreground & 255, 255)

    def test_native_persistent_globals_survive_but_float_and_old_sound_queues_do_not(self):
        caverns = self.game.caverns
        caverns.potions.float_timer = 100
        caverns.plates.songs.append(120)
        caverns.bridge.songs.append(121)
        snapshot = self.checkpoint()
        caverns.bridge.set_tension(3, 15)
        caverns.potions.flip_timer = 70
        snapshot.restore_world(self.game.combat)
        self.assertEqual((caverns.bridge.tension_level, caverns.bridge.tension), (3, 15))
        self.assertEqual(caverns.potions.flip_timer, 70)
        self.assertEqual(caverns.potions.float_timer, 0)
        self.assertEqual((caverns.plates.songs, caverns.bridge.songs), ([], []))

    def test_checkpoint_mechanisms_roundtrip_through_progress_save(self):
        self.game.caverns.plates.foreground[6, 13] = 0x300 | 255
        self.checkpoint()
        self.game.caverns.bridge.state = 3
        restored, _ = restore_progress(capture(self.game), self.resources)
        self.assertEqual(restored.caverns.bridge.state, 0)
        self.assertEqual(restored.level_map.tile(6, 3, 1).foreground & 255, 255)
        restored.caverns.plates.foreground[6, 13] = 0x300
        restored.checkpoint.restore_world(restored.combat)
        self.assertEqual(restored.level_map.tile(6, 3, 1).foreground & 255, 255)

    def test_old_checkpoints_without_mechanism_field_still_load(self):
        self.checkpoint()
        document = deepcopy(capture(self.game))
        del document['resume']['checkpoint']['fields']['caverns']
        restored, _ = restore_progress(document, self.resources)
        self.assertIsNone(restored.checkpoint.caverns)
        self.assertEqual(restored.level_map.tile(6, 3, 1).foreground & 255, 0)


class LevelFiveRetrySceneTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        self.scene.load_level(5)
        self.scene.peaceful = True
        self.scene.jump_to_room(11, 1, 105, 1)
        RooftopSceneTests.tick(self)
        self.assertIsNotNone(self.scene.checkpoint)

    def test_alt_r_rewinds_bridge_and_gate_before_reentering_checkpoint_room(self):
        from types import SimpleNamespace

        scene = self.scene
        scene.game.caverns.plates.foreground[6, 13] = 0x300 | 255
        scene.game.caverns.bridge.state = 3
        scene.game.caverns.bridge.pieces[3] = 2
        scene.dev_key_press(SimpleNamespace(keysym='r', state=0x20000))
        self.assertEqual((scene.room_id, scene.terrain_motion.row), (11, 1))
        self.assertEqual(scene.game.caverns.bridge.state, 0)
        self.assertEqual(scene.game.caverns.bridge.pieces, {})
        self.assertEqual(scene.level_map.tile(6, 3, 1).foreground & 255, 0)

    def test_old_progress_save_gets_a_retry_baseline_after_world_initialization(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from pop2.save_game import write_save

        scene = self.scene
        document = capture(scene.game)
        del document['resume']['checkpoint']['fields']['caverns']
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'old.pop2save'
            write_save(path, document)
            scene.load_game_from(path)
        self.assertIsNotNone(scene.checkpoint.caverns)
        self.assertTrue(scene.checkpoint.caverns.torches)
        scene.game.caverns.plates.foreground[6, 13] = 0x300 | 255
        scene.game.caverns.bridge.state = 3
        scene.restart_level_now(redraw=False)
        self.assertEqual(scene.game.caverns.bridge.state, 0)
        self.assertEqual(scene.level_map.tile(6, 3, 1).foreground & 255, 0)


if __name__ == '__main__':
    unittest.main()
