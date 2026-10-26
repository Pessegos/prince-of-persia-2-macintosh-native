# Temple collision banks and incoming contacts

Original CheckBarr4:4e34 now executes history selection, generated column
limits, all three row sweeps and incoming-contact flags together. Body
edges/height, actor, preceding banks/row and displayed-room slots remain
fixtures. This does not enable temple gameplay.

The routine first clears both contact indices to-1. Mode7 and selected
sources70/78 bypass ordinary bank rebuilding. Otherwise it selects/copies
history through4:5152, records the new row, derives the interval from actual
GetCharCol and sweeps current, lower, then upper rows. The right limit is
min(column(bodyRight)+4,11); the left is column(bodyLeft)-2. The final
division remainder comes from bodyLeft. This inherits the original mixed
word/long column arithmetic, not ordinary Python floor division.

A contact requires a non-FFFF current room tag equal to its history tag,
and a newly nonzero low or high nibble. The scan runs from9 down to0 and
overwrites each matching flag, so the smallest qualifying column wins.
Already-overlapping masks alone do not constitute a new contact. Previous
row selection and directional nibble clipping therefore affect the result.
These are candidates for the later CheckCollide1 decision, not damage,
movement correction or automatic gate admission.

## Evidence

`tools/probe_temple_collision_banks.py` compares26,370 original calls with
zero mismatches:26,352 room/row/facing/velocity/body/history states across
all122 declared rooms of levels10-13, plus18 early-return/empty-rock controls.
The generated span is restricted to the separately verified-2..11 table
domain. These supplied states are not assertions of physical reachability.

The actual sliding-rock query and overlay routines execute against an
explicitly empty MOB bank, with its memory guarded. The original level's
rock flag controls ordinary queries; separate controls cover both flag values.
Mode7 may still query a rock; source70/78 do not. Float timer0 excludes the
separate ceiling/head helper4:50da. No native endpoint is stubbed.

Complete A5 comparison permits only collision banks, row/interval/anchor/
remainder/contact globals and ReadCell cache/pointers. Ordered cell and rock
queries agree. Actor, saved actor, TROBs, level and MOB memory remain intact.
Eight asset-free tests cover composition order, tag matching, lowest-column
priority, persistent overlap, row-transition clipping, bypasses, empty rocks,
empty intervals and rejection outside the bounded anchor-table domain.

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_collision_banks --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_collision_banks_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_collision_banks_reference
```

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Compared-output SHA256:
`93068d69a8b07f5741f7abbe6c91d68a4c17ebfa097339467261cf4251cc1dda`.
Original resources/reports stay local and ignored. Nonempty sliding-rock
overlays, ShapeBounds, floating head checks, CheckCollide1/Collide and the
outer FrameAdv remain separate integration boundaries.
