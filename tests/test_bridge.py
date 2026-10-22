import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pop2.bridge import (
    bridge_column, BREAK_SONG, BREAK_SOUND, CREAK_SOUND, PLANK_FRAMES, Bridge, bridge_checked,
)
from pop2.paths import ASSET_DIR


class FixedRandom:
    def __init__(self, *values):
        self.values = list(values)
        self.calls = []

    def randint(self, low, high):
        self.calls.append((low, high))
        return self.values.pop(0) if self.values else low


class BridgeBreakTests(unittest.TestCase):
    """BridgeCheckBreak 8:002e-016c and TriggerBrgFloorMob 8:0ba2-0d18."""

    def test_counter_rises_close_falls_apart_and_drains_by_two_when_alone(self):
        bridge = Bridge()
        for _ in range(5):
            bridge.check_break(5, 8, 0)
        self.assertEqual(bridge.counter, 5)
        bridge.check_break(1, 6, 0)
        self.assertEqual(bridge.counter, 4)
        bridge.check_break(5, None, 0)
        bridge.check_break(None, None, 0)
        self.assertEqual(bridge.counter, 0)
        # Only a counter above one drains by two; one stays, apart never goes negative.
        bridge.counter = 1
        bridge.check_break(None, 5, 0)
        bridge.check_break(1, 8, 0)
        self.assertEqual(bridge.counter, 0)
        bridge.check_break(1, 8, 0)
        self.assertEqual(bridge.counter, 0)

    def test_break_needs_sixty_counts_middle_columns_and_not_sequence_85(self):
        for prince, opponent, selected, broken in (
                (4, 5, 0, True), (6, 6, 0, True), (3, 5, 0, False), (7, 6, 0, False),
                (5, 4, 0, False), (5, 7, 0, False), (5, 5, 85, False)):
            with self.subTest(prince=prince, opponent=opponent, selected=selected):
                bridge = Bridge(counter=59)
                bridge.check_break(prince, opponent, selected)
                self.assertEqual(bridge.state, int(broken))
                self.assertEqual(bridge.counter, 60)
        bridge = Bridge(counter=58)
        bridge.check_break(5, 5, 0)
        self.assertEqual(bridge.state, 0)

    def test_collapse_drops_columns_seven_to_three_one_per_frame(self):
        bridge = Bridge(state=1, counter=60)
        rng = FixedRandom(1, 0, 1, 1, 0)
        results = [bridge.check_break(None, None, 0, rng) for _ in range(8)]
        self.assertEqual(results[:2], [((), False)] * 2)
        self.assertEqual(results[2], ((BREAK_SOUND,), False))
        self.assertEqual(results[3:7], [((), False)] * 4)
        self.assertEqual(results[7], ((), True))
        self.assertEqual(bridge.state, -1)
        self.assertEqual(bridge.songs, [BREAK_SONG])
        self.assertEqual(bridge.pieces, {7: 2, 6: 1, 5: 2, 4: 2, 3: 1})
        self.assertEqual(rng.calls, [(0, 1)] * 5)
        self.assertEqual(bridge.check_break(5, 5, 0), ((), False))
        self.assertEqual(bridge.counter, 60)

    def test_prince_sequence_85_ends_the_collapse_after_the_current_plank(self):
        bridge = Bridge(state=3)
        self.assertEqual(bridge.check_break(None, None, 85, FixedRandom(0)), ((BREAK_SOUND,), True))
        self.assertEqual((bridge.state, set(bridge.pieces)), (-1, {7}))

    def test_fallen_cells_are_empty_custom_floor_only_in_room_ten_row_one(self):
        bridge = Bridge(pieces={4: 1})
        self.assertEqual(bridge.tile(9, 14, 44, 0), (0, 0xc000))
        self.assertEqual(bridge.tile(9, 15, 44, 0), (44, 0))
        self.assertEqual(bridge.tile(9, 4, 0, 0), (0, 0))
        self.assertEqual(bridge.tile(8, 14, 3, 5), (3, 5))

    def test_turns_are_refused_only_in_level_five_room_ten_while_breaking(self):
        for state, level, room, blocked in ((1, 5, 9, True), (3, 5, 9, True), (0, 5, 9, False),
                                            (-1, 5, 9, False), (2, 5, 6, False), (2, 4, 9, False)):
            with self.subTest(state=state, level=level, room=room):
                self.assertEqual(Bridge(state=state).blocks_turn(level, room), blocked)
        self.assertEqual([room for room in range(32) if bridge_checked(5, room)], [6, 9, 11])
        self.assertFalse(bridge_checked(4, 9))

    def test_hanging_plank_holds_frame_seven_and_falling_plank_ends_after_thirteen(self):
        bridge = Bridge(pieces={7: 1, 6: 2}, planks=[[7, 0], [6, 8]])
        frames = []
        for _ in range(9):
            frames.append([frame for _column, frame in bridge.planks])
            bridge.advance_planks()
        self.assertEqual(frames[0], [0, 8])
        self.assertEqual(frames[5], [5, 13])
        self.assertEqual(frames[6], [6])
        self.assertEqual(frames[8], [7])

    def test_plank_drawing_uses_column_sag_and_frame_offsets(self):
        bridge = Bridge(pieces={5: 2}, planks=[[5, 10]])
        record, dy, dx = PLANK_FRAMES[10]
        self.assertEqual(list(bridge.plank_drawings()), [(record, 255 + dx, 245 + 7 + dy - 1)])

    def test_creak_odds_depend_on_how_many_characters_stand_on_the_bridge(self):
        bridge = Bridge()
        rng = FixedRandom(0, 0, 3)
        self.assertEqual(bridge.creak(4, 5, False, rng), (CREAK_SOUND,))
        self.assertEqual(bridge.creak(None, 5, False, rng), (CREAK_SOUND,))
        self.assertEqual(bridge.creak(4, None, False, rng), ())
        self.assertEqual(rng.calls, [(0, 40), (0, 80), (0, 80)])
        self.assertEqual(bridge.creak(4, 5, True, rng), ())
        self.assertEqual(bridge.creak(None, None, False, rng), ())
        self.assertEqual(len(rng.calls), 3)


@unittest.skipUnless((ASSET_DIR / 'caverns_level5.json').is_file(), 'Imported level-five resources required')
class BridgeSceneryTests(unittest.TestCase):
    def test_room_ten_redraw_omits_only_the_fallen_planks(self):
        # A native redraw of the emptied cells (all five collapse stages)
        # equals the export without the fallen columns' SHAP 4226 commands.
        from pop2.caverns import cavern_assets, cavern_room, without_fallen_planks

        program = cavern_assets(5)[0]
        commands = program['rooms']['9']
        planks = [command[8] for command in commands if command[1] == 4226]
        self.assertEqual(planks, list(range(1, 9)))
        left = without_fallen_planks(commands, frozenset(range(3, 8)))
        self.assertEqual([command[8] for command in left if command[1] == 4226], [1, 2, 8])
        self.assertEqual(len(left), len(commands) - 5)
        intact = cavern_room(9, animated=True, level_number=5)
        broken = cavern_room(9, animated=True, level_number=5, bridge_fallen=frozenset({7}))
        self.assertNotEqual(intact.background.crop((357, 200, 408, 250)).tobytes(),
                            broken.background.crop((357, 200, 408, 250)).tobytes())
        self.assertEqual(intact.background.crop((0, 0, 300, 200)).tobytes(),
                         broken.background.crop((0, 0, 300, 200)).tobytes())


@unittest.skipUnless((ASSET_DIR / 'caverns_level5.json').is_file(), 'Imported level-five resources required')
class BridgeSceneTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        self.scene.load_level(5)
        self.tick(16)

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.tick(self, count)

    def test_fighting_on_the_middle_planks_breaks_the_bridge_and_drops_the_prince(self):
        scene = self.scene
        scene.god_mode = True
        # Mid-bridge duel, Prince in column 4-5 and skeleton in 5-6. The
        # skeleton's AI is held so that the break rule alone is exercised.
        scene.jump_to_room(9, 1, 230, 1)
        skeleton = scene.combat.active_guards()[0]
        skeleton.state.facing = 0
        skeleton.state.target_x = skeleton.state.current_x = 290
        scene.combat.choose_guard_action = lambda guard=None: None
        scene.start_sword_action("sword_draw")
        bridge = scene.game.caverns.bridge
        blocked = False
        for _ in range(240):
            self.tick()
            if bridge.state > 0:
                blocked = blocked or not scene.resume_combat_turn()
            if bridge.state == -1:
                break
        self.assertEqual(bridge.state, -1)
        self.assertTrue(blocked)
        self.assertEqual(set(bridge.pieces), {3, 4, 5, 6, 7})
        self.assertEqual([scene.level_map.tile(9, column, 1).kind for column in range(10)],
                         [1, 44, 44, 0, 0, 0, 0, 0, 44, 34])
        self.tick(30)
        self.assertNotEqual((scene.combat.player.room, scene.terrain_motion.row), (9, 1))

    def test_an_opponent_falling_out_of_room_ten_is_removed_not_carried_below(self):
        scene = self.scene
        scene.god_mode = True
        scene.jump_to_room(9, 1, 20, 0)
        skeleton = scene.combat.active_guards()[0]
        skeleton.state.target_x = skeleton.state.current_x = 230
        scene.game.caverns.bridge.pieces.update({column: 1 for column in range(3, 8)})
        self.tick(12)
        self.assertNotIn(skeleton, scene.combat.active_guards())
        self.assertFalse(any(skeleton in guards for guards, _points
                             in scene.combat.room_encounters.values()))
        self.assertEqual(scene.combat.room_encounters.get(10, ([], []))[0], [])

    def test_bridge_state_survives_a_snapshot_roundtrip_and_old_snapshots_omit_it(self):
        from pop2.save_game import capture_snapshot, read_snapshot, write_save

        game = self.scene.game
        game.caverns.bridge = Bridge(state=-1, counter=61, pieces={7: 2, 6: 1}, planks=[[6, 7]])
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'bridge.json'
            write_save(path, capture_snapshot(game))
            loaded, _saved = read_snapshot(path, self.scene.resources)
            self.assertEqual(loaded.caverns.bridge, game.caverns.bridge)
            self.assertEqual(loaded.level_map.tile(9, 7, 1).kind, 0)
            value = json.loads(path.read_text())

            def remove_bridge(item):
                if isinstance(item, dict):
                    if item.get('record') == 'CavernState':
                        item['fields'].pop('bridge')
                    for child in item.values():
                        remove_bridge(child)
                elif isinstance(item, list):
                    for child in item:
                        remove_bridge(child)

            remove_bridge(value)
            path.write_text(json.dumps(value))
            loaded, _saved = read_snapshot(path, self.scene.resources)
            self.assertEqual(loaded.caverns.bridge, Bridge())


class BridgeChasmTests(unittest.TestCase):
    def test_only_level_five_room_ten_refuses_the_down_cut(self):
        # CutChar 6:4cd2-4d0c: the bridge chasm kills instead of cutting.
        import struct
        from pop2.terrain import LevelMap

        for number, kind, room, allowed in ((5, 3, 9, False), (5, 3, 10, True), (4, 3, 9, True),
                                            (13, 3, 3, False), (5, 3, 9, True)):
            with self.subTest(number=number, room=room):
                level = bytearray(0x49ca)
                struct.pack_into('>H', level, 0x2186, kind)
                struct.pack_into('>H', level, 0x218a, number)
                actor = 2 if allowed and number == 5 and room == 9 else 0
                self.assertEqual(LevelMap(level).allows_down_cut(room, actor), allowed)


class BridgeTensionTests(unittest.TestCase):
    def test_tension_changes_level_and_accumulates_like_set_tension_level(self):
        # SetTensionLevel 6:5022: 2<->3 keeps tension less 10, other changes reset.
        bridge = Bridge()
        for _ in range(4):
            bridge.set_tension(2, 5)
        self.assertEqual((bridge.tension_level, bridge.tension), (2, 20))
        bridge.set_tension(3, 5)
        self.assertEqual((bridge.tension_level, bridge.tension), (3, 15))
        bridge.set_tension(1, -1)
        self.assertEqual((bridge.tension_level, bridge.tension), (1, 0))


@unittest.skipUnless((ASSET_DIR / 'caverns_level5.json').is_file(), 'Imported level-five resources required')
class BridgeGuardAiTests(unittest.TestCase):
    """8:02ae, 8:033c, 8:0424 and 8:04a2 on level five's bridge."""

    def setUp(self):
        BridgeSceneTests.setUp(self)
        self.scene.jump_to_room(9, 1, 30, 1)
        self.combat = self.scene.combat
        self.skeleton = self.combat.active_guards()[0]

    def tick(self, count=1):
        BridgeSceneTests.tick(self, count)

    def place(self, x, facing):
        self.skeleton.state.target_x = self.skeleton.state.current_x = x
        self.skeleton.state.facing = facing

    def test_engage_and_hold_follow_the_bridge_columns(self):
        combat, skeleton = self.combat, self.skeleton
        self.assertTrue(combat._bridge_fight_room(skeleton))
        self.place(60, 0)
        self.assertTrue(combat._bridge_engage(skeleton))
        for x in range(100, 200, 4):
            self.place(x, 0)
            if bridge_column(9, combat._supporting_column(skeleton)) in (2, 3):
                break
        self.assertFalse(combat._bridge_engage(skeleton))
        self.assertTrue(combat._bridge_holds(skeleton))
        self.place(440, 1)
        self.assertTrue(combat._bridge_engage(skeleton))

    def test_skeleton_turns_back_when_the_prince_hides_behind_room_sevens_gate(self):
        scene, skeleton = self.scene, self.skeleton
        scene.jump_to_room(6, 1, 400, 0)
        scene.game.caverns.plates.active[6, 13] = 0
        self.assertTrue(self.combat._kid_behind_bridge_gate())
        self.place(200, 0)
        self.assertFalse(skeleton.skeleton.bridge_guard(self.combat, skeleton))
        self.assertEqual((skeleton.state.facing, skeleton.state.target_x), (1, 210))


class BridgeRoomCutTests(unittest.TestCase):
    def test_bridge_room_opponents_always_follow_the_prince(self):
        # CutAllOpponents 6:4510-4540 for level five's rooms 7/10/12, row not 0.
        from types import SimpleNamespace
        from pop2.combat import opponent_follows_cut

        guard = SimpleNamespace(state=SimpleNamespace(action=171, target_x=300), generation_flags=0,
                                alive=False, native_alive=False, skeleton=None, sword_drawn=False, row=1)
        self.assertTrue(opponent_follows_cut(guard, 'left', 1, bridge_room=True))
        self.assertFalse(opponent_follows_cut(guard, 'left', 1))


@unittest.skipUnless((ASSET_DIR / 'caverns_level5.json').is_file(), 'Imported level-five resources required')
class BridgeSkeletonImmunityTests(unittest.TestCase):
    def test_bridge_skeleton_takes_no_sword_damage(self):
        # DecLifePts 4:34f2-352e returns before subtracting for a skeleton in
        # level five's bridge rooms (row not 0).
        BridgeSceneTests.setUp(self)
        scene = self.scene
        scene.jump_to_room(9, 1, 30, 1)
        skeleton = scene.combat.active_guards()[0]
        life = skeleton.life
        scene.combat._hurt('guard', skeleton, scene.combat.player)
        self.assertEqual(skeleton.life, life)
        self.assertTrue(skeleton.alive)

    def tick(self, count=1):
        BridgeSceneTests.tick(self, count)
