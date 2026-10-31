import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pop2.bridge import (
    bridge_column, BREAK_SONG, BREAK_SOUND, CREAK_SOUND, PLANK_FRAMES, Bridge, bridge_checked,
    bridge_engage,
)
from pop2.combat import select_sequence
from pop2.paths import ASSET_DIR


class BridgeEngageRuleTests(unittest.TestCase):
    """8:02ae (tools/probe_bridge_engage.py: 1,244,160 native cases)."""

    def engage(self, column, facing_right, room=9, dx=-100, opponent_room=9, opponent_column=5,
               armed=True, gate=False, level=2, tension=20):
        return bridge_engage(room, column, facing_right, 300 + dx, opponent_room,
                             opponent_column, 300, armed, gate, level, tension)

    def test_facing_left_presses_from_column_eight(self):
        self.assertEqual([self.engage(c, False) for c in (7, 8)], [False, True])
        # Rooms 7 and 12 continue room 10's columns.
        self.assertTrue(self.engage(0, False, room=11))
        self.assertFalse(self.engage(9, False, room=6))
        # The swapped sides the port used before: right from 8, left below 2.
        self.assertFalse(self.engage(9, True, armed=False))
        self.assertFalse(self.engage(0, False))

    def test_facing_right_presses_at_the_left_end_or_toward_the_gate(self):
        self.assertEqual([self.engage(c, True, armed=False) for c in (1, 2)], [True, False])
        self.assertTrue(self.engage(5, True, armed=False, gate=True, opponent_room=6,
                                    opponent_column=9))
        self.assertFalse(self.engage(5, True, armed=False, gate=True, opponent_column=2))

    def test_facing_right_presses_an_armed_opponent_ahead_on_a_taut_bridge(self):
        self.assertTrue(self.engage(5, True))
        for change in (dict(armed=False), dict(dx=-204), dict(dx=0), dict(opponent_column=7),
                       dict(level=1), dict(tension=19)):
            self.assertFalse(self.engage(5, True, **change), change)


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

    def test_characters_mark_their_plank_and_its_neighbours(self):
        # 8:0534-057c and MarkBridgeForCol 8:05cc.
        bridge = Bridge()
        for prince, opponent, marks in ((4, 5, 0xff), (4, None, 0x1c), (None, 1, 0x03),
                                        (8, None, 0xc0), (None, None, 0)):
            bridge.creak(prince, opponent, True)
            self.assertEqual(bridge.marks, marks)

    def test_marked_planks_wobble_for_one_frame_on_a_high_roll(self):
        # ATMBrgFloor 8:06d8-0764: Rnd(3) >= 2 lifts (1) or drops (2) a
        # resting marked plank; a wobbling plank rests on the next frame.
        bridge = Bridge(marks=0x1c, pieces={5: 2})
        bridge.advance_wobble(FixedRandom(2, 3))
        self.assertEqual(bridge.wobble, {3: 1, 4: 2})
        bridge.advance_wobble(FixedRandom(3, 3))
        self.assertEqual(bridge.wobble, {})
        rng = FixedRandom(1, 0)
        bridge.advance_wobble(rng)
        self.assertEqual((bridge.wobble, rng.calls), ({}, [(0, 3), (0, 3)]))


@unittest.skipUnless((ASSET_DIR / 'caverns_level5.json').is_file(), 'Imported level-five resources required')
class BridgeSceneryTests(unittest.TestCase):
    def test_wobbling_planks_match_the_native_redraw(self):
        # A native room-10 redraw with plank 3's nibble at 1 or 2.
        from pop2.caverns import cavern_assets, with_plank_wobble

        program, resources, _palette, _shapes = cavern_assets(5)
        plank = next(command for command in program['rooms']['9']
                     if command[1] == 4226 and command[8] == 3)
        self.assertEqual(with_plank_wobble([plank], {(3, 1)}, resources),
                         [['back', 4227, 153, 247, 16, 1, [215, 153, 247, 242], 4, 3, 1]])
        self.assertEqual(with_plank_wobble([plank], {(3, 2)}, resources),
                         [['back', 4228, 153, 248, 16, 1, [215, 153, 248, 243], 4, 3, 1]])
        self.assertEqual(with_plank_wobble([plank], {(4, 2)}, resources), [plank])

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
        # The chasm has no floor: the Prince dies below room 10, and that
        # fatal fall raises tension level 3.
        scene.god_mode = False
        self.tick(30)
        self.assertTrue(scene.terrain_motion.dead)
        self.assertEqual(scene.terrain_motion.room, 9)
        self.assertEqual((bridge.tension_level, bridge.tension), (3, 5))

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


def bridge_level(number=5):
    import struct

    level = bytearray(0x49ca)
    struct.pack_into('>H', level, 0x2186, 3)
    struct.pack_into('>H', level, 0x218a, number)
    return level


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

    def test_no_floor_of_the_linked_room_catches_the_prince_below_the_chasm(self):
        # CutChar 6:4d5a-4d66 leaves him in room 0: he falls to Y 730 and dies
        # instead of landing, unseen, on the floor of room 11 below.
        import struct
        from pop2.cavern_state import CavernState
        from pop2.sequence_runtime import SequenceRuntime, SequenceState
        from pop2.terrain import LevelMap, RooftopPhysics, TerrainMotion

        sequences = {7: (-7, 4, 102, -1, 7), 17: (-7, 1, 109, -1, 17), 22: (-7, 1, 185, -1, 22)}
        for number, expected in ((5, 'death'), (4, 'land')):
            with self.subTest(number=number):
                level = bridge_level(number)
                struct.pack_into('>H', level, 0x2080 + 9 * 8 + 6, 11)
                struct.pack_into('>H', level, 10 * 60 + 4 * 2, 1)
                level_map = LevelMap(level)
                level_map.caverns = CavernState()
                physics, motion = RooftopPhysics(level_map), TerrainMotion(9, 2, falling=True)
                runtime = SequenceRuntime(sequences, SequenceState(
                    7, target_x=250, current_x=250, facing=1, actor_type=0, vertical_velocity=20))
                runtime.next_frame()
                kinds = []
                for _ in range(20):
                    kinds += [event.kind for event in physics.advance(
                        motion, runtime, runtime.state.target_x, (240, 300, 270, 360))]
                    if not motion.falling or motion.dead:
                        break
                self.assertEqual(kinds[-1], expected)
                self.assertNotIn('land' if number == 5 else 'death', kinds)


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


class BridgeFallTests(unittest.TestCase):
    """StartFall 4:4c4a-4ca4, SetKidDeathMethod 4:31b4-31d6 and Catch 4:382c-3880."""

    SEQUENCES = {7: (-7, 4, 102, -1, 7), 19: (-7, 4, 102, -1, 19), 22: (-7, 1, 185, -1, 22),
                 198: (-7, 5, 100, -1, 198), 228: (-7, 4, 102, -1, 228)}

    def setUp(self):
        from pop2.cavern_state import CavernState
        from pop2.terrain import LevelMap, RooftopPhysics

        self.map = LevelMap(bridge_level())
        self.map.caverns = CavernState()
        self.physics = RooftopPhysics(self.map)

    def fall(self, room=9, facing=1, held=0, sword_drawn=False, action=15, actor_type=0):
        from pop2.sequence_runtime import SequenceRuntime, SequenceState
        from pop2.terrain import TerrainMotion

        runtime = SequenceRuntime(self.SEQUENCES, SequenceState(
            2, action=action, target_x=250, current_x=250, facing=facing, actor_type=actor_type))
        self.physics.held_direction = held
        self.physics.start_fall(TerrainMotion(room, 1), runtime, sword_drawn)
        return runtime.state

    def test_holding_the_direction_behind_the_prince_turns_him_back_in_room_ten(self):
        self.assertEqual(self.fall(facing=1, held=-1).selected_sequence_id, 198)
        self.assertEqual(self.fall(facing=0, held=1).selected_sequence_id, 198)
        for room, facing, held, actor_type in ((9, 1, 1, 0), (9, 0, -1, 0), (9, 1, 0, 0),
                                               (8, 1, -1, 0), (9, 1, -1, 4)):
            with self.subTest(room=room, facing=facing, held=held, actor_type=actor_type):
                self.assertEqual(self.fall(room, facing, held, actor_type=actor_type).selected_sequence_id, 7)
        self.map.level = bridge_level(4)
        self.assertEqual(self.fall(facing=1, held=-1).selected_sequence_id, 7)

    def test_the_turn_back_skips_the_hang_release_pose_adjustment(self):
        # StartFall 4:4cb6 bypasses the pose table, including pose 81's +24.
        state = self.fall(facing=1, held=-1, action=81)
        self.assertEqual((state.selected_sequence_id, state.current_y), (198, -120))
        self.assertEqual(self.fall(facing=1, action=81).current_y, -96)

    def test_tension_three_turns_back_an_armed_prince_facing_right(self):
        bridge = self.map.caverns.bridge
        bridge.tension_level, bridge.tension = 3, 20
        self.assertEqual(self.fall(facing=1, sword_drawn=True).selected_sequence_id, 198)
        self.assertEqual(self.fall(facing=1).selected_sequence_id, 7)
        self.assertEqual(self.fall(facing=0, sword_drawn=True).selected_sequence_id, 7)
        bridge.tension = 15
        self.assertEqual(self.fall(facing=1, sword_drawn=True).selected_sequence_id, 7)
        bridge.tension_level, bridge.tension = 2, 40
        self.assertEqual(self.fall(facing=1, sword_drawn=True).selected_sequence_id, 7)

    def test_a_fatal_fall_into_the_chasm_raises_tension_level_three(self):
        from pop2.sequence_runtime import SequenceRuntime, SequenceState
        from pop2.terrain import TerrainMotion, VOID_DEATH_Y, floor_y

        for room, expected in ((9, (3, 5)), (8, (0, 0))):
            with self.subTest(room=room):
                self.setUp()
                motion = TerrainMotion(room, 1, falling=True)
                runtime = SequenceRuntime(self.SEQUENCES, SequenceState(
                    7, action=102, target_x=200, current_x=200, facing=1, actor_type=0,
                    animation_state=4, vertical_velocity=30,
                    # Ordinary unlinked room9 continues in native room0
                    # with Y-360; the bridge's vetoed down cut does not.
                    current_y=VOID_DEATH_Y + (360 if room == 8 else 0) - floor_y(1) + 10))
                events = self.physics.advance(motion, runtime, 200, (190, 300, 230, 360))
                self.assertEqual([event.kind for event in events], ['death'])
                bridge = self.map.caverns.bridge
                self.assertEqual((bridge.tension_level, bridge.tension), expected)

    def catch(self, x, solid, tension=(3, 40), room=9):
        from pop2.animation_data import FrameRecord
        from pop2.sequence_runtime import SequenceState
        import struct

        for column in solid:
            struct.pack_into('>H', self.map.level, room * 60 + column * 2, 1)
        bridge = self.map.caverns.bridge
        bridge.tension_level, bridge.tension = tension
        state = SequenceState(7, action=102, target_x=x, current_x=x, facing=0, vertical_velocity=20)
        caught = self.map.catch_ledge(room, 1, state, FrameRecord(102, 0, 0, 0, 0, 0))
        return caught, state.target_x

    def test_tension_forty_extends_a_left_facing_catch_forward(self):
        # From x 285 the ordinary look-behind tests column 5; the reach of
        # 25 pixels tests column 4, whose left neighbour is solid.
        self.assertEqual(self.catch(285, (3,), tension=(3, 35)), (False, 285))
        self.assertEqual(self.catch(285, (3,), tension=(2, 40)), (False, 285))
        self.assertEqual(self.catch(285, (3,)), (True, 277))

    def test_the_catch_reach_is_not_used_from_the_first_three_columns(self):
        self.assertEqual(self.catch(132, (0,)), (False, 132))


@unittest.skipUnless((ASSET_DIR / 'caverns_level5.json').is_file(), 'Imported level-five resources required')
class BridgeTensionPersistenceTests(unittest.TestCase):
    def test_tension_survives_a_restart_but_not_a_new_level(self):
        # RestartGame 2:5b66 reloads the level and clears the bridge (2:6e38)
        # but never SetTensionLevel's globals; the next-level opcode -16
        # (4:2f5a) resets them.
        from pop2.game_session import GameResources, GameSession

        resources = GameResources.load()
        game = GameSession.load(resources, 5)
        game.caverns.bridge.set_tension(3, 15)
        game.caverns.bridge.state = 2
        game.restart()
        bridge = game.caverns.bridge
        self.assertEqual((bridge.state, bridge.tension_level, bridge.tension), (0, 3, 15))
        fresh = GameSession.load(resources, 5).caverns.bridge
        self.assertEqual((fresh.tension_level, fresh.tension), (0, 0))


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
        # 8:02c2-0332 (native facing word -1 = left): facing left the
        # skeleton presses from column 8 on, facing right below column 2.
        # The port had the two sides swapped until 2026-10-31.
        self.place(440, 0)
        self.assertTrue(combat._bridge_engage(skeleton))
        self.place(60, 1)
        self.assertTrue(combat._bridge_engage(skeleton))
        self.place(60, 0)
        self.assertFalse(combat._bridge_engage(skeleton))
        self.place(440, 1)
        self.assertFalse(combat._bridge_engage(skeleton))
        for x in range(100, 200, 4):
            self.place(x, 0)
            if bridge_column(9, combat._supporting_column(skeleton)) in (2, 3):
                break
        self.assertFalse(combat._bridge_engage(skeleton))
        self.assertTrue(combat._bridge_holds(skeleton))

    def test_skeleton_turns_back_when_the_prince_hides_behind_room_sevens_gate(self):
        scene, skeleton = self.scene, self.skeleton
        scene.jump_to_room(6, 1, 400, 0)
        scene.game.caverns.plates.active[6, 13] = 0
        self.assertTrue(self.combat._kid_behind_bridge_gate())
        self.place(200, 0)
        self.assertFalse(skeleton.skeleton.bridge_guard(self.combat, skeleton))
        self.assertEqual((skeleton.state.facing, skeleton.state.target_x), (1, 210))

    def test_a_pressing_skeleton_does_not_turn_to_a_prince_behind_it(self):
        # SwordCtrl 6:22b4-22e4: in the bridge rooms (row not 0) an engaging
        # skeleton (8:02ae) keeps its inputs; otherwise DoTurn selects SEQS 60.
        combat, skeleton = self.combat, self.skeleton
        player = combat.player
        skeleton.sword_drawn, skeleton.alert_mode = True, 3
        selected = []
        player.state.target_x = player.state.current_x = 20
        for x, facing in ((50, 1), (470, 1)):
            self.place(x, facing)
            skeleton.state.action, skeleton.state.animation_state = 158, 0
            skeleton.selected_sequence = None
            self.assertEqual(combat._bridge_engage(skeleton), x == 50)
            combat.choose_guard_action(skeleton)
            selected.append(skeleton.selected_sequence)
        self.assertNotEqual(selected[0], 60)
        self.assertEqual(selected[1], 60)


    def test_a_pressing_prince_does_not_turn_to_the_skeleton_behind_him(self):
        # SwordCtrl 6:22b4-22e4 asks 8:02ae for the Prince as well: facing
        # left from bridge column 8 on, he keeps his inputs (OnAlert) rather
        # than turning to the skeleton behind him; nearer the middle he turns.
        combat, skeleton, player = self.combat, self.skeleton, self.combat.player
        player.sword_drawn = skeleton.sword_drawn = True
        skeleton.alert_mode = 3
        turns = []
        for x in (440, 200):
            select_sequence(player, 227)
            player.runtime.next_frame()
            player.state.facing, player.state.animation_state = 0, 1
            player.state.target_x = player.state.current_x = x
            self.place(x + 40, 0)
            column = bridge_column(player.room, combat._supporting_column(player))
            self.assertEqual(combat._bridge_engage(player, skeleton, skeleton), column >= 8)
            turns.append(combat.choose_player_turn())
        self.assertEqual(turns, [False, True])

@unittest.skipUnless((ASSET_DIR / 'caverns_level5.json').is_file(), 'Imported level-five resources required')
class BridgeSwordLossTests(unittest.TestCase):
    """DoClimbUp 6:19aa-19c4, GenCtrl 6:0c70 and the hit re-arm 6:53f8-5406."""

    def setUp(self):
        BridgeSceneTests.setUp(self)

    def tick(self, count=1):
        BridgeSceneTests.tick(self, count)

    def climb(self, room=9, lost=False):
        import copy

        scene = self.scene
        scene.jump_to_room(room, 2, 200, 0)
        scene.combat.player.sword_lost = lost
        scene.combat.choose_guard_action = lambda guard=None: None
        for guard in scene.combat.active_guards():
            guard.state.target_x = guard.state.current_x = 450
        if room == 9:
            scene.game.caverns.bridge.pieces.update({column: 1 for column in range(3, 8)})
        state = scene.sequence_state
        state.current_y, state.action, state.facing = -24, 106, 0
        for x in range(120, 480):
            trial = copy.deepcopy(state)
            trial.target_x = trial.current_x = x
            if scene.level_map.catch_ledge(room, 2, trial, scene.frames[106]):
                break
        else:
            self.skipTest('no ledge to catch in this room')
        state.target_x = state.current_x = x
        scene.terrain_motion.row = 2
        self.assertTrue(scene.level_map.catch_ledge(room, 2, state, scene.frames[106]))
        scene.player_x = state.target_x
        scene.in_animation_tick = True
        scene._begin_native_ledge(15)
        scene.shift_held = scene.up_held = True
        sequences = []
        for _ in range(20):
            self.tick()
            sequences.append(state.sequence_id)
            if 235 in sequences:
                break
        scene.shift_held = scene.up_held = False
        return sequences

    def test_climbing_out_of_the_chasm_drops_the_sword(self):
        scene = self.scene
        sequences = self.climb()
        self.assertIn(236, sequences)
        self.assertNotIn(10, sequences)
        self.assertTrue(scene.combat.player.sword_lost)
        self.tick(12)
        self.assertFalse(scene.queue_sword_action("sword_draw"))
        self.tick(4)
        self.assertFalse(scene.sword_drawn)
        # Without a sword, a climb in room 10 is the ordinary SEQS:10.
        self.assertIn(10, self.climb(lost=True))

    def test_a_sword_hit_re_arms_a_prince_who_lost_his_sword(self):
        self.scene.jump_to_room(9, 1, 30, 1)
        combat = self.scene.combat
        combat.player.sword_lost = True
        guard = combat.active_guards()[0]
        combat._hurt('player', combat.player, guard)
        self.assertFalse(combat.player.sword_lost)
        self.assertTrue(combat.player.sword_drawn)


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

    def test_bridge_skeleton_has_no_opponent_meter(self):
        # DrawOppMeter 3:4b7a-4ba8 erases the meter for a skeleton in level
        # five's bridge rooms (row not 0) instead of drawing its life.
        BridgeSceneTests.setUp(self)
        scene = self.scene
        scene.jump_to_room(9, 1, 30, 1)
        skeleton = scene.combat.active_guards()[0]
        self.assertIsNone(scene.combat.health_opponent())
        skeleton.row = 0
        self.assertIs(scene.combat.health_opponent(), skeleton)

    def tick(self, count=1):
        BridgeSceneTests.tick(self, count)
