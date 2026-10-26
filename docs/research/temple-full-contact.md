# Temple gate contact with real distance and ejection

The previously separate [contact routing](temple-gate-contact.md),
[distance selector](temple-gate-soft-distance.md) and
[hard ejection](temple-gate-ejection.md) now execute together in the real
4:60e4 caller. Actor/body rectangles, cached frame fields, room slots and
overlap banks remain fixtures; temple gameplay is still not enabled.

Soft contact performs the real JumpSeq50 lookup before the real4:5eae
measurement. A successful lookup updates active/source/cursor but does not
animate the actor or load the new frame. The previous pose and cached frame
dx/flags therefore determine the supporting-foot measurement. A failed
lookup preserves that clip state but still runs the measurement/correction.
Selected source50 suppresses repeated selection and distance calls.

The measurement is not locked to the gate found by the caller: it reads
the actor's current and forward cells according to its own rules. It may
leave a different cell/room-base cache. Below25, the real signed relative
X correction follows; otherwise X remains. High-byte-only foreground can
choose this soft response even though the low gate position is zero.

Hard contact instead updates the mark and executes the real4:6202
ejection. Neither response zeros HP/ALIVE or registers a death in these
temple paths. Open admission, exact-overlap rejection, nonnegative ALIVE
and source118 preserve the appropriate early-exit behavior. The two overlap
words must intersect to exactly255, not merely contain those bits.

## Evidence

`tools/probe_temple_full_contact.py` compares66,500 calls, zero differences:
66,420 fixtures around all41 original gate anchors and80 focused caller
controls. The anchor corpus crosses both facings, current/adjacent columns,
five foregrounds, three selected sources/body positions/cached frame pairs
and successful/failed SEQS50 lookup. Controls include short/tall bodies,
armed/pose109 hard responses, ALIVE/source exits and exact overlap masks.
Raw anchors beyond a level's declared room count are controls, not admitted
playable content. Fixtures are not claimed reachable world trajectories.

Whole A5 comparison allows only predicted actor, mark, anchor, distance-kind,
remainder, cell cache and room-base pointer writes. Saved actor, TROBs,
overlap banks, original SEQS50 bytes and level bytes remain unchanged.
Ordered resource/response events and cell requests match. Only SEQS50's
Resource Manager lookup is supplied; no geometry, distance selector,
ejection, audio or animation endpoint is substituted on these paths.

Seven new asset-free tests pin actual measurement/correction after selection,
cached-frame preservation, failed-resource continuation, source50 repetition
suppression, safe42, high-byte versus zero foreground and hard/early paths.
All466 temple reference tests pass. The latest shared gameplay suite after
the coordinate correction passes2994 tests518.608s with10 desktop skips;
this subsequent research-only module was tested separately and changes no
runtime, assets or saves. The native draft was promoted byte-for-byte.

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_full_contact --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_full_contact_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_full_contact_reference
```

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Compared-output SHA256:
`0d27ba4f03e749386a2ee1da898949feb6f0713dfeed646ae5573fcdcdd1ab17`.
Original bytes and detailed reports remain ignored locally.

Next remove the supplied overlap-bank boundary by recovering the native
collision sweep/history, then compose real frame/body setup and persistent
support/fall/hazard updates. InitRoom, outer FrameAdv, actual rendering/
audio, damage/death, save/reset and playable-temple parity remain open.
