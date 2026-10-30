import unittest

from pop2.paths import ASSET_DIR


class RuinsHelperTests(unittest.TestCase):
    def serpent_alert(self, tiles, column, mode=1, facing=0):
        from types import SimpleNamespace
        from pop2.ruins_ai import PrinceView, RuinsCreatures
        from pop2.terrain import Tile

        creatures = RuinsCreatures()
        creatures.column = lambda actor, encounter: 0
        encounter = SimpleNamespace(terrain=SimpleNamespace(
            tile=lambda room, col, row: Tile(tiles.get(col, 1))))
        actor = SimpleNamespace(state=SimpleNamespace(sequence_mode=0), row=1, room=0)
        prince = PrinceView(column, 1, 400, 226, facing, 15, 0, -1, 3, False, 2, mode)
        return creatures.serpent_alert(actor, encounter, prince)

    def test_serpent_alert_stops_at_a_gap_before_a_later_wall(self):
        # 2:70c4 continues only while alert==3, not past a cautious result.
        self.assertEqual(self.serpent_alert({1: 0, 2: 20}, 3), 1)
        self.assertEqual(self.serpent_alert({1: 20, 2: 0}, 3), 0)

    def test_serpent_alert_uses_the_cell_behind_a_hanging_prince(self):
        # 2:6f76-6f98 and DATA a5-0x4b96: left +1 / right -1.
        self.assertEqual(self.serpent_alert({2: 20}, 2), 0)
        self.assertEqual(self.serpent_alert({2: 20}, 2, mode=6), 3)
        self.assertEqual(self.serpent_alert({2: 20}, 1, mode=6, facing=-1), 0)

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
        # DrawOppMeter(-1), 3:4aa0-4aaa, selects the nearest eligible
        # opponent; the first head banked by HeadGetAngry is not its owner.
        from pop2.opponent_selection import nearest_opponent

        candidates = [actor for actor in combat.visible_ruins()
                      if actor.alive and actor.ruins.alert == 3 and actor.ruins.mode != 2]
        self.assertIs(opponent, nearest_opponent(combat.player, candidates))
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
        self.assertNotIn(137, combat.ruins.songs)
        frames = []
        for frame in range(10):
            combat.ruins.songs.clear()
            combat.ruins.advance(combat)
            if 137 in combat.ruins.songs:
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

    def test_the_ruins_play_their_room_ambient_and_count_angry_heads_as_a_fight(self):
        from tests.test_terrain import RooftopSceneTests
        from pop2.environments import environment_for

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(6)
        combat = scene.game.combat
        combat.enter_room(6, 0)
        scene.jump_to_room(6, 0, 330, 1)
        calls = []

        class Audio:
            def ambient(self, room, row, column, fighting=False, alive=True, special=None):
                calls.append((room, row, fighting))

        environment_for(scene).ambient_audio(Audio(), scene.terrain_motion)
        # PlayAmbient 5:4fd0 with bank 4 (LEVL 0x2186) and the room table.
        self.assertEqual(calls, [(6, 0, False)])
        combat.ruins.actors(6)[0].ruins.alert = 3
        environment_for(scene).ambient_audio(Audio(), scene.terrain_motion)
        # OppToFight 6:2392: an angry head (-0x5024 = 3) is a fight.
        self.assertEqual(calls[-1], (6, 0, True))

    def test_the_second_sword_draws_its_own_set(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(7)
        self.assertEqual(scene.game.sword_type, 2)
        # LoadSwordSet 3:5a4e: AFRM 25201 (3:5b3e) and SHPL 1200 (3:5ab6).
        self.assertEqual(scene.sword_set(), 2)
        self.assertIsNot(scene.attachment_frames, scene.ordinary_attachment_frames)
        scene.sequence_state.action = 158  # En garde, sword in hand.
        scene.action = 158
        sprite = scene.sword_sprite()
        self.assertIsNotNone(sprite)
        _kind, index, _dx, _dy = scene.attachment_frames[scene.frames[158].afrm_index]
        self.assertIn(int.from_bytes(scene.resources.prince['SHPL'][1200]['data'][:2], 'big') + index,
                      scene.sword_sprite_cache)
        scene.load_level(6)
        self.assertIs(scene.attachment_frames, scene.ordinary_attachment_frames)

    def test_level_nine_custom_rooms_request_their_songs_on_entry(self):
        from tests.test_terrain import RooftopSceneTests
        from pop2.environments import environment_for

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(9)
        ruins = scene.game.combat.ruins
        environment = environment_for(scene)
        # 7:37d6, the enter hook of CUST kinds 20/21 (native rooms 2 and 16).
        scene.jump_to_room(1, 1, 60, 1)
        environment.entered_room()
        environment.entered_room()
        self.assertEqual(ruins.songs, [185])  # Once (a5-0x4ff8).
        ruins.songs.clear()
        scene.jump_to_room(15, 1, 505, 1)
        environment.entered_room()
        self.assertEqual(ruins.songs, [292])
        scene.jump_to_room(15, 1, 100, 1)
        ruins.songs.clear()
        environment.entered_room()
        self.assertEqual(ruins.songs, [])

    def test_level_eight_throne_vision_gives_the_fathers_sword(self):
        from tests.test_terrain import RooftopSceneTests
        from pop2.environments import environment_for

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(8)
        caverns, ruins = scene.game.caverns, scene.game.combat.ruins
        environment = environment_for(scene)
        # 7:3864-38a2: Throne1 (180) left of column 9, else SeeThron (179) once.
        scene.jump_to_room(8, 1, 60, 1)
        environment.entered_room()
        self.assertEqual(ruins.songs, [180])
        ruins.songs.clear()
        scene.jump_to_room(8, 1, 505, 1)
        environment.entered_room()
        environment.entered_room()
        self.assertEqual(ruins.songs, [179])
        self.assertTrue(caverns.throne_seen)
        ruins.songs.clear()
        # 6:14ec-152a: crouching at the sword collapses the Prince (237)
        # without taking the item; pose 185 wakes him (7:38ca).
        self.assertEqual(scene.level_map.tile(8, 5, 2).kind, 22)
        scene.game.sword_type = 2
        heard = []
        songs = caverns.plates.songs

        class Heard(list):
            def append(self, song):
                heard.append(song)
                super().append(song)

        caverns.plates.songs = Heard(songs)
        ruins.songs = Heard(ruins.songs)
        for x in range(240, 320, 3):
            scene.jump_to_room(8, 2, x, 1)
            scene.shift_held = scene.down_held = True
            for _ in range(10):
                RooftopSceneTests.tick(self)
                if scene.sequence_state.selected_sequence_id == 237:
                    break
            scene.shift_held = scene.down_held = False
            if scene.sequence_state.selected_sequence_id == 237:
                break
        self.assertEqual(scene.sequence_state.selected_sequence_id, 237)
        self.assertEqual(heard, [181])
        self.assertEqual(scene.level_map.tile(8, 5, 2).kind, 22)
        scene.combat.player.life = 1
        # At pose 185 the vision (NIS 6) plays; the Prince wakes after it.
        visions = []
        scene.start_vision = lambda wake: visions.append(wake) or True
        for _ in range(200):
            RooftopSceneTests.tick(self)
            if visions:
                break
        self.assertEqual(len(visions), 1)
        self.assertEqual(scene.sequence_state.action, 185)
        self.assertFalse(caverns.throne_done)
        visions[0]()
        self.assertTrue(caverns.throne_done)
        self.assertEqual(scene.sequence_state.selected_sequence_id, 231)
        self.assertEqual(scene.sequence_state.facing, 1)
        self.assertEqual(scene.game.sword_type, 1)
        self.assertEqual(scene.combat.player.life, scene.combat.player.max_life)
        self.assertEqual(heard, [181, 182])
        # Once over, the throne hook is silent and the sword is an item.
        environment.entered_room()
        self.assertEqual(heard, [181, 182])

    def test_presses_during_the_throne_wake_wait_for_the_standing_gate(self):
        # SEQS 237/231 are mode 1; GenCtrl's 6:0b5a branch for 179-183 and
        # IsDeadPos 185 touches no latch for the Prince. The vision's
        # ClearControls (7:39ca) discards presses made during the collapse;
        # a press during the wake waits for SEQS 2's pose 15 (6:05fe). The
        # previous code had no bank there and dropped both.
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene

        def press(key, release=True):
            if key in ('up', 'down'):
                scene.set_key_state(key, True)
                if release:
                    scene.set_key_state(key, False)
            else:
                scene.horizontal_key(None, key, True)
                if release:
                    scene.horizontal_key(None, key, False)

        def run(phase, key, release=True):
            scene.load_level(8)
            scene.directional_input = None
            for x in range(240, 320, 3):
                scene.jump_to_room(8, 2, x, 1)
                scene.shift_held = scene.down_held = True
                for _ in range(10):
                    RooftopSceneTests.tick(self)
                    if scene.sequence_state.selected_sequence_id == 237:
                        break
                scene.shift_held = scene.down_held = False
                if scene.sequence_state.selected_sequence_id == 237:
                    break
            self.assertEqual(scene.sequence_state.selected_sequence_id, 237)
            visions = []
            scene.start_vision = lambda wake: visions.append(wake) or True
            for _ in range(200):
                if phase == 'collapse' and scene.action == 181 and key is not None:
                    press(key, release)
                    key = None
                RooftopSceneTests.tick(self)
                if visions:
                    break
            visions[0]()
            sequences = []
            for _ in range(40):
                if phase == 'wake' and scene.action == 182 and key is not None:
                    press(key, release)
                    key = None
                RooftopSceneTests.tick(self)
                sequence = scene.sequence_state.sequence_id
                if sequence != (sequences[-1] if sequences else None):
                    sequences.append(sequence)
            for name in ('up', 'down'):
                scene.set_key_state(name, False)
            scene.held_directions.clear()
            return sequences

        # The wake faces right: Backward is Left (turn, SEQS 5).
        for phase, key, release, first in (
                ('wake', 'up', True, 28), ('wake', -1, True, 5), ('wake', 1, True, 1),
                ('collapse', 'up', True, 2), ('collapse', -1, True, 2),
                ('collapse', 'up', False, 28)):
            with self.subTest(phase=phase, key=key, release=release):
                sequences = run(phase, key, release)
                self.assertEqual(sequences[0], 231)
                self.assertEqual(sequences[1], first)
                if first == 2:
                    self.assertEqual(sequences, [231, 2])


if __name__ == '__main__':
    unittest.main()
