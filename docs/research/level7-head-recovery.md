# Head Peaceful And Attack-Recovery States

Research only; no runtime integration. `R` means recovered/reference behavior.

| Rule | Source | Status |
| --- | --- | --- |
| Return to peaceful state | 7:1012-1064 | R: full leaf with native motion/sequence/floor helpers |
| Finish attack according to cached native ALIVE | 7:0b16-0b54 | R: full leaf, threshold controls and selected-166 preservation |
| Rejected-target routing into actual recovery | 7:1324-1452 | R: supplied rejection cases, real leaf/record lookup/bank save, bounds supplied |

## Reproduction And Result

```powershell
python -m tools.probe_level7_head_recovery --source PATH_TO_RECOVERY --output rendered/level7-native-head-recovery.json
python -m unittest -q tests.test_level7_head_recovery_reference
```

Original executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
The ignored JSON records resource hashes/output digest and supplied endpoints.

Across the eight actual head-family slots of LEVL 2006, the native probe checks:

- 3,456 direct peaceful calls, varying actor pose/facing/X/row and record mode.
- 7,776 direct done-attacking calls, varying selected sequence and cached
  native ALIVE around the threshold, as well as pose/facing/X/row.
- 1,728 wrapper calls in modes 1/3, with target rejection via zero +0x1e,
  or selected sequence 70 with target pose 0/223. These execute real record
  lookup, derive the actual mode pointer, run the recovery leaf, save the
  working actor bank and restore the unchanged Prince snapshot.

All 12,960 comparisons pass. The 8,208 peaceful transitions in the report
are a subset of these cases, not an additional case count. Checks cover
all 62 working bytes, declared scratch remainder, frame/attachment bytes,
full level bytes, resource/reload requests, unchanged cached target and,
in wrapper cases, the saved working bank and restored Prince bytes.
Seven asset-free tests exercise the reference, not the native executable.

## Peaceful Transition

HeadGetPeaceful receives a POINTER to the generator record's +0x1c mode
word. It sets that word to zero. It does not serialize the entire working
actor back to the 38-byte generator record; the record's sequence/cursor
remain unchanged during this isolated operation.

The leaf clears armed state, both working velocity words and field
A5-0x5024 (called `alert` in the probe, without certifying its full lifecycle).
It requests SEQS 139 through the original JumpSeq. The facing/12-pixel
normalization described in [sequence selection](level7-sequence-selection.md)
therefore happens BEFORE final cell alignment.

Using the current pose's frame metadata, it recalculates the supporting
column/remainder and sets native working X to `207 + column * 51 + 47`.
SetCharFloor then sets working Y to `row * 120 + 73` for types 7/8,
including the original -33 head offset. This is not an animation tick:
pose is unchanged, and the frame/remainder are not recomputed after the snap.
The leaf by itself does not clear working special field A5-0x5022.

## Done-Attacking Transition

The input at A5-0x5078 is cached opponent/Prince struct +0x1c, the native
ALIVE word, NOT HP and NOT generator mode +0x1c. Those offsets belong to
different structures and must not be conflated.

- Cached ALIVE >=6: call HeadGetPeaceful, clearing generator mode as above.
- Cached ALIVE <6 and selected sequence !=166: SetCharFloor, then JumpSeq166.
  This preserves armed state, velocities and the alert field. JumpSeq may
  normalize facing/X and reload supporting metadata as established separately.
- Cached ALIVE <6 and selected sequence already166: do NOT restart the
  sequence, clear its cursor, snap to the floor or change position/facing.
- In every branch, clear working special field A5-0x5022.

The threshold probes use -1/0/5/6/7/20 directly. They establish the branch,
not the scheduler/death producer that makes those values occur over time.
Do not substitute `not target.alive` or `target.hp == 0` for this comparison.

## Supplied Endpoints And Remaining Gaps

17:330e GetResource supplies only actual Prince SEQS existence, as in the
selection probe. No SEQS interpretation/resource loading is performed.
In additional wrapper checks ONLY, 4:5cbc shape-bound calculation is inert;
the rejection branches tested do not consume its geometry. Other AI leaves
are NOT silently stubbed: execution outside declared ranges fails the probe.

Working states, cached target states, record modes and initial resource
handles are supplied. Direct leaf calls receive a supplied mode pointer;
the additional wrapper cases verify native pointer derivation independently.
No actual death timing, all-state reachability, LOS/attack/locked routes,
animation, collision, pixels, campaign integration or complete AI claim.
Native SaveShad in the wrapper is a working-bank save, not proof of full
persistent generator serialization or offscreen lifecycle.
