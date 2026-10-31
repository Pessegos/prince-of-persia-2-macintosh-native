import random
import struct
import unittest

from pop2.paths import ASSET_DIR


FLAME_INSTALLED = all((ASSET_DIR / name).is_file() for name in (
    'Prince.rsrc', 'FlameSword.rsrc', 'Temple.rsrc', 'temple_level12.json'))
PRINCE_INSTALLED = (ASSET_DIR / 'Prince.rsrc').is_file()


class StepRandom:
    """Rnd stand-in: returns the queued values in order."""

    def __init__(self, *values):
        self.values = list(values)

    def randrange(self, limit):
        value = self.values.pop(0)
        assert 0 <= value < limit
        return value


class FlameSwordPresentationTests(unittest.TestCase):
    def actor(self, current_y=0):
        from types import SimpleNamespace

        return SimpleNamespace(state=SimpleNamespace(current_y=current_y))

    def test_hover_pieces_flicker_through_19_to_22(self):
        # 4:1be4-1c32: counter 0 keeps the piece, -1..-4 show 18 - counter.
        from pop2.flame_sword import FlameSword

        flame, actor = FlameSword(), self.actor()
        shown = []
        for _ in range(11):
            flame.present(actor, 4, StepRandom(4))
            shown.append(flame.piece)
        self.assertEqual(shown, [4, 19, 20, 21, 22, 4, 19, 20, 21, 22, 4])
        # Other pieces neither flicker nor advance the counter.
        flame.flicker = -2
        flame.present(actor, 8, StepRandom())
        self.assertEqual((flame.piece, flame.flicker), (8, -2))

    def test_bob_moves_within_the_native_bands(self):
        # 4:1cce: Y <= floor-4 -> Rnd(1)+1; Y >= floor+4 -> Rnd(1)-4;
        # otherwise Rnd(8)-4. The bob follows the piece actually shown.
        from pop2.flame_sword import FlameSword

        for y, draw, expected in ((-4, 1, -2), (-5, 0, -4), (4, 0, 0), (7, 1, 4),
                                  (0, 0, -4), (3, 8, 7)):
            with self.subTest(y=y):
                flame, actor = FlameSword(), self.actor(y)
                flame.present(actor, 19, StepRandom(draw))
                self.assertEqual(actor.state.current_y, expected)
        flame, actor = FlameSword(flicker=-3), self.actor(0)
        flame.present(actor, 4, StepRandom())  # piece 21: no bob, no Rnd
        self.assertEqual((flame.piece, actor.state.current_y), (21, 0))


@unittest.skipUnless(PRINCE_INSTALLED, 'Imported Prince resources required')
class FlameSwordCombatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pop2.animation_data import sequence_words
        from pop2.combat import GuardSpawn
        from pop2.render_opening import load_resource_file

        cls.prince = load_resource_file('Prince.rsrc')
        cls.sequences = {i: sequence_words(r['data']) for i, r in cls.prince['SEQS'].items()}
        cls.spawn = GuardSpawn.from_level(cls.prince['LEVL'][2000]['data'], 3)

    def encounter(self, player_x=240, sword_x=200):
        from pop2.combat import CombatEncounter, select_sequence
        from pop2.flame_sword import FlameSword
        from pop2.sequence_runtime import SequenceRuntime, SequenceState

        runtime = SequenceRuntime(self.sequences, SequenceState(
            227, action=171, current_x=player_x, target_x=player_x,
            facing=0, actor_type=0, level_kind=2, animation_state=1))
        combat = CombatEncounter(runtime, self.sequences, self.spawn, 408, random.Random(1))
        combat.player.sword_drawn = True
        sword = combat.guard
        sword.state.actor_type = 10
        sword.flame_sword = FlameSword(native_alive=True)
        sword.life = sword.max_life = 6
        sword.sword_drawn = True
        sword.alert_mode = 3
        select_sequence(sword, 227)
        sword.runtime.next_frame()
        sword.state.target_x = sword.state.current_x = sword_x
        return combat

    def test_a_parried_strike_costs_it_a_life_and_pushes_it_back(self):
        # TestStrike 6:5a3c-5a7c -> FlameSwordDecLifePts 4:1c36: SEQS 103,
        # cue 10, the parry cue 239 (6:5ae6) and no SEQS 69.
        c = self.encounter()
        c.guard.state.action = 154
        c.player.state.action = 150
        events = c.resolve_contacts()
        self.assertEqual([(e.kind, e.actor, e.sound) for e in events], [('parry', 'player', 239)])
        self.assertEqual((c.guard.life, c.guard.state.sequence_id), (5, 103))
        self.assertIn(10, c.guard.state.sound_events)
        self.assertEqual((c.player.life, c.player.state.action, c.parry_timer), (3, 161, 4))

    def test_the_parry_window_is_24_to_70(self):
        # 6:5962: 24..70 instead of the ordinary 61..99.
        for gap, parried in ((23, False), (24, True), (70, True), (71, False), (80, False)):
            with self.subTest(gap=gap):
                c = self.encounter(player_x=200 + gap - 21)
                c.guard.state.facing = 1
                c.guard.state.action = 154
                c.player.state.action = 150
                events = c.resolve_contacts()
                self.assertEqual(any(e.kind == 'parry' for e in events), parried)

    def test_its_strike_reaches_from_minus_16_to_61(self):
        # GetCharStrikeRanges 6:5c58: (-16, 61), not the guard's 45..85.
        from pop2.combat import opponent_distance, strike_range

        c = self.encounter()
        self.assertEqual(strike_range(c.guard, c.player), (-16, 61))
        # Opposed, the distance is (Prince X - its X) + 21 when ahead.
        for x, hit in ((183, False), (184, True), (200, True), (240, True), (241, False)):
            with self.subTest(x=x):
                c = self.encounter(player_x=x)
                c.guard.state.facing = 1
                c.player.state.action = 171
                c.guard.state.action = 154
                distance = opponent_distance(c.guard, c.player)
                events = c.resolve_contacts()
                self.assertEqual(any(e.kind == 'hit' for e in events), hit, distance)
                self.assertEqual(distance, x - 200 + (21 if x >= 200 else 0))
                if hit:
                    self.assertEqual(c.player.life, 2)

    def test_the_last_parry_drops_it_for_480_frames(self):
        # 4:1c9e: SEQS 107, SetSkelTimer(480), song 238, ALIVE 0.
        c = self.encounter()
        c.guard.life = 1
        c.guard.state.action = 154
        c.player.state.action = 150
        c.resolve_contacts()
        flame = c.guard.flame_sword
        self.assertEqual((c.guard.life, c.guard.state.sequence_id), (0, 107))
        self.assertEqual((flame.timer, flame.native_alive, flame.song_pending), (480, False, True))
        # AutoCtrl 4:16e8-1704 counts the timer down while it rests.
        for _ in range(20):
            c.advance_guard()
        self.assertEqual(flame.timer, 460)
        self.assertEqual(c.guard.state.action, 213)

    def test_the_prince_never_strikes_it(self):
        # TestStrike 6:590a skips a type-10 defender entirely.
        c = self.encounter(player_x=150, sword_x=210)
        c.player.state.facing = 1
        c.player.state.action = 154
        c.guard.state.action = 171
        self.assertEqual(c.resolve_contacts(), [])
        self.assertEqual(c.guard.life, 6)

    def test_it_never_blocks_and_advances_with_seqs_108(self):
        # Defence 4:1206 skips type 10; DoAdvance 6:1e1c selects SEQS 108.
        from pop2.combat import GuardIntent

        c = self.encounter(player_x=280, sword_x=200)
        c.guard.state.facing = 1
        c.player.state.action = 152
        c._chance = lambda table, guard=None: True
        intent = c.decide_guard_intent()
        self.assertFalse(intent.block)
        c.apply_guard_intent(GuardIntent(advance=True))
        self.assertEqual(c.guard.state.sequence_id, 108)

    def test_its_turn_moves_it_25_pixels_first(self):
        # AnimChar 4:2ca2: AddCharX(25) along the old facing, then the flip.
        from pop2.sequence_runtime import SequenceRuntime, SequenceState

        for actor_type, expected in ((10, 225), (2, 200)):
            state = SequenceState(60, target_x=200, current_x=200, facing=1, actor_type=actor_type)
            runtime = SequenceRuntime({60: (-2, 171)}, state)
            runtime.next_frame()
            self.assertEqual((state.facing, state.target_x), (0, expected))

    def test_its_alert_ignores_gaps(self):
        # CheckAlert 2:704c-7068: a gap limits an ordinary guard (1), not it.
        from types import SimpleNamespace
        from pop2.enemy_alerts import alert_path_mode

        tiles = {4: SimpleNamespace(kind=0, foreground=0), 5: SimpleNamespace(kind=1, foreground=0)}
        tile_at = lambda column: tiles.get(column, SimpleNamespace(kind=1, foreground=0))
        self.assertEqual(alert_path_mode(tile_at, 2, 6, 2), 1)
        self.assertEqual(alert_path_mode(tile_at, 2, 6, 2, floating=True), 3)
        tiles[5] = SimpleNamespace(kind=20, foreground=0)
        self.assertEqual(alert_path_mode(tile_at, 2, 6, 2, floating=True), 0)


@unittest.skipUnless(FLAME_INSTALLED, 'Imported temple scenery and FlameSword.rsrc required')
class LevelTwelveFlameSwordTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.tick(self, count)

    def enter(self, x):
        scene = self.scene
        scene.enter_next_level(12)
        scene.jump_to_room(6, row=0, x=x, facing=1)
        return scene.combat.guards[0]

    def test_native_room_seven_holds_a_resting_flame_sword(self):
        # Raw kind 1 (6:2bca -> actor 10) at X 560 on a floor: SEQS 105,
        # pose 213, no life (InitOpp 6:2b08), not ALIVE (IsDeadPos 4:489c).
        # Before, set 7 skipped it entirely.
        from pop2.coordinates import scene_x

        scene = self.scene
        scene.enter_next_level(12)
        level = scene.game.level.data
        self.assertEqual(struct.unpack_from('>h', level, 0x21a4)[0], 7)
        scene.jump_to_room(6, row=0, x=480, facing=0)
        sword = scene.combat.guards[0]
        flame = sword.flame_sword
        self.assertEqual((sword.state.actor_type, sword.state.sequence_id, sword.state.action),
                         (10, 105, 213))
        self.assertEqual((sword.life, sword.max_life, sword.state.target_x), (0, 6, scene_x(560)))
        self.assertEqual((flame.native_alive, flame.timer), (False, 0))
        self.assertEqual(len(scene.combat.guard_art.frames), 79)

    def test_it_rises_within_five_columns_and_attacks(self):
        # 4:14c6: JumpSeq(106), full life, engaged, alert 3, facing the Prince.
        sword = self.enter(290)
        self.tick(1)
        self.assertEqual((sword.state.sequence_id, sword.life, sword.alert_mode), (106, 6, 3))
        self.assertEqual(sword.state.facing, 0)
        self.assertTrue(sword.flame_sword.native_alive)
        self.tick(30)
        self.assertLess(self.scene.combat.player.life, 3)

    def test_it_rests_while_the_prince_is_six_columns_away(self):
        scene = self.scene
        scene.enter_next_level(12)
        scene.jump_to_room(6, row=0, x=480, facing=0)
        sword = scene.combat.guards[0]
        sword.state.target_x = sword.state.current_x = 30
        self.tick(5)
        self.assertEqual(sword.state.sequence_id, 105)

    def test_the_drawn_sword_uses_its_own_artwork(self):
        # SetupSword 3:0b1c: image set 3, AFRM piece 14 for pose 213.
        sword = self.enter(480)
        scene = self.scene
        scene.render()
        art = scene.combat.guard_art
        bounds = art.bounds(sword.state, 118)
        self.assertGreater(bounds[2] - bounds[0], 40)
        self.assertLess(bounds[3] - bounds[1], 20)

    def test_reentering_the_room_clears_a_resting_timer_only(self):
        # InitOpps keeps a dead record's cursor; after AnimChar IsDeadPos
        # (pose 213) clears its timer (6:2e34-2e4e). Mid-fall the pose is not
        # dead, so the timer survives and PlayerCtrl registers zero HP.
        scene = self.scene
        sword = self.enter(480)
        combat, flame = scene.combat, sword.flame_sword
        sword.state.target_x = sword.state.current_x = 420
        self.tick(2)
        self.assertTrue(flame.native_alive)
        flame.fall(sword)
        sword.runtime.next_frame()
        self.tick(3)
        self.assertEqual(sword.state.sequence_id, 107)
        timer = flame.timer
        combat.enter_room(11, 0)
        combat.enter_room(6, 0)
        self.assertEqual(flame.timer, timer)
        self.tick(1)
        self.assertFalse(flame.native_alive)
        self.assertEqual(flame.timer, timer - 1)
        self.tick(12)
        self.assertEqual(sword.state.action, 213)
        combat.enter_room(11, 0)
        combat.enter_room(6, 0)
        self.assertEqual((flame.timer, flame.native_alive, sword.state.action), (0, False, 213))

    def test_a_saved_game_keeps_the_resting_timer(self):
        from pathlib import Path
        import tempfile
        from pop2.game_session import GameResources
        from pop2.save_game import capture_snapshot, read_snapshot, write_save

        sword = self.enter(480)
        sword.flame_sword.timer = 321
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'flame.pop2save'
            write_save(path, capture_snapshot(self.scene.game))
            restored, _saved = read_snapshot(path, GameResources.load())
        actor = next(actor for actor in restored.combat.guards if actor.flame_sword is not None)
        self.assertEqual((actor.state.actor_type, actor.flame_sword.timer), (10, 321))


if __name__ == '__main__':
    unittest.main()
