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

## Block 2: developer controls and map entries

K now visits the separate ruins actor bank, selecting native head/serpent
kill sequences154/174 and clearing the banked opponent. It stays in the
selected room; other-room actors and ordinary skeleton rules are unchanged.
Level7's map displays both actual entrance doors (native rooms32 and4),
including cache restoration and Start tooltips. Primary start remains the
same API field. User-requested rooms24/26 of level6 are hidden from the map
only; original level records and gameplay links are preserved.

Validation:61 map/cache/developer-cheat and ruins playtest tests pass17.492s.

## Block 3: ordinary ruins gates

GetBarrCode4:531c-534a classifies cavern gates as5 and ordinary ruin gates
as1 (throne barrier8 remains special). Both use CheckCollide4:5688 and the
height predicate4:5b0e, so the host's environment3-only side/step/rise tests
were incorrect. Restore ruin barrier1's narrower DATA span (column+62..72),
plus crouch/ejection under a lowering gate. CrushedByGate4:61b8-61de and
6:2ac8 stays cavern-only. Existing approved cavern run clearance stays scoped.

Validation:184 gate/terrain/throne/crush tests and2 new both-facing narrow
ruins gate regressions pass. New probe_ruins_gate_void executes4096 original
gate predicates and2 barrier classifications without predicate stubs. It also
establishes23 original room-zero down rebases for the next cliff fix; full
frame/admission/redraw/audio remain excluded from this bounded probe.
