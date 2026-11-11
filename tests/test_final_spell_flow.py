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
        # SEQS 55's first AnimChar advances X from native 484 by six pixels.
        self.assertEqual((scene.sequence_state.target_x, scene.action), (283, 207))

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

    def test_room_two_full_animation_loop_with_audio_reaches_room_four(self):
        from unittest.mock import Mock, call
        from pop2.audio import AudioEngine

        scene = self.scene
        playback = Mock()
        playback.busy.return_value = False
        playback.playing_effects.return_value = ()
        scene.audio = AudioEngine(playback=playback)
        scene.schedule_next_animation = lambda: None
        for route in ('teleport', 'descent'):
            with self.subTest(route=route):
                if route == 'teleport':
                    scene.jump_to_room(1, row=1, x=250, redraw=False)
                else:
                    scene.jump_to_room(0, row=2, x=250, redraw=False)
                    scene.start_sequence(23)
                    scene.sequence_state.current_y = 100
                    scene.terrain_motion.falling = True
                for _ in range(30):
                    if scene.intro is not None:
                        break
                    scene.advance_animation()
                self.assertIsNotNone(scene.intro)
                self.assertEqual(scene.room_id, 1)
                for _ in range(240):
                    if scene.intro is None:
                        break
                    scene.last_intro_at -= .25
                    scene.advance_animation()
                self.assertIsNone(scene.intro)
                self.assertEqual(scene.room_id, 3)
                self.assertFalse(scene.in_animation_tick)
        self.assertIn(call('music', 'scene-0-31030'), playback.play.call_args_list)


if __name__ == '__main__':
    unittest.main()
