import unittest

from pop2.paths import ASSET_DIR


class RuinsActorRuleTests(unittest.TestCase):
    def test_head_frames_and_bite_bounds(self):
        from pop2.ruins_actors import chomp_again, frame_index

        # LoadFrame 4:2a8e: type 8 uses the second set below pose 182.
        self.assertEqual((frame_index(7, 150), frame_index(8, 150), frame_index(8, 182)), (1, 44, 33))
        with self.assertRaises(ValueError):
            frame_index(7, 148)
        # ChompAgain 7:0494 at skill 4 (bounds 2..2): below bites again.
        self.assertTrue(chomp_again(1, 4, 0, lambda _n: 0))
        self.assertFalse(chomp_again(2, 4, 0, lambda _n: 1))
        # Skill 9 (2..4) leaves the middle to Rnd(1); wounds > 30 lower both.
        self.assertTrue(chomp_again(2, 9, 0, lambda _n: 1))
        self.assertFalse(chomp_again(2, 9, 31, lambda _n: 1))


@unittest.skipUnless((ASSET_DIR / 'Prince.rsrc').is_file(), 'Imported game resources required')
class RuinsSpawnTests(unittest.TestCase):
    def test_level_seven_has_eight_heads_and_six_serpents(self):
        # InitOpps 6:2bd2-2c0e and the a5-0x5280 table (Codex's actor probe).
        from collections import Counter
        from pop2.game_session import GameResources
        from pop2.ruins_actors import initial_state, ruins_spawns

        level = GameResources.load().level(7).data
        spawns = [spawn for room in range(32) for spawn in ruins_spawns(level, room)]
        self.assertEqual(Counter(spawn.kind for spawn in spawns), {5: 6, 6: 2, 8: 6})
        self.assertEqual(Counter(spawn.actor_type for spawn in spawns), {7: 6, 8: 2, 11: 6})
        self.assertEqual(sorted({spawn.room + 1 for spawn in spawns}), [2, 3, 7, 9, 10, 20, 22, 24, 29, 31])
        serpents = [spawn for spawn in spawns if spawn.actor_type == 11]
        self.assertEqual(Counter(spawn.room + 1 for spawn in serpents), {3: 2, 20: 1, 29: 2, 31: 1})
        self.assertTrue(all(spawn.sequence_id == 170 for spawn in serpents))
        for spawn in spawns:
            start = initial_state(spawn)
            if spawn.actor_type == 11:
                self.assertIn(start.sequence_id, (170, 175))
                self.assertEqual((start.armed, start.sound), (True, 128))
            else:
                # HeadAddOpponent 7:05f6-0628: column anchor + 47, SEQS 130.
                self.assertEqual((start.sequence_id, start.mode, start.armed), (130, 0, False))
                self.assertEqual(start.x, spawn.column * 51 + 47)

    def test_other_opponent_sets_have_no_ruins_actors(self):
        from pop2.game_session import GameResources
        from pop2.ruins_actors import ruins_spawns

        level = GameResources.load().level(5).data
        self.assertEqual([ruins_spawns(level, room) for room in range(32)], [()] * 32)


if __name__ == '__main__':
    unittest.main()
