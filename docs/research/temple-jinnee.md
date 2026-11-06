# The Genie of Level 12

Status: 2026-11-06. Recovered from the original code. The flight itself has not
been watched in the native game.

Room 23 of level 12 holds the game's only flask of type 6, at cell 24. Its row
runs east to gate 23:28, which has no link, and plate 23:29 behind it. That plate
is the only one that reopens gate 18:19. The flask is how the plate gets pressed.

## What it does

1. The Prince takes the flask like any other (PickItUp 6:1576). SEQS 91's -14
   event 1 reaches 4:45dc, and jump table 4:4634 sends type 6 to 4:46b2: sound 12
   and JumpSeq 111. The healing, the song and the rest of the potion do not happen.
2. SEQS 111 ends in `-15 243, -14 3`, and event 3 calls TriggerJinnee 4:1d7e
   (from 4:2df0). No other sequence uses the event in the levels checked.
3. TriggerJinnee makes a new opponent in the Prince's room: actor type 12,
   opponent set 9 (`Jinnee.rsrc`), SEQS 180, song 244. X is the Prince's X plus 85
   ahead of him, by DATA -4b98. His facing is always -1 (left).
4. SEQS 180 is a cloud that opens and thins (poses 150-162, the Prince's own
   shapes 752-763 attached as AFRM pieces), and a tiny Prince, 9 by 14 pixels,
   stands in it. Then SEQS 225 loops poses 163-166 with X steps of -4, -6, -5, -6.
   Facing left, AddCharX 4:2bae makes those a run to the right, 21 pixels a loop.
5. Type 12 is the actor that gate contact skips (4:6046, 6:3190). Poses 163-166
   have the frame flag 0x40, so CheckPress 5:127e treats him like anyone on foot,
   and he is alive, so it is an ordinary press (5:240c).
6. 4:1d64 removes him at a column outside -1..10 (the main loop, 2:6668).

The name comes from the resource. What the player sees is a small copy of the
Prince running out of a cloud of smoke, under the gate and over the plate.

## Port

`pop2/jinnee.py` holds the rules. `Potions` asks for SEQS 111 and reports event
3, and `Temple.jinnee` runs one opponent frame while the Prince is in his room:
the real SEQS through `SequenceRuntime`, then the same `loose.press`,
`trapdoors.check` and `plates.press` the other actors use.

- He is drawn as the flaming sword's piece is, from FRAM and AFRM 750. Without
  `Jinnee.rsrc` nothing is drawn and the rules still run, so a reimport only adds
  the picture. `tools/extract_assets.py` now copies the file.
- `RUNNING_FLAGS` repeats FRAM 750's flags so that the plate does not depend on
  the artwork; a test and the probe check them against the resource.
- He is not saved. A game saved in the 70 frames between drinking and the plate
  has spent the flask without pressing it.

Not ported, because nothing reaches it in this room: his fall at an empty cell
(4:35ba then 4:4c1e), wall barriers, the spike calls, and the shadow-like draw in
3:0ba4 (`-5046` 10 or mode 8 only, and he has neither).

## Evidence

`tools/probe_temple_jinnee.py` runs the original bodies: TriggerJinnee (522
cases of X, facing and row), CheckPress for type 12 over poses 150-166, X, height,
action word and tile kinds 5, 6, 34, 1, 11 and 15 (13,464 cases) and the removal
over columns -4..13 (18 cases). 0 mismatches. It supplies the opponent record
and the frame flags; JumpSeq, the song, the life, the set load and the record
save are sinks that record their calls. There is no full FrameAdv, so the timing
of the first frame after the release is not proven.

`tests/test_jinnee.py` runs the real scene: the Prince drinks, the gate stays
shut and plate 169 is pressed. Before this work the flask stayed on the floor.
