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
| Hall of Fame | Alt+H | Disabled until scoring/frontend exists |
| Version | Alt+V | Port information, not the original game's version |
| Full Screen | Alt+Enter | Aspect-preserving nearest-neighbor scaling |

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
even if another capture arrives. Cancel never changes files; after successful
confirmed deletion, the frozen thumbnail shrinks and sinks into the lava for
0.65 seconds. Failed deletions never play the effect. The animation also works
for the last PNG in the folder, does not advance gameplay and is discarded when
the gallery closes. The normal click/keyboard delete path is still available.
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
