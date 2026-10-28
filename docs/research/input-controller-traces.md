# Composed input-controller traces

This combines [action consumption](input-action-consumption.md) with the
previously recovered sampler and unarmed router. It remains executable
research; the game's directional command slot has not been replaced.

`tools/probe_input_traces.py` executes original GenCtrl with the actual run,
turn, step, standing forward jump and running-jump bodies enabled. It compares
the resulting input bank, terminal sequence request, X, warning and cleared
step-helper flag against `tools/reference_input_traces.py`.

All **45,044 composed cases match**. The matrix crosses 405 banks, both
facings, 29 poses and two supplied terrain contexts. **1,936 other-action
cases are explicitly excluded**, rather than treating Up/Down-only actions
or sword drawing as if those action bodies had also been composed.

The probe then executes 18 persistent traces, containing **62 sampled steps**,
through actual sampling4:3e84, facing wrapper4:3d96, GenCtrl and those action
bodies. Bank, X and warning persist between steps. These also all match.

| Trace, repeated in both facings | Confirmed result |
| --- | --- |
| Running jump initially refused by pose, then terrain | Released Up remains pending; success clears the other directions and consumes Up |
| Backward and Up during running | Reversal wins and clears Up; releasing the keys leaves no later jump request |
| Jump tap before pose26 | The reset discards it |
| Jump tap after pose26 | It can survive to a standing gate |
| Recovery modes5 then1 | A released tap is discarded; a hold becomes fresh again after the last reset |
| Near-barrier run/step followed by an unobstructed run | Step consumption and run clearing compose without a phantom pending direction |
| Released Ctrl through run/brake | No later draw request |
| Facing changes during a turn | The physical key is reinterpreted against the new facing, rather than retaining an old run/turn classification |

The facing-change trace supplies the new facing explicitly, as an animation
would. Poses, modes and sequence context are also supplied. JumpSeq only
records animation requests; it does not advance an animation or transform
the next fixture. Terrain services remain supplied as in the action probe.
This is **not** a complete physical gameplay replay, original-hardware input
poll, full player-wrapper execution or FrameAdv comparison. It does not
prove that arbitrary supplied pose/mode combinations are physically reachable.

`tests/test_input_traces.py` checks the meaningful distinctions without
original assets. It also verifies that unsupported actions fail explicitly.
Its additional no-expiry example is a model composition property, not another
1,000-frame native gameplay measurement: a pending direction persists until
consumption/reset, rather than an elapsed-time timeout.

Reproduce the native comparison locally:

```powershell
.venv\Scripts\python.exe -m tools.probe_input_traces --source ..\PoP2-Mac-Code-Recovery --output rendered\native-input-traces.json
```

Output digest: `533c3a6d8ca10532fc2f39f841030af003ae4ebef96aa228e96181cd283bdd2d`.
Executable resource-fork digest remains
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.

## Runtime comparison and remaining migration work

A local port experiment at running pose8 supplied Backward and Up in both
callback orders, in both facings. The host retained different pending-jump
metadata, but its 40-step continuation after releasing the keys did **not**
produce an extra jump: reversal/recovery cleared it. Reports are local at
`rendered/input-queue-audit/host-conflicts.json` and
`host-conflicts-released.json`. This is not evidence that this combination
causes the user's unwanted actions. An intermediate bank/slot difference
alone is not a demonstrated visible bug.

The architecture difference is nevertheless concrete. A faithful migration
needs one authority for directions, rather than retaining a slot and a bank
that can both dispatch the same command:

1. Recover the remaining Up/Down, low-pose, ledge, pickup and armed outer
   gates, including failed-action consumption and entry/exit resets. Trace
   the actual player wrapper's saved bank and active-control gate separately
   from the automatic opponents' input bank.
2. Put the production directional bank in the input layer. Keyboard callbacks
   should update physical holds, with action classification at the simulation
   gate against the current facing and actor state. Keep the independent
   research model as the oracle, not a runtime dependency on `tools`.
3. Move a controller family at a time to that bank; remove its old slot
   producer and consumer in the same change. Accepted, rejected and deferred
   actions need their own verified effects. Keep the full animation and
   terrain clocks unchanged, then compare integrated movement traces.
4. Preserve explicit port policies as named policies. The 300ms repeated
   command filter is not native expiry. Existing chord, climb and armed
   buffering tolerances must not be silently removed while changing the
   representation. The user has revoked only the running Ctrl stop-and-draw
   extension in this investigation; that correction is already on main.

This avoids implementing a blanket reset or adding another time limit to
hide an unresolved consumption/scheduling difference.
