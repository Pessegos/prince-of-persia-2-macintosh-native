import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

from pop2.cavern_state import CavernState
from pop2.caverns import _cavern_assets, cavern_assets, cavern_room
from pop2.game_session import GameResources, GameSession
from pop2.level_data import LevelDefinition
from pop2.level_rendering import LevelRenderer
from pop2.paths import ASSET_DIR
from pop2.render_opening import load_resource_file


class CavernLevelIsolationTests(unittest.TestCase):
    def test_program_and_decoded_sprite_caches_are_separate_and_default_means_level_three(self):
        _cavern_assets.cache_clear()
        self.addCleanup(_cavern_assets.cache_clear)
        with TemporaryDirectory() as directory:
            directory = Path(directory)
            for number, name in ((3, 'caverns_entry.json'), (4, 'caverns_level4.json')):
                (directory / name).write_text(json.dumps({'level': number}), encoding='ascii')
            with (patch('pop2.caverns.ASSET_DIR', directory),
                  patch('pop2.caverns.load_resource_file', return_value={'CTBL': {3500: {'data': b''}}}),
                  patch('pop2.caverns.decode_ctbl', return_value={})):
                three, four = cavern_assets(), cavern_assets(4)
                self.assertIs(cavern_assets(3), three)
                self.assertIs(cavern_assets(4), four)
                three[3]['sentinel'] = object()
                self.assertNotIn('sentinel', four[3])
                self.assertEqual((three[0]['level'], four[0]['level']), (3, 4))

    def test_export_identity_is_checked_before_drawing(self):
        _cavern_assets.cache_clear()
        self.addCleanup(_cavern_assets.cache_clear)
        with TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / 'caverns_level4.json').write_text('{"level": 3}', encoding='ascii')
            with (patch('pop2.caverns.ASSET_DIR', directory),
                  self.assertRaisesRegex(ValueError, 'different level')):
                cavern_assets(4)
        for number in (True, 2, 10, '4'):
            with self.subTest(number=number), self.assertRaisesRegex(ValueError, 'Unsupported cavern'):
                cavern_assets(number)

    def test_level_four_artwork_uses_its_own_level_and_skips_unapproved_rooms(self):
        from pop2.cavern_retouch import retouched_sprite

        program = {'version': 14, 'level': 4, 'rooms': {'0': [['back', 3501, 0, 1, 16, 0]]}}
        sprite = Image.new('RGBA', (1, 1), 'red')
        with (patch('pop2.caverns.cavern_assets', return_value=(program, {}, {}, {3501: sprite})),
              patch('pop2.cavern_retouch.retouch_assets', side_effect=AssertionError('Unapproved room')),
              patch('pop2.caverns.retouched_sprite', wraps=retouched_sprite) as retouch):
            room = cavern_room(0, retouched=True, level_number=4)
        self.assertEqual(room.background.getpixel((0, 0)), (255, 0, 0, 255))
        self.assertEqual(retouch.call_args.kwargs, {'level_number': 4})

    def test_renderer_routes_static_and_animated_drawing_to_the_selected_level(self):
        program = {'torches': {}}
        level = SimpleNamespace(number=4, kind=3, start_room=0, data=b'')
        with patch('pop2.caverns.cavern_assets', return_value=(program, None, None, None)) as assets:
            renderer = LevelRenderer(level, preload_room=False)
            # Menus build renderers for every level; the export loads on first use.
            assets.assert_not_called()
            self.assertIs(renderer.cavern_program, program)
            assets.assert_called_once_with(4)
        room = object()
        with (patch('pop2.caverns.cavern_assets', return_value=(program, None, None, None)),
              patch('pop2.caverns.cavern_room', return_value=room) as draw):
            self.assertIs(renderer.room(0), room)
            self.assertEqual(draw.call_args.kwargs['level_number'], 4)
        renderer.cavern_map = object()
        frame = Image.new('RGBA', (1, 1))
        with (patch('pop2.caverns.draw_cavern_flasks', return_value=frame) as flasks,
              patch('pop2.caverns.draw_cavern_spikes', return_value=frame) as spikes):
            renderer.animated_layer(frame, 0, None, front=True, caverns=CavernState())
            self.assertEqual(flasks.call_args.kwargs['level_number'], 4)
            self.assertEqual(spikes.call_args.kwargs['level_number'], 4)


@unittest.skipUnless((ASSET_DIR / 'caverns_level4.json').is_file(), 'Imported level-four resources required')
class LevelFourSceneryTests(unittest.TestCase):
    def test_level_four_session_restarts_its_own_cavern_world_and_entry(self):
        game = GameSession.load(GameResources.load(), 4)
        self.assertIsNone(game.opening)
        self.assertIsNone(game.harbor)
        self.assertIsNotNone(game.caverns)
        self.assertEqual((game.runtime.state.source_sequence_id, game.motion.room, game.motion.row),
                         (5, 0, 2))
        old = game.caverns
        game.place(16, 1, 270, 1)
        game.restart()
        self.assertIsNot(game.caverns, old)
        self.assertEqual(game.level.number, 4)
        self.assertEqual((game.motion.room, game.motion.row, game.runtime.state.source_sequence_id),
                         (0, 2, 5))
        self.assertIs(game.level_map.caverns, game.caverns)

    def test_progress_save_resumes_level_four_at_its_real_entry(self):
        from pop2.save_game import capture, read_save, write_save

        resources = GameResources.load()
        game = GameSession.load(resources, 4)
        game.place(16, 1, 270, 1)
        game.combat.player.life = game.combat.player.max_life = 5
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'level4.pop2save'
            write_save(path, capture(game, copy_verified=True))
            restored, saved = read_save(path, resources)
        self.assertEqual(restored.level.number, 4)
        self.assertEqual((restored.motion.room, restored.motion.row), (0, 2))
        self.assertEqual(restored.combat.player.max_life, 5)
        self.assertTrue(saved['copy_verified'])

    def test_level_four_export_has_its_own_start_and_all_room_layers(self):
        level = LevelDefinition.read(load_resource_file('Prince.rsrc'), 4)
        program = cavern_assets(4)[0]
        self.assertEqual((level.kind, level.start_room, level.start_tile, level.start_x, level.facing),
                         (3, 0, 25, 277, 0))
        self.assertIn(program['version'], (15, 16, 17))
        self.assertEqual(program['level'], 4)
        rooms = {str(room) for room in range(32)}
        for key in ('rooms', 'torches', 'climb_redraw', 'floor_redraw'):
            self.assertEqual(set(program[key]), rooms)
        self.assertEqual(program['entry_exit']['room'], level.start_room)
        self.assertEqual(program['entry_exit']['cell'], 25)
        self.assertNotEqual(program['rooms'], cavern_assets(3)[0]['rooms'])

    def test_room_nineteen_keeps_the_native_decoration_beneath_an_upper_room_loose_floor(self):
        # DrawCaveFloorCommon 8:1998 reads the upper room from room setup.
        commands = cavern_assets(4)[0]['rooms']['18']
        self.assertIn(['front', 3604, 306, 23, 16, 0, [5, 306, 23, 356], 4, 6, 0], commands)

    def test_all_rooms_and_animated_layers_render_without_reusing_level_three(self):
        level = LevelDefinition.read(load_resource_file('Prince.rsrc'), 4)
        renderer = LevelRenderer(level, preload_room=False)
        world = CavernState()
        world.configure_entry(renderer.cavern_program.get('entry_exit'))
        world.configure_torches(renderer.cavern_program.get('torches', {}))
        world.configure_lava(renderer.cavern_program.get('lava'))
        self.assertEqual(set(renderer.supported_rooms()), set(range(32)) - {7, 29, 30, 31})
        self.assertEqual(len(renderer.screen_entries()), 28)
        for room_id in range(32):
            with self.subTest(room=room_id):
                room = renderer.enter_room(room_id, world)
                frame = renderer.animated_layer(room.background.copy(), room_id, None, caverns=world)
                frame = Image.alpha_composite(frame, room.foreground)
                frame = renderer.animated_layer(frame, room_id, None, front=True, caverns=world)
                self.assertEqual(frame.size, (510, 365))
                self.assertEqual(frame.getchannel('A').getextrema(), (255, 255))


@unittest.skipUnless((ASSET_DIR / 'caverns_level4.json').is_file(), 'Imported level-four resources required')
class LevelFourHostTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)

    def tick(self, count):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.tick(self, count)

    def test_f3_load_restart_and_room_warp_keep_level_four_and_close_the_entrance(self):
        scene = self.scene
        self.assertIn(4, [option[0] for option in scene.development_levels()])
        scene.load_level(4)
        self.assertEqual(scene.level_renderer.cavern_program['level'], 4)
        self.tick(16)
        self.assertEqual((scene.room_id, scene.terrain_motion.row, scene.action), (0, 2, 15))
        self.assertEqual(scene.game.caverns.entry_frame, len(scene.game.caverns.entry_frames) - 1)
        self.assertIsNotNone(scene.native_viewport.getbbox())
        scene.jump_to_screen('Room 19')
        self.assertEqual((scene.game.level.number, scene.room_id), (4, 18))
        self.assertTrue(scene.combat.player.alive)
        scene.restart_level()
        self.assertEqual((scene.game.level.number, scene.room_id, scene.terrain_motion.row), (4, 0, 2))

    def test_host_save_preview_and_load_keep_level_four(self):
        scene = self.scene
        scene.load_level(4)
        self.tick(16)
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'level4.pop2save'
            scene.save_game_to(path, 'Cavern four')
            scene.load_level(1)
            scene.load_game_from(path)
        self.assertEqual((scene.game.level.number, scene.room_id, scene.terrain_motion.row), (4, 0, 2))
        self.assertTrue(scene.combat.player.alive)

    def test_cavern_turn_consumer_passes_current_body_bounds_to_combat(self):
        scene = self.scene
        scene.load_level(4)
        self.tick(16)
        scene.sword_drawn = True
        bounds = scene.player_bounds()
        with patch.object(scene.combat, 'choose_player_turn', return_value=False) as turn:
            self.assertFalse(scene.resume_combat_turn())
        turn.assert_called_once_with(scene.frames[scene.sequence_state.action], bounds)


if __name__ == '__main__':
    unittest.main()


@unittest.skipUnless((ASSET_DIR / 'caverns_level4.json').is_file(), 'Imported level-four resources required')
class LevelFourExitGuardedSkeletonTests(unittest.TestCase):
    """4:17aa / SkelDoneShaking 4:1ae0-1b34 for rooms 22 and 24-28."""

    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        self.scene.load_level(4)
        self.tick(16)

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.tick(self, count)

    def open_exit(self):
        door = self.scene.level_map.tile(21, 4, 2)
        self.assertEqual(door.kind, 17)
        self.scene.game.caverns.plates.foreground[21, 24] = (door.foreground & 0xff00) | 79

    def visit(self, room, x, count=40):
        scene = self.scene
        scene.jump_to_room(room, 2, x, 1)
        guards = [guard for guard in scene.combat.active_guards() if guard.room == room]
        self.tick(count)
        return guards

    def test_closed_exit_keeps_the_bones_shaking_even_beside_the_prince(self):
        for room in (25, 27):
            with self.subTest(room=room + 1):
                guards = self.visit(room, 100 if room == 27 else 60)
                self.assertEqual({guard.skeleton.phase for guard in guards}, {'dormant'})
                self.assertFalse(any(guard.alive for guard in guards))

    def test_open_exit_raises_bones_only_when_the_prince_is_to_their_left(self):
        self.open_exit()
        right = self.visit(25, 300)
        self.assertEqual(right[0].skeleton.phase, 'dormant')
        left = self.visit(25, 60)
        self.assertIn(left[0].skeleton.phase, ('rising', 'active'))
        self.assertTrue(left[0].alive)

    def test_rooms_outside_the_exit_group_keep_the_ordinary_wake(self):
        from pop2.skeleton import exit_guarded

        combat = self.scene.combat
        for room, guards in ((room, guards) for room, (guards, _points)
                             in combat.room_encounters.items() if guards):
            for guard in guards:
                self.assertEqual(exit_guarded(combat, guard), room in (21, 23, 24, 25, 26, 27))


@unittest.skipUnless((ASSET_DIR / 'caverns_level4.json').is_file(), 'Imported level-four resources required')
class LevelFourHeapPlacementTests(unittest.TestCase):
    def test_room_fourteen_heap_moves_off_the_flask_away_from_the_gap(self):
        # SkelAddOpponent 4:19f0-1a54: open space on the heap's left moves it
        # right; the original data put it on the type-5 flask's cell.
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(4)
        RooftopSceneTests.tick(self, 16)
        scene.jump_to_room(13, 0, 450, 0)
        heap = next(guard for guard in scene.combat.active_guards() if guard.room == 13)
        self.assertEqual((heap.state.facing, heap.state.action), (1, 206))
        self.assertGreater(heap.state.target_x, 302 + 20)
        self.assertEqual(heap.skeleton.settle_heap(scene.combat, heap), 0)


@unittest.skipUnless((ASSET_DIR / 'caverns_level4.json').is_file(), 'Imported level-four resources required')
class LevelFourSkeletonChaseTests(unittest.TestCase):
    """AutoCtrl 4:0780-0798 and AnimCharTap 4:311e-314a in rooms 22, 24-28."""

    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        self.scene.load_level(4)
        RooftopSceneTests.tick(self, 16)

    def runner(self, room, x, facing):
        from pop2.combat import select_sequence

        scene = self.scene
        scene.jump_to_room(room, 2, 60, 0)
        skeleton = next(guard for guard in scene.combat.active_guards() if guard.room == room)
        skeleton.skeleton.rise(scene.combat, skeleton)
        select_sequence(skeleton, 216)
        skeleton.state.facing = facing
        skeleton.state.target_x = skeleton.state.current_x = x
        skeleton.sword_drawn = False
        return scene, skeleton

    def test_runner_in_reach_lunges_with_sword_in_exit_rooms(self):
        scene, skeleton = self.runner(25, 200, 0)
        player = scene.combat.player.state
        player.target_x = player.current_x = 130
        player.facing, player.action, player.animation_state = 0, 8, 1
        skeleton.state.action = 195
        scene.combat._choose_unarmed_guard_action(skeleton)
        self.assertEqual(skeleton.state.source_sequence_id, 87)
        self.assertTrue(skeleton.sword_drawn)

    def test_running_footsteps_add_twice_the_bank_slot_in_exit_rooms(self):
        scene, skeleton = self.runner(25, 300, 1)
        skeleton.bank_slot = 2
        state = skeleton.state
        sequence = scene.combat.sequences[216]
        state.cursor = sequence.index(-15)
        state.action = 193
        before = state.target_x
        expected = state.target_x
        probe = type(state)(**{**state.__dict__, 'sound_events': [], 'sequence_events': []})
        from pop2.sequence_runtime import SequenceRuntime

        SequenceRuntime(scene.combat.sequences, probe).next_frame()
        expected = probe.target_x + 4
        with unittest.mock.patch.object(scene.combat, 'choose_guard_action'):
            scene.combat.advance_guard()
        self.assertGreater(probe.callback_counter, 0)
        self.assertEqual(state.target_x - before, expected - before)


@unittest.skipUnless((ASSET_DIR / 'caverns_level4.json').is_file(), 'Imported level-four resources required')
class LevelExitSceneryTests(unittest.TestCase):
    def test_torches_keep_flickering_while_the_exit_song_plays(self):
        # 2:6100-6134: FrameAdv still runs before the exit-music check.
        from pop2.level_transition import LevelExit
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(4)
        RooftopSceneTests.tick(self, 16)
        program = scene.level_renderer.cavern_program
        room = next(int(room) for room, records in program['torches'].items() if records)
        scene.jump_to_room(room)
        scene.game.complete = True
        scene.game.exit = LevelExit(32, 1000)
        keys = {(record['room'], record['cell']) for record in program['torches'][str(room)]}
        seen = set()
        for _ in range(12):
            RooftopSceneTests.tick(self)
            seen.add(tuple(scene.game.caverns.torches[key] for key in sorted(keys)))
        self.assertIsNotNone(scene.game.exit)
        self.assertGreater(len(seen), 1)


@unittest.skipUnless((ASSET_DIR / 'caverns_level4.json').is_file(), 'Imported level-four resources required')
class LevelFourRunnerBumpTests(unittest.TestCase):
    def test_running_skeleton_bumps_a_wall_as_an_armed_opponent(self):
        # Collide 4:5910/59b6: SEQS:46/47 hold Prince poses 50-52, which the
        # skeleton FRAM lacks; selecting them froze the game (action -99).
        from pop2.combat import select_sequence
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(4)
        RooftopSceneTests.tick(self, 16)
        scene.god_mode = True
        scene.jump_to_room(25, 2, 255, 0)
        skeleton = next(guard for guard in scene.combat.active_guards() if guard.room == 25)
        skeleton.skeleton.rise(scene.combat, skeleton)
        select_sequence(skeleton, 216)
        skeleton.state.facing, skeleton.state.target_x = 0, 450
        skeleton.state.current_x, skeleton.sword_drawn = 450, False
        sequences = set()
        for _ in range(40):
            RooftopSceneTests.tick(self)
            sequences.add(skeleton.state.sequence_id)
        self.assertIn(64, sequences)
        self.assertFalse(sequences & {46, 47})


@unittest.skipUnless((ASSET_DIR / 'caverns_level4.json').is_file(), 'Imported level-four resources required')
class LevelFourReliefTests(unittest.TestCase):
    """ATMGate 5:42c6-42ce, 5:4766-489c and FrameAdv 2:640c-6446 (sound 110)."""

    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(4)
        RooftopSceneTests.tick(self, 16)
        scene.god_mode = True
        # Room 24's gate (cell 22) open; its reversible plate is cell 21.
        scene.game.caverns.plates.foreground[23, 22] = 0x200 | 184
        scene.jump_to_room(25, 2, 300, 0)
        self.skeleton = next(guard for guard in scene.combat.active_guards() if guard.room == 25)
        scene.combat.room_encounters[25][0].remove(self.skeleton)

    def slam(self, x):
        from tests.test_terrain import RooftopSceneTests

        scene, skeleton = self.scene, self.skeleton
        scene.jump_to_room(23, 2, 120, 0)
        skeleton.room, skeleton.row, skeleton.bank_room, skeleton.bank_slot = 23, 2, 23, 0
        skeleton.state.target_x = skeleton.state.current_x = x
        if skeleton.terrain_motion is not None:
            skeleton.terrain_motion.room, skeleton.terrain_motion.row = 23, 2
        scene.combat.room_encounters[23][0].append(skeleton)
        skeleton.skeleton.rise(scene.combat, skeleton)
        from unittest.mock import patch
        from pop2.environments import Caverns

        sounds = []
        relief = Caverns.advance_relief

        def spy(environment, caverns):
            events = scene.sequence_state.sound_events
            start = len(events)
            relief(environment, caverns)
            sounds.extend(cue for cue in events[start:] if cue == 110)
        with patch.object(Caverns, 'advance_relief', spy):
            for _ in range(12):
                RooftopSceneTests.tick(self)
        return sounds

    def test_slamming_the_gate_on_a_skeleton_makes_the_prince_sigh_once(self):
        self.assertEqual(self.slam(330), [110])
        self.assertEqual(self.scene.game.caverns.phew_countdown, -2)

    def test_no_sigh_with_the_skeleton_on_the_princes_side(self):
        self.assertEqual(self.slam(60), [])
        self.assertEqual(self.scene.game.caverns.phew_countdown, -1)
