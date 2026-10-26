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

## Block 4: cautious cliff descent

Actual reproduction: level6/native room27, row2, X250 facing left, Down
enters SEQS68, then releases to99. Before the fix, the visible-room Y730
limit killed him at velocity57 before the threshold59 scream.

CutChar6:49ee-4a02 waits until Y>=440+body height for an unlinked down cut.
Cut6:4890/48f2 still enters native room0 and subtracts360 from actor Y even
when there is no lower neighbor. The host had omitted this continuation.
TerrainMotion now tracks it explicitly (void_fall), retaining camera-space Y
and the visible room. Its native death limit730 is therefore camera-space
1090. No subsequent walls, catches or room cuts exist in native room0.
Rooftop/water and vetoed/chasm paths keep their separate existing behavior.

The native Cut probe independently verifies23 original unlinked down rebases;
no Cut/row helper is stubbed.208 cliff/terrain/ceiling/snapshot/ruins tests
pass48.501s, including an actual descent/release and one scream/no impact.
The new snapshot field is optional for older saves and roundtrips explicitly.

## Block 5: tunnel reveal leaves a stale wall mask

Reproduction follows the supplied room18 entry: crouch then crawl left.
At pose251/X9 the old per-cell mask hid about60% of the Kid, although the
new tunnel backdrop had already erased that wall from the picture.
CavernRoom's per-cell background redraw cleared foreground alpha, row masks
and the custom mask, but omitted actor_cell_occlusion. Clear those positioned
cell masks with the same uncovered pixels. This restores the cutaway without
special actor/room exceptions, removing pillars or redrawing replacement art.

Validation:104 scenery/custom-foreground/level6/slot/gate tests pass15.769s.
The new regression rejects foreground ghost mask pixels within the revealed
passage. Entry trace now retains over99% of pose251/X9 instead of39%.
