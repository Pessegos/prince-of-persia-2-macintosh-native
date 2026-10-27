# Stone-gate opening audio: source loop and recorded pauses

The cavern movement sound has an internal sustain loop. The port currently
discards that metadata and repeats the whole sample. Its seamless-loop rework
removes the old port's periodic restart gaps, but uses a different repeating
section from the Macintosh. This audit changes no runtime sound or asset.

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
documented fixed gain/conversion. The omission is the loop metadata.
`MixerPlayback` currently crossfades12 ms at the whole sample's ends and loops
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
explicit reconstruction of the resource loop, the current port's actual
prepared loop and the historical old-port capture. The reconstruction supplies
four seconds of movement and no emulator/device delays; it is not labelled as
an original recording. It uses the same fixed import gain as the port version.

Before another subjective audio change, preserve the introductory section and
the native sustain region, then compare that version with the present rework.
Any smoothing at joins or stopping should be described as a port choice.
The README should describe the resulting continuous playback without claiming
that its old Before example is evidence of repeated Macintosh gaps.
