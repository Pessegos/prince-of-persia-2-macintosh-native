# Ruins overnight playtest

## Block 1: inverted potion and cut-body drawing

Room 25's inverted potion followed by a short jump reproduces a StopIteration
in cavern_scene_signature when the slab above clears the already consumed
item's floor. That ordinary floor shares the base item slot's scenery (the
pickup itself is separately drawn); select that slot rather than reject it.
A later slab impact must also override the consumed item with rubble, without
resurrecting an item after an older decoration change.

The dedicated physical Up press bypassed GenCtrl's 4:3e1c inversion while its
release used the swap. Route it through the same logical Down handling while
inverted. Physical Down already goes through the swapped ordinary path.

The scythe uses SEQS 113, Kid poses267-271, and death method5 (5:5942-597e).
Lava also uses method5, but replaces SEQS116's ordinary Prince drawing with
the pool's animation. Restrict that suppression to the lava sequence.

Validation:140 targeted potion/lava/floor/slot/crevice/ruins tests pass52.783s.
Regression reproduces actual room25 potion consumption, jump and slab fall.
No resource reimport or save-schema change. Complete overnight suite pending.

## Remaining requests

- Tunnel18 X-ray; ordinary ruins gates; cautious cliff scream.
- God-mode K heads/serpents; serpent runtime/source review.
- Ceiling shake; mega-potion shaft and cushioning slab.
- Level7 alternate start room4; room32 special collapsing floor.
- Room2 wall art preview; level6 rooms24/26 map removal (not LEVL deletion).
