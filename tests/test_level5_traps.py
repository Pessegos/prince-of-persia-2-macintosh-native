import unittest

from pop2.audio import AudioEngine
from pop2.darts import Dart
from tests.test_audio import TimedPlayback


class LevelFiveTrapSceneTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        self.scene.load_level(5)
        self.scene.peaceful = True

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.tick(self, count)

    def test_room_four_right_button_fires_right_shooter_and_projectile_can_hit_prince(self):
        scene = self.scene
        scene.jump_to_room(3, 0, 445, 1)
        self.tick()
        self.assertEqual(scene.game.caverns.plates.darts.projectiles, [Dart(3, 346, 95, 0)])
        self.assertIn(65, scene.sequence_state.sound_events)
        life = scene.combat.player.life
        self.tick(4)
        self.assertLess(scene.combat.player.life, life)

    def test_room_four_left_button_fires_independently(self):
        scene = self.scene
        scene.jump_to_room(3, 0, 285, 1)
        self.tick()
        self.assertIn(Dart(3, 91, 95, 0), scene.game.caverns.plates.darts.projectiles)
        self.assertIn(65, scene.sequence_state.sound_events)

    def test_room_nine_right_debris_impact_plays_one_impact_and_still_spawns_projectile(self):
        scene = self.scene
        scene.god_mode = True
        scene.jump_to_room(8, 1, 310, 0)
        caverns = scene.game.caverns
        caverns.loose.trigger(scene.level_map.tile(8, 6, 1), force=True)
        scene.audio = None
        impact = []
        for _ in range(10):
            scene.sequence_state.sound_events.clear()
            self.tick()
            if 26 in scene.sequence_state.sound_events:
                impact = list(scene.sequence_state.sound_events)
                break
        self.assertIn(26, impact)
        self.assertIn(65, impact)
        self.assertEqual(caverns.plates.timer(scene.level_map, 67), 31)
        audio = AudioEngine(playback=object())
        audio.playback = TimedPlayback(audio.cues)
        audio.drain(scene.sequence_state)
        audio.flush()
        self.assertIn(26, audio.playback.playing_effects())
        self.assertNotIn(65, audio.playback.playing_effects())


if __name__ == '__main__':
    unittest.main()
