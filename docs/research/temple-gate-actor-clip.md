# Temple Gate Actor Clip Progression

Research only, continuing the [type4 hanging gate proof](temple-gate-hanging-animation.md)
on baseline `ba683c2`. No game runtime, scenery or save changes.

## Findings

The distinction between selecting a sequence and executing it matters here:

- Native StopGate `5:14a8` can select SEQS47 and copy the actor back, but its
  mode, pose, X, Y and health do not change at that point.
- The first subsequent AnimChar `4:2c0c` executes mode5 and relative X-16.
  StopGate admits facing-1, so this moves native X **+16**, with signed-word
  wrapping, before showing pose50. It does not change Y, ALIVE, life or
  pending damage in this bounded clip-only execution.
- The next two calls show poses51 and52. The fourth follows the link to
  SEQS2, sets mode0 and shows pose15 in the same call. Idle then repeats.
- A sequence link changes active word+38/cursor+36, but retains selected
  source+40 as47. This is not a new JumpSeq selection.
- Wrong-facing and supplied missing-resource controls retain the existing
  hanging clip9; it links to210 and remains mode2 over the eight calls tested.
  Fast closing and permanent opening do not select47 in these controls.

Thus this proves an animation-state transition, **not a physical fall**.
GenCtrl, support/collision, actor movement and the complete FrameAdv order
are not executed. Do not translate the clip alone into a guessed fall timer.

## Evidence

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_gate_actor_clip --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_gate_actor_clip_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_gate_actor_clip_reference
```

**2,952 persistent traces, 73,800 native/reference comparisons, zero
mismatches**, across all41 header-admitted original temple gate anchors.
Each trace runs the real type4 gate body, then eight supplied actor updates;
each update compares LoadKid, AnimChar and copyback separately. Controls:
slow close3/phase1, fast close60/phase4, permanent open180/phase3, facing-1/0,
saved actor room0/matching room, resource present/missing, and three X values
including signed wrapping boundaries. These placements are supplied controls,
not proof that each hanging state is reachable at every gate.

246 traces select47; 2,706 retain clip9. There are738 mode5/active47 results
and1,230 mode0/active2 results after selection. All62 working/saved actor
bytes, event ordering, complete level data, gate scratch, ReadCell cache,
160-byte TROB-bank canaries and the relief countdown are compared at every
operation. Original SEQS bytes and prepared handles must remain unchanged.
Nine asset-free regressions cover selection/execution separation, poses,
mode/X, source preservation, handle order, canaries and decoder exclusions.

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Compared-output SHA256:
`35ff029497d98182fdd8aaa70b1f5063761392a64cc1cedb30786cfe8e25d403`.
The ignored report also records the four LEVL and four SEQS hashes.

## Native And Supplied Boundaries

Native bodies include type4 dispatch/gate motion, StopGate, LoadKid,
JumpSeq47, AnimChar, GetSeqOp, relative-X arithmetic and the gate's actor
copyback. Original SEQS2/9/47/210 bytes are loaded from preserved resources.
The independent reference interpreter covers only positive poses and
opcodes-7/-5/-1 used in this finite corpus; it rejects unsupported opcodes,
missing links and context-dependent link11 rather than guessing.

Supplied endpoints: gate sound5:3828, redraw5:0fe6, audio5:4d84,
resource existence17:330e, hGetSequence4:3098 returning prepared handles,
and HGetState/HLock/HSetState with supplied state0. There is no native
Resource/Memory Manager or sound/pixel proof.

After each animation call the harness explicitly executes the **inline**
copy fragment5:1516-1526 and stops before5:1528's StopGate epilogue. This
fragment is not a standalone SaveKid function. Its reuse and the eight
LoadKid/AnimChar/copyback iterations are supplied scheduling, not evidence
that the original frame coordinator follows that sequence at that site.
Full TROB iteration/compaction, physical falling/contact/death, complete
FrameAdv, saves/reset and playable temple integration remain open.
