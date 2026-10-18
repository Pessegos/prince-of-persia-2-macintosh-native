# Game Commands

The Macintosh application resource fork lists the normal game commands in
MENU 401 (File) and MENU 403 (Game). The Windows port uses Alt in place of
Command, with the requested exception of Alt+Enter for fullscreen. It does
not bind Alt+Q, Alt+F or the redundant Alt+E. F1 opens the in-game command menu,
F2 opens standalone screenshot controls, and F3 opens Developer Tools.

Screenshots are a port-only feature, not a recovered Macintosh command.
F8 saves the current clean game framebuffer as PNG without altering playback or
pause, then briefly displays `Saved screenshot as <filename>` in the game's bitmap
font. F2's screenshot controls show an F8 reminder and offer `Save PNG`, a native
folder picker (including typed/pasted paths), and 1x-4x integer sizes. The original 510x384
viewport and HUD are retained; host padding, menus and pause overlays are not.
Local preferences and the default output folder live under ignored `rendered/`.
Capture does not require Developer Tools; F3 remains separate development UI.
Neither screenshot controls nor Developer Tools add a command row to F1.
F2 toggles the screenshot controls, and Escape closes them; both restore the
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
| Load Game | Alt+O | Resume a slot at its checkpoint or level entry |
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
The browser includes previews, dates, twelve slots, paging and confirmation
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
