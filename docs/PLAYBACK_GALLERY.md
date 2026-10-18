# F3 Playback Gallery

Playback in the tabless F3 hub opens a full-viewport visual browser, covering
the entire 510x384 game image including the bottom HUD/status strip. The hub
label has no ellipsis: its chevron already indicates another page. Part
destinations still come from the imported programs.
This is a host development aid, not a recovered Macintosh menu.

The dropdown groups the narrative into Opening (prologue, cloud titles and palace
story, followed by the recorded demo and credits) and After Level 1 (the voyage
and arrival). Later level stories can
add their own chronological groups without expanding every opening chapter
into a top-level dropdown item. Absolute playback indices and timing remain
unchanged. Descriptive part labels are host-authored navigation names based on
the original TEXT:27000 entries and scene content, not official game titles.
Voyage parts use Departure, Stowaway, Dream and Storm without repeated prefixes.

## Navigation

The header contains Back, previous/next sequence, the sequence dropdown, and
previous/next page when needed. Each page contains up to six real snapshots,
with larger 152x114 thumbnails and compact centered captions just below the images.
The original bitmap font is reduced to 75 percent and can wrap to two lines
without overlapping another image or clipping
descenders. Caption areas also accept hover/click. Cyan marks only the actual
playing part, captured when F3 opens; browsing a new group/page does not invent
a current scene. The pending selection becomes white only after explicit arrow-key
navigation; opening a page or browsing a group does not highlight its first item.
Mouse movement clears that keyboard marker, and hover is gold.
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
the gallery and seek. Play, thumbnail activation and Next part start the destination
immediately, even if F3 was opened from pause. Resume/Escape without seeking restores
the previous explicit pause state.

## Artwork And Isolation

`pop2/playback_preview.py` runs private, silent IntroPlayer/CreditsPlayer
instances using the original resource bitmaps, palettes, strings and scene
instructions. Sampling stops at the next part and selects a visible image
rather than an intervening black fade. Active reveals finish at the current
operation boundary, before a later caption clear or animation can replace the
scene. Only the actual title operation receives the six-second cloud sample;
its retained animation object must not advance subsequent palace scenes.
Recorded demo thumbnails use the imported actor records and
private level scenery; the arrival destination uses its own level artwork.
No live scene player, actor, gate, audio engine or game clock is reused. The
global random state is restored after generation.

Generation is lazy per visible page (at most six sources), not per entire
sequence or at application startup/F3 opening. Neighboring program snapshots
share one private forward replay; their results are pixel-identical to independent
seeks, including reveals, captions and title animation.
The same validated local RGB archive mechanism as the map stores previews in
`assets/.developer-cache/playback-N.zip`. Its content fingerprint invalidates
outdated program/artwork/code. Cache writes are atomic and optional; damaged
or stale archives rebuild. Full 510x384 source frames supply the displayed
thumbnails at fitted window resolution, not enlarged tiny menu screenshots.
The four most recently used page atlases and their fitted images persist for
the session, including across closing/reopening F3. Revisiting a page therefore
does not reload sources or repeat Lanczos scaling. Least-recently-used pages
are discarded to keep large-window image memory bounded.
The map's bounded size cache and partial Tk photo uploads also serve gallery
hover, including popup/tooltip restoration and removal of old highlights.
F8 still captures the clean game instead of the developer overlay.

## Verification

`tests/test_playback_preview.py` covers lazy generation, every imported part,
visible native artwork, lossless disk reuse, global RNG/live-world isolation,
page-only loading, bounded LRU reuse across reopenings, shared replay equivalence,
pagination/group selection, mouse/keyboard gaps and direct activation,
Back/Escape, key-repeat protection, autoplay versus pause restoration, wheel paging and real
Tk photo equivalence to full redraw at four viewport sizes. Caption/image
regions, complete scaled caption ink, full HUD coverage and actual-current
versus pending-selection colors have focused regression tests. Synthetic reveal/clear
boundaries and every post-title palace picture/caption also have regression coverage. Existing attract,
playback-navigation, menu, map, screenshots and pause tests remain applicable.
