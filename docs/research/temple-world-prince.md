# Temple World And Prince Caller

Research only, continuing [gate-bank/actor progression](temple-gate-actor-bank.md).
No runtime, input policy, artwork or playable level changes.

## Connected Findings

The harness now executes the actual world coordinator `2:6224` and Prince
coordinator `2:62e6`, including the real actor save at `2:6472`. This replaces
the previous supplied scheduling and stopped inline-copy fragment with the
original caller for this bounded experiment. It agrees with the already
recorded [static frame-order reading](frame-phase-order.md): gate-bank work
precedes the Prince controller and animation in the ordinary world update.

- Live world work runs rubble, the real AnimTrobs bank, optional special
  actor work, generators and nearest-side selection before the Prince.
- The room0 Prince path calls supplied controls/outside-fall handling and
  saves immediately. It bypasses ordinary animation, countdown and edge save.
- Control result-1 or non-live state skips ordinary animation and contact
  work. Animation suppression returns1 from the Prince path instead of
  executing the clip. A positive controller result alone does not suppress
  animation: the ordinary completed Prince path returns0.
- Ordinary actor work executes real AnimChar, gravity `4:341a`, vertical
  movement `4:3464`, then the ordered geometry/contact service calls. A
  mode4 mutation supplied at the controller boundary therefore moves before
  those calls. This is not evidence that real controls choose that mutation.
- Invulnerability skips the two hit services, not pressure, spikes or
  scythe-start calls. Opponent strikes are also guarded in the world caller.
- Countdown `2:640c` consults the saved actor's ALIVE/mode before the final
  copy, not the newly animated working mode. Supplied nonnegative countdowns
  are branch controls, not a claim of their ordinary temple reachability.
- A nonzero Prince result takes the short presentation path; normal result0
  executes the longer opponent/effect/cut/clock path. Supplied prepare-cut
  results and time-zero controls distinguish the return and timeout branches.

Gravity controls separately confirm signed velocities, the ordinary63 and
floating8 caps, arithmetic halving of negative horizontal speed, and the
Y3650 movement guard. Gravity changes velocity even when that guard prevents
movement. Modes outside4/9 do not accelerate, but vertical movement can still
apply an existing speed.

## Evidence

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_world_prince --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_world_prince_v2.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_world_prince_reference
```

**8,528 persistent traces / 34,112 world-update comparisons, zero mismatches.**
All41 header-admitted original temple gates, four position/phase inputs,
13 caller controls, saved actor room0/matching and single/full20 banks are
covered. Each trace advances four times without replacing its evolved actor
or bank. Original temple kind2/opponent-set7 headers and original sequence
resources2/9/47/210 are checked.

**2,400 additional direct gravity/movement comparisons, zero mismatches.**
Five modes, three horizontal speeds, eight vertical speeds, five Y values,
two facings and floating on/off bound those helper branches independently.
These are helper cases, not additional world frames.

Comparisons include complete level data, both62-byte actor records, TROB
count/storage/scratch, object scratch, ordered calls, saved edges, countdown,
view, exit flag and returned word. ReadCell cache, MOB scratch/count and
pending effects are canaries. Prepared sequence bytes/handles remain read-only.
Twelve asset-free tests reject reordered/omitted work and wrong suppression,
room0, countdown, clock and gravity behavior.

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
World compared-output SHA256:
`75737f3baa4f97c2baf43bb45e61aadd6c7d8af98ac61386cfb6768bd0e69fb8`.
Gravity compared-output SHA256:
`5377ac8006d81ab4fa4ae741a38caf0bbc8e25e4b47db1fcbb3086bfd05abf24`.
Input/resource hashes and the complete supplied-address list are in the
ignored JSON report and the tool's `ENDPOINTS` table.

## Boundaries And Next Step

PlayerCtrl `4:3b88` supplies a result and optional mode mutation. Nearest/
opponent work, LoadFrame/sword/edges, barrier/collision/gate/floor/pressure,
hazards, rubble/generators, effects, cut/clock/timeout and rendering are
request/result sinks at their documented addresses, not their native bodies.
Sound/redraw endpoints `5:3828/0fe6/4d84`, resource existence `17:330e`,
prepared sequence handles `4:3098` and state0 Memory Manager traps remain
supplied. Level, actor placement, input flags and gate/bank state are fixtures.

This does not execute the outer FrameAdv `2:60fc` timer/input loop, real
PlayerCtrl/GenCtrl, physical geometry/contact/fall/death, actual clock/cuts,
reachable placement, audio/pixels, save/reset or playable temple integration.
The next bounded connection is the real hanging control branch between
gate selection and AnimChar, which can replace that selected sequence.
