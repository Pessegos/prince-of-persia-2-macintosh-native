# Game Commands

The Macintosh application resource fork lists the normal game commands in
MENU 401 (File) and MENU 403 (Game). The Windows port uses Alt in place of
Command, with the requested exception of Alt+Enter for fullscreen. It does
not bind Alt+Q, Alt+F or the redundant Alt+E. F1 opens the in-game command menu,
F2 opens the integrated screenshot gallery, and F3 opens Developer Tools.

Screenshots are a port-only feature, not a recovered Macintosh command.
F8 saves the current clean game framebuffer as PNG without altering playback or
pause, then briefly displays `Saved screenshot as <filename>` in the game's bitmap
font. F2's gallery offers `Capture PNG`, an in-game folder picker (including
typed/pasted paths), and 1x-4x integer sizes. The original 510x384
viewport and HUD are retained; host padding, menus and pause overlays are not.
Shift+F8 instead saves the presented game framebuffer, including visible menus,
Developer Tools, pause overlays and existing notices. It uses the same folder,
native viewport crop and integer scale. The new capture notification is drawn
only after the PNG is saved, and neither shortcut closes menus or resumes play.
Local preferences and the default output folder live under ignored `rendered/`.
Capture does not require Developer Tools; F3 remains separate development UI.
Neither screenshot controls nor Developer Tools add a command row to F1.
F2 toggles the screenshot gallery, and Escape closes it after cancelling any
folder/deletion dialog; both restore the
previous pause state. Switching among F1, F2 and F3 also preserves that state.
The gallery keeps the folder's last listing and the pictures it has read
(`SHARED_READS`, by path, time and size) for its next opening, so it opens
with its thumbnails while the folder is read again in the background. A
moving list is sent to Tk without comparing it with the previous frame.
While F1 is shown (the game is paused) `pop2/menu_warmup.py` prepares the
pages it leads to, in steps of a few tens of milliseconds between Tk's
events: the screenshots folder's listing, newest thumbnails and lava, every
save read once, the theme's frames for the saves and screenshots pages and
the Cutscene Viewer's covers. It stops when F1 gives way to another page or
closes, so the first opening of each page is as quick as the later ones.

Developer Tools prepares its level and playback lists before the animation
clock starts. Navigation reads scene-program metadata without decoding
cutscene images or rendering other levels' rooms. The first F3 press therefore
uses the same cached lists as later presses; artwork is loaded when playback
or a level jump actually needs it. Menu presentation remains synchronous.

| Original command | Port shortcut | Status |
| --- | --- | --- |
| New Game | Alt+N | Confirmation, default Cancel |
| Restart Level | Alt+R | Latest checkpoint or level start |
| Save Game | Alt+S | In-game slots; bank checkpoint or level-entry progress |
| Load Game | Alt+O (also Alt+L) | Resume a save at its checkpoint or level entry; F1 shows Alt+O |
| Sound | Alt+T | Master audio toggle |
| Ambient Music | Alt+M | Ambient tracks only |
| End Game | Not bound | New Game already returns to the introduction |
| Hall of Fame | Alt+H | The five best times left when Jaffar falls; a victory adds a named row |
| Version | Alt+V | Port information, not the original game's version |
| Full Screen | Alt+Enter | Aspect-preserving nearest-neighbor scaling |

Controls (Alt+K) is also port-only: it shows the keyboard or controller
layout, lets each action take two chosen keys or buttons, and switches
controller input on or off. Esc and F1 keep their meaning. Chosen keys reach
the game as the original keys, so no command behaves differently. Choices are
kept in `preferences.json`. See [CONTROLS.md](CONTROLS.md).

With God mode enabled in F3 Developer Tools, `+` and `-` add or remove one
minute from the campaign clock after it starts. `Alt+Shift+T` adds one health
point, increasing the maximum capacity when the meter is full (up to 12).
The campaign clock is capped at 300 minutes (five hours).
Hold `+` or `-` to repeat the minute adjustment. `Alt+R` removes cheated hearts
when restarting at the level opening; a reached checkpoint keeps the capacity
it recorded. `Alt+T` continues to toggle sound.

Cave Ambience (Alt+A) has no original counterpart. It is a port-only item, off
by default. Unlike Sound and Ambient Music, the choice is kept between sessions
in `preferences.json`, beside the saves. See `docs/CAVERN_ARTWORK.md`.

Dragging a window edge preserves the 510:384 game viewport: changing width
also changes height, rather than only adding letterbox space. Fullscreen
and maximized windows still fit the undistorted viewport inside the available
display. The Windows WM_SIZING constraint includes title/frame and optional
debug-status dimensions, follows Tk's recreated outer HWND across fullscreen,
and reads cached dimensions without reentering Tcl from a native callback.

The version key is handled in CODE 2:4838-486a rather than relying on the
Edit menu's V entry. Pause and gameplay bindings are unchanged.

Save/Load use an integrated slot browser and a versioned `.pop2save` progress
format, not the original Macintosh save-file format. Loading resumes at the
activated checkpoint or normal level entry, never the exact saved position.
The browser includes named saves, previews, dates, smooth scrolling and confirmation
before overwriting/loading/deleting. Existing version-one snapshots remain
readable with the new resume rules. Saves live outside the project directory.
A cancelled or invalid load leaves the running game intact; cutscenes/death/
transitions disable saving without disabling Load. Details and validation
coverage are in [SAVE_GAME.md](SAVE_GAME.md).

New Game is deliberately a host confirmation rather than an immediate
restart. Confirming clears the checkpoint and replays the introduction;
Restart Level shares the existing rebirth path, without requiring death.
Space skips the introduction to the window escape. Neither action changes
the sound settings or peaceful-mode preference. The isolated animation test
harness still restarts directly at the window, without a frontend.

Menus freeze simulation and audio, operate on the native framebuffer and
use the game's NFNT. Mouse hit testing follows viewport scaling and
letterboxing. Closing a menu consumes held keys until release. An activation
key cannot repeat into a newly opened confirmation, and focus loss leaves
the game paused even if the menu was opened while running.

Master mute sets both SDL channel volumes to zero without stopping their
playback clocks. This preserves the playback-dependent death prompt timing.
Disabling ambient music cancels only ambient requests/playback; death cues
and sound effects remain active. Both preferences survive level restarts
within the session; they are not yet persisted to disk.

Regression coverage: `tests.test_game_menu`, `tests.test_audio`,
`tests.test_development_menu`, `tests.test_window_controls` and
`tests.test_rebirth`. Menu-model and audio tests run without game assets;
scene tests exercise imported resources and actual Tk event bindings.

## Screenshot Gallery

The gallery shows PNGs from the selected destination folder, newest first, with
a scrolling two-column thumbnail grid, an aspect-preserving large preview, dimensions and
file size. Capture selects the new PNG after it is successfully written; Refresh
discovers external file changes. Thumbnails always appear in pairs; the large
preview is slightly smaller to leave room for the original F8 hint below the panel.
Preview borders follow the fitted image,
without adding black letterboxing, cropping or stretching the screenshot. The
lava-asset delete control has a hover label and requires explicit confirmation,
defaults to Cancel and verifies the file's timestamp/size before deleting it.
The button uses the edited, transparent `pop2/screenshot_lava.png` surface rather
than the in-level rock rim. Its 22-frame, 12 fps loop uses an independent enhanced
`LavaPool`, preserving the +5/-1 bubble offset and gapless wrap. Frames are prepared
once on the worker and cached at the display size. Only the button's changed pixels
are uploaded during idle animation; gameplay stays paused, and dialogs freeze the
icon. Closing the gallery cancels its timer. In-level artwork and lava rules are unchanged.
The lava sits directly on the panel without a visible button border. Pointer hover
or keyboard focus adds a muted dark-red fill; opening the confirmation brightens
that fill. The original hit area, hover label and confirmation remain unchanged.
Drag a thumbnail onto the lava to request deletion. A small movement threshold
keeps ordinary thumbnail clicks unchanged, and dropping elsewhere, Escape or
leaving the canvas cancels the drag. The confirmation retains the dragged file
and the held thumbnail draws above the lava until deletion is confirmed. The
liquid occludes it only during the subsequent sinking animation. The target stays fixed
even if another capture arrives. Cancel never changes files; after successful
confirmed deletion, the frozen thumbnail shrinks and sinks into the lava for
0.65 seconds. Failed deletions never play the effect. The animation also works
for the last PNG in the folder, does not advance gameplay and is discarded when
the gallery closes. The normal click/keyboard delete path is still available.
The lava remains visible and animated even before the first capture or after the
last PNG is deleted. Clicking it with no selected screenshot is a harmless no-op.
While a thumbnail is dragged, the window shows it in a canvas item of its own over
the page (`ScreenshotGallery.held_overlay`), so a step of the pointer only moves
that item. Redrawing and comparing the whole page for each step took about 25 ms
at 3440x1440 (5 ms in a 1020x768 window); a step now takes well under 1 ms at any
size. The page is redrawn only when the drag starts, reaches or leaves the lava,
or the lava's own frame changes, and the page's picture stays RGBA: only the parts
sent to Tk are converted. The cursor and the page's canvas coordinates are set
only when they change, since Tk repaints the whole canvas or item even for an
unchanged value. The held picture now lies over the "Take Screenshots with F8"
hint where the two meet, at the page's lower right.
The delete button and its "Delete screenshot" label are shown in a small canvas
item of their own, just over the page and under a held picture. Each copy into
the page's photo made Tk look over all of that photo again, about 2 ms at
3440x1440, and the lava changes twelve times a second. The label is drawn on
each frame instead of being kept in the page's cached surface, so reaching or
leaving the lava with a picture redraws no page: it took 50-90 ms at 3440x1440,
depending on the theme, and now takes about 5 ms; a frame of the lava took 9-35
ms and now takes about 4. The cached surface takes the thumbnail list as last
drawn once the list is still, with what it was drawn from
(`ScreenshotGallery.list_state`: thumbnails, scroll, selection and focus), so a
frame whose list has not changed neither draws nor compares it, and the theme's
sign is laid again only over what was drawn again.
In the ruins and spider themes the sign now stays off the large picture, as the
first drawing of the page always kept it: the later frames used to lay it over
the picture's pixels that had the page's colours, and over the empty preview
while a picture was still being read.
The delete confirmation and the burn after it are quicker too. A drawing of the
page from scratch starts from the game's picture darkened once for the page
(`ScreenshotGallery.backdrop`), and a dialog darkens the page through a table of
the levels compositing gives (`dimmed`). Opening or closing a dialog changes all
of the page, so the window puts it into its photo without comparing it; while a
dialog stays open over the same page, only the dialog is compared. A confirmed
deletion takes the picture out of the list at once, and the folder's listing
that follows changes nothing when it brings nothing new; the large picture the
page shows next is read while the confirmation is open. The burn asks for a new
frame on its twelve steps a second rather than sixty, and falls inside the
lava's own canvas item. At 3440x1440, opening the confirmation took 127 ms and
takes about 55; a pointer step over it 16-20 ms, now about 7-11; the deletion
with the redrawing it brought while the picture burned, 106 + 85 + 66 ms, now
about 45 in all. Most of what is left is Tk preparing a whole 3440x1440 photo
for the screen when all of the page darkens or lightens (about 25-30 ms). In
the spider theme the lava's ground no longer shows the fur in a page's first
frame only, for the twelfth of a second until the lava moved.
Damaged, missing or oversized images report an unavailable preview without
closing the menu. Decoding is limited to PNGs of at most 32 million pixels / 128 MiB.

`With menus` changes the gallery's Capture command only. F8 always remains clean,
and Shift+F8 always includes the displayed UI. The checkbox is remembered within
the session; scale and folder retain their existing persisted settings. Both
shortcuts work during menus, intros and paused play. Gallery capture feedback is
inline, so it never covers the preview or footer; errors outside F2 use an in-game
notice instead of a Windows message box.

The folder picker supports Home, parent navigation, Windows drives, Default,
scrollable child folders, keyboard focus and a selectable path field with
Ctrl+A/C/X/V, Shift selection and Home/End. Relative paths are resolved against
the displayed directory. Browsing and cancellation do not create directories or
write preferences. Only `Use folder` creates a missing destination and remembers
it; failures keep the original destination. Default navigates to the original
output folder and still requires `Use folder` to confirm.
`Change folder` chooses the destination inside the game; `Open folder` opens the
current destination in the Windows Explorer for sharing or managing PNGs. Opening
is an explicit asynchronous command, does not change preferences or create a
missing folder, and reports failures inside the gallery. The F8 hint stays hidden
while a folder or deletion confirmation is open.
Folder and file labels compose missing Latin accents using the native bitmap
letters, with a system-font fallback for other Unicode characters. This is local
to the screenshot gallery and does not modify the original Macintosh font assets.

Directory reads, image decoding and explicit folder/deletion operations run on a
single daemon worker; Tk state and presentation are updated on the UI thread.
Stale directory results cannot replace the currently requested directory. Caches
bound decoded images, fitted previews, glyphs and dimmed modal backgrounds.
Small thumbnails and full previews have separate decoding budgets (64 and 3);
queued thumbnails that are no longer visible are skipped. Smooth scrolling only
redraws visible rows and compares/uploads the thumbnail strip, reusing the static
panel and large preview. Neither rendering nor hit testing loops over the full library.
Pointer hover does not rescan folders, and menu redraws never advance gameplay.
Closing F2, changing menus or destroying the game closes the worker and cancels
its polling callback. The renderer draws directly at the fitted window/PNG size
and reuses the Tk photo, uploading only changed pixels.

`tests.test_screenshot_gallery` covers this library without imported assets;
scene tests additionally cover real capture pixels, clipboard paths, persistence,
pause isolation, HD presentation and worker/callback cleanup.
