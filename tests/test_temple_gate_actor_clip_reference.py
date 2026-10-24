import unittest

from tools.probe_temple_gate_actor_clip import clip_reference, put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_gate_hanging_animation import hanging_animation_reference
from tools.probe_temple_slide_rock_update import actor_word


# Small semantic fixtures, not the original resource bank.
CLIPS = {47: (-7, 5, -5, -16, 50, 51, 52, -1, 2),
         2: (-7, 0, 15, -1, 2), 9: (-7, 2, 91, -1, 210),
         210: (90, 89, 88, 87)}


def hanging_actor(facing=-1, x=400):
    actor = bytearray(actor_fixture(3, 1, 2, facing, 2))
    for field, value in ((4, x), (10, 91), (28, -1), (30, 3), (34, 0), (36, 3), (38, 9), (40, 9)):
        put_actor(actor, field, value)
    return bytes(actor)


class TempleGateActorClipTests(unittest.TestCase):
    def selected(self, actor=None):
        actor = hanging_actor() if actor is None else actor
        return hanging_animation_reference(3, 1, actor, bytes(range(62)), 3, 2)['prince']

    def test_gate_selection_does_not_execute_the_first_clip_instruction(self):
        actor = self.selected()
        self.assertEqual(tuple(actor_word(actor, field) for field in (4, 10, 16, 36, 38, 40)),
                         (400, 91, 2, 0, 47, 47))

    def test_first_animation_changes_mode_and_x_before_showing_pose50(self):
        actor = clip_reference(self.selected(), CLIPS)['actor']
        self.assertEqual(tuple(actor_word(actor, field) for field in (4, 10, 16, 36, 38, 40)),
                         (416, 50, 5, 5, 47, 47))

    def test_three_poses_then_idle_link_retain_the_selected_source(self):
        actor = self.selected()
        poses = []
        for _ in range(6):
            actor = clip_reference(actor, CLIPS)['actor']
            poses.append(actor_word(actor, 10))
        self.assertEqual(poses, [50, 51, 52, 15, 15, 15])
        self.assertEqual(tuple(actor_word(actor, field) for field in (4, 16, 36, 38, 40)),
                         (416, 0, 3, 2, 47))

    def test_link_unlocks_old_handle_and_locks_new_handle_before_reading_pose(self):
        actor = self.selected()
        for _ in range(3):
            actor = clip_reference(actor, CLIPS)['actor']
        result = clip_reference(actor, CLIPS)
        self.assertEqual(result['events'], [('animate', 47, 7), ('sequence', 47),
                         ('handle', 'HGetState'), ('handle', 'HLock'), ('handle', 'HSetState'),
                         ('sequence', 2), ('handle', 'HGetState'), ('handle', 'HLock'),
                         ('handle', 'HSetState')])

    def test_rejected_facing_keeps_hanging_clip_instead_of_displacing_actor(self):
        actor = hanging_actor(facing=0)
        selected = self.selected(actor)
        self.assertEqual(selected, actor)
        result = clip_reference(selected, CLIPS)['actor']
        self.assertEqual(tuple(actor_word(result, field) for field in (4, 10, 16, 38, 40)),
                         (400, 90, 2, 210, 9))

    def test_animation_does_not_change_health_alive_y_or_actor_canaries(self):
        actor = self.selected()
        result = clip_reference(actor, CLIPS)['actor']
        changed = {4, 5, 10, 11, 16, 17, 36, 37}
        self.assertTrue(all(a == b for i, (a, b) in enumerate(zip(actor, result)) if i not in changed))
        self.assertEqual(tuple(actor_word(result, field) for field in (6, 28, 30, 34)),
                         tuple(actor_word(actor, field) for field in (6, 28, 30, 34)))

    def test_relative_x_uses_signed_word_wrapping(self):
        actor = clip_reference(self.selected(hanging_actor(x=32760)), CLIPS)['actor']
        self.assertEqual(actor_word(actor, 4), -32760)

    def test_missing_initial_clip_returns_without_actor_changes(self):
        actor = self.selected()
        result = clip_reference(actor, {})
        self.assertEqual(result, dict(actor=actor, events=[('animate', 47, 0), ('sequence', 47)]))

    def test_decoder_rejects_uncovered_opcodes_truncation_links_and_actor_kinds(self):
        actor = self.selected()
        for clips in ({47: (-8, 0, 0)}, {47: (-7,)}, {47: (-1, 11)}, {47: (-1, 99)}):
            with self.subTest(clips=clips), self.assertRaises(ValueError):
                clip_reference(actor, clips)
        other = bytearray(actor)
        put_actor(other, 8, 1)
        with self.assertRaises(ValueError):
            clip_reference(bytes(other), CLIPS)


if __name__ == '__main__':
    unittest.main()
