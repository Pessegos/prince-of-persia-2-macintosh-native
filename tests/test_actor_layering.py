import unittest
from types import SimpleNamespace

from pop2.combat_art import actor_draw_object, slab_crush_draw_state
from pop2.object_order import DrawObject, mob_kind, sort_objects
from pop2.scene_prototype import ScenePrototype
from pop2.sequence_runtime import SequenceState


class ActorLayeringTests(unittest.TestCase):
    """DrawObjs' one sort of the whole object table (3:39e6, 3:3b62, 3:3bec)."""

    def actor(self, name, x=100, bottom=346, facing=0, action=15, actor_type=2):
        state = SequenceState(2, target_x=x, facing=facing, action=action, actor_type=actor_type)
        return actor_draw_object(state, (x - 4, bottom - 78, x + 13, bottom), name)

    def order(self, *objects):
        return [item.item for item in sort_objects(list(objects))]

    def test_the_lower_bottom_is_drawn_later_whatever_the_cells(self):
        # The level-10 room-11 birdhead (bottom 349, cell 7) and the crouching
        # Prince to its right (343, cell 8): the old cell order put the Prince
        # in front.
        guard = self.actor('guard', x=367, bottom=349)
        prince = self.actor('prince', x=370, bottom=343, actor_type=0)
        self.assertEqual(self.order(prince, guard), ['prince', 'guard'])
        self.assertEqual(self.order(guard, prince), ['prince', 'guard'])
        # A body on the row above is drawn before one on the floor below.
        upper = self.actor('upper', x=100, bottom=226)
        lower = self.actor('lower', x=300, bottom=346, actor_type=0)
        self.assertEqual(self.order(lower, upper), ['upper', 'lower'])

    def test_equal_bottoms_go_left_to_right_by_drawing_point(self):
        left, right = self.actor('left', x=95), self.actor('right', x=100, actor_type=0)
        self.assertEqual(self.order(right, left), ['left', 'right'])
        # Facing right, the drawing point is the mirrored shape's right edge.
        mirrored = self.actor('mirrored', x=90, facing=1)
        self.assertEqual(self.order(mirrored, left), ['left', 'mirrored'])

    def test_offscreen_bodies_have_no_first_bucket(self):
        offscreen = self.actor('offscreen', x=560, bottom=390, actor_type=0)
        visible = self.actor('visible', x=500, bottom=346)
        self.assertEqual(self.order(offscreen, visible), ['visible', 'offscreen'])

    def test_heads_in_their_back_poses_go_behind_the_others(self):
        prince = self.actor('prince', bottom=346, actor_type=0)
        for pose in (166, 181):
            head = self.actor('head', bottom=360, action=pose, actor_type=7)
            self.assertEqual(self.order(prince, head), ['head', 'prince'], pose)
        hovering = self.actor('head', bottom=360, action=165, actor_type=8)
        self.assertEqual(self.order(prince, hovering), ['prince', 'head'])

    def test_a_falling_slab_above_the_feet_is_drawn_over_the_body(self):
        prince = self.actor('prince', bottom=346, actor_type=0)
        for y, expected in ((300, ['prince', 'slab']), (346, ['prince', 'slab']),
                            (360, ['slab', 'prince'])):
            slab = DrawObject(120, y, mob_kind(0), 0, 'slab')
            self.assertEqual(self.order(prince, slab), expected, y)
            self.assertEqual(self.order(slab, prince), expected, y)

    def test_priorities_put_flames_and_bursts_in_front_and_the_shadow_flame_behind(self):
        shadow = self.actor('shadow', bottom=346, actor_type=6)
        burst = DrawObject(100, 200, 5, 0, 'burst')
        behind = DrawObject(100, 400, 14, 0, 'flame')
        self.assertEqual(self.order(burst, shadow, behind), ['flame', 'shadow', 'burst'])

    def test_a_slab_sorted_after_a_body_covers_only_his_pixels(self):
        from PIL import Image

        body = Image.new('RGBA', (20, 20))
        body.paste((255, 255, 255, 255), (0, 0, 10, 20))
        slab = Image.new('RGBA', (20, 20))
        slab.paste((157, 114, 98, 255), (5, 0, 15, 20))
        state = SequenceState(2, target_x=4, action=15, actor_type=0)
        actor = (state, None, (0, 0, 9, 19), 2, body)
        scene = SimpleNamespace(composite_actor=lambda frame, layer, *_args: Image.alpha_composite(frame, layer))
        drawn = ScenePrototype.draw_objects(scene, Image.new('RGBA', (20, 20), (0, 0, 0, 255)),
                                            [actor], [(0, 4, 10, slab)])
        self.assertEqual(drawn.getpixel((7, 5)), (157, 114, 98, 255))   # slab over the body
        self.assertEqual(drawn.getpixel((2, 5)), (255, 255, 255, 255))  # the body elsewhere
        self.assertEqual(drawn.getpixel((12, 5)), (0, 0, 0, 255))       # not repainted outside him
        below = ScenePrototype.draw_objects(scene, Image.new('RGBA', (20, 20), (0, 0, 0, 255)),
                                            [actor], [(0, 4, 30, slab)])
        self.assertEqual(below.getpixel((7, 5)), (255, 255, 255, 255))


class SlabCrushPresentationTests(unittest.TestCase):
    def test_first_crush_frame_keeps_expression_without_mutating_simulation(self):
        for kind in (7, 8):
            with self.subTest(kind=kind):
                state = SequenceState(146, cursor=1, action=150, actor_type=kind,
                                      target_x=200, current_y=-33)
                actor = SimpleNamespace(state=state)
                before = vars(state).copy()
                drawn = slab_crush_draw_state(actor, {id(actor): (actor, 165)})
                self.assertEqual(drawn.action, 165)
                self.assertEqual(vars(state), before)
                self.assertEqual(drawn.target_x, state.target_x)
                self.assertEqual(drawn.current_y, state.current_y)
                self.assertEqual(drawn.cursor, 1)

    def test_later_frames_other_deaths_and_stale_snapshots_use_real_pose(self):
        for sequence, cursor, pose, kind in (
                (146, 10, 226, 7), (154, 1, 150, 7), (169, 1, 288, 11),
                (146, 1, 150, 2)):
            with self.subTest(sequence=sequence, kind=kind):
                actor = SimpleNamespace(state=SequenceState(
                    sequence, cursor=cursor, action=pose, actor_type=kind))
                self.assertIs(slab_crush_draw_state(actor, {id(actor): (actor, 165)}), actor.state)
        actor = SimpleNamespace(state=SequenceState(146, cursor=1, action=150, actor_type=7))
        self.assertIs(slab_crush_draw_state(actor, {}), actor.state)
        self.assertIs(slab_crush_draw_state(actor, {id(actor): (object(), 165)}), actor.state)


if __name__ == '__main__':
    unittest.main()
