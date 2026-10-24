# Temple Gate Bank And Actor Updates

Research only, extending [actor clip progression](temple-gate-actor-clip.md)
from `d9ca6c8`. No runtime changes or temple gameplay enabled.

## Connected Findings

The experiment now executes the complete native AnimTrobs `5:0c38` bank
loop and its stable compaction, not just one type4 dispatcher call. It
interleaves those bank calls with native actor clip updates over eight
persistent cycles, comparing **both supplied orders**:

- In actor-first order the initial hanging animation can advance before
  StopGate selects47. At the end of that cycle mode remains2 and cursor0
  points at newly selected47; its first pose/mode/X effects wait for the
  next supplied actor update.
- In bank-first order a gate stopping immediately can select47 before the
  actor update, yielding mode5/pose50/X+16 in that same supplied cycle.
  There are246 such first-cycle mode5 results in this corpus, versus none
  with actor-first ordering. This demonstrates why ordering matters; it
  does **not** identify the original FrameAdv schedule.
- Every initial record is visited before completed records are compacted.
  Default-kind1 controls are removed, and surviving gates retain order.
  All160 bank bytes, including unused tail bytes, match the native writes.
- Supplied duplicate gate records can select47 twice before an actor
  animation runs: selection leaves mode2 unchanged. These are deliberate
  bank controls, not a claim that ordinary native registration creates
  duplicate coordinate records.
- Fast closing still has separate cue/relief behavior without selecting47.
  Ending gate records do not remove or change the actor's subsequent clip.

The existing [frame-order reading](frame-phase-order.md) already places
AnimTrobs at2:6230 before the Prince update2:625c and AnimChar2:6372. That is
static evidence for bank-first ordering in the ordinary world update, not
an unresolved guess between these two controls. The present probe does not
execute that coordinator or the intervening PlayerCtrl/geometry; those can
change the selected clip before its AnimChar call.

## Evidence

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_gate_actor_bank --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_gate_actor_bank_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_gate_actor_bank_reference
```

**2,460 persistent traces, 78,720 native/reference operation comparisons,
zero mismatches.** Each trace runs eight bank updates and eight separately
checked LoadKid/AnimChar/copyback triplets. Both supplied orders cover all41
header-admitted original temple gates, five position/phase controls and six
bank topologies: single gate, removed record before/after, full20 with one
gate, duplicated gate, and two same-anchor slow/fast records.

17,548 original record visits execute. After eight cycles,2,050 traces
have no bank records left,328 retain one and82 retain two;1,230 traces
retain selected source47 and1,230 source9. These are corpus outcomes, not
game-wide frequency or completion measures.

Every operation compares all level bytes, both62-byte actor records,
TROB records/count/storage/scratch, object scratch and event order. ReadCell
cache,22-byte MOB scratch, MOB count, pending effect and relief countdown
are canaries; original sequence bytes and prepared handles are read-only.
Eight asset-free tests fix compaction/order, duplicate selection, the
first-cycle scheduling difference, fast closing, empty-bank preservation,
scratch writes and unsupported-input rejection.

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Compared-output SHA256:
`854dade83af706036ff0097739c46606e22f3caf5de13df121362dd9e07c6195`.
Original level/sequence hashes remain in the ignored report.

## Boundaries

Native execution includes AnimTrobs iteration/compaction, per-record raw
cell loading, type4 motion/hanging effects, LoadKid, JumpSeq, AnimChar and
the original clip words. The independent bank model reuses the separately
checked hanging-gate reference and bounded clip decoder.

Supplied services remain sound5:3828/4d84, redraw5:0fe6, resource existence
17:330e, prepared sequence handles4:3098 and state0 handle traps. Actor
copyback executes inline5:1516-1526 with a harness stop before its epilogue.
There is no standalone SaveKid function or native scheduler claim here.

Actor placement, initial foreground phases, bank topology and both update
orders are supplied. These are not complete FrameAdv, reachable hanging/
duplicate-bank gameplay, input/GenCtrl, support/physics/fall/contact/death,
plate activation, MOB motion, drawing/audio playback, saves/reset or temple
runtime integration. The next useful connection is the actual world/Prince
caller and its intervening controls/geometry, not interpreting mode5 alone
as a fall or re-discovering the already recorded static call order.
