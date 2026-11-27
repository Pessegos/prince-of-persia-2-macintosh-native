# Level 13 Room 32 Birdhead Deaths

The Macintosh comparison shows the first two birdheads tumbling through the
balcony at about 16 and 32 seconds. The third lies on the balcony at 43
seconds. In the port video all three bodies stay on the balcony.

The original and imported LEVL 2012 declare temple environment 2, level 13
and opponent set 7. Rebirth is room 32, tile 19. The room has no down link.
Its one generator starts with three opponents and packed life 0xff83.
Bit 0x80 permits tumbles (IsOppGenPtWithTumbleOn 6:406e–40da), including
after the generator has spent its quota. DoOppTumbleSeq 4:0154–02cc allows
a roll of 0–3 up to the registered death count, subject to the overlap,
facing and cell checks. CheckStab 6:56b2–56e8 selects either SEQS 185
(tumble) or 85 (flat death). The video comparisons come from separate
playthroughs with unknown RNG states.

## Native trace and regression

A local probe based on the original room-26 probe executed CheckStab
6:51f2 and the opponent portion of FrameAdv, 2:64de–668a, using original
LEVL, Birdhead FRAM and resident SEQS. Fixture was a one-HP, right-facing
type-2 birdhead at scene X140, absolute Y226, row 1, pose 158, with a
left-facing attacker. The probe supplied Rnd results, the active-bank
records and registration at ALIVE=0 after the fatal hit. It recorded
AddSound and skipped opponent control, sword geometry, edge geometry and
Sound Manager playback. It used the inherited resident handle and
Memory Manager trap stubs. It excluded the outer frame scheduler,
opponent storage after 2:668a and rendering.

With zero registered deaths, roll 0 selected 185 and roll 1 selected 85.
With one death the boundary was 1/2, and with two it was 2/3. The mode-9
fall came past the balcony in pose 215 at Y250, held pose 218 and row 4
after Y490, and stopped at Y730 in pose 185. The hit requested 31 and
the tumble requested 30. No impact sound was requested at Y730.

Before the fix, the port chose SEQS 185 under the same roll and hit state,
then landed in pose 185 at Y226 on the next guard update and requested
cue 7. The room-32 regression uses the real generator and contact
resolver in a hidden scene, with a supplied roll and fight positions.
It compares the fall through repose at Y730, the room, the registered
death and the sound queue. The linked-down variant stores far offscreen
depth in the Y offset. The rooftop limits and harbor handling retain
their existing behavior.

SetupOpponent 3:0942–0990 marks tumble objects for the front pass. Its
3:0f46–0f6a branch skips ordinary front-cell marks, and ClipChar
4:4210–4224 retains the temple viewport clip. The previous port layer
could hide the body behind the decorative stone even with the fall
trajectory corrected. The scene regression compares the rendered
birdhead pixels below the balcony against the opaque sprite pixels.
A checkpoint restart check with supplied rolls 0, 1 and 3 renders two
tumbles and one flat death, and reads back a temporary save after all three.

## God mode K and the room 2 to 28 cut

The clip crosses 32 → 2 → 28. The port passed K through CheckStab's sword-hit
logic. In a replay with the room 2 initial birdhead followed by its left
reinforcement, both started SEQS 185. The reinforcement was at X−45 when
killed and appeared at X383, Y369 on the room 28 cut. With the direct
SEQS 85 selection it stays at floor Y226 through the cut.

The native CheckCheatKeys slot loop loads each opponent at 2:4c12–4c1a.
An isolated execution of 2:4c1c–4cb0 used LEVL 2012 and supplied type-2
records in room 2 at Y226. A living guard at native X407 with 3 HP and one
at X162 with 2 HP both set ALIVE to 0, queued their respective life loss
and requested JumpSeq(85). An already dead record requested no sequence.
The output anchors were (407, 226) and (162, 226). JumpSeq 6:0006 and the
slot write at 4:4a46 were recorded and stubbed. The probe excluded input,
the surrounding loop, AnimChar, the room cut and audio. The regression uses
the port's K input, room 2 generator and running jump into room 28.
