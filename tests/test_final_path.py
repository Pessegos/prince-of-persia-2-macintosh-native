"""The final Jaffar's palace path controller (CODE 9:16fe)."""

import unittest
from types import SimpleNamespace

from pop2.final_path import (
    KILL_SEQUENCE, SPELL_SEQUENCE, STOP, TURN, Controller, Figure, PathInfo,
    prince_in_range, prince_near)
from pop2.paths import ASSET_DIR

# Poses 120-159 lack FRAM flag 0x40 here; the spell poses (272-282) have it.
EXPOSED = ([SimpleNamespace(aux=0x40)] * 120 + [SimpleNamespace(aux=0)] * 40
           + [SimpleNamespace(aux=0x40)] * 260)


class Kid:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def call(*args):
            self.calls.append((name, *args))
        return call


def jaffar(**fields):
    values = dict(pose=15, selected=2, facing=-1, x=626, column=7, row=0, room=8)
    values.update(fields)
    return Figure(**values)


def prince(**fields):
    # Most decisions below need a Prince without a sword (armed -1): 9:16fe
    # closes in on no one else.
    values = dict(pose=15, selected=2, facing=0, x=300, column=2, row=0, room=8,
                  life=3, armed=-1)
    values.update(fields)
    return Figure(**values)


def run(j, p, info=None):
    kid = Kid()
    info = info if info is not None else PathInfo()
    events = Controller(j, p, info, EXPOSED, kid).run()
    return kid.calls, events, info


class DecisionTests(unittest.TestCase):
    def test_upper_right_casts_at_an_exposed_prince_on_the_upper_floor(self):
        calls, _events, info = run(jaffar(), prince())
        self.assertEqual(calls, [('select', SPELL_SEQUENCE)])
        self.assertEqual(info.mode, 2)
        # Facing away: he turns first (9:09ca).
        calls, _events, _info = run(jaffar(facing=0), prince())
        self.assertEqual(calls, [('select', TURN)])

    def test_a_prince_between_his_two_turned_positions_keeps_him_turning(self):
        # Original behaviour, kept: 9:09ca turns him toward the Prince's X
        # before casting, and SEQS 5 ends 9 pixels ahead in the new facing
        # (-5 12, 0, 3, -3, 0, -3). Native X 484 facing right turns to 475
        # facing left; a Prince standing still at 479 is behind him both
        # times, so he turns for as long as the Prince stays.
        p = prince(x=479, row=2, room=7, column=5)
        info = PathInfo(2, 2, 2)
        calls, _events, _info = run(jaffar(x=484, facing=0, row=2, room=7, column=5), p, info)
        self.assertEqual(calls, [('select', TURN)])
        calls, _events, _info = run(jaffar(x=475, facing=-1, row=2, room=7, column=5), p, info)
        self.assertEqual(calls, [('select', TURN)])

    def test_the_spell_strikes_at_pose_282_only_in_range(self):
        calls, events, _info = run(jaffar(pose=282, selected=SPELL_SEQUENCE), prince())
        self.assertEqual((calls, events), ([('select', KILL_SEQUENCE)], [('kill',)]))
        # 9:0bee-0c2c test Jaffar's own pose (-0x504c), not the Prince's:
        # crouching does not save the Prince, a crouching Jaffar is out of
        # range, and so is one in a pose without FRAM flag 0x40.
        _calls, events, _info = run(jaffar(pose=282, selected=SPELL_SEQUENCE),
                                    prince(pose=109))
        self.assertEqual(events, [('kill',)])
        self.assertFalse(prince_in_range(jaffar(pose=109), prince(), EXPOSED))
        self.assertFalse(prince_in_range(jaffar(pose=150), prince(), EXPOSED))
        self.assertTrue(prince_in_range(jaffar(), prince(pose=150), EXPOSED))
        _calls, events, _info = run(jaffar(pose=281, selected=SPELL_SEQUENCE), prince())
        self.assertEqual(events, [('sound', 289)])

    def test_over_the_defeated_prince_he_does_not_move(self):
        # Native room 11 after 9:0062: the Kid lies dead (life 0). With four
        # or more turns on his row the flee branch needs life above 2;
        # otherwise closing in may pick a target but moves only towards a
        # Prince with life, and CharDistance's life gate blocks the sword
        # dissolve. Playing his sequence there is the whole behaviour.
        room = 11
        for turns, armed, row in ((5, -1, 2), (0, -1, 2), (0, 1, 2), (6, 0, 2), (0, -1, 1)):
            dead = prince(life=0, room=room, row=row, column=6, x=513, turns=turns,
                          armed=armed, pose=185, selected=71)
            calls, events, _info = run(jaffar(room=room, row=2, column=4, x=430), dead)
            self.assertEqual((calls, events), ([], []), (turns, armed, row))

    def test_upper_floor_range_skips_the_middle_columns(self):
        self.assertTrue(prince_in_range(jaffar(column=3, room=8), prince(), EXPOSED))
        self.assertFalse(prince_in_range(jaffar(column=1, room=8), prince(), EXPOSED))
        self.assertTrue(prince_in_range(jaffar(column=6, room=7), prince(), EXPOSED))

    def test_a_prince_below_sends_him_to_the_previous_position(self):
        calls, _events, info = run(jaffar(), prince(row=2))
        self.assertEqual((info.pos, info.prev), (3, 0))
        # Route 3 from position 0 at global column 17: forward (6:11a0).
        self.assertEqual(calls, [('forward',)])

    def test_rapid_turns_on_his_row_make_him_flee(self):
        calls, _events, info = run(jaffar(), prince(turns=4, column=8, room=8, life=3))
        # Position 0's side +1 zone is row 0, columns 1-18.
        self.assertTrue(prince_near(0, 1, prince(column=8)))
        self.assertEqual((info.mode, info.pos), (1, 1))
        self.assertEqual(calls, [('descend',)])
        # Too weak to scare him: no decision this frame.
        calls, _events, info = run(jaffar(), prince(turns=4, life=2))
        self.assertEqual((calls, info.mode), ([], 0))

    def test_arrival_window_and_run_stop(self):
        info = PathInfo(mode=2, pos=3, prev=0)
        calls, _events, info = run(jaffar(room=7, column=5, x=580, facing=0),
                                   prince(row=2), info)
        self.assertEqual((calls, info.prev), ([], 3))
        info = PathInfo(mode=2, pos=3, prev=0)
        calls, _events, _info = run(jaffar(room=7, column=5, pose=7, selected=1),
                                    prince(row=2), info)
        self.assertEqual(calls, [('select', STOP)])

    def test_a_drawn_sword_within_91_pixels_is_taken(self):
        # 9:173e-17bc reads the opponent's +0x1a (-0x507a), the armed word,
        # not ALIVE (+0x1c): a living Prince with his sword drawn loses it.
        _calls, events, _info = run(jaffar(x=626), prince(armed=1, x=560))
        self.assertEqual(events, [('dissolve', 241, 264)])
        _calls, events, _info = run(jaffar(x=626), prince(armed=1, x=500))
        self.assertEqual(events, [])
        _calls, events, _info = run(jaffar(x=626, pose=158), prince(armed=1, x=560))
        self.assertEqual(events, [])

    def test_he_waits_while_the_prince_keeps_his_sword(self):
        # 9:17ec-17fc: closing in needs armed -1. A sheathed sword (0), or a
        # drawn one out of reach, leaves him standing; an earlier port
        # read ALIVE there and cast at any living Prince.
        for armed, x in ((0, 300), (0, 600), (1, 300)):
            with self.subTest(armed=armed, x=x):
                calls, events, info = run(jaffar(), prince(armed=armed, x=x))
                self.assertEqual((calls, events, info.mode), ([], [], 0))
        # Four rapid turns still make him flee from an armed Prince.
        _calls, _events, info = run(jaffar(), prince(armed=0, turns=4, column=8))
        self.assertEqual(info.mode, 1)


INSTALLED = all((ASSET_DIR / name).is_file() for name in (
    'Final.rsrc', 'final_level14.json'))


@unittest.skipUnless(INSTALLED, 'Imported Macintosh final level required')
class PalaceSceneTests(unittest.TestCase):
    def setUp(self):
        from tools.audit_temple_routes import Harness

        self.harness = Harness(14, peaceful=False)
        scene = self.scene = self.harness.scene
        scene.jump_to_room(5, row=2, x=420, facing=0, redraw=False)
        self.combat = scene.combat
        for figure in list(self.combat.room_encounters[5][0])[:3]:
            self.combat._hurt('guard', figure, self.combat.player)
        self.ticks(30)
        self.jaffar = self.combat.room_encounters[7][0][0]

    def lose_sword(self):
        # The state 9:177e leaves: no sword (armed -1).
        self.scene.sword_drawn = self.combat.player.sword_drawn = False
        self.combat.player.sword_lost = True

    def tearDown(self):
        self.harness.close()

    def ticks(self, count):
        for _ in range(count):
            self.harness.tick()

    def test_standing_on_his_floor_without_a_sword_is_fatal(self):
        self.scene.jump_to_room(7, row=0, x=200, facing=1, reset_guards=False, redraw=False)
        self.lose_sword()
        self.ticks(14)
        self.assertEqual(self.jaffar.state.selected_sequence_id, KILL_SEQUENCE)
        self.assertFalse(self.combat.player.alive)
        self.assertEqual(self.scene.death.method, 17)

    def test_a_prince_keeping_his_sword_has_time_for_the_turns(self):
        # The video's player stood on his floor while he waited, then he
        # fled. With the sword sheathed he never casts.
        from tests.test_final_magic import ShadowSceneTests

        self.scene.jump_to_room(7, row=0, x=200, facing=1, reset_guards=False, redraw=False)
        self.combat.player.life = self.combat.player.max_life = 12
        self.ticks(40)
        self.assertTrue(self.combat.player.alive)
        self.assertNotIn(self.jaffar.state.selected_sequence_id, (SPELL_SEQUENCE, KILL_SEQUENCE))
        ShadowSceneTests.turn(self, 4)
        self.ticks(1)
        self.assertEqual(self.jaffar.final_info.mode, 1)
        self.assertTrue(self.combat.player.alive)

    def test_he_passes_through_and_bumps_walls_unarmed(self):
        # FrameAdv 2:6cb4: the Kid-like actor 6 never stops the Prince, so
        # SEQS 241's stagger from x 400 carries him through and off the
        # floor. Jaffar follows him down; HitFloor 6:036a-0374 does not arm
        # actor 6, so his wall bump is the unarmed one (Collide 4:5910),
        # not an armed SEQS 64 that left him en garde for good.
        scene = self.scene
        scene.jump_to_room(7, row=0, x=400, facing=1, reset_guards=False, redraw=False)
        self.ticks(1)
        scene.sword_drawn = self.combat.player.sword_drawn = True
        sequences, rows = set(), set()
        for _ in range(60):
            self.ticks(1)
            sequences.add(self.jaffar.state.selected_sequence_id)
            rows.add(self.combat.player.row)
        self.assertIn(1, rows)
        self.assertIn(47, sequences)
        self.assertFalse(sequences & {64, 65})

    def test_his_reach_takes_a_drawn_sword_and_then_he_casts(self):
        scene = self.scene
        # From x 400, SEQS 241's stagger carries the Prince through him (the
        # Kid-like actor 6 never stops him, FrameAdv 2:6cb4) and off the
        # floor; from 380 it ends on his side.
        scene.jump_to_room(7, row=0, x=380, facing=1, reset_guards=False, redraw=False)
        self.ticks(1)
        scene.sword_drawn = self.combat.player.sword_drawn = True
        for _ in range(30):
            self.ticks(1)
            if self.combat.player.sword_lost:
                break
        self.assertTrue(self.combat.player.sword_lost)
        self.assertFalse(scene.sword_drawn)
        self.assertEqual(scene.sequence_state.selected_sequence_id, 241)
        # During SEQS 241 the Prince is out of his range (9:0bd8); after
        # it, unarmed, he casts.
        spell = None
        for tick in range(40):
            self.ticks(1)
            selected = scene.sequence_state.selected_sequence_id
            if self.jaffar.state.selected_sequence_id == SPELL_SEQUENCE and spell is None:
                spell = tick
                self.assertNotEqual(selected, 241)
        self.assertIsNotNone(spell)
        self.assertFalse(self.combat.player.alive)
        self.assertEqual(scene.death.method, 17)

    def test_in_the_left_view_he_waits_at_the_upper_right(self):
        self.scene.jump_to_room(6, row=0, x=100, facing=1, reset_guards=False, redraw=False)
        self.ticks(20)
        self.assertTrue(self.combat.player.alive)
        self.assertEqual((self.jaffar.room, self.jaffar.state.target_x), (7, 415))

    def test_a_prince_below_sees_him_run_to_the_left_view_and_climb_down(self):
        self.scene.jump_to_room(7, row=2, x=100, facing=1, reset_guards=False, redraw=False)
        self.lose_sword()
        for _ in range(60):
            self.harness.tick()
            if self.jaffar.room == 6:
                break
        self.assertEqual((self.jaffar.room, self.jaffar.row), (6, 0))
        # CutOpponent 6:42fc: once cut into room 7 he leaves the Prince's
        # active list, and his record waits there in the move he was in.
        state = self.jaffar.state
        held = (state.target_x, state.action, state.selected_sequence_id)
        self.ticks(40)
        self.assertEqual((state.target_x, state.action, state.selected_sequence_id), held)
        # Following him there, the Prince sees him finish the route and
        # climb down toward position 2.
        self.scene.jump_to_room(6, row=2, x=100, facing=1, reset_guards=False, redraw=False)
        rows = set()
        for _ in range(130):
            self.harness.tick()
            rows.add((self.jaffar.room, self.jaffar.row))
        self.assertIn((6, 1), rows)
        self.assertEqual((self.jaffar.final_info.prev, self.jaffar.final_info.pos), (3, 2))

    def test_a_fall_through_the_left_views_floor_ends_in_room_6_and_back_at_the_start(self):
        # Native room 7's row-2 gap (column 3) opens onto room 6. Cut 6:472a
        # in UpdateOppInfo moves the falling record there; the port kept him
        # in room 7 at row 3, out of every route. In room 6, 9:08e8 runs the
        # copies' 9:1526 for him: the last figure shimmers (SEQS 240) and
        # 9:19fa sends him to the palace start, path words kept.
        from pop2.final_tower import SHIMMER_SEQUENCE

        from pop2.combat import select_sequence

        combat, jaffar = self.combat, self.jaffar
        # A Prince keeping his sword on the upper floor: 9:16fe leaves the
        # run going, left along row 2 to the gap.
        self.scene.jump_to_room(6, row=0, x=60, facing=1, reset_guards=False, redraw=False)
        combat.room_encounters[7][0].remove(jaffar)
        combat.room_encounters[6][0].append(jaffar)
        jaffar.room, jaffar.row = 6, 2
        jaffar.state.target_x = jaffar.state.current_x = 260
        jaffar.state.facing = 0
        jaffar.terrain_motion = None
        jaffar.final_info = PathInfo(2, 2, 3)
        select_sequence(jaffar, 1)
        rows = set()
        for _ in range(40):
            self.ticks(1)
            rows.add((jaffar.room, jaffar.row))
            if jaffar.room != 6:
                break
        self.assertIn((6, 2), rows)
        self.assertEqual((jaffar.room, jaffar.row), (5, 0))
        self.assertIn(jaffar, combat.room_encounters[5][0])
        self.assertNotIn(jaffar, combat.room_encounters[6][0])
        self.scene.jump_to_room(5, row=0, x=60, facing=1, reset_guards=False, redraw=False)
        sequences = set()
        for _ in range(40):
            self.ticks(1)
            sequences.add(jaffar.state.selected_sequence_id)
            if jaffar.room == 7:
                break
        self.assertIn(SHIMMER_SEQUENCE, sequences)
        self.assertEqual((jaffar.room, jaffar.row, jaffar.state.target_x), (7, 0, 415))
        self.assertTrue(jaffar.final_path)
        # 9:185a put him at position 2 (prev = pos) before 9:19fa.
        self.assertEqual(jaffar.final_info, PathInfo(2, 2, 2))

    def test_away_from_the_palace_a_travelling_jaffar_is_put_at_his_target(self):
        info = self.jaffar.final_info
        info.mode, info.pos = 1, 2
        self.scene.jump_to_room(5, row=2, x=100, facing=1, reset_guards=False, redraw=False)
        self.ticks(2)
        self.assertEqual((self.jaffar.room, self.jaffar.row, info.prev), (6, 2, 2))
        self.assertEqual(self.jaffar.state.target_x + 207, 494)
        self.assertEqual(self.jaffar.state.facing, 1)


if __name__ == '__main__':
    unittest.main()
