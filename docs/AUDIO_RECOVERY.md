# Level-1 Audio

## Import And Playback

The importer reads `DigiSnd.dat` and `MIDISnd.dat` data forks as Mohawk
archives. Digital effects are unsigned 8-bit PCM. Their samples, channel
counts and source rates are retained; signed 16-bit conversion uses
`(sample - 128) * 64`. No smoothing, denoising or per-effect normalization is
applied. Fixed gain leaves headroom when effects and music overlap.

Music is MIDI, not a recording. Application `INST` and `snd ` resources
provide the original instrument samples, base notes, pitch/rate flags and
sustain loops. Import renders level-1 songs with upstream `smssynth`, then
stores conventional PCM WAVs under ignored `assets/audio/`. The application
itself is not retained. No game content is stored in `vendor/`.

Upstream's integer BPM/pulse conversion otherwise shortens these sequences.
Import preserves absolute MIDI event times on a 1 ms grid, with tempo 60 BPM
and 1000 ticks per beat: every pulse is exactly 48 frames at 48 kHz. Event
displacement is at most 0.5 ms. The importer also repairs that build's
oversized float-WAV length fields while converting the actual payload with
one common gain, not stretching or normalizing individual songs.

This is not a bit-exact reimplementation of Apple's MIDI driver. The host
sampler's interpolation, envelopes (including its default release tail), pan
and mixing may differ from Sound Manager. Original instruments and MIDI
timing are preserved, but listening comparisons remain necessary. The
manifest records MIDI event duration and actual prepared playback duration
separately; they are not assumed to be identical.

SDL/pygame uses independent music/effect channels. Samples are loaded once
at startup; gameplay does not spawn a synthesizer, read new sound files
every step or generate diagnostic recordings. Pause/F2 pauses both channels.
Restart/developer warps stop current and pending playback. Import is staged
before replacing installed resources; progress reaches Tk through a queue.

## Recovered Rules

Addresses are CODE segment:offset. `tools/extract_audio.py` expands DATA/ZERO
globals to export these tables, rather than installing a hand-written copy:

- A5 `-0x40a0`: cue mode, priority, handle and PCM/MIDI format, 301 entries.
- A5 `-0x4396`: 16 death-method-to-song entries.
- A5 `-0x40fe`, `-0x40e2`, `-0x40c6`: ambient starts, inclusive last indices
  and combat groups. LEVL `0x2186` selects the bank; `0x424a` stores cell groups.
- Level 1 uses bank 5: start 40, inclusive last index 3, combat group -1.
  Its four songs are RoofA-D (cues 40-43). The -1 gate clears combat selection
  before `SpecialMusic`; BrgFight is not enabled here.

`AddSound` (5:4d84) retains one pending effect per simulation update; smaller
priority wins and a tie replaces the pending request. `SetCueSnd` (5:530a)
gates interruption: mode 0 waits, mode 1 rejects itself while playing, and
mode 2 can retrigger itself. Mode 1/2 priority still gates replacement.
Actor type 1 suppresses footsteps; rooftop guards are type 2. `AddSong`
(5:4d58) retains the first pending song independently of effects.

`PlayAmbient` (5:4f92) waits for the current song. `Rnd` (17:6e06) includes
both bounds. If it chooses the previous song, 5:50c2 advances one and wraps
at the inclusive end, rather than rerolling or excluding that song before
sampling. Later-level combat-group transitions are not implemented.

Non-sequence events use their ordinary recovered cue sites:

| Event | Source | Cue |
| --- | --- | --- |
| Window glass | TriggerRoofGlass 23:151e | 36 |
| Ordinary landing | HitFloor 6:039c | 296 |
| Damaging/fatal landing | HitFloor 6:0280 onward | 7 |
| Long Prince fall outside harbor rooms 15/16/19 | Falling 6:00ae; AddKidScream 5:4b5a | 8 |
| Ordinary guard fall / tumble | Falling 6:00d4; SEQS:185 | 30 |
| Ledge catch | 4:38c8 | 9 |
| Wall contact / blocked attacker pose 167 | 4:5a54; AddSFX 5:4cf6 | 10 |
| Parry | 6:5af4/5b18 | 11 |
| Prince / guard hit | CheckStab 6:54dc/550e | 12 / 31 |
| Water splash | SetupSplash, CODE:23 | 35 |

SEQS opcode -15 forwards explicit sounds and alternates footsteps 294/295
through callback 1. Landing or catching stops the Prince's long-fall scream.
Offscreen/peaceful guard events are drained without playback, so they cannot
accumulate and sound on a later visit.

## Death And Retry

`DeathState` retains the settled-pose counter and retry gate. It asks the
audio engine about current/pending playback, including the original
272/17/192 effect exceptions, and queues the extracted death song at counter
6. The message appears after actual music/effect completion, not a fitted
delay or MIDI-duration table. Silent harnesses have no sound to await.
See [REBIRTH_RECOVERY.md](REBIRTH_RECOVERY.md) for checkpoint/input rules.

Tests cover arbitration, the inclusive pool, event retiming, PCM preservation,
headroom, real SDL pause/stop, scene cues, failed imports and playback-gated
retry. The SDL unit test uses a dummy device and synthetic audio; original
sample comparisons require locally imported game files.

## Next: Intro

The Macintosh intro is not a ready-made movie file. CODE:15 coordinates
ANI/SCRP/SHAP/CTBL animations in the NIS/TNIS resources, with separate
`NISDIGI.dat` and `NISMIDI.dat` sound archives. These are not part of the
gameplay cache above and have not been added to the launcher yet.

The generic dispatcher is `tAnimation::runScript`, CODE:16 08ee. Its indirect
handlers at 099c-0a9e are absent from the recursive disassembly but present
in CODE bytes. Commands carry an opcode byte and instruction-length byte:
stop, frame boundary, notify callback, sound callback, tick interval, layer
shape, layer position and layer flags (0-7). ANI supplies bounds, layer count
and script ID. This establishes a recoverable format, not a completed intro;
choreography, palettes, drawing and audio synchronization need translation
and validation before replacing the current startup.
