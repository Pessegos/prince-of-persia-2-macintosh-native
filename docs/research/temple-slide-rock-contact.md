# Temple Sliding-Rock Contact Consequences

Research/reference only. This replaces the supplied10:1b04 reaction used by the
[connected update probe](temple-slide-rock-update.md) with its native body,
native health/death-method primitives, JumpSeq and the complete first AnimChar
call made by that body. It is not a complete game-frame or death-lifecycle test.

## Executed Original Bodies

| Body | CODE Resource Offsets |
| --- | --- |
|Contact reaction|10:1b04-1ca2|
|Contact admission and Prince copyback|10:16f6-176e,4:4b02-4b14|
|Character column / mixed-width arithmetic|4:3ad6-3aea ->5:48b0-48dc|
|SetKidDeathMethod|4:3196-31e2; method13 invocation here|
|Align actor Y|4:31fa-3228|
|DecLifePts|4:34f2-3596; amount==current-life invocation here|
|JumpSeq|6:0006-0098; actor1 conversion excluded|
|AnimChar and GetSeqOp|4:2c0c-3050,4:305e-308a|
|Facing-relative AddCharX|4:2bae-2bcc|
|ReadCell/normalization/cache and IsWall|Native paths from the geometry/update probes|

Offsets include the CODE resource header. Native SEQS47/48/71/93 data are read
from the preserved Prince.rsrc fork into prepared, nonmoving handles. No asset
payload is committed. The unit tests use DIFFERENT synthetic clips/poses.

## Actor Fields

All offsets in this table are **bytes** into the62-byte working actor at
A5-5056. The Prince buffer is A5-50d2 and uses the same layout.

| Hex Offset | Field Used Here |
| --- | --- |
|02/04/06|Facing / X / Y|
|08/0a/10|Actor kind / pose / action|
|0e/14/16|Row / vertical-motion word / room|
|1a/1c/1e/22|Armed / alive / current life / pending life delta|
|24/26/28/34|Sequence cursor / current ID / selected ID / sequence mode|

Other checked state: correction word A5-3570, character-column remainder
A5-481c, Kid death method A5-500e and all six cell-cache words. The correction
word is supplied; deriving it from frame/shape data is not validated here.

## Native Reaction Rules

- Action5 returns before X adjustment, geometry, health or sequence requests.
- If signed actorX-229 > signed rockX, set X to rockX+223; subtract the
  correction only for facing exactly-1. This differs from the admission gate's
  **any nonzero facing** correction rule.
- Query the first tile using actor room/row and GetCharCol of X-12, additionally
  subtracting the correction for facing0. This is not simply rockX/51.
- A native wall or tile4 snaps X using DATA table A5-4b86:
  `258+51*column+12`, plus correction+6 only for facing0. The table formula is
  checked over the bounded lookup columns-2..12.
- If that first tile is2, return after the snap: no terminal kill, sequence or
  common Y/velocity reset. Tile2 is deliberately different from other walls.
- For another solid first tile and control100: if alive<0, call DecLifePts with
  the entire current-life word and set alive0. Pending delta becomes at most
  negative current-life, preserving an already larger pending loss. Set pose185
  even when alive was already nonnegative. This path does not JumpSeq/AnimChar,
  change the current-life word, or itself set the death-method global.
- For another solid first tile and nonterminal control: query a second tile at
  `trunc(signedWord(rockX-18)/51)` in the actor's room/row. If that tile is a wall
  or4 AND the signed remainder is<46, request cue193 when alive<0 and call
  SetKidDeathMethod13. In this corpus it writes the Kid global only for actor0;
  the supplied nonplayer actor kinds do not write it. Then set sequence mode4
  and choose SEQS71 whether or not that second-tile/remainder condition passed.
- For a nonsolid first tile and alive<0: armed exactly1 selects93 and clears
  armed. Otherwise facing0 selects47, any other facing48. Armed values other
  than1 are not cleared by this branch.
- For a nonsolid first tile and nonnegative alive: subtract12 from X, without a
  sequence request or common Y/velocity reset.

For a selected sequence, align Y to120*row+106 (minus33 for supplied kinds7/8),
clear the vertical-motion word, call native JumpSeq and then native AnimChar once.
With the original resources present, JumpSeq writes current/selected IDs and
cursor0. AnimChar executes to the first pose:47/48 produce pose50/action5,
71 produces pose179/action1,93 produces pose234/action1. Facing-relative X shifts
and the final cursor are compared, not supplied. Opcode-19 in71 aligns Y again;
it is not an immediate kill opcode. Alignment is formula-based, not cumulative.

The26 character-column controls also preserve the original mixed-width order:
sign-extend the coordinate, subtract four from ONLY the low word, then DIVS.
At coordinates0..3 this is not ordinary signed subtraction. These arithmetic
controls do not feed their resulting large columns into room traversal.

## Connected Contact Traces

Eight traces run six consecutive original MakeRubble calls each, using a single
type6 rock in a canary-guarded bank, prepared floor/solid rooms, both facings and
armed0/1. Geometry/cache, motion, admission, contact, first sequence step and
native bank writeback all execute together. No working-actor marker replaces
contact, and no Python-produced actor/record is injected between native calls.

In the four solid-room traces, the first update leaves alive-1, pose179,
sequence mode4 and the supplied initial pending delta-1; death method becomes13. The next update
finalizes the rock to control100 and writes alive0, pose185 and pending delta-3,
without changing current life3 or reselecting the clip. Later tested updates
preserve those values. The free-room traces instead exercise push/disarm clips.

**Ordering is supplied:** ordinary Prince animation/controller updates are NOT
inserted between these MakeRubble calls. A real FrameAdv can advance71 into its
linked clip or apply pending health between them. Therefore this is evidence of
the specified connected mechanism, not the elapsed death timeline of live play.

## Evidence And Boundaries

```powershell
python -m tools.probe_temple_slide_rock_contact --source PATH_TO_RECOVERY --output rendered/temple-slide-rock-contact.json
python -m unittest -q tests.test_temple_slide_rock_contact_reference
```

8,322 comparisons pass:

| Corpus | Cases |
| --- | --- |
|Character-column signed/mixed-width boundaries|26|
|Controlled first/second tiles,controls,facings,alive,armed,actor kinds|6144|
|Remainder45/46/50/0 and pending-health boundaries|216|
|Position/correction/action5 boundaries|144|
|Supplied missing-sequence-manager controls|8|
|All12 original markers with supplied actor/contact states|1728|
|Native contact gate/copyback with actual reaction and first animation|8|
|Eight connected six-update traces|48|

All13 declared reaction branch checkpoints are reached. Sequence requests are
47:294,48:283,71:2908,93:468. Branch count for SetKidDeathMethod is a call count,
not a claim that its global changed for nonplayer kinds.

Comparisons include the entire working/Prince actor buffers, incoming contact
actors, rock/bank/count/canaries, ordered geometry/sequence/audio/handle requests,
cache/remainder/death method, entire unchanged level and read-only prepared
SEQS bytes/handles. The native body is not reduced to checking its return value.
16 asset-free tests cover the reference, including synthetic first-frame clips.

Supplied native boundaries are only GetResource(SEQS)17:330e and hGetSequence
4:3098 to prepared original handles; HGetState/HLock/HSetState with zero state/
errors and nonmoving memory; audio requests without playback, with cue193 query
false if motion asks. Handle-trap opcodes at the three supplied sites are checked.
Eight missing-resource cases deliberately supply no available sequence handles;
they are not an assertion that the original files lack these clips.

Actor1's JumpSeq conversion, other movement reactions5:3cee/6:1a84, unvisited
VM opcodes/clips, general health-library behavior, life-delta application, later
death/animation progression, real sound/resource management, rendering and
file-save/restart are excluded. Movement calls to the other reaction bodies
fail closed in this probe rather than silently using the earlier tagged stubs.
Kinds4/7/8 are counterfactual leaf inputs, not new head/enemy-AI coverage.

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Outputs SHA256:
`8d69ed5a1def3f43e078fb4bfd5130dda481f89816fa62fad66e1fbf7a4bc245`.
The ignored report records Prince.rsrc, level and individual sequence hashes.

[Presentation/restoration](temple-slide-rock-presentation.md) is now recovered
in a separate native queue-building probe, not interleaved into these contact
traces. Next work connects the stages, then follows native persistence/reset/save
paths and the remaining trap-door caller/admission/scheduling/collision audit.
Production code, imports/assets, campaign and README remain untouched.
