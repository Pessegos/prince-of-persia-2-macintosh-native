# Ruins scenery and sword pickup

The reported level-six route is native rooms 18 to 17 through a crevice,
followed by the sword at room 17 cell 15. Room 18 cell 14 has floor decoration
`0x300`, the large crack below the floor. These are original resource pieces;
no replacement artwork or reimport is needed.

## Scenery filter

The live scenery renderer suppressed library 4 shapes 3581–3589 as animated
cavern torches, regardless of environment. Those numbers mean different things
in `Ruins.rsrc`. DrawRuinCrevice `7:2344–24ae` uses 3578–3581 for revealed
back pieces and 3582–3585 for revealed front pieces. The floor-decoration
helper `7:282e–295c`, called by floor drawing `7:295e`, selects shape 3587
for decoration `0x300` from the native decoration table.

Restricting the torch exclusion to cavern levels 3–5 restores the ruin
pieces in base drawings, slot variants and crevice cell redraws. The existing
exports already contain the commands. Base-room commands reference the
affected range in 46 rooms across levels 6–9 (159 drawing commands, including
multiple passes). This is a filter audit, not certification of every sprite.
All base drawing commands in the 128 ruin rooms reference shapes present in
their corresponding resource libraries; this does not prove that every
native drawing command has been exported.

The large crack specifically occurs in these native rooms:

| Level | Rooms |
| --- | --- |
| 6 | 18 |
| 7 | 10, 12, 20, 21, 24 |
| 8 | 3, 18, 22 |
| 9 | 9, 20 |

Regressions compare complete static and live drawings in the 102 item-free
ruin rooms, plus the cross-room revealed crevice. Items intentionally have
separate runtime drawing. A previous level-six scene test expected the old
wall to remain unchanged above a newly revealed opening: this inadvertently
depended on the suppressed native crevice ceiling. Its assertion now requires
that front piece to appear; whole-room versus cell-redraw lifetime is retained.

## Pickup admission and held Shift

TryPickUp `6:1350–13c0` checks the cached supporting-foot cell first, then one
cell ahead, for either tile 10 or 22. It does not search behind the Prince.
GetFCharX `4:3a72` derives the foot from FRAM offset/flags; GetCharCol
`4:3ad6` calls the original signed division at `5:48b0`. PickItUp
`6:13d0` performs the subsequent alignment and pickup animation.

`tools.probe_item_pickup` runs those original instructions with the original
level-six LEVL and original Kid FRAM bytes. It supplies working actor fields
and the FRAM offset/flags, calculates the column with the original helpers,
and intercepts only entry into PickItUp. No native admission/read-cell helper
is stubbed. Animation/effects and the complete GenCtrl dispatcher are excluded.

There are 2,200 direct admission comparisons with `pickup_target`: scene X
180–399, both facings, poses 15/50/51/52/109, room 17 row 1. All agree. For
example, facing left in standing pose 15 admits X 276–377; X 275 is outside
the native cell range. The videos do not contain identical recorded inputs;
their visual difference alone cannot establish an incorrect geometric range.

Another 3,520 native calls run StandingCtrl's `6:0c50–0c66` Shift gate with
the held flag set/clear across the four standing poses and those positions.
It tests held Shift on every call and does not consume it after an unsuccessful
TryPickUp. The port used a fresh-edge condition, so a failed eligible attempt
could suppress a later eligible attempt while the key remained held. It now
resamples held Shift, preserving the existing single attempt for a released
queued tap and all pose/airborne/combat/hard-fall exclusions. The geometric
pickup range is unchanged. The focused scene regression verifies a failed
attempt followed by entering reach with the same held Shift; it is not a
frame-for-frame replay of the user's recording.

Run locally with preserved, read-only original resources:

```powershell
python -m tools.probe_item_pickup --source PATH_TO_RECOVERY
```

The 5,720 checks cover this bounded admission/gate slice, not the complete
pickup controller, flask effects or throne vision.

## Mega-potion descent foreground (2026-10-26)

The supplied Macintosh/port fall videos show two drawing errors: the trouser
leg crosses the upper platform face during downward climbing, and the foot
crosses the cushioning shelf's face. The actor compositor only called the
already-exported QuickFloor/MarkHalf redraw for environment3. Ruins (kind4)
already contain their own native floor_redraw and climb_redraw slot commands,
but the compositor never replayed them over actors. It now admits kind4 as
well. QuickFloor2:697e-6ac4 selects the same mode/pose/cell redraws; the
exporter runs each environment's own piece drawers and clips them to the
actor rectangle. This change reuses those native commands, not an arbitrary
sprite crop or a change to fall velocity/cushioning rules.

The hidden level6 room5->6->18 Down-input regression reproduces both cases:
pose141 below the upper ledge and pose106 at shelf-contact Y+6. It checks
specific native floor pixels instead of the old visible leg/foot, then follows
the fall to room18 row1, with one life lost and survival. A local before/after
trace changes only three sampled frames in that route. Original video inputs
are not logged, so this does not establish frame-for-frame replay timing.
Artifacts and trace are ignored under `rendered/ruins-mega/`.

The sword-position screenshot shows the Prince facing away from the item.
The bounded original TryPickUp/held-Shift probe was rerun:5,720 checks agree
with the existing reach rule. It checks the supporting-foot cell and the
forward cell, not behind. Native standing-left pose15 admits X276..377;
standing-right admits X229..330 in room17. These checks describe the native
rule; the subsequent user-approved micro-QoL below deliberately softens it.

## Four-pixel sword tolerance (2026-10-26)

The second back-facing screenshot was reproduced near X272: the original
TryPickUp rejects it, while X276 succeeds. Both full held-Shift attempts were
followed in the hidden runtime. The user confirmed that this was a requested
micro-QoL, not a demand for original equivalence, and approved a small tolerance.

The runtime opts into four pixels of extra sword reach on either boundary,
in both facings. The pure `pickup_target` defaults to the strict native rule
so native probes retain that independent comparison. Only when strict
admission fails does the optional fallback try the two shifted foot positions;
it accepts only a sword, and includes that shift in the final alignment. The
lowering animation therefore reaches the usual pickup anchor instead of moving
the Prince away from the sword. Existing flask admission/alignment and native
item priority are preserved. Room17 standing-left admits X272..381 with this
exception; standing-right admits X225..334. This is a port exception, not newly
recovered Macintosh behavior.

Regressions cover all four boundaries and the next rejected pixel, alignment
to the same native anchor, unchanged flask reach and alignment, and the actual
X272 back-facing held-Shift animation through collection. The existing held
Shift retry scene now starts at X224 and retries at225, reflecting the approved
four-pixel extension of its old native boundary229. Its key-repeat behavior
remains under test. The strict native admission/gate probe still agrees in
all5,720 cases; it intentionally excludes this opt-in runtime exception.
