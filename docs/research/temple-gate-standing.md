# Temple Gate Standing Clearance

Research only. Executes GateBarrToStandUp4:5baa with original ReadCell4:27ee,
normalization4:26e2, GetCellsInFront4:39fc, FrontCell4:3a48 and AddCharX4:2bae.
No supplied services, runtime edits or claim of physically reachable actors.

## Ordered Rule

Level8/actor room9 returns zero without reading a cell. This is a controlled
non-temple level-number check, not a temple exception inferred from a map.

Otherwise, look for tile4 in this precise order: current actor column,
GetCellsInFront(1), FrontCell. The original direction tables for the latter
two are opposite: facing-1 uses column-1 then column+1; facing0 uses column+1
then column-1. Stop at the **first gate**, even if that gate is fully raised
or outside the overlap band. Do not keep searching for a gate that blocks.

Only low-byte positions1..183 can make this predicate return one. Zero and
184..255 return zero. This does **not** mean a closed gate permits standing
or passage overall: its other collision rules are outside this helper.

For the first gate's normalized cached column, let `L = 207 + 51 * column`.
`anchor = AddCharX(-10) - 22`, wrapping each word operation. One is returned
iff `L + 19 <= anchor <= L + 57`, inclusive. Actor X is not converted to a
port coordinate; neither the supplied actor column nor its room is used as
a substitute for the resolved gate column after neighbor traversal.

ReadCell writes all six cache words and can update the foreground/kind room
base pointers at A5-4824/A5-4820. Undefined reads retain the preceding valid
room bases. The probe predicts these writes and compares the entire A5 data
bank with no other changes permitted; level bytes stay immutable.

## Evidence

`tools/probe_temple_gate_standing.py` compares39,318 native calls:

-17,712 fixtures around all41 original gate anchors in levels10..13: both
 facings, three supplied actor columns, eight gate positions (including
 a high-byte control), nine X values spanning inclusive limits and selected
 warm-cache reads. Gate positions/actor placements are controlled fixtures.
-21,600 controlled topology fixtures: no links, horizontal links and
 vertical links; missing gates, competing gates, room edges, undefined
 cells, signed-extreme X and gate priorities. Modified maps are synthetic
 controls, not additional original content or reachable gameplay.
-Six level-number/room fixtures isolate the level8/room9 short circuit.
-Zero mismatches. Return values, ordered requested cells, normalized cache,
 pointer side effects and unchanged A5/level bytes match independently.
 Original DATA direction and boundary tables are asserted before the run.
 Eleven asset-free regressions pin limits, priority, traversal, exemption,
 cache retention and word wrapping.

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Compared-output SHA256:
`50bfd07b28b8b4d30927e67e102111864e6a2d37a80f9c6fd20f49415777ad08`.
Original resources and detailed reports remain ignored locally.

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_gate_standing --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_gate_standing_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_gate_standing_reference
```

## Remaining Scope

No sprite bounds or animation are executed by this helper. It is distinct
from [visible-height passage](temple-gate-admission.md), CheckGateForKid's
contact response and the controller that decides whether to request standing.
Supporting floor, overlap-bank construction, complete barrier/ejection,
multi-frame motion and playable temple integration remain separate gaps.
