"""The recovered room-2 Jaffar spell in a hidden level-14 scene."""

import unittest

from pop2.paths import ASSET_DIR


INSTALLED = all((ASSET_DIR / name).is_file() for name in (
    'Final.rsrc', 'final_level14.json', 'Happy.rsrc', 'final_spell.json'))


@unittest.skipUnless(INSTALLED, 'Imported Macintosh final spell and scenery required')
class FinalSpellFlowTests(unittest.TestCase):
    def setUp(self):
        from pop2.scene_prototype import ScenePrototype

        self.scene = ScenePrototype(peaceful=True, level_number=14)
        self.scene.root.withdraw()
        if self.scene.animation_after_id is not None:
            self.scene.root.after_cancel(self.scene.animation_after_id)
            self.scene.animation_after_id = None

    def tearDown(self):
        self.scene.root.destroy()

    def test_room_two_spell_enters_room_four_with_native_sequence_and_existing_life(self):
        from pop2.environments import Final, environment_for

        scene = self.scene
        scene.jump_to_room(1, row=1, x=250, redraw=False)
        scene.sequence_state.sequence_mode = 13
        scene.combat.player.life = 3
        self.assertIsInstance(environment_for(scene), Final)
        controller = Final(scene)
        controller.frame_start()
        controller.frame_hook()
        self.assertIsNotNone(scene.intro)
        self.assertEqual(scene.intro.program_kind, 'final_spell')
        scene.intro.advance(120)
        self.assertTrue(scene.intro.done)
        scene.finish_attract_stage()
        self.assertEqual((scene.room_id, scene.terrain_motion.row,
                          scene.sequence_state.source_sequence_id,
                          scene.sequence_state.sequence_mode,
                          scene.combat.player.life), (3, 1, 55, 13, 3))
        # 9:05de faces him right (word 0); SEQS 55's first AnimChar moves
        # X six pixels back from native 484.
        self.assertEqual(scene.sequence_state.facing, 1)
        self.assertEqual((scene.sequence_state.target_x, scene.action), (271, 207))

    def test_saved_room_edge_and_animation_gate(self):
        from pop2.environments import Final

        scene = self.scene
        controller = Final(scene)
        scene.jump_to_room(0, row=1, x=250, redraw=False)
        controller.frame_start()
        scene.jump_to_room(1, row=1, x=250, redraw=False)
        controller.frame_hook()
        self.assertIsNone(scene.intro)
        scene.jump_to_room(1, row=1, x=495, redraw=False)
        controller.frame_start()
        controller.frame_hook()
        self.assertIsNone(scene.intro)
        scene.jump_to_room(1, row=1, x=250, redraw=False)
        scene.sequence_state.animation_state = 4
        controller.frame_start()
        controller.frame_hook()
        self.assertIsNone(scene.intro)

    def test_native_right_edge_is_working_x_and_exclusive(self):
        """GetCharEdges 4:5d5a-5d6a stores the right edge as drawing X + 207,
        one past the last column. The old port compared its own inclusive
        drawing column with 486 directly, so any room-2 position admitted
        the spell."""
        from pop2.environments import Final

        scene = self.scene
        controller = Final(scene)
        scene.jump_to_room(1, row=0, x=298, redraw=False)
        controller.frame_start()
        room, right, _animation = scene.final_saved_prince
        self.assertEqual(right, scene.player_collision_bounds()[2] + 1 + 207)
        self.assertGreater(right, 486)
        controller.frame_hook()
        self.assertIsNone(scene.intro)

    def test_spell_reset_leaves_the_prince_armed_and_responsive(self):
        """9:05ec selects SEQS 55 with a5-0x503c = 1: the en-garde hold that
        SEQS 55 ends in answers only the armed controls. Without the sword
        flag no key left it, which froze the game in room 4."""
        from pop2.environments import Final

        scene = self.scene
        scene.peaceful = False
        scene.jump_to_room(1, row=0, x=240, redraw=False)
        Final(scene).finish_spell()
        self.assertTrue(scene.sword_drawn)
        self.assertIn(14, scene.sequence_state.sound_events)


@unittest.skipUnless(INSTALLED, 'Imported Macintosh final spell and scenery required')
class FinalSpellRouteTests(unittest.TestCase):
    """The video's route with real keys from the level's native entry."""

    # Step to the roof edge, turn, climb down and drop onto the sill.
    DESCENT = [(('shift', 'R'), (), 14), ((), ('R', 'shift'), 2), (('L',), (), 1),
               ((), ('L',), 10), (('down',), (), 20), ((), ('down',), 20)]
    WINDOW_STEP = [(('shift', 'L'), (), 14), ((), ('L', 'shift'), 2)]

    def setUp(self):
        from unittest.mock import Mock
        from pop2.audio import AudioEngine
        from tools.audit_temple_routes import Harness

        self.harness = Harness(14, peaceful=False)
        self.playback = Mock()
        self.playback.busy.return_value = False
        self.playback.playing_effects.return_value = ()
        self.harness.scene.audio = AudioEngine(playback=self.playback)

    def tearDown(self):
        self.harness.close()

    def play(self, script):
        from tools.audit_temple_routes import play

        play(self.harness, script)

    def test_landing_outside_waits_for_the_window_then_room_four_responds(self):
        from unittest.mock import call

        scene = self.harness.scene
        self.play(self.DESCENT)
        # Landed and crouched on the outside sill (video 00:43.5): no spell.
        self.assertEqual((scene.room_id, scene.terrain_motion.row), (1, 0))
        self.assertFalse(scene.terrain_motion.falling)
        self.assertIsNone(scene.intro)
        self.assertGreater(scene.final_saved_prince[1], 486)
        self.play([((), (), 30)])
        self.assertIsNone(scene.intro)
        # One step left carries him into the window (00:44-00:44.5).
        self.play(self.WINDOW_STEP)
        self.assertIsNotNone(scene.intro)
        self.assertEqual(scene.intro.program_kind, 'final_spell')
        self.assertLessEqual(scene.final_saved_prince[1], 486)
        for _ in range(400):
            if scene.intro is None:
                break
            self.harness.tick()
        self.assertIsNone(scene.intro)
        self.assertIn(call('music', 'scene-0-31030'), self.playback.play.call_args_list)
        self.assertEqual((scene.room_id, scene.terrain_motion.row), (3, 1))
        self.play([((), (), 20)])
        self.assertEqual(scene.action, 171)
        # Retreat, sheathe, turn and run: each key must leave the hold.
        x = scene.sequence_state.target_x
        self.play([(('L',), (), 4), ((), ('L',), 8)])
        self.assertLess(scene.sequence_state.target_x, x)
        self.play([(('down',), (), 2), ((), ('down',), 20)])
        self.assertFalse(scene.sword_drawn)
        x = scene.sequence_state.target_x
        self.play([(('L',), (), 12), ((), ('L',), 2)])
        self.assertEqual(scene.sequence_state.facing, 0)
        self.assertLess(scene.sequence_state.target_x, x - 20)
        self.assertTrue(scene.combat.player.alive)


if __name__ == '__main__':
    unittest.main()
