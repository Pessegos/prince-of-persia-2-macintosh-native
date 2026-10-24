# Temple Mixed Plate/Gate/Rock Lifetime

Research only, based on `c1151d1`. Connects real CheckPress admission,
ordinary/permanent pressure, both original level11 room3 mixed link chains,
gate animation and native TROB bank iteration/stable compaction. It does
not enable levels10-13 or change the playable port.

## Original Chains And Supplied Traces

The closing source at cell15 is kind6, link54: gate cell2 first, then rock
cell18 through link50. The opening source at cell16 is kind5, link51:
rock cell18 first, then gate cell2 through link52. Both original traversal
orders and their source-before-target registration order execute natively.

120 persistent traces combine five supplied plans with gate positions0/80/
255, empty/full MOB banks, and four TROB topologies (empty, existing gate,
19 default controls,20 default controls). The plans are full ordinary open/
hold/close, opening reversed by the closing plate, held pressure followed
by rejected contact, permanent opening, and closing followed by opening.
Positions and bank controls are explicit fixtures, not claims of reachable
gameplay states. Call counts are not rendered-frame timings.

The current actor is supplied type0/mode0, with selected supporting cell,
Y, FRAM auxiliary and ALIVE/pose values. The saved actor's room0 excludes
hanging reactions. ReadCell, pressure admission, both linked mechanism
bodies, gate motion and stable bank compaction are native, not request sinks.

## Findings

- A source plate can release and disappear while its gate continues opening,
  holding and closing in a separate TROB. Compaction preserves the surviving
  record's order and unused storage bytes; it does not cancel linked motion.
- The closing plate can change the live gate to fast-close phase4 while
  activating the forced rock record. Its following bank update can remove
  the gate while preserving the source plate's remaining release lifetime.
- Opening-mode5 may leave an absent rock absent; that does not prevent gate
  activation. Conversely, a full MOB bank does not prevent gate registration.
- Permanent pressure can open a gate to255 without a source plate TROB;
  the gate record subsequently disappears while the permanent state remains.
- Source registration can take the last TROB slot ahead of the target. In
  bounded full-capacity controls, a gate may remain at80 without any TROB
  after all source/default records disappear. Subsequent held pressure can
  register a missing gate without recreating a missing source record whose
  timer5 never received animation updates. This documents native capacity
  behavior; it is not a recommendation to remove port capacity safeguards.
- Admission rejection does not refresh the source, and bank animation leaves
  the pressure ReadCell cache intact even when its last read named the rock.

## Evidence

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_mixed_lifetime --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_mixed_lifetime_v2.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_mixed_lifetime_reference
```

**14,784 native/reference operation comparisons, zero mismatches**:
576 CheckPress calls and14,208 animation calls in120 traces. Every operation
compares full level bytes, MOB/TROB banks including unused storage, scratch
records, object/rock/pressure requests and arguments, OS scratch, press flag,
relief-countdown word, complete ordered reads/cache and current/saved actor
canaries. Final states include74 gates at0,40 at255 and6 at80; all120 traces
end without TROBs under their supplied plans. Ten asset-free regressions
cover the composed behavior and capacity consequences.

Audio/redraw endpoints remain request sinks. LoadKid4:4b02 is a no-op and
the level4 relief predicate5:4766 returns supplied0:30 relief requests are
observed, not collision checks. The initial v1 support/contact/damage labels
were incorrect; v2 corrects the names without changing native transitions.
The [real-service probe](temple-gate-services.md) separately executes both
callees for bounded gate steps. Loose-floor/trapdoor sinks
remain guarded and are not reached. The native rock **activation** body is
executed; its movement/presentation dispatchers are not part of this trace.

Full FrameAdv order, actual support/contact geometry, hanging reactions,
sound playback, pixels, room cuts, saves/reset and playable temple logic
remain outside this experiment.

Executable SHA256 is
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`;
original level11 SHA256 is
`3f3559f2d1dd4853098d9a812692a69a64fd86ac1ae677745f8fea6cdb6f1664`;
compared-output digest is
`6901932fd123ca5cb477169f9748a7dd10bad1c4a02c7d163e828356b04bf274`.

## Persistent Trace With Real Gate Callees

The subsequent variant based on `758d4ce` removes the supplied LoadKid and
relief endpoints from the same120 persistent traces:

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_mixed_lifetime --source ..\PoP2-Mac-Code-Recovery --native-gate-services --output rendered\temple_mixed_real_gate_services_v1.json
```

All14,784 comparisons pass again, now with64 native LoadKid copies and30
native relief checks. The copied working actor is checked byte-for-byte
against all62 saved bytes; steps without LoadKid must retain the supplied
working actor. The current actor/FRAM inputs are explicitly resupplied
before **each** operation, as in the original schedule: this is not an
independently evolving Prince controller or a complete FrameAdv trace.

Source/target order, gate/plate motion, capacity outcomes, stable compaction
and unused bank/cache bytes remain identical. Real relief rejects level11;
its countdown never becomes damage or changes on a fast close. Only four
audio/redraw endpoints are reached as services; loose/trapdoor sinks remain
guarded and are not reached. Compared-output digest is
`578e76562e31998f27fb0eafbed8633fa8ca13f1d1d3822b9320e796ce5cbc03`.

Four asset-free actor-copy tests plus a service-boundary regression cover
the new variant. Next bounded work: connect rock movement. Hanging
reactions, geometry and whole-game timing require their own evidence;
relief alone is not collision or damage evidence.
