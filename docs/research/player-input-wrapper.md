# Saved player input and the raw-control gate

This extends the [composed controller traces](input-controller-traces.md)
through the original player-input wrapper at **4:3cae-3d14**. It is research,
not a replacement of the game's directional command slot.

The wrapper executes this order:

1. Restore the player's saved five-word bank from `cb6e..cb76` to `cb78..cb80`.
2. Read keyboard axes/modifier through 2:55d2.
3. Gate the raw horizontal/vertical axes at 4:3cda-3cfc.
4. Sample the bank, remap facing, run GenCtrl and its selected action, then
   restore keyboard coordinates.
5. Call the recording endpoint 5:6072, save the resulting bank, and return
   that endpoint's word result.

The raw gate allows directions only if words `b06e` and `b02e` match, the
actor room is nonzero, and its sequence is not 59. Otherwise it zeros the
two raw direction words **without clearing the pending bank or raw modifier**.
A pre-existing negative direction can therefore remain pending, or even be
accepted by a later controller gate. This is not a universal input freeze.
The production migration must distinguish this gate, ClearControls, saved-bank
initialization and host focus/pause handling.

`tools/probe_player_input.py` compares actual wrapper execution with
`tools/reference_player_input.py`:

| Matrix | Matching cases |
| --- | ---: |
| All 405 saved banks, 27 raw combinations, both facings, gate matched/unmatched | 43,740 |
| Room 0/sequence 59, auxiliary countdown and recording-return boundaries | 2,160 |
| Wrapper plus recovered router/action composition | 21,940 |
| Persistent steps, both facings | 10 |

All **67,850 cases/steps match**; another **740 unsupported-action cases**
are explicitly excluded from the composed matrix. Each call checks the
bank seen at keyboard entry, the bank seen by recording, both final bank
copies, requested sequence, X, warning, auxiliary countdown and return word.
Keyboard and recording endpoints must each be called exactly once.

Before every call the probe writes a deliberately different working bank.
In the persistent traces it repeats this between calls while retaining the
saved player bank. Restoring and saving the player's bank keeps those values
from becoming player commands. This validates bank ownership at this boundary;
it does not execute an opponent's automatic controller or prove all NPC/player
scheduling in FrameAdv.

The auxiliary word `b06a` decrements when nonzero, using signed-word wrapping.
Pending commands survive its reaching zero. This proves that this word is
not a blanket pending-input expiry; its wider game meaning is not inferred
from this wrapper alone. It is unrelated to the port's 300ms repeat filter.

## Boundaries

The actual restore/save, raw gate, bank sampler, facing remap, covered GenCtrl
paths and ordinary action bodies execute. The fixture verifies the original
level 5/environment 3 header and a living type0 Prince. Raw keyboard output
and the recording endpoint/result are supplied. Recording is read-only in
this probe; actual demo recording/playback behavior is not recovered here.
Terrain remains supplied, and JumpSeq is a sequence-request sink.

This does not run OS keyboard polling, advance real animation/physics, cover
death lifecycle, vertical inversion, the special replay hook, all outer game
callers or FrameAdv. Up/Down-only actions, ledge/pickup/armed outer paths still
need their own composition. The earlier trace reports retain their original
scope; they are not retroactively full-wrapper measurements.

Reproduce locally:

```powershell
.venv\Scripts\python.exe -m tools.probe_player_input --source ..\PoP2-Mac-Code-Recovery --output rendered\native-player-input.json
```

Output digest: `629559d461e4dc95f69855b9c0a8ebb5438d6f39a53685aaef703a19f5a4c17f`.
Executable resource-fork digest remains
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.

Eight asset-free regressions in `tests/test_player_input.py` cover the gate,
modifier release, pending versus consumed directions, mode reset, countdown
independence and recording-return word. They run alongside the action and
composed-trace tests in CI. No additional gameplay behavior is changed by
this research block.
