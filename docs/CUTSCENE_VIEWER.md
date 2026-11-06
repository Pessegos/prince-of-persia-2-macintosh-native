# Cutscene Viewer

The F1 menu opens a horizontal collection of complete story chapters. The F3
tools offer a shortcut to the same collection. Three cards are visible at a
time; Left/Right, the mouse wheel and the side arrows browse the chapters.
Clicking a card selects it, and Play or Enter starts it. Locked chapters show
a generic numbered card; neither their image nor their story title is drawn.

The catalog in `pop2/cutscenes.py` includes the opening, voyage after level 1,
discovery after level 3, carpet flight after level 5, the throne vision in
level 8, the horse ride after level 9 and the flight after level 13. These are
port chapter labels. Recurring tree scenes, the gameplay demo and attract
credits are not part of the collection. Adding an implemented story program
to the catalog gives it a card and a replay automatically; scenes started
through `start_story_scene` also consult that catalog when unlocking.

## Collection and existing saves

The opening is available immediately. Other chapters unlock when the normal
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
replay. Existing low-level navigation/thumbnail tests retain direct access to
their model, while the public F3 activation regression now checks the isolated
chapter viewer and rejects its former destructive seek behavior.
