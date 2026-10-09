# Level-1 Harbor And Ship

The level-1 route now reaches the ship. Native room numbers are one-based;
runtime indices are zero-based. The F2 traversal labels are:

| F2 screen | Native room | Runtime room | Entry |
| --- | --- | --- | --- |
| 7 | 12 | 11 | Last palace rooftop |
| 8 | 15 | 14 | Upper roof, followed by the drop to the street |
| 9 | 16 | 15 | Right end of the quay |
| 10 | 19 | 18 | Right end of the final quay, ship at berth |

Room 12 links down to 15; 15 links left to 16, then 19. No replacement
map, artwork or jump arc is used for this extension.

## Right Exit And Descent Recovery

CutChar 6:4c26-4c48 vetoes the rightward camera cut in native room 15,
despite its LEVL right link. The Prince can continue offscreen;
RoofMakeWaterTestRect 23:0882 starts the fatal branch at native X >818
(scene X >611). The port retains that boundary and selects original SEQS:71.
The native helper's sound waits, cinematic and staged life depletion are not
implemented; the host marks the player defeated and plays the death poses.

The drop from native room 12 into 15 has one intentional DOS-style change.
Its landing and stand-up sequences finish instead of being replaced by a
wall-bump sequence beside the upper building. Barrier position correction
still applies. This exception belongs only to that incoming fall and its
landing recovery; ordinary wall responses resume afterward. Original frame
data, damage thresholds and the five-tick movement cadence are unchanged.

## Scenery

The descent room uses CUST:4350 and SHAP:4351/4352 from Rooftops.rsrc.
Its background and foreground are full-room images, not ordinary roof tiles.
The two 32-byte image records provide the original X, bottom Y and draw pass.
Only this fixed custom-room template is supported; animated templates for
later levels are not translated.

CODE:23 DrawRoofBackWall adds 108 to the background shape index in native
rooms 15/16/19 and skips the ordinary roof fill. DrawRoofFloor selects the
dock planks and bollards instead of roof/parapet pieces. DrawRoofFloor
23:0288 puts SHAP:3614 (the far cap) in the background using PIEC:1's first
triple. Its near cap, SHAP:3613, uses the final triple in the foreground;
SHAP:3612 supplies the background planks in pass 5. DrawHalf 3:3480 requests
their foreground pass 2 for poses 135-144, clipped by ComputeHalfRect's
DATA b4ba rectangle and DrawRoofFloor's 22-pixel near strip. At an exposed
left edge, DrawFloorBuf 3:37ca-38d4 also redraws that near strip, with a
row*120+100 minimum clip top. The port keeps its SHAP alpha as separate
foreground geometry throughout descent, hold and climb, not a hold-only
mask. The tip's opaque pixels start below the walkable surface. Applying the
whole plank as foreground would hide actors' feet on the walking surface.
These are different pieces and offsets, not the same cap moved across the pier.
Overlapping near pillars
remain in front during a catch, free-air hang and climb, even when the
actor's indexed cells shift behind the ledge. Tile 47 supplies
pillar back/front pieces and four original wave sprites. DrawRoofPillar's
DATA cc32/cc3a rectangles clip the foreground/background waves respectively,
offset by the 51x120 cell origin. The source's random initial wave phases and
conditional per-actor pillar redraw are not fully translated.
The near reflection also retains its two upper sprite rows, which complete
the submerged post foot. Cropping those to the reflection strip left a
straight, severed waterline on every near post; all four phases are tested.

## Ship

- KeepTime 2:5374 triggers the ship when entering native room 19.
- TriggerRoofShip 23:1256 activates departure below counter 98; entering
  in poses 34-40 resets the counter to 6.
- AnimRoofShip 23:1066 advances the counter once per simulation frame,
  stops after 98, and moves the ship two pixels left per frame.
- DrawRoofShip 23:1120 uses original body, hatch and wake SHAPs. The hatch
  is drawn over the Prince during boarding, rather than flattened behind him.
- RoofCanGrabShip 23:12f0 requires native X <297 (scene X <90), row <3 and
  counter <33. Catch retains the ordinary velocity <60 and height [-48,+3]
  checks before reaching this special destination.
- RoofHangingFromShip 23:132c and RoofClimbingIntoShip 23:12ba move the
  gripped Prince with the ship and select SEQS:59 instead of an ordinary climb.
- GetUndefineCellId 4:28e8-28ea returns empty cells outside rooftop maps,
  not wall 20. This matters as the hanging Prince moves past the left edge:
  a false wall selected SEQS:25 and triggered water entry while still gripping
  the hull. The original SEQS:210 grip expiry is retained; releasing or
  climbing after the anchor crosses X=0 also remains valid.
- SEQS:59 retains poses 135-149, then 118/119, with the original row/X offsets.
  Opcode -16 requests a level transition; SEQS:215 then holds invisible pose 0.

The full native obstacle-bank entry used by the moving ship is not translated.
The implemented catch/controller path is covered directly rather than
replacing the ship with stationary floor tiles.

## Water

The helper at 23:06fe, called from RoofWatchOpps, checks native rooms 16/19.
It exempts sequences 68/15/59/10 and hanging mode 2. Ordinary actors enter
water at absolute Y >=327; mode-9 tumbles use Y >=354. SetupSplash 23:0b3e
centers the original six splash shapes on the actor's anchor plus/minus half
its sprite width, with the native Y offsets and the tumble's additional 27.
Sound event 35 plays the original water-entry effect.
Ordinary splashes are masked by the near pillar's original SHAP alpha,
so they cannot paint over its wood. DrawPillarInBack 23:0f96 permits a
different ordering for tumble splashes; that existing rendering is retained.

Water entry starts a counter. After more than seven frames, an actor on row
2 or below dies. Move 4:36ae-36ec caps harbor falls at Y=730 without the
ordinary immediate void death, leaving the water watcher to finish the fall.
The renderer uses the corresponding waterline clip rather than leaving
submerged bodies visible. The host retains one splash per actor, not the
original single shared splash slot.

## Verification And Boundary

tests/test_harbor.py covers the ship counter and strict catch limits, wave
clipping, dock cap/plank pixels and depth, the partial climb redraw, visible
player-foot pixels on both docks, CUST image pixels, splash expiry and all
six splash frames beside each near pillar,
water thresholds/delay, the right-exit veto/death boundary, native
generator profiles and a slain quay guard's tumble. Integrated tests use
the real input callbacks to traverse screens 7-10 and board the ship without
teleporting between rooms. They also check failure without Shift, late arrival,
the complete boarding pose chain and fixed relative position on the moving hull.
They also cover a real dock descent/hold/climb, the plank-tip pixels throughout
both transitions and the full hold cycle, and the full landing/rise pose
chain after releasing the final rooftop, with ordinary wall bumps unchanged.

Successful boarding freezes gameplay at a host level-complete screen.
Dev Mode and the New Game/Restart Level commands remain available. The
level-ending movie and level-2 loader are not implemented; green tests are
not a claim of full original-game parity.
