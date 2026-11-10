"""CODE 9 copy generation and its original level-14 record bank."""

import random
import struct
import unittest

from pop2.final_jaffars import JaffarSpawn, next_jaffar_spawn
from pop2.paths import ASSET_DIR


class FixedRandom:
    def __init__(self, *values):
        self.values = iter(values)
        self.calls = []

    def randrange(self, stop):
        self.calls.append(stop)
        value = next(self.values)
        assert value < stop
        return value


class JaffarRulesTests(unittest.TestCase):
    def test_first_copy_uses_opposite_column_and_independent_row_and_life_draws(self):
        for player_row, column, base_row in ((2, 1, 4), (0, 2, 2), (1, 2, 2)):
            for boost in (0, 1):
                for life_roll in (0, 1):
                    rng = FixedRandom(boost, life_roll)
                    self.assertEqual(next_jaffar_spawn(0, 2, 0, player_row, rng),
                                     JaffarSpawn((base_row + 4 * boost) * 10 + column,
                                                 column, base_row + 4 * boost, 3 + life_roll))
                    self.assertEqual(rng.calls, [2, 2])

    def test_second_copy_checks_sequence_column_and_one_in_twenty_one_gate(self):
        for sequence, first_row, player_row, expected_calls in (
                (238, 0, 2, []), (2, 1, 2, []), (2, 0, 1, []),
                (2, 1, 1, [21]), (2, 0, 2, [21])):
            rng = FixedRandom(1)
            self.assertIsNone(next_jaffar_spawn(1, sequence, first_row, player_row, rng))
            self.assertEqual(rng.calls, expected_calls)
        rng = FixedRandom(0, 1, 0)
        self.assertEqual(next_jaffar_spawn(1, 2, 1, 1, rng),
                         JaffarSpawn(62, 2, 6, 3))
        self.assertEqual(rng.calls, [21, 2, 2])

    def test_two_copies_are_the_limit_without_rng_use(self):
        rng = FixedRandom()
        self.assertIsNone(next_jaffar_spawn(2, 2, 0, 0, rng))
        self.assertEqual(rng.calls, [])


@unittest.skipUnless((ASSET_DIR / 'Prince.rsrc').is_file(), 'Imported original Prince resource required')
class OriginalFinalLevelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pop2.game_session import GameResources

        cls.resources = GameResources.load()

    def test_original_room_three_has_empty_copy_bank_and_sequence(self):
        level = self.resources.level(14).data
        self.assertEqual((len(level), struct.unpack_from('>3H', level, 0x2186)[0],
                          struct.unpack_from('>H', level, 0x218a)[0]),
                         (18890, 6, 14))
        self.assertEqual(struct.unpack_from('>H', level, 0x2326)[0], 0)
        self.assertEqual(self.resources.sequences[238][:4], (-7, 1, 230, 231))

    def test_generated_copy_stays_in_room_three_bank_and_survives_save(self):
        from pathlib import Path
        import tempfile
        from pop2.game_session import GameSession
        from pop2.save_game import capture_snapshot, read_snapshot, write_save

        game = GameSession.load(self.resources, 14)
        game.place(2, 2, 200, 0)
        game.runtime.state.sequence_mode = 13
        game.combat.rng = random.Random(1)
        game.combat.generate_opponents()
        first = game.combat.guards[0]
        self.assertTrue(first.final_jaffar)
        self.assertEqual((first.guard_record.cell, first.row, first.state.target_x,
                          first.state.facing, first.state.source_sequence_id,
                          first.state.action, first.skill, first.palette_variant),
                         (41, 4, 51, 0, 238, 230, 5, 3))
        self.assertEqual(len(game.combat.guards), 1)
        game.combat.enter_room(0, 1)
        game.combat.enter_room(2, 2)
        self.assertIs(game.combat.guards[0], first)
        self.assertEqual(first.guard_record.cell, 41)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'copies.pop2save'
            write_save(path, capture_snapshot(game))
            restored, _ = read_snapshot(path, self.resources)
        copy = restored.combat.guards[0]
        self.assertEqual((copy.final_jaffar, copy.guard_record.cell, copy.row,
                          copy.state.source_sequence_id), (True, 41, 4, 238))

    def test_two_copies_enter_the_bank_with_the_original_visible_guard_frame(self):
        from pop2.animation_data import parse_frame_records, shape_id_for_action
        from pop2.game_session import GameSession
        from pop2.render_opening import decode_ctbl, decode_shap, load_resource_file

        game = GameSession.load(self.resources, 14)
        game.place(2, 1, 200, 1)
        rng = FixedRandom(0, 0, 0, 0, 0)
        game.combat.rng = rng
        game.combat.generate_opponents()
        self.assertEqual((game.combat.guards[0].guard_record.cell,
                          game.combat.guards[0].row), (22, 2))
        game.combat.generate_opponents()
        self.assertEqual(len(game.combat.guards), 1)
        # The first copy's selected SEQS 238 blocks another birth. AnimChar
        # clears that selected ID only after the appearance sequence ends.
        for _ in range(3):
            game.combat.advance_guard()
        visible = game.combat.visible_guards()
        self.assertEqual((len(visible), visible[0].state.action), (1, 233))
        for _ in range(9):
            game.combat.advance_guard()
        self.assertEqual(game.combat.guards[0].state.source_sequence_id, 0)
        game.combat.player.row = 2
        game.combat.generate_opponents()
        self.assertEqual([actor.guard_record.cell for actor in game.combat.guards], [22, 41])
        self.assertEqual(rng.calls, [2, 2, 21, 2, 2])
        game.combat.generate_opponents()
        self.assertEqual(len(game.combat.guards), 2)
        guard_resource = load_resource_file('Guard.rsrc')
        frames = parse_frame_records(guard_resource['FRAM'][750]['data'])
        base = int.from_bytes(guard_resource['SHPL'][750]['data'][:2], 'big')
        shape_id = shape_id_for_action(frames, base, 233 - 149)
        self.assertEqual(shape_id, 782)
        sprite = decode_shap(guard_resource['SHAP'][shape_id]['data'],
                             decode_ctbl(guard_resource['CTBL'][752]['data']))
        self.assertEqual(sprite.size, (23, 80))
        self.assertIsNotNone(sprite.getbbox())

    def test_room_three_frame_cycle_runs_bounded_copies(self):
        from pop2.game_session import GameSession

        game = GameSession.load(self.resources, 14)
        game.place(2, 2, 200, 0)
        game.combat.player.state.sequence_mode = 13
        game.combat.rng = random.Random(1)
        for frame in range(25):
            game.combat.step(frame / 12, 1 / 12)
        self.assertEqual([actor.guard_record.cell for actor in game.combat.guards], [41, 81])
        self.assertTrue(all(actor.final_jaffar for actor in game.combat.guards))


if __name__ == '__main__':
    unittest.main()
