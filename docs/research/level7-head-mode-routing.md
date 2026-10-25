# Ruins Head Mode Routing

Original head-controller wrapper 7:1324, separate from its AI leaf bodies.
This is research tooling, not a live gameplay implementation.

```powershell
python -m tools.probe_level7_head_routing --source PATH_TO_RECOVERY --output rendered/level7-native-head-routing.json
python -m unittest -q tests.test_level7_head_route_reference
```

## Native Boundary

The original wrapper, GetOppInfoIdx 6:3642, cached-Prince copy 4:3272,
LoadFrame 4:2a8e (actual Head FRAM/AFRM), working-bank save 4:4a46 and
opponent-cache restoration 4:338e all execute natively. The probe checks
that inert leaves leave the level records and cached Prince unchanged.

Explicit supplied boundaries:

- Shape bounds 4:5cbc returns without computing geometry.
- CharCanSeeOpp 7:00f8 returns the supplied value -1, 0 or 4. This is not
  an independent sight-path/obstacle test.
- Idle/angry/attack/done/flee/locked leaf entries record a call and return
  without applying their effects. No mode transition inside a leaf is claimed.
- Working fields, record mode and cached-Prince fields are fixture inputs.

Results: 20,160 routing combinations across all eight original head slots,
plus 24 nonnegative-ALIVE controls and 32 missing-record controls; zero
differences against the isolated routing reference. Six asset-free unit tests
check that reference's thresholds without claiming native execution.

## Recovered Dispatch

The wrapper rejects native ALIVE >=0 and missing records before loading
frames or asking a leaf to run. Its mode is the generator's +0x1c word,
not the working actor's animation state.

For target admission, it requires the cached opponent word +0x1e to be
nonzero. It also vetoes selected sequence 70 when the cached pose is zero
or >=223. Keep these exact fields until their producer/lifecycle has been
traced; do not replace the test with a generic `Fighter.alive` predicate.

| Record Mode | Original Requested Leaf |
| --- | --- |
| 0 | Angry 7:0f88 only if target admitted, own pose is 150/159/165/166/173, and CharCanSeeOpp != -1; otherwise idle 7:1268 |
| 1 | Attack 7:064c if target admitted; otherwise done 7:0b16 |
| 2 | Flee helper 7:0cae, independent of target admission |
| 3 | Locked 7:1164 if target admitted; otherwise done 7:0b16 |
| Other | No leaf request |

Visibility result 0 is accepted: this is a multi-valued result where only
-1 rejects, not a Boolean. Mode 2 does not fall through the live-target gate.
The idle leaf starts at 7:1268; the jump-table entry two bytes before it is
an RTS, another reason not to infer function bounds from markers alone.

## Exclusions

No leaf effects, target-field lifecycle, actual sight/bounds calculation,
flight/collision, neck attachment, damage, animation cadence, persistence or
full AI equivalence is established. The original wrapper runs with inert
leaves; continuing it through a real leaf may change both generator and
cached-Prince state. Those effects require separate probes.
