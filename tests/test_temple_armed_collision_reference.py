import struct
import unittest

from tools.probe_temple_armed_collision import armed_collision_reference
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_slide_rock_update import actor_word


class TempleArmedCollisionTests(unittest.TestCase):
    def query(self, *, pose=153, facing=0, side=-1, gate=60, tile=4, available=True,
              vy=49, alive=-1, hp=3, pending=0, active=2, selected=2, x=460, bank=(), env=2,
              raw_kind=None):
        actor = bytearray(actor_fixture(1, 1, 4, facing, 0))
        for offset,value in ((4,x),(6,180),(8,0),(10,pose),(18,5),(20,vy),(24,17),(26,1),
                (28,alive),(30,hp),(34,pending),(36,0),(38,active),(40,selected)):
            put_actor(actor,offset,value)
        level=bytearray(0x2400)
        struct.pack_into('>h',level,0x2186,env)
        if raw_kind is not None:
            for cell in range(10,20):struct.pack_into('>h',level,cell*2,raw_kind)
        sequences={2:(-7,0,15),55:(-7,1,-5,-6,207),64:(-7,5,-5,-10,157),
                   65:(-7,5,160),93:(-7,1,-5,-10,234)}
        return armed_collision_reference(bytes(actor),side,level,bank,(tile,gate,14,1,4,1),sequences,
                                         struct.pack('>5h',1,0,0,0,0)*352,bytes(8),available=available)

    def test_armed_bypasses_unarmed_height_redirect(self):
        result=self.query()
        self.assertEqual(result['events'][0],('align',))
        self.assertEqual((actor_word(result['actor'],6),actor_word(result['actor'],40)),(226,64))

    def test_gate_threshold_is_strictly60_and_uses_low_byte(self):
        for gate,selected in ((59,64),(60,64),(61,2),(184,2),(0x813c,64),(0x813d,2)):
            with self.subTest(gate=gate):
                result=self.query(gate=gate)
                self.assertEqual(actor_word(result['actor'],40),selected)
        self.assertEqual(actor_word(self.query(tile=1,gate=255)['actor'],40),64)

    def test_only_four_prince_strike_poses_admit_gate_suppression(self):
        for pose in (153,154,244,245):
            result=self.query(pose=pose,gate=61)
            self.assertEqual(actor_word(result['actor'],40),2)
            self.assertEqual(result['mark'],73)
            self.assertNotIn(('frame',),result['events'])
        for pose in (152,155,243,246):
            self.assertEqual(actor_word(self.query(pose=pose,gate=61)['actor'],40),64)

    def test_collision_side_selects_distinct_relative_reactions(self):
        front=self.query(side=0)
        back=self.query(side=-1)
        self.assertEqual([actor_word(front['actor'],o) for o in (4,10,16,40)],[466,160,5,65])
        self.assertEqual([actor_word(back['actor'],o) for o in (4,10,16,40)],[475,157,5,64])
        self.assertEqual((front['mark'],back['mark']),(1,73))

    def test_extra17_uses_active55_and_pose207_not_selected_source(self):
        yes=self.query(pose=207,active=55,side=0)
        no=self.query(pose=207,selected=55,side=0)
        self.assertEqual((actor_word(yes['actor'],4),actor_word(no['actor'],4)),(483,466))
        self.assertEqual(actor_word(self.query(pose=208,active=55,side=0)['actor'],4),466)

    def test_health_does_not_replace_native_alive_gate(self):
        result=self.query(hp=0,pending=-3)
        self.assertEqual(actor_word(result['actor'],40),64)
        dead=self.query(alive=0)
        self.assertEqual(dead['events'],[('align',)])
        self.assertEqual(actor_word(dead['actor'],20),0)

    def test_fast_fall_precedes_alive_and_rock_lookup(self):
        result=self.query(vy=50,alive=0)
        self.assertEqual([actor_word(result['actor'],o) for o in (4,6,20)],[443,226,50])
        self.assertEqual(result['events'],[('align',),('frame',)])

    def test_opposite_facing_wraps_the_relative_backoff(self):
        result=self.query(facing=-1,side=-1,x=-32768)
        self.assertEqual(actor_word(result['actor'],4),32762)

    def test_failed_lookup_keeps_old_animation_and64_source56_suppresses_sound(self):
        result=self.query(available=False,selected=56)
        self.assertEqual([actor_word(result['actor'],o) for o in (4,10,38,40)],[485,15,2,56])
        self.assertNotIn(('sound',10),result['events'])
        self.assertIn(('sound',10),self.query(available=False)['events'])
        self.assertIn(('sound',10),self.query(selected=56)['events'])

    def test_rock_can_override_the_gate_suppression_and_sheathe_sword(self):
        rock=((255,236,1,0,-2,6,1,459),)
        result=self.query(gate=61,bank=rock)
        self.assertEqual([actor_word(result['actor'],o) for o in (4,10,26,40)],[450,234,0,93])
        self.assertEqual(result['mark'],1)
        self.assertIn(('rock_edge',-1,1,1),result['events'])
        self.assertNotIn(('sound',10),result['events'])

    def test_static_rock_filter_first_live_record_and_environment(self):
        first=(102,236,1,0,-2,6,1,459)
        second=(255,236,1,0,-2,6,1,459)
        self.assertEqual(actor_word(self.query(bank=(first,second),gate=61)['actor'],40),2)
        inactive=first[:3]+(-1,)+first[4:]
        self.assertEqual(actor_word(self.query(bank=(inactive,second),gate=61)['actor'],40),93)
        result=self.query(bank=(second,),env=3)
        self.assertEqual(actor_word(result['actor'],40),64)
        self.assertFalse(any(e[0]=='rock_edge' for e in result['events']))

    def test_raw_gate_clips_rock_left_edge_before_armed_reaction(self):
        rock=((153,236,1,0,-2,6,1,459),)
        # At X380 the unclipped edge371 permits the reaction65 advance, but
        # the gate-clipped edge388 remains in front and forces disarming93.
        plain=self.query(bank=rock,x=380,side=0,raw_kind=1)
        clipped=self.query(bank=rock,x=380,side=0,raw_kind=4)
        self.assertEqual(actor_word(plain['actor'],40),65)
        self.assertEqual(actor_word(clipped['actor'],40),93)
