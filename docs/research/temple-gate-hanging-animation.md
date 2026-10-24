# Temple Gate Animation With Hanging Actor Effects

Research only, based on `61c8910`. Composes the
[hanging helper proofs](temple-gate-hanging.md) with the actual type4 TROB
dispatch5:0cd6 ->5:41aa, rather than calling StopGate/cue helpers directly.
This is not the complete AnimTrobs bank loop or a full game frame.

## Connected Findings

- Ordinary closing at/below zero runs StopGate, real LoadKid, conditional
  JumpSeq47 and full actor copyback **before** the separate hanging cue and
  final redraw. The action word remains2 after selection because AnimChar
  does not execute here; sequence selection alone is not a completed fall.
- Fast closing at/below zero calls the hanging cue **before** the level4
  relief predicate and slam sound. It does not pass through StopGate/LoadKid
  or select47 on this path. Working/saved actor bytes remain unchanged.
- A permanent opening reaching255 and an already255 gate do invoke StopGate
  and LoadKid, but pass a nonzero position. Therefore they do not select47,
  and these branches do not call the separate hanging cue helper.
- Ordinary opening from180/phase2 requests redraw with the old foreground,
  stores237/phase0 and requests cue0x111, without actor effects.
- StopGate's local lack of a room equality test and the cue helper's room
  requirement remain distinct inside the real gate body. Wrong facing can
  reject47 while still admitting cue29. A supplied missing resource retains
  old actor sequence fields without suppressing the independent cue.

## Evidence

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_gate_hanging_animation --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_gate_hanging_animation_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_gate_hanging_animation_reference
```

**26,568 native/reference comparisons, zero mismatches** at all41 original
header-admitted temple gate anchors. Each of these supplied states covers
4,428 actor/facing/action/column/room/resource-availability combinations:

| Initial Position / Phase | Targeted Path |
| --- | --- |
|3 /1|Ordinary closing completion|
|0 /0|Hold/slow completion at zero|
|60 /4|Fast closing completion|
|180 /3|Permanent opening completion|
|255 /1|Already-permanent stop|
|180 /2|Ordinary open-limit redraw/hold|

Observed native entries include17,712 LoadKid copies,328 JumpSeq/resource/
copyback admissions,2,952 hanging cue requests and4,428 real relief checks.
Relief always rejects temple levels and preserves countdown4321. All actor
byte effects and their order relative to gate redraw/cues are compared,
together with the entire level, foreground/phase, TROB scratch/bank canaries
and ReadCell cache. Seven asset-free tests fix these connected distinctions.

Original executable SHA256 is
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`;
compared-output digest is
`be126cde3028c55257c173f5475c58e093c55be1463794bfd3e067d1e0c56cb7`.
Original level10-13 and SEQS47 hashes are recorded in the ignored report.

## Boundaries

Actors are supplied type0 records; these combinations are not claims of
reachable hanging states at every gate. Resource existence/non-null handles,
missing-resource controls, sound and redraw are supplied. JumpSeq itself is
native, but SEQS47's words/AnimChar are not executed. The six phase/position
controls do not exhaust all gate states. Actor controller/fall/collision/
death, bank iteration/compaction with hanging actors, complete FrameAdv,
sound playback/pixels, saves/reset and temple runtime integration remain
outside this experiment. No production gate improvements were altered.
