# Opening Scenes

The opening is not a video file. It combines indexed SHAP images, CTBL palettes,
TEXT strings, NFNT lettering, ANI/SCRP animations, Mohawk PCM voices and MIDI.

## Import

`tools/extract_intro.py` executes the two CODE 15 coordinators, Opening1 at
`0x45c2` and Opening2 at `0x4ee8`, inside a bounded, import-only 68000 instance.
Calls out of those coordinators are intercepted and translated into scene
instructions. Drawing, audio and Macintosh OS routines do not execute there.
Unknown helper calls or failure to terminate reject the import. The resulting
`assets/intro.json` retains source PCs, audio durations and MIDI cue markers.
Neither the executable nor translated scene content is committed to Git.

This recovers scene ordering, sprite placement, transformation loops, original
timer deadlines, palette selection and sound starts from the supported game
image. Audio preloads do not start playback: CreateSound and SetSoundId have
different roles. NISDialog at `15:0bf4` starts a voice, changes the subtitle and
waits for that voice to finish.

The title runs between Opening1 and Opening2, on the continuing 25011 score.
TitleFunc (`15:6fec`) uses markers e/f for the title, g/h for the subtitle,
and i to end the animation. Opening2 subsequently waits for marker j and the
end of that same score. Original title overlay rectangles come from expanded
A5 data at `-0x22f4` and `-0x22ec`.

## Native Playback

`pop2/intro.py` maintains separate indexed drawing and display buffers. Drawing
does not become visible until CopyNIS or DissolveNIS, while subtitles update
their own panel. Transparency depends on drawing flags; color zero is not
universally transparent. The original NFNT 24878 renders the story text and
separate SHAP images provide the decorative initials.

SCRP commands select a layer's shape, position and drawing flags, change the
tick interval, notify the coordinator, sound an effect, end a frame or stop.
Layers and shape indices are one-based. Title shapes use base ID 25001.
The title's script interval is five Macintosh ticks, not five gameplay frames.

All scene deadlines use 60 Hz Macintosh ticks or the original audio markers.
SetTimer establishes a deadline; WaitTimer waits only for the remaining time,
including intervening transitions. FadeInColors/FadeOutColors derive the
percentage step and tick delay from their original flags. Muting does not stop
the scene clock. Pausing freezes playback and the scene clock together.

SDL's existing music and effect channels play the imported audio. MIDI is
rendered at import with the original Macintosh instruments and the same
headroom as level audio. No emulated sound driver or post-processing filter
is used.

Space skips to the palace window escape without leaking input into the level.
F1/F2, fullscreen, focus-loss pause, New Game and End Game work during playback.
Game simulation remains stopped until the intro ends or is skipped.

## Remaining Fidelity Work

Scene resources, sound starts and musical cue synchronization are recovered.
The dissolve duration is original, but its randomized pixel ordering is a
native approximation, not the recovered Macintosh random-number sequence.
Subtitle shadow offsets and title cloud-loop presentation still need a direct
frame-by-frame capture comparison. This is not a claim of pixel-perfect intro
parity. Later cutscenes are not enabled by this implementation.
