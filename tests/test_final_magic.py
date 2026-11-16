"""The Prince's shadow and magic fire in the final tower (CODE 4:1fb2,
4:2174, 4:2206, 9:2674, 9:27a0, 9:24ee)."""

import unittest
from types import SimpleNamespace

from pop2.final_magic import (
    BURN_SEQUENCE, CAST_SEQUENCE, COLLAPSE_SEQUENCE, DEAD_POSE, REJOIN_SEQUENCE,
    Fireball, advance_fireball, body_distance, fireball_hits, throw_fireball, turn_flash)
from pop2.paths import ASSET_DIR


def pose(action, facing=1, x=300):
    return SimpleNamespace(action=action, facing=facing, target_x=x, current_y=0)


class RuleTests(unittest.TestCase):
    def test_turn_flashes_from_the_fourth_turn(self):
        self.assertFalse(any(turn_flash(action, 3) for action in range(45, 53)))
        self.assertEqual([turn_flash(action, 4) for action in range(46, 52)],
                         [True, False, False, True, False, False])
        self.assertEqual([turn_flash(action, 5) for action in range(46, 52)],
                         [True, False, True, False, True, False])
        self.assertEqual([turn_flash(action, 7) for action in range(46, 52)],
                         [True, True, False, True, True, False])

    def test_lying_down_keeps_the_distance_measured_before_turning(self):
        # 4:1f1e: a shadow in pose 185 facing away from the body turns,
        # steps 6 and moves by the distance taken before the turn
        # (17 + 7), not by one measured again (23 + 7).
        from tools.probe_final_body import port_crouch

        shadow = SimpleNamespace(target_x=121, facing=0, action=DEAD_POSE)
        body = SimpleNamespace(target_x=104, facing=1, action=DEAD_POSE)
        self.assertEqual(port_crouch(shadow, body, 0, 0), (COLLAPSE_SEQUENCE, 103, 1))
        shadow.action = 15
        self.assertEqual(port_crouch(shadow, body, 0, 0), (COLLAPSE_SEQUENCE, 103, 1))

    def test_a_fatal_eighth_turn_still_clears_the_count(self):
        # 4:1fb2: after a fatal DecLifePts(1), 4:203e still tests the eighth
        # turn; its low-life branch kills again and clears a5-0x5004.
        from tools.probe_final_magic import port_turn

        turn = port_turn(life=1, capacity=8, shadow=False, selected=5, mode=0, turns=7)
        self.assertEqual((turn.outcome[0], turn.turns, turn.life), ('kill', 0, 0))
        turn = port_turn(life=1, capacity=8, shadow=False, selected=5, mode=0, turns=5)
        self.assertEqual((turn.outcome, turn.turns), (['kill'], 6))

    def test_the_temples_flame_keeps_the_shadow_burning_at_low_life(self):
        # 3:0884 -> SetupShadowFlame 4:2630 draws the flame while
        # IsShadowImbued 4:2590: mode 13 at any life, else life above 2.
        from pop2.environments import Final
        from pop2.final_magic import FinalMagic

        magic = FinalMagic()
        magic.shadow = True
        scene = SimpleNamespace(game=SimpleNamespace(caverns=SimpleNamespace(final_magic=magic)),
                                combat=SimpleNamespace(player=SimpleNamespace(life=2)),
                                sequence_state=SimpleNamespace(sequence_mode=0))
        final = Final(scene)
        self.assertFalse(final.player_flame())
        scene.sequence_state.sequence_mode = 13
        self.assertTrue(final.player_flame())
        scene.combat.player.life = 3
        scene.sequence_state.sequence_mode = 0
        self.assertTrue(final.player_flame())
        magic.shadow = False
        self.assertFalse(final.player_flame())

    def test_body_distance_counts_six_more_facing_the_same_way(self):
        body = pose(185, facing=1, x=300)
        self.assertEqual(body_distance(pose(15, 1, 320), body, 1, 1), 14)
        self.assertEqual(body_distance(pose(15, 0, 320), body, 1, 1), 20)
        self.assertEqual(body_distance(pose(DEAD_POSE, 1, 320), body, 1, 1), 20)
        self.assertEqual(body_distance(pose(15, 1, 320), body, 1, 0), 999)

    def test_the_fire_accelerates_and_bursts_at_a_wall(self):
        ball = throw_fireball(pose(281, facing=1, x=100), 6, 0, 60)
        self.assertEqual((ball.x, ball.y, ball.speed), (143, 5, 12))
        speeds = []
        for _ in range(6):
            advance_fireball(ball, lambda room, column, row: False, 20)
            speeds.append(ball.speed)
        self.assertEqual(speeds, [15, 18, 21, 24, 27, 27])
        # 9:25e4: the cell at X - 22 + width; the burst is aligned to it.
        ball = Fireball(6, 300, 50, 0, 27)
        walls = {(6, 6)}
        sounds, ended = advance_fireball(ball, lambda room, column, row: (room, column) in walls, 20)
        self.assertEqual((ball.burst, ball.x, sounds, ended), (True, 328, [259], False))
        for _ in range(3):
            advance_fireball(ball, lambda *cell: False, 20)
        self.assertEqual(advance_fireball(ball, lambda *cell: False, 20), ([], True))
        self.assertFalse(ball.active)
        # Flying left, X - 22 - width; a negative lead is one column left.
        ball = Fireball(6, 40, 50, 0, -27)
        advance_fireball(ball, lambda room, column, row: column == -1, 20)
        self.assertEqual((ball.burst, ball.x), (True, -51 + 22 + 51))

    def test_the_fire_starts_in_state_two_and_resets_its_sounds(self):
        # 9:28d6: state 2; 9:2804/2664: PrinceResetSnd(258) when it leaves
        # the level, PrinceResetSnd(265), the cast's song, at a wall.
        from pop2.final_magic import fire_hits_wall

        ball = throw_fireball(pose(281, facing=1, x=100), 6, 0, 60)
        self.assertEqual((ball.frame, ball.shape), (2, 4117))
        sounds, resets = [], []
        # X 143 - 22 + 20 lies in column 2: a wall there bursts it at once.
        self.assertTrue(fire_hits_wall(ball, lambda room, column, row: column == 2, 20,
                                       sounds, resets))
        self.assertEqual((ball.burst, ball.x, sounds, resets), (True, 124, [259], [265]))
        ball = Fireball(None, 300, 50, 0, 27)
        resets = []
        self.assertEqual(advance_fireball(ball, lambda *cell: False, 20, resets), ([], True))
        self.assertEqual(resets, [258])

    def test_the_fire_span_reaches_seventeen_pixels(self):
        ball = Fireball(7, 380, 50, 0, 27)
        self.assertTrue(fireball_hits(ball, 0, 423, 460, 0))
        self.assertFalse(fireball_hits(ball, 0, 424, 460, 0))
        self.assertFalse(fireball_hits(ball, 1, 400, 460, 0))
        self.assertTrue(fireball_hits(Fireball(6, 480, 50, 0, 27), 0, 0, 40, -510))


INSTALLED = all((ASSET_DIR / name).is_file() for name in (
    'Final.rsrc', 'final_level14.json'))


@unittest.skipUnless(INSTALLED, 'Imported Macintosh final level required')
class ShadowSceneTests(unittest.TestCase):
    def setUp(self):
        from tools.audit_temple_routes import Harness

        self.harness = Harness(14, peaceful=False)
        self.scene = self.harness.scene
        self.combat = self.scene.combat

    def tearDown(self):
        self.harness.close()

    def environment(self):
        from pop2.environments import environment_for

        return environment_for(self.scene)

    def magic(self):
        return self.scene.game.caverns.final_magic

    def turn(self, count):
        """Presses the way he is not facing each frame until ``count`` more
        standing turns have begun."""
        from tools.audit_temple_routes import press

        scene = self.scene
        started = 0
        for _ in range(count * 6):
            if started == count:
                break
            key = 'L' if scene.sequence_state.facing else 'R'
            before = scene.sequence_state.facing
            magic = getattr(scene.game.caverns, 'final_magic', None)
            shadow = magic is not None and magic.shadow
            press(self.harness, key, True)
            self.harness.tick(1)
            press(self.harness, key, False)
            magic = scene.game.caverns.final_magic
            if (scene.sequence_state.facing != before or not scene.combat.player.alive
                    or magic.shadow != shadow):
                started += 1

    def test_eight_rapid_turns_leave_the_body_and_cost_eight_points(self):
        scene = self.scene
        scene.jump_to_room(3, row=1, x=277, facing=1, redraw=False)
        player = scene.combat.player
        player.life = player.max_life = 12
        self.turn(3)
        self.assertEqual((self.magic().turns, player.life), (3, 12))
        self.turn(4)
        self.assertEqual((self.magic().turns, player.life, player.max_life), (7, 8, 8))
        self.turn(1)
        magic = self.magic()
        self.assertTrue(magic.shadow)
        self.assertEqual(scene.sequence_state.actor_type, 1)
        self.assertEqual(magic.body.state.selected_sequence_id, COLLAPSE_SEQUENCE)
        self.harness.tick(6)
        # The falling body drains three more: 12 -> 4, as in the video.
        self.assertEqual(magic.body.state.action, DEAD_POSE)
        self.assertEqual((player.life, player.max_life), (4, 4))

    def test_a_weak_prince_collapses_on_the_eighth_turn(self):
        scene = self.scene
        scene.jump_to_room(3, row=1, x=277, facing=1, redraw=False)
        player = scene.combat.player
        player.life = player.max_life = 8
        self.turn(8)
        self.assertFalse(self.magic().shadow)
        self.assertFalse(player.alive)
        self.assertEqual(scene.sequence_state.selected_sequence_id, COLLAPSE_SEQUENCE)
        self.assertEqual(scene.death.method, 17)

    def test_crouching_on_the_body_rejoins_it(self):
        from tools.audit_temple_routes import press

        scene = self.scene
        scene.jump_to_room(3, row=1, x=277, facing=1, redraw=False)
        player = scene.combat.player
        player.life = player.max_life = 12
        self.environment().leave_body()
        self.harness.tick(8)
        press(self.harness, 'down', True)
        sequences = []
        for _ in range(8):
            self.harness.tick(1)
            sequences.append(scene.sequence_state.selected_sequence_id)
        self.assertIn(COLLAPSE_SEQUENCE, sequences)
        self.assertIn(REJOIN_SEQUENCE, sequences)
        self.assertFalse(self.magic().shadow)
        self.assertIsNone(self.magic().body)
        self.assertEqual(scene.sequence_state.actor_type, 0)
        self.assertTrue(player.alive)

    def test_a_dead_shadow_returns_to_the_dead_body(self):
        scene = self.scene
        scene.jump_to_room(3, row=1, x=277, facing=1, redraw=False)
        player = scene.combat.player
        player.life = player.max_life = 12
        self.environment().leave_body()
        self.harness.tick(8)
        scene.player_x = scene.sequence_state.target_x = 380
        player.life = 0
        self.harness.tick(2)
        self.assertFalse(self.magic().shadow)
        self.assertEqual((scene.sequence_state.action, scene.sequence_state.target_x),
                         (DEAD_POSE, 278))

    def test_a_shadow_falling_off_the_level_returns_to_the_body(self):
        # 4:36a2 -> 4:374a: below Y 730 with no room beneath, DecLifePts(100)
        # and, for the shadow (type 1), CutToKidRoom 4:2338. Port room 7's
        # row-2 gap at column 0 has no room below.
        scene = self.scene
        scene.jump_to_room(6, row=2, x=100, facing=1, redraw=False)
        player = scene.combat.player
        player.life = player.max_life = 12
        self.environment().leave_body()
        self.harness.tick(8)
        body = self.magic().body
        self.assertEqual((body.room, body.row), (6, 2))
        scene.jump_to_room(7, row=2, x=20, facing=0, reset_guards=False, redraw=False)
        for _ in range(40):
            self.harness.tick(1)
            if not self.magic().shadow:
                break
        self.assertFalse(self.magic().shadow)
        self.assertFalse(player.alive)
        self.assertEqual((scene.room_id, scene.terrain_motion.row), (6, 2))
        self.assertEqual(scene.sequence_state.actor_type, 0)

    def test_the_fire_burns_jaffar_and_ends_the_game(self):
        from tools.audit_temple_routes import press

        scene = self.scene
        combat = scene.combat
        scene.jump_to_room(5, row=2, x=420, facing=0, redraw=False)
        for figure in list(combat.room_encounters[5][0])[:3]:
            combat._hurt('guard', figure, combat.player)
        self.harness.tick(30)
        jaffar = combat.room_encounters[7][0][0]
        scene.jump_to_room(6, row=0, x=100, facing=1, reset_guards=False, redraw=False)
        combat.player.life = combat.player.max_life = 12
        self.environment().leave_body()
        self.harness.tick(6)
        life = combat.player.life
        press(self.harness, 'ctrl', True)
        self.harness.tick(2)
        press(self.harness, 'ctrl', False)
        self.assertEqual(scene.sequence_state.selected_sequence_id, CAST_SEQUENCE)
        self.assertEqual(combat.player.life, life - 2)
        burned = False
        for _ in range(60):
            self.harness.tick(1)
            burned = burned or jaffar.state.selected_sequence_id == BURN_SEQUENCE
            if scene.intro is not None:
                break
        self.assertTrue(burned)
        self.assertFalse(jaffar.alive)
        self.assertIsNotNone(scene.intro)

    def test_a_flask_after_a_miss_brings_back_the_glow_and_the_flame(self):
        # ChangeMeters 2:54fa -> 4:210a: the shadow's life crossing 2 sets
        # CTBL 2000 or 2001; SetupShadowFlame follows IsShadowImbued.
        from pop2.final_magic import GLOW_PALETTE, SHADOW_PALETTE

        scene = self.scene
        scene.jump_to_room(6, row=2, x=4 * 51 + 55, facing=0, reset_guards=False)
        player = self.combat.player
        player.life = player.max_life = 5
        self.harness.tick(1)
        self.environment().leave_body()
        self.harness.tick(8)
        # The falling body takes him from 5 to 2: the weak colours, no flame.
        magic = self.magic()
        self.assertEqual((player.life, magic.palette), (2, SHADOW_PALETTE))
        self.assertFalse(self.environment().player_flame())
        player.max_life = 4
        scene.shift_held = True
        self.harness.tick(40)
        self.assertEqual(scene.level_map.tile(6, 4, 2).kind, 1)
        self.assertEqual((player.life, magic.palette), (3, GLOW_PALETTE))
        self.assertTrue(self.environment().player_flame())

    def test_the_cast_keeps_the_glow_until_its_fire_ends(self):
        from pop2.final_magic import (
            CAST_SEQUENCE, GLOW_PALETTE, SHADOW_PALETTE, meter_palette)
        from tools.audit_temple_routes import press

        scene = self.scene
        player = self.combat.player
        scene.jump_to_room(6, row=0, x=100, facing=1, reset_guards=False, redraw=False)
        player.life = player.max_life = 12
        self.harness.tick(1)
        self.environment().leave_body()
        self.harness.tick(20)
        player.life = player.max_life = 4
        press(self.harness, 'ctrl', True)
        self.harness.tick(2)
        press(self.harness, 'ctrl', False)
        magic = self.magic()
        # The cast takes him to 2 (no flame: IsShadowImbued) but the glow
        # stays while the fire flies (4:210a skips SEQS 242); its end in a
        # wall loads CTBL 2000 (9:2838-2850).
        flying = []
        for _ in range(150):
            self.harness.tick(1)
            if magic.fireball is None and flying:
                break
            if magic.fireball is not None:
                flying.append(magic.palette)
        self.assertEqual(player.life, 2)
        self.assertTrue(flying)
        self.assertEqual(set(flying), {GLOW_PALETTE})
        self.assertEqual(magic.palette, SHADOW_PALETTE)
        self.assertFalse(self.environment().player_flame())


        self.assertIsNone(meter_palette(4, 2, CAST_SEQUENCE))
        self.assertEqual(meter_palette(2, 3, CAST_SEQUENCE), GLOW_PALETTE)
        self.assertIsNone(meter_palette(5, 3, 2))

    def test_without_life_to_spare_the_shadow_cannot_cast(self):
        from tools.audit_temple_routes import press

        scene = self.scene
        scene.jump_to_room(6, row=0, x=100, facing=1, redraw=False)
        player = scene.combat.player
        player.life = player.max_life = 5
        self.environment().leave_body()
        self.harness.tick(6)
        self.assertLessEqual(player.life, 2)
        press(self.harness, 'ctrl', True)
        self.harness.tick(2)
        self.assertNotEqual(scene.sequence_state.selected_sequence_id, CAST_SEQUENCE)
        self.assertFalse(scene.sword_drawn)


@unittest.skipUnless(INSTALLED, 'Imported Macintosh final level required')
class DefeatSceneTests(unittest.TestCase):
    """GenCtrl 6:0780-07a0 -> 9:0062: the defeated Kid lies in room 11."""

    def setUp(self):
        from tools.audit_temple_routes import Harness

        self.harness = Harness(14, peaceful=False)
        self.scene = self.harness.scene

    def tearDown(self):
        self.harness.close()

    def die(self, checkpoint=True):
        from pop2.environments import environment_for

        scene = self.scene
        scene.jump_to_room(3, row=1, x=218, facing=1, redraw=False)
        self.harness.tick(1)
        if checkpoint:
            scene.capture_rebirth_checkpoint(scene.checkpoints[0])
        environment_for(scene).kill_prince()
        trace = []
        for _ in range(20):
            self.harness.tick(1)
            trace.append((scene.death.counter, scene.room_id))
        return trace

    def test_with_a_rebirth_point_the_body_lies_before_the_laughing_jaffar(self):
        scene = self.scene
        trace = self.die()
        # The move waits for ALIVE > 6 (the counter after the death song).
        first = next(index for index, (_, room) in enumerate(trace) if room == 10)
        self.assertEqual(trace[first - 1], (6, 3))
        self.assertGreater(trace[first][0], 6)
        state = scene.sequence_state
        self.assertEqual((scene.terrain_motion.room, scene.terrain_motion.row), (10, 2))
        self.assertEqual((state.selected_sequence_id, state.action), (COLLAPSE_SEQUENCE, DEAD_POSE))
        self.assertEqual(scene.combat.player.room, 10)
        self.assertAlmostEqual(state.target_x, 306, delta=2)
        jaffar, = scene.combat.room_encounters[10][0]
        self.assertEqual((jaffar.state.actor_type, jaffar.state.selected_sequence_id), (6, 197))
        self.assertIn(jaffar.state.action, range(297, 301))

    def test_the_laugh_sounds_as_the_room_is_entered(self):
        from pop2.environments import environment_for

        scene = self.scene
        scene.jump_to_room(3, row=1, x=218, facing=1, redraw=False)
        self.harness.tick(1)
        scene.capture_rebirth_checkpoint(scene.checkpoints[0])
        environment_for(scene).kill_prince()
        sounds = []
        for _ in range(20):
            self.harness.tick(1)
            sounds.extend(scene.sequence_state.sound_events)
            scene.sequence_state.sound_events.clear()
            if scene.room_id == 10:
                break
        self.assertEqual(scene.room_id, 10)
        self.assertEqual(sounds.count(261), 1)

    def test_without_a_rebirth_point_the_body_stays(self):
        trace = self.die(checkpoint=False)
        self.assertEqual({room for _, room in trace}, {3})
        self.assertEqual(self.scene.sequence_state.action, DEAD_POSE)

    def test_the_retry_restarts_at_the_rebirth_point(self):
        scene = self.scene
        self.die()
        self.assertEqual(scene.room_id, 10)
        self.assertTrue(scene.death.can_restart)
        self.assertTrue(scene.restart_after_death())
        self.assertEqual(scene.room_id, 3)
        self.assertTrue(scene.combat.player.alive)


if __name__ == '__main__':
    unittest.main()
