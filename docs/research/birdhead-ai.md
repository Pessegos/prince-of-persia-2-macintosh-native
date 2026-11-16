# Birdhead AI: What Set 7 Changes

Started 2026-11-16. The temple's birdheads (LEVL 2009-2012, opponent set 7,
LEVL `0x21a4` = 7) are actor type 2: GenerateOpponent 6:3be0 and InitOpps
6:2bca map set 7 through DATA a5-0x5280 to type 2, so OppCtrl runs the
ordinary guard controller. Whatever makes a birdhead differ from a palace
guard must therefore read the opponent set, the environment or the
artwork. This note checks the set first. Evidence is the Macintosh
disassembly. No native run was done for this batch.

## Every read of the opponent set

The CODE segments read LEVL `0x21a4` at 30 places. Each one was read and
sorted by what it does for set 7:

| Place | Test | Set 7 |
| --- | --- | --- |
| 2:043e, 3:5726, 3:5762 | passed to the loaders (3:5986, LoadOppSet 3:5f58) | Birdhead.rsrc, already imported |
| 2:4c3a, 2:6238, 4:1538, 4:1588, 4:1854, 5:28d8, 6:2a82, 6:41aa, 6:422e | `== 2` (skeletons) | not taken |
| 2:4c76, 3:5290, 5:37a6, 6:2a1c | `== 5` or `== 6` | not taken |
| 6:2a04 CrushOppInfo | `!= 2` clears the record's life | taken, as for set 0 (ported) |
| 6:2bce, 6:2f26 CheckSideRoomsForVisibleOpps | `5`/`6` against the rest | the same as set 0 |
| 6:39ce SetCharacterBank, 6:4102/41e4 PresetOppBanks | sets 0/5/6 call PresetOppBanks; any other set gets colour bank 0 (6:39ec) | colour bank 0, no AI effect |
| 6:3be0, 9:0486 | DATA a5-0x5280[set] gives the actor type | type 2 |
| 4:0082 GetOppDeadSeq 4:00ac | `== 7`: corpses SEQS 191-194 by slot | ported 2026-11-06 |
| **4:484a IsDeadPos** | `== 0` against the rest | **differed, fixed below** |
| **6:33ec, 6:340a SetSpecialOppInfo** | `== 7` | **missing, fixed below** |
| **6:5a8a TestStrike** | `== 7` | **missing, fixed below** |

So, apart from colour banks and the corpse sequences, the original has three
set-7 rules for actor type 2, and the port lacked all three.

## Recovered rules

### A parried attacker steps 13 forward (TestStrike 6:5a84-5a9e)

When a strike is parried (the block branch from 6:5a3c, defender pose 161),
the attacker takes JumpSeq 69 and AnimChar. For types 7, 8 and 10 the
sequence comes from their own helpers. For every other type, Prince
included, the sequence is 69, and in a set-7 level AddCharX(13) (4:2bae)
first moves the attacker 13 pixels in the direction he faces. The port
selected SEQS 69 in place. `resolve_contacts` now passes the 13 to
`select_sequence`. `tests.test_combat` rejects the old result for both a
birdhead and the Prince as the parried attacker.

The extra step changes two birdhead duels in the level-12 video replay
(native rooms 15 and 7). The Prince now ends each one further east, so
`LEVEL_12_VIDEO` gains one `runL11` and one `stepL` after them. The route
still finishes with the same checks, using life 12 as before.

### Saved records in set 7 (SetSpecialOppInfo 6:33bc)

UpdateOppInfo 6:3164 and TransferOppInfo 6:338e call SetSpecialOppInfo. The
Cut copy at 6:3186 does not. For a type 2:

- selected SEQS 100 or 186: word +1c gets the height (ported before);
- otherwise, in set 7 only: +8 gets the current sequence (a5-0x5030) and
  +1c gets 0 (6:33e8-3402). This happens even when UpdateOppInfo restarted
  the cursor and kept the old header;
- in set 7, +0x18 (the raw kind) becomes 7 (6:3406-3418). The port keeps
  actor types, not raw kinds, so this needs no change.

`GuardRoomRecord.capture` takes the opponent set. `tests.test_opponent_records`
covers set 0, set 7, the Cut copy and SEQS 100.

### Dead poses depend on the set (IsDeadPos 4:47a0)

For type 2, pose 185 is dead in every set. Set 0 adds 228 (4:4846-485c),
and any other set adds 248 and 251-256 instead (4:4864-4896). The port used
one list, {185, 228, 252-255}, for everything. A temple record in pose 228
therefore reloaded dead, and one in 248, 251 or 256 reloaded alive. The
new `is_dead_pose(actor_type, opponent_set, pose)` covers the opponents'
cases: type 2 by set, type 10 213, type 4 206/207 and type 11 273, plus
185 for all types. The Prince's branch (4:47e2) is not included. Record
reloads and the tumble scan (4:025a) use it.

### The physics frame table reaches pose 256 (LoadFrame 4:2b0e)

The opponents' terrain physics built its frame table for poses 149-254.
Birdhead.rsrc has 108 frames, so its frames go up to pose 256. A wounded
birdhead's fall (SEQS 183) lands in SEQS 190, pose 256, and the replay
above crashed there with `KeyError: 256`. The table now covers poses
149-256, limited to the frames the resource actually has. Only
entries that were missing are added, so palace guards behave as before.

## Still open

- Level 11's native room 26: a birdhead stands between the Prince and the
  closed right gate (26:19), and the user suspects a fault there
  (temple-remaining.md, item 2). It has not been examined yet.
- The environment's own reads (LEVL `0x2186` == 2) in the AI segments are
  the Prince's or the scenery's: rocks (10:2036 from 4:3644, 4:5806 and
  6:1a3a), the jinnee trigger (6:0c3a), stairs (6:115c) and the colour
  table (6:5212). None of them changes a birdhead's decision. This was
  checked by reading the code, not with a probe.
- No native CPU probe was run for the three rules. Each is a short
  straight-line branch, but a probe of TestStrike's block path with set 7
  supplied would confirm the X result independently.
