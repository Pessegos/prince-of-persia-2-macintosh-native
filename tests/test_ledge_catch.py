import struct
import unittest
from types import SimpleNamespace

from pop2.paths import ASSET_DIR
from pop2.sequence_runtime import SequenceState
from pop2.terrain import LevelMap


class CatchReleaseRuleTests(unittest.TestCase):
    def setUp(self):
        self.level = bytearray(0x49ca)
        struct.pack_into('>H', self.level, 0x2198, 1)
        self.terrain = LevelMap(self.level)
        self.record = SimpleNamespace(offset_x=3, aux=77)

    def state(self, facing, source, *, x=None):
        return SequenceState(12, selected_sequence_id=source, action=106, actor_type=0,
                             animation_state=4, level_kind=3, facing=facing,
                             current_x=(196, 258)[facing] if x is None else x,
                             target_x=(196, 258)[facing] if x is None else x,
                             current_y=-30, horizontal_velocity=1, vertical_velocity=33)

    def ledge(self, room, row, facing):
        self.level[:0x780] = bytes(0x780)
        column = (2, 5)[facing]
        struct.pack_into('>H', self.level, room * 60 + ((row - 1) * 10 + column) * 2, 1)

    def test_toward_ledge_release_rejects_the_artificial_second_grip(self):
        for environment in (1, 3, 5, 6):
            struct.pack_into('>H', self.level, 0x2186, environment)
            for room in (0, 7, 21, 30):
                for row in (1, 2):
                    for facing in (0, 1):
                        with self.subTest(environment=environment, room=room, row=row, facing=facing):
                            self.ledge(room, row, facing)
                            state = self.state(facing, 99)
                            state.level_kind = environment
                            before = vars(state).copy()
                            self.assertFalse(self.terrain.catch_ledge(room, row, state, self.record))
                            self.assertEqual(vars(state), before)

    def test_ordinary_falls_and_away_release_keep_the_seventeen_pixel_test(self):
        for facing in (0, 1):
            for source in (19, 23):
                self.ledge(0, 1, facing)
                state = self.state(facing, source)
                x = state.target_x
                self.assertTrue(self.terrain.catch_ledge(0, 1, state, self.record))
                self.assertEqual(state.target_x, x + (17 if not facing else -17))
                self.assertEqual(state.current_x, state.target_x)
                self.assertEqual((state.current_y, state.vertical_velocity, state.horizontal_velocity), (0, 0, 0))

    def test_release_history_survives_the_link_to_the_generic_fall_loop(self):
        for facing in (0, 1):
            self.ledge(0, 1, facing)
            state = self.state(facing, 99)
            self.assertEqual(state.sequence_id, 12)
            self.assertEqual(state.source_sequence_id, 99)
            self.assertFalse(self.terrain.catch_ledge(0, 1, state, self.record))
            state.selected_sequence_id = None
            self.assertTrue(self.terrain.catch_ledge(0, 1, state, self.record))

    def test_toward_release_can_still_catch_a_genuinely_reachable_ledge(self):
        for facing, x in ((0, 180), (1, 280)):
            self.ledge(0, 1, facing)
            state = self.state(facing, 99, x=x)
            self.assertTrue(self.terrain.catch_ledge(0, 1, state, self.record))
            self.assertEqual(state.target_x, x + (24 if not facing else -24))

    def test_release_extension_does_not_bypass_speed_or_height_limits(self):
        self.ledge(0, 1, 0)
        for y, velocity, expected in ((-49, 33, False), (-48, 59, True),
                                      (3, 59, True), (4, 33, False), (-30, 60, False)):
            with self.subTest(y=y, velocity=velocity):
                state = self.state(0, 99, x=180)
                state.current_y, state.vertical_velocity = y, velocity
                self.assertEqual(self.terrain.catch_ledge(0, 1, state, self.record), expected)


@unittest.skipUnless((ASSET_DIR / 'caverns_entry.json').is_file(), 'Imported game resources required')
class CavernSecondLedgeTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests
        RooftopSceneTests.setUp(self)

    def test_reported_collapse_catches_first_ledge_but_not_second_after_release(self):
        from tests.test_terrain import RooftopSceneTests

        scene = self.scene
        scene.load_level(3)
        scene.jump_to_room(21, row=0, x=460, facing=0)
        scene.peaceful = True
        scene.game.caverns.loose.trigger(scene.level_map.tile(21, 4, 0), force=True)
        RooftopSceneTests.tick(self, 2)
        scene.horizontal_key(None, -1, True)
        first, dropped = None, None
        grips = []
        for tick in range(85):
            if scene.terrain_motion.falling and first is None:
                scene.set_key_state('shift', True)
            if scene.ledge_hanging and first is None:
                first = tick
                scene.horizontal_key(None, -1, False)
            if first is not None and dropped is None and tick >= first + 4:
                scene.set_key_state('shift', False)
                if not scene.ledge_hanging:
                    dropped = tick
            if dropped is not None:
                scene.set_key_state('shift', True)
            RooftopSceneTests.tick(self)
            if scene.action == 80:
                grips.append((scene.room_id, scene.terrain_motion.row, scene.player_x))
            if dropped is not None:
                self.assertFalse(scene.ledge_hanging)
        self.assertIsNotNone(dropped)
        self.assertEqual(grips, [(21, 1, 219)])
        self.assertEqual((scene.room_id, scene.terrain_motion.row), (21, 2))
        self.assertFalse(scene.terrain_motion.falling or scene.terrain_motion.dead)
        self.assertTrue(scene.combat.player.alive)

    def test_ctrl_held_through_the_collapse_catches_the_same_ledge(self):
        # Catch 4:37cc admits any nonzero modifier word (a5-0x3480), and
        # 4:3f08 writes -2 for a held Ctrl as -1 for Shift. Previously only
        # Shift caught, although Ctrl already kept the hang (6:18e0).
        from tests.test_terrain import RooftopSceneTests

        scene = self.scene
        for key in ('shift', 'ctrl'):
            with self.subTest(key=key):
                scene.load_level(3)
                scene.jump_to_room(21, row=0, x=460, facing=0)
                scene.peaceful = True
                scene.game.caverns.loose.trigger(scene.level_map.tile(21, 4, 0), force=True)
                RooftopSceneTests.tick(self, 2)
                scene.horizontal_key(None, -1, True)
                grips = []
                for _ in range(60):
                    if scene.terrain_motion.falling and not grips:
                        scene.set_key_state(key, True)
                        scene.horizontal_key(None, -1, False)
                    RooftopSceneTests.tick(self)
                    if scene.action == 80:
                        grips.append((scene.room_id, scene.terrain_motion.row, scene.player_x))
                hanging = scene.ledge_hanging
                scene.set_key_state(key, False)
                self.assertEqual(grips, [(21, 1, 219)])
                self.assertTrue(hanging)
