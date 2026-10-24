# Temple PlayerCtrl Inside The World Caller

Research only, connecting [world/Prince callers](temple-world-prince.md) and
[hanging controls](temple-hanging-control.md). No runtime or playable temple
changes. The earlier [input audit](../INPUT_RECOVERY.md) already records the
static latch rules; this block executes their bounded native composition.

**Naming correction:** references to the supplied `bars`/`10:2036` query
mean SlideRockInCell, a sliding-rock occupancy query, not bars. That legacy
fixture name does not change the old comparison digest. The follow-up
[geometry proof](temple-controller-geometry.md) executes its actual body.

## Connected Behavior

Actual world `2:6224` and Prince `2:62e6` now call real PlayerCtrl `4:3b88`,
including preparation `4:3cae`, normalization `4:3e84`, orientation `4:3d96`,
GenCtrl `6:0560`, native hanging/climb/release/preview and the final actor
save `2:6472`. PlayerCtrl is no longer a supplied return/mode sink in this
experiment. Only raw input polling remains supplied at that boundary.

- Preparation restores all five saved latches before sampling; unrelated
  working-latch canaries do not become input. Directional and modifier latch
  normalization follows the existing audit, including consumed values and
  negative pending directions surviving a contrary sample.
- Hanging climb tests Up for nonzero, not only a fresh negative request.
  A consumed Up1 can therefore still admit this branch. Do not generalize
  a fresh-press-only policy from other controller gates to hanging climb.
- The cooldown word is decremented before GenCtrl. Input1 becomes0 and can
  allow climbing in that same update; input2 remains1 and blocks it. Negative
  values also decrement with word wrapping, rather than being clamped to0.
- The active-control guard can zero the two sampled directions without
  clearing the sampled modifier or pending negative directional latches.
  The corpus checks mismatching context words, room0 and selected source59.
- Facing0 swaps horizontal latches and negates the sampled horizontal axis
  around GenCtrl. Vertical inversion similarly swaps Up/Down. Both transforms
  are undone before saving the resulting consumed/reset keyboard latch bank.
  A global Up input therefore need not request a climb when vertically inverted.
- The actual caller keeps the ordering gate-bank -> PlayerCtrl -> AnimChar ->
  physics/contact requests -> Prince save. GenCtrl can retain gate-selected47
  or replace it before the ordinary animation.
- Animation suppression still executes PlayerCtrl, its sequence changes and
  latch save. It suppresses the later ordinary AnimChar, not input processing.
- With both-space release responses, DoJumpHang's preview can retain47's
  X/mode/pose changes. Selection99 and the subsequent ordinary first frame
  then reach the real Prince save with those effects intact.
- Room0 still prepares/saves controls before the supplied outside-fall helper
  and immediate Prince save, without the ordinary animation/contact chain.

HP, ALIVE and death-counter words are kept distinct. These fixtures use HP3,
ALIVE-1 and death-counter-1; the later death/retry branches of PlayerCtrl are
not exercised or inferred from that living path.

## Reproducer And Validation

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_player_control --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_player_control_v2.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_player_control_reference
```

**7,090 native/reference world-update comparisons, zero mismatches.**
The all-anchor portion has4,920 fixtures; sampled-latch controls add1,728,
gate/controller response controls432, room0 controls8 and source59 controls2.
Sixteen real DoJumpHang preview calls occur within the actual coordinator.

The corpus uses all41 header-admitted original temple gate anchors across
three position/phase pairs, two facings, vertical inversion on/off and ten
input patterns. Additional fixtures vary sampled axes/modifiers, previous
latch states, cooldowns, cell/bars responses, room0 and selected source59.
Each fixture executes one complete world-coordinator call, not a multi-frame
reachable gameplay trace. Original kind2/opponent-set7 headers are checked.

Comparisons include full level data, both62-byte actors, TROB count/records/
storage/scratch, object scratch, return word, ordered events/service counts,
both latch banks, sampled axes, cooldown, cell cache, countdown, saved edges,
view and exit flag. MOB scratch/count, pending effects, inversion/demo flags
and the inactive demo handle are canaries. Original sequences and prepared
handles are read-only. Sixteen asset-free tests reject wrong order, latch-bank
selection, orientation, cooldown timing, lost preview effects and unsupported
dead-controller inputs.

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Compared-output SHA256:
`b0a1021d7400e6128ae30a612b9291056b9cabbb867af27fc76cd34a6eb3f3a6`.
Original resource hashes, input fields and the complete supplied-service list
remain in the ignored JSON report. No original resource bytes are committed.

## Explicit Boundaries

Native execution includes the existing gate-bank/clip/gravity/save bodies and
real PlayerCtrl's living hanging path, control preparation/restore/save,
normalization, horizontal/vertical transforms, hanging/climb/release/preview,
ClearControls, tile predicates and inactive-demo result helper `5:6072`.

Supplied endpoints remain:

- `2:55d2`: writes three sampled raw axis/modifier words; no keyboard,
  device polling, event loop or native sampling priority is executed.
- `4:35a6/3a48/3ff8`: current/front/above kinds and above foreground. These
  values do not come from actual actor/room geometry in this composition.
- `10:2036`: bars-query result.
- All non-control world/Prince services listed in the tool's `ENDPOINTS`:
  rubble/generators/opponents, frame/sword/edges, barriers/collision/gates/
  floor/pressure/hazards, environment/effects/cuts/clock/timeout.
- `5:3828/0fe6/4d84`: cue/redraw/audio requests; `17:330e` and `4:3098`:
  prepared original sequence handles; state0 Memory Manager handle traps.

Demo playback/recording is inactive, with a null handle and override flag0.
The actual `5:6072` guard returns-2; active demo controls, missing resources,
death registration/continuation and other GenCtrl routes remain excluded.
Initial actor state, prior latch state, gate phases, input samples, inversion
and cell/bars responses are deliberately supplied, not demonstrated reachable.

The independent world reference accepts an optional controller callback to
reuse its already-tested ordering/physics model without duplicating it. The
default supplied-controller corpus is unchanged. Neither model uses the
port's gameplay input/controller implementation as its oracle.

Next useful work: replace the three cell-query sinks and bars query with real
ReadCell/temple geometry in this actual caller, then extend persistent actor
progression beyond the first hanging decision. This does not establish outer
FrameAdv, physical support/fall/contact/death, real rendering/audio, save/reset
or playable temple integration.
