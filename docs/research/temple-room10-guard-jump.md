# Level 13 room 10 reinforcement timing

The supplied Macintosh recording shows the Prince climb to the right ledge,
turn left, then cross the gap in the air as the reinforcement jumps right.
The supplied port recording ends at a scythe in another room. A separate
input replay reproduces the reported stall with the actual room and guards.

The room uses LEVL 2012 (header environment 2, level 13, opponent set 7,
Birdhead). Native room 10 has a row-1, column-0 generation point, countdown
10, repeat 10, movement flags 1 and life 3. The standing right-hand guard
at scene X353 is a separate actor. Both replays begin on row 2 at scene
X188, facing right. Up and Shift climb via SEQS 16 and 10 to X189.

## Original frame trace

An offscreen original CODE trace uses the room's LEVL, Kid and Birdhead
FRAM/AFRM/SHAP and original SEQS resources. FrameAdv 2:6224 calls
CheckOppGenPts 6:3a0c at 2:6252, before the Prince's 2:625c pass. The climb
reaches row 1 at pose 141 on frame 22. Generation starts its countdown on
the following frame and the new guard presents pose 187 at native X105
(scene X-102) on frame 33, the Prince's first standing pose.

FrameAdv copies the updated Kid record to Opp for the guard pass
(2:64c8 and 4:3272). AutoCtrl 4:0606-0738 reads the current Prince pose:
poses 49–56 participate in the moving-player spacing adjustment. When the
guard is at pose 195, native X177, supporting column -2, the room's
left-linked floor still permits an ordinary spacing brake. Advancing to
pose 196 lets AutoCtrl 4:07dc/0834 select the running jump through
DoRunJump 6:1c14, reaching pose 202 at native X205.

| Input tick on the original | Prince pose at the 195 check | Guard result |
| --- | ---: | --- |
| No turn | 15 | SEQS 100, pose 202 |
| 34, immediately after the climb | 15 | SEQS 100, pose 202 |
| 38, after guard pose 191 | 49 | SEQS 101, pose 200 |
| 39, after guard pose 192 | 48 | SEQS 100, pose 202 |

The harness supplies the starting Prince placement and key latches (2:55d2),
resource lookups (4:3098, 17:330e), rectangle intersection and the harness's
random service. It bypasses the room transition (2:532c), timer, display and
audio services and the temple-specific callbacks in CODE 10. The trace ends
at the takeoff or brake.

An extended trace from the frame-34 turn starts the Prince's standing jump
with Up+Left on frame 43. On frame 50 the Prince is in pose 23 at scene X144
and the guard is in pose 209 at X170, reversing their order from the previous
frame (X151 and X130). The Prince finishes at scene X15 in pose 15 with life
3. This extension also supplies OffsetRect at 5:021c and skips redraw
marking at 5:19f8. It runs the original movement and contact checks.
With the same turn, inputs at frames 45 and 46 hit the later guard contact
window and lose one life in this setup.

## Port replay and scope

The port used the post-climb Prince for generation, so the reinforcement
was already at pose 188 on the first standing frame. An immediate standing
turn also advanced pose 45 by itself when the guard clock had just stepped.
With Left pressed after guard pose 192, this made the guard compare against
Prince pose 49 and select SEQS 101. The guard now sees pose 48 and reaches
SEQS 100. The adjacent pose-191 input still brakes.

On a native climb that changes rows, jump-capable generation points use
the Prince's state from before the climb step. The existing opponent pass
still performs generation. When a live, unarmed runner on the same room
and row has alert mode 1 (an obstruction in its path) and can jump, a
standing turn starts its animation on the scheduled world tick. Opponent
control uses the Prince's updated pose for the spacing check.

The hidden replay climbs, turns, waits for guard pose 203 and uses Up+Left.
The two actors exchange horizontal order in the air, and the Prince settles
on the left ledge at X15 with all three life points. The focused regressions
reject the old generation and turning behaviour independently.
