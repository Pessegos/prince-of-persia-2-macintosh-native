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

The three symbol variants use the same puzzle controller. SetupDesert chooses
Rnd(2) for the symbol and Rnd(4) + 1 for the marked stone (18:046a-0484).
All fifteen combinations were compared with execution of CODE:18, including
the complete opening sequence. Failure song 49 is requested on leaving the
marked stone, after SinkDsrtStone succeeds (18:02c4-02e2), not on initial contact.

CheckFloor (4:3616-3628) treats tile 30 as unsupported below phase 2.
The live stone phases must therefore feed terrain queries, not just rendering.
StartFall (4:4d94-4db2) selects SEQS:27 and death method 8 for desert falls,
calling 18:0d06 to sink both the remembered and current foot-contact stones.
SEQS:27 supplies all sinking displacements without ordinary fall gravity.
SetupSand (18:051e-0666) uses CUST 4/5 at bottom 243, centered on the actor,
and the sand surface conceals the submerged body.

The importer prepares original MIDI cues 46-50, including failure and quicksand
death songs. AnimDsrtStone (18:0a3c-0a56) starts song 50 when the last rise ends.
DesertFunc (18:01ee-0278) keeps waves until song 50 plays; subsequent background
requests require a living actor outside mode 7, no playing song or active stone,
and inclusive Rnd(30) == 0. Shores permit those requests only after the first
desert music request. Music disabled in the port suppresses this ambient song.

The closed entrance uses the desert barrier branch in GetBarrCode (4:532e).
The desert controller owns the outer shore boundaries rather than following
dummy room links. Restart and F3 placement reset the puzzle; disabling the
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

DialogFadeIn (2:0746, flags at 0774) and DialogFadeOut (2:07da, flags at 07ee)
pass 0x40001 to the palette fade routines 17:0ab6/0d0e: 4 percent per Macintosh
tick, reaching the endpoint after 25 ticks (about 0.416 seconds). The port uses
these discrete brightness steps on a 60 Hz presentation loop, freezing the
world and mouse selection during the fade. The dialog fades in once and fades
out after acceptance or final failure; changing the page after an intermediate
wrong answer does not restart a fade (CopyProtectionDialog, 2:1a36-1b84).
Level 3 loads only after the accepted dialog reaches black.

After three wrong answers the port restarts level 2. This is a port policy,
not a claim to reproduce the original failure alert and exit path.

## Cavern Boundary

Import runs the original drawing routines for all 32 level-3 rooms and stores
their commands in `caverns_entry.json`. Runtime uses those commands and
Caverns.rsrc directly, without executing the Macintosh program.
The rooms are available as scenery previews; animated cavern objects and
special enemies remain future work. See [Cavern recovery](CAVERN_RECOVERY.md).
DesertFunc (CODE:18 0334-0392) queues splash cue 56 in native room 3 at X >=
0x30B, with a Rnd(20) gate while that cue is not playing. The far-right shore
stays in view past the viewport, so the native threshold is not room-local.
Other far-shore interactions remain unrecovered.

`tests/test_desert.py` covers room-entry delays, reentry, stone phases, contact,
failure, opening cues and rendering, a solution using gameplay controls, manual
answers, modal input, the F1 toggle, exit collision and loading level 3.
