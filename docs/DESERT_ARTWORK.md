# Desert artwork: the level 2 seam

This is an intentional port artwork improvement, not a recovered game rule.
The imported native resources are not changed. The approved pixels live in
`pop2/desert_retouch.png`, with `pop2/desert_retouch.json`. They are applied
when `DesertScene.read` builds a room's background, and only when the
background's SHA256 equals the recorded native source. Any other export keeps
its own picture. `DesertScene.read(..., retouch=False)` returns the native
drawing.

## Why

Level 2's stone chamber (native room 1, port room 0) and the start shore
(native room 2, port room 1) meet badly. The chamber's horizon, lagoon and
far hills sit about 20 pixels lower than the shore's sea, so the stitched map
and any future wide view show a step at the join.

Lifted by exactly 20 rows, the chamber's sky gradient matches the shore's row
for row. The chamber's painting appears to have been placed 20 pixels too
low. The user made the first edit by hand: columns 122-509, rows 0-165,
lifted 20 rows. The rest of the edit, approved on 2026-11-15 as review round
v17d, makes that lift seamless.

## What changes

Port room 0 has 65,127 pixels in rows 0-189. They are all background pixels:
- the floor, the stones, the foreground cliff (pass 1) and the sliding exit
  pieces (pass 11) are unchanged;
- the palm tops lose the 20 rows that move out of the frame.

The changes in that room:
- **Cliff join.** A minimum-error cut joins the lifted and unlifted pictures.
  It runs diagonally through the cliff rock, right of the carved face and the
  skull pillar, which stay in place.
- **Trunk foot.** The rock foot keeps its native position. Its edge flares
  out to meet the foot instead of leaving the old black crevice. The sand
  next to it gets a dithered shadow: it fades with distance, uses the
  painting's own shadow-sand colours and falls from the upper left.
- **Uncovered strip.** Plain sand fills the strip down to the native sand
  patch. On it lie 11 wind wisps taken from the shore's own beach, each used
  once.
- **Clean-up.** Seven black boulder dots and a few stray water pixels are
  removed. The native one-row black line at the top (the painting is drawn
  from row 1) is filled.

Port room 1 changes 107 pixels at x 0-87, rows 120-128: its grey shallows
(46,128,139) at the join become lagoon teal fading into its own sea teal.

## Checks

`tests/test_desert_retouch.py` checks:
- the sky match at the join, and that the native picture fails it;
- the changed bounds, and that the foreground and moving shapes are
  untouched;
- the removal of the grey shallows;
- the source-hash guard;
- the preview-cache fingerprint.

The level 2 development map's three room frames equal the approved review
image pixel for pixel.

The review images and the scripts for each round stay local and are not
part of the repository.
