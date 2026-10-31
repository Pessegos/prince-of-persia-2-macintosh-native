from types import SimpleNamespace
import struct
import unittest
from unittest.mock import patch

from pop2.animation_data import FrameRecord
from pop2.lava import ENHANCED_BUBBLE_OFFSET_X, ENHANCED_BUBBLE_OFFSET_Y, Lava, LavaPool
from pop2.paths import ASSET_DIR
from pop2.terrain import LevelMap, RooftopPhysics, TerrainMotion
from pop2.sequence_runtime import SequenceRuntime, SequenceState
from pop2.rebirth import DeathState
from tools.extract_lava import lava_tables


def synthetic_tables():
    return {'limits': [4, 5, 4], 'piece_offsets': [0, 0],
            'characters': [[(150, 45, -18)] * 5, [(148, 45, -18)] * 22,
                           [(168, 18, -15)] * 5],
            'splashes': [(146, 43, -16)] * 3,
            'events': [(0, 0, -11, 58, 0), (4, 1, -15, 64, 1)],
            'bubbles': [[0, 1, -2, 2, -1], [3, 4, 5, -1]]}


class LavaRuleTests(unittest.TestCase):
    def setUp(self):
        self.pool = LavaPool(synthetic_tables())

    def test_cell_seed_and_initial_bubbles(self):
        for cell, phase, active in ((27, 0, 0), (22, 5, 1), (23, 10, 0)):
            pool = LavaPool(synthetic_tables())
            pool.initialize(cell)
            self.assertEqual(pool.flags, phase)
            self.assertEqual(sum(b[0] for b in pool.bubbles), active)

    def test_normal_cycle_uses_previous_phase_and_retains_bubbles_at_reset(self):
        self.assertEqual(self.pool.advance(), ())
        self.assertEqual(self.pool.bubbles[0], [1, 0, 0, -11, 58, 0])
        self.pool.advance()
        self.assertEqual(self.pool.bubbles[0][1], 1)
        self.pool.advance()
        self.assertEqual(self.pool.bubbles[0][1], 3)
        self.assertEqual(self.pool.bubbles[0][5], 1)
        self.pool.advance()
        self.assertEqual(self.pool.bubbles[0][0], 0)
        self.pool.flags = 22
        self.pool.bubbles[2] = [1, 1, 0, -11, 58, 1]
        self.pool.advance()
        self.assertEqual(self.pool.flags, 0)
        self.assertEqual(self.pool.bubbles[2], [1, 1, 0, -11, 58, 1])

    def test_death_selection_and_inclusive_random_branch(self):
        for mode, roll, expected in ((3, 0, 0x8000), (4, 0, 0x8000),
                                     (0, 1, 0xa000), (0, 2, 0xa000),
                                     (1, 3, 0xa000), (0, 0, 0xb000)):
            self.assertEqual(self.pool.begin_death(mode, 1, random_value=roll), (116, 70))
            self.assertEqual(self.pool.flags, expected)
        with patch('pop2.lava.random.randint', return_value=0) as draw:
            self.pool.begin_death(0, 1)
            draw.assert_called_once_with(0, 3)
        self.pool.begin_death(0, 0, random_value=1)
        self.assertEqual(self.pool.flags, 0xa800)
        self.assertEqual(self.pool.character_sequence, 1)
        self.assertEqual(self.pool.begin_death(0, 1, actor_type=2), (115, 69))
        self.assertEqual(self.pool.character_sequence, 2)

    def test_death_duration_and_sound_use_old_phase(self):
        for mode, roll, last in ((3, 0, 4), (0, 1, 5), (0, 0, 21)):
            pool = LavaPool(synthetic_tables())
            pool.begin_death(mode, 1, random_value=roll)
            sounds = []
            for tick in range(1, last + 2):
                sounds.extend((tick, cue) for cue in pool.advance())
                self.assertEqual(pool.character_sequence >= 0, tick <= last)
            self.assertEqual(sounds, [(5 if mode == 3 else 6, 68)])

    def test_death_reset_at_three_preserves_flags_but_does_not_advance_bubbles(self):
        self.pool.begin_death(0, 0, random_value=0)
        self.pool.flags |= 3
        self.pool.bubbles[0] = [1, 1, 0, -11, 58, 1]
        self.pool.advance()
        self.assertEqual(self.pool.flags, 0xb804)
        self.assertEqual(self.pool.bubbles[0][1], 1)

    def test_native_cover_is_between_rear_and_front_bubbles(self):
        self.pool.bubbles[0] = [1, 0, 0, -11, 58, 0]
        self.pool.bubbles[1] = [1, 1, 0, -11, 42, 1]
        self.assertEqual(self.pool.drawings(), [(3617, 42, -11, False),
                                              (3615, 0, 0, False),
                                              (3616, 58, -11, False)])
        self.pool.begin_death(3, 0)
        self.assertEqual(self.pool.drawings(), [(3615, 0, 0, False),
                                              (3650, 45, -18, True)])

    def test_room_changes_reinitialize_but_rendering_same_room_does_not(self):
        lava = Lava(synthetic_tables())
        records = [{'room': 5, 'cell': 27}] * 2
        lava.enter_room(5, records)
        self.assertEqual(len(lava.pools), 1)
        lava.advance()
        lava.enter_room(5, records)
        self.assertEqual(lava.pools[5, 27].flags, 1)
        lava.enter_room(12, records)
        self.assertEqual(lava.pools[5, 27].flags, 0)
        lava.enter_room(0, [])
        self.assertEqual(lava.pools, {})

    def contact(self, foot, y=346, flags=0x40, offset=0, facing=1, dead=False):
        data = bytearray(0x4200)
        import struct
        struct.pack_into('>H', data, 27 * 2, 23)
        struct.pack_into('>H', data, 28 * 2, 24)
        terrain = LevelMap(bytes(data))
        lava = Lava(synthetic_tables())
        lava.enter_room(0, [{'room': 0, 'cell': 27}])
        frame = FrameRecord(15, 0, 0, offset, 0, flags)
        state = SimpleNamespace(target_x=foot - offset * (1 if facing else -1),
                                facing=facing, current_y=y - 346)
        return lava.contact(terrain, TerrainMotion(0, 2, dead=dead), state, frame)

    def test_native_contact_limits_and_surface_y(self):
        for foot in range(380, 470):
            with self.subTest(foot=foot):
                self.assertEqual(self.contact(foot) is not None, 400 <= foot <= 444)
        self.assertIsNone(self.contact(420, y=316))
        self.assertIsNotNone(self.contact(420, y=317))
        self.assertIsNone(self.contact(420, flags=0))
        self.assertIsNone(self.contact(420, dead=True))

    def test_fast_lava_landing_defers_to_lava_instead_of_selecting_flat_impact_death(self):
        from pop2.cavern_state import CavernState

        level = bytearray(0x49ca)
        struct.pack_into('>H', level, 0x2186, 3)
        struct.pack_into('>H', level, 27 * 2, 23)
        terrain = LevelMap(level)
        terrain.caverns = CavernState()
        state = SequenceState(12, action=106, animation_state=4, actor_type=0,
                              target_x=420, current_y=-45, vertical_velocity=63)
        runtime = SequenceRuntime({22: (-7, 1, 185, -23)}, state)
        motion = TerrainMotion(0, 2, falling=True)
        events = RooftopPhysics(terrain).advance(
            motion, runtime, 420, (400, 220, 435, 301), cut_enabled=False,
            frame_record=FrameRecord(106, 0, 0, 0, 0, 0x40))
        self.assertEqual([event.kind for event in events], ['lava'])
        self.assertTrue(motion.lava_landing)
        self.assertFalse(motion.dead)
        self.assertEqual((state.source_sequence_id, state.action, state.animation_state), (12, 106, 4))
        self.assertEqual(state.current_y, 0)
        self.assertNotIn(7, state.sound_events)

    def test_lava_landing_uses_the_whole_tile_without_surface_contact_pose_or_edge_limits(self):
        level = bytearray(0x49ca)
        struct.pack_into('>H', level, 27 * 2, 23)
        struct.pack_into('>H', level, 28 * 2, 24)
        terrain = LevelMap(level)
        lava = Lava(synthetic_tables())
        lava.enter_room(0, [{'room': 0, 'cell': 27}])
        state = SequenceState(23, action=77, target_x=399, facing=1)
        motion = TerrainMotion(0, 2)
        record = FrameRecord(77, 0, 0, 0, 0, 0)
        for foot in (390, 399, 420, 445, 460):
            state.target_x = foot
            self.assertIsNone(lava.contact(terrain, motion, state, record))
            self.assertIs(lava.contact(terrain, motion, state, record, landed=True), lava.pools[0, 27])
        state.target_x = 350
        self.assertIsNone(lava.contact(terrain, motion, state, record, landed=True))
        motion.dead = True
        state.target_x = 420
        self.assertIsNone(lava.contact(terrain, motion, state, record, landed=True))

    def test_column_is_derived_from_supporting_foot_not_anchor(self):
        for facing in (0, 1):
            for offset in (-30, 0, 30):
                self.assertIsNotNone(self.contact(420, offset=offset, facing=facing))
                self.assertIsNone(self.contact(399, offset=offset, facing=facing))

    def test_sequence_death_music_selector_does_not_replace_lava_cause(self):
        state = SequenceState(116, actor_type=0)
        runtime = SequenceRuntime({116: (-7, 1, -11, 1, 15, 185, -23)}, state)
        self.assertEqual(runtime.next_frame().action, 15)
        self.assertEqual(state.death_song_method, 1)
        death = DeathState(counter=6, method=5, music_method=state.death_song_method)
        from unittest.mock import Mock
        audio = Mock()
        audio.death_ready.return_value = True
        death.advance(185, 0.1, audio)
        audio.death_song.assert_called_once_with(1)
        self.assertEqual(death.method, 5)
        other = SequenceState(115, actor_type=2)
        SequenceRuntime({115: (-11, 1, 185)}, other).next_frame()
        self.assertIsNone(other.death_song_method)


class LavaExtractionTests(unittest.TestCase):
    def setUp(self):
        self.data = bytearray(0x6000)
        self.pieces = bytearray(0x220)
        struct.pack_into('>3h', self.data, len(self.data) - 0x2e54, 4, 5, 4)
        for index, count in enumerate((5, 22, 5)):
            displacement = -0x4000 + index * 200
            struct.pack_into('>i', self.data, len(self.data) - 0x2f4a + index * 4, displacement)
            for frame in range(count):
                struct.pack_into('>3h', self.data, len(self.data) + displacement + frame * 6,
                                 150 + frame, 40 + index, -18)
        for index in range(6):
            displacement = -0x3800 + index * 100
            struct.pack_into('>i', self.data, len(self.data) - 0x2cfa + index * 4, displacement)
            struct.pack_into('>5h', self.data, len(self.data) + displacement, 0, 1, -2, 2, -1)
        struct.pack_into('>5h', self.data, len(self.data) - 0x2e4e, 0, 2, -11, 58, 1)
        struct.pack_into('>2h', self.pieces, 0x1d6, -3, -4)

    def extract(self):
        with (patch('tools.extract_lava.expand_a5_data', return_value=bytes(self.data)),
              patch('tools.extract_lava.parse_resource_fork',
                    side_effect=[{}, {'PIEC': {3500: {'data': bytes(self.pieces)}}}])):
            return lava_tables(b'program', b'artwork')

    def test_signed_offsets_markers_and_full_rare_continuation_are_imported(self):
        tables = self.extract()
        self.assertEqual(tables['schema'], 1)
        self.assertEqual([len(seq) for seq in tables['characters']], [5, 22, 5])
        self.assertEqual(tables['characters'][1][21], [171, 41, -18])
        self.assertEqual(tables['piece_offsets'], [-3, -4])
        self.assertEqual(tables['events'][0], [0, 2, -11, 58, 1])
        self.assertEqual(tables['bubbles'][4], [0, 1, -2, 2, -1])

    def test_unsupported_death_limits_are_rejected(self):
        struct.pack_into('>h', self.data, len(self.data) - 0x2e54, 20)
        with self.assertRaisesRegex(ValueError, 'death tables'):
            self.extract()

    def test_unterminated_bubble_table_is_rejected(self):
        start = len(self.data) - 0x3800
        self.data[start:start + 80] = bytes(80)
        with self.assertRaisesRegex(ValueError, 'Unterminated'):
            self.extract()


class EnhancedLavaTests(unittest.TestCase):
    def test_wrap_advances_bubbles_and_starts_next_cycle_in_the_same_tick(self):
        pool = LavaPool(synthetic_tables(), enhanced=True)
        pool.flags = 22
        pool.bubbles[0] = [1, 0, 0, -11, 58, 1]
        self.assertEqual(pool.advance(), ())
        self.assertEqual(pool.flags, 1)
        self.assertEqual(pool.bubbles[0], [1, 1, 0, -11, 58, 1])
        self.assertEqual(pool.bubbles[1], [1, 0, 0, -11, 58, 0])

    def test_enhanced_surface_is_behind_both_bubble_layers(self):
        original = LavaPool(synthetic_tables())
        enhanced = LavaPool(synthetic_tables(), enhanced=True)
        for pool in (original, enhanced):
            pool.bubbles[0] = [1, 0, 0, -11, 58, 0]
            pool.bubbles[1] = [1, 1, 0, -11, 42, 1]
        self.assertEqual(enhanced.drawings(), [(3614, 0, 0, False),
                                             (3617, 47, -12, False),
                                             (3616, 63, -12, False)])
        self.assertEqual(enhanced.drawings()[1:], [
            (shape, x + ENHANCED_BUBBLE_OFFSET_X, y + ENHANCED_BUBBLE_OFFSET_Y, flip)
            for shape, x, y, flip in original.drawings() if shape != 3615])

    def test_bubble_offset_is_visual_only_and_does_not_move_surface_or_death_art(self):
        original = LavaPool(synthetic_tables())
        enhanced = LavaPool(synthetic_tables(), enhanced=True)
        for pool in (original, enhanced):
            pool.bubbles[0] = [1, 0, 0, -11, 58, 0]
        self.assertEqual(original.bubbles, enhanced.bubbles)
        self.assertIn((3616, 58, -11, False), original.drawings())
        self.assertIn((3616, 63, -12, False), enhanced.drawings())
        for mode in (0, 3):
            for facing in (0, 1):
                for pool in (original, enhanced):
                    pool.begin_death(mode, facing, random_value=1)
                    pool.flags |= 1
                self.assertEqual(enhanced.drawings()[0], (3614, 0, 0, False))
                self.assertEqual(enhanced.drawings()[1:], original.drawings()[1:])

    def test_death_flags_probability_duration_and_sounds_are_unchanged(self):
        bubble_shapes = {3616 + index for sequence in synthetic_tables()['bubbles']
                         for index in sequence if index >= 0}
        for mode in (0, 1, 3, 4):
            for roll in range(4):
                for facing in (0, 1):
                    for actor in (0, 2):
                        with self.subTest(mode=mode, roll=roll, facing=facing, actor=actor):
                            original = LavaPool(synthetic_tables())
                            enhanced = LavaPool(synthetic_tables(), enhanced=True)
                            for pool in (original, enhanced):
                                pool.initialize(22)
                            self.assertEqual(original.begin_death(mode, facing, actor, roll),
                                             enhanced.begin_death(mode, facing, actor, roll))
                            for _ in range(23):
                                self.assertEqual(enhanced.flags, original.flags)
                                self.assertEqual(enhanced.bubbles, original.bubbles)
                                self.assertEqual(enhanced.drawings(), [
                                    (3614 if shape == 3615 else shape,
                                     x + (ENHANCED_BUBBLE_OFFSET_X if shape in bubble_shapes else 0),
                                     y + (ENHANCED_BUBBLE_OFFSET_Y if shape in bubble_shapes else 0), flip)
                                    for shape, x, y, flip in original.drawings()])
                                self.assertEqual(enhanced.advance(), original.advance())
                                if original.character_sequence < 0:
                                    self.assertEqual(enhanced.character_sequence, -1)
                                    break
                            else:
                                self.fail('Death animation did not finish')

    def test_room_initialization_propagates_mode_and_native_reference_remains_available(self):
        records = [{'room': 5, 'cell': 27}]
        enhanced = Lava(synthetic_tables(), enhanced=True)
        original = Lava(synthetic_tables())
        for lava in (original, enhanced):
            lava.enter_room(5, records)
            self.assertEqual(lava.pools[5, 27].enhanced, lava.enhanced)


class RecessedLavaArtworkTests(unittest.TestCase):
    def test_surface_ripples_stay_in_liquid_and_raised_drops_cross_the_rim(self):
        from PIL import Image
        from pop2.caverns import draw_cavern_lava

        rock, red = (60, 40, 30, 255), (255, 31, 0, 255)
        base = Image.new('RGBA', (8, 8), rock)
        base.paste((255, 127, 0, 255), (2, 3, 6, 7))
        base.putpixel((3, 4), (127, 0, 0, 255))
        effect = Image.new('RGBA', (8, 10), red)
        effect.paste((0, 0, 0, 0), (0, 8, 8, 9))
        pool = LavaPool(synthetic_tables(), enhanced=True)
        state = SimpleNamespace(lava=SimpleNamespace(pools={(0, 27): pool}))
        program = {'lava': {'rooms': {'0': [{'room': 0, 'cell': 27, 'x': 10, 'bottom': 20}]}}}
        shapes = {('recessed', 3614): base, 3645: effect, 3632: effect}
        with patch('pop2.caverns.cavern_assets', return_value=(program, {}, {}, shapes)):
            with patch.object(pool, 'drawings', return_value=[(3614, 0, 0, False), (3645, 0, 0, False)]):
                ripple = draw_cavern_lava(Image.new('RGBA', (30, 30), rock), 0, state)
            self.assertEqual(ripple.getpixel((12, 15)), red)
            for point in ((12, 10), (12, 13), (13, 16), (12, 19)):
                self.assertNotEqual(ripple.getpixel(point), red)
            with patch.object(pool, 'drawings', return_value=[(3614, 0, 0, False), (3632, 0, 0, False)]):
                splash = draw_cavern_lava(Image.new('RGBA', (30, 30), rock), 0, state)
            for point in ((12, 10), (12, 13)):
                self.assertEqual(splash.getpixel(point), red)
            self.assertEqual(splash.getpixel((13, 16)), (127, 0, 0, 255))
            self.assertEqual(splash.getpixel((12, 19)), rock)

    def test_splitting_an_effect_preserves_every_pixel_exactly_once(self):
        from PIL import Image, ImageChops
        from pop2.caverns import split_lava_bubble

        sprite = Image.new('RGBA', (20, 15), (255, 79, 0, 255))
        for shape in range(3616, 3646):
            surface, airborne = split_lava_bubble(sprite, shape)
            self.assertIsNone(ImageChops.multiply(surface.getchannel('A'), airborne.getchannel('A')).getbbox())
            combined = surface.copy()
            combined.paste(airborne, (0, 0), airborne)
            self.assertEqual(combined.tobytes(), sprite.tobytes())
        for shape in (3616, 3622, 3624, 3631, 3643, 3644, 3645):
            self.assertIsNone(split_lava_bubble(sprite, shape)[1].getbbox())

    def test_raised_body_continues_below_seed_band_without_taking_diagonal_ripples(self):
        from PIL import Image
        from pop2.caverns import split_lava_bubble

        red = (255, 31, 0, 255)
        sprite = Image.new('RGBA', (6, 9))
        sprite.paste(red, (2, 0, 4, 6))
        sprite.putpixel((5, 1), red)
        for point in ((1, 6), (2, 7), (3, 7), (4, 6)):
            sprite.putpixel(point, red)
        surface, airborne = split_lava_bubble(sprite, 3619)
        self.assertEqual(airborne.getpixel((2, 5)), red)
        self.assertEqual(airborne.getpixel((5, 1)), red)
        self.assertEqual(surface.getpixel((2, 5))[3], 0)
        for point in ((1, 6), (2, 7), (3, 7), (4, 6)):
            self.assertEqual(surface.getpixel(point), red)
            self.assertEqual(airborne.getpixel(point)[3], 0)

    def test_foreground_mask_protects_inset_rock_and_floor_but_not_the_rear_rim(self):
        from PIL import Image
        from pop2.caverns import recessed_lava_foreground_mask

        surface = Image.new('RGBA', (5, 5), (60, 40, 30, 255))
        surface.putpixel((1, 1), (255, 127, 0, 255))
        surface.putpixel((1, 3), (127, 0, 0, 255))
        surface.putpixel((2, 2), (255, 79, 0, 255))
        surface.putpixel((3, 2), (255, 79, 0, 0))
        mask = recessed_lava_foreground_mask(surface)
        self.assertEqual({(x, y) for y in range(5) for x in range(5) if mask.getpixel((x, y))},
                         {(1, 2), (1, 4), (2, 3), (2, 4)})

    def test_inset_rock_and_embedded_crust_occlude_animation_without_hiding_liquid(self):
        from PIL import Image
        from pop2.caverns import draw_cavern_lava

        rock, crust = (60, 40, 30, 255), (127, 0, 0, 255)
        surface = Image.new('RGBA', (5, 7), rock)
        for y in (1, 5):
            surface.putpixel((2, y), (255, 127, 0, 255))
        surface.putpixel((2, 3), crust)
        bubble = Image.new('RGBA', surface.size, (255, 31, 0, 255))
        unchanged = surface.tobytes()
        pool = LavaPool(synthetic_tables(), enhanced=True)
        state = SimpleNamespace(lava=SimpleNamespace(pools={(0, 27): pool}))
        program = {'lava': {'rooms': {'0': [{'room': 0, 'cell': 27, 'x': 10, 'bottom': 20}]}}}
        shapes = {('recessed', 3614): surface, 3616: bubble, 3619: bubble}
        for shape in (3616, 3619):
            with (self.subTest(shape=shape),
                  patch('pop2.caverns.cavern_assets', return_value=(program, {}, {}, shapes)),
                  patch.object(pool, 'drawings', return_value=[(3614, 0, 0, False), (shape, 0, 0, False)])):
                frame = draw_cavern_lava(Image.new('RGBA', (30, 30)), 0, state)
            self.assertEqual(frame.getpixel((12, 15)), rock)
            self.assertEqual(frame.getpixel((12, 16)), crust)
            if shape == 3616:
                self.assertEqual(frame.getpixel((12, 13)), rock)
            else:
                self.assertEqual(frame.getpixel((12, 13)), (255, 31, 0, 255))
            for y in (14, 18):
                self.assertEqual(frame.getpixel((12, y)), (255, 31, 0, 255))
        self.assertEqual(surface.tobytes(), unchanged)

    def test_inset_mask_excludes_liquid_transparency_and_outer_rims(self):
        from PIL import Image
        from pop2.caverns import recessed_lava_inset_mask

        surface = Image.new('RGBA', (3, 7), (60, 40, 30, 255))
        for y in (1, 5):
            surface.putpixel((1, y), (255, 127, 0, 255))
        surface.putpixel((1, 3), (127, 0, 0, 255))
        surface.putpixel((1, 4), (0, 0, 0, 0))
        mask = recessed_lava_inset_mask(surface)
        self.assertEqual({(x, y) for y in range(7) for x in range(3) if mask.getpixel((x, y))},
                         {(1, 2), (1, 3)})

    def test_animation_is_behind_the_front_rock_but_not_the_back_rim(self):
        from PIL import Image
        from pop2.caverns import draw_cavern_lava

        surface = Image.new('RGBA', (5, 5), (60, 40, 30, 255))
        surface.putpixel((2, 2), (255, 127, 0, 255))
        bubble = Image.new('RGBA', (5, 5), (255, 31, 0, 255))
        bubble.paste((0, 0, 0, 0), (0, 3, 5, 4))
        unchanged = surface.tobytes()
        pool = LavaPool(synthetic_tables(), enhanced=True)
        state = SimpleNamespace(lava=SimpleNamespace(pools={(0, 27): pool}))
        program = {'lava': {'rooms': {'0': [{'room': 0, 'cell': 27, 'x': 10, 'bottom': 20}]}}}
        shapes = {('recessed', 3614): surface, 3619: bubble}
        with (patch('pop2.caverns.cavern_assets', return_value=(program, {}, {}, shapes)),
              patch.object(pool, 'drawings', return_value=[(3614, 0, 0, False), (3619, 0, 0, False)])):
            frame = draw_cavern_lava(Image.new('RGBA', (30, 30)), 0, state)
        self.assertEqual(frame.getpixel((12, 19)), (60, 40, 30, 255))
        self.assertEqual(frame.getpixel((12, 17)), (255, 31, 0, 255))
        self.assertEqual(frame.getpixel((12, 15)), (255, 31, 0, 255))
        self.assertEqual(surface.tobytes(), unchanged)

    def test_pixel_touchup_matches_the_supplied_edit_and_changes_nothing_else(self):
        import hashlib
        from pop2.caverns import recessed_lava_surface

        palette = {i: (i, 255 - i, i, 255) for i in range(256)}
        sprite = recessed_lava_surface(palette)
        edits = ((75, 5, 0xb9, 0xd4), (78, 5, 0xb9, 0xd4),
                 (56, 6, 0xb9, 0xd4), (43, 7, 0xb9, 0xaa),
                 (44, 7, 0xbb, 0xd4), (45, 8, 0xaa, 0xbb))
        edits += tuple((x, 10, 0xd4, index) for x, index in enumerate(
            (0xbc, 0xbb, 0xbc, 0xbc, 0xbb, 0xbc, 0xbb, 0xbc, 0xbc, 0xbb, 0xbb), 84))
        edits += ((82, 11, 0xd4, 0xbc), (83, 11, 0xd4, 0xbc), (84, 11, 0xd4, 0xbb),
                  (88, 11, 0xd4, 0xbb), (89, 11, 0xd4, 0xbb), (90, 11, 0xd4, 0xb9))
        edits += ((85, 11, 0xa8, 0xbb),)
        for x, y, old, new in edits:
            self.assertEqual(sprite.getpixel((x, y)), palette[new])
            sprite.putpixel((x, y), palette[old])
        self.assertEqual(hashlib.sha256(sprite.tobytes()).hexdigest(),
                         'f7f98f89fdd6d8e8fc78647aa31a4f205440c05ea0f6045bfb49dc0ea165f118')

    def test_artwork_uses_only_palette_pixels_and_binary_transparency(self):
        from pop2.caverns import recessed_lava_surface

        palette = {i: (i, 255 - i, i, 255) for i in range(256)}
        sprite = recessed_lava_surface(palette)
        self.assertEqual(sprite.size, (140, 33))
        self.assertEqual(sprite.getchannel('A').getbbox(), (13, 3, 116, 29))
        self.assertEqual(set(sprite.getchannel('A').tobytes()), {0, 255})
        self.assertLessEqual({sprite.getpixel((x, y)) for y in range(sprite.height)
                              for x in range(sprite.width)}, {(0, 0, 0, 0), *palette.values()})
        # Keep the approved surface's broad middle and dark-red crust details.
        self.assertEqual(sprite.getpixel((80, 10)), palette[0xbc])
        self.assertEqual(sprite.getpixel((41, 10)), palette[0xd4])
        self.assertEqual(sprite.getpixel((0, 15)), (0, 0, 0, 0))

    def test_enhanced_rendering_caches_art_and_retains_the_native_bottom_anchor(self):
        from PIL import Image
        from pop2.caverns import draw_cavern_lava

        pool = LavaPool(synthetic_tables(), enhanced=True)
        state = SimpleNamespace(lava=SimpleNamespace(pools={(0, 27): pool}))
        program = {'lava': {'rooms': {'0': [{'room': 0, 'cell': 27, 'x': 10, 'bottom': 50}]}}}
        shapes = {}
        surface = Image.new('RGBA', (140, 33), (1, 2, 3, 255))
        with (patch('pop2.caverns.cavern_assets', return_value=(program, {}, {}, shapes)),
              patch('pop2.caverns.recessed_lava_surface', return_value=surface) as build,
              patch('pop2.caverns.decode_shap') as decode):
            for _ in range(2):
                image = draw_cavern_lava(Image.new('RGBA', (200, 70)), 0, state)
                self.assertEqual(image.getbbox(), (10, 17, 150, 50))
            build.assert_called_once_with({})
            decode.assert_not_called()

    def test_native_reference_does_not_load_the_enhancement(self):
        from PIL import Image
        from pop2.caverns import draw_cavern_lava

        pool = LavaPool(synthetic_tables())
        state = SimpleNamespace(lava=SimpleNamespace(pools={(0, 27): pool}))
        program = {'lava': {'rooms': {'0': [{'room': 0, 'cell': 27, 'x': 10, 'bottom': 50}]}}}
        resources = {'SHAP': {3615: {'data': b'native cover'}}}
        cover = Image.new('RGBA', (140, 30), (1, 2, 3, 255))
        with (patch('pop2.caverns.cavern_assets', return_value=(program, resources, {}, {})),
              patch('pop2.caverns.recessed_lava_surface') as build,
              patch('pop2.caverns.decode_shap', return_value=cover) as decode):
            image = draw_cavern_lava(Image.new('RGBA', (200, 70)), 0, state)
            self.assertEqual(image.getbbox(), (10, 20, 150, 50))
            build.assert_not_called()
            decode.assert_called_once_with(b'native cover', {})


@unittest.skipUnless((ASSET_DIR / 'caverns_entry.json').is_file(), 'Imported game resources required')
class ImportedLavaTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests
        RooftopSceneTests.setUp(self)
        self.scene.load_level(3)
        self.scene.peaceful = True

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests
        RooftopSceneTests.tick(self, count)

    def test_all_native_pools_and_visible_border_copies_are_recovered(self):
        tables = self.scene.level_renderer.cavern_program['lava']
        pools = {(item['room'], item['cell']) for records in tables['rooms'].values() for item in records}
        self.assertEqual(pools, {(5, 27), (9, 23), (14, 22), (25, 23), (30, 23)})
        self.assertEqual(tables['limits'], [4, 5, 4])
        self.assertEqual([len(t) for t in tables['characters']], [5, 22, 5])

    def test_pool_boils_without_player_input_and_does_not_change_static_art(self):
        scene = self.scene
        scene.jump_to_room(5, row=2, x=350, facing=1)
        scene.render()
        initial = scene.native_viewport.crop((375, 325, 470, 365)).tobytes()
        base = scene.background.tobytes()
        self.tick(8)
        self.assertNotEqual(scene.native_viewport.crop((375, 325, 470, 365)).tobytes(), initial)
        self.assertEqual(scene.background.tobytes(), base)
        self.assertTrue(scene.combat.player.alive)

    def test_walk_into_lava_dies_with_original_sequence_and_retry(self):
        scene = self.scene
        scene.jump_to_room(5, row=2, x=420, facing=1)
        with patch('pop2.lava.random.randint', return_value=1):
            self.tick()
        self.assertEqual(scene.death.method, 5)
        self.assertEqual(scene.death.music_method, 1)
        self.assertEqual(scene.sequence_state.selected_sequence_id, 116)
        self.assertEqual(scene.sequence_state.sequence_mode, 5)
        self.assertEqual(scene.game.caverns.lava.pools[5, 27].flags, 0xa000)
        self.assertTrue(scene.terrain_motion.dead)
        self.assertFalse(scene.combat.player.alive)
        self.assertIsNone(scene.player_sprite())
        self.tick(40)
        self.assertTrue(scene.death.can_restart)
        scene.restart_after_death()
        self.assertTrue(scene.combat.player.alive)
        self.assertNotEqual(scene.death.method, 5)
        self.assertEqual(scene.game.caverns.lava.pools, {})

    def test_airborne_contact_uses_other_sequence_and_jump_clears_surface(self):
        scene = self.scene
        scene.jump_to_room(5, row=2, x=420, facing=1)
        state = scene.sequence_state
        state.animation_state, state.current_y = 3, -31
        scene.advance_level_events()
        self.assertTrue(scene.combat.player.alive)
        state.current_y = -29
        scene.advance_level_events()
        self.assertFalse(scene.combat.player.alive)
        self.assertEqual(scene.game.caverns.lava.pools[5, 27].flags, 0x8000)

    def test_fast_falls_into_all_five_pools_use_lava_death_and_finish_with_retry(self):
        scene = self.scene
        for room, cell in ((5, 27), (9, 23), (14, 22), (25, 23), (30, 23)):
            for facing in (0, 1):
                with self.subTest(room=room + 1, facing=facing), patch.object(scene, 'render'):
                    scene.jump_to_room(room, row=2, x=cell % 10 * 51 + 60, facing=facing)
                    state, motion = scene.sequence_state, scene.terrain_motion
                    scene.physics.select(scene.sequence_runtime, 12)
                    scene.action, scene.player_x = state.action, state.target_x
                    state.current_y, state.vertical_velocity = -45, 63
                    state.horizontal_velocity = 0
                    state.sound_events.clear()
                    motion.falling = True
                    self.tick()
                    self.assertEqual(scene.death.method, 5)
                    self.assertEqual(state.source_sequence_id, 116)
                    self.assertFalse(scene.combat.player.alive)
                    self.assertTrue(motion.dead)
                    self.assertFalse(motion.lava_landing)
                    self.assertEqual(scene.game.caverns.lava.pools[room, cell].flags,
                                     0x8000 if facing else 0x8800)
                    self.assertIsNone(scene.player_sprite())
                    self.assertNotIn(7, state.sound_events)
                    self.tick(30)
                    self.assertTrue(scene.death.prompt_visible)

    def test_long_fall_from_room_3_into_room_10_enters_lava_death(self):
        scene = self.scene
        for facing in (0, 1):
            with self.subTest(facing=facing), patch.object(scene, 'render'):
                scene.jump_to_room(2, row=1, x=213, facing=facing)
                state, motion = scene.sequence_state, scene.terrain_motion
                scene.physics.select(scene.sequence_runtime, 12)
                scene.action, scene.player_x = state.action, state.target_x
                state.current_y, state.vertical_velocity = -45, 1
                state.horizontal_velocity = 0
                motion.falling = True
                for _ in range(40):
                    self.tick()
                    if motion.dead:
                        break
                self.assertEqual(scene.room_id, 9)
                self.assertEqual(scene.death.method, 5)
                self.assertEqual(state.source_sequence_id, 116)
                self.assertTrue(motion.dead)
                self.assertEqual(scene.game.caverns.lava.pools[9, 23].flags,
                                 0x8000 if facing else 0x8800)
                self.tick(30)
                self.assertTrue(scene.death.prompt_visible)

    def test_all_five_enhanced_pools_have_no_frozen_frames_at_loop_boundaries(self):
        from pop2.caverns import cavern_room, draw_cavern_lava
        from pop2.cavern_state import CavernState

        tables = self.scene.level_renderer.cavern_program['lava']
        for room in (5, 9, 14, 25, 30):
            state = CavernState()
            state.configure_lava(tables)
            state.lava.enter_room(room, tables['rooms'][str(room)])
            record = tables['rooms'][str(room)][0]
            box = (record['x'], record['bottom'] - 80, record['x'] + 140, record['bottom'])
            background = cavern_room(room).background
            previous = None
            for tick in range(100):
                state.lava.advance()
                frame = draw_cavern_lava(background.copy(), room, state).crop(box).tobytes()
                with self.subTest(room=room, tick=tick):
                    self.assertNotEqual(frame, previous)
                previous = frame

    def test_enhanced_surface_changes_only_the_lava_region(self):
        from pop2.caverns import cavern_room, draw_cavern_lava
        from pop2.cavern_state import CavernState
        from PIL import ImageChops

        tables = self.scene.level_renderer.cavern_program['lava']
        frames = []
        for enhanced in (False, True):
            state = CavernState()
            state.configure_lava(tables, enhanced=enhanced)
            state.lava.enter_room(5, tables['rooms']['5'])
            for _ in range(10):
                state.lava.advance()
            frames.append(draw_cavern_lava(cavern_room(5).background.copy(), 5, state))
        changed = ImageChops.difference(frames[0].convert('RGB'), frames[1].convert('RGB')).getbbox()
        self.assertIsNotNone(changed)
        self.assertGreaterEqual(changed[0], 357)
        self.assertGreaterEqual(changed[1], 335)
        self.assertLessEqual(changed[2], 497)
        self.assertLessEqual(changed[3], 365)

    def test_enhanced_surface_does_not_erase_rear_bubble_pixels(self):
        from pop2.caverns import cavern_room, draw_cavern_lava
        from pop2.cavern_state import CavernState
        from PIL import ImageChops

        tables = self.scene.level_renderer.cavern_program['lava']
        state = CavernState()
        state.configure_lava(tables)
        state.lava.enter_room(5, tables['rooms']['5'])
        pool = state.lava.pools[5, 27]
        pool.bubbles[0] = [1, 1, 0, -11, 58, 1]
        records = pool.drawings()
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0][0], 3614)
        background = cavern_room(5).background
        corrected = draw_cavern_lava(background.copy(), 5, state)
        with patch.object(pool, 'drawings', return_value=records[::-1]):
            erased = draw_cavern_lava(background.copy(), 5, state)
        changed = ImageChops.difference(corrected.convert('RGB'), erased.convert('RGB')).getbbox()
        self.assertIsNotNone(changed)
        self.assertGreaterEqual(changed[0], 415 + ENHANCED_BUBBLE_OFFSET_X)
        self.assertLessEqual(changed[2], 440 + ENHANCED_BUBBLE_OFFSET_X)
        self.assertGreaterEqual(changed[1], 335)
        self.assertLessEqual(changed[3], 354)

    def test_recess_is_shared_by_every_pool_and_camera_border_copy(self):
        from PIL import Image
        from pop2.caverns import cavern_assets, draw_cavern_lava, recessed_lava_surface
        from pop2.cavern_state import CavernState

        tables = self.scene.level_renderer.cavern_program['lava']
        sprite = recessed_lava_surface(cavern_assets()[2])
        dx, dy = tables['piece_offsets']
        for room, records in tables['rooms'].items():
            state = CavernState()
            state.configure_lava(tables)
            state.lava.enter_room(int(room), records)
            for pool in state.lava.pools.values():
                for bubble in pool.bubbles:
                    bubble[0] = 0
            frame = Image.new('RGBA', (510, 365))
            expected = frame.copy()
            for record in records:
                expected.paste(sprite, (record['x'] + dx, record['bottom'] + dy - 33), sprite)
            with self.subTest(room=room):
                self.assertEqual(draw_cavern_lava(frame, int(room), state).tobytes(), expected.tobytes())

    def test_native_ripples_cannot_cross_any_edge_of_the_liquid(self):
        from PIL import Image, ImageChops, ImageOps
        from pop2.caverns import (cavern_assets, cavern_room, draw_cavern_lava,
                                 recessed_lava_liquid_mask, recessed_lava_surface)
        from pop2.cavern_state import CavernState

        tables = self.scene.level_renderer.cavern_program['lava']
        surface = recessed_lava_surface(cavern_assets()[2])
        liquid = recessed_lava_liquid_mask(surface)
        dx, dy = tables['piece_offsets']
        visible = 0
        for room, records in tables['rooms'].items():
            room = int(room)
            state = CavernState()
            state.configure_lava(tables)
            state.lava.enter_room(room, records)
            for pool in state.lava.pools.values():
                for bubble in pool.bubbles:
                    bubble[0] = 0
            static = draw_cavern_lava(cavern_room(room).flattened(), room, state)
            allowed = Image.new('L', static.size)
            for record in records:
                allowed.paste(liquid, (record['x'] + dx, record['bottom'] + dy - surface.height))
            for event in tables['events']:
                if event[1] != 0:
                    continue
                for phase in range(3):
                    for pool in state.lava.pools.values():
                        pool.bubbles[0] = [1, phase, 0, event[2], event[3], event[4]]
                    frame = draw_cavern_lava(cavern_room(room).flattened(), room, state)
                    changed = ImageChops.difference(frame.convert('RGB'), static.convert('RGB')).convert('L')
                    visible += changed.getbbox() is not None
                    with self.subTest(room=room, event=event, phase=phase):
                        self.assertIsNone(ImageChops.multiply(changed, ImageOps.invert(allowed)).getbbox())
        self.assertGreater(visible, 0)

    def test_native_raised_bodies_are_not_sliced_at_the_seed_row(self):
        from pop2.caverns import cavern_assets, split_lava_bubble
        from pop2.render_opening import decode_shap

        _, resources, palette, _ = cavern_assets()
        for shape, point in ((3626, (4, 5)), (3632, (4, 9)), (3633, (5, 7)),
                             (3634, (6, 6)), (3635, (7, 5))):
            sprite = decode_shap(resources['SHAP'][shape]['data'], palette)
            surface, airborne = split_lava_bubble(sprite, shape)
            with self.subTest(shape=shape):
                self.assertEqual(airborne.getpixel(point), sprite.getpixel(point))
                self.assertNotEqual(airborne.getpixel(point)[3], 0)
                self.assertEqual(surface.getpixel(point)[3], 0)

    def test_raised_splash_pixels_rise_above_pool_but_stay_behind_front_rock(self):
        from PIL import ImageChops
        from pop2.caverns import (cavern_assets, cavern_room, draw_cavern_lava,
                                 recessed_lava_foreground_mask, recessed_lava_inset_mask,
                                 recessed_lava_liquid_mask,
                                 recessed_lava_surface, split_lava_bubble)
        from pop2.render_opening import decode_shap
        from pop2.cavern_state import CavernState

        tables, resources, palette, _ = cavern_assets()
        tables = tables['lava']
        state = CavernState()
        state.configure_lava(tables)
        state.lava.enter_room(5, tables['rooms']['5'])
        pool = state.lava.pools[5, 27]
        pool.bubbles[0] = [1, 7, 5, -15, 55, 0]
        record = tables['rooms']['5'][0]
        sprite = decode_shap(resources['SHAP'][3632]['data'], palette)
        raised = split_lava_bubble(sprite, 3632)[1]
        surface = recessed_lava_surface(palette)
        liquid = recessed_lava_liquid_mask(surface)
        occlusion = ImageChops.lighter(recessed_lava_inset_mask(surface), recessed_lava_foreground_mask(surface))
        frame = draw_cavern_lava(cavern_room(5).flattened(), 5, state)
        x = record['x'] + 55 + ENHANCED_BUBBLE_OFFSET_X
        y = record['bottom'] - 15 + ENHANCED_BUBBLE_OFFSET_Y - sprite.height
        outside = 0
        for yy in range(sprite.height):
            for xx in range(sprite.width):
                pixel = raised.getpixel((xx, yy))
                if not pixel[3]:
                    continue
                lx, ly = x + xx - record['x'], y + yy - (record['bottom'] - surface.height)
                if 0 <= lx < occlusion.width and 0 <= ly < occlusion.height and occlusion.getpixel((lx, ly)):
                    self.assertEqual(frame.getpixel((x + xx, y + yy)), surface.getpixel((lx, ly)))
                    continue
                self.assertEqual(frame.getpixel((x + xx, y + yy)), pixel)
                outside += not (0 <= lx < liquid.width and 0 <= ly < liquid.height
                                and liquid.getpixel((lx, ly)))
        self.assertGreater(outside, 0)

    def test_small_particle_tail_does_not_cross_near_perimeter(self):
        from PIL import Image, ImageChops, ImageOps
        from pop2.caverns import (cavern_assets, cavern_room, draw_cavern_lava,
                                 recessed_lava_foreground_mask, recessed_lava_surface)
        from pop2.cavern_state import CavernState

        program, _, palette, shapes = cavern_assets()
        tables = program['lava']
        state = CavernState()
        state.configure_lava(tables)
        state.lava.enter_room(5, tables['rooms']['5'])
        pool = state.lava.pools[5, 27]
        for bubble in pool.bubbles:
            bubble[0] = 0
        pool.bubbles[0] = [1, 5, 2, -7, 40, 1]
        record = tables['rooms']['5'][0]
        surface = recessed_lava_surface(palette)
        dx, dy = tables['piece_offsets']
        position = record['x'] + dx, record['bottom'] + dy - surface.height
        background = cavern_room(5).flattened()
        with patch.dict(shapes, {('recessed-front', 3614): Image.new('L', surface.size)}):
            before = draw_cavern_lava(background.copy(), 5, state)
        after = draw_cavern_lava(background.copy(), 5, state)
        for x, y in ((48, 24), (50, 24)):
            point = position[0] + x, position[1] + y
            self.assertNotEqual(before.getpixel(point), surface.getpixel((x, y)))
            self.assertEqual(after.getpixel(point), surface.getpixel((x, y)))
        allowed = Image.new('L', background.size)
        allowed.paste(recessed_lava_foreground_mask(surface), position)
        changed = ImageChops.difference(before.convert('RGB'), after.convert('RGB')).convert('L')
        self.assertIsNone(ImageChops.multiply(changed, ImageOps.invert(allowed)).getbbox())

    def test_reported_particle_frames_and_remaining_inset_rock_stay_occluded(self):
        from PIL import Image, ImageChops, ImageOps
        from pop2.caverns import (cavern_assets, cavern_room, draw_cavern_lava,
                                 recessed_lava_foreground_mask, recessed_lava_inset_mask, recessed_lava_surface)
        from pop2.cavern_state import CavernState

        program, _, palette, shapes = cavern_assets()
        tables = program['lava']
        state = CavernState()
        state.configure_lava(tables)
        state.lava.enter_room(5, tables['rooms']['5'])
        record = tables['rooms']['5'][0]
        surface = recessed_lava_surface(palette)
        inset = recessed_lava_inset_mask(surface)
        dx, dy = tables['piece_offsets']
        position = record['x'] + dx, record['bottom'] + dy - surface.height
        background = cavern_room(5).flattened()
        allowed = Image.new('L', background.size)
        allowed.paste(ImageChops.lighter(inset, recessed_lava_foreground_mask(surface)), position)
        for tick in range(48):
            with patch.dict(shapes, {('recessed-inset', 3614): Image.new('L', surface.size),
                                     ('recessed-front', 3614): Image.new('L', surface.size)}):
                before = draw_cavern_lava(background.copy(), 5, state)
            after = draw_cavern_lava(background.copy(), 5, state)
            changed = ImageChops.difference(before.convert('RGB'), after.convert('RGB')).convert('L')
            with self.subTest(gif_frame=tick + 1):
                self.assertIsNone(ImageChops.multiply(changed, ImageOps.invert(allowed)).getbbox())
                if tick in (18, 40):
                    for x, y in ((43, 12), (45, 12), (47, 12), (44, 13), (46, 13), (48, 13)):
                        point = position[0] + x, position[1] + y
                        self.assertNotEqual(before.getpixel(point), surface.getpixel((x, y)))
                        self.assertEqual(after.getpixel(point), surface.getpixel((x, y)))
                for y in range(surface.height):
                    for x in range(surface.width):
                        if inset.getpixel((x, y)):
                            point = position[0] + x, position[1] + y
                            self.assertEqual(after.getpixel(point), surface.getpixel((x, y)))
            state.lava.advance()

    def test_removed_right_crust_becomes_liquid_and_no_longer_hides_effects(self):
        from pop2.caverns import (cavern_assets, cavern_room, draw_cavern_lava,
                                 recessed_lava_foreground_mask, recessed_lava_inset_mask,
                                 recessed_lava_liquid_mask, recessed_lava_surface)
        from pop2.cavern_state import CavernState

        program, _, palette, _ = cavern_assets()
        tables = program['lava']
        surface = recessed_lava_surface(palette)
        liquid = recessed_lava_liquid_mask(surface)
        foreground = recessed_lava_foreground_mask(surface)
        inset = recessed_lava_inset_mask(surface)
        points = [(x, 10) for x in range(84, 95)] + [(x, 11) for x in (82, 83, 84, 85, 88, 89, 90)]
        for point in points:
            self.assertEqual(liquid.getpixel(point), 255)
            self.assertEqual(foreground.getpixel(point), 0)
            self.assertEqual(inset.getpixel(point), 0)
        state = CavernState()
        state.configure_lava(tables)
        state.lava.enter_room(5, tables['rooms']['5'])
        record = tables['rooms']['5'][0]
        dx, dy = tables['piece_offsets']
        changed = set()
        for _ in range(48):
            frame = draw_cavern_lava(cavern_room(5).flattened(), 5, state)
            for x, y in points:
                if frame.getpixel((record['x'] + dx + x, record['bottom'] + dy - surface.height + y)) != surface.getpixel((x, y)):
                    changed.add((x, y))
            state.lava.advance()
        self.assertGreater(len(changed), 0)

    def test_eight_right_edge_pixels_retain_their_lava_colors(self):
        from pop2.caverns import cavern_assets, recessed_lava_liquid_mask, recessed_lava_surface

        palette = cavern_assets()[2]
        surface = recessed_lava_surface(palette)
        liquid = recessed_lava_liquid_mask(surface)
        pixels = {(96, 9): 0xbd, (90, 10): 0xbb, (91, 10): 0xbc, (92, 10): 0xbc,
                  (93, 10): 0xbb, (94, 10): 0xbb, (95, 10): 0xb9, (90, 11): 0xb9}
        self.assertEqual(len(pixels), 8)
        for point, index in pixels.items():
            self.assertEqual(surface.getpixel(point), palette[index])
            self.assertEqual(liquid.getpixel(point), 255)
        self.assertEqual(surface.getpixel((96, 10)), palette[0x83])
        self.assertEqual(surface.getpixel((85, 11)), palette[0xbb])

    def test_surface_clipping_and_airborne_order_across_all_pools_and_death_phases(self):
        from PIL import Image, ImageChops
        from pop2.caverns import (cavern_assets, cavern_room, draw_cavern_lava,
                                 recessed_lava_foreground_mask, recessed_lava_inset_mask,
                                 recessed_lava_surface)
        from pop2.cavern_state import CavernState

        tables = self.scene.level_renderer.cavern_program['lava']
        _, _, palette, shapes = cavern_assets()
        sprite = recessed_lava_surface(palette)
        mask = recessed_lava_foreground_mask(sprite)
        inset = recessed_lava_inset_mask(sprite)
        for point in ((41, 13), (89, 12), (36, 26)):
            self.assertEqual(mask.getpixel(point), 255)
        for point in ((75, 5), (80, 10), (83, 11)):
            self.assertEqual(mask.getpixel(point), 0)
        dx, dy = tables['piece_offsets']
        for room, records in tables['rooms'].items():
            room = int(room)
            state = CavernState()
            state.configure_lava(tables)
            state.lava.enter_room(room, records)
            background = cavern_room(room).flattened()
            static = background.copy()
            for record in records:
                static.paste(sprite, (record['x'] + dx, record['bottom'] + dy - sprite.height), sprite)

            def check_frame():
                with patch.dict(shapes, {('recessed-front', 3614): Image.new('L', sprite.size),
                                         ('recessed-inset', 3614): Image.new('L', sprite.size)}):
                    uncut = draw_cavern_lava(background.copy(), room, state)
                corrected = draw_cavern_lava(background.copy(), room, state)
                expected = uncut.copy()
                for record in records:
                    x, y = record['x'] + dx, record['bottom'] + dy - sprite.height
                    expected.paste(static.crop((x, y, x + sprite.width, y + sprite.height)), (x, y), mask)
                for record in records:
                    pool = state.lava.pools[record['room'], record['cell']]
                    for shape, x, y, _ in pool.drawings():
                        if 3616 <= shape <= 3645:
                            raised = shapes['recessed-effect', shape][1]
                            expected.paste(raised, (record['x'] + x, record['bottom'] + y - raised.height), raised)
                for record in records:
                    x, y = record['x'] + dx, record['bottom'] + dy - sprite.height
                    expected.paste(static.crop((x, y, x + sprite.width, y + sprite.height)), (x, y), mask)
                    expected.paste(static.crop((x, y, x + sprite.width, y + sprite.height)), (x, y), inset)
                self.assertIsNone(ImageChops.difference(corrected.convert('RGB'), expected.convert('RGB')).getbbox())

            for tick in range(100):
                state.lava.advance()
                with self.subTest(room=room, tick=tick):
                    check_frame()
            for mode, roll in ((3, 0), (0, 1), (0, 0)):
                for facing in (0, 1):
                    for pool in state.lava.pools.values():
                        pool.begin_death(mode, facing, random_value=roll)
                    for tick in range(23):
                        with self.subTest(room=room, mode=mode, roll=roll, facing=facing, tick=tick):
                            check_frame()
                        state.lava.advance()


if __name__ == '__main__':
    unittest.main()
