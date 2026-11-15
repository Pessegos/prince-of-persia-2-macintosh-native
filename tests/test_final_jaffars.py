"""CODE 9 copy generation and its original level-14 record bank."""

import random
import struct
import unittest

from pop2.final_jaffars import JaffarSpawn, dead_copy_step, drop_foreground, next_jaffar_spawn
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
    def test_first_copy_takes_the_other_row_and_a_column_and_life_draw(self):
        # 9:0202 pushes the row (d6) and then the column (d3): 9:03c8 reads
        # the column first. Life is Rnd(2) + 3, inclusive.
        for player_row, row, base in ((2, 1, 4), (0, 2, 2), (1, 2, 2)):
            for boost in (0, 1):
                for life_roll in (0, 1, 2):
                    rng = FixedRandom(boost, life_roll)
                    column = base + 4 * boost
                    spawn = next_jaffar_spawn(0, 2, 0, player_row, rng)
                    self.assertEqual(spawn, JaffarSpawn(row * 10 + column, column, row,
                                                        3 + life_roll))
                    self.assertEqual(rng.calls, [2, 3])
                    self.assertEqual((spawn.native_x, spawn.facing_right),
                                     (207 + 51 * column, column < 5))

    def test_the_old_reading_of_rows_four_to_eight_is_rejected(self):
        spawn = next_jaffar_spawn(0, 2, 0, 2, FixedRandom(1, 0))
        self.assertEqual((spawn.cell, spawn.row, spawn.column), (18, 1, 8))
        self.assertLess(spawn.row, 3)
        self.assertFalse(spawn.facing_right)

    def test_second_copy_checks_sequence_row_and_one_in_twenty_one_gate(self):
        for sequence, first_row, player_row, expected_calls in (
                (238, 1, 0, []), (2, 1, 2, []), (2, 2, 1, []),
                (2, 1, 1, [21]), (2, 2, 2, [21])):
            rng = FixedRandom(1)
            self.assertIsNone(next_jaffar_spawn(1, sequence, first_row, player_row, rng))
            self.assertEqual(rng.calls, expected_calls)
        rng = FixedRandom(0, 1, 0)
        self.assertEqual(next_jaffar_spawn(1, 2, 2, 2, rng), JaffarSpawn(18, 8, 1, 3))
        self.assertEqual(rng.calls, [21, 2, 3])

    def test_two_copies_are_the_limit_without_rng_use(self):
        rng = FixedRandom()
        self.assertIsNone(next_jaffar_spawn(2, 2, 0, 0, rng))
        self.assertEqual(rng.calls, [])


class DeadCopyTests(unittest.TestCase):
    def test_alive_six_draws_and_drops_on_floor_only(self):
        for roll, kind, objects, cell_row, column, drop in (
                (1, 1, 0, 2, 5, 1), (2, 1, 3, 1, 4, 2), (0, 1, 0, 2, 5, 0),
                (2, 0, 0, 2, 5, 0), (2, 10, 0, 2, 5, 0), (1, 1, 4, 2, 5, 0),
                (1, 1, 0, 2, 2, 0), (1, 1, 0, 2, 4, 0), (1, 1, 0, 2, 1, 1)):
            rng = FixedRandom(roll)
            step = dead_copy_step(6, True, 0, kind, objects, cell_row, column, rng)
            self.assertEqual(rng.calls, [3])
            self.assertEqual((step.alive, step.drop, step.vanish), (7, drop, False))
            self.assertEqual(step.cell, cell_row * 10 + column if drop else 0)
        self.assertEqual(drop_foreground(2), 0x4040)

    def test_count_runs_on_once_the_cue_is_consumed_and_shimmers_at_ninety_six(self):
        rng = FixedRandom()
        self.assertEqual(dead_copy_step(5, False, 0, 1, 0, 2, 5, rng).alive, 5)
        self.assertEqual(dead_copy_step(7, True, 0, 1, 0, 2, 5, rng).alive, 7)
        self.assertEqual(dead_copy_step(7, False, 0, 1, 0, 2, 5, rng).alive, 8)
        step = dead_copy_step(96, False, 0, 1, 0, 2, 5, rng)
        self.assertEqual((step.alive, step.vanish), (98, True))
        self.assertEqual(dead_copy_step(98, False, 239, 1, 0, 2, 5, rng),
                         dead_copy_step(98, False, 239, 1, 0, 2, 5, rng))
        self.assertFalse(dead_copy_step(98, False, 239, 1, 0, 2, 5, rng).vanish)
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
                         (14, 1, 204, 1, 238, 230, 5, 3))
        self.assertEqual(len(game.combat.guards), 1)
        game.combat.enter_room(0, 1)
        game.combat.enter_room(2, 2)
        self.assertIs(game.combat.guards[0], first)
        self.assertEqual(first.guard_record.cell, 14)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'copies.pop2save'
            write_save(path, capture_snapshot(game))
            restored, _ = read_snapshot(path, self.resources)
        copy = restored.combat.guards[0]
        self.assertEqual((copy.final_jaffar, copy.guard_record.cell, copy.row,
                          copy.state.source_sequence_id), (True, 14, 1, 238))

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
        self.assertEqual([actor.guard_record.cell for actor in game.combat.guards], [22, 14])
        # Native X 309 and 411 face right; SEQS 238's -5 -1 has stepped the
        # first one a pixel back.
        self.assertEqual([(actor.row, actor.state.target_x, actor.state.facing)
                          for actor in game.combat.guards], [(2, 101, 1), (1, 204, 1)])
        self.assertEqual(rng.calls, [2, 3, 21, 2, 3])
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
        # The copy is born on row 1; a second one would need the Prince
        # off row 2.
        self.assertEqual([actor.guard_record.cell for actor in game.combat.guards], [14])
        self.assertTrue(all(actor.final_jaffar for actor in game.combat.guards))


if __name__ == '__main__':
    unittest.main()
