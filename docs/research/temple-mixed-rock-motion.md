# Temple Mixed Plate/Gate/Rock Motion

Research only, based on `5f19e0a`. This extends the
[persistent mixed gate traces](temple-mixed-lifetime.md) with real sliding-rock
geometry, motion, crush admission, MOB writeback and stable compaction in the
same native CPU/memory. No gameplay/runtime files change.

## Connected Bodies

The two original level11 room3 chains remain unchanged: closing plate cell15
visits gate2 then rock18; opening plate16 visits rock18 then gate2. Real
CheckPress5:127e, ordinary/permanent setup and source timer release feed
AnimTrobs5:0c38 and MakeRubble5:29e8. The latter executes type6 motion10:1d5c
then crush admission10:16f6, real band geometry10:1656, ReadCell/cache and
bank writeback/compaction. Gate motion, LoadKid and relief remain native.

192 persistent traces combine four supplied plans, gate positions0/80, six
initial MOB banks, empty/full TROB banks and two supplied update orders.
The plans cover full forced motion, close/open/close, held/rejected/repress
and permanent opening. Banks cover absent/active/forced/terminal rocks,
30 retained terminal fillers and30 removed terminal fillers. Gate/plate and
rock updates run in both orders; neither order is claimed to be FrameAdv.

The current actor/FRAM inputs are supplied afresh before each operation.
The separate saved Prince is deliberately room0/frame0, excluding both
movement reactions and contact admission. Actor endpoints5:3cee,6:1a84 and
10:1b04 raise immediately if reached; they are NOT simulated successful
reactions. This experiment cannot establish actual damage or actor timing.

## Findings

- Closing pressure can create a forced rock even when the gate is already
  closed or cannot register a TROB. Plate, gate and rock lifetimes are separate.
- A forced rock moves two native X units per admitted motion helper call.
  Source release/rejection does not remove or stop its existing MOB record.
- Opening pressure changes an existing control-2 to2. The ensuing real band
  scans can stop it and clear a matching pending cue192. Closing pressure
  cannot restart terminal control100. These rules now run after actual plate
  admission/link traversal rather than direct injected trigger calls.
- A full retained MOB bank prevents a new rock, not the gate. When removed
  records free slots during MakeRubble, later held pressure can create a rock
  without a fresh source plate animation. Compaction preserves unused tail.
- Motion changes the ReadCell cache. The following real CheckPress reads its
  own source again; it must not use stale rock geometry coordinates/foreground.
  TROB scratch/OS and MOB scratch remain independent and are checked together.

## Evidence

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_mixed_rock_motion --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_mixed_rock_motion_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_mixed_rock_motion_reference
```

**83,040 native/reference operation comparisons, zero mismatches**:
960 CheckPress,41,040 TROB animation and41,040 MOB update calls across192
traces. The compared state includes the entire level, both complete guarded
banks/unused tails, both62-byte actors, pending cue and relief countdown,
pressure flag, MOB/TROB/OS scratch, all ordered calls and ReadCell requests/
cache, plus motion-before-crush ordering. Native MakeRubble's visited count
must equal the pre-update bank length, not the compacted count.

The initial full run records11,920 moving updates,24 LoadKid copies and96
native relief rejections. All192 traces finish with an empty TROB bank;
136 finish with one MOB,32 with30 retained fillers and24 with none.
Thirteen asset-free tests pin linked movement, cache repopulation, source
release, control stop/release, capacity recovery, stable tail preservation,
actor-copy boundaries and excluded reactions/types.

Audio requests/query193 and redraw are supplied endpoints, not playback or
pixel rendering. Loose-floor/trapdoor sinks are guarded and not reached.
All original source resources are read-only; gate/source/timer/capacity
controls alter only the emulated level copy. Executable SHA256 is
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`;
original level11 SHA256 is
`3f3559f2d1dd4853098d9a812692a69a64fd86ac1ae677745f8fea6cdb6f1664`;
compared-output digest is
`d4c3f28a3c19a9f50c244fbed5aa131a5e1567332930fbf5544ec94f006e91f3`.

## Remaining Boundaries

No actual Prince controller/ordinary animation, contact damage/death, hanging
reactions, rock presentation/pixels, audio playback/arbitration, complete
FrameAdv, saves/reset or playable temple integration is established here.
The earlier [contact probe](temple-slide-rock-contact.md) separately covers
bounded native reaction bodies, but they are not silently imported into this
no-contact pressure/motion trace. Next: compose those actor consequences or
rock presentation while retaining explicit scheduling/resource boundaries.
