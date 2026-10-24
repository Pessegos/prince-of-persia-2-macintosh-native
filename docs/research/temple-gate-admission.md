# Temple Gate Admission

Research only. Native4:5b0e, used by CheckGateForKid4:60e4 at4:6168,
returns **one for blocked**, not one for permitted. No runtime changes.

## Recovered Rule

Outside environment1, actor kind1 and selected source68 bypass this test.
Otherwise the height is the signed-word difference between the actor's
visible rectangle bottom and top (actor offsets46 and42). Kind7 adds46;
kind8 adds33, again with signed-word wrapping. The comparison itself uses
signed longs: blocked iff `2 * ((foreground & 255) >> 2) + 11 < height + 13`.
Equality permits passage. Phase/high-byte flags and the low two position
bits do not change this predicate. It does not read a tile or move an actor.

Environment1 has a different branch, before the actor exemptions: blocked
iff `(foreground & 31) < 19`. Environments2/3/4 share the height branch.
These extra-environment cases are controlled headers, not native temple data.

The visible height is not interchangeable with SHAP image height or the
collision width. [Real bounds](temple-sprite-bounds.md) intersect the visible
rectangle with the supplied screen rectangle; unavailable/imageless images
can retain the default rectangle. These details affect the gate threshold.
This is only one predicate: its exemption must not be interpreted as a
promise that the caller's other collision conditions permit movement.

## Evidence

`tools/probe_temple_gate_admission.py` executes the original instructions in
bounded Unicorn M68000, independently of `pop2` collision rules:

-102,400 direct comparisons: every foreground low byte, controlled high
 bytes, environments1..4, kinds0/1/7/8/11, selected sources9/68 and ten
 rectangle fixtures including signed subtraction/addition overflow.
-14,080 predicate comparisons after actual type0 LoadFrame4:2a72,
 SetupSword3:0ac8 and GetCharEdges4:5cbc. All352 original Kid poses, both
 facings and four supplied X/Y placements produce2,816 real bound chains;
 five foreground thresholds are checked after each chain. These are not
14,080 independent world updates or reachable gameplay states.
-Zero mismatches. The complete A5 data bank is unchanged by each predicate
 call; frame/bound outputs, metadata, drawing, level and unrelated canaries
 are also checked in the composed path. Eight asset-free regressions fix
 equality, quantization, exemptions, clipping and signed-width arithmetic.

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Compared-output SHA256:
`2a924fafaa2bc7ac9a57f696d024a268d4d7ec6ed08608ae267335e3c7c94fe0`.
Original resources and the detailed report remain ignored locally.

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_gate_admission --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_gate_admission_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_gate_admission_reference
```

## Boundaries

The isolated predicate needs no services. The composed drawing path retains
the explicit SHAP-header dimension service and half-open SectRect callback,
prepared FRAM/AFRM/library handles and supplied actor/drawing positions from
the preceding bounds proof. Resource loading and graphics are not executed.
Real cell selection, barrier/contact response, standing, crush/ejection,
physical support, multi-world updates and playable temple remain separate.
