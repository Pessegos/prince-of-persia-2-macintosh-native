"""Jaffar's false Princes in native room 6 (CODE 9:1526, CheckStab 6:52b8)."""

import unittest
from types import SimpleNamespace

from pop2.final_tower import (
    LAUGH_SEQUENCE, SHEATHE_SEQUENCE, SHIMMER_SEQUENCE, STRIKE_SEQUENCE,
    PrinceView, copy_control)
from pop2.paths import ASSET_DIR


def copy(x=300, facing=1, action=15, selected=2, row=2, alive=True):
    state = SimpleNamespace(target_x=x, facing=facing, action=action,
                            selected_sequence_id=selected)
    return SimpleNamespace(alive=alive, room=5, row=row, state=state)


def prince(x=360, facing=1, action=1, alive=-1, selected=1, animation=0,
           actor_type=0, row=2):
    return PrinceView(alive, selected, actor_type, action, animation, facing,
                      5, row, x)


EXPOSED = [SimpleNamespace(aux=0x40)] * 8 + [SimpleNamespace(aux=0)] * 300


class CopyControlTests(unittest.TestCase):
    def test_strikes_an_exposed_prince_ahead_in_the_native_window(self):
        for x, expected in ((339, None), (340, STRIKE_SEQUENCE),
                            (385, STRIKE_SEQUENCE), (386, None)):
            decision = copy_control(copy(), prince(x=x), 4, EXPOSED)
            self.assertEqual(decision.sequence, expected, x)
        decision = copy_control(copy(), prince(), 4, EXPOSED)
        self.assertEqual((decision.x_offset, decision.sword_drawn, decision.turn),
                         (15, True, False))

    def test_an_unexposed_or_dead_prince_is_safe(self):
        self.assertIsNone(copy_control(copy(), prince(action=20), 4, EXPOSED).sequence)
        self.assertIsNone(copy_control(copy(), prince(alive=3), 4, EXPOSED).sequence)
        self.assertIsNone(copy_control(copy(), prince(animation=4), 4, EXPOSED).sequence)
        self.assertIsNone(copy_control(copy(), prince(row=1), 4, EXPOSED).sequence)

    def test_turns_on_a_prince_behind_it(self):
        decision = copy_control(copy(), prince(x=250, facing=0), 4, EXPOSED)
        self.assertEqual((decision.sequence, decision.turn), (STRIKE_SEQUENCE, True))

    def test_last_figure_shimmers_and_the_shadow_does_not_count(self):
        self.assertEqual(copy_control(copy(), prince(action=20), 1, EXPOSED).sequence,
                         SHIMMER_SEQUENCE)
        self.assertEqual(copy_control(copy(), prince(action=20, actor_type=1), 2,
                                      EXPOSED).sequence, SHIMMER_SEQUENCE)
        # 9:157a-1580 falls through to the pose tests: no second SEQS 240.
        self.assertIsNone(copy_control(copy(selected=SHIMMER_SEQUENCE), prince(action=20), 1,
                                       EXPOSED).sequence)
        # Not while the Prince is dying.
        self.assertIsNone(copy_control(copy(action=20), prince(alive=0), 1,
                                       EXPOSED).sequence)

    def test_en_garde_sheathes_and_pose_52_laughs_after_his_death(self):
        decision = copy_control(copy(action=171), prince(), 4, EXPOSED)
        self.assertEqual((decision.sequence, decision.sword_drawn),
                         (SHEATHE_SEQUENCE, False))
        self.assertIsNone(copy_control(copy(action=52), prince(), 4, EXPOSED).sequence)
        decision = copy_control(copy(action=52), prince(alive=1), 4, EXPOSED)
        self.assertEqual((decision.sequence, decision.sound), (LAUGH_SEQUENCE, 261))


INSTALLED = all((ASSET_DIR / name).is_file() for name in (
    'Final.rsrc', 'final_level14.json'))


@unittest.skipUnless(INSTALLED, 'Imported Macintosh final level required')
class CopyRoomSceneTests(unittest.TestCase):
    def setUp(self):
        from tools.audit_temple_routes import Harness

        self.harness = Harness(14, peaceful=False)
        self.scene = self.harness.scene
        self.scene.jump_to_room(5, row=2, x=420, facing=0, redraw=False)
        self.combat = self.scene.combat
        self.copies = list(self.combat.room_encounters[5][0])

    def tearDown(self):
        self.harness.close()

    def ticks(self, count):
        for _ in range(count):
            self.harness.tick()

    def test_one_hit_dissolves_a_copy_and_the_last_one_leaves_for_room_eight(self):
        self.assertEqual(len(self.copies), 4)
        for figure in self.copies[:3]:
            event = self.combat._hurt('guard', figure, self.combat.player)
            self.assertEqual(event.kind, 'death')
            self.assertEqual(figure.state.selected_sequence_id, 196)
        self.ticks(6)
        remaining = self.combat.room_encounters[5][0]
        self.assertEqual(remaining, [self.copies[3]])
        self.assertEqual(remaining[0].state.selected_sequence_id, SHIMMER_SEQUENCE)
        self.ticks(20)
        self.assertEqual(self.combat.room_encounters[5][0], [])
        moved = self.combat.room_encounters[7][0]
        self.assertEqual([(f.row, f.state.target_x, f.final_path) for f in moved],
                         [(0, 415, True)])

    def test_a_copy_that_kills_him_stays_while_the_others_shimmer(self):
        killer = self.copies[0]
        event = self.combat._hurt('player', self.combat.player, killer)
        self.assertEqual(event.death_method, 17)
        self.ticks(20)
        self.assertEqual(self.combat.room_encounters[5][0], [killer])

    def test_a_crouching_prince_ahead_is_struck_and_the_copy_laughs(self):
        from tools.audit_temple_routes import play

        scene = self.scene
        scene.jump_to_room(5, row=2, x=360, facing=1, reset_guards=False, redraw=False)
        killer = self.copies[0]
        play(self.harness, [(('down',), (), 12), ((), ('down',), 20)])
        self.assertFalse(self.combat.player.alive)
        self.assertEqual(self.combat.room_encounters[5][0], [killer])
        self.assertEqual(killer.state.selected_sequence_id, LAUGH_SEQUENCE)


if __name__ == '__main__':
    unittest.main()
