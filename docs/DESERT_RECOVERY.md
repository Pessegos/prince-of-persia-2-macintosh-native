# Desert Recovery

Level 2 uses the original LEVL resource and Desert.rsrc CUST/SHAP/CTBL data.
The shore's planks advance through six animation steps, two per image
(Anim/DrawDsrtPlanks, CODE:18 0808-08b4).

## Stones And Exit

`DesertState` implements the CODE:18 desert controller independently of the
window. KeepTime (CODE:2 512a-5136) triggers the loaded room's stones through
TriggerStone (18:0d90-0dd2), which chooses an inclusive Rnd(10) + 21 delay.
The 21-31 frames start on entering the stone room, not on arriving at the beach.
Once triggered, stone animations continue offscreen; delayed rises wait while
the Prince is dead or uses sequence 27 (18:0a82-0a9e).

Stones have the original 0-13 phases and standing-pose contact checks.
SinkDsrtStone (18:0cce) advances a departing stone immediately, before the normal
AnimTrobs frame. Stepping on the marked stone fails the puzzle; jumping over it
does not. SetupDesert (18:043c-0448) clears contact and failure on room entry.
Returning to the stone room schedules a fresh delayed rise for stones at phase 0.

Keeping only the marked stone raised starts the original counter and cues 46,
55 and 53, then opens the exit with song 47 (18:0050-0166). The gate takes twenty
animation steps; effect 17 waits for cue 55 to finish and stops after phase 20
(18:067c-0706). DrawDsrtExit (18:074c-0788) shifts the door and its wall symbol
three pixels **left** per phase, at unchanged heights, on background pass 11.
The foreground cliff stays fixed. RedrawStone (18:0aa8-0b36) shows the small
marked-stone symbol at phase 9 and its raised version only above that phase.

The closed entrance uses the desert barrier branch in GetBarrCode (4:532e).
The desert controller owns the outer shore boundaries rather than following
dummy room links. Restart and F2 placement reset the puzzle; disabling the
manual challenge never changes its solution or gate state.

## Manual Challenge

The original COPY:8005 resource supplies nineteen page/symbol pairs.
TEXT:8005, SHAP:8005-8014, CTBL:8000 and NFNT:24878 supply the prompt,
symbols, colors and font. CODE:02 also contains the native PlayNIS 100,
CopyProtectionDialog and symbol drawing/selection routines. The port uses
those resources and recovered layout, but implements the modal in its own
renderer. No answer is inferred from the puzzle stones.

The dialog appears only when crossing the opened cavern exit from the stone
room into level 3, not on entering the stone room. As on Macintosh, the mouse
is required; clicking a symbol selects it. The world stops while the dialog is
open. F1 can disable this challenge; it is enabled by default. Correct answers
persist until New Game.

After three wrong answers the port restarts level 2. This is a port policy,
not a claim to reproduce the original failure alert and exit path.

## Cavern Boundary

Import runs the original drawing routines for the level-3 entrance and stores
their commands in `caverns_entry.json`. Runtime uses those commands and
Caverns.rsrc directly, without executing the Macintosh program.
Only the starting room is currently supported. Animated cavern objects,
special enemies, later rooms and the complete cavern renderer remain future work.
DesertFunc (CODE:18 0334-0392) queues splash cue 56 in native room 3 at X >=
0x30B, with a Rnd(20) gate while that cue is not playing. The far-right shore
stays in view past the viewport, so the native threshold is not room-local.
Other far-shore interactions remain unrecovered.

`tests/test_desert.py` covers room-entry delays, reentry, stone phases, contact,
failure, opening cues and rendering, a solution using gameplay controls, manual
answers, modal input, the F1 toggle, exit collision and loading level 3.
