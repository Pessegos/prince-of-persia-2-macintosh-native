# TestStrike Writes To The Prince Target

Research note, 2026-10-21, `claude/ai-research`. Follows
`prince-turn-flag-and-rear-target.md`. No gameplay code changed. Labels:
**[D]** direct reading of original instructions, **[X]** executed in a local
native probe, **[I]** inference, **[?]** open.

## Original rule

- [D] TestStrike `6:57b2` runs two loops over the active bank. Loop 1
  (`6:5800-5838`) makes each NPC the attacker and the Prince the Opp. Loop 2
  (`6:583a-5874`) makes the Prince the attacker and each slot in turn the Opp.
  Loop 2 has no early exit. After its last slot, `4:32d0` copies the working
  Prince record back to the saved Prince record, so writes to the working
  target field (`+0x3a`, `a5-0x501c`) persist.
- [D] The contact routine `6:5896` requires all of these:
  - sword state 1, the same row, and a Y difference below 15;
  - IsStrikingPos `6:5d60` for the attacker;
  - the Opp with native ALIVE < 0, type not 10/1, wound mark not 8, and word
    `+0x28` not 110.

  From there:
  - **Block:** the opposing Opp is 61-99 px away and in pose 161 or 150. The
    Opp's pose becomes 161 (`6:5a3c`). When the attacker is the Prince, the
    Prince target becomes the Opp's slot (**`6:5a48`**). The Prince then
    selects SEQS:69 and runs AnimChar (`6:5a84-5ab0`).
  - **Hit:** IsTheStrikePos `6:5e42` plus GetCharStrikeRanges `6:5b38`. The
    Opp's wound mark becomes 10 (`6:59fa`). When the attacker is the Prince,
    the Prince target becomes the Opp's slot (**`6:5a06`**).

## Executed comparison [X]

Local probe `teststrike_target_writer_native_probe_v1.py` (not published). It
makes one full original TestStrike call per fixture, including the real record
loads and saves, and records every write to the Prince target field.

- **Fixtures:** resident guards only; room 1 of the level-1 LEVL; Prince at
  X=250 with both facings; Prince pose 154 or 153 (and 158 as a control); all
  HP 3; swords drawn.
- **Supplied/stubbed:** AddSound `5:4d84` is the inherited stub. The block path
  stops at `6:5a4e`, after its write and before JumpSeq(69)/AnimChar (sequence
  resources are not loaded), so later slots are not tested after a block.
- **Port side:** `resolve_contacts()`, which ends with `refresh_target()`.

| Fixture | Original Prince target | Port target |
| --- | --- | --- |
| Cached A out of reach, B hit | B | A |
| Cached A and B both hit | last hit slot in bank order | A |
| Cached A out of reach, B blocks | B | A |
| Only cached A hit | A | A |
| Pose 153, nobody blocking | no write | unchanged |
| Ready pose 158 | no write | unchanged |

- **Contact outcomes match in every fixture.** Bank wound marks agree with the
  port's hurt guards, and blocks with the port's parries, including blocks
  against pose 153. These fixtures are evidence of `resolve_contacts` contact
  parity, not of its target handling.
- The only other difference: with no cached target and no contact at pose 153,
  the original keeps -1 while the port's `refresh_target()` already picks the
  nearest guard. SwordCtrl makes the same choice on the next native frame, so
  this is representational [I].

## Consequence [I]

After the Prince hits or is blocked by a guard other than the cached one, the
original's next SwordCtrl keeps that guard (HP > 0) as the Prince's Opp. The
port keeps the earlier target, which still drives its turn, unarmed bump,
fast-block check (`scene_prototype.start_sword_action` reads the target's pose
168/153) and the saved target index. This is a second independent source of
the target difference, separate from the same-facing reselection (D1).

## Turn routine closure (static) [D]

The Prince turn routine `6:26b8` reaches `6:2770` JumpSeq(0x7f = 127) on every
path except the special-room exit at `6:26d8`, which needs LEVL `+0x218a = 5`,
room 10 and `a5-0x3130 > 0`. The floor checks at `6:26dc-276c` only set the
AddCharX adjustment, which the port already models in
`terrain.combat_turn_offset`. Executing it natively would need the frame
loader `4:2a8e`, whose jump-table dispatch at `4:2ab8` is not decoded in the
recovered listing, so the offset itself was not compared.

## Open

- A full-frame sequence: TestStrike → CheckStab → next SwordCtrl.
- Multi-slot ordering after a block, which needs AnimChar with sequence data.
- **Proposed port change, not implemented.** When the Prince's strike lands or
  is blocked, set the persistent Prince target to that guard, using the last
  slot in active-bank order. This would be the same persistent SwordCtrl cache
  proposed in the companion note, and it needs coordination on `combat.py`.
