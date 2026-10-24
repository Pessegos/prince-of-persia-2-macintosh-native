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

        state = SequenceState(1, actor_type=7)
        SequenceRuntime({1: (-9, 5, -6, -9, 30, 0, 160, -1, 1)}, state).next_frame()
        # AnimChar 4:2cd6: additive, horizontal capped at 24.
        self.assertEqual((state.horizontal_velocity, state.vertical_velocity), (24, -6))
        sequences = {1: (160, -22, 5, 2, 3, 161), 2: (170, 171, 172, -1, 2), 3: (180, 181, 182, -1, 3)}
        for value, pose in ((1, 171), (0, 181)):
            state = SequenceState(1, actor_type=7)
            runtime = SequenceRuntime(sequences, state)
            runtime.rng = Fixed(value)
            self.assertEqual(runtime.next_frame().action, 160)
            # 4:2df8 selects the new sequence but this frame still reads the
            # old handle from cursor 0 (the probe found this quirk).
            self.assertEqual((runtime.next_frame().action, state.sequence_id), (160, 3 - value))
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

    def test_heads_bite_in_play_and_a_sword_hit_sends_them_back(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(6)
        combat = scene.game.combat
        combat.enter_room(6, 0)
        scene.jump_to_room(6, 0, 150, 1)
        self.assertEqual(len(combat.visible_ruins()), 2)
        RooftopSceneTests.tick(self, 60)
        # A head reaches the unarmed Prince and bites (CheckStab, damage 1).
        self.assertLess(combat.player.life, 3)
        head = combat.ruins.actors(6)[0]
        head.life = 3
        combat.ruins.stab(head, combat, 1)
        # Sword type 1 does 2 damage; a survivor is knocked back (SEQS 153).
        self.assertEqual((head.life, head.state.source_sequence_id), (1, 153))
        combat.ruins.stab(head, combat, 1)
        self.assertEqual((head.alive, head.state.source_sequence_id), (False, 154))
        # SEQS 154 ends with -17 (removal); a wall on the way back sends a
        # dead head through 164/145 first (HeadEnemyCollide), which is longer.
        for _ in range(120):
            RooftopSceneTests.tick(self, 1)
            if head.ruins.removed:
                break
        self.assertTrue(head.ruins.removed)
        self.assertNotIn(head, combat.visible_ruins())

    def test_the_low_strike_kills_a_facing_serpent(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(6)
        combat = scene.game.combat
        combat.enter_room(19, 2)
        scene.jump_to_room(19, 2, 270, 0)
        serpent = combat.visible_ruins()[0]
        scene.sword_drawn = combat.player.sword_drawn = True
        scene.start_sword_action('sword_attack')
        # DoStrike 6:27d8: against a serpent the strike is SEQS 96.
        self.assertEqual(scene.sequence_state.source_sequence_id, 96)
        RooftopSceneTests.tick(self, 6)
        # 100 damage (CheckStab 6:52a0) and the serpent's death, SEQS 174.
        self.assertEqual((serpent.alive, serpent.state.source_sequence_id), (False, 174))
        scene.start_sword_action('sword_attack')
        self.assertEqual(scene.sequence_state.source_sequence_id, 75)

    def test_an_angry_head_shows_its_life_meter(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(6)
        combat = scene.game.combat
        combat.enter_room(6, 0)
        scene.jump_to_room(6, 0, 150, 1)
        self.assertIsNone(combat.health_opponent())
        for _ in range(100):
            RooftopSceneTests.tick(self, 1)
            if combat.ruins.banked is not None:
                break
        opponent = combat.health_opponent()
        self.assertIsNotNone(opponent)
        self.assertIs(opponent, combat.ruins.banked)
        self.assertEqual(opponent.ruins.mode in (1, 3), True)

    def test_killed_heads_stay_dead_through_rebirth_and_saves(self):
        import tempfile
        from pathlib import Path
        from pop2.game_session import GameResources, GameSession
        from pop2.rebirth import RebirthSnapshot
        from pop2.save_game import capture, read_save, write_save

        resources = GameResources.load()
        # Level seven's native room 22 has two heads; the level has a checkpoint.
        game = GameSession.load(resources, 7)
        combat = game.combat
        combat.enter_room(21, 0)
        first, second = combat.ruins.actors(21)
        first.life, first.ruins.removed = 0, True
        game.checkpoint = RebirthSnapshot.capture(game.level.checkpoints[0], combat)
        game.checkpoint.restore_world(combat)
        combat.enter_room(21, 0)
        restored = combat.ruins.actors(21)
        self.assertEqual([actor.ruins.removed for actor in restored], [True, False])
        self.assertEqual(restored[1].state.source_sequence_id, 130)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ruins.pop2save'
            write_save(path, capture(game))
            loaded, _saved = read_save(path, resources)
        loaded.combat.enter_room(21, 0)
        self.assertEqual([actor.ruins.removed for actor in loaded.combat.ruins.actors(21)],
                         [True, False])

    def test_a_biting_head_is_drawn_on_the_princes_neck(self):
        from dataclasses import replace
        from tests.test_terrain import RooftopSceneTests
        from pop2.combat import actor_frame_index
        from pop2.terrain import floor_y

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(7)
        combat = scene.game.combat
        combat.enter_room(21, 0)
        scene.jump_to_room(21, 0, 250, 1)
        for _ in range(300):
            RooftopSceneTests.tick(self, 1)
            heads = [head for head in combat.ruins.actors(21) if head.ruins.neck]
            if heads:
                break
        self.assertTrue(heads)
        head = heads[0]
        # AlignHeadOnKidNeck 7:0006: the working X is the drawing X.
        self.assertEqual(head.state.target_x, head.ruins.neck[0])
        record = scene.guard_art.frames[actor_frame_index(head.state)]
        shift = record.offset_x if head.state.facing else -record.offset_x
        ground = floor_y(head.row)
        drawn = replace(head.state, target_x=head.ruins.neck[0] - shift,
                        current_y=head.ruins.neck[1] - ground - record.offset_y)
        left, top, right, bottom = scene.guard_art.bounds(drawn, ground)
        prince = scene.player_bounds()
        self.assertTrue(left <= prince[2] and prince[0] <= right)
        self.assertTrue(prince[1] - 40 <= bottom <= prince[1] + 40)
        scene.render()

    def test_the_development_map_shows_heads_and_serpents(self):
        from pop2.development_map import map_enemies
        from pop2.game_session import GameResources

        level = GameResources.load().level(6)
        art, actors = map_enemies(level, {room: (room, 0) for room in range(32)})
        # Level six: heads in native rooms 4, 7 and 16, serpents in 20 and 25.
        self.assertEqual(sorted(room + 1 for room in actors), [4, 7, 16, 20, 25])
        self.assertEqual(len(art.frames), 141)
        self.assertEqual({actor.state.actor_type for room in actors.values() for actor in room}, {7, 11})

    def test_the_head_kill_song_waits_for_the_death_count(self):
        from pop2.game_session import GameResources, GameSession

        combat = GameSession.load(GameResources.load(), 6).combat
        combat.enter_room(3, 0)
        combat.player.room = 3
        head = combat.ruins.actors(3)[0]
        head.life = 1
        combat.ruins.stab(head, combat, 1)
        self.assertNotIn(137, head.state.sound_events)
        frames = []
        for frame in range(10):
            head.state.sound_events.clear()
            combat.ruins.advance(combat)
            if 137 in head.state.sound_events:
                frames.append(frame)
        # 4:3d24: registration, six counted frames, then 5:4bb8 once.
        self.assertEqual(frames, [7])

    def test_alerts_and_the_drawn_prince_are_taken_before_he_moves(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(6)
        combat = scene.game.combat
        combat.enter_room(19, 2)
        scene.jump_to_room(19, 2, 270, 0)
        calls = []
        original = combat.ruins.before_prince
        combat.ruins.before_prince = lambda encounter: (calls.append(encounter.player.state.target_x),
                                                         original(encounter))
        RooftopSceneTests.tick(self, 1)
        # Ruins.frame_start (FrameAdv step 4) ran before the controls.
        self.assertEqual(calls, [270])
        self.assertEqual(combat.ruins.prince_drawn[0], 19)
        self.assertFalse(combat.ruins.alerts_ready)


if __name__ == '__main__':
    unittest.main()
