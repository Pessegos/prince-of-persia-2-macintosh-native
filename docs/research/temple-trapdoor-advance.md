# Trap-Door Phase Advancement

Research/reference only, no runtime changes. This separates advancement
from the presentation/restoration pass; routine names alone are misleading.

```powershell
python -m tools.probe_temple_trapdoor_advance --source PATH_TO_RECOVERY --output rendered/temple-native-trapdoor-advance.json
python -m unittest -q tests.test_temple_trapdoor_advance_reference
```

## Native Evidence

| Rule | Source | Scope |
| --- | --- | --- |
| Advance trap-door state and request loop sound | 10:24fa-253e | Full original helper, supplied sound-playing queries |
| Type10 update dispatch and bank save/compaction | 5:29e8-2b0e | Full MakeRubble iterator, actual indirect switch bytes |
| Presentation/restore dispatch | 5:307c-3126 ->10:225c | Located; NOT executed by this experiment |

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
The report also records the level10 fixture hash/output digest.

192 direct-helper and 192 bank-driver comparisons pass, plus four bank
controls at counts0/1/3/30 and two 20-call advancement-only traces. Checks
cover the 16-byte object, audio request order, unchanged full level, bank
count/content and prefix/suffix canaries. Seven synthetic tests exercise
the reference separately from native execution.

The initial attempted ATMLoose5:307c update-driver probe stopped at an
unexpected10:225c instruction, exposing that it dispatches PRESENTATION,
not the phase helper. The corrected successful update driver is MakeRubble
5:29e8. This was a research-harness assumption, not a production-game defect.

## Recovered Behavior

Object word+6 exactly -1 returns immediately. Other supplied values0/2 do
not reject. If the low five bits of word+0xe are <=16, increment the entire
signed word by one. At low phase17 or higher, do not increment. Upper bits
are not cleared.

Afterward, query PrinceSndOn(197). If active, stop sound handling. Otherwise
query198, and if that is also inactive request AddSound(198). This still
happens at phase17 while the object has not been marked -1.

| Constructor Value | Low Phase | Values After Advancement | Calls To Low Phase17 |
| --- | --- | --- | --- |
| 1 | 1 | 2..17, then holds17 | 16 |
| 75 | 11 | 76..81, then holds81 | 6 |

The value75 therefore starts later in the same low-five-bit phase scheme;
it is not independently a 75-tick delay. Neither trace deletes the object,
changes its position or restores the floor. Counts are calls to this
helper, NOT certified elapsed game frames or milliseconds.

Native MakeRubble loads/saves every supplied type10 object and then removes
entries with word+6=-1, preserving surviving order. Deleted tail bytes are
not required to be zeroed. Its count changes only during that compaction,
not because reaching phase17 directly deletes an object.

## Boundaries And Next Step

PrinceSndOn5:52c8 returns supplied independent booleans for197/198;
AddSound5:4d84 records requests without playback or sound-queue mutation.
The supplied bank contains only type10 records; no other type's dispatcher
is certified. Negative/counterfactual phase/status controls establish
instruction behavior, not live reachability.

No rendering, restoration, actual sound state, full-frame scheduling,
collision/damage, save/restart or campaign equivalence claim.
The subsequent [presentation probe](temple-trapdoor-presentation.md) and
[connected lifecycle probe](temple-trapdoor-lifecycle.md) now cover the ATM
restoration effects and bank handoff, with their explicit supplied services.
Complete FrameAdv ordering and real audio remain open.
