# Cutscene Viewer

The F1 menu lists Cutscene Viewer with Alt+C, also available from gameplay.
The F3 tools offer a shortcut to the same collection. Six large previews fit
in two rows of three, with compact Back and Play buttons beside the title.
Chapter names sit immediately below their images; the duplicate selected-title
footer and large control row are removed.

The wheel (including fractional touchpad deltas), side arrows and scrollbar
move both rows horizontally without snapping to cards or pages; dragging moves
them directly. Chapters fill each column top-to-bottom before continuing to
the right, keeping the two-row strip dense when later chapters come into view. Left/Right and Up/Down follow the grid and
reveal the selection when necessary; Home/End select the first/last chapter.
Clicking a card selects it on release, while a drag never activates a card.
Play or Enter starts it. Locked chapters show a generic numbered card;
neither their image nor their story title is drawn.

The catalog in `pop2/cutscenes.py` includes Prologue, Title and The Palace
Escape from the opening, voyage after level 1,
discovery after level 3, carpet flight after level 5, the throne vision in
level 8, the horse ride after level 9 and the flight after level 13. These are
port chapter labels. Recurring tree scenes, the gameplay demo and attract
credits are not part of the collection. Adding an implemented story program
to the catalog gives it a card and a replay automatically; scenes started
through `start_story_scene` also consult that catalog when unlocking.

## Collection and existing saves

All three opening chapters are available immediately, preserving the previous
whole-opening availability and existing version-1 collection files. Other chapters unlock when the normal
campaign actually starts their scene; finishing or watching every frame is
not required. Seeking through the retained developer navigation, developer
level jumps and gallery replays do not unlock chapters. Natural story starts
after a developer jump still count as encountering the actual scene.

`cutscenes.json` is a small atomic JSON collection alongside the default
Saved Games data, or in `POP2_USER_DATA` when that override is set. It survives
new games and installs into a different folder. Unknown chapter keys are
ignored; an invalid profile falls back to the opening, and a write failure
leaves the in-memory collection usable with an explanatory viewer message.

Campaign save version 2 is unchanged. Loading a validated older save admits
earlier mandatory chapters according to the catalog's completed-level
thresholds. A level 8 save can also admit the vision from its existing throne
flags. A level 13 save does not imply the subsequent tower flight was seen.
An arbitrary developer warp is not used as evidence of campaign progress.

## Presentation and opening boundaries

The grid renders directly at the aspect-fitted window resolution, using the
original 510x384 preview images and original bitmap glyphs. Card surfaces,
the complete two-row strip and the static frame are prepared and cached before
scrolling. Animation crops that prepared strip and updates the scrollbar;
it does not load assets, draw fonts or resize thumbnails on each frame.
Unlocked source previews are warmed before browsing. Locked previews are never
requested. UI screenshots use direct rendering at their capture size.

The viewer keeps a retained Tk photo in both windowed and fullscreen modes.
Tk therefore owns redisplay after hover highlights, cursor changes, exposure
or resizing. Direct Windows bitmap painting is reserved for its existing live
fullscreen gameplay path; it must not be used for this interactive menu, where
a later Tk redraw could erase it and leave a black canvas. The viewer reuses
its photo, shifts existing pixels and uploads exposed edges and scrollbar
changes. Static frame or toast changes update the complete affected patch.
Pixel regressions compare the result to a full render, including reverse
motion, screenshot notices, repeated hover and forced Tk redisplay.

The animation callback aims for 60 Hz including drawing time, runs only while
moving, and is cancelled on playback/destruction or stops when its gallery is
no longer active. Hidden-window timing measures rendering work, not physical
input/compositor latency, so it is not a universal zero-latency guarantee.

Opening boundaries come from the imported title operation, the following frame
setup and the first story music before narration resumes. Prologue ends before
the title; Title includes its fade-out; The Palace Escape reconstructs the
following frame setup silently and begins with its own music/reveal. This omits
an empty transition wait owned by the preceding title song, without omitting
narration. A private player reconstructs palette/animation/cue state, resumes
only currently active cues at their sample offsets, and stops at its chapter's
operation boundary. Imported operations and natural campaign playback are unchanged.

## Replay isolation

The underlying game remains paused. A replay constructs its own `IntroPlayer`,
advances on a separate Tk callback and never calls the campaign's scene-finish
handlers, loads a level or invokes its stored continuation. The live game,
original scene, random generators, world clock, opponents and checkpoints
remain in place. Completion, Space, F1 or the bottom-right Back hint returns
to the collection. Escape or a click on the film pauses/resumes the replay;
losing focus pauses it without automatically resuming on focus return.

The replay borrows already-decoded audio samples and allocates two private SDL
channels. The game's own channels remain paused and its audio-engine state is
not reset. Closing the viewer stops only its channels and restores the channel
count when no other channels were allocated meanwhile. Root destruction also
cancels the replay callback and releases its channels.

The carpet chapter starts FlyinRug at its first film marker: the earlier music
lead-in belongs to the in-game carpet ride and must not create a long blank
wait at the start of a standalone replay. Chapter thumbnails are silent,
private excerpts; the opening uses its animated title rather than the publisher
card. The original campaign's music carry and transitions are unchanged.

## Validation

`tests.test_cutscene_viewer` exercises persistence, legacy-save admission,
locked-card spoilers, horizontal navigation, private audio channels, actual SDL
channel preservation, input/focus/error cleanup and all seven real scene
programs. The full world snapshot is identical before and after each complete
replay, including all three opening chapters. Device presentation, continuous
wheel motion, drag-vs-click behavior, clipping and the Alt+C route are covered. Existing low-level navigation/thumbnail tests retain direct access to
their model, while the public F3 activation regression now checks the isolated
chapter viewer and rejects its former destructive seek behavior.
