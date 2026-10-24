# Temple Hanging Control After Gate Selection

Research only, following [world/Prince callers](temple-world-prince.md).
No runtime changes. This separately bounded composition removes the supplied
GenCtrl decision, not the whole PlayerCtrl or geometry boundary.

**Naming correction:** `10:2036` is SlideRockInCell, not a bars query.
The historical probe field/event `bars` below is a supplied-bool compatibility
alias, not evidence of bars. [Real controller geometry](temple-controller-geometry.md)
executes the actual sliding-rock lookup/occupancy body. The old comparison
digests and bounded supplied-result behavior are unchanged by this correction.

## Findings

Native GenCtrl `6:0560` routes the tested unarmed living type0 actors with
poses87..99 to hanging control `6:18e0`. Gate selection alone does not decide
the subsequent actor clip: it leaves mode/pose unchanged until animation,
allowing that controller to keep or replace the sequence first.

- With solid above/current responses, holding preserves the selected clip,
  including gate-selected47. Space above instead invokes release. Current
  walls select25 unless mode6; a current gate facing left also selects25.
- Up with zero cooldown takes climb `6:1998` before held-release or the
  actor+52==11 check. It clears the four directional latches, sets held/up1
  and selects10, or73 for an obstructed gate/bars response.
- The gate shortcut uses `(foreground & 255) >> 2 < 12`, facing left for
  temple kind2. Thus47 admits it,48 does not, and a high foreground byte
  does not alter the result. Otherwise the bars query `10:2036(0)` decides
  whether to select73. That query's result is supplied here.
- Releasing clears the four directions and sets down1 without clearing the
  held latch. The actor+52==11 trigger clears that word; climb priority leaves
  it unchanged. A nonzero supplied cooldown suppresses the climb branch.
- Release `6:1a84` distinguishes IsSpace `3:4eb2`, IsWall `3:4ef2`, IsFloor
  `3:4da6` and IsLandOnable `3:4e32`. Impassable objects can be floor-like
  without being land-onable, affecting the wall/floor pair adjustments.
  Relative X corrections are-23,-12,+10 or0 before selecting11/23.
- With space both in front and current, DoJumpHang `6:1b7e` previews a real
  AnimChar. An unsigned new-pose<=old-pose comparison chooses99, otherwise23.
  It restores only cursor, active sequence and selected source. Position,
  pose and mode side effects of that preview survive.

In particular, after a closing gate selects47, a supplied both-space release
can preview47 and retain X+16/mode5/pose50, select99, then enter mode3/pose81
on the ordinary first animation. Merely playing47 without the intervening
controller would miss this path. This is a verified helper composition, not
proof of a physically reachable placement or the later fall/contact outcome.
Selecting73 has another distinction: its first pose135 does not itself change
the previous mode, unlike the first mode-setting command of sequence10.

## Evidence

```powershell
.venv\Scripts\python.exe -m tools.probe_temple_hanging_control --source ..\PoP2-Mac-Code-Recovery --output rendered\temple_hanging_control_v1.json
.venv\Scripts\python.exe -m unittest -q tests.test_temple_hanging_control_reference
```

**28,220 traces / 112,880 native/reference operation comparisons, zero
mismatches.** The connected gate portion contains6,560 traces; release
and hold tile-pair controls contain10,816 each, plus28 climb-threshold
controls. This is bounded branch coverage, not28,220 reachable game states.

The corpus separately checks native gate-bank update, LoadKid, GenCtrl and
first AnimChar. Original temple kind2/opponent-set7 headers and prepared
original sequence resources are checked. Connected controls use all41 original
gate anchors, four phase/position pairs, two facings and20 control inputs.
Additional supplied pair controls cover tile kinds0..51 in both facings,
two preview contexts, mode2/6 hold behavior and climb foreground boundaries.

Every operation compares full level data, both62-byte actors, all160 TROB
storage bytes/count/records/scratch, object scratch, ordered events, service
counts and all five latches. ReadCell cache is otherwise a canary: only the
above-cell sink writes its supplied foreground word. MOB scratch/count,
pending effects, countdown and cooldown are canaries. Original sequence data
and prepared handles are read-only. Fourteen asset-free tests reject wrong
priorities, reversed space admission, erased preview effects, wrong facing/
threshold corrections and unsupported GenCtrl routes.

Executable SHA256:
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`.
Compared-output SHA256:
`9801c0c3a3014ea9489d307878971c9703a2da03f2b3f9fb250a124a254a15cd`.
Original level/sequence hashes and supplied input records remain in the
ignored JSON report; no original resource data is committed.

## Boundaries And Next Step

Real native bodies: AnimTrobs/compaction/type4 gate work, LoadKid, type0
JumpSeq, GenCtrl's bounded hanging dispatch, hanging/climb/release/preview,
ClearControls `4:3e3a`, tile predicates, relative-X adjustment and first
AnimChar. Original executable and resources are read-only local inputs.

Supplied endpoints: current-cell kind `4:35a6`, front kind `4:3a48`, above
kind/foreground `4:3ff8`, bars query `10:2036`, cue/redraw/audio requests
`5:3828/0fe6/4d84`, resource existence/prepared handles `17:330e` and
`4:3098`, state0 handle traps. All selected sequences exist in this corpus;
missing-resource behavior is not extended by it.

The four calls are harness-scheduled. The world/Prince coordinators are not
executed in this second composition; their separate proof still supplies
PlayerCtrl. Latches/cooldown are values at GenCtrl entry, not raw key input:
PlayerCtrl's earlier sampling, orientation and cooldown decrement are not
executed here. Actor placements, cell responses, gate phases and input values
are deliberate controls, not ordinary reachable gameplay traces.

No complete FrameAdv/PlayerCtrl, physical geometry/support/fall/contact/death,
multi-frame climb/release animation, actor save after the last clip, actual
bars query, audio/pixels, save/reset or temple runtime integration is claimed.
Next: connect actual PlayerCtrl input preparation and cell geometry to this
branch inside the world/Prince caller, preserving these preview side effects.
