# Vertical-jump input handoff

This fourth runtime stage extends the existing directional bank through vertical
jump14/28 and landing11. It reuses the recovered sampler, GenCtrl and action
prefixes; it does not redo their earlier matrices or claim full native physics.

## Observable correction

On the actual flat platform in level6 room8, supplied valid vertical takeoffs
previously left directional callbacks using the old single pending command.
Early released taps survived the protected landing, and the last of two late
taps replaced the earlier one. Both effects disagree with recovered routing.

| Inputs during either vertical jump, both facings | Original routing | Host before | Host after |
| --- | --- | --- | --- |
| Up then Down at75/76, released before83 | None | Down | None |
| Down then Up at75/76, released before83 | None | Up | None |
| Up then Down at84/85 | Up | Down | Up |
| Down then Up at84/85 | Up | Up | Up |

The unchanged routing/action evidence establishes the implementation:

- DoJumpUp6:1608-160c clears the four directions and consumes Up, preserving
  the modifier. The rest of its geometry remains the existing terrain code.
- GenCtrl6:064c-0660 ->6:15de accepts **active** Forward at displayed67-69,
  including a consumed hold. It calls forward jump6:15ea, which consumes
  Forward/Up. A new Up press is not required. Forward after69 waits instead.
- GenCtrl6:0576-059c clears directions in protected modes4/5/9. The actual
  landing SEQS11 enters mode5 at83, then returns to mode1 at84/85. Late taps
  after that clear reach the ordinary ready selector, which prioritizes Up.

`AirborneControls` retains the bank through14/28 ->11 ->ground. Its takeoff
set is distinct from its ownership set: linking/selecting landing11 does not
consume another Up or erase valid late input. The first-pose guard prevents
the previous displayed15 from being dispatched before the new arc loads67.
Callbacks in the owned family no longer populate an executable pending slot.
There is no new timeout or second directional queue.

The early Forward gate can convert to SEQS3, whose existing bank ownership
and reset26 then apply. Ordinary held-jump repeat/cancellation, the rapid-jump
filter, startup chords and the explicit wall-climb tolerance remain. Shift/Ctrl
normalization and the upside-down physical mapping are unchanged.

## Evidence and scope

`tools/audit_vertical_handoff.py` executes two separate experiments:

- Sixteen hidden host scenes using actual scenery/SEQS/terrain and callbacks:
  jump14/28, both facings, early/late windows and both tap orders. Each key
  is held across one animation tick and released before the next key. The
  fixture supplies the already-selected valid takeoff, not its geometry
  admission. All remain on the intended room8 platform, alive and not falling.
- 112 persistent original sample4:3e84 + player/remap4:3d96 + GenCtrl6:0560
  steps against the separate `reference_input_bank/routes` model. Poses,
  modes, sequences, raw axes, living unarmed player and level6 room8 are
  supplied. Up/Down/cell/pickup services are explicit sinks. All112 match.

Native execution has no animation/physics/FrameAdv, emulator or OS key polling.
The native ready15 is a supplied routing observation; it is not evidence that
both games display the same ready frame or run synchronized clocks. The host
can select an action before displaying that idle. The native14 terminal mode
differs from28 before landing; this fixture supplies the common routing modes
for those non-dispatching poses. Original SEQS modes are used by the host.
No whole-game queue parity or native ledge/terrain action admission is claimed.

```powershell
.venv\Scripts\python.exe -m tools.audit_vertical_handoff --source ..\PoP2-Mac-Code-Recovery --output rendered/input-queue-audit/vertical-after.json
```

Before migration: 12 host differences in16 cases. After: zero differences.
Original executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Before report SHA256:
`f2d4543254362da3095380c057186231325438f261a1357bb1cffcd2720a3957`.
After report SHA256:
`8b056258a5749946d89672c02caa1abee03ed91305aad746ed05d126c006dcc1`.
The original file is read only and verified unchanged after execution.

`tests/test_vertical_controls.py` additionally compares the production early/
protected selector with the independent existing route model in4,860 cases.
Runtime tests cover the two arcs, both facings, early/late direction windows,
takeoff and modifier-preserving landing clears, cancellation of automatic
repeat and inverted physical input. The inverted fixture keeps the actual
potion timer active and asserts the logical held key after every callback.
The selector test is also included in asset-free GitHub CI.

## Boundary with ledges and next stage

Historical boundary for this fourth stage: the subsequent
[ledge migration](ledge-input-handoff.md) now transfers the same bank into
native24 and through hanging/release/climb. The two terrain regressions retain
their67-69 pose checks and now assert that new ownership instead of retirement.
The remaining text records the boundary before that fifth stage.

Real level3 ledge entries in both facings select24 and retire the bank before
their first67-69 poses. They must not be mistaken for ordinary14/28 just
because the pose numbers coincide. Two actual terrain fixtures verify this
boundary; existing wall-climb/release/pause scenarios still pass.

Native ledge24/15/9/210/25, release and climb ownership remains a separate
migration. Reuse GenCtrl6:18e0-1994, climb6:1998 onward and release6:1a84
along with the existing terrain recovery. The next bounded audit should
exercise the grip-delay/Up-before-release/modifier/mode11 gate and actual
climb/release consumption, with supplied terrain services clearly separated.
Then transfer bank ownership through the climb and remove its legacy callbacks
together. Current host wall/climb input tolerances must remain explicit;
the protected native mode5 clear must not silently erase those extensions.

## Validation of this stage

- The initial regressions rejected the prior runtime in34 subcases, including
  early/late tap orders, early Forward admission and the protected reset.
  All eight final vertical tests pass, including the real ledge boundaries.
- The focused terrain/UI/ceiling/ledge/playtest run passed242 tests in123.871s.
- Full shared-desktop discovery ran3,244 tests in547.286s, with ten explicit
  skips and four failures belonging to one old waiting-controls assertion.
  It expected the bank to disappear on vertical takeoff. The corrected test
  keeps the same28/67 animation expectation and verifies the actual takeoff
  bank `(0, 0, 1, 0, 1)`: consumed Up, cleared Down, retained consumed Shift.
  The raw full run is not reported as green. No production code changed
  during/after it; the final199 affected input/animation/playtest/wall tests
  passed in11.413s after this fixture-only correction, without repeating
  the full importer. This run also uses the strengthened inverted fixture.
- Asset-free CI selection, Ruff F/E9, dependency check, recovery catalog and
  whitespace checks pass. Original resources and save formats are unchanged.
  All scenes used hidden isolated fixtures; no live game/emulator, physical
  keyboard focus or real user saves/settings were operated.
