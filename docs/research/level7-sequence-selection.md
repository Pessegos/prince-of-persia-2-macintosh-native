# Head Sequence Selection

Research only, branch `codex/level7-preparation`. No runtime change.
`R` below means recovered/reference logic, not integrated gameplay.

| Rule | Source | Status |
| --- | --- | --- |
| Existing SEQS selection and missing-resource rejection | 6:0006-0098 | R: supplied actors 7/8/11, resource-existence service supplied |
| Head facing normalization and 12-pixel correction | 6:003e-0090; 4:2bae | R: both head types, boundary sequences and poses |
| Frame reload and supporting-cell recalculation | 4:2a72; 4:3a72/3ad6; 5:48b0 | R: real Head frame metadata, explicit coordinate domain |

## Evidence And Reproduction

```powershell
python -m tools.probe_level7_sequence_selection --source PATH_TO_RECOVERY --output rendered/level7-native-sequence-selection.json
python -m unittest -q tests.test_level7_sequence_selection_reference
```

The probe executes full original JumpSeq and its frame/coordinate helpers.
GetResource 17:330e is supplied: the result is non-null exactly when the ID
exists in the original Prince.rsrc SEQS bank. JumpSeq only tests this handle
for null, without dereferencing it. The fake handle is not animation data.
Head FRAM/AFRM handles contain the actual resources; LoadFrame is native.

There are 7,296 supplied selection cases: actors 7/8/11; poses
149/150/151/158/159/160/181/182; facings -1/0; eight X coordinates including
negative/edge controls; and 19 requested IDs. There are zero differences.
Of these, 1,408 reload the frame and 768 reject a missing resource (IDs 167
and 32000). Another 16 direct supporting-column boundary controls pass.
The probe compares all 62 working bytes, the declared column remainder,
frame/attachment bytes, lookup/reload calls and unchanged full level bytes.

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
The ignored JSON also records Prince/Head resource hashes and output digest.
Eight asset-free unit tests check the research reference, not independent
native equivalence.

## Recovered Behavior

Missing SEQS leaves the actor unchanged. Existing SEQS sets current sequence
and selected sequence to the requested ID and resets the cursor to zero.

Only actor types 7/8 have the extra normalization, and only for sequences
130 through 139 inclusive or sequence 166. If facing is already nonzero,
there is no normalization/reload. Facing zero becomes -1; poses 150 and 159
also subtract 12 from native working X. Other supplied poses turn without
that displacement. Type 11 does not use the head correction.

The sign matters: AddCharX receives +12 AFTER facing becomes -1, so its
direction-relative operation moves native X LEFT by 12, not right by 12.
The subsequent reload uses the existing pose, not the first pose of the
new sequence. It reloads FRAM/AFRM and recalculates the supporting column
and division remainder. Animation has not advanced at this point.

Supporting-foot displacement uses FRAM dx minus the low six flag bits,
with the actor's facing sign. The head-specific frame remap is still the
one described in [frame loading](level7-frame-loading.md).

### Narrow Native Arithmetic Edge

5:48b0 sign-extends the input coordinate BEFORE subtracting four from its
low word. A coordinate of 0..3 therefore wraps the low word without
re-extending it. For a supplied foot X of 22 (after the caller's -22),
the native result is column 1280, remainder 48. Foot X 21 instead produces
column -5, remainder -5. The reference preserves this instruction order.

These are supplied low-coordinate controls, not proof that these states
are reachable in a valid live actor. This observation is NOT a request to
remove the port's capacity/collision safeguards or introduce unsafe indices.

## Limits And Next Step

No SEQS interpretation, pose reachability, resource-manager lifecycle,
animation cadence, actor-1 pre-hook, collision, drawing or AI parity claim.
Inputs deliberately include serpent/head combinations not certified reachable.
The full original HeadGetPeaceful is the next bounded consumer: it requests
139, clears movement/armed state and snaps the head to the cell/floor.
