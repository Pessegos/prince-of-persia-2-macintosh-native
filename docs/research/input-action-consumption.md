# Ordinary action input consumption

This extends the [input audit](../INPUT_RECOVERY.md) past the dispatcher's
action-call boundaries. It is research, not integration of a new runtime queue.

`tools/probe_input_actions.py` executes the original action bodies and compares
their bank, sequence requests, X and warning state with the independent
`tools/reference_input_actions.py`. The original relative-X helper at 4:2bae
and ClearControls at 4:3e3a execute too. All **11,304 cases match**.

| Original action | Cases | Input-bank effect |
| --- | ---: | --- |
| Standing forward jump, 6:15ea | 810 | Consume Forward and Up; preserve Backward, Down and modifier |
| Step, 6:1276 | 1,746 | Consume Forward and modifier, including rejected/no-sequence attempts; preserve the other directions |
| Run/restart, 6:11a0 | 2,556 | Clear all directions, then consume Forward; a near-barrier step attempt may also consume the modifier |
| Turn, 6:10e4 | 954 | Clear directions, consume Backward, set warning state |
| Running jump, 6:1c14 | 5,238 | Rejection leaves the bank intact; acceptance clears directions and consumes Up |

These differences matter when two commands overlap. A standing jump does not
erase the same inputs as a run start. An attempted step can consume its
command without starting an animation. A rejected running jump can retry a
released Up at a later valid pose; accepting it removes the other pending
directions. A universal queue clear or universal one-action consume would
therefore both be wrong.

The running-jump matrix checks the unsigned pose7-14 gate for sequence4,
the alternate sequence100 pose192/196 gate, and the alignment interval
[-31,15). A more negative alignment rejects an ordinary running jump;
the other out-of-range cases use a fallback. Two supplied supported cells
accept without that alignment adjustment. These are original branches,
not proof that the supplied terrain occurs at a particular room position.

The matrix uses every valid 405-state bank in canonical action contexts and
both facings, then boundary sweeps for distance, barrier kind, warnings,
supported cells and signed word wrapping. It fixes the real level5 header
(environment3), a living type0 Prince and ordinary turn sequence selection.
Other environments, actor-specific turn branches and scripted entries remain
outside this proof. Tests run without original assets in `tests/test_input_actions.py`.

Terrain distance, wall predicates, ahead cells, support, column and gap
distance are supplied. JumpSeq is an animation-request sink: the test does
not execute the requested animation, automatically advance poses, establish
physical reachability, or run the full player wrapper/FrameAdv. The separate
dispatch matrix still has its documented action boundaries; its conclusions
must not be silently upgraded to full gameplay parity by this result.

Reproduce with local read-only original resources:

```powershell
.venv\Scripts\python.exe -m tools.probe_input_actions --source ..\PoP2-Mac-Code-Recovery --output rendered\native-input-actions.json
```

Output digest: `bb0a54499d01fad56ed311a140f392d889fabad81ac2f4f67531f8122be7948f`.
Executable resource-fork digest remains
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.

The [composed controller traces](input-controller-traces.md) now combine these
bodies with sampling and routing. Remaining work includes Up/Down, low-pose,
ledge, pickup and armed-controller paths. The runtime still has its host
directional command slot. The Ctrl lifecycle correction is already integrated
separately; this research does not replace that slot or the approved port
input tolerances.
