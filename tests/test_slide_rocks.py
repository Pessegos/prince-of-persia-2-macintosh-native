import random
import struct
import unittest

from pop2.slide_rocks import SlideRocks, object_shape, signed_word
from tools.probe_temple_slide_rock_motion import motion_reference
from tools.probe_temple_slide_rock_trigger import trigger_reference


class FakeTerrain:
    """Rooms of kinds by (one-based room, column, row); room 2 is left of 1."""

    def __init__(self, kinds, default=1):
        self.kinds, self.default = kinds, default

    def neighbor(self, room, direction):
        return {(0, 'left'): 1}.get((room, direction))

    def tile(self, room, column, row):
        from types import SimpleNamespace
        return SimpleNamespace(kind=self.kinds.get((room + 1, column, row), self.default))


class SlideRockTests(unittest.TestCase):
    """The production model against Codex's native-checked references
    (asset-free: the references are pure Python)."""

    def test_trigger_matches_trigger_slide_rock(self):
        generator = random.Random(25)
        for _ in range(400):
            bank = [(generator.randrange(0, 500), 116, generator.choice((1, 2)), generator.choice((-1, 0, 1)),
                     generator.choice((-2, 0, 2, 5, 100)), generator.choice((6, 6, 4)),
                     generator.randrange(3), 0) for _ in range(generator.randrange(4))]
            room, cell, mode = generator.choice((1, 2)), generator.randrange(30), generator.choice((5, 6, 34))
            rocks = SlideRocks(list(bank))
            rocks.trigger(room, cell, mode)
            expected = trigger_reference(room, cell, 2 if mode == 5 else 1, bank)['bank']
            self.assertEqual(tuple(rocks.bank), expected)

    def test_motion_matches_10_1d5c(self):
        generator = random.Random(6)
        for _ in range(600):
            kinds = {(room, column, row): generator.choice((1, 1, 0, 20, 2, 25, 4))
                     for room in (1, 2) for column in range(-2, 12) for row in range(-1, 3)}
            terrain = FakeTerrain(kinds)
            row = generator.randrange(3)
            x = generator.randrange(0, 460)
            mob = (x, 116 + row * 120, 1, generator.choice((0, 0, 1)),
                   generator.choice((-2, -2, 1, 2, 7, 8, 9, 0, 100)), 6, row,
                   x + generator.choice((0, 51, 102)))
            prince = (generator.choice((15, 90)), generator.randrange(10), generator.randrange(4))
            rocks = SlideRocks()

            def tiles(room, column, row):
                return kinds.get((room, column, row), 1)

            def filled(at):
                probe = (at, *mob[1:])
                return rocks.span(terrain, probe, -1, 51) and rocks.span(terrain, probe, 0, 51)

            expected = motion_reference(mob, 2, filled=filled, tiles=tiles, prince=prince)
            record, events = rocks.move(terrain, mob, prince)
            self.assertEqual(record, expected['mob'], mob)
            self.assertEqual(events, [event[1] for event in expected['events'] if event[0] == 'actor'])

    def test_a_started_rock_slides_left_until_a_wall_then_stops(self):
        # Control -2 moves two pixels per update with no band test; the wall
        # edge marks it (mark 1, Y-1, cue 18), the next update stops it (100).
        terrain = FakeTerrain({(1, 3, 1): 20})
        rocks = SlideRocks()
        rocks.trigger(1, 18, 6)
        self.assertEqual(rocks.bank, [(408, 236, 1, 0, -2, 6, 1, 408)])
        for _ in range(400):
            rocks.update(terrain)
            if rocks.bank[0][4] == 100:
                break
        x, y, _room, mark, control, *_ = rocks.bank[0]
        self.assertEqual((mark, control, y), (0, 100, 236))
        self.assertLess(x, 408)
        self.assertGreater(x, 3 * 51)
        # A kind-5 plate only resumes a rock waiting at -2.
        rocks.trigger(1, 18, 5)
        self.assertEqual(rocks.bank[0][4], 100)

    def test_a_rock_without_a_left_room_is_removed(self):
        rocks = SlideRocks([(1, 116, 2, 0, -2, 6, 0, 51)])
        rocks.update(FakeTerrain({}))
        self.assertEqual(rocks.bank, [])

    def test_crush_admission_window_and_mode_four(self):
        mob = (300, 236, 1, 0, -2, 6, 1, 408)
        self.assertEqual([SlideRocks.crushes(mob, 1, 1, front) for front in (523, 524, 547, 548)],
                         [False, True, True, False])
        self.assertTrue(SlideRocks.crushes(mob, 1, 1, 0, sequence_mode=4))
        self.assertFalse(SlideRocks.crushes(mob, 1, 2, 530))

    def test_crush_admission_matches_10_16f6_with_the_saved_width(self):
        # Facing left, the front adds the saved ShapeBounds width (a5-0x3570);
        # before, the width was taken as 0.
        from tools.probe_temple_slide_rock_update import crush_admission_reference, make_prince

        generator = random.Random(0x3570)
        mob = (300, 236, 1, 0, -2, 6, 1, 408)
        for _ in range(500):
            room, row, facing = generator.choice((1, 2)), generator.choice((1, 2)), generator.choice((0, 1))
            width, mode = generator.randrange(0, 60), generator.choice((0, 0, 4))
            front = 523 + generator.randrange(-70, 30)
            prince = make_prince(room=room, row=row, x=front, facing=0 if facing else -1, mode=mode)
            self.assertEqual(SlideRocks.crushes(mob, room, row, front, mode, facing, width),
                             crush_admission_reference(mob, prince, width))
        self.assertTrue(SlideRocks.crushes(mob, 1, 1, 500, facing=0, width=30))
        self.assertFalse(SlideRocks.crushes(mob, 1, 1, 500, facing=1, width=30))

    def test_a_rock_in_the_left_room_is_drawn_510_pixels_left(self):
        # ComputeMobRect 5:32f6 projects a neighbour's rectangle: -510 for
        # both horizontal relations (native), -365 above, +365 below. Before,
        # only rocks in the view room were drawn.
        rocks = SlideRocks([(500, 236, 2, 0, -2, 6, 1, 459)])
        terrain = FakeTerrain({})
        own = rocks.objects(terrain, 2)
        seen = rocks.objects(terrain, 1)
        self.assertEqual(len(own), len(seen))
        for (kind, x, y, phase, clip), shifted in zip(own, seen):
            self.assertEqual(shifted, (kind, x - 510, y, phase,
                                       (clip[0], clip[1] - 510, clip[2], clip[3] - 510)))
        self.assertEqual(rocks.objects(terrain, 3), [])

    def test_objects_and_shapes_follow_atm_slide_rock_and_draw_mob(self):
        rocks = SlideRocks([(300, 236, 1, 0, -2, 6, 1, 408)])
        objects = rocks.objects(None, 1)
        self.assertEqual(objects[:2], [(7, 300, 236, 0, (104, 300, 237, 382)),
                                       (6, 351, 234, 0, (102, 351, 235, 433))])
        self.assertEqual({kind for kind, *_ in objects[2:]}, {8, 9})
        # A filled band above (no space) shortens the body to 111/109.
        filled = rocks.objects(FakeTerrain({}), 1)
        self.assertEqual([item[4][0] for item in filled[:2]], [236 - 111, 234 - 109])
        self.assertEqual([object_shape(kind, 1) for kind in (6, 7, 8, 9)], [3593, 3584, 3590, 3586])
        self.assertEqual(rocks.edge(1, 1), 579)
        self.assertEqual(signed_word(struct.unpack('>h', b'\x80\x00')[0] - 1), 32767)


if __name__ == '__main__':
    unittest.main()
