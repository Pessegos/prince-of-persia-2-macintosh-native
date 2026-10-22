# Ruins Special-Actor Initialization

Independent continuation of [level-seven preparation](level7-preparation.md),
not a runtime implementation. Original addresses are CODE:offset. The probe
reads local original resources only; nothing is imported into a running game.

## Boundary And Commands

```powershell
python -m tools.probe_level7_initialization --source PATH_TO_RECOVERY --output rendered/level7-native-initialization.json
python -m unittest -q tests.test_level7_initialization_reference
```

`HeadAddOpponent` 7:0574 executes completely, including its fallback call
to SetCharFloor 4:31fa. The record pointer is a 32-bit stack argument, not
the 16-bit word arguments used by the previous probes. Native GetCharCol
5:48b0 derives the supplied working column from each original record's X.
AddSound 5:4d84 is the only supplied service: its cue is recorded, not played.

168 cases use the 14 actual level-seven records, each with supplied native
ALIVE -1/0/1 and record +0x1c -1/0/1/3. Three additional kind-zero controls
exercise fallback across all three rows. All record/level bytes, the nine
declared working fields and sound requests match the isolated reference;
zero differences. The requested cue 128 occurs in 24 of the supplied cases.
The actual eight heads / six serpents classification comes from the previous
selector/dispatch probe, not a guess based on the resource filename.

## Record And Working Fields

Do not confuse a 38-byte generator record with the 62-byte working actor.

| Value | Record Offset | Working A5 Offset |
| --- | --- | --- |
| Special kind / actor type | +0x18 (converted through DATA) | -0x504e |
| Animation resource and cursor | +0x08 / +0x0a | Not assigned by this routine |
| Family-specific mode | +0x1c | Not interchangeable with animation mode |
| Native ALIVE | Not interpreted as HP here | -0x503a |
| Armed flag | Not assigned in the record here | -0x503c |
| Special flag | Not assigned in the record here | -0x5022 |

## Original Rules

**Kind-zero fallback, 7:0580-0592.** Set record kind to 5, select working
actor type 7 from the original type table, then call SetCharFloor. For
types 7/8 its native Y is `row * 120 + 106 - 33`, not the ordinary actor's
floor height. These supplied kind-zero controls are not untouched fixtures.

**Head types 7/8, 7:05f6-0628.** Set X to the original column anchor plus
47 (`207 + column * 51 + 47`), force native facing -1, replace record
sequence with 130 and cursor with 0, clear armed and record mode +0x1c.
The routine does not change Y unless the kind-zero fallback ran. It does
not itself run JumpSeq or advance an animation pose.

**Serpent type 11, 7:0596-05f4.** Only the negative-ALIVE branch enters
the live initializer. For record mode <=0, choose sequence 170, clear the
cursor and store mode -1. For mode >0, choose sequence 175, clear the
cursor and set working special flag 6, retaining the record mode. Both
negative-ALIVE paths set armed=1 and request sound 128. Nonnegative ALIVE
clears armed without replacing the sequence/cursor/mode or playing sound.
Do not replace that signed ALIVE test with a generic `life > 0` condition.

## Checks And Exclusions

The eight synthetic tests cover reference boundaries, preservation of source
objects and word-versus-pointer stack encoding. They do not establish native
equivalence by themselves. The native command performs that separate comparison
on the original routines and actual records.

Initialization assumes the caller has loaded the correct actor type, row and
other working fields. This is not full InitOpps, proof that all supplied states
are reachable, resource loading, motion, neck attachment, snake activation,
damage, audio duration or frame scheduling. A head's mode is reset here, but
its full lifecycle still needs tracing before saving/reloading is implemented.
