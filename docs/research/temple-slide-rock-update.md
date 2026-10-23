# Temple Sliding-Rock Connected Updates

Status: bounded native/reference evidence. This connects real geometry and
motion to **crush admission**, bank writeback/compaction and repeated activation.
Admission is NOT damage: actor reaction bodies, animation, presentation and
file-save/restart behavior are excluded from THIS probe. The subsequent
[contact-consequence probe](temple-slide-rock-contact.md) now executes10:1b04
and its actual first animation call separately. No production port code changed.

## Executed Native Path

```text
TriggerSlideRock10:2152 -> lookup10:1a9e -> optional constructor/append5:2914
MakeRubble5:29e8 -> type dispatcher5:2a94 -> type6 case5:2afa
    motion10:1d5c -> band predicate10:1656/scan10:1ca4 -> real ReadCell
    crush admission10:16f6 -> optional reaction10:1b04 [SUPPLIED]
    scratch writeback -> optional removed-record compaction
```

The earlier [motion](temple-slide-rock-motion.md) and
[geometry](temple-slide-rock-geometry.md) references are composed through
independent geometry callbacks, not through Python-produced native responses.
Native cell normalization, six-word cache, signed division, IsSpace, IsWall,
record selection, constructor, bank loading and both62-byte actor copies run.
No ReadCell or band-predicate endpoint is supplied in this new probe.

All addresses are CODE resource offsets, including the four-byte header.

## Crush Admission

Original10:16f6-176e compares rock room with Prince word+22 and rock stored row
with Prince word+14. Both must match, including in the special mode below.
Prince offsets in this note are byte offsets into the62-byte actor record,
not word-array indices.

The tested Prince front is word+4. For **any nonzero** facing word+2, add the
supplied signed word at A5-3570, wrapping as a native word. This parameter is
called `width` in the probe; its full frame-derived construction is not tested.

Let `lower=signedWord(rockX+223)`. Ordinary admission requires strictly:

```text
lower < signedPrinceFront < signedLong(lower)+25
```

Both endpoints reject. The lower/front calculations wrap as words; the final
upper addition is long arithmetic and must not wrap at32767. The corpus includes
rockX32540 to distinguish those cases.

If Prince word+52 (A5-509e, sequence-mode field+34hex) equals4, skip the proximity
test, but NOT room/row matching. This is **not actor-kind4** at word+8. Mode and
actor kind must not be interchanged when implementing the eventual port rule.

This local gate does not filter control0/100, mark-1 or room0. Counterfactual
room0/mark/state controls demonstrate that narrow fact; they are not proof that
all those states occur in a live game. Motion runs before this gate even when
motion itself returns immediately. Contact can call reaction10:1b04, whose own
conditions and consequences are not certified here. Do not replace the endpoint
with unconditional damage/death based on this admission result alone.

## Connected Experiment

24 traces cover all12 actual tile25 markers, each with a fixed-view and a
changed-view profile. Each starts with an empty canary-guarded bank and executes
160 native MakeRubble calls, for3840 updates total. The supplied trigger schedule
is how1 at cycle0, how2 at8, how1 again at64, and how2 again at72:96 native trigger
calls total. This is a controlled schedule, not recovered FrameAdv/input timing.

No fixture reset or Python-record injection occurs between these native calls.
The reference bank is a comparison output only. Trigger construction legitimately
updates the real cell cache; existing-record activation must leave it alone.
The view-change profile supplies A5-4fc2 at cycles40/80/120 as4/13/another room.
This changes the selector used by undefined-cell rules without clearing the
bank. It does NOT execute a complete room cut or update every view-neighbor
global, so it is not a whole-room-transition parity test.

After160 supplied updates, each view profile has:

- Eight records at control100, retained in the bank.
- Three records at control0, also retained.
- One empty bank: level12 room10/cell0 constructs at X0, crosses the absent
  left link, marks removal and is compacted out. A later activation can create
  it again; this is not persistence of an invisible deleted record.

The probe compares full bank/tail bytes after every operation. Compaction keeps
survivor order and does not clear the unused old tail; those bytes are modeled
and compared rather than incorrectly requiring zero fill. Mixed-bank controls
use counts0/1/3/30 with native type1 no-op entries and type6 rocks. Other mob-type
interactions remain outside the corpus. The native iterator's current index
must reach the original supplied count, including when compaction reduces count.

These traces prove live bank state survives the specified trigger/update/view
selector operations. They do NOT prove file-save serialization, checkpoint
restoration, level restart, rendering or full actor interaction persistence.

## Supplied Endpoints

| Endpoint | Supplied Behavior / Exclusion |
| --- | --- |
|5:5252 StopSound|Record request; no queue/channel side effects|
|5:4d84 AddSound|Record request; no actual playback|
|5:52c8 PrinceSndOn|Cue193 always false in this connected corpus|
|5:3cee|Record actor admission, change first/last working words to30001/30002|
|6:1a84|Same, with30003/30004|
|10:1b04|Same, with30005/30006; NOT the native reaction body|

The original copy-in and copy-back must preserve all other58 actor bytes.
An explicit control triggers5:3cee and then10:1b04 in the same update: the second
endpoint must receive the Prince already updated by the first. Two more controls
reach6:1a84 at frame/row/column admission, including a different Prince room;
the later crush gate still applies its separate room/row requirements.

## Verification

```powershell
python -m tools.probe_temple_slide_rock_update --source PATH_TO_RECOVERY --output rendered/temple-slide-rock-update.json
python -m unittest -q tests.test_temple_slide_rock_update_reference tests.test_native_rules_call_guard
```

13,708 comparisons pass:

| Corpus | Count |
| --- | --- |
|Crush bounds/signs/facing/correction/mode/room/row controls|6912|
|Crush gate ignores control/mark and permits matching room0|18|
|All three actor endpoints and successive actor-copy order|3|
|Complete type6 updates at actual anchor/boundary positions|2835|
|Mixed type1/type6 bank iteration/compaction/capacity controls|4|
|Connected native triggers|96|
|Connected native bank updates|3840|

Each comparison checks record/scratch, ordered motion/crush entry snapshots,
actor-endpoint inputs, ordered service and cell-read requests, complete cache,
pending cue, both actor buffers, full bank/canaries/count and entire level.
The original level bytes remain unchanged throughout these operations.
The native actor endpoint totals are3303 for10:1b04, one for5:3cee, two for6:1a84.
The ignored report contains24 trace snapshots and four original level hashes.

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Outputs SHA256:
`7946fb6cd7334eeb47ecf175e376afe7cf148439a00c160b5a964ab8c948a27e`.

The shared research-only NativeRules harness now clears `reached`/`failure` for
EACH invocation. Previously a prior successful call could leave a stale reached
flag if a later call exhausted its instruction bound without a stop. Three
asset-free mock-CPU tests require a fresh stop and reject a fresh failure. This
does not change native instruction execution, original rules or the runtime.
The3190 supplied-motion comparisons and40 trap-door lifecycle traces/800 cycles
were rerun after this guard change; their output hashes are unchanged.

## Remaining Work

- Current markers do not model reaction consequences. The subsequent contact
  probe recovers10:1b04, pushes/disarm, native pending-health/dead-pose writes
  and first-frame animation, but not later animation/death progression.
- Include ATMSlideRock presentation, retaining/restoring temporary record fields.
- Recover surrounding trigger admission and actual update/presentation cadence.
- Inspect native reset/checkpoint/file-save behavior separately from bank state.
- Complete the requested trap-door caller/admission/scheduling/collision audit.

No complete game-frame simulation, save/restart parity, temple playability or
whole-game coverage is claimed. Production importer, campaign, runtime and
README remain untouched, and this branch is not merged or pushed.
