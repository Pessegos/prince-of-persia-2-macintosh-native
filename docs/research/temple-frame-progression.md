# Temple Frames Inside World Control And Bounded Clip Progression

Research only, building on [Kid frame support](temple-kid-frames.md) and
[controller geometry](temple-controller-geometry.md). No runtime changes.

## Actual Caller Composition

The actual world2:6224/Prince2:62e6/PlayerCtrl4:3b88 chain now executes
type0 LoadFrame4:2a72 instead of supplying it. Both loads around ordinary
animation read original Kid FRAM25001/AFRM25001, update the supporting column
and preserve the full18-byte metadata. Current/front/above ReadCell/cache
and SlideRockInCell also execute their original bodies. Gate decisions in
AnimTrobs still precede the Prince update and use the saved actor.

Across all41 original temple gates (levels10..13), three gate-position/phase
pairs, two facings, three sampled input combinations and three anchor offsets,
**2,214 actual world calls** match the independent reference. The changed
column reaches the controller's cell queries before GenCtrl, and the final
Prince save includes post-animation frame effects.

## Persistent Helper Continuation

After each actual world call, separately scheduled native AnimChar4:2c0c and
LoadFrame pairs retain the working actor and other memory. This deliberately
does **not** run another world call, copy working actor back to the saved
Prince, resample inputs or simulate support/contact/gravity between pairs.
It is a bounded animation proof, not physically reachable climbing/falling.

- Source10: six additional pairs reach pose141, relative X23, Y-120 and row--.
  Row decrement (`-3`,4:3030) has **no operand**; relative Y (`-6`,4:2d6e) does.
  The next link235 is excluded.
- Sources23/99: two additional pairs cover Y+11 then Y+17. The later `-8`
  command and following controller/physics dependencies remain excluded.
- Source47: eight pairs include its ordinary link to idle2 without replacing
  the selected source47. Source9 continues into prepared clip210.
- Sources25/73/11 stop before their unbounded commands/context-dependent
  links. Exact per-source horizons are recorded in the probe/report.

There are **10,875 AnimChar plus10,875 LoadFrame comparisons** after the
world calls: **23,964 operation comparisons total, zero mismatches**.
Observed changes:554 supporting columns,492 scripted rows and1,554 scripted
Y values. These are operation counts, not unique reachable game states.

Full level/TROB banks, both actor records, cell cache, latch banks, sampled
axes, cooldown, frame width, division remainder, metadata, empty MOB storage,
scratch/flags and ordered events/service counts are compared after every
operation. Original sequence/frame bytes and prepared handles remain unchanged.
Only the real world return is checked; helper return registers are not modeled
as additional world results.

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_frame_progression --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_frame_progression_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_frame_progression_reference
```

Compared-output SHA256:
`cadb215c6c3644c1722027b925cdbf465f37fe3c56e2e5e904a506f73666c98d`.
Executable/frame/attachment/sequence hashes and supplied service addresses
are listed in the ignored report. Nine asset-free regressions cover frame
ordering, stale-column replacement, saved-versus-working actors, X/Y/row
commands, wrapping, ordinary links and explicit excluded boundaries.

## Remaining Boundaries

GetCharEdges/sprite width (supplied18), other contacts/hazards/floor/pressure,
opponents, external services, prepared resource bindings and sampled axes
remain supplied. The MOB bank is empty here; occupied-bank geometry belongs
to the earlier separate proof. Initial X/Y/row and saved column are fixtures.
Only normal AFRM25001 is connected here, not story-driven attachment binding.
Full FrameAdv scheduling, physical support and complete climb/drop collision,
all animation opcodes, rendering, saves and playable temple remain unproved.
