# Level 13 Room 2 Inscription and Guards

The Macintosh clip plays Chasm as the Prince enters from room 32. Its
resident birdhead draws on the right-hand approach. After the resident,
reinforcements come from the left first. The port clip has the resident
waiting until the Prince closes the distance and shows a reinforcement
from the right before the resident is killed.

## Chasm

Temple CUST 4025 (Inscription), kind 31, points through DATA a5-0x4c2e to
the entry hook at jump-table offset 0xe6a, CODE 10:27a6. LoadCustomRoomData
3:13ec–13f8 calls it when entering the room. It requests AddSong(292) when
the saved Prince foot column a5-0x50c6 is at least 9. There is no leave
handler. LEVL 2012 is the temple level with custom room 2. The port queues
Chasm once at a qualifying room cut and respects its Music toggle. The
existing imported Chasm.mmf is shared with the level-nine crossing. A
spectral comparison finds Chasm near 2.3 s in the supplied Macintosh clip.

## Guard draw after a footstep

AutoCtrl 6:4faa–4ff4 can clear movement noise if the last active slot
runs unarmed control. FrameAdv 2:6740–6742 also clears a5-0x4f9e after
the entire opponent pass, even when the last slot is a corpse. The port
had only the first clear. In a hidden replay from room 32, a corpse at X65
was imported behind the resident. The Prince crossed in pose 8 and made
noise during pose 9. With the stale noise, the resident facing the Prince
stayed in pose 166 through the rest of the run. The fixed pass leaves the
one-frame pose-9 delay and the resident draws on the next frame (pose 158).

## Reinforcement order

GetOppGenPtOnRow 6:3d28–3df4 picks the first point with remaining quota,
the right floor, and more than two columns between the Prince's supporting
foot and the point. CheckOppGenPts 6:3a2a–3a68 then checks that point's
corridor and countdown. A blocked point does not give its turn to the next
point. LEVL 2012, room 2 contains one resident (X200, three HP) plus two
left reinforcements at X−102, countdown 8, and up to five right ones at
X561, countdown 22. Reinforcements have two HP. This order depends on the
Prince's position. At column 2 the left point is out of range and the
right point can act while the left still has quota. The right-side
spacing check at 6:3f72–3f80 also admits a single intervening guard on
the inside of the spawn column. The port had the inequality reversed.

## Verification

A local original-code probe used LEVL 2012 (environment 2, level 13,
opponent set 7), CUST 4025 and its relocated entry pointer. It executed
10:27a6–27b8 with seven supplied columns around the 8/9 boundary,
2:66dc–6746 with zero through four bank records and live/dead entries,
and CheckOppGenPts with real GetOppGenPtOnRow, IsActiveOppGenPt,
IsTimeToGenOpp and wall queries. It supplied actor records, row, foot
column, frame counter and the matching room-state words. AddSong and
GenerateOpponent were recorded endpoints. After each supplied generation
the next call saw an occupied registered-dead slot. With the Prince at
X350/column 6 and the resident alive, both timers hold. Once the resident
is registered dead, arrivals are left, left, right on eligible ticks 9,
18 and 41. When the Prince starts at column 2, the right point fires at
tick 23 with left quota intact. Another 300 original/port fixtures
compared the chosen countdown across ten foot columns, 15 blocker X
positions and both registered life states, with matching results.

The hidden-scene regressions use actual cuts into room 2 from both sides,
real playback initialization with a dummy device, a transferred corpse and
the port's real generator tables. The probe does not execute Macintosh
sound synthesis, the full frame loop, generation constructors or a full
duel. The port's existing offscreen-capacity safeguards and generation
corridor model remain in place.
