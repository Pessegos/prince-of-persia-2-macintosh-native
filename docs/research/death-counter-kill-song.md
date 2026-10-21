# NPC Death Counter And Kill-Song Dispatch

Research note, 2026-10-21, `claude/ai-research`. No runtime code changed.
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

Level environments and opponent types (LEVL `0x2186`/`0x21a4`):

| LEVL | Levels | Environment | Opponents |
| --- | --- | --- | --- |
| 2000 | 1 | 5 | guards |
| 2001 | 2 | 1 | none |
| 2002-2004 | 3-5 | 3 | skeletons |
| 2005-2008 | 6-9 | 4 | type 7 |
| 2009-2012 | 10-13 | 2 | type 9 |
| 2013 | 14 | 6 | guards |

- **Level 1:** a guard kill never plays a song (environment 5). The port
  plays none, which is correct.
- **Levels 3-5:** the skeleton song 63 is already implemented
  (`skeleton.victory_pending`). It covers the level-four work.
- **Guard song 189:** first matters in level 14. Types 7/8 (song 137) and
  10 (238) belong to later levels.
- **Port model:** the port has no `+0x18`. Its death registration matches the
  native ALIVE transition (`death-target-lifecycle.md`), and the ALIVE ≥ 6
  target clear was shown not to change the effective target. A death that
  never sets `+0x18` (no CheckStab) would stop at ALIVE 0. Then neither the
  song nor the target clear fires; GenCtrl's dead branch still reselects.
  This was not executed.
