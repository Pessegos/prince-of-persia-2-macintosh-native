# F3 Playback Gallery

Playback in the tabless F3 hub opens a full-viewport visual browser, covering
the entire 510x384 game image including the bottom HUD/status strip. The hub
label has no ellipsis: its chevron already indicates another page. Part
destinations still come from the imported programs.
This is a host development aid, not a recovered Macintosh menu.

The dropdown groups the narrative into Opening (prologue, titles and palace
story) and After Level 1 (the voyage and arrival). Extras follows the story
groups and contains the recorded demo and credits. Later level stories can
add their own chronological groups without expanding every opening chapter
into a top-level dropdown item. Absolute playback indices and timing remain
unchanged. Descriptive part labels are host-authored navigation names based on
the original TEXT:27000 entries and scene content, not official game titles.
Voyage parts use Departure, Stowaway, Dream and Storm without repeated prefixes.

## Navigation

The header contains Back, previous/next sequence, the sequence dropdown, and
previous/next page when needed. Each page contains up to six real snapshots,
with centered captions in reserved areas below the images. The original
bitmap font wraps to two lines without overlapping another image or clipping
descenders. Caption areas also accept hover/click. Cyan marks only the actual
playing part, captured when F3 opens; browsing a new group/page does not invent
a current scene. The keyboard's pending selection is white and hover is gold.
Live gameplay has no fake current cutscene.
Clicking a thumbnail seeks directly through the existing playback dispatcher.
With gallery focus, Left/Right move one part and Up/Down move three; Enter
plays the selection. Mouse wheel and page arrows move six parts at a time.
The page count appears beside the page controls.

The footer offers the optional debug status checkbox (with a tooltip), Next
part, Play and Resume. Next part keeps the imported global playback order,
including sequence boundaries. Tab visits only visible controls. Dropdowns
take hit-test priority over thumbnails. Back/Escape returns to tools without
playing; a further fresh Escape closes F3. Held activation cannot both open
the gallery and seek. The previous explicit pause state is restored after
playing or resuming.

## Artwork And Isolation

`pop2/playback_preview.py` runs private, silent IntroPlayer/CreditsPlayer
instances using the original resource bitmaps, palettes, strings and scene
instructions. Sampling stops at the next part and selects a visible image
rather than an intervening black fade. Titles are sampled during their own
animation. Recorded demo thumbnails use the imported actor records and
private level scenery; the arrival destination uses its own level artwork.
No live scene player, actor, gate, audio engine or game clock is reused. The
global random state is restored after generation.

Generation is lazy per sequence, not at application startup or F3 opening.
The same validated local RGB archive mechanism as the map stores previews in
`assets/.developer-cache/playback-N.zip`. Its content fingerprint invalidates
outdated program/artwork/code. Cache writes are atomic and optional; damaged
or stale archives rebuild. Full 510x384 source frames supply the displayed
thumbnails at fitted window resolution, not enlarged tiny menu screenshots.
The map's bounded size cache and partial Tk photo uploads also serve gallery
hover, including popup/tooltip restoration and removal of old highlights.
F8 still captures the clean game instead of the developer overlay.

## Verification

`tests/test_playback_preview.py` covers lazy generation, every imported part,
visible native artwork, lossless disk reuse, global RNG/live-world isolation,
pagination/group selection, mouse/keyboard gaps and direct activation,
Back/Escape, key-repeat protection, pause restoration, wheel paging and real
Tk photo equivalence to full redraw at four viewport sizes. Caption/image
regions, exact bitmap-ink preservation, full HUD coverage and actual-current
versus pending-selection colors have focused regression tests. Existing attract,
playback-navigation, menu, map, screenshots and pause tests remain applicable.
