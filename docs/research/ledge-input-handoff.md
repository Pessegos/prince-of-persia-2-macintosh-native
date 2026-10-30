# Hanging and climbing input handoff

The fifth directional-bank runtime stage extends the existing bank through
native ledge entry, hanging, release and protected climbing. It follows the
standing/step, running, forward-jump and [vertical-jump](vertical-input-handoff.md)
stages. Low/prone, armed and other special controllers still need migration.

## Original gate and consumption

CODE6:18e0-191e checks these conditions in order:

1. Native ALIVE is nonnegative: release. This is not an HP test.
2. Grip delay is zero and Up is active, negative or positive: climb.
3. Modifier is zero, or sequence mode is11: release.
4. Otherwise continue to the separate terrain/support decisions at1920-1994.

Up therefore takes priority over releasing the modifier, once grip delay
has expired. Ctrl and Shift share the native modifier word; positive consumed
modifier values also keep the hold. The runtime uses the existing boolean
`native_alive` representation when supplied, with its existing living-state
fallback when absent. It does not introduce a new HP/death state machine.

The climb prefix at1998-19d4 reaches ClearControls4:3e3a at19c8, then consumes
Up and modifier as1. The release prefix at1a84-1a92 clears directions and
consumes Down as1 while retaining the modifier. Geometry and action bodies
continue to use the existing terrain/climb implementation. Grip decrement
scheduling is unchanged; this audit supplies the counter, rather than proving
the complete native FrameAdv order.

## Runtime ownership and deliberate port policies

`pop2/ledge_controls.py` carries the same `DirectionalInput` through the
`native_ledge` lifecycle, including protected climbing and its grounded tail.
The flag distinguishes native ledge24's67-69 poses from ordinary vertical
preparation. Entry does not replay the interrupted jump. A fall catch keeps
a fresh Up pressed at the fall's mode-3 poses (native, see INPUT_RECOVERY
"Input During Falls"); other pre-catch directions are discarded. Native ledge callbacks now sample this bank instead of
classifying a second executable pending command. Legacy scripted directional
requests are imported once and removed from that slot.

Observable changes include Ctrl maintaining a free-air hang after Shift is
released, a released Up tap waiting for grip delay, and independent late
Up/Down taps using Up priority at the end of climbing. The Ctrl and independent
tap regressions rejected the previous runtime before this migration.

Existing port tolerances remain explicit:

- Complete tapped commands are retained through protected climbing. This
  deliberately differs from clearing every protected-mode input as the native
  controller does; no complete protected-climb timing parity is claimed.
- If Up from the climb overlaps a horizontal press, then Up is released while
  only the arrow remains held, the completed climb continues horizontally.
  A fully released new jump chord remains a jump request in the same bank.
- Automatic held-Up repeat waits until the completion pose has been rendered;
  releasing Up before the next tick cancels it. A fresh tap can dispatch at
  completion. A small repeat-policy marker distinguishes these cases without
  holding another directional command.
- Shift + Backward still completes one turn without running out of that turn
  because the preceding climb consumed its modifier. Wall-climb, ship and
  non-native rooftop fallback behavior retain their existing regressions.
- Menu/focus/restart clearing discards the bank, chord and repeat markers.
  Pause retains the already-approved held-key behavior.

No stop-and-draw QoL, pending-input timeout, resource, save-schema or artwork
change is introduced. The public alpha artifact is not rebuilt by this block.

## Independent native comparison

```powershell
.venv\Scripts\python.exe -m tools.probe_ledge_input --source ..\PoP2-Mac-Code-Recovery --output rendered/input-queue-audit/ledge-native.json
```

The probe executes actual M68K gate instructions in360 cases and actual
climb/release consumption prefixes in810 cases against the separate
`tools/reference_ledge_input.py` model. All1170 agree.

- Gate: three Up states, five modifier states, three grip values, living/dead
  native ALIVE, modes0/11 and both facings. Other direction words are supplied
  and remain unchanged.
- Prefix: all405 directional/modifier combinations for both actions. Execution
  stops at19d4/1a92 before terrain lookup.
- Level6 LEVL2005 environment4 and level number6 are checked. During gate
  routing climb/release are sinks; here/wall/ahead/gap/special services return
  zero to supply an ordinary unsupported-cell hold. Those stubs do not verify
  support geometry, blocked climbing or special-level behavior.

Original executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Result SHA256:
`63ce2f63aa5af045e6a9b7b5f778f5c1158f9ca3797712212d76dcd0c432f932`.
The original remains read only and is verified unchanged after execution.

This is not an emulator input replay or full animation/physics/FrameAdv
comparison. Level5's sword-drop branch, ship action bodies, all special
terrain paths and OS sampling timing are excluded. Existing sampler/action
evidence is reused instead of rerunning unrelated matrices.

## Validation and next boundary

The production gate and consumption prefixes are compared against the
independent model in1170 asset-free cases in GitHub CI. Hidden actual-scene
tests cover Ctrl hold, grip-delayed released Up, conflicting released taps,
both native24 entry directions, modal reset and existing complete-chord,
pause, held-repeat, wall-climb and harbor behavior.

The two native24 boundary fixtures now assert a cleared, owned bank through
their unchanged67-69 poses rather than retirement. Older protected-climb
tests inspect the corresponding bank latches instead of `pending_action`;
their animation, geometry and final action assertions remain unchanged.

The first full discovery ran3250 tests in562.838s, with ten skips and five
failures in gate-climb/finger-audio scenarios. This exposed a runtime defect,
not an obsolete test expectation: a wall event could clear the newly adopted
bank on the catch tick, then lazy adoption misclassified the still-held takeoff
Up as a fresh pending tap. Catch entry and lazy ledge adoption now mark that
inherited Up consumed. Releasing it during grip cancels it; a genuinely new
released Up tap remains pending. The gate tests keep their original hang,
failed-climb, successful-climb and finger-audio expectations. Final discovery
is rerun because production behavior changed after that first run.

Before the full-run catch correction, focused input/animation tests passed196
cases in4.704s and actual UI/terrain/cavern/harbor/ruins tests passed273 cases
in170.180s. After the correction, all260 affected input/animation/gate/audio
tests passed in81.808s, retaining the previously failing gate expectations.

Final shared-desktop discovery:3250 tests in540.792s, **OK**, with ten explicit
skips for exclusive-desktop tests. No runtime changes followed that run.
Ruff F/E9, recovery catalog, dependency and whitespace checks pass; the
asset-free CI selection passes locally. Scenes use isolated hidden widgets
and temporary user data. No live game/emulator, physical focus/input or real
user settings/saves were operated. No reimport is needed to use this block.

The next bounded runtime migration is low/prone ownership through crouch,
rise and crawl, using the existing [consumption audit](low-input-consumption.md).
Do not repeat that isolated audit or treat this stage as complete game-wide
queue parity. Armed/special controllers and full scheduling remain separate.
