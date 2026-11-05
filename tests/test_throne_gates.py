"""Macintosh throne grille foreground and back-facing sword draw reports."""

from dataclasses import replace
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops

from pop2.paths import ASSET_DIR


class DrawContactScopeTests(unittest.TestCase):
    def test_other_environments_do_not_use_a_stale_cavern_contact_rectangle(self):
        import struct
        from types import SimpleNamespace

        from pop2.sequence_runtime import SequenceRuntime, SequenceState
        from pop2.terrain import LevelMap, RooftopPhysics, TerrainMotion

        for environment in (2, 5):
            with self.subTest(environment=environment):
                level = bytearray(0x49ca)
                struct.pack_into('>H', level, 0x2186, environment)
                struct.pack_into('>H', level, 0x218a, 10 if environment == 2 else 1)
                struct.pack_into('>H', level, 0x2198, 1)
                for cell in range(30):
                    struct.pack_into('>H', level, cell * 2, 1)
                struct.pack_into('>H', level, 15 * 2, 20)  # A wall far to the right.
                state = SequenceState(55, action=207, animation_state=1, target_x=200, current_x=200,
                                      facing=1, actor_type=0, level_kind=environment)
                runtime = SequenceRuntime({55: (207,), 65: (160,)}, state)
                motion = TerrainMotion(0, 1)
                # This cache belongs to the earlier cavern-style gate check;
                # it is not maintained each frame in the other environments.
                old = (400, 150, 430, 226)
                motion.gate_contact_bounds = (0, 1, old, old)
                events = RooftopPhysics(LevelMap(level)).advance(
                    motion, runtime, 206, (186, 149, 214, 226), sword_drawn=True,
                    old_bounds=(192, 149, 220, 226), cut_enabled=False,
                    frame_record=SimpleNamespace(offset_x=0, aux=0x40))
                self.assertEqual(state.target_x, 200)
                self.assertNotIn('wall', [event.kind for event in events])


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

    def test_back_facing_sword_draw_ejects_to_room_twenty_one_instead_of_crossing(self):
        self.approach_from_room_twenty_one()
        self.turn_back_to_grille()
        scene = self.scene
        with patch.object(scene, 'render'), patch.object(scene, 'advance_audio'):
            scene.set_key_state('ctrl', True)
        self.assertEqual(scene.sequence_state.source_sequence_id, 65)
        self.assertGreater(scene.player_x, 480)
        self.tick(4)
        self.assertEqual(scene.room_id, 20)
        self.assertTrue(scene.sword_drawn)
        scene.set_key_state('ctrl', False)
        # Walk back at the closed grille with the sword still drawn. The
        # first draw must not have put the Prince on its interior side.
        scene.horizontal_key(None, -1, True)
        self.tick(18)
        self.assertGreater(scene.sequence_state.target_x + (510 if scene.room_id == 20 else 0), 450)
        self.assertEqual(scene.level_map.tile(8, 8, 2).foreground & 255, 0)

    def test_first_draw_after_a_warp_also_keeps_the_pre_draw_rectangle(self):
        scene = self.scene
        scene.jump_to_room(8, 2, 473, 1)
        self.assertIsNone(scene.terrain_motion.gate_contact_bounds)
        with patch.object(scene, 'render'), patch.object(scene, 'advance_audio'):
            scene.set_key_state('ctrl', True)
        self.assertEqual(scene.sequence_state.source_sequence_id, 65)
        self.tick(4)
        self.assertEqual(scene.room_id, 20)
