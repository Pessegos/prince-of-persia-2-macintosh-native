# Trailing Gate Contact

This is an intentional port improvement, not Macintosh parity. The original
CheckGateForKid response (CODE:4 613c-616e) can force a crouch when only the
trailing edge of a running pose still touches a stone gate's collision band.
The user requested that a nearly completed passage finish naturally instead.

The port now ignores at most four native pixels of rear contact for an
unarmed, grounded Prince in run start/cycle/stop sequences 1, 200-202 or 13.
It is symmetric across facings and applies to geometry, not a room number.
There is no grace timer, forced movement or gate animation change. The closed
phase uses the same narrow exception, preventing a last trailing pixel from
ejecting the actor immediately after a permitted closing-phase contact.

Front contact and deeper overlap retain their existing response. Idle,
turning, airborne, crouching and sword poses are excluded. Side collision,
height thresholds, the crush sequence, displayed-health timing and slam
presentation are unchanged.

`tests/test_gate_clearance.py` covers the four/five-pixel boundary, both
facings, every permitted sequence and excluded poses. The room-11 level-four
host regression in `tests/test_cavern_retry.py` reproduces a short left tap
while its lower gate closes, checking normal run completion, retained life
and a real slam (the next reversible plate can subsequently reopen it).
