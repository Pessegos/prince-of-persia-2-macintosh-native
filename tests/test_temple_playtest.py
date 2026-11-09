"""The user's temple playtest reports of 2026-11-06, in the real hidden scene."""

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pop2.combat import select_sequence
from pop2.coordinates import column_left
from pop2.loose_floors import FallingFloor, floor_hits_body, floor_hits_record
from pop2.opponent_records import CORPSE_POSES, GuardRoomRecord, corpse_sequence
from pop2.paths import ASSET_DIR
from pop2.wall_spikes import WallSpikes
from tools.audit_temple_routes import Harness, press

TEMPLE_INSTALLED = all((ASSET_DIR / name).is_file()
                       for name in ('temple_level10.json', 'Temple.rsrc', 'Birdhead.rsrc'))


class TempleSpikeDrawingTests(unittest.TestCase):
    def commands(self, value, **options):
        terrain = SimpleNamespace(neighbor=lambda _room, _side: None)
        spikes = WallSpikes(foreground={(13, 22): value})
        return list(spikes.drawing_commands(terrain, 13, **options))

    def test_the_temple_binds_its_own_banks_and_origin(self):
        # 10:1296 and TriggerSpikes 5:40d6-411e. Before, the temple drew the
        # caverns' SHAP 3575 (a scenery piece) at the caverns' origin.
        self.assertEqual(self.commands(2, temple=True),
                         [['back', 3608, 2 * 51 + 66 + 5, 2 * 120 + 105 - 13, 16]])
        self.assertEqual(self.commands(2, front=True, temple=True),
                         [['front', 3614, 2 * 51 + 66 - 1, 2 * 120 + 105 - 2, 16]])

    def test_the_caverns_keep_theirs(self):
        self.assertEqual(self.commands(2), [['back', 3573, 2 * 51 + 63 + 12, 2 * 120 + 106 - 14, 16]])

    def test_a_retracted_trap_draws_nothing_in_either(self):
        self.assertEqual(self.commands(0, temple=True), [])


class CorpseSequenceTests(unittest.TestCase):
    def test_birdheads_have_four_flat_corpses_by_slot(self):
        # 4:00ac with set 7: base 191, modulo five; slot 0 stays on pose 185.
        self.assertEqual([corpse_sequence(7, 2, slot) for slot in range(6)],
                         [None, 191, 192, 193, 194, None])

    def test_ordinary_guards_keep_slot_parity(self):
        self.assertEqual([corpse_sequence(0, 1, slot) for slot in range(3)], [None, 195, None])

    def test_no_variant_on_level_kind_six_or_other_sets(self):
        self.assertIsNone(corpse_sequence(0, 6, 1))
        self.assertIsNone(corpse_sequence(2, 3, 1))

    def test_a_reloaded_birdhead_corpse_stays_dead(self):
        for pose in range(252, 256):
            self.assertIn(pose, CORPSE_POSES)


class RecordContactTests(unittest.TestCase):
    def test_temple_body_contact_does_not_depend_on_the_advancing_foot(self):
        block = FallingFloor(12, 5, 1, 186, 48)
        motion = SimpleNamespace(room=12, row=1)
        self.assertTrue(floor_hits_body(block, motion, (300, 169, 325, 226)))
        self.assertFalse(floor_hits_body(block, motion, (342, 169, 365, 226)))
        self.assertFalse(floor_hits_body(block, motion, (300, 169, 325, 226), alive=False))
        self.assertFalse(floor_hits_body(block, SimpleNamespace(room=13, row=1), (300, 169, 325, 226)))
        self.assertFalse(floor_hits_body(block, SimpleNamespace(room=12, row=0), (300, 49, 325, 106)))

    def test_contact_needs_the_column_and_a_crossing_of_the_head(self):
        floor = 226  # floor_y(1)
        hit = FallingFloor(12, 5, 1, floor - 56, 8)
        self.assertTrue(floor_hits_record(hit, 1, 302))
        self.assertFalse(floor_hits_record(FallingFloor(12, 4, 1, floor - 56, 8), 1, 302))
        self.assertFalse(floor_hits_record(FallingFloor(12, 5, 1, floor - 57, 8), 1, 302))
        self.assertFalse(floor_hits_record(FallingFloor(12, 5, 1, floor - 56 + 32, 8), 1, 302))


@unittest.skipUnless(TEMPLE_INSTALLED, 'Imported temple resources required')
class TemplePlaytestTests(unittest.TestCase):
    def harness(self, number=10, **options):
        options.setdefault('peaceful', True)
        harness = Harness(number, draw=True, **options)
        self.addCleanup(harness.close)
        return harness

    def test_standing_jump_from_14_turns_the_guard_when_the_prince_lands_behind(self):
        harness = self.harness(peaceful=False)
        scene = harness.scene
        scene.jump_to_room(13, row=2, x=330, facing=0)
        scene.physics.select(scene.sequence_runtime, 3)
        scene.action = scene.sequence_state.action
        harness.tick(45)
        self.assertEqual((scene.room_id, scene.terrain_motion.row), (12, 1))
        guard = scene.combat.active_guards()[0]
        self.assertEqual(guard.state.facing, 0, 'the landing behind him must make him turn left')
        self.assertTrue(guard.sword_drawn)

    def test_recoiling_guard_falls_into_the_wall_spikes(self):
        harness = self.harness(peaceful=False)
        scene = harness.scene
        scene.jump_to_room(12, row=1, x=270, facing=1)
        guard = scene.combat.active_guards()[0]
        guard.state.target_x = guard.state.current_x = 340
        guard.state.facing = 0
        guard.sword_drawn = True
        select_sequence(guard, 104)
        guard.runtime.next_frame()
        # Supply the combat recoil only; real FRAM/AFRM, floor alignment,
        # falling and wall-spike activation/contact run normally.
        with patch.object(scene.combat, 'choose_guard_action', return_value=None):
            for _ in range(12):
                harness.tick()
                if not guard.alive:
                    break
        self.assertFalse(guard.alive, 'the guard landed beyond the spikes')
        self.assertEqual(scene.level_map.tile(12, 6, 2).foreground & 255, 240)
        self.assertIn(guard.state.source_sequence_id, (188, 189))
        self.assertTrue(guard.terrain_motion.dead)

    def test_a_nonfatal_hit_knocks_the_guard_onto_the_wall_spikes(self):
        harness = self.harness(peaceful=False)
        scene = harness.scene
        scene.jump_to_room(12, row=1, x=290, facing=1)
        guard = scene.combat.active_guards()[0]
        scene.sword_drawn = scene.combat.player.sword_drawn = True
        guard.state.target_x = guard.state.current_x = 360
        guard.state.facing = 0
        guard.sword_drawn = True
        select_sequence(guard, 90)
        guard.runtime.next_frame()
        # Supply one successful strike, then retain the real AI, hit recovery,
        # floor checks, falling and trap lifecycle (the user's follow-up clip).
        scene.combat._hurt('guard', guard, scene.combat.player)
        self.assertEqual(guard.state.source_sequence_id, 183)
        self.assertTrue(guard.alive, 'the sword hit itself must be nonfatal')
        fell = False
        for _ in range(15):
            harness.tick()
            if guard.terrain_motion.falling and guard.alive:
                fell = True
                self.assertFalse(guard.sword_drawn, 'StartFall must put the sword away')
            if not guard.alive:
                break
        self.assertTrue(fell)
        self.assertFalse(guard.alive, 'the struck guard landed beside the spikes')
        self.assertEqual(scene.level_map.tile(12, 6, 2).foreground & 255, 240)
        self.assertIn(guard.state.source_sequence_id, (188, 189))
        self.assertTrue(guard.terrain_motion.dead)

    def test_running_prince_still_dies_on_these_wall_spikes_without_god_mode(self):
        harness = self.harness()
        scene = harness.scene
        scene.jump_to_room(12, row=1, x=200, facing=1)
        press(harness, 'R', True)
        for _ in range(45):
            harness.tick()
            if not scene.combat.player.alive:
                break
        self.assertFalse(scene.combat.player.alive)
        self.assertEqual(scene.level_map.tile(12, 6, 2).foreground & 255, 240)

    def catch_room14_floor(self, harness, x=270):
        # Last falling frame of the jump, before the vertical cut 14 -> 13.
        # The real Catch/AnimChar aligns the grip to floor 14:25 at X 281.
        scene = harness.scene
        scene.jump_to_room(13, row=2, x=x, facing=1)
        scene.physics.select(scene.sequence_runtime, 21)
        scene.sequence_state.current_y = 100
        scene.sequence_state.vertical_velocity = 8
        scene.terrain_motion.falling = True
        scene.action = scene.sequence_state.action
        press(harness, 'shift', True)
        harness.tick()
        self.assertEqual(scene.room_id, 12)
        self.assertTrue(scene.native_ledge)
        return scene

    def test_the_falling_grabbed_floor_drops_the_prince_and_kills_the_guard(self):
        harness = self.harness(peaceful=False)
        scene = self.catch_room14_floor(harness)
        guard = scene.combat.active_guards()[0]
        self.assertTrue(guard.alive)
        collapsed = released = None
        for tick in range(40):
            harness.tick()
            if collapsed is None and scene.level_map.tile(13, 5, 2).kind == 0:
                collapsed = tick
            if released is None and not scene.native_ledge:
                released = tick
        self.assertIsNotNone(collapsed)
        self.assertIsNotNone(released, 'the Prince still hangs after his support has fallen')
        self.assertLessEqual(released, collapsed + 1)
        self.assertTrue(scene.shift_held, 'letting go must not require releasing Shift')
        self.assertFalse(scene.ledge_hanging)
        self.assertEqual(scene.terrain_motion.row, 1)
        self.assertTrue(scene.combat.player.alive)
        # Deliberate port behavior requested by the user: keep the debris
        # lethal here even though his Macintosh recording leaves the guard alive.
        self.assertFalse(guard.alive)
        self.assertIn(guard.state.action, CORPSE_POSES)

    def test_an_intact_temple_ledge_keeps_its_grip(self):
        harness = self.harness(peaceful=False)
        # The same geometry with a permanent floor must keep hanging.
        harness.scene.game.caverns.loose.tiles[13, 25] = 1, 0
        scene = self.catch_room14_floor(harness)
        harness.tick(24)
        self.assertEqual(scene.level_map.tile(13, 5, 2).kind, 1)
        self.assertTrue(scene.native_ledge)

    def run_onto_door(self, harness, *, shift):
        # Trap door 12:27, entered at a run from the west along row 2.
        scene = harness.scene
        scene.jump_to_room(11, row=2, x=column_left(4) + 25, facing=1)
        harness.tick(3)
        press(harness, 'R', True)
        for _ in range(40):
            harness.tick()
            if scene.level_map.tile(11, 7, 2).kind != 26:
                break
        self.assertEqual(scene.level_map.tile(11, 7, 2).kind, 0, 'the door never opened')
        press(harness, 'R', False)
        if shift:
            press(harness, 'shift', True)
        return scene

    def test_running_onto_a_trap_door_opens_it_and_drops_the_prince(self):
        harness = self.harness()
        scene = self.run_onto_door(harness, shift=False)
        door = scene.game.caverns.trapdoors.bank[0]
        self.assertEqual(door[7], 1, 'A door under his own column starts at phase 1')
        harness.tick(3)
        self.assertTrue(scene.terrain_motion.falling)

    def test_an_open_trap_door_cannot_be_grabbed(self):
        # IsLedge 4:3f58-3f6e. Holding Shift all the way down: without the
        # rule he caught the far edge of the door.
        harness = self.harness()
        scene = self.run_onto_door(harness, shift=True)
        for _ in range(12):
            harness.tick()
            self.assertFalse(scene.native_ledge or scene.ledge_hanging)
            if scene.terrain_motion.room != 11:
                break
        self.assertNotEqual(scene.terrain_motion.room, 11)

    def test_check_trap_door_admits_a_foot_on_the_floor_of_a_closed_door(self):
        # CheckTrapDoor 10:2540: FRAM bit 0x40, exact floor height, tile 26 with
        # a clear low foreground, any actor but the shadow (type 1).
        harness = self.harness()
        scene = harness.scene
        terrain, doors = scene.level_map, scene.game.caverns.trapdoors
        motion = SimpleNamespace(room=11, row=2)
        record = scene.frames[15]
        foot = SimpleNamespace(aux=record.aux | 0x40, offset_x=record.offset_x)
        x = column_left(7) + 25

        def actor(**changes):
            return SimpleNamespace(**{'actor_type': 2, 'target_x': x, 'facing': 1, 'current_y': 0,
                                      **changes})

        self.assertEqual(doors.check(terrain, motion, actor(actor_type=1), foot), ())
        self.assertEqual(doors.check(terrain, motion, actor(current_y=-1), foot), ())
        self.assertEqual(doors.check(terrain, motion, actor(),
                                     SimpleNamespace(aux=0, offset_x=record.offset_x)), ())
        self.assertEqual(terrain.tile(11, 7, 2).kind, 26)
        self.assertEqual(doors.check(terrain, motion, actor(), foot), (197,))
        self.assertEqual(terrain.tile(11, 7, 2).kind, 0)
        self.assertEqual(doors.bank[0][7], 1)

    def test_each_frame_checks_the_door_under_a_guard_too(self):
        # FrameAdv 2:6642 runs CheckTrapDoor for each opponent as well.
        harness = self.harness(peaceful=False)
        scene = harness.scene
        scene.jump_to_room(12, row=1, x=column_left(2) + 25, facing=1)
        harness.tick(2)
        doors = scene.game.caverns.trapdoors
        with patch.object(type(doors), 'check', return_value=()) as check:
            harness.tick()
        guard = scene.combat.active_guards()[0]
        self.assertIn(guard.state, [call.args[2] for call in check.call_args_list])

    def test_a_block_falling_into_the_next_room_kills_its_sleeping_guard(self):
        # Loose 14:25 over guard 13's column 5, the Prince above in room 14.
        # MakeRubble 5:3602-362c reaches the saved record; before, only actors
        # in the Prince's own bank were tested and the guard survived.
        harness = self.harness()
        scene = harness.scene
        scene.jump_to_room(13, row=1, x=column_left(1) + 25, facing=1)
        harness.tick(2)
        tile = scene.level_map.tile(13, 5, 2)
        self.assertEqual(tile.kind, 11)
        scene.game.caverns.loose.trigger(tile, force=1)
        for _ in range(60):
            harness.tick()
            if not scene.game.caverns.loose.falling:
                break
        guards = scene.combat.room_encounters[12][0]
        self.assertEqual(len(guards), 1)
        self.assertFalse(guards[0].alive)
        record = guards[0].guard_record
        self.assertEqual((record.sequence, record.cursor, record.pending), (22, 0, True))
        scene.jump_to_room(12, row=1, x=column_left(2) + 25, facing=1, reset_guards=False)
        harness.tick(12)
        self.assertEqual(guards[0].state.action, 185)
        self.assertFalse(guards[0].alive)
        self.assertFalse(guards[0].targetable)

    def test_a_block_falling_on_a_guard_in_his_own_room_still_kills_him(self):
        harness = self.harness(peaceful=False)
        scene = harness.scene
        scene.jump_to_room(12, row=1, x=column_left(2) + 25, facing=1)
        harness.tick(2)
        guard = scene.combat.active_guards()[0]
        scene.game.caverns.loose.trigger(scene.level_map.tile(13, 5, 2), force=1)
        for _ in range(60):
            harness.tick()
            if not guard.alive:
                break
        self.assertFalse(guard.alive)

    def test_the_second_birdhead_of_a_room_lies_down(self):
        # GetOppDeadSeq on set 7: slot 1 is SEQS 191, pose 252. SEQS 195's
        # pose 228 is an upright frame in Birdhead.rsrc.
        harness = self.harness()
        scene = harness.scene
        scene.jump_to_room(12, row=1, x=column_left(2) + 25, facing=1)
        harness.tick(2)
        combat = scene.combat
        guard = combat.active_guards()[0]
        guard.bank_slot = 1
        guard.state.select(22)
        guard.runtime.next_frame()
        self.assertEqual(guard.state.action, 185)
        combat._select_guard_corpse_pose(guard)
        self.assertEqual((guard.state.sequence_id, guard.state.action), (191, 252))
        art = scene.guard_art
        body = art.body(guard.state, guard.palette_variant)
        self.assertGreater(body.width, body.height)
        guard.state.select(195)
        guard.runtime.next_frame()
        upright = art.body(guard.state, guard.palette_variant)
        self.assertGreater(upright.height, upright.width)

    def test_a_room_record_restores_the_temple_corpse(self):
        harness = self.harness()
        scene = harness.scene
        scene.jump_to_room(12, row=1, x=column_left(2) + 25, facing=1)
        harness.tick(2)
        guard = scene.combat.active_guards()[0]
        self.assertTrue(GuardRoomRecord(22, 0, 0, False, 10).restore(guard, 1, opponent_set=7))
        self.assertEqual(guard.state.sequence_id, 191)
        self.assertFalse(guard.native_alive)

    def test_every_temple_screen_has_a_development_entry(self):
        # Before, all but the rooms with floor in column 9 refused the warp.
        for number in (10, 11, 12, 13):
            with self.subTest(level=number):
                harness = Harness(number, peaceful=True, draw=True)
                try:
                    scene = harness.scene
                    screens = scene.dev_screens()
                    self.assertGreaterEqual(len(screens), 26)
                    for label, room in screens.items():
                        scene.jump_to_screen(label)
                        self.assertEqual(scene.terrain_motion.room, room, label)
                finally:
                    harness.close()

    def test_a_temple_wall_trap_comes_out_of_the_wall(self):
        # Room 14 cell 22. Drawing commands alone do not show that the pieces
        # exist in Temple.rsrc or reach the frame, so check the pixels.
        harness = self.harness()
        scene = harness.scene
        terrain = scene.level_map
        scene.jump_to_room(13, row=1, x=column_left(1) + 25, facing=1)
        harness.tick(2)
        spikes = scene.game.caverns.spikes
        tile = terrain.tile(13, 2, 2)
        self.assertEqual(tile.kind, 2)
        spikes.trigger(tile)
        harness.tick(1)
        key = 13, 22
        self.assertTrue(spikes.foreground[key] & 255)
        for front in (False, True):
            commands = list(spikes.drawing_commands(terrain, 13, front, temple=True))
            self.assertEqual(len(commands), 1)
            self.assertGreaterEqual(commands[0][1], 3604)
        rest = scene.background.crop((100, 270, 240, 370)).tobytes()
        spikes.foreground[key] = 3
        drawn = scene.level_renderer.animated_layer(
            scene.background.copy(), 13, None, caverns=scene.game.caverns)
        self.assertNotEqual(drawn.crop((100, 270, 240, 370)).tobytes(), rest)


if __name__ == '__main__':
    unittest.main()
