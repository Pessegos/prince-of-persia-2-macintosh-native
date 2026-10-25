"""Asset-free connected admission/mechanism regressions; no native assets needed."""

from dataclasses import replace
import struct
import unittest

from tests.test_temple_plate_lifetime_reference import ROCK, fixture, timer, depressed
from tools.probe_temple_actor_plate_lifetime import actor_plate_step, actor_variant
from tools.probe_temple_pressure_admission import PressureActor


ACTOR = PressureActor(1, 3, 2, 356)


def step(state, reader, operation='check', actor=ACTOR):
    reader.requests.clear()
    return actor_plate_step(dict(state, events=[], object_calls=[], rock_calls=[]), reader, operation, actor)


class TempleActorPlateLifetimeTests(unittest.TestCase):
    def test_admission_reads_above_then_current_before_activating_the_rock(self):
        state, reader = fixture()
        state = step(state, reader)
        self.assertEqual(reader.requests, [(1, 3, 1), (1, 3, 2), (1, 9, 2)])
        self.assertEqual(state['pressure_requests'], [('push', (0, -1))])
        self.assertEqual((state['bank'], state['trobs']), ((ROCK,), ((23, 1, 1, 6),)))
        self.assertEqual(reader.cache[2:4], (29, 1))

    def test_rejected_actor_cannot_refresh_a_stale_cache(self):
        state, reader = fixture()
        state = step(state, reader)
        bank, cache = state['bank'], reader.cache
        state = step(state, reader, actor=replace(ACTOR, kind=1, selected=29))
        self.assertEqual((state['pressure_requests'], reader.requests), ([], []))
        self.assertEqual((state['bank'], reader.cache, timer(reader)), (bank, cache, 5))
        state = step(state, reader, 'animate')
        self.assertEqual(timer(reader), 4)

    def test_aux_rejection_still_leaves_the_above_cell_cached(self):
        state, reader = fixture()
        state = step(state, reader)
        state = step(state, reader, actor=replace(ACTOR, aux=0))
        self.assertEqual((state['pressure_requests'], reader.requests), ([], [(1, 3, 1)]))
        self.assertEqual(reader.cache[2:4], (13, 1))
        self.assertEqual(timer(reader), 5)

    def test_permanent_actor_sets_timer_before_push_and_never_registers_source_trob(self):
        state, reader = fixture()
        state = step(state, reader, actor=replace(ACTOR, alive=0, pose=185))
        self.assertEqual(state['pressure_requests'], [('permanent', ()), ('push', (6, 4))])
        self.assertEqual((timer(reader), state['trobs'], state['bank']), (31, (), (ROCK,)))
        self.assertTrue(depressed(reader))
        self.assertEqual(state['press_flag'], 4321)
        self.assertFalse(any(event[0] in ('sound', 'redraw') for event in state['events']))
        for _ in range(8):
            state = step(state, reader, 'animate')
        state = step(state, reader)
        self.assertEqual((timer(reader), state['trobs'], depressed(reader)), (31, (), True))

    def test_nonnegative_alive_type4_remains_an_ordinary_releasing_press(self):
        state, reader = fixture()
        state = step(state, reader, actor=replace(ACTOR, kind=4, alive=0))
        self.assertEqual(state['pressure_requests'], [('push', (0, -1))])
        self.assertEqual((timer(reader), len(state['trobs'])), (5, 1))
        for _ in range(5):
            state = step(state, reader, 'animate')
        self.assertEqual((timer(reader), depressed(reader), state['trobs']), (0, False, ()))

    def test_special_pose_can_press_above_without_fram_or_normal_mode_admission(self):
        state, reader = fixture()
        state = step(state, reader, actor=actor_variant(ACTOR, 'above'))
        self.assertEqual(state['pressure_requests'], [('push', (0, -1))])
        self.assertEqual(reader.requests, [(1, 3, 2), (1, 9, 2)])
        self.assertEqual((state['bank'], timer(reader)), ((ROCK,), 5))

    def test_full_trob_bank_admits_contact_but_cannot_register_the_source(self):
        state, reader = fixture(trobs=((9, 2, 1, 1),) * 20)
        state = step(state, reader)
        self.assertEqual((timer(reader), len(state['trobs']), state['bank']), (5, 20, (ROCK,)))
        state = step(state, reader, 'animate')
        state = step(state, reader)
        self.assertEqual((timer(reader), state['trobs'], depressed(reader)), (5, (), True))

    def test_living_y_boundary_is_inclusive_after_actual_admission(self):
        for y, expected in ((334, 0), (335, 1), (336, 1)):
            state, reader = fixture()
            state = step(state, reader, actor=replace(ACTOR, y=y))
            self.assertEqual(len(state['pressure_requests']), expected)

    def test_loose_floor_endpoint_stays_a_request_not_a_connected_implementation(self):
        state, reader = fixture()
        level = bytearray(reader.level)
        struct.pack_into('>h', level, 13 * 2, 11)
        reader.level = level
        state = step(state, reader, actor=replace(ACTOR, pose=79))
        self.assertEqual(state['pressure_requests'], [('loose', (0,))])
        self.assertEqual((state['bank'], state['trobs'], state['press_flag']), ((), (), 4321))

    def test_invalid_plan_and_operation_names_are_rejected(self):
        state, reader = fixture()
        with self.assertRaises(ValueError):
            actor_variant(ACTOR, 'frame')
        with self.assertRaises(ValueError):
            step(state, reader, 'frame')


if __name__ == '__main__':
    unittest.main()
