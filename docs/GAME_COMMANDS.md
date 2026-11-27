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
the Cutscene Viewer's covers. It also draws the page that Save game opens
(Load game when saving is unavailable) into a window-sized photo, so that
page appears without being drawn again. It stops when F1 gives way to another
page or closes, so the first opening of each page is as quick as the later ones.

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

Ambient Effects (Alt+A; first called Cave Ambience) has no original counterpart.
It is a port-only item, off by default, for the caves and the ruins. Unlike Sound
and Ambient Music, the choice is kept between sessions in `preferences.json`,
beside the saves. See `docs/CAVERN_ARTWORK.md`.

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
The browser includes named saves, previews, dates and smooth scrolling. Double-click
a save in the Load tab to resume it immediately. Overwrite, Load game and Delete
still ask for confirmation. Existing version-one snapshots remain
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

Passing the pointer over a menu's options costs about as much in a large
window as in a small one. The game menu, its options and controls, its
dialogs, the copy challenge and Developer Tools are drawn at the game's
resolution. For each option the pointer reached, the window made a new photo
of its whole size, which Tk then painted again in full: about 35 ms at
3440x1440, against 19 ms in a 1020x768 window. Now only the bands of rows that
changed are enlarged, exactly as the whole page's enlargement shows them
(`nearest_axes`, `changed_bands`), and written into the window's photo
(`WindowControls.patch_native_menu`) by Tk's own function (`put_patch`, see
below). Copying a patch from another photo made Tk check the alpha of the
whole photo, about 2 ms at 3440x1440 for each patch. The photo is moved
only when its place changes (`keep_photo_at`), since even unchanged
coordinates make Tk paint all of it.

The paused game under a menu is not drawn again for what only moves the
menu's focus or leads to another of its pages: the pointer, the keys, the
wheel. `ScenePrototype.draw_menus` keeps the picture it drew the menu over;
`WindowControls.redraw_menu` draws the menu again over it, while the game is
paused and no other picture (a cutscene played from the menu) was shown since.
Anything else that changes, a loaded save or a setting, still draws all of it.
Under the tools the pointer now shows the same picture as a whole drawing: it
was drawn over the captures' picture, which keeps the prompt to restart that
the window leaves out under a menu. A step over the menu, its options or its
controls took 11-13 ms at 3440x1440 and takes 7-10; in a 1020x768 window
8-11 ms, now 4-7.

The menu's own drawing keeps what does not change with the focus. The font
keeps each line it drew (`MacintoshFont.text`, a copy for each caller): letter
by letter, the labels took most of a page's time. The page's ground, the game's
picture under the theme's veil with the panel laid over it, is kept for the
picture `draw_menus` holds (`menu_theme.hold`, `menu_theme.ground`); the
picture is held while it is shown under the menu, and nothing draws into it.
The controls page lays its keyboard as one picture (`keyboard_picture`), drawn
once for each set of key colours and lock lights, rather than each key in turn,
and each controller callout keeps its pixels (`callout_pixels`). The sign of
the ruins and the spider compares each pixel as one number. Drawing a page took
2-2.3 ms (menu, options), 3-5 ms (controls) and 1.4 ms (tools), up to 7 ms
under the spider; it takes 0.3-0.7 ms, up to 1.5 ms under the spider. A step
over the menu or its options takes about 5 ms at 3440x1440 and 2.5-3 ms at
1020x768, one over the controls 3-4 ms and 2.6 ms. The rest was Tk's copy of
the changed rows. Drawn by the previous code and this one, 4176 pages (the menu, its
options, dialogs, controls and tools, eight themes, every focus, three pictures
under them, each drawn twice) were the same.

The changed rows go into the window's photo through `Tk_PhotoPutBlock`, the
function in which Tk's photo commands end and which Pillow calls for a whole
photo (`pop2.tk_photo.put_pixels`). Given as data, Tk 8.6 read a patch at about
26 ns a pixel (1.8 ms for two options at 3440x1440); copied from another photo,
a patch made Tk check the alpha of the whole photo. Called directly, with the
pixels marked opaque, the function takes them where they are, about 5 ns a
pixel, most of it Tk preparing them for the display. It is taken from the Tk
this process loaded, only for Tk 8.6, whose structure it is given, and only
once two pixels it wrote into a photo of its own read back as written;
otherwise `put_patch` sends data or copies as before. The changed bands are
found by comparing the page's packed pixels whole, a fifth of the time of
finding the box of what changed first, and each band is enlarged from its own
pixels, columns first. A step over the menu or its options took about 5 ms at
3440x1440 and takes 2.5-2.7, one over the controls 3.8 and 2.5, over the tools
6 and 2.6; at 1020x768 2.6-2.8 ms, now 1.4-1.8. The saves and screenshots pages
send their patches the same way, but their time is their own drawing (6.5-8 ms
at 3440x1440): each step copies the window-sized page they keep.

The copy challenge covers the whole window, yet the game was drawn under it at
each of its 60 frames a second, and the same page again between its fades.
The game is no longer drawn under it, and a frame is drawn only when the fade
changes it; a symbol the pointer or the keys light is drawn at once. A frame
took about 6 ms; between fades nothing is drawn, and a lit symbol takes 4-5 ms
instead of 7-8.

The saves and screenshots pages are drawn at the window's resolution. They kept
a cached page for each focus, so each button, save or picture the pointer
reached drew the whole page again and compared the whole window. They now keep
one cached page, draw over it the controls the focus lights, and compare only
those controls and the list rows or cells the focus left and reached. The saves
list is pasted rather than composited, since it starts from its own opaque
ground. At 3440x1440 a step over the saves page took about 63 ms and now takes
about 7. A step over the screenshots page took 15-45 ms and now takes about 9.
In a 1020x768 window both take 2-4 ms.

Nor do they copy that page for each step any more. The window asks for each
page in place (`in_place`), at its own resolution and at the game's: a page
that differs from the last one drawn so only where the focus, the scroll, the
lava or the delete button's label changed is that same picture, drawn over
again in those parts alone, each with the theme's sign laid over it alone
(`within`), and the page lists the parts it drew (`redrawn`) with the pixels
they had. The window compares only those, and an outline that changed colour,
around a save or a picture the focus left or reached, goes to Tk as its four
sides (`changed_parts`): at 3440x1440 its box is about fifteen times as many
pixels. The lava's own item takes only what changed in it, through the same
Tk function. The screenshots page draws as before while a picture is held or
burning; its label is taken away by the surface's pixels under it, which never
had it. A toast makes a new picture of the saves page: the parts drawn over in
the page the window showed are then sent with what the comparison finds. At
3440x1440 a step over the saves page took about 7 ms and takes 1.3; over the
screenshots page about 8, now 1.6. Under the ruins both took about 10 ms and
take 1.3-1.5; under the spider 22 and 14, now 1.6 and 2.7: the sign was laid
over the whole panel for each step. At 1020x768 both take about 1 ms. Over
three random sequences of pointer steps, keys, wheel, lava frames, a dialog
and the other tab (eight themes, four window sizes), 7040 pages drawn in
place, the window's and the game's resolution's, were the same as the pages
drawn afresh.

The dialogs over those pages are drawn in place too (`kept_dialogs`): the
saves page's confirmations and its name dialog, the screenshots page's delete
confirmation and its folder chooser. A dialog that shows the same as the last
one drawn so but for what the pointer or the keys light is that same picture,
with the buttons they lit or left drawn again over themselves, and the folder
list again where a folder's row did; `redrawn` lists those boxes alone. A new
name, caret, folder list or target draws the dialog afresh, as before. Each
step had copied the darkened page and laid the dialog over it again. At
3440x1440 a step between a confirmation's buttons took about 10 ms and takes
1.6 (saves) or 1.9 (screenshots); over the folder chooser about 20, now 2.1.
At 1020x768 they take about 1 ms. Over random pointer steps, keys, typing,
wheel and the other tab (eight themes, four window sizes), 1600 pages drawn
in place, the window's and the game's resolution's, were the same as the
pages drawn afresh.

A saves dialog opens over the page kept under the list (`list_base_cache`),
darkened, rather than over that page drawn again from the game's picture, and
both darkenings go through a table of the levels compositing gives
(`menu_theme.dimmed`, which the screenshots page already used). Opening or
closing a dialog changes all of the window, which is then sent whole without
being compared with the page before, as the screenshots page did. At
3440x1440 a saves dialog took 140-185 ms to open and takes about 63, and 70-90
to close, now about 45; the screenshots page's take about 75 and 41.

The pointer's shape is the window's own cursor, not the canvas's
(`WindowControls.set_window_cursor`): the hand over a chapter, a save's name or
a room of the map, the hand or the cross of a dragged picture, the arrow, and
the hidden pointer of fullscreen play. A Tk window with no cursor of its own
shows the one of the window around it, so the canvas, and the strip of chapters
over it, show the toplevel's. Configuring the canvas, even with the cursor it
had, made Tk paint all of it again: at 3440x1440 about 8 ms, at times 30-70, for
each option the pointer reached or left where the shape changes, which the
benches of a hidden window never saw. Changing the toplevel's costs nothing to
paint. On Windows, Tk puts a cursor on the screen when the pointer moves, and
every 250 ms while it rests: one given to the window under the pointer shows at
once, the toplevel's only then. `pop2.tk_pointer.refresh_pointer` has Tk do at
once what its pointer timer does (`Tk_PointerEvent` with the point on the
screen); a pointer that did not move gets no event. In a transparent window
mapped off the screen at 3440x1440, a step from a chapter to the viewer's
arrows took 0.1 ms and 8 ms of painting, from there to a chapter 11-13 ms; both
now paint in 0.3-4 ms. Tested where the desktop is free
(`tests.desktop_exclusive`): a canvas without a cursor shows its toplevel's once
Tk updates the pointer, in the Tk in use.

Master mute sets both SDL channel volumes to zero without stopping their
playback clocks. This preserves the playback-dependent death prompt timing.
Disabling ambient music cancels only ambient requests/playback; death cues
and sound effects remain active. Both preferences survive level restarts
within the session; they are not yet persisted to disk.

Regression coverage: `tests.test_game_menu`, `tests.test_audio`,
`tests.test_development_menu`, `tests.test_window_controls`,
`tests.test_tk_pointer`, `tests.test_save_game` and `tests.test_rebirth`. Menu-model and audio tests run without game assets;
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
The burn keeps an even beat as well. The picture falls and sinks 36 times a
second (`BURN_FPS`), three frames to each of the game's twelve steps, in which
its fire flickers and sparks: in those steps alone the fall was five places,
and at the window's 60 the user found it too fluid beside the game. Its steps
were caught by a tick 60 times a second, so they lasted 70 or 88 ms in turn;
the window now waits for the burn's next frame, the lava's next frame or the
fire's sound, whichever comes first, and each step lasts its 83 ms. The burn's clock starts with its first
frame: that frame, which closes the confirmation, takes the longest to reach
the screen, and the time it took cut the picture's first place above the lava
to under half its twelfth of a second.
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
