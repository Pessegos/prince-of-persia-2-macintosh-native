"""Ruins exit admission, half-life HUD and multi-head opponent selection."""

import struct
from types import SimpleNamespace
import unittest

from pop2.cavern_state import CavernState
from pop2.combat_art import HealthArtwork
from pop2.opponent_selection import nearest_opponent
from pop2.paths import ASSET_DIR
from pop2.terrain import LevelMap


class RuinsExitTests(unittest.TestCase):
    def fixture(self, number=8, room=0, entry=15):
        level = bytearray(0x49ca)
        struct.pack_into('>H', level, 0x2186, 4)
        struct.pack_into('>H', level, 0x218a, number)
        struct.pack_into('>H', level, 0x2198, entry + 1)
        struct.pack_into('>H', level, room * 60 + 15 * 2, 17)
        struct.pack_into('>5h', level, 0x1680, room + 1, 15, 0, -3, -3)
        terrain = LevelMap(level)
        terrain.caverns = CavernState()
        return terrain, terrain.caverns.plates

    def test_fresh_level_eight_exit_does_not_open_without_the_fathers_sword(self):
        terrain, plates = self.fixture()
        plates.trigger(terrain, 0, 5)
        self.assertNotIn((0, 15), plates.active)
        self.assertEqual(plates.songs, [])

    def test_entry_exit_and_other_levels_keep_their_ordinary_opening(self):
        for number, room in ((6, 0), (7, 0), (8, 15), (9, 0)):
            with self.subTest(number=number, room=room):
                terrain, plates = self.fixture(number, room)
                plates.trigger(terrain, 0, 5)
                self.assertEqual(plates.active[room, 15], 1)
                self.assertEqual(plates.songs, [297])

    def test_only_sword_one_unlocks_a_closed_exit_and_an_open_exit_does_not_restart(self):
        for sword in (-1, 0, 1, 2, 3):
            with self.subTest(sword=sword):
                terrain, plates = self.fixture()
                plates.trigger(terrain, 0, 5, sword_type=sword)
                self.assertEqual((0, 15) in plates.active, sword == 1)
                if sword == 1:
                    for _ in range(79):
                        plates.advance(terrain)
                    self.assertNotIn((0, 15), plates.active)
                    self.assertEqual(terrain.tile(0, 5, 1).foreground & 255, 79)
                    plates.songs.clear()
                    plates.trigger(terrain, 0, 5, sword_type=sword)
                    self.assertNotIn((0, 15), plates.active)
                    self.assertEqual(plates.songs, [])

    def test_locked_exit_does_not_block_other_destinations_in_the_same_chain(self):
        terrain, plates = self.fixture()
        struct.pack_into('>h', terrain.level, 0x1680 + 8, 1)
        struct.pack_into('>5h', terrain.level, 0x1680 + 10, 1, 16, 0, -3, -3)
        struct.pack_into('>H', terrain.level, 16 * 2, 4)
        plates.trigger(terrain, 0, 5, sword_type=2)
        self.assertNotIn((0, 15), plates.active)
        self.assertIn((0, 16), plates.active)

    def test_loose_floor_impact_obeys_the_same_sword_gate(self):
        for sword in (1, 2):
            with self.subTest(sword=sword):
                terrain, plates = self.fixture()
                struct.pack_into('>H', terrain.level, 14 * 2, 5)
                plates.impact(terrain, 0, 14, 5, sword_type=sword)
                self.assertEqual((0, 15) in plates.active, sword == 1)


class HeadMeterTests(unittest.TestCase):
    def drawn_opponent(self, kind, life):
        art = HealthArtwork.__new__(HealthArtwork)
        art.icons = {index: index for index in range(297, 301)}
        calls = []
        viewport = SimpleNamespace(paste=lambda icon, position, mask: calls.append((icon, position)))
        opponent = SimpleNamespace(life=life, state=SimpleNamespace(actor_type=kind))
        encounter = SimpleNamespace(player=SimpleNamespace(life=3, max_life=3),
                                    world_frame=0, health_opponent=lambda: opponent)
        art.draw(viewport, encounter)
        return calls[3:]

    def test_head_points_draw_full_and_half_bottles_at_native_positions(self):
        for kind in (7, 8):
            for life in range(9):
                with self.subTest(kind=kind, life=life):
                    shapes = [298] * (life // 2) + [297] * (life & 1)
                    self.assertEqual(self.drawn_opponent(kind, life),
                                     [(shape, (496 - index * 12, 368))
                                      for index, shape in enumerate(shapes)])

    def test_other_opponent_types_keep_one_bottle_per_point(self):
        for kind in (2, 4, 6):
            for life in range(5):
                with self.subTest(kind=kind, life=life):
                    self.assertEqual(self.drawn_opponent(kind, life),
                                     [(298, (496 - index * 12, 368)) for index in range(life)])


class HeadWaitingTests(unittest.TestCase):
    @staticmethod
    def actor(x, *, kind=8, mode=1):
        return SimpleNamespace(state=SimpleNamespace(target_x=x, current_y=-33, actor_type=kind),
                               row=1, room=0, alive=True, native_alive=None, skeleton=None,
                               ruins=SimpleNamespace(mode=mode))

    def test_fleeing_head_does_not_keep_the_next_head_waiting(self):
        player = self.actor(250, kind=0)
        for kind in (7, 8):
            for side, first_x, second_x in ((-1, 230, 170), (1, 270, 330)):
                with self.subTest(kind=kind, side=side):
                    first = self.actor(first_x, kind=kind, mode=2)
                    second = self.actor(second_x, kind=kind)
                    self.assertIs(nearest_opponent(player, [first, second], side), second)

    def test_recovered_head_can_compete_again_and_a_fleeing_serpent_is_not_a_head(self):
        player = self.actor(250, kind=0)
        first, second = self.actor(230), self.actor(170)
        self.assertIs(nearest_opponent(player, [first, second], -1), first)
        first.ruins.mode = 2
        self.assertIs(nearest_opponent(player, [first, second], -1), second)
        first.ruins.mode = 1
        self.assertIs(nearest_opponent(player, [first, second], -1), first)
        serpent = self.actor(230, kind=11, mode=2)
        self.assertIs(nearest_opponent(player, [serpent], -1), serpent)

    def test_zero_hp_keeps_its_native_slot_only_until_death_is_registered(self):
        player = self.actor(250, kind=0)
        first, second = self.actor(230), self.actor(170)
        first.alive = False
        first.ruins.dead_frames = -1
        self.assertIs(nearest_opponent(player, [first, second], -1), first)
        first.ruins.dead_frames = 0
        self.assertIs(nearest_opponent(player, [first, second], -1), second)
        first.alive = True  # HP cannot override a registered native death.
        self.assertIs(nearest_opponent(player, [first, second], -1), second)
        first.ruins.dead_frames, first.ruins.removed = -1, True
        self.assertIs(nearest_opponent(player, [first, second], -1), second)


@unittest.skipUnless((ASSET_DIR / 'Head.rsrc').is_file(), 'Imported game resources required')
class LevelEightHeadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pop2.game_session import GameResources

        cls.resources = GameResources.load()

    def setUp(self):
        from pop2.game_session import GameSession

        self.game = GameSession.load(self.resources, 8)
        self.game.sword_type = 1  # The throne vision has completed.
        self.combat = self.game.combat
        self.combat.enter_room(0, 1)  # Native level8 room1: three real heads.
        self.combat.player.state.target_x = self.combat.player.state.current_x = 220
        self.heads = self.combat.ruins.actors(0)
        self.assertEqual(len(self.heads), 3)

    def anger(self, actor):
        ruins = self.combat.ruins
        ruins.get_angry(actor, self.combat, ruins.prince(self.combat))

    def test_meter_hands_over_when_the_current_head_dies(self):
        first, _lower, second = self.heads
        first.state.target_x, second.state.target_x = 230, 300
        self.anger(first)
        self.anger(second)
        self.assertIs(self.combat.health_opponent(), first)
        first.life = 0
        self.combat.ruins.kill(first, self.combat)
        self.assertIs(self.combat.health_opponent(), second)

    def test_fleeing_head_leaves_the_meter_to_the_next_active_head(self):
        first, _lower, second = self.heads
        first.state.target_x, second.state.target_x = 230, 300
        self.anger(first)
        self.anger(second)
        first.ruins.mode, first.ruins.alert = 2, 1
        self.combat.ruins.banked = None
        self.assertIs(self.combat.health_opponent(), second)

    def test_meter_selects_the_nearby_row_instead_of_the_first_angry_head(self):
        first, lower, _second = self.heads
        self.anger(lower)
        self.anger(first)
        self.assertIs(self.combat.ruins.banked, lower)
        self.assertIs(self.combat.health_opponent(), first)

    def test_room_entry_does_not_keep_a_previous_rooms_banked_head(self):
        self.anger(self.heads[0])
        self.combat.enter_room(20, 0)
        self.assertIsNone(self.combat.ruins.banked)

    def test_sword_damage_preserves_the_native_half_point_units(self):
        head = self.heads[0]
        for sword, damage in ((2, 1), (1, 2)):
            with self.subTest(sword=sword):
                head.life = 4
                self.combat.ruins.stab(head, self.combat, sword)
                self.assertEqual(head.life, 4 - damage)

    def test_room_one_waiting_controller_advances_after_the_nearer_head_flees(self):
        first, _lower, second = self.heads
        ruins = self.combat.ruins
        for mode, sight, sequence in ((1, 4, 166), (2, 0, 142)):
            with self.subTest(mode=mode):
                first.state.target_x = first.state.current_x = 280
                second.state.target_x = second.state.current_x = 400
                self.anger(first)
                self.anger(second)
                first.ruins.mode, first.ruins.alert = mode, 3 if mode == 1 else 1
                ruins.jump(second, 165)
                second.runtime.next_frame()
                self.assertEqual(ruins.can_see(second, self.combat, ruins.prince(self.combat)), sight)
                ruins.control_head(second, self.combat)
                self.assertEqual(second.state.sequence_id, sequence)


@unittest.skipUnless((ASSET_DIR / 'ruins_level8.json').is_file(), 'Imported level-eight scenery required')
class LevelEightExitHostTests(unittest.TestCase):
    def test_throne_checkpoint_receives_the_sword_state_and_survives_retry(self):
        from unittest.mock import patch
        from pop2.environments import environment_for
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        with patch.object(scene, 'render'):
            scene.load_level(8)
            scene.peaceful = True
            scene.jump_to_room(8, 2, 290, 1)
            scene.advance_rebirth()
            self.assertIsNone(scene.checkpoint)
            environment_for(scene).wake_from_vision()
            scene.advance_rebirth()
            self.assertIsNotNone(scene.checkpoint)
            self.assertEqual(scene.checkpoint.checkpoint.slot, 1)
            scene.restart_level_now(redraw=False)
            self.assertEqual(scene.game.sword_type, 1)
            self.assertTrue(scene.game.caverns.throne_done)
            self.assertEqual(scene.room_id, 8)

    def test_actual_room_twenty_three_button_requires_the_throne_sword(self):
        from unittest.mock import patch
        from pop2.environments import environment_for
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        with patch.object(scene, 'render'):
            scene.load_level(8)
            scene.peaceful = True
            scene.jump_to_room(22, 2, 490, 1)
            RooftopSceneTests.tick(self, 10)
            plates = scene.game.caverns.plates
            button = scene.level_map.tile(22, 9, 2)
            self.assertTrue(button.foreground & 0x2000)
            self.assertEqual(scene.game.sword_type, 2)
            self.assertEqual(scene.level_map.tile(22, 2, 2).foreground & 255, 0)
            self.assertNotIn((22, 22), plates.active)

            scene.jump_to_room(8, 2, 267, 1)
            environment_for(scene).wake_from_vision()
            self.assertTrue(scene.game.caverns.throne_done)
            self.assertEqual(scene.game.sword_type, 1)
            scene.jump_to_room(22, 2, 490, 1)
            RooftopSceneTests.tick(self, 10)
            self.assertGreater(scene.level_map.tile(22, 2, 2).foreground & 255, 0)


if __name__ == '__main__':
    unittest.main()
