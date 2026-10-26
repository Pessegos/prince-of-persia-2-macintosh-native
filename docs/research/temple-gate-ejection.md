# Temple hard gate contact and ejection

This block replaces the log-only ejection in the earlier
[contact routing](temple-gate-contact.md) investigation with actual4:6202,
[face/back geometry](temple-gate-distance.md), admission, classification,
room adjustment and AddCharX. Prepared overlap banks and collision/body
rectangles remain inputs. It enables no temple gameplay.

Ejection calls each distance service twice. It stores their absolute values
as signed words, so the exceptional absolute value of-32768 remains-32768.
If the face distance is strictly smaller, the relative displacement is its
negative magnitude minus3. Working actor kind4 gets a further-8 on that
branch. Otherwise the back magnitude is used, including exact ties. Native
facing then determines the sign applied to actor X. The helper does not
change HP, ALIVE, animation, death registration or physical support.

The distinction from admission matters: a direct call can move an actor even
when the gate's face service returns the open/passable sentinel-1. The real
4:60e4 caller first rejects passable gates. Do not replace that caller with
an unconditional push or treat this movement as native crushing damage.

## Evidence

`tools/probe_temple_gate_ejection.py` compares24,264 original calls, zero
mismatches:648 direct ejections with neighbor/signed controls and23,616
complete hard-contact calls at all41 original temple gates. Caller controls
include both facings, three positions, source9/118, ALIVE-1/0, armed and
pose109 paths, body offsets and exact overlap255 versus511. These are
prepared fixtures, not additional original content or reachable paths.

Every byte of A5 is compared, allowing only the predicted actor-X, contact
mark, anchor, ReadCell cache and room-base pointer effects. Level, saved
actor, TROBs, supplied overlap banks and unrelated actor fields remain
unchanged. The order face/face/back/back is observed, not stubbed. No
geometry, ejection, resource, audio or animation endpoint is supplied on
these hard paths. Soft/cave responses are outside this caller corpus.

Nine asset-free regressions fix the side/tie rule, three/eight-pixel margins,
relative facing, signed absolute minimum, caller admission, exact overlap,
early exits and HP/ALIVE/animation invariance. Together with the prior
distance/contact tests,33 pass. All448 temple reference tests and seven
inventory tests also pass without original game resources.

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_gate_ejection --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_gate_ejection_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_gate_ejection_reference
```

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Compared-output SHA256:
`32073d2d5c95cd8dd5c837094299ad8ee58f08512e87ab458fe40dc41db97c0a`.
Detailed reports and original bytes remain ignored locally.

The old general soft distance4:5eae fixture is still separate: its forward
cell, floor/lava decisions and remainder/distance-kind side effects have
not been replaced by this ejection model. Next recover that selector, then
construct actual overlap banks around Collide and connect repeated physical
support. No complete FrameAdv, damage/death or playable-temple parity claim.
