# Level 1 To Level 2

Boarding no longer stops at a level-complete screen. The route now continues
through the ship's departure, the voyage cutscene and the beach arrival.

## Original Rules

- SEQS:59 finishes boarding and emits opcode -16. SEQS:215 holds invisible
  pose 0 while the ship continues moving.
- GetEndSong, CODE:5 4e0c-4e42, selects song 32 for the rooftop environment.
  The port waits for that imported song's playback, not a fixed frame count.
  Without an audio device it uses the imported duration instead.
- CODE:2 6134-6168 waits for the end song and the current effect, with the
  original exemptions for effects 272, 17 and 192.
- CheckPlayNIS selects NIS 9. Its coordinator is CODE:15 0cf2-1620, using
  the 28000-range artwork and dialogue from NIS.rsrc, MIDI 28100/28101 and
  the original voice/effect resources. Import recovers 129 drawing, palette,
  timer, audio-marker and wait operations into ending.json.
- The scene uses separate frame and story palettes. Its initial fade restores
  both; the voyage's first dialogue uses the original large capital T.
- LEVL:2001 starts level 2 in native room 2, tile 15, facing right. SetKidDefaults,
  CODE:2 5dba-5dca, chooses SEQS:124: poses 256-263 followed by idle pose 15.
  The final anchor is X=247 on the second floor.
- Desert CUST:4025 places the beach background and three floating-plank images
  with bottom-based coordinates. AnimDsrtPlanks/DrawDsrtPlanks, CODE:18
  0808-08b4, cycle six steps with two steps per image. GetObjShouldAnim,
  CODE:5 11e2, is a visibility gate, not a separate animation timer.
- DesertFunc, CODE:18 01ee-020a, checks `PrinceSndOn(51)` and queues wave
  sound 51 again when that specific cue finishes; unrelated effects do not
  suppress the repeat.
- DesertFunc, CODE:18 0334-0392, queues splash cue 56 on the far-right shore
  once native X reaches `0x30B`, repeating only after cue 56 finishes. Room 2's
  local X threshold is 267 after accounting for its 512-pixel world offset.

The recovered scene calls control the cutscene timing. The port does not add
an artificial black-screen delay to imitate resource-loading time in an emulator.

## Runtime And Tests

The host reuses the intro player for the voyage, then constructs a fresh level
session and renderer. Maximum health carries forward; rooftop guards, harbor
state, checkpoints, pending commands and sprite caches do not. Skipping the
voyage reaches the same beach arrival, and pausing freezes playback and audio.

Dev Mode's Playback tab groups departure, stowaway, dream, storm and arrival
under `After Level 1`. Seeking creates the destination's own state. New Game
or seeking the opening demo from the beach returns to the level-1 renderer.

tests/test_level_ending.py covers the music/effect gate, scene fades and initial
capital, deterministic large/small time steps, departure animation, pause,
skip, health transfer, level-state isolation, the complete arrival pose chain,
shore audio and the development shortcuts. Synthetic scenery and transition
tests also run in CI without original assets.

The level-2 shore and stone puzzle lead to the level-3 entrance. Level 3 remains
limited to that first room; its later rooms, interactive objects, animated
cavern details and other far-shore interactions still need recovery.
