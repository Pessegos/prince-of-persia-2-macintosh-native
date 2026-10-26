# Temple floating ceiling contact

Original4:50da is a ceiling-contact helper, despite the decoded catalog
marker InitColDetBufs. The separate collision-history entry is4:5152.
This probe executes the helper, ReadCell/IsSpace, relative X adjustment
and JumpSeq229, and composes it with its actual CheckBarr caller.

The helper computes head Y using signed-word subtraction of supplied
body height. Only a head strictly above physical row*120-8 queries the
cell above the actor's cached column. Native space kinds0/9/27/47/49
leave the actor alone. A solid ceiling moves him six pixels backwards,
clears horizontal velocity and requests sequence229. It does not advance
animation or refresh the frame/body geometry, change vertical velocity,
move rows, reduce HP or register a death.

If Resource Manager lookup fails, the physical backoff and stop still
happen, while the old sequence/source/cursor remain. A successful lookup
sets source/active229 and cursor0. The lookup is the sole supplied endpoint;
the guarded original sequence bytes are present but not animated.

CheckBarr invokes this helper only for type0, both incoming-contact indices
exactly-1, a nonzero floating timer and mode4. Source70 skips ordinary bank
rebuilding but can still reach this final ceiling check. A new side contact
suppresses it. This ordering is checked with generated flags, not a replaced
caller decision. Sliding-rock queries use an actual empty MOB bank.

## Evidence

The native report compares27,116 calls with zero mismatches:21,960
declared-cell/head-position cases,3,904 actual caller cases,1,200 tile/
lookup controls,36 signed extremes and16 contact-suppression controls.
It covers all declared cells of temple levels10-13 at the strict head
threshold and both facings. Signed extremes distinguish word subtraction
from an unbounded host expression. Whole A5 comparison guards unrelated
fields, saved actor and TROBs; ordered cell/rock queries agree. Original
level, sequence and MOB memory remain unchanged. Eight asset-free tests
cover threshold/height, all space kinds, relative backoff, preserved fields,
failed lookup, vertical traversal and signed wrapping.

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_floating_ceiling --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_floating_ceiling_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_floating_ceiling_reference
```

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Compared-output SHA256:
`2c62a241486e107d9d52cf1e34244830b453400afe589876880ac134e5e70040`.
Detailed reports and original resources remain ignored locally. Actor/body,
prior banks/row, floating timer and empty MOB state are supplied. Nonempty
rock overlays, Collide responses, AnimChar/frame refresh, ShapeBounds and
complete FrameAdv remain outside this proof. No temple runtime is enabled.
