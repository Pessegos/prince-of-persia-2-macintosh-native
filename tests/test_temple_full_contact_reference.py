import struct
import unittest

from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_contact import ContactCellReader
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_slide_rock_update import actor_word
from tools.probe_temple_full_contact import full_contact_reference


class TempleFullContactTests(unittest.TestCase):
    def query(self, *, phase=1, metadata=(0, 0), available=True, source=9,
              armed=0, pose=1, alive=-1, overlap=(255, 255), ahead=0):
        level = bytearray(0x218c)
        for offset, value in ((0x2180, 1), (0x2186, 2), (0x218a, 10),
                              (14 * 2, 4), (13 * 2, ahead), (0x780 + 14 * 4, phase)):
            struct.pack_into('>H', level, offset, value)
        actor = bytearray(actor_fixture(1, 1, 4, -1, 0))
        for offset, value in ((4, 460), (10, pose), (26, armed), (28, alive),
                              (30, 3), (40, source), (42, 20), (46, 94)):
            put_actor(actor, offset, value)
        reader = ContactCellReader(level, 1)
        result = full_contact_reference(bytes(actor), reader, tuple((v,) * 10 for v in overlap),
                                        (445, 475), metadata, 1, (0,) * 6, available=available)
        return result, bytes(actor), reader

    def test_soft_contact_selects50_but_keeps_the_old_pose_and_cached_frame_for_distance(self):
        result, actor, reader = self.query(metadata=(8, 0))
        self.assertEqual([actor_word(result['actor'], o) for o in (36, 38, 40)], [0, 50, 50])
        self.assertEqual((actor_word(result['actor'], 10), actor_word(result['actor'], 4)), (1, 467))
        self.assertEqual((result['distance'], result['reason'], result['remainder']), (18, 0, 18))
        self.assertEqual(result['events'], [('resource', 50), ('distance',)])
        self.assertEqual(reader.requests, [(1, 4, 1), (1, 4, 1), (1, 3, 1)])
        self.assertEqual(actor_word(actor, 4), 460)

    def test_missing_resource_preserves_the_clip_but_still_uses_the_real_distance(self):
        result, actor, _ = self.query(metadata=(8, 0), available=False)
        self.assertEqual(result['actor'][36:42], actor[36:42])
        self.assertEqual(actor_word(result['actor'], 4), 467)

    def test_source50_prevents_repeat_distance_or_position_correction(self):
        result, actor, reader = self.query(metadata=(8, 0), source=50)
        self.assertEqual((result['actor'], result['events']), (actor, []))
        self.assertEqual((result['anchor'], result['remainder'], result['reason']), (73, 79, 71))
        self.assertEqual(reader.requests, [(1, 4, 1)])

    def test_clear_forward_floor_uses_safe42_instead_of_a_prepared_push(self):
        result, _, _ = self.query(ahead=1, metadata=(8, 0))
        self.assertEqual((result['distance'], result['reason'], actor_word(result['actor'], 4)),
                         (42, 2, 460))
        self.assertEqual(result['remainder'], 79)

    def test_phase_zero_ejects_and_high_byte_only_foreground_uses_the_soft_path(self):
        hard, _, _ = self.query(phase=0)
        soft, _, _ = self.query(phase=0x8100)
        self.assertEqual((hard['events'], hard['mark'], actor_word(hard['actor'], 4)),
                         ([('eject',)], 1, 458))
        self.assertEqual((soft['events'], soft['mark']), ([('resource', 50), ('distance',)], 79))
        self.assertEqual((actor_word(hard['actor'], 28), actor_word(hard['actor'], 30)), (-1, 3))

    def test_armed_and_pose109_hard_paths_do_not_animate_or_measure_the_soft_distance(self):
        for kwargs in ({'armed': 1}, {'pose': 109}):
            result, actor, _ = self.query(**kwargs)
            self.assertEqual(result['events'], [('eject',)])
            self.assertEqual(result['actor'][36:42], actor[36:42])
            self.assertEqual((result['remainder'], result['reason']), (79, 71))

    def test_open_or_exact_overlap_rejection_and_early_exits_do_not_run_either_response(self):
        for kwargs in ({'phase': 184}, {'overlap': (511, 511)}, {'source': 118}, {'alive': 0}):
            result, actor, _ = self.query(**kwargs)
            self.assertEqual((result['actor'], result['events'], result['mark']), (actor, [], 79))
        self.assertEqual(self.query(overlap=(511, 255))[0]['events'],
                         [('resource', 50), ('distance',)])


if __name__ == '__main__':
    unittest.main()
