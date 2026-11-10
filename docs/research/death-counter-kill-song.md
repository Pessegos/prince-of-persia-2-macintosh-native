# NPC Death Counter And Kill-Song Dispatch

Research note, 2026-10-21, `claude/ai-research`. Originally research only.
Ordinary-guard runtime dispatch was added on 2026-11-10; see the update below.
It answers the open item in `death-target-lifecycle.md`: who sets `+0x18`,
and what `5:4bb8` does. Labels: **[D]** direct reading; **[I]** inference.

## `+0x18` is a pending-cue flag, not a death flag [D]

Many routines write the working `+0x18` (a5-0x503e):
- CheckStab sets 1 (`6:556c`) on every sword stab check;
- other setters include OpponentClose `4:1728`, StairClimbing `6:10f2`,
  DoStepFwd `6:12aa`, GenerateOpponent `6:3c4e` and GenCtrl `6:098a`
  (when it was 0);
- the clearers include `4:3d5e`, `5:4cd4`, `6:131c` and the side-room import
  `6:2e20`.

In the NPC control prefix `4:3d24-3d70`:

| Native ALIVE `+0x1c` | Action |
| --- | --- |
| < 0 (alive) with HP 0 | ALIVE = 0, which registers the death |
| 0..5 with `+0x18` set | ALIVE + 1 per frame (the clear at 20 is unreachable here) |
| 0..5 with `+0x18` clear | Nothing; the count stops |
| ≥ 6 | call `5:4bb8`, then clear the Prince target if it is this NPC; ALIVE stays 6 |

A sword kill passes through CheckStab, so its count normally reaches 6
after six NPC frames [I].

## `5:4bb8`: kill song per actor type [D]

The routine returns unless `+0x18` is set. It dispatches on the type `+0x8`
through the table at `5:4bde` (types 2-11, decoded from the CODE bytes):

| Type | Handler | Song condition | Song |
| --- | --- | --- | --- |
| 2 (ordinary guard; level opponent type 0) | `5:4c2c` | ALIVE ≥ 6, always true here | 189 |
| 3-6, 9 (skeleton is 4) | `5:4c4a` (AddSkelSong, `AUDIO_RECOVERY.md`) | Prince alive, selected sequence 120 or 115, ALIVE > 4, effects 61/68/69 silent | 63 |
| 7, 8 | `5:4c10` | sound 132 not playing | 137 |
| 10 | `5:4bf2` | sound 241 not playing | 238 |
| 11 | `5:4c44` | clears the flag, then the type-3 path | 63 |

In the type table, the song numbers 189, 63, 137 and 238 are the
manifest's KillBird, KillSkel, KillHead and BeatFS cues.

Common tail `5:4c9e-4cd4`: the song is added only when OppToFight (`6:2392`)
and GetOppGenPtOnRow (`6:3d28`) are both false, and the environment (LEVL
`0x2186`) is not 5. The flag is then cleared, so each kill can trigger it
once.

## Relevance to the port

Level environments and opponent families. LEVL `0x21a4` selects an opponent
set, not necessarily the runtime actor type; the temple row was corrected
against the original headers on 2026-11-10.

| LEVL | Levels | Environment | Opponents |
| --- | --- | --- | --- |
| 2000 | 1 | 5 | guards |
| 2001 | 2 | 1 | none |
| 2002-2004 | 3-5 | 3 | skeletons |
| 2005-2008 | 6-9 | 4 | type 7 |
| 2009-2012 | 10-13 | 2 | set 7; ordinary birdheads are actor type 2 |
| 2013 | 14 | 6 | guards |

- **Level 1:** a guard kill never plays a song (environment 5). The port
  plays none, which is correct.
- **Levels 3-5:** the skeleton song 63 is already implemented
  (`skeleton.victory_pending`). It covers the level-four work.
- **Guard song 189:** applies to the temple's ordinary birdheads too, as well
  as palace guards. The earlier claim that it first mattered in level 14
  confused the opponent set with the actor type.
- **Port model:** initially lacked the ordinary pending-cue/count path. The
  2026-11-10 implementation below adds its audio subset while keeping HP,
  registered death and the existing boolean native ALIVE distinct. The
  earlier ALIVE >= 6 target-clear audit remains separate.

## OppToFight `6:2392-2492`, which gates the songs [D]

The routine loads the Prince and returns false when any of these holds:
- the Prince's `+0x34` is 13;
- the Prince's type is 1;
- the Prince's mode is 3 or 4;
- IsDeadPos(pose) holds. For type 0 this is pose 185, 242, 243, 266 or 271,
  plus level-specific checks from `4:4810`.

Otherwise it returns true when any bank slot in the Prince's room has native
ALIVE < 0, alert > 0 and type other than 11. Types 7/8 also need the
generator info `+0x1c` to be 1 or 3.

`CombatEncounter.opponent_to_fight` matches this with three differences:
- it adds a Prince HP test, which the original lacks; the original relies on
  the dead poses;
- it uses guard HP instead of native ALIVE, so a pending death (HP 0, ALIVE
  -1) counts in the original for that frame;
- it applies the intentional rooftop-escape stand-down.

The first two last only a few frames around a death, and the port's tests
state them explicitly (`test_combat_music_excludes_native_player_and_opponent_states`).
The default ambient query retains those existing policies. Ordinary kill-song
dispatch now separately requests native ALIVE, as described below.

## Ordinary-guard implementation (2026-11-10)

The level-12 room-9 playtest exposed both a lingering fall scream and the
missing ordinary KillBird song. Fresh original bytes confirm that the type-2
jump-table entry reaches **5:4c2c**, whose `MOVE.W #189,D5` selects KillBird.
Original LEVL 2009-2012 all have environment 2 and opponent set 7.

`Fighter.death_song_frames` tracks registration at zero and six subsequent
NPC control updates; the next call consumes `death_song_pending`. The flag
is armed for ordinary living control (the supported GenCtrl idle cue),
explicit sword hits and generated actors. This is an ordinary-audio subset,
not a recovery of every writer/clearer of the shared native `+0x18` word.
Cold room-record imports clear the flag/count, so old corpses do not replay.

At dispatch the current native-ALIVE bank and native active-generator
row/column/remaining conditions suppress the song. The flag is consumed on
suppression too. Existing ambient HP policy remains the default; the kill
song specifically asks for native ALIVE and uses the selected projected bank.
Rooftop environment 5 stays silent. Heads, skeletons and the flaming sword
retain their separate existing handlers. No target selection or HP behavior
was replaced by the new counter.

The two defaulted fields are optional in older version-2 saves; new saves
retain a pending count and validate -1..6. Static source and real-scene/timed
audio regressions cover the reported fall, four temple levels, trap death
endpoints, one-shot timing, suppression, imports and save continuation.
No new native CPU probe or complete scheduler/pending-word parity is claimed.
The trap endpoint check also exposed the save validator's old pose-254 cap:
ordinary scythe SEQS 190 ends on pose 256. Ordinary type-2 saves now admit
that real terminal frame (including existing corpse variant 255); the other
actor bounds stay unchanged. Its save roundtrip keeps the music consumed.
See [playtest details](temple-november-playtest.md#guard-fall-scream-and-victory-music-2026-11-10).
