# Crouch and prone input consumption

This extends the [saved-player input work](player-input-wrapper.md) with the
low controller families. It reuses the earlier crawl geometry and alignment
investigation (`tools/probe_crawl_lie_down.py` and
[level 6 research](level6-ruins-plan.md)); it does not replace that evidence.
Those probes addressed entering and drawing tunnels, not the complete input
bank effects of crouching, crawling and standing up.

## Executed scope

`tools/probe_low_input.py` executes the original GenCtrl gates and these bodies:

| Original code | Covered behavior |
| --- | --- |
| 6:0560-07e0 | Living type0 Prince, low/prone dispatch and protected-mode reset |
| 6:07ee-0998 | Prone inputs, crawl requests, standing clearance and input consumption |
| 6:099a-0b58 | Crouched controller, rise veto, low step and lie-down selection |
| 6:0e8e-0f56, 1068-10e2 | Ordinary no-gap Down path and crouch entry |
| 6:0006-0098 | Actual type0 JumpSeq resource lookup and sequence/cursor writes |
| 4:2bae-2bcc, 3e3a | Relative-X arithmetic and ClearControls |
| 4:3cae-3d14 and prior sampler/remap ranges | Saved-player composition in persistent traces |

JumpSeq is **not a no-op request sink in this probe**. A supplied resource
lookup reports the real SEQS IDs from `Prince.rsrc`, with explicit missing-ID
boundary cases. The original selection code then updates both sequence words
and resets the cursor. This matters because the prone controller reads the
selection again after requesting the stand sequence: successful selection of
124 suppresses a second crawl request in that same call.

The independent reference is `tools/reference_low_input.py`, outside runtime.
The level headers and native column-table values are checked against original
data. No original resource file is modified.

## Recovered rules

In crouch pose 109, carpet handling and pickup precede ordinary low movement.
The level 5 carpet check uses the current cell and the physical cell to its
left, not the cell behind the actor relative to facing. The actual carpet and
pickup actions remain supplied endpoints here.

With Down active, fresh Forward requests the short low step (79), or lie-down
(125) if the supplied tunnel/scythe cell requires it. ClearControls followed
by Forward consumption leaves Forward at +1; it does not also leave Down
consumed. If no Forward step was accepted, active Down clears the other
directions and ends at +1 instead. **Shift does not veto the low step.**

With Down zero, rise (49) has priority unless a gate or enabled scythe vetoes
it. A fresh Forward under that veto may request 79 without the consumption
used by the Down-held branch. These paths therefore cannot be represented by
one unconditional consume-on-crouch rule.

Ordinary crouch entry requests 50, clears directions and consumes Down while
preserving the modifier. This consumption still occurs if the sequence
resource lookup fails. The ordinary Down probe supplies a false gap predicate;
it proves this no-gap path, not ledge-descent admission. Ruins scythe alignment
at distance below 8 uses the native signed-word arithmetic.

In prone poses 246-261, leaving all low cells requests stand sequence 124.
Other non-idle prone poses clear directions while keeping the modifier.
At prone idle pose 251, active Up may stand if clearance permits it;
otherwise fresh Forward precedes fresh Backward (122/123). Consumed horizontal
input alone is insufficient. The outer dispatcher can also call the handler
for poses 262/263, but its own range check returns without these input effects.

Protected GenCtrl modes 4/5/9, and selected sequences 27/110, clear directions
before any of these low actions. Rising poses 110-116 use the protected mode;
later rise poses do not acquire a generic low-action dispatch merely because
they look similar.

## Native comparisons and persistent traces

| Matrix | Matching calls/steps |
| --- | ---: |
| Crouched controller, all 405 banks, both facings, cave/ruins contexts | 11,340 |
| Prone contexts and pose boundaries | 40,500 |
| Lie-down alignment boundaries | 1,188 |
| Prone standing-clearance boundaries | 1,188 |
| Protected resets | 18,225 |
| Carpet priority | 48 |
| Resource-selection boundaries | 24 |
| Ordinary crouch and no-gap Down entry | 3,240 |
| Crouch-entry alignment/resource boundaries | 504 |
| Persistent saved-player steps | 100 |
| **Total** | **76,357** |

All match, including the bank, X, warning, both selected-sequence words,
cursor, sequence requests and supplied-action observations. These are bounded
synthetic controller cases, not a count of distinct reachable gameplay states.

The 100 steps form 32 traces: eight scenarios, both facings and both level
contexts. They cover Forward held or released through the last lower reset,
low step/release/rise, crawl held versus released, stand-before-crawl, rise
veto followed by clearance, and a raw gate retaining an existing pending tap.
The saved player bank persists; the working bank is deliberately poisoned
between calls. Native X, warning, sequence selection and cursor also persist
without being overwritten from the reference result. Recording observes the
expected resulting bank, which is then saved by the real wrapper.

Pose/mode progression, terrain, pickup success, gate/scythe clearance, reveal,
keyboard and recording endpoints are supplied. The traces do not advance
AnimChar, simulate FrameAdv, prove terrain reachability, cover vertical
inversion/death/replay, or certify full input parity. Earlier matrices retain
their original boundaries; their JumpSeq sink is not retroactively removed.

Reproduce locally:

```powershell
.venv\Scripts\python.exe -m tools.probe_low_input --source ..\PoP2-Mac-Code-Recovery --output rendered\native-low-input.json
.venv\Scripts\python.exe -m unittest -q tests.test_low_input
```

Output digest: `5d1120d8f0dfc72d7e9d9c07324d1362e7fb98499f50ef75da07ba67763e9694`.
Executable resource-fork digest:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Seventeen asset-free tests run in CI alongside the prior input tests.

## Runtime consequence and remaining migration

The subsequent [runtime handoff](low-input-handoff.md) now replaces the
ordinary low/prone command slot with the production bank, using this audit.
It records the actual resource modes, preserved host tolerances and remaining
special contexts. The text below records the earlier correction and boundary
before that migration; it is not the current ownership checklist.

The recovered Shift rule exposed a concrete port mismatch: while crouched,
Shift + Forward was classified as a standing cautious step and left pending,
so the Prince did not make the low step. The same happened if Forward arrived
during lowering. The runtime now uses its existing low-step path in both cases.
A scene regression covers both facings, input before/after pose 109, and
release afterward without an unintended standing step.

This correction does not introduce a second directional authority or a new
timeout. The port's latest-command slot still needs replacement using the
recovered bank lifecycle. Remaining research includes ordinary vertical/ledge
action admission, pickup admission and armed outer gates; integration must
also preserve documented intentional host tolerances. Full keyboard-event,
animation and scene transition checks are still required during that migration.
