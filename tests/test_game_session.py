import struct
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pop2.game_session import GameResources, GameSession
from pop2.level_data import LevelDefinition
from pop2.paths import ASSET_DIR
from pop2.rebirth import RebirthSnapshot


def level_bytes(number=1, kind=5, room=4, tile=2, facing=65535, opponent_type=0):
    data = bytearray(0x49ca)
    for offset in range(0, 0x780, 2):
        struct.pack_into(">H", data, offset, 1)
    struct.pack_into(">H", data, 0x2186, kind)
    struct.pack_into(">H", data, 0x218a, number)
    struct.pack_into(">3H", data, 0x2198, room, tile, facing)
    struct.pack_into(">h", data, 0x21a4, opponent_type)
    return data


def resources():
    first = level_bytes()
    struct.pack_into(">2h", first, 0x39a6, 15, 5)
    second = level_bytes(2, 1, 2, 15, opponent_type=-1)
    sequences = {2: (-7, 0, 15, -1, 2), 4: (-7, 3, *range(34, 45), -1, 2),
                 124: (-7, 1, *range(256, 264), -1, 2)}
    return GameResources({"LEVL": {2000: {"data": first}, 2001: {"data": second}}},
                         {}, sequences, (), (), 25002)


class EmptyEncounter:
    """An empty world for session lifecycle tests, without imported AI tables."""

    def __init__(self, runtime, sequences, _spawn, _edge, level):
        self.runtime, self.sequences, self.level = runtime, sequences, level
        self.reset()

    def reset(self):
        self.player = SimpleNamespace(state=self.runtime.state, life=3, max_life=3,
                                      room=0, row=0, terrain_motion=None)
        self.room_encounters = {}
        room = struct.unpack_from(">H", self.level, 0x2198)[0] - 1
        self.enter_room(room, struct.unpack_from(">H", self.level, 0x219a)[0] // 10)

    def enter_room(self, room, row):
        self.guards, self.generation_points = self.room_encounters.setdefault(room, ([], []))
        self.player.room, self.player.row = room, row
        self.guard = None


def session(source, number=1, terrain_enabled=True):
    return GameSession.load(source, number, terrain_enabled, encounter_factory=EmptyEncounter)


class LevelDefinitionTests(unittest.TestCase):
    def test_resource_selection_decodes_start_and_checkpoint_per_level(self):
        data = resources()
        first, second = data.level(1), data.level(2)
        self.assertEqual((first.resource_id, first.number, first.kind, first.start_room,
                          first.start_tile, first.facing, first.start_row, first.entry_sequence),
                         (2000, 1, 5, 3, 2, 1, 1, 4))
        self.assertEqual((second.resource_id, second.number, second.kind, second.start_room,
                          second.start_tile, second.start_x, second.start_row, second.entry_sequence),
                         (2001, 2, 1, 1, 15, 277, 1, 124))
        self.assertEqual((first.checkpoints[0].room, first.checkpoints[0].tile), (14, 5))
        self.assertEqual(second.checkpoints, ())
        self.assertEqual(second.opponent_type, -1)

    def test_start_facing_uses_the_native_complement(self):
        level = LevelDefinition.decode(2, level_bytes(2, 1, 2, 15, facing=0))
        self.assertEqual(level.facing, 0)

    def test_definition_does_not_share_mutable_import_data(self):
        data = level_bytes()
        level = LevelDefinition.decode(1, data)
        data[0] = 255
        self.assertEqual(level.data[0], 0)

    def test_invalid_level_number_or_missing_resource_has_a_clear_error(self):
        for number in (0, -1, "2", 1.5, True, 15):
            with self.subTest(number=number), self.assertRaises(ValueError):
                resources().level(number)

    def test_truncated_or_inconsistent_metadata_is_rejected(self):
        for data in (b"", level_bytes()[:0x39ad], level_bytes(2),
                     level_bytes(kind=0), level_bytes(kind=7), level_bytes(room=0),
                     level_bytes(room=33), level_bytes(tile=30), level_bytes(facing=1)):
            with self.subTest(data_length=len(data)), self.assertRaises(ValueError):
                LevelDefinition.decode(1, data)
        data = level_bytes()
        struct.pack_into(">H", data, 0x2080, 33)
        with self.assertRaisesRegex(ValueError, "room link"):
            LevelDefinition.decode(1, data)

    def test_unknown_entry_controller_is_not_silently_the_palace_window(self):
        level = LevelDefinition.decode(3, level_bytes(3, 3, 1, 14))
        self.assertFalse(level.window_escape)
        with self.assertRaisesRegex(ValueError, "entry controller"):
            _ = level.entry_sequence


class GameSessionTests(unittest.TestCase):
    def test_level_one_and_two_have_independent_worlds_and_shared_sequences(self):
        data = resources()
        first, second = session(data), session(data, 2)
        self.assertIs(first.runtime.sequences, second.runtime.sequences)
        self.assertIsNot(first.runtime.state, second.runtime.state)
        self.assertIsNot(first.combat, second.combat)
        self.assertIsNot(first.level_map, second.level_map)
        self.assertTrue(first.opening.active)
        self.assertIsNotNone(first.harbor)
        self.assertIsNone(second.opening)
        self.assertIsNone(second.harbor)
        self.assertEqual((second.room_id, second.motion.row, second.runtime.state.action,
                          second.runtime.state.target_x, second.runtime.state.level_kind),
                         (1, 1, 256, 277, 1))
        self.assertIs(second.combat.player.terrain_motion, second.motion)
        self.assertEqual(second.combat.guards, [])
        self.assertIsNone(second.combat.guard)
        second.combat.enter_room(14, 2)
        self.assertEqual(second.combat.generation_points, [])
        self.assertEqual(second.combat.guards, [])
        first.combat.player.life = 0
        first.death.begin(15)
        first.harbor.ship_frame = 80
        first.complete = True
        self.assertEqual(second.combat.player.life, 3)
        self.assertEqual(second.death.counter, -1)
        self.assertFalse(second.complete)

    def test_restart_keeps_current_level_and_shared_runtime_but_resets_world(self):
        game = session(resources(), 2)
        runtime, state = game.runtime, game.runtime.state
        game.combat.player.life = 0
        game.motion.dead = True
        game.death.begin(3)
        game.complete = True
        game.room_id = 14
        state.sound_events.append(8)
        state.sequence_events.append((-16, ()))
        game.restart()
        self.assertIs(game.runtime, runtime)
        self.assertIs(game.runtime.state, state)
        self.assertEqual((game.level.number, game.room_id, game.motion.row, state.action), (2, 1, 1, 256))
        self.assertEqual(game.combat.player.life, 3)
        self.assertFalse(game.motion.dead)
        self.assertEqual(game.death.counter, -1)
        self.assertFalse(game.complete)
        self.assertEqual(state.sound_events, [])
        self.assertEqual(state.sequence_events, [])
        self.assertIsNone(game.harbor)
        self.assertIsNone(game.opening)

    def test_dev_placement_preserves_checkpoint_and_uses_current_environment(self):
        game = session(resources())
        point = game.level.checkpoints[0]
        game.checkpoint = RebirthSnapshot.capture(point, game.combat)
        checkpoint = game.checkpoint
        game.place(14, 0, 277, 0, reset_guards=False, preserve_checkpoint=True)
        self.assertIs(game.checkpoint, checkpoint)
        self.assertFalse(game.opening.active)
        self.assertEqual((game.room_id, game.motion.row, game.runtime.state.level_kind), (14, 0, 5))
        game.place(3, 1, 411, 1)
        self.assertIsNone(game.checkpoint)
        second = session(resources(), 2)
        second.place(14, 2, 100, 0)
        self.assertEqual(second.runtime.state.level_kind, 1)
        self.assertIsNone(second.harbor)

    def test_invalid_placement_leaves_the_running_world_untouched(self):
        game = session(resources())
        state = vars(game.runtime.state).copy()
        motion, combat = game.motion, game.combat
        for args in ((32, 1, 100, 0), (3, 3, 100, 0), (3, 1, 510, 0)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                game.place(*args)
        self.assertEqual(vars(game.runtime.state), state)
        self.assertIs(game.motion, motion)
        self.assertIs(game.combat, combat)

    def test_preview_uses_the_same_entry_without_enabling_terrain_or_combat(self):
        game = session(resources(), terrain_enabled=False)
        self.assertIsNone(game.level_map)
        self.assertIsNone(game.physics)
        self.assertIsNone(game.combat)
        self.assertIsNone(game.motion)
        self.assertEqual((game.runtime.state.action, game.runtime.state.target_x), (43, 116))

    def test_resources_and_sessions_do_not_import_a_window_backend(self):
        script = ("import sys; from tests.test_game_session import resources, session; "
                  "from pop2.game_session import GameSession; "
                  "a=resources(); g=session(a); h=session(a, 2); "
                  "h.restart(); assert 'tkinter' not in sys.modules; "
                  "assert 'pygame' not in sys.modules")
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_level_completion_is_consumed_once_without_a_harbor_controller(self):
        game = session(resources(), 2)
        self.assertFalse(game.consume_completion())
        game.runtime.state.sequence_events.extend([(-10, (1,)), (-16, ())])
        self.assertTrue(game.consume_completion())
        self.assertTrue(game.complete)
        self.assertFalse(game.consume_completion())
        self.assertEqual(game.runtime.state.sequence_events, [(-10, (1,))])
        game.restart()
        self.assertFalse(game.complete)

    def test_blank_sessions_do_not_share_death_state(self):
        first, second = GameSession(), GameSession()
        first.death.begin(3)
        self.assertEqual(second.death.counter, -1)
        self.assertFalse(second.consume_completion())


@unittest.skipUnless((ASSET_DIR / "Prince.rsrc").is_file(), "Imported game resources required")
class OriginalLevelSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resources = GameResources.load()

    def test_every_original_level_decodes_its_own_metadata(self):
        for number in range(1, 15):
            with self.subTest(number=number):
                level = self.resources.level(number)
                self.assertEqual(level.resource_id, 1999 + number)
                self.assertEqual(level.data, self.resources.prince["LEVL"][level.resource_id]["data"])

    def test_original_level_two_enters_from_the_ship_without_rooftop_state(self):
        game = GameSession.load(self.resources, 2)
        poses = [game.runtime.state.action]
        for _ in range(8):
            game.runtime.next_frame()
            poses.append(game.runtime.state.action)
        self.assertEqual(poses, [256, 257, 258, 259, 260, 261, 262, 263, 15])
        self.assertEqual((game.level.kind, game.room_id, game.motion.row), (1, 1, 1))
        self.assertEqual(game.combat.guards, [])
        self.assertIsNone(game.harbor)
        self.assertIsNone(game.opening)

    def test_room_cache_matches_existing_rooftop_pixels_and_stays_lazy(self):
        from pop2.level_rendering import LevelRenderer
        from pop2.render_opening import build_opening_room

        level = self.resources.level(1)
        renderer = LevelRenderer(level)
        before = set(renderer.rooms)
        with patch("pop2.level_rendering.build_opening_room") as build:
            self.assertEqual(tuple(renderer.screen_entries()),
                             ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "Secret (right)"))
            build.assert_not_called()
        self.assertEqual(set(renderer.rooms), before)
        for room in (3, 0, 14, 15, 18):
            self.assertEqual(renderer.room(room).flattened().tobytes(),
                             build_opening_room(include_curtain=False, room_id=room).flattened().tobytes())
            self.assertIs(renderer.room(room), renderer.room(room))

    def test_missing_level_two_scenery_is_reported_before_opening_a_window(self):
        from pop2.level_rendering import LevelRenderer

        game = GameSession.load(self.resources, 2)
        with self.assertRaisesRegex(ValueError, "scenery is not implemented"):
            LevelRenderer(game.level)

    def test_initial_visited_and_generated_guards_inherit_the_player_environment(self):
        data = bytearray(self.resources.level(1).data)
        struct.pack_into(">H", data, 0x2186, 1)
        prince = {**self.resources.prince, "LEVL": {2000: {"data": data}}}
        source = GameResources(prince, self.resources.kid, self.resources.sequences,
                               self.resources.frames, self.resources.attachment_frames,
                               self.resources.first_shape_id)
        game = GameSession.load(source)
        self.assertEqual(game.combat.guard.state.level_kind, 1)
        game.combat.enter_room(4, 1)
        self.assertTrue(game.combat.guards)
        self.assertTrue(all(guard.state.level_kind == 1 for guard in game.combat.guards))
        game.combat.enter_room(3, 1)
        point = game.combat.generation_points[0]
        before = len(game.combat.guards)
        with patch.object(point, "advance", return_value=True):
            game.combat.generate_opponents()
        self.assertGreater(len(game.combat.guards), before)
        self.assertTrue(all(guard.state.level_kind == 1 for guard in game.combat.guards))


@unittest.skipUnless((ASSET_DIR / "Prince.rsrc").is_file(), "Imported game resources required")
class LevelHostTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)

    def test_unsupported_scenery_does_not_replace_or_reset_live_gameplay(self):
        scene = self.scene
        game, renderer = scene.game, scene.level_renderer
        state = vars(scene.sequence_state).copy()
        scene.combat.player.life = 2
        viewport = scene.native_viewport.tobytes()
        with patch.object(scene, "render") as render, \
                self.assertRaisesRegex(ValueError, "scenery is not implemented"):
            scene.load_level(2)
        render.assert_not_called()
        self.assertIs(scene.game, game)
        self.assertIs(scene.level_renderer, renderer)
        self.assertEqual(vars(scene.sequence_state), state)
        self.assertEqual(scene.combat.player.life, 2)
        self.assertEqual(scene.native_viewport.tobytes(), viewport)

    def test_restart_keeps_the_current_level_and_new_game_returns_to_level_one(self):
        scene = self.scene
        second = GameSession.load(scene.resources, 2)
        # Keep a test-only scenery adapter: this test exercises host reset
        # ownership, not level-two rendering, which is still unsupported.
        scene.bind_level(second, scene.level_renderer)
        scene.combat.player.max_life = 5
        scene.combat.player.life = 1
        scene.game.complete = True
        with patch.object(scene, "render"):
            scene.restart_level()
        self.assertIs(scene.game, second)
        self.assertEqual((scene.game.level.number, scene.action, scene.room_id), (2, 256, 1))
        self.assertEqual(scene.combat.player.life, 5)
        self.assertIsNone(scene.opening)
        self.assertIsNone(scene.harbor)
        scene.new_game()
        self.assertEqual((scene.game.level.number, scene.action, scene.room_id), (1, 43, 3))
        self.assertIsNot(scene.game, second)
        self.assertIs(scene.sequence_runtime, scene.game.runtime)
        self.assertIs(scene.sequence_state, scene.game.runtime.state)
        self.assertIs(scene.terrain_motion, scene.combat.player.terrain_motion)
        self.assertTrue(scene.opening.active)
        self.assertIsNotNone(scene.harbor)
        self.assertEqual(scene.combat.player.max_life, 3)
