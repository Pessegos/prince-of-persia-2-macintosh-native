# Trailing Gate Contact

This is an intentional port improvement, not Macintosh parity. The original
CheckGateForKid response (CODE:4 613c-616e) can force a crouch when only the
trailing edge of a running pose still touches a stone gate's collision band.
The user requested that a nearly completed passage finish naturally instead.

The port ignores four native pixels of rear contact for an unarmed, grounded
Prince in run start/cycle/stop sequences 1, 200-202 or 13. For SEQS:13, a
completed passage also uses the settled idle footprint, rather than the
temporary backward lean of each braking pose. The idle sprite is18 pixels
wide with anchor4: its rear extends14 pixels from the actor anchor. Reserve
one further pixel for the sequence's final backward displacement. The stop
may finish only when this entire15-pixel rear reach is outside the gate on
the departure side. Its current head/limbs can therefore lean back into the
band without interrupting an otherwise completed passage.

This is symmetric across facings and applies to geometry, not a room number.
There is no grace timer, forced movement or gate animation change. The closed
phase uses the same rule, avoiding an ejection during the permitted settling.

Front contact and overlap of the settled body retain their existing response. Idle,
turning, airborne, crouching and sword poses are excluded. Side collision,
height thresholds, the crush sequence, displayed-health timing and slam
presentation are unchanged.

`tests/test_gate_clearance.py` covers the ordinary four/five-pixel boundary,
the settled footprint's exact-fit/one-pixel-overlap boundary, both facings,
every permitted sequence and excluded poses. The room-11 level-four
host regression in `tests/test_cavern_retry.py` reproduces a short left tap
while its lower gate closes, checking normal run completion, retained life
and a real slam (the next reversible plate can subsequently reopen it).

The initial fixed four-pixel margin missed the user's follow-up video:
the last wide stop pose (56) still overlapped the gate by about nine pixels,
despite the head and torso having cleared it. The next per-pose head margins
still missed the plate-edge return: pose56 at X119 overlaps the band by about
20 pixels, while the idle footprint including the final backward pixel clears
it by eight. This motivated the stable footprint instead of larger pose tables.

Live host regressions close the gate during SEQS:13 at several start anchors,
including the earlier X114/X108 and plate-edge X125/X119 pose55/56 pairs.
They verify uninterrupted settling and retained life, mirrored right. The
exact-fit boundary (pose56 at X127) finishes; one pixel further in (X128)
still crouches. An imported-art/sequence regression verifies the15-pixel reach.

The room10->14 seam regression keeps its room-cut/no-pullback assertions.
Its nearer starts477/480 still need a crouch: the settled body overlaps the
rebased gate by9/6 pixels. Starts489/495 now finish without crouching because
they clear by3/9 pixels. This is the same deliberate port exception, not a
room-specific restoration of native behavior.
