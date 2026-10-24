# Temple Gate Hanging Reactions

Research only, based on `62d0ab3`. Executes the previously excluded hanging
branches of StopGate5:14a8-152e and the separate cue helper5:153c-15a2. This
does not connect hanging actors to the persistent mixed-motion experiment or
make the temple playable.

## StopGate And Sequence Selection

In temple environment2, StopGate sets the TROB phase to-1, requests cue0x112
and runs real LoadKid4:4b02, replacing all62 working-actor bytes with the saved
Prince. It then computes `FirstInRow(savedRow-1)+savedColumn`, with signed-word
addition. The negative FirstInRow sentinel at-1 is-1, not-10.

It calls native JumpSeq6:0006 with47 only if that computed cell equals the
gate cell, facing is exactly-1, **action word+16 is2**, and the supplied stopped
position argument is exactly0. Nonzero positions56/255, other facings,
action0/6 and adjacent columns do not pass. Sequence-mode word+52 is not
the action word and is not this admission condition.

JumpSeq's SEQS47 resource existence service is supplied. With a non-null
result, the native body sets cursor word+36 to0 and current/selected IDs+38/
+40 to47; all other actor bytes remain unchanged. With a missing resource,
those fields retain their old values. In both cases the original StopGate
copy loop still copies all62 working bytes back to the saved Prince.

There is **no local room-equality check in StopGate's hanging branch**.
Supplied actor room0 controls still enter when the other conditions match.
This is a statement about this helper, not proof of cross-room hanging
behavior during live play: caller admission/order remains a separate boundary.

## Separate Hanging Cue

Helper5:153c does require gate room==saved Prince room. It accepts action2
or6, computes `FirstInRow(savedRow)+savedColumn`, and requests sound29 only
when that cell equals gateCell+10 or gateCell+11. It does not test facing,
select a sequence, copy actors or modify the gate phase. Its predicate must
not be substituted for StopGate's narrower sequence-selection condition.

## Evidence

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_gate_hanging --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_gate_hanging_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_gate_hanging_reference
```

**14,268 native/reference comparisons, zero mismatches**:
13,284 StopGate controls and984 separate cue controls at all41 original
header-admitted temple gate anchors. Supplied controls cover facings,
actions, adjacent columns, stopped positions, actor rooms and resource
availability. The native FirstInRow DATA prefix0/10/20/30 is checked.

The run observes164 JumpSeq47/resource/copyback admissions,82 with an
available resource and82 with the supplied missing-resource control, plus
164 separate sound29 admissions. Eleven asset-free tests fix the exact
conditions, action/sequence-mode distinction, complete actor byte effects,
negative-row sentinel and service boundaries.

Comparisons include both62-byte actors, complete original level, TROB
scratch/phase and bank canaries, ReadCell cache, ordered requests and the
unchanged relief countdown. Native bodies execute; GetResource17:330e
returns only existence/non-null, since JumpSeq47/type0 never dereferences
the handle. Actual original SEQS47 presence/hash is checked, but its words
are not executed by this probe. Audio remains a request sink.

Executable SHA256 is
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`;
original SEQS47 SHA256 is
`5ce1dbf877bcd04bddf78671d58060c491463e7738d89b6d304a2669f6866bcd`;
compared-output digest is
`324918b526680ea072d2b6b9e6d62d175e2b5d251fc6834c770338ca18b4aaf0`.
Original level10-13 hashes remain in the ignored report.

## Remaining Boundaries

Only supplied type0 actors and bounded FirstInRow indexes-1..3 are covered.
Actor1 conversion and special enemy sequence branches are not executed.
There is no AnimChar/SEQS47 clip execution, fall progression, actual geometry/
collision/death, complete caller/FrameAdv schedule, sound playback/pixels,
saves/reset or runtime integration. Next: compose the actor byte effects
with full gate animation or persistent mixed traces, preserving those bounds.
