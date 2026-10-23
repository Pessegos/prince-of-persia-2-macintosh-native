# Trailing Gate Contact

This is an intentional port improvement, not Macintosh parity. The original
CheckGateForKid response (CODE:4 613c-616e) can force a crouch when only the
trailing edge of a running pose still touches a stone gate's collision band.
The user requested that a nearly completed passage finish naturally instead.

The port ignores four native pixels of rear contact for an unarmed, grounded
Prince in run start/cycle/stop sequences 1, 200-202 or 13. The four extended
stop poses use their own rear inset instead: 53 -> 15, 54 -> 7, 55 -> 18,
56 -> 15 pixels. These exclude the trailing arm/leg, not the head or torso;
the retained rectangle includes the native turban pixels plus one outline pixel.
It is symmetric across facings and applies to geometry, not a room number.
There is no grace timer, forced movement or gate animation change. The closed
phase uses the same narrow exception, preventing a last trailing pixel from
ejecting the actor immediately after a permitted closing-phase contact.

Front contact and deeper overlap retain their existing response. Idle,
turning, airborne, crouching and sword poses are excluded. Side collision,
height thresholds, the crush sequence, displayed-health timing and slam
presentation are unchanged.

`tests/test_gate_clearance.py` covers the ordinary four/five-pixel boundary,
each extended stop-pose boundary, both facings, every permitted sequence and
excluded poses. The room-11 level-four
host regression in `tests/test_cavern_retry.py` reproduces a short left tap
while its lower gate closes, checking normal run completion, retained life
and a real slam (the next reversible plate can subsequently reopen it).

The initial fixed four-pixel margin missed the user's follow-up video:
the last wide stop pose (56) still overlapped the gate by about nine pixels,
despite the head and torso having cleared it. A live host regression now
closes the gate during SEQS:13, reaches poses 55/56 at X114/X108 facing left,
and verifies uninterrupted settling and retained life, also mirrored right.
An imported-art regression checks the insets against the original head pixels.
