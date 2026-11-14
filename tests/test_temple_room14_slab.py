"""Room14 loose-floor contact, debris and downstairs guard progression."""
import unittest

from PIL import ImageChops

from pop2.paths import ASSET_DIR


@unittest.skipUnless((ASSET_DIR / 'temple_level10.json').is_file(), 'Imported temple resources required')
class Room14SlabTests(unittest.TestCase):
    def test_real_short_jump_keeps_slab_at_contact_and_guard_waits_for_head_crossing(self):
        from tools.audit_temple_routes import Harness, press
        from pop2.caverns import cavern_room

        harness = Harness(10, draw=True, peaceful=False)
        scene = harness.scene
        scene.audio = None
        try:
            scene.jump_to_room(13, 1, 120, 1)
            # Actual key events select the directional short jump, then its
            # SEQS18 fall. Start/keys are supplied, not recovered video input.
            press(harness, 'up', True)
            press(harness, 'R', True)
            scenery = cavern_room(13, level_number=10).flattened().convert('RGB')
            observed = {}
            for tick in range(23):
                harness.tick()
                if tick == 2:
                    press(harness, 'up', False)
                if tick == 9:
                    press(harness, 'R', False)
                blocks = scene.game.caverns.loose.falling
                if tick == 16:
                    self.assertEqual((scene.sequence_state.action, scene.sequence_state.current_y), (106, 6))
                    self.assertFalse(blocks)
                if tick == 17:
                    block, = blocks
                    self.assertEqual((block.room, block.y, block.mob_type, block.size),
                                     (13, 365, 3, (91, 31)))
                    self.assertNotIn((12, 5), scene.game.caverns.loose.tiles)
                    scene.render()
                    drawn = scene.native_viewport.crop((1, 0, 511, 365)).convert('RGB')
                    # Original slab still masks the trousers at the bottom
                    # border; the old cave-origin slab was already18px lower.
                    box = (285, 345, 301, 360)
                    self.assertIsNone(ImageChops.difference(drawn.crop(box), scenery.crop(box)).getbbox())
                if tick in (18, 19, 20, 21):
                    observed[tick] = (blocks[0].y, blocks[0].row)
                if tick == 20:
                    guard, = scene.combat.active_guards()
                    self.assertEqual(guard.life, 4, 'slabY165 has not crossed the native head plane169')
                if tick == 21:
                    guard, = scene.combat.active_guards()
                    self.assertEqual((guard.life, guard.state.source_sequence_id), (0, 22))
                if tick == 22:
                    self.assertFalse(blocks)
                    self.assertEqual(scene.level_map.tile(12, 5, 1).kind, 14)
            self.assertEqual(observed, {18: (47, 0), 19: (102, 0), 20: (165, 1), 21: (228, 1)})
        finally:
            harness.close()
