# Desert Recovery

Level 2 uses the original LEVL resource and Desert.rsrc CUST/SHAP/CTBL data.
The shore's planks advance through six animation steps, two per image
(Anim/DrawDsrtPlanks, CODE:18 0808-08b4).

## Stones And Exit

`DesertState` implements the CODE:18 desert controller independently of the
window. Stones have the original 0-13 phases, 21-31-frame initial delays and
standing-pose contact checks. Leaving a stone sinks it; stepping on the marked
stone fails the puzzle. Jumping over it does not. Keeping only that stone raised
starts the original counter and sound sequence, sinks it and opens the exit.
The exit moves three pixels per phase (DrawDsrtExit, 18:06dc).

The closed entrance uses the desert barrier branch in GetBarrCode (4:532e).
The desert controller owns the outer shore boundaries rather than following
dummy room links. Restart and F2 placement reset the puzzle; disabling the
manual challenge never changes its solution or gate state.

## Manual Challenge

The original COPY:8005 resource supplies nineteen page/symbol pairs.
TEXT:8005, SHAP:8005-8014, CTBL:8000 and NFNT:24878 supply the prompt,
symbols, colors and font. No answer is inferred from the puzzle stones.
Mouse or arrow navigation and Enter/Space select a symbol. The world stops
while the dialog is open. F1 can disable this challenge; it is enabled by
default. Correct answers persist until New Game.

After three wrong answers the port restarts level 2. This is a port policy,
not a claim to reproduce the original failure alert and exit path.

## Cavern Boundary

Import runs the original drawing routines for the level-3 entrance and stores
their commands in `caverns_entry.json`. Runtime uses those commands and
Caverns.rsrc directly, without executing the Macintosh program.
Only the starting room is currently supported. Animated cavern objects,
special enemies, later rooms and the complete cavern renderer remain future work.
The optional far-shore event also remains unrecovered.

`tests/test_desert.py` covers stone phases, contact, failure, opening cues,
manual answers, modal input, the F1 toggle, exit collision and loading level 3.
