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

## Initial backlog after block1 (resolved below)

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

## Block 6: serpent alert boundaries

CODE2:6f76-6f98 adjusts a hanging Prince's supporting column by the native
facing table (left +1, right -1). CODE2:70c4 stops the LOS scan at its first
non-clear result; continuing could overwrite a cautious gap alert with a later
wall. PrinceView now carries the cached animation mode and both rules apply.
The bounded original alert slice agrees on5000 deterministic cases across
levels6-9, respecting the original LEVL room-count header. Working actor and
A6 locals are supplied; no LOS/classification/tile helper is stubbed. Full
FrameAdv, actor loading and pose admission remain outside this comparison.
Two regressions cover the gap-before-wall and both hanging facings.

Full-suite follow-up: the existing bridge tension test's ordinary unlinked
room9 fixture assumed camera Y730 was native void Y730. Updated its initial
camera Y by360, preserving its death/tension assertions. The bridge chasm
(vetoed down cut) fixture stays unchanged. Extended the independent native
Cut probe to actual level5 room9:46 original rebases now pass in both
caverns and ruins.56 focused ruins/bridge/void tests pass12.883s. The earlier
2951-test full run had this one fixture failure and10 explicit skips; a new
full run is required after the remaining shared changes.

## Block 7: ruins collapsing shelves and mega-potion shaft

Native Falling6:0236-0260 halves vertical speed and sets Y from DATA
row-bottom125+120*row minus13, not SetCharFloor106+120*row minus13.
The port's position was19px too high, adding a fatal extra falling frame.
The original arithmetic agrees for189 supplied row/velocity cases. A real
cautious Down/release from level6 room5 X340 now breaks the preserved room6
cell25 slab and lands in room18 row1 alive with one HP lost. Running blindly
into the shaft can still be fatal; damage thresholds were not relaxed.

Room32 level7 cell22 is type15, omitted from the previous type11-only host.
CheckPress5:1330/13d2, ShakeEm5:28c2, Falling6:0204 and MakeRubble5:2bc4
invoke7:36a0: immediate MakeSpace plus a type3 MOB, no warning controller or
cue28. The native room32 shelf call matches cell removal and all eight MOB
words; only object drawing/redraw services are supplied. Added this family
to pressure, ceiling pose79, shake, Prince/debris contact and dynamic export.
Normal type11 ceiling contact already works, including the room25 potion
regression; special15 was the missing ceiling family found in this audit.

AnimLoose5:446a also distinguishes environment4 MOB3's initial bottom
125+120*row from the cavern MOB0 bottom143+120*row. ComputeMobRect5:32f6
uses91x31 versus87x43. Preserve that type through split debris and snapshots;
older snapshots default to the original MOB0 field. Per-slot scenery export
version17 includes type15 removal and downstream impact surfaces; ruins
exports6-9 were regenerated locally. Original resources remain read-only.
The installation check requests updated ruins exports, while earlier compatible
cavern exports remain accepted. Native draw/raster parity and full MOB/frame
scheduling are outside the small native shelf/position probe.

Validation:169 focused loose-floor, actual level6/7 scenes, ceiling, slot,
shaft and save tests pass28.958s;77 pure installation/floor/helper tests pass.
The old room17 crevice test now asserts every crevice digit and every other
unchanged digit rather than assuming the export has only three dynamic cells.
The serpent controller independently matches20000 cases in addition to the
5000 alert slice checks. Full shared-desktop discovery follows this block.

## Room2 artwork and final scope

The level6/native room2 screenshot combines the repeated dark ruin sky
(SHAP3506/3507) with a remaining right-hand strip of the landscape behind
it. Prepared a local-only comparison extending the same native sky repeat
under that strip, preserving the original foreground wall, character and HUD.
This is a subjective proposal, not an integrated artwork change. Evidence:
`rendered/ruins-night/room2-wall-proposal.png` and `.gif`. Existing approved
cavern art is unchanged. No original resource is edited or published.

An additional original drawing check covers17 rooms and51 rest/removed
combinations for type15 floors: stored slot composition matches whole-room
original command lists, including floor/climb redraws, with zero differences.
The importer/decoder is shared with the existing native drawing harness;
this establishes command equality, not independent QuickDraw raster equality.
Base room commands, entrance/exit frames, pressure plates and other sections
of all four regenerated exports are identical to the earlier version16 files;
only version and loose-floor metadata changed.

A hidden scene smoke run exercises the15 serpent-bearing rooms across
levels6-9 for180 frames each. It exposes no runtime exception, but some
serpents continue offscreen in these artificial invulnerable/warped fixtures.
This is not evidence that the complete serpent runtime is correct or that
an offscreen trajectory itself differs from the original. CheckCollide4:569e
explicitly exempts serpents from barriers. Keep full serpent scheduling,
room transitions and retreat behavior as an open parity audit rather than
adding speculative wall clamps. The two independently demonstrated alert
errors are corrected; the user's broad serpent concern is not closed in full.

Full discovery2962 tests555.665s reached all gameplay checks without a
failure; two strict fresh-import comparisons failed solely because unchanged
cavern exports3/4 had been labelled17. Scope the new export version17 to
ruins/environment4; cavern exports retain16 and their byte-equivalent data.
The strict import equality assertions remain intact. A new full run follows
the one-line importer correction, with10 explicit desktop skips expected.
