# Cutscene Viewer

The F1 menu lists Cutscene Viewer with Alt+C, also available from gameplay.
The F3 tools open a developer version with every chapter available, independently
of recorded story progress. It uses the same covers and isolated replay, but
does not add unlocks, save the collection or change the campaign. Returning to
F1 or opening Alt+C restores the normal progress restrictions, even after
replaying a later chapter through the developer viewer. Its title includes
"Dev Tools" so the two entry modes can be distinguished. The local responsive
sketch uses the full window for this page: six previews fit in two rows of
three at 4:3 and 16:9, while wider windows fit more columns (four at 2560x1080).
The header contains only the title; there are no Back or Play buttons.
Chapter names sit immediately below their images; the duplicate selected-title
footer and large control row are removed.

The wheel (including fractional touchpad deltas), side arrows and scrollbar
move both rows horizontally without snapping to cards or pages; dragging moves
them directly. Chapters fill each column top-to-bottom before continuing to
the right, keeping the two-row strip dense when later chapters come into view. Left/Right and Up/Down follow the grid and
reveal the selection when necessary; Home/End select the first/last chapter.
Clicking a card selects it on release; a double click on that same card starts
it. A drag, scrolling, leaving the canvas or losing focus clears the pending
click, so browsing cannot accidentally start a film. Arrow keys and Tab also
navigate the cards; Enter remains available without an on-screen key legend.
Escape returns to the F1 menu. Locked chapters show a numbered card whose
picture is the chapter's own cover reduced to four samples across and then
spread over sixteen columns of darkened blocks: a wash of its colours in which
no shape can be made out. Their story title is not drawn. A chapter unlocked
by playing it since the viewer was last open is selected when the viewer opens
and, after a short wait, resolves in eight steps that bring back detail and
finer blocks together, like a console's mosaic fade; its title appears halfway.
Chapters admitted from a loaded save, and the developer viewer, do not animate.
The page takes the level's menu theme (docs/MENU_THEMES.md).

The catalog in `pop2/cutscenes.py` includes Prologue, Title and The Palace
Escape from the opening, voyage after level 1,
discovery after level 3, carpet flight after level 5, The Mother's Vision in
level 8, the horse ride after level 9 and the flight after level 13. These are
port chapter labels. The vision is the mother's; its persistent collection key
remains `vision`. Recurring tree scenes, the gameplay demo and attract
credits are not part of the collection. Adding an implemented story program
to the catalog gives it a card and a replay automatically; scenes started
through `start_story_scene` also consult that catalog when unlocking.

## Collection and existing saves

All three opening chapters are available immediately. Other
chapters unlock when the normal campaign actually starts their scene and the
preceding mandatory story chapters have been reached. Finishing or watching
every frame is not required. Collection reads retain a chronological prefix;
an isolated debug flag such as the horse without the earlier chapters is
ignored. New Game starts with the three opening chapters again.

A successful F3 room/level warp or retained developer seek suspends collection
updates for that debug session, including scenes triggered afterward. Starting
a new game or loading a validated campaign save restores normal admission.
Gallery browsing and replays never unlock chapters.

The current collection lives in memory and is saved as a short `cutscenes` list
inside each `.pop2save` when Save succeeds. Loading another save replaces the
collection with that save's list; progress gained since the last Save remains
in memory until the next Save. Scene starts and gallery browsing do no disk I/O.
The old global `cutscenes.json` is left untouched but is no longer read, since
its chapters cannot reliably be attributed to any one save. The existing
atomic save writer protects the updated file.

Campaign save version 2 adds an optional, validated `cutscenes` field. Loading
a validated older save without it admits
earlier mandatory chapters according to the catalog's completed-level
thresholds. A level 8 save can also admit the vision from its existing throne
flags. A level 13 save does not imply the subsequent tower flight was seen.
An arbitrary developer warp is not used as evidence of campaign progress.

## Presentation and opening boundaries

The grid renders directly at the menu viewport resolution. A shared UI
viewport/mouse transform lets this page use wide windows independently of the
game's fitted 510x384 viewport. Text, icons and margins use one uniform scale;
extra width changes card layout rather than stretching them. Taller windows
retain a minimum 510:384 UI aspect. Windows' proportional sizing constraint is
suspended while browsing this page, so it can also be resized horizontally.
Other menus retain their existing layouts during this local design review.

Chapter covers use the nine user-selected images in a 16:9 area. Their exact
scene moments and crop rectangles are recorded in `pop2/cutscene_covers.py`,
so imported original resources reconstruct the covers without shipping original
artwork or depending on private PNG paths. The updated title crop also fills
the 16:9 image area. An exact 8x intermediate retains the
fractional native-pixel boundaries of the supplied crops; the source preview is
then cached at 1024x576. No generated detail or changes to story playback are
introduced. Locked covers are never requested. The separate cover-cache namespace
prevents reuse of the earlier temporary screenshots.
The story films and the game still render at their original proportions, with
bars where needed. The paused game behind the panel is centered and fitted too.

Card surfaces, the complete two-row strip and the static frame are prepared
and cached before scrolling. Interactive animation moves the retained strip
inside a clipped child Tk canvas and updates the small scrollbar patch;
it does not copy the whole image, load assets, draw fonts or resize thumbnails
on each frame. The full PIL renderer remains the reference for captures.
Unlocked source previews are warmed before browsing. Locked previews are never
requested. UI screenshots use direct rendering at their capture size, keeping
the menu's current aspect. A private gallery copy prevents export geometry from
changing live hit boxes, selection, hover or dragging. Ordinary game screenshots
keep their existing native crop and integer scaling.

The viewer keeps a retained Tk photo in both windowed and fullscreen modes.
Tk therefore owns redisplay after hover highlights, cursor changes, exposure
or resizing. Direct Windows bitmap painting is reserved for its existing live
fullscreen gameplay path; it must not be used for this interactive menu, where
a later Tk redraw could erase it and leave a black canvas. The viewer reuses
its static photo and a separate retained photo of the prepared strip. The
child canvas clips the moving photo, so scrolling changes an item coordinate
rather than uploading the visible strip's pixels each time. Pointer events
from that child retain the parent viewport coordinates and input bindings.
Both photos are opaque RGB after composition. Selection and static frame
changes refresh the full frame; screenshot notices temporarily use that full
renderer to preserve their overlay order. Replay, menu close and destruction
dispose of the child viewport.
Hover uses four retained border rectangles over the cached strip. Crossing
cards changes those rectangles immediately, without rebuilding or uploading
card artwork. The capture renderer draws the same clipped border in pixels.
The static parent image is repositioned only when its position changes.
Reassigning identical canvas coordinates still invalidates a Tk image item;
doing that every frame needlessly redraws the large background behind the strip.
Pixel regressions compare the result to a full render, including reverse
motion, screenshot notices, repeated hover and forced Tk redisplay.

The animation callback has its own adaptive clock targeting the current monitor's
refresh rate, including 120 and 240 Hz. On Windows, `MonitorFromWindow`,
`GetMonitorInfoW` and `EnumDisplaySettingsW(ENUM_CURRENT_SETTINGS)` identify the
monitor containing the Tk wrapper window and read its current display frequency.
This is read-only and never changes the display mode. Detection runs when motion
starts and once a second during motion, so moving the window to another monitor
updates the target. Unavailable/default driver rates use 60 Hz.
The monitor APIs and structure layouts follow Microsoft's
[display settings](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-enumdisplaysettingsw)
and [DEVMODEW](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/ns-wingdi-devmodew)
documentation.

Frames have deadlines and rendering headroom on slower machines. Tk schedules
canvas drawing in idle handlers; the next timer is therefore scheduled after an
idle completion callback, including that drawing work in the measured budget.
This avoids reentrant `update()` calls and does not change Tk's ownership of
redisplay. The clock is independent of the game's actor ticks. A time-based
spring preserves velocity when wheel input
changes. Scrolling past an end carries that same position and velocity into a
wider overscroll, then makes a slower soft return. An outward gesture at an
already reached edge reacts on the first animation frame; there is no wait for
the ordinary scroll to settle before starting a separate bounce. Dragging
past an edge gives bounded resistance and springs back on release. No bounce
is applied if all chapters fit. The callback runs only while moving and is
cancelled on playback/destruction or stops when its gallery is no longer active.
The target is a scheduling rate, not a hardware VSync or measured presentation
FPS guarantee. Hidden-window timing omits physical painting/compositor/input
latency; simulated 240 Hz tests do not establish physical 240 Hz presentation.

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
remain in place. Completion, Space, Backspace or F1 returns to the collection.
Escape or a click on the film pauses/resumes the replay. This keeps Escape for
pause and Space for skipping, as in the campaign scenes. Held-key repeats cannot
toggle pause repeatedly or restart a chapter after skipping;
losing focus pauses it without automatically resuming on focus return.
Playing and paused films have no overlaid keyboard legends or hidden Back
hit area; the normal pause indicator and story captions remain.

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

`tests.test_cutscene_covers` compares all nine reconstructed images with RGB
hashes independently obtained from the supplied crops, verifies the updated
16:9 title and checks reuse of the cover cache. `tests.test_menu_animation`
checks elapsed-time motion and frame deadlines. Gallery regressions cover edge
bounce, elastic drag, reverse input, exact retained-display pixels and child
input/lifecycle behavior. `tests.test_display_refresh` checks monitor/device
selection, current-mode frequency, Windows ABI sizes and failure fallbacks.
Scheduler tests include the paint-idle phase, timer cancellation and a simulated
120-to-240 Hz monitor change. Synthetic scene callbacks cover
the first click, double-click binding and trailing release without pausing or
changing the underlying game. Physical desktop double-click timing is not part
of the shared-desktop suite.
