"""Level 14's moving scenery (CODE 9 trobs): serpents, face, crystals, gargoyles."""

import random
import unittest

from pop2.final_scenery import (
    ACTIVE, TROB, SceneryImage, crystal_image, crystal_step, enter_room, face_images,
    face_step, gargoyle_image, gargoyle_step, invalidates, serpent_images, serpent_step, step,
)
from pop2.paths import ASSET_DIR


class FixedRandom:
    def __init__(self, *values):
        self.values = list(values)
        self.calls = []

    def randrange(self, stop):
        self.calls.append(stop)
        return self.values.pop(0)


class SerpentTests(unittest.TestCase):
    def test_the_frames_run_once_then_the_timer_never_returns_to_zero(self):
        rng = FixedRandom(0, 4, 0)
        word, words = 0, []
        for _ in range(6):
            word = serpent_step(word, rng)
            words.append(word)
        # Frames 1-5 with the timer at zero, then Rnd(60) + 30 at frame 5.
        self.assertEqual(words, [1, 2, 3, 4, 5, 5 | 30 << 3])
        for _ in range(29):
            word = serpent_step(word, rng)
        self.assertEqual(word, 5 | 1 << 3)
        # 9:1c66-1c74: the expired wait draws Rnd(5) + 1 and sets frame 7.
        word = serpent_step(word, rng)
        self.assertEqual(word, 7 | 5 << 3)
        for _ in range(4):
            word = serpent_step(word, rng)
        word = serpent_step(word, rng)
        self.assertEqual(word, 7 | 1 << 3)
        self.assertEqual(rng.calls, [61, 6, 6])
        # A model whose wait ends in a new animation (timer 0) is rejected.
        self.assertNotEqual(word & 0x7f8, 0)

    def test_the_frame_seven_word_draws_only_the_left_fang(self):
        # DrawFinlSpider 9:1d28: a5-0x29a6[7] reads a5-0x299a[1].
        self.assertEqual(serpent_images(0), (SceneryImage(3, 11), SceneryImage(7, 11)))
        self.assertEqual(serpent_images(5 | 30 << 3), (SceneryImage(4, 11), SceneryImage(7, 11)))
        self.assertEqual(serpent_images(7 | 3 << 3), (SceneryImage(8, 11), SceneryImage(7, 11)))
        self.assertEqual(serpent_images(ACTIVE | 2 | 3 << 3),
                         (SceneryImage(3, 11), SceneryImage(9, 11)))

    def test_only_a_zero_timer_redraws(self):
        self.assertEqual(step(2, 4, FixedRandom()), (5, True))
        self.assertEqual(step(2, 5 | 2 << 3, FixedRandom()), (5 | 1 << 3, False))


class FaceTests(unittest.TestCase):
    def test_the_face_blinks_at_twelve_to_fifteen_and_ends(self):
        word, records, dirty = 0, [], []
        for _ in range(15):
            after = face_step(word)
            dirty.append(invalidates(3, word, after))
            word = after
            records.append(tuple(image.record for image in face_images(word)))
        self.assertEqual(records, [()] * 11 + [(3,), (4,), (4,), (3,)])
        self.assertEqual(dirty, [False] * 11 + [True] * 4)
        self.assertIsNone(face_step(word))
        self.assertFalse(invalidates(3, word, None))


class GlintTests(unittest.TestCase):
    def test_a_crystal_waits_glints_five_frames_and_waits_again(self):
        rng = FixedRandom(7)
        word = TROB | 3 | 2 << 4
        word = crystal_step(word, rng)
        self.assertEqual(word, TROB | 3 | 1 << 4)
        word = crystal_step(word, rng)
        self.assertEqual(word, TROB | ACTIVE | 3)
        images = []
        for _ in range(5):
            before, word = word, crystal_step(word, rng)
            self.assertTrue(invalidates(5, before, word))
            images.append(crystal_image(word))
        self.assertEqual([image.record for image in images], [8, 9, 10, 11, 8])
        self.assertEqual({(image.dx, image.dy, image.draw_pass) for image in images}, {(201, 191, 0)})
        before, word = word, crystal_step(word, rng)
        self.assertEqual(word, TROB | 3 | 47 << 4)
        # No redraw: the last small glint stays on the screen.
        self.assertFalse(invalidates(5, before, word))
        self.assertIsNone(crystal_image(word))
        self.assertEqual(rng.calls, [41])

    def test_gargoyles_pair_with_their_rooms_and_records(self):
        self.assertIsNone(gargoyle_step(TROB | 2, 6, FixedRandom()))
        self.assertIsNone(gargoyle_step(TROB | 1, 7, FixedRandom()))
        word = TROB | ACTIVE | 1
        records = []
        for _ in range(7):
            word = gargoyle_step(word, 6, FixedRandom())
            records.append(gargoyle_image(word).record)
        self.assertEqual(records, [8, 7, 8, 9, 7, 8, 6])
        self.assertEqual(gargoyle_image(TROB | ACTIVE | 0 | 1 << 4),
                         SceneryImage(4, 0, x=172, bottom=147))
        self.assertEqual(gargoyle_image(TROB | ACTIVE | 3 | 7 << 4),
                         SceneryImage(6, 1, x=320, bottom=274))
        self.assertEqual(gargoyle_step(word, 6, FixedRandom(40)), TROB | 1 | 80 << 4)

    def test_room_entry_triggers_crystals_in_cell_order_up_to_nine(self):
        cells = {cell: (0, TROB | 0x7f0) for cell in range(12)}
        rng = FixedRandom(*range(9))
        words = enter_room(5, cells, rng)
        self.assertEqual(sorted(words), list(range(9)))
        self.assertEqual([words[cell] for cell in range(9)],
                         [TROB | index | index << 4 for index in range(9)])
        self.assertEqual(rng.calls, [41] * 9)
        words = enter_room(7, {22: (1, TROB), 26: (1, TROB)}, FixedRandom(0, 0))
        self.assertEqual(words, {22: TROB | 2, 26: TROB | 3})
        self.assertEqual(enter_room(2, {23: (40, 0x2d), 24: (0, 0)}, FixedRandom()), {23: 0x2d})
        self.assertEqual(enter_room(3, {1: (31, 0)}, FixedRandom()), {1: 0})


INSTALLED = all((ASSET_DIR / name).is_file() for name in ('Final.rsrc', 'final_level14.json'))


@unittest.skipUnless(INSTALLED, 'Imported Macintosh final level required')
class LevelFourteenSceneryTests(unittest.TestCase):
    def setUp(self):
        from tools.audit_temple_routes import Harness

        self.harness = Harness(14, draw=True)
        self.scene = self.harness.scene
        self.scene.combat.rng = random.Random(3)
        self.caverns = self.scene.game.caverns

    def tearDown(self):
        self.harness.close()

    def frame(self):
        self.scene.render()
        return self.scene.native_viewport

    def test_room_three_draws_its_fangs_from_the_spider_word(self):
        from pop2.caverns import FINAL_MOVING_SHAPES, cavern_assets

        program, *_ = cavern_assets(14)
        self.assertEqual(sorted({command[1] for command in program['rooms']['2']
                                 if command[1] in FINAL_MOVING_SHAPES[2]}), [4053, 4057])
        scene = self.scene
        scene.jump_to_room(2, row=2, x=450, facing=0)
        self.harness.tick(3)
        rest = self.frame().crop((143, 290, 244, 348))
        self.assertEqual(self.caverns.final_scenery_drawn[2, 23] & 0x7f8, 0)
        self.harness.tick(10)
        moved = self.frame().crop((143, 290, 244, 348))
        self.assertEqual(self.caverns.final_scenery_drawn[2, 23] & 7, 5)
        self.assertNotEqual(rest.tobytes(), moved.tobytes())
        # The static room no longer holds the resting pose.
        empty = scene.level_renderer.room(2, self.caverns).background.crop((142, 290, 243, 348))
        self.assertNotEqual(empty.convert('RGB').tobytes(), rest.convert('RGB').tobytes())
        self.harness.tick(100)
        self.assertEqual(self.caverns.final_scenery[2, 23] & 7, 7)
        # The frame-7 word is drawn only once the room is drawn again.
        self.assertEqual(self.caverns.final_scenery_drawn[2, 23] & 7, 5)
        scene.jump_to_room(3, row=2, x=200, facing=0)
        self.harness.tick(2)
        scene.jump_to_room(2, row=2, x=450, facing=0)
        self.harness.tick(1)
        self.assertEqual(self.caverns.final_scenery_drawn[2, 23] & 7, 7)

    def test_a_room_not_yet_entered_draws_its_resting_fangs(self):
        # A map preview: no trob words yet, so the level's own word (rest).
        from pop2.caverns import draw_final_scenery
        from pop2.cavern_state import CavernState
        from pop2.terrain import LevelMap

        renderer = self.scene.level_renderer
        background = renderer.room(2, self.caverns).background.convert('RGBA')
        fresh = CavernState()
        self.assertFalse(fresh.final_scenery_drawn)
        bare = draw_final_scenery(background.copy(), 2, fresh)
        fangs = draw_final_scenery(background.copy(), 2, fresh,
                                   terrain=LevelMap(renderer.level.data))
        box = (142, 290, 243, 348)
        self.assertEqual(bare.crop(box).tobytes(), background.crop(box).tobytes())
        self.assertNotEqual(fangs.crop(box).tobytes(), background.crop(box).tobytes())

    def test_room_six_crystals_glint_and_keep_a_small_glint(self):
        scene = self.scene
        scene.jump_to_room(5, row=2, x=250, facing=0)
        self.harness.tick(1)
        first = dict(self.caverns.final_scenery_drawn)
        self.assertEqual(sorted(cell for room, cell in first if room == 5),
                         [9, 11, 12, 14, 16, 17, 20, 24, 28])
        self.assertEqual(sorted(word & 15 for word in first.values()), list(range(9)))
        before = self.frame().copy()
        self.harness.tick(130)
        drawn = self.caverns.final_scenery_drawn
        self.assertTrue(all(word & ACTIVE for word in drawn.values()))
        after = self.frame()
        self.assertIsNotNone(crystal_image(drawn[5, 28]))
        # Crystal 8 (cell 28) is moved by (296, 403) from its record.
        box = (400, 255, 440, 300)
        self.assertNotEqual(before.crop(box).tobytes(), after.crop(box).tobytes())

    def test_scenery_words_survive_a_save(self):
        from pathlib import Path
        import tempfile
        from pop2.save_game import capture_snapshot, read_snapshot, write_save

        scene = self.scene
        scene.jump_to_room(6, row=2, x=100, facing=0)
        self.harness.tick(5)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'scenery.pop2save'
            write_save(path, capture_snapshot(scene.game))
            restored, _ = read_snapshot(path, scene.resources)
        self.assertEqual(restored.caverns.final_scenery, self.caverns.final_scenery)
        self.assertEqual(restored.caverns.final_scenery_drawn, self.caverns.final_scenery_drawn)
        self.assertEqual(restored.caverns.final_scenery_room, 6)


if __name__ == '__main__':
    unittest.main()
