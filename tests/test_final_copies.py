"""Level 14 room 3: Jaffar copies fight, leave flasks and shimmer away."""

import random
import unittest

from PIL import Image

from pop2.paths import ASSET_DIR


INSTALLED = all((ASSET_DIR / name).is_file() for name in (
    'Final.rsrc', 'final_level14.json'))


class LifeEnhancementDraws(random.Random):
    """Rnd(2) draws (randrange(3)) give 2: life 5, and a life enhancement."""

    def randrange(self, start, stop=None, step=1):
        if stop is None and start == 3:
            return 2
        return super().randrange(start, stop, step)


@unittest.skipUnless(INSTALLED, 'Imported Macintosh final level required')
class RoomThreeCopyTests(unittest.TestCase):
    def setUp(self):
        from tools.audit_temple_routes import Harness

        self.harness = Harness(14, peaceful=False)
        self.scene = self.harness.scene
        self.combat = self.scene.combat
        self.combat.rng = LifeEnhancementDraws(4)
        # Native room 3; the copy is born on row 1 while the Prince is on 2.
        self.scene.jump_to_room(2, row=2, x=60, facing=1, redraw=False)
        self.harness.tick(13)

    def tearDown(self):
        self.harness.close()

    def test_a_copy_appears_on_the_other_row_with_sound_243(self):
        copy, = self.combat.guards
        self.assertEqual((copy.row, copy.guard_record.cell, copy.life, copy.skill,
                          copy.state.facing), (1, 14, 5, 5, 1))
        self.assertEqual(self.combat.visible_guards()[0].state.actor_type, 2)

    def test_a_copy_on_the_princes_row_draws_and_fights(self):
        # The copies are ordinary type-2 guards (AutoCtrl 6:4f04 -> 6:4f60);
        # they were frozen in their sequence before.
        copy, = self.combat.guards
        self.scene.jump_to_room(2, row=1, x=330, facing=0, reset_guards=False, redraw=False)
        player = self.combat.player
        player.life = player.max_life = 12
        self.harness.tick(30)
        self.assertTrue(copy.sword_drawn)
        self.assertGreater(copy.alert_mode, 0)
        self.assertLess(player.life, 12)

    def test_a_dead_copy_leaves_a_flask_then_shimmers_away(self):
        from pop2.potions import potion_kind

        copy, = self.combat.guards
        scene, potions = self.scene, self.scene.game.caverns.potions
        copy.life = 0
        self.harness.tick(10)
        # ALIVE 6 (9:00e2): tile 10 on the copy's cell, kind 2 in bits 5-7.
        column = self.combat._supporting_column(copy)
        tile = scene.level_map.tile(2, column, 1)
        self.assertEqual((tile.kind, potion_kind(tile.foreground)), (10, 2))
        self.assertEqual(potions.tiles[2, 10 + column], (10, 0x4040))
        self.assertIn((2, 10 + column), potions.phases)
        blank = Image.new('RGBA', (510, 365))
        drawn = scene.level_renderer.animated_layer(blank.copy(), 2, None, front=True,
                                                    caverns=scene.game.caverns)
        box = drawn.getbbox()
        self.assertIsNotNone(box)
        self.assertTrue(column * 51 + 20 <= box[0] <= column * 51 + 40 and box[3] <= 231)
        # PlayerCtrl counts 0..6 over seven calls; 9:00e2 then goes on.
        self.assertEqual(copy.final_alive, 10)
        # 9:019c: at ALIVE 96 the body takes SEQS 239 (sound 243); its -17
        # removes the record from the room-3 bank.
        self.harness.tick(86)
        self.assertNotEqual(copy.state.selected_sequence_id, 239)
        self.harness.tick(1)
        self.assertEqual(copy.state.selected_sequence_id, 239)
        self.assertIn(copy, self.combat.guards)
        self.harness.tick(13)
        self.assertNotIn(copy, self.combat.guards)
        # With the bank empty, FinlCheckGenOpp brings another copy.
        self.harness.tick(2)
        self.assertEqual(len(self.combat.guards), 1)
        self.assertIsNot(self.combat.guards[0], copy)
        # The flask stays where the copy fell.
        self.assertEqual(scene.level_map.tile(2, column, 1).kind, 10)

    def test_the_life_enhancement_left_by_a_copy_can_be_drunk(self):
        copy, = self.combat.guards
        scene = self.scene
        copy.life = 0
        self.harness.tick(10)
        column = self.combat._supporting_column(copy)
        self.assertEqual(scene.level_map.tile(2, column, 1).kind, 10)
        scene.jump_to_room(2, row=1, x=column * 51 + 35, facing=0, reset_guards=False,
                           redraw=False)
        player = self.combat.player
        player.life, player.max_life = 2, 4
        scene.shift_held = True
        self.harness.tick(28)
        self.assertEqual(scene.level_map.tile(2, column, 1).kind, 1)
        self.assertEqual((player.life, player.max_life), (5, 5))


if __name__ == '__main__':
    unittest.main()
