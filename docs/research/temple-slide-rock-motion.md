# Temple Sliding-Rock Motion

Status: bounded native/reference evidence, not production gameplay. This extends
[activation](temple-slide-rock-trigger.md) with the complete motion body, while
deliberately supplying geometry/audio/actor endpoints. It does NOT yet connect
real geometry to the full update dispatcher, rendering or saves.

## Original Addresses

All addresses below are CODE resource offsets, including the four-byte resource
header, not the `segment_offset` column of the recovery jump-table CSV.

| Body | Address | Execution Here |
| --- | --- | --- |
| MakeRubble mob iterator | 5:29e8 | Static dispatch tracing only in this block |
| Type dispatcher | 5:2a94, type6 case5:2afa | Calls motion then crush, in that order |
| Motion | 10:1d5c-1fa6 | Full body executes |
| Filled-band predicate | 10:1656 | Supplied independent booleans; X logged |
| ReadCell | 4:27ee | Supplied tile responses; requested room/column/row logged |
| IsWall | 3:4ef2-4f24 | Native, including original wall-kind constants |
| Signed division | 19:4bb0/4bd0/4bfe | Native; truncates toward zero |
| Prince to working-actor copy | 4:4b02-4b14 | Native full62-byte copy |
| Actor reactions | 5:3cee,6:1a84 | Admission recorded; supplied marker changes only |
| CheckSlideRockCrush | 10:16f6 | NOT executed; separate next step |
| ATMLoose/type6 presentation | 5:307c/3116,10:1456 | NOT executed |

The motion jump is A5+0e1a ->10:1d5c. The next type6 case call is
A5+0df2 ->10:16f6. A direct motion-helper probe must not be described as a
complete MakeRubble/type6 controller probe. Rendering is a different driver.

## Record And Control Rules

The eight signed words remain `(X,Y,room,mark,control,type,row,originalX)`.
These names describe observed storage, not a final runtime API. In particular,
`mark` is NOT a pure deleted boolean: exact-1 excludes lookup/marks eventual
compaction, while value1 is also a temporary movement phase.

- Control0 and100 return immediately with no services or record changes.
- Control-2 skips the band predicate and proposes `X-2` without changing control.
- Every other nonzero/non100 control tests the bands at the original X. If true and
  control>=8, set control0, request StopSound192, and clear pending cue A5-439e
  only if it equals192. No second test, tile read or candidate-X write follows.
- Otherwise test the bands again at a temporary `X-16`, request cue191 if true,
  restore the original scratch X, and propose `X-2`. Increment control by one
  when its old signed value<=8; values above8 remain unchanged. The control is
  not the X displacement. Reaching zero from-1 exits before committing X.
- If candidate X<0, read the real left-room link and add510 to the candidate.
  No originalX adjustment occurs in this body. If that room is0, mark-1 and
  request StopSound192; scratch X stays at its pre-candidate value. The pending
  cue is not explicitly cleared by this path.
- This body has no initial `mark==-1` return. Supplied removed records still
  take the motion path unless control is0/100. This does not establish that a
  live game necessarily reaches such an input.

All displacement units above are native coordinates **per helper call**, not
port pixels, elapsed milliseconds or certified game-frame cadence.

Terminology correction after [native geometry validation](temple-slide-rock-geometry.md):
the predicate does NOT mean empty/clear space. It returns true when both scanned
bands contain neither IsSpace kinds nor marker25, including vacuous empty
intervals. The initial provisional `clear` response/event name in this probe has
been renamed `filled` to avoid implying the opposite result. Motion transitions
are unchanged; the output digest below reflects the renamed endpoint events.

## Obstacle Phase

For a still-active, nonzero room, read the tile at the stored row and column
`trunc(signedWord(candidateX-31)/51) - (signedWord(candidateX-31)<=0)`.
The explicit nonpositive adjustment is present even when the numerator is0.

If mark is1, clear mark, set control100, increment Y and set X to candidate+3.
If that first tile is2, invoke actor endpoint5:3cee after copying the Prince to
the working actor, then copy all62 working bytes back to the Prince. Request
StopSound192. This path skips the later frame/position actor admission.

Otherwise compute old/new columns as `trunc((X-6)/51)` and
`trunc((candidateX-6)/51)`. If the columns differ, or the first requested column
differs from the old one, read another tile at the new column/stored row.
When mark is0 and that second tile is a native wall (20,2,7,25,43), tile4,
or the first tile is2, set mark1 and decrement Y. Query cue193; request cue18
only when it is not playing and the first tile is not2. Other mark values do
not start this phase. The next active call finalizes a mark1 record as above;
Y is restored, not accumulated indefinitely.

The non-mark1 path also tests the stored Prince frame unsigned in87..99
inclusive, Prince row==rock row+1, and Prince column==trunc((candidateX-12)/51).
On a match it copies the Prince, invokes6:1a84, and copies the result back.
There is no Prince-room equality test in this local admission body; do not
infer a complete collision rule from it or silently add a local room gate.
The later10:16f6 crush body has not been included in this block.

Finally, nonterminal control writes candidate X and requests cue192 if control
is nonzero. Control100 requests StopSound192 instead. The mark1 terminal path
preserves its earlier candidate+3 correction. Signed Y operations wrap as native
words. The actual audio queue/replay/interrupt policy is outside this probe.

## Executable Evidence

```powershell
python -m tools.probe_temple_slide_rock_motion --source PATH_TO_RECOVERY --output rendered/temple-slide-rock-motion.json
python -m unittest -q tests.test_temple_slide_rock_motion_reference
```

Original executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.

3,190 comparisons, zero differences:

| Supplied Controls | Cases |
| --- | --- |
|14 control values,12 X boundaries,3 mark values,4 band-response pairs|2016|
|Front/edge tile responses,4 mark values,audio query outcomes,X thresholds|864|
|Pending-cue clearing and stop thresholds|32|
|Actor frame/row/column admission boundaries|108|
|Signed Y limits|8|
|All12 actual tile25 anchors,4 controls and3 X positions|144|
|Explicit absent/present left-link controls|18|

All11 declared native branch checkpoints were reached: unconditional-2,
filled-band stop, second-band test, matching-pending-cue clear, room crossing,
missing-room removal, begin/finalize marker, both actor endpoints, terminal
sound stop. This is targeted branch evidence, not exhaustive path coverage.
The report records endpoint totals and four original level hashes.
Outputs SHA256:
`5827bb09d0607168328592b8310e7791a2e8e6d6520872c6e7b1eaa4115985e5`.

Each case compares the record, ordered endpoint requests/arguments, pending
cue, entire level, unrelated512-byte bank guards, and both62-byte actors.
Actor endpoints record their incoming working actor and change only its first
and last words to distinctive markers. The original copy-in/copy-back must
preserve the other58 bytes. These markers do not model damage, death or a
particular animation. Source level resources are read-only; the two explicit
left-link controls modify in-memory copies only. Unit tests use synthetic data.

## Boundaries And Next Work

- The supplied geometry in THIS probe is now independently validated by the
  [geometry probe](temple-slide-rock-geometry.md) and composed with native motion/
  crush admission/bank updates by the [connected probe](temple-slide-rock-update.md).
- ReadCell responses here do not update the original cell cache. Consequently
  this block does not certify the cache-dependent effects of5:3cee.
- Actor reactions and crush do not execute in THIS probe. Follow-ups cover
  [admission](temple-slide-rock-update.md) and [native contact consequences](temple-slide-rock-contact.md),
  including first-frame animation, but not complete actor/death progression.
- The connected probe covers bounded live-bank lifecycle/persistence, not
  presentation, actual actor consequences, file-save or restart persistence.
- ATMSlideRock rendering, controller admission, FrameAdv ordering/cadence,
  save/restart persistence and complete temple progression remain open.

Nothing here changes the production port, imports resources into it, or claims
that levels10-13 are playable. A later implementation must apply the port's
coordinate/collision contracts deliberately, not paste this reference into it.
