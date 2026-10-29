# Airborne directional handoff audit

This block applies the already recovered input-bank rules to a missing runtime
boundary. It does not redo the sampler/action matrices or enable another queue.

## Concrete remaining difference

On the actual level6 room8 platform, start an ordinary forward jump (SEQS3),
then press/release Up followed by Down after displayed pose27. The current host
lands into crouch50/107. Reverse the order and it lands into jump28/67. The
same difference occurs in both facings. Each tap is held for one simulation
tick and released for one tick, with no held direction remaining at landing.

The grounded controller is already migrated. The missing part is bank ownership
during the arc: `start_sequence(3)` retires the bank, so these callbacks still
replace `pending_action`. The new standing gate can import only the last request.
The recovered original bank retains both fresh directional latches and chooses
Up before Down at its ordinary ready gate.

| Window / tap order | Original routing | Current host, both facings |
| --- | --- | --- |
| Before pose26 / Up then Down | No action after reset | No extra action |
| Before pose26 / Down then Up | No action after reset | No extra action |
| After pose26 / Up then Down | Up | Crouch50/107 |
| After pose26 / Down then Up | Up | Jump28/67 |

This distinguishes the remaining priority defect from a missing reset: the
existing ordinary-jump pose26 clear already discards these earlier released
taps. A larger timeout or another clear would incorrectly discard valid late
input instead of preserving its original priority.

## Execution and limits

`tools/audit_airborne_handoff.py` runs two separate experiments:

- Eight hidden host scenes with original SEQS, actual terrain, normal animation
  progression and real callbacks. The supplied entry is an already selected
  valid SEQS3 jump; takeoff admission is outside this fixture. Peaceful mode
  excludes combat. Left-facing X450 and right-facing X260 keep the whole arc
  above the same flat platform. The diagnostic checks room/floor/death state.
- Eight persistent original M68K traces, 84 steps total, through sample4:3e84,
  remap/player wrapper4:3d96 and GenCtrl6:0560-07e0, including pose26's
  ClearControls4:3e3a. Pose/mode/sequence/raw axes/facing are supplied per step;
  living unarmed Prince, level6 room8. Cell/pickup/Up/Down action bodies are
  explicit route sinks. The native bank/events match the separate existing
  `reference_input_bank` / `reference_input_routes` model on all84 steps.

The native experiment has no animation, physics, FrameAdv, keyboard polling or
emulator. Its supplied ready pose15 is a routing observation, not a claim that
the original and host display the same idle frame or run synchronized clocks.
The host can select a buffered action before displaying that idle pose. No
whole-game or full airborne-control parity follows from these eight cases.

The diagnostic must distinguish `sequence_id` from `source_sequence_id`: the
ordinary jump links to idle2 while its selected/source ID can remain3. An
initial report incorrectly classified that idle as an unfinished jump. Inspecting
the pose/sequence trace corrected the diagnostic; the runtime was unchanged.

```powershell
.venv\Scripts\python.exe -m tools.audit_airborne_handoff --source ..\PoP2-Mac-Code-Recovery --output rendered/input-queue-audit/airborne-handoff.json
```

Result: eight host cases, two priority differences, 84 matching native/model
steps. Original executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Report SHA256:
`c5acbd5d1ba9591aa4a5419c900e8d846a654a3728889af0587eac6d972c8beb`.
The original file was read only and checked unchanged after execution.

## Next runtime block

Extend the existing directional bank through ordinary/running jump families3/4
and their grounded return. Transfer ownership at takeoff rather than recreate
intent from the last legacy command. Apply the native pose26/44 clears to that
same bank and preserve modifier sampling; import no executable directional slot
in parallel. Route airborne callbacks into the bank and retire the superseded
pending-command reset paths together.

Before enabling that stage, preserve and test the explicit host tolerances:
held-jump repeat/cancellation, horizontal release followed by vertical wall
alignment/climb, late genuine taps, startup chords, terrain wall/fall/death
interrupts, and modal resets. Extend coverage to running-jump44, horizontal and
modifier conflicts, and inverted controls. Low/prone/ledge/armed ownership
remains a separate migration. This audit changes no runtime behavior.
