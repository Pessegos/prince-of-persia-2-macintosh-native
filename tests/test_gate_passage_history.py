"""An admitted body keeps its gate side during a tap, stop or pose change."""

import struct
from types import SimpleNamespace
import unittest

from pop2.paths import ASSET_DIR
from pop2.terrain import LevelMap


class GatePassageHistoryTests(unittest.TestCase):
    def setUp(self):
        self.level = bytearray(0x49ca)
        struct.pack_into('>H', self.level, 15 * 2, 4)
        self.state = SimpleNamespace(actor_type=0, source_sequence_id=13)
        self.before = (300, 148, 345, 226)

    def phase(self, position):
        struct.pack_into('>H', self.level, 0x780 + 15 * 4, position)

    def test_open_admission_survives_closure_and_any_unarmed_pose(self):
        for environment in (2, 4):
            struct.pack_into('>H', self.level, 0x2186, environment)
            terrain = LevelMap(self.level)
            self.phase(184)
            history = terrain.gate_passage_history(0, 1, self.before, self.before, (), self.state)
            self.assertEqual(history, ((0, 15),))
            for phase in (124, 64, 4, 0, 0):
                self.phase(phase)
                for sequence in (1, 13, 2, 5, 43, 50, 200, 201, 202):
                    self.state.source_sequence_id = sequence
                    for facing, x, after in ((1, 330, (300, 150, 350, 226)),
                                              (0, 320, (295, 150, 345, 226))):
                        with self.subTest(environment=environment, phase=phase,
                                          sequence=sequence, facing=facing):
                            history = terrain.gate_passage_history(0, 1, after, self.before,
                                                                    history, self.state)
                            self.assertEqual(history, ((0, 15),))
                            self.assertEqual(terrain.wall_correction(0, 325, x, after, self.before,
                                facing, 1, self.state, gate_passages=history), x)

    def test_cold_closed_overlap_keeps_recovery_and_cannot_gain_admission(self):
        struct.pack_into('>H', self.level, 0x2186, 2)
        terrain = LevelMap(self.level)
        self.phase(0)
        history = terrain.gate_passage_history(0, 1, self.before, self.before, (), self.state)
        self.assertEqual(history, ())
        after = (300, 150, 350, 226)
        self.assertLess(terrain.wall_correction(0, 325, 330, after, self.before,
            1, 1, self.state, gate_passages=history), 330)

    def test_clear_body_row_change_replacement_actor_and_arming_drop_admission(self):
        struct.pack_into('>H', self.level, 0x2186, 2)
        terrain = LevelMap(self.level)
        self.phase(184)
        history = terrain.gate_passage_history(0, 1, self.before, self.before, (), self.state)
        self.phase(0)
        for row, body, actor, armed in ((1, (340, 148, 365, 226), 0, False),
                                         (2, self.before, 0, False),
                                         (1, self.before, 2, False),
                                         (1, self.before, 0, True)):
            with self.subTest(row=row, actor=actor, armed=armed):
                self.state.actor_type = actor
                self.assertEqual(terrain.gate_passage_history(0, row, body, body,
                                                             history, self.state, armed), ())

    def test_descent_exemption_cannot_admit_a_body_through_a_closed_gate(self):
        struct.pack_into('>H', self.level, 0x2186, 2)
        self.phase(0)
        self.state.source_sequence_id = 68
        self.assertEqual(LevelMap(self.level).gate_passage_history(
            0, 1, self.before, self.before, (), self.state), ())
        self.phase(104)
        self.assertEqual(LevelMap(self.level).gate_passage_history(
            0, 1, self.before, (300, 200, 345, 226), (), self.state), ())

    def test_linked_throne_grille_never_receives_open_gate_admission(self):
        struct.pack_into('>H', self.level, 0x2186, 4)
        struct.pack_into('>H', self.level, 0x218a, 8)
        struct.pack_into('>H', self.level, 0x2080 + 7 * 8 + 2, 9)
        struct.pack_into('>H', self.level, 8 * 60 + 10 * 2, 4)
        struct.pack_into('>H', self.level, 0x780 + 8 * 120 + 10 * 4, 255)
        body = (560, 148, 595, 226)
        self.assertEqual(LevelMap(self.level).gate_passage_history(
            7, 1, body, body, (), self.state), ())

    def test_gate_identity_survives_the_horizontal_room_cut(self):
        struct.pack_into('>H', self.level, 0x2186, 2)
        struct.pack_into('>H', self.level, 0x2080 + 2, 2)
        struct.pack_into('>H', self.level, 60 + 10 * 2, 4)
        struct.pack_into('>H', self.level, 0x780 + 120 + 10 * 4, 184)
        terrain = LevelMap(self.level)
        body = (560, 148, 595, 226)
        history = terrain.gate_passage_history(0, 1, body, body, (), self.state)
        self.assertEqual(history, ((1, 10),))
        struct.pack_into('>H', self.level, 0x780 + 120 + 10 * 4, 0)
        shifted = (50, 148, 85, 226)
        self.assertEqual(terrain.gate_passage_history(1, 1, shifted, shifted, history, self.state), history)


@unittest.skipUnless((ASSET_DIR / 'temple_level12.json').is_file(), 'Imported temple artwork required')
class GateTapSceneTests(unittest.TestCase):
    def test_short_taps_stop_beyond_the_closed_gate_then_can_resume(self):
        from tools.audit_temple_routes import Harness, press

        harness = Harness(12, draw=True)
        scene = harness.scene
        try:
            for duration in (1, 2, 3, 4, 5, 6):
                with self.subTest(duration=duration):
                    scene.game.caverns.plates.active.clear()
                    scene.game.caverns.plates.foreground.clear()
                    scene.game.caverns.plates.foreground[(2, 18)] = 184
                    scene.jump_to_room(2, row=1, x=445, facing=1)
                    press(harness, 'R', True)
                    for tick in range(20):
                        if tick == duration:
                            press(harness, 'R', False)
                        harness.tick()
                        self.assertNotEqual(scene.sequence_state.source_sequence_id, 47)
                    self.assertEqual((scene.room_id, scene.terrain_motion.row,
                                      scene.player_x, scene.action), (10, 1, 15, 15))
                    self.assertEqual(scene.level_map.tile(2, 8, 1).foreground & 255, 0)
                    self.assertEqual(scene.terrain_motion.gate_passages, ())
                    press(harness, 'R', True)
                    harness.tick(3)
                    press(harness, 'R', False)
                    self.assertGreater(scene.player_x, 15)
                    self.assertTrue(scene.combat.player.alive)
        finally:
            harness.close()
