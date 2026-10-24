# Temple Gate Callee Semantics And Native Services

Research only, based on `56041b9`. This corrects two misidentified supplied
endpoints in the initial gate/mixed experiments and then replaces them with
their real original bodies. No playable runtime changes.

## Semantic Correction

-4:4b02-4b14 is LoadKid: it copies the complete62-byte saved Prince at
  a5-0x50d2 into the working actor at a5-0x5056. It does not calculate support
  or update the ReadCell cache. A no-op cannot prove its actor side effects.
-5:4766-489c tests eligibility for the level4 sigh of relief after shutting
  opponents behind a gate. It is not a collision or crushing predicate.
-The caller5:42c6-42ce writes4 to a5-0x5008 when that predicate succeeds.
  This is a relief countdown, not pending damage. FrameAdv2:640c-6446 reads
  that word, eventually requests sound110 and stores the once-only sentinel
  -2. That FrameAdv slice was inspected, not executed by this experiment.

The earlier gate and mixed reports' v1 field names were wrong, though their
motion/phase/compaction byte comparisons passed. Their v2 reruns rename
`damage` to `relief_countdown`, `support_cache` to `load_kid`, and `contact`
to `relief_check`, explicitly marking a supplied true return as a forced
branch control. Native temple levels cannot take that positive relief path.

## Relief Predicate

The native predicate returns0 immediately unless the level header number
is4, and also rejects countdown-2. Otherwise, it uses the current gate TROB's
room/cell, the saved Prince's room/row/support column and the room's actor
count at LEVL+0x21a6+(room-1)*192. Room0 gives a zero count.

A nonempty bank, matching Prince room/row and distance below5 columns are
required. The loop considers only actors in the same room/row with native
ALIVE<0. At least one must be on the far side, and any qualifying actor on
the near side vetoes the result regardless of bank order. Dead/other-row/
other-room records are ignored, not positive evidence. With the gate left
of the Prince, an opponent exactly at the gate counts as far; with the gate
at/right of the Prince, only strictly greater opponent columns count as far.

## Evidence

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_gate_services --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_gate_services_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_gate_services_reference
```

**11,361 native/reference comparisons, zero mismatches**:

-246 rejection controls across all41 original temple gates, countdowns and
  supplied empty/nonempty opponent banks;
-7,200 supplied level4 column/distance/ALIVE boundary controls;
-840 supplied level-number/countdown/room/row/mixed-bank-order controls;
-3,075 connected original temple gate steps with real LoadKid and real relief
  predicate, all41 anchors, five positions, five phases and three countdowns.

The level4 controls patch only the number/count fields in a temple level
fixture and supply up to three actor records. They test the predicate, not
original level4 playthroughs or opponent generation. All8,286 direct calls
leave the level, actor banks, saved/current actors, ReadCell cache, TROB bank/
scratch and countdown unchanged;541 return1 and7,745 return0. No endpoint
is supplied in those direct calls.

Connected gate calls compare complete level bytes, gate foreground/phase,
ordered calls, countdown and actor/bank/cache canaries. On StopGate paths,
all62 working-actor bytes must equal the saved Prince after real LoadKid.
Other paths must preserve the working actor. The real relief result is
always0 in temple levels, so the countdown is preserved. Only audio5:3828
and redraw5:0fe6 remain request sinks for these connected steps.

Nine asset-free tests fix admission, asymmetric equality, distance4/5,
near-side veto order, ignored records and the bounded model domain.
Executable SHA256 is
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`;
compared-output digest is
`89b0251ab8e3dbceff1c27fa12b1864f15c4e6f8fc171dca89bcf72a5833b0e6`.
Original level hashes remain in the ignored report.

## Remaining Boundaries

Saved Prince room0/mode0 excludes StopGate hanging reactions; those paths
are not recovered by this connected test. Actor support columns are supplied,
not derived from FRAM geometry. Bank iteration/compaction, mixed rock motion,
actual collision/crushing, sound playback/pixels, complete FrameAdv order,
saves/reset and temple runtime integration are outside this experiment.

The [persistent mixed variant](temple-mixed-lifetime.md#persistent-trace-with-real-gate-callees)
now also executes both real callees in120 traces/14,784 comparisons, with
all62 copied working-actor bytes checked. Four additional asset-free tests
pin the actor-copy model. Next: connect rock movement, preserving the
explicit scheduling boundary.
