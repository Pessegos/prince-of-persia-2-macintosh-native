import struct
import unittest

from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_gate_standing import StandingCellReader
from tools.probe_temple_slide_rock_update import actor_word
from tools.probe_temple_wall_spacing import spacing_reference


class TempleWallSpacingTests(unittest.TestCase):
    def query(self, *, facing=0, distance=17, ahead=1, room=1, row=1, column=4,
              kind=0, special=0, env=2, warm=False, displacement=0, live_links=True):
        level=bytearray(0x2400)
        struct.pack_into('>h',level,0x2180,32)
        struct.pack_into('>h',level,0x2186,2)
        struct.pack_into('>h',level,0x218a,10)
        if live_links:
            for linked_room in (1,2,3):
                struct.pack_into('>4h',level,0x2080+(linked_room-1)*8,2,2,2,2)
        # The forward query uses the supplied support column. Keep the final
        # current-cell return distinct so a missing refresh cannot pass.
        for cell in range(30):struct.pack_into('>h',level,(room-1)*60+cell*2,9)
        if 0<=row<3 and 0<=column+(-1 if facing==-1 else 1)<10:
            c=column+(-1 if facing==-1 else 1)
            struct.pack_into('>h',level,(room-1)*60+(row*10+c)*2,ahead)
        reader=StandingCellReader(level,room)
        struct.pack_into('>h',level,0x2186,env)
        actor=bytearray(actor_fixture(room,row,column,facing,0))
        rem=50-distance if facing==0 else distance
        x=26+(column+4)*51+rem
        for off,value in ((4,x),(8,kind),(10,15),(28,-1),(52,special)):
            put_actor(actor,off,value)
        metadata=bytes(8)+struct.pack('>5h',1,0,displacement,0,0)
        if warm:
            reader.read(room,column,row);reader.requests.clear()
        # A later LoadFrame uses dx7 rather than the supplied metadata dx0.
        frames=struct.pack('>5h',1,0,7,0,0)*352
        result=spacing_reference(bytes(actor),metadata,reader,frames,bytes(8))
        return dict(result,reads=reader.requests,cache=reader.cache,x_before=x)

    def test_exact18_boundary_selects_51_backoff(self):
        a,b,c=(self.query(distance=d) for d in (17,18,19))
        self.assertEqual([r['adjustment'] for r in (a,b,c)],[35,-33,-32])
        self.assertEqual(actor_word(a['actor'],4),a['x_before']+35)
        self.assertEqual(actor_word(b['actor'],4),b['x_before']-33)

    def test_wall_in_front_changes_only_the_near_boundary_branch(self):
        for kind in (2,7,20,25):
            self.assertEqual(self.query(distance=17,ahead=kind)['adjustment'],-34)
        for kind in (0,1,4,9,27):
            self.assertEqual(self.query(distance=17,ahead=kind)['adjustment'],35)
        self.assertEqual(self.query(distance=18,ahead=0)['adjustment'],-33)

    def test_front_cell_is_queried_even_when_distance_already_selects_backoff(self):
        result=self.query(distance=19)
        self.assertEqual(result['reads'][0],(1,5,1))
        self.assertEqual(len(result['reads']),2)

    def test_relative_motion_and_forward_cell_follow_native_facing(self):
        result=self.query(facing=-1)
        self.assertEqual(result['adjustment'],35)
        self.assertEqual(actor_word(result['actor'],4),result['x_before']-35)
        self.assertEqual(result['reads'][0],(1,3,1))

    def test_reload_uses_original_pose_frame_then_refreshes_new_support_column(self):
        result=self.query(distance=17)
        self.assertEqual(actor_word(result['actor'],10),15)
        self.assertEqual(result['events'],[('frame',)])
        self.assertEqual(result['metadata'][12:14],struct.pack('>h',7))
        self.assertEqual(result['reads'][-1],(1,actor_word(result['actor'],12),1))
        self.assertEqual(result['returned'],result['cache'][0])

    def test_incoming_metadata_and_reloaded_pose_metadata_are_separate(self):
        result=self.query(distance=17,displacement=1)
        self.assertEqual(result['distance'],16)
        self.assertEqual(result['adjustment'],34)
        self.assertEqual(result['metadata'][12:14],struct.pack('>h',7))

    def test_special4_and_serpent_type_skip_move_but_still_refresh_current_cell(self):
        for kind,special in ((0,4),(11,0),(11,4)):
            result=self.query(kind=kind,special=special)
            self.assertTrue(result['skip'])
            self.assertEqual(result['reads'],[(1,4,1)])
            self.assertEqual(result['events'],[])
            self.assertEqual(actor_word(result['actor'],4),result['x_before'])
            self.assertEqual(result['remainder'],79)

    def test_special_exception_is_room3_environment6_not_row3(self):
        result=self.query(room=3,row=1,column=-1,env=6)
        self.assertTrue(result['skip'])
        for kwargs in (dict(room=3,row=1,column=0,env=6),dict(room=3,row=1,column=-1,env=2),
                       dict(room=1,row=3,column=-1,env=6)):
            self.assertFalse(self.query(**kwargs)['skip'])

    def test_warm_cache_preserves_order_and_observable_result(self):
        cold,warm=self.query(),self.query(warm=True)
        for key in ('actor','metadata','remainder','reads','cache','returned'):
            self.assertEqual(cold[key],warm[key])

    def test_non_temple_undefined_cell_behavior_is_an_explicit_boundary(self):
        with self.assertRaisesRegex(ValueError,'Non-temple undefined-cell'):
            self.query(room=3,column=-1,env=6,live_links=False)
