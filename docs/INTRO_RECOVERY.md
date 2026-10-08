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

NISTextDraw (`15:0302-03ae`) selects font family 213 at size 20, whose FOND
entry references NFNT 24878. The three text passes shift the rectangle by
8, 6 and 5 pixels horizontally and use palette indices 255 (black), 3 and 14.
They do not shift vertically. TextInRect (`17:28de/2b9a`) centers the line
height, places each baseline four pixels above the line's bottom, then applies
the font ascent to the bitmap. Decorative initials use the first pass's
rectangle, not the main lettering's rectangle.

NIS palette uploads (`15:2976-2982`, `17:0b40-0b4c`) call ShowColors
(`17:0694`) for entries 1 through 254 only. The display's black entry 255
stays reserved even when a scene CTBL contains a different RGB value there.
Playback retains those source colors in its working table but presents index
255 as black. Applying CTBL 27013's green entry 255 to the display would
incorrectly recolor the text shadow throughout the second opening.

DrawDisolveData (`15:31ba-3256`) copies 2x1-pixel words in two passes. The first
alternates offsets 0 and 2 for successive shuffled four-pixel groups; the
second copies the complementary words in the same order. D7 advances per
group, not only per pass. Copying every low-address word first would produce
vertical stripes at half progress. This affects the inner story rectangle only,
leaving the molded frame and subtitle panel intact. The importer recovers that permutation
from the optional `Prince2.opt` DSLV resource. Cached source/destination byte
offsets use different framebuffer strides; the source stride is inferred from
the complete row layout before translating to native pixel coordinates.
Only the permutation and rectangle are retained in `intro.json`, not pointers
or machine-specific delay calibration. Without a usable cache, playback uses
a deterministic shuffled group order with the same two-pass word geometry.

GetFullScreenRect (`17:1ada-1b00`) returns 510x384, matching the NIS frame
SHAP. The host keeps its 512-wide composition buffer but removes its two
padding columns before nearest-neighbor presentation. Story images are
aligned with that visible rectangle; gameplay coordinates are unchanged.
Fullscreen fitting and menu pointer conversion use the same 510x384 extent.

SCRP commands select a layer's shape, position and drawing flags, change the
tick interval, notify the coordinator, sound an effect, end a frame or stop.
Layers and shape indices are one-based. Title shapes use base ID 25001.
The title's script interval is five Macintosh ticks, not five gameplay frames.

TitleDrawBack (`15:7178-7224`) draws the sky opening at (172, -19), with
rear clouds at (-21, 128), (-116, 58), (283, 197) and (96, 163). The negative
coordinates are signed MOVEQ immediates, not positive byte values. Animated
cloud layers retain the positions and order from the original SCRP.

TitleFunc's second-frame callback (`15:7014-7060`) performs a 25-tick fade.
During that blocking fade the script stays on frame two. The animation
maintainer (`16:0366-0468`) schedules from its current TickCount and resumes
one frame after the fade, without replaying all missed deadlines. With the
five-tick script interval this adds 20 ticks to the animation clock. The
original SCRP terminates at tick 1000, so the title ends at tick 1020 (about 16.96 s),
unless the music's final title cue arrives earlier. PlayTheAnimation
(`16:14be-14d4`) exits when the script stops; it does not loop clouds until
cue i. The following fade retains the last drawn title image.

Tick-based scene deadlines use the classic Macintosh VBL clock, 60.14742 Hz,
also used by Mini vMac's `OSGLUWIN.c` host timer. Treating it as exactly 60 Hz
would leave the cloud script about 40 ms behind after 17 seconds. MIDI markers
and sampled audio retain their own timestamps in seconds; they are not sped up.
SetTimer establishes a deadline; WaitTimer waits only for the remaining time,
including intervening transitions. FadeInColors/FadeOutColors derive the
percentage step and tick delay from their original flags. Muting does not stop
the scene clock. Pausing freezes playback and the scene clock together.

After the title's initial fade, the host schedules from the next SCRP deadline
or title cue, accounting for time already spent rendering. It does not snap
cloud updates to a separate 60 Hz refresh grid. Repeated calls within the same
cloud frame reuse the indexed composition and converted image unless its
palette or title overlay changes. The window only presents changed intro
revisions; resizing and menus still explicitly redraw. Fullscreen measurements
at 3440x1440 visited every cloud script frame without skipping or reversing.
Overdue intro callbacks yield for at least one millisecond so Tk can paint and
process idle work even when a full-resolution upload exceeds a transition's
frame budget. A continuous zero-delay callback chain would defer painting until
the fade or dissolve ended. Alt+F4 closes the host before modal input filters,
including during the intro and while paused.

SDL's existing music and effect channels play the imported audio. MIDI is
rendered at import with the original Macintosh instruments and the same
headroom as level audio. No emulated sound driver or post-processing filter
is used.

Space skips to the palace window escape without leaking input into the level.
F1/F2, fullscreen, focus-loss pause, New Game and End Game work during playback.
Game simulation remains stopped until the intro ends or is skipped.

## Remaining Fidelity Work

Scene resources, sound starts and musical cue synchronization are recovered.
Cached dissolve order is original; the fallback for images without that cache
does not reproduce Macintosh Random's seed and sequence. Title composition
and finite script timing have been compared with Macintosh captures. Capture
start phase, audio-driver timing and complete frame parity are not established.
Later cutscenes are not enabled by this implementation.
