"""Macintosh throne grille foreground and back-facing sword draw reports."""

from dataclasses import replace
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops

from pop2.paths import ASSET_DIR


@unittest.skipUnless((ASSET_DIR / 'ruins_level8.json').is_file(), 'Imported ruins required')
class ThroneGateTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        self.scene.load_level(8)
        self.scene.peaceful = True

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests

        with patch.object(self.scene, 'render'), patch.object(self.scene, 'advance_audio'):
            RooftopSceneTests.tick(self, count)

    def approach_from_room_twenty_one(self):
        scene = self.scene
        scene.jump_to_room(20, 2, 110, 0)
        scene.horizontal_key(None, -1, True)
        self.tick(45)
        scene.horizontal_key(None, -1, False)
        self.tick(12)
        self.assertEqual(scene.room_id, 8)  # Native throne room9, port index8.
        self.assertGreater(scene.player_x, 450)

    def turn_back_to_grille(self):
        scene = self.scene
        scene.set_key_state('shift', True)
        scene.horizontal_key(None, 1, True)
        self.tick(4)
        scene.horizontal_key(None, 1, False)
        scene.set_key_state('shift', False)
        self.tick(8)
        self.assertEqual((scene.action, scene.sequence_state.facing), (15, 1))

    def test_grille_covers_the_prince_in_both_facings_after_real_room_entry(self):
        self.approach_from_room_twenty_one()
        scene = self.scene
        for facing in (0, 1):
            if facing:
                self.turn_back_to_grille()
            state = scene.sequence_state
            room = scene.level_renderer.enter_room(8, scene.game.caverns)
            record = scene.frames[state.action]
            bounds = scene.player_bounds()
            baseline = replace(room, gate_occlusion={})
            original_mask = baseline.actor_mask(2, bounds[3], state, bounds, record)
            mask = room.actor_mask(2, bounds[3], state, bounds, record)
            # Render the real Prince using the production compositor. The
            # promoted gate must cover body pixels, not only an unused mask.
            sprite = scene.player_sprite(state.action)
            if facing:
                from PIL import ImageOps

                sprite = ImageOps.mirror(sprite)
            layer = Image.new('RGBA', (510, 365))
            layer.paste(sprite, bounds[:2], sprite)
            visible = ImageChops.multiply(layer.getchannel('A'), ImageChops.invert(original_mask))
            hidden = ImageChops.multiply(visible, ImageChops.subtract(mask, original_mask))
            self.assertGreater(sum(hidden.histogram()[1:]), 20)
            frame = room.flattened()
            result = scene.composite_actor(frame.copy(), layer, 2, bounds[3], state, bounds, record)
            self.assertEqual(ImageChops.multiply(
                ImageChops.difference(result.convert('RGB'), frame.convert('RGB')).convert('L'),
                hidden).getbbox(), None)
            self.assertNotEqual(result.tobytes(), frame.tobytes())  # Visible between the bars.

    def test_throne_grille_promotion_keeps_native_column_row_and_hanging_exclusions(self):
        from pop2.caverns import cavern_room
        from pop2.sequence_runtime import SequenceState
        from types import SimpleNamespace

        room = cavern_room(8, level_number=8, animated=True)
        baseline = replace(room, gate_occlusion={})
        record = SimpleNamespace(offset_x=0, aux=0)
        for row in (1, 2):
            for column in (6, 7, 8, 9):
                for mode in (0, 1, 2, 5, 6):
                    state = SequenceState(2, target_x=column * 51 + 35,
                                          animation_state=mode, actor_type=0)
                    mask = room.actor_mask(row, 346, state, (0, 200, 510, 346), record)
                    original = baseline.actor_mask(row, 346, state, (0, 200, 510, 346), record)
                    promoted = ImageChops.subtract(mask, original).getbbox() is not None
                    self.assertEqual(promoted, row == 2 and column in (7, 8) and mode not in (2, 6))
