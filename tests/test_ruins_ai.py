import unittest

from pop2.paths import ASSET_DIR


class RuinsHelperTests(unittest.TestCase):
    def test_native_cell_windows_and_rows(self):
        from pop2.ruins_ai import character_row, signed_remainder, x_within_middle, y_within_middle

        # 19:4bd0 keeps the dividend's sign, unlike Python's modulo.
        self.assertEqual((signed_remainder(-7, 51), signed_remainder(58, 51)), (-7, 7))
        # 7:1768 at a head's rest X (anchor + 47) and 7:17c8 at its floor.
        self.assertTrue(x_within_middle(207 + 51 + 47, 12))
        self.assertFalse(x_within_middle(207 + 51 + 47 + 20, 12))
        self.assertTrue(y_within_middle(73, 30))
        # GetRow 4:3afa subtracts 5 and steps below zero.
        self.assertEqual((character_row(73), character_row(193), character_row(5)), (0, 1, -1))

    def test_serpent_passable_cells(self):
        from pop2.ruins_ai import serpent_passable
        from pop2.terrain import Tile

        self.assertTrue(serpent_passable(Tile(1)))
        self.assertFalse(serpent_passable(Tile(4, 0x40)))
        self.assertTrue(serpent_passable(Tile(4, 0x80)))
        self.assertTrue(serpent_passable(Tile(7, 0x80)))
        self.assertFalse(serpent_passable(Tile(7)))
        self.assertFalse(serpent_passable(Tile(0)))

    def test_head_velocity_and_random_branch_opcodes(self):
        from pop2.sequence_runtime import SequenceRuntime, SequenceState

        class Fixed:
            def __init__(self, value):
                self.value = value

            def randrange(self, stop):
                return self.value % stop

        sequences = {1: (-9, 5, -6, -9, 30, 0, 160, -22, 5, 2, 3, 161), 2: (162, -1, 2), 3: (163, -1, 3)}
        for value, pose in ((1, 162), (0, 163)):
            state = SequenceState(1, actor_type=7)
            runtime = SequenceRuntime(sequences, state)
            runtime.rng = Fixed(value)
            runtime.next_frame()
            # AnimChar 4:2cd6: additive, horizontal capped at 24.
            self.assertEqual((state.horizontal_velocity, state.vertical_velocity), (24, -6))
            self.assertEqual(runtime.next_frame().action, pose)


@unittest.skipUnless((ASSET_DIR / 'Head.rsrc').is_file(), 'Imported game resources required')
class RuinsControllerTests(unittest.TestCase):
    def test_level_six_heads_attack_and_serpents_move_headlessly(self):
        from tests.test_terrain import RooftopSceneTests
        from pop2.ruins_ai import RuinsCreatures

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(6)
        combat = scene.game.combat
        creatures = RuinsCreatures()
        seen = set()
        for room in range(32):
            creatures.load_room(combat, room)
            if not creatures.actors(room):
                continue
            scene.jump_to_room(room, 1, 200, 1)
            combat.player.room = room
            for _ in range(300):
                creatures.advance(combat)
                seen.update((actor.ruins.actor_type, actor.state.source_sequence_id)
                            for actor in creatures.actors(room))
        # Angry (140), swoop (147), bite (150/151) and shaken off (152).
        self.assertTrue({(7, 140), (7, 147), (7, 152)} <= seen)
        self.assertTrue({(7, 150), (7, 151)} & seen)
        self.assertIn((11, 170), seen)


if __name__ == '__main__':
    unittest.main()
