# Stone-gate opening audio: source loop and recorded pauses

The cavern movement sound has an internal sustain loop. The initial audit
found that the port discarded that metadata and repeated the whole sample.
Its seamless-loop rework removed the old port's periodic restart gaps, but
repeated a different section from the Macintosh. The follow-up implementation
below preserves the introduction and repeats the resource's sustain region.

The historical `gate-opening-before.wav` is an SDL capture of the old port,
created by the local `gate_opening_loop.py` experiment. It is not a Macintosh
recording. The experiment requested movement at an imposed 100 ms cadence and
waited for each finite sample to finish before requesting another. Neither
that capture nor the README's Before player proves that the Macintosh has the
same repeated gaps. Original frame timing also distinguishes five unarmed
Macintosh ticks from six armed ticks; the experiment was not a native frame run.

## Original resource and native execution

Cavern movement cue17 resolves to `DigiSnd.dat` Mohawk WAVE resource9769.
The Data header is not just PCM length/rate: it also stores loop information.

| Field | Original value |
| --- | ---: |
| Sample rate | 11025 Hz |
| PCM format | unsigned 8-bit mono |
| Total frames | 11524 (1.045261 s) |
| Loop start | frame5025 (0.455782 s) |
| Loop end | frame11520 (1.044898 s) |
| Loop duration | 6495 frames (0.589116 s) |
| Stored repeat count | 65535 |

The original `waveObj` header loads20:3b2a-3b96 independently read these fields.
`calcBlocks`20:37a8-396c builds a block beginning5025 and ending11520 with
both loop-boundary flags set (0x0c). `resetLoop`20:467c-46c2 translates65535
into a signed32-bit repeat count of-1. This is a sustained tail, not a series
of full-sample starts requested once per game frame. Two cue markers at3168
also split the introductory block; they are not extra gate sound variants.

Cues18/20/27/60/61 have no active loop block in the native block calculation.
Their stored loop offsets lie beyond their sample lengths, so the raw65535
word alone must not be treated as a valid infinite loop for every effect.

The port's imported cue17 PCM matches the resource samples exactly after its
documented fixed gain/conversion. At audit time the omission was the loop
metadata: `MixerPlayback` crossfaded12 ms at the whole sample's ends and looped
that private copy, giving a period near1.033 s. Imported WAVs remain unchanged.

## Macintosh recordings

Two supplied Macintosh captures were matched against several separate windows
of the actual cue17 source. The scenes differ: the level-four room11 gate
and the cavern gate/ledge scene from the earlier door-behaviour investigation.

| Capture | Initial larger gap | Later tail period | Excess over resource loop duration |
| --- | ---: | ---: | ---: |
| `macintosh stone correct.mp4` | about92.11 ms | 598.50-598.51 ms | about9.39 ms |
| `macintosh correct behaviour 1.mp4` | about92.16 ms | 598.50-598.55 ms | about9.39-9.43 ms |

Both captures contain an initial full passage, a larger pause, a second full
start, and then repeats matching the5025..11520 tail. The first passage also
has small delays at the introductory block boundaries. Thus the recordings
do contain pauses; they do not show the old port's larger gap after every
full-sample repetition. The two captures consistently reproduce the initial
pause, so it cannot be dismissed as merely a single unrelated sound in one
recording.

These are source-matching estimates from emulator recordings with background
audio. They are not measurements of original Macintosh hardware. This audit
does not establish why the first passage restarts, whether a cached later
opening avoids it, or whether the small block delays come from the game,
Sound Manager, the emulator or their interaction. It would be incorrect to
generalize the exact pause pattern to every opening on every Macintosh.

The source file has no comparable stretch of encoded silence: the longest
run within one unsigned8-bit step of zero in cue17 is less than1 ms.

## Situational interruptions

The native `AddSound`5:4d84 and `SetCueSnd`5:530a retain single-effect priority
arbitration. Cue17 is mode1, priority110. Repeated movement requests do not
restart it while `PrinceSndOn` reports it active. A higher-priority cue can
replace it; movement can restart once that effect has finished.

For example, bone effect61 has priority90 and replaces movement17. Effect60
has priority125 and cannot interrupt an already playing17. The probe executes
these cases through actual5:5122 effect dispatch,5:52c8 `PrinceSndOn` and
16:25fe `SoundItemOn`, with audio start/stop and completion supplied. The port's
approved overlapping-effects policy is a separate intentional improvement.

## Reproduction and limits

Run with local original recovery files:

```powershell
.venv\Scripts\python.exe -m tools.probe_stone_gate_audio --source ../PoP2-Mac-Code-Recovery --output rendered/stone-gate-audio-audit/native-probe.json
```

The probe validates six original resource headers/block graphs, the cue17
infinite-repeat initialization,516 busy/idle cue admission cases, and isolated,
interrupt/resume, lower-priority and stop traces. It uses real CODE instructions
and DATA cue rules. The wave-object pointer, resource handles, initial channel
state,19:2ff0 memset,16:2200 stop,16:23cc start and the interrupting effect's
completion are supplied. The full gate/frame loop, physical Sound Manager and
device buffer timing are excluded. No original executable or audio is committed.

The final probe reports zero mismatches and output fingerprint
`5653e07dbbdaf2824ac5e0efa72c8d0fe67e5571b379ba78b5067274d5cac242`.

Local listening evidence includes the two unfiltered recording excerpts, an
explicit reconstruction of the resource loop, the pre-fix port's actual
prepared loop and the historical old-port capture. The reconstruction supplies
four seconds of movement and no emulator/device delays; it is not labelled as
an original recording. It uses the same fixed import gain as the port version.

## Implemented resource-loop playback

The user approved the metadata-loop reconstruction. `digitized_sound` now
decodes the Hz word, full32-bit frame count and validated loop fields. Import
adds optional loop metadata without changing PCM samples, rates or fixed gain.
All83 `DigiSnd.dat` and74 `NISDIGI.dat` PCM records were checked: their frame
counts fit16 bits, so the corrected header layout does not change their lengths.
Out-of-range loop offsets do not turn other effects into infinite sounds.

`pop2/audio_loop.py` plays the introduction once and repeats only5025..11520,
using the loaded SDL PCM and an independent cursor per gate voice. The callback
runs before ducking and release, on the audio clock rather than gameplay ticks.
At48 kHz the boundaries round to21878..50155, within one output sample of the
source positions. No crossfade or encoded silence is added at sustain joins.
This follows the resource layout, without reproducing the measured emulator
delays or claiming bit-exact Macintosh hardware playback.

Existing imports work without reimporting: only the exact original signed16-bit
cue17 PCM hash, format, frame count and rate enable its known loop when metadata
is absent. Equal duration alone is insufficient. New imports retain metadata
directly. Unknown replacement sounds keep the previous whole-file fallback.

The two gate voices, impact ducking,12 ms stop release, pause/mute/reset and
movement-request deadline remain in place. These are port mixing choices,
separate from original single-effect priority arbitration.

Tests reject repeated intros, skipped intros, gaps at callback/carrier wraps,
shared cursors, accidental loops on unrelated effects and modified source PCM.
An actual SDL postmix capture using an existing original import matched192000
stereo frames (four seconds) exactly against intro-once/tail-repeat PCM, with
zero mismatching samples. Stop cleared its cursor. Local capture and validation
are under ignored `rendered/gate-sustain-runtime/`. The native audit still has
the same six block graphs,516 admission comparisons and fingerprint above.

The README's historical Before example remains old-port audio, not evidence
of repeated Macintosh gaps. Its presentation is reserved for user review.

## Iron gates outside the caverns (2026-10-30)

Cues 17/18/20 are the caverns' stone gates only. ATMGate's AddGateSound
calls (5:42b4, 4360, 43dc, 4416, in a region the listing leaves unmapped)
and StopGate 5:14b6-14cc test LEVL 0x2186: with any environment but 3 the
gate asks for 272 while moving, 273 when it reaches the open-wait position
237, 274 when it stops (closed, or fully open at 255) and 275 for the slam.
A rising iron gate asks for 272 only when its position is a multiple of
eight (5:43d4-43da), i.e. every other frame; a closing one every frame.
Exit doors (ATMExit 5:15c0-1670) keep 17/18/20 in every environment.

Cue 272 has an active sustain loop (frames 2368-13120 of 13195, repeat count
65535), so the mixer's sustain, PCM release, direction voices and the
11/60 s slam lead-in now apply to 272/275 as to 17/20. Only the stone gate
ends its loop on a frame without a request; an iron gate's loop ends with
273/274 or, if those are lost, the sustain's expiry (the sample length).
The rock-impact duck stays a stone-gate feature. Before this the port played
the stone gate's sounds for the ruins' iron gates. Regressions:
`tests.test_pressure_plates` (iron gate phases and slam) and
`tests.test_gate_audio` (iron cues on the mechanism voices).
