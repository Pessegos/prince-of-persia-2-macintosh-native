"""Level 14 route rules found by playing native room 1 to Jaffar."""

import unittest

from PIL import Image, ImageChops

from pop2.paths import ASSET_DIR


INSTALLED = all((ASSET_DIR / name).is_file() for name in (
    'Final.rsrc', 'final_level14.json'))


@unittest.skipUnless(INSTALLED, 'Imported Macintosh final level required')
class FinalRouteTests(unittest.TestCase):
    def setUp(self):
        from tools.audit_temple_routes import Harness

        self.harness = Harness(14, peaceful=False)
        self.scene = self.harness.scene
        self.combat = self.scene.combat

    def tearDown(self):
        self.harness.close()

    def test_room_three_refuses_its_right_exit(self):
        # CutChar 6:4c50-4c6c: environment 6 never cuts native room 3 to
        # room 9; the same edge cuts on any other level kind.
        from pop2.sequence_runtime import SequenceState
        from pop2.terrain import TerrainMotion

        for kind, allowed in ((6, False), (5, True)):
            with self.subTest(level_kind=kind):
                motion = TerrainMotion(2, 1)
                state = SequenceState(2, action=15, target_x=510, facing=1, level_kind=kind)
                self.assertEqual(self.scene.physics.cut_horizontal(
                    motion, state, (490, 150, 524, 226)), allowed)
                self.assertEqual(motion.room, 8 if allowed else 2)

    def test_the_false_princes_are_struck_within_the_type_six_range(self):
        # 6:5bd2-5c06 and 6:5cd4-5cec: (16, 86) facing each other, else
        # (16, 79); the ordinary (61, 99) could never reach a copy.
        from pop2.combat import strike_range

        self.scene.jump_to_room(5, row=2, x=420, facing=0, redraw=False)
        player = self.combat.player
        figure = self.combat.room_encounters[5][0][0]
        self.assertEqual(figure.state.actor_type, 6)
        for kid, copy, expected in ((0, 1, (16, 86)), (1, 0, (16, 86)),
                                    (1, 1, (16, 79)), (0, 0, (16, 79))):
            with self.subTest(kid=kid, copy=copy):
                player.state.facing, figure.state.facing = kid, copy
                self.assertEqual(strike_range(player, figure), expected)
                self.assertEqual(strike_range(figure, player), (16, 79))

    def test_a_shadow_standing_at_rest_casts_instead_of_drawing(self):
        # DoKidEngarde 6:1f4c-1f72 is also the standing gate's Ctrl. After
        # the eight turns the waiting controls own the bank, and their old
        # Ctrl branch drew the sword instead.
        from pop2.final_magic import CAST_SEQUENCE
        from tests.test_final_magic import ShadowSceneTests
        from tools.audit_temple_routes import press

        scene = self.scene
        scene.jump_to_room(6, row=0, x=100, facing=1, redraw=False)
        self.combat.player.life = self.combat.player.max_life = 12
        ShadowSceneTests.turn(self, 8)
        self.assertTrue(scene.game.caverns.final_magic.shadow)
        self.harness.tick(12)
        self.assertEqual(scene.sequence_state.action, 15)
        self.assertIsNotNone(scene.directional_input)
        press(self.harness, 'ctrl', True)
        self.harness.tick(2)
        press(self.harness, 'ctrl', False)
        self.assertEqual(scene.sequence_state.selected_sequence_id, CAST_SEQUENCE)
        self.assertFalse(scene.sword_drawn)

    def test_palace_flasks_are_drawn_and_heal(self):
        from pop2.caverns import draw_cavern_flasks

        # Flasks are library-1 front commands the static room leaves out;
        # the old animated layer drew none in environment 6.
        scene = self.scene
        caverns = scene.game.caverns
        self.assertIn((6, 24), caverns.potions.phases)
        renderer = scene.level_renderer
        blank = Image.new('RGBA', (510, 365))
        expected = draw_cavern_flasks(blank.copy(), 6, caverns, scene.level_map,
                                      level_number=14)
        self.assertIsNotNone(expected.getbbox())
        actual = renderer.animated_layer(blank.copy(), 6, None, front=True, caverns=caverns)
        self.assertIsNone(ImageChops.difference(actual, expected).getbbox())
        behind = renderer.animated_layer(blank.copy(), 6, None, caverns=caverns)
        self.assertIsNone(behind.getbbox())

        scene.jump_to_room(6, row=2, x=4 * 51 + 35, facing=0, reset_guards=False)
        player = self.combat.player
        player.life, player.max_life = 1, 4
        scene.shift_held = True
        self.harness.tick(28)
        self.assertEqual(scene.level_map.tile(6, 4, 2).kind, 1)
        self.assertEqual(player.life, 2)
        self.assertFalse(caverns.potions.effect_pending)


if __name__ == '__main__':
    unittest.main()
