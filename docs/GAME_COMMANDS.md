# Game Commands

The Macintosh application resource fork lists the normal game commands in
MENU 401 (File) and MENU 403 (Game). The Windows port uses Alt in place of
Command, with the requested exception of Alt+Enter for fullscreen. It does
not bind Alt+Q, Alt+F or the redundant Alt+E. F1 opens the in-game command menu; F2 retains the
development menu.

| Original command | Port shortcut | Status |
| --- | --- | --- |
| New Game | Alt+N | Confirmation, default Cancel |
| Restart Level | Alt+R | Latest checkpoint or level start |
| Save Game | Alt+S | Disabled; save system not yet recovered |
| Open Game | Alt+O | Disabled; save system not yet recovered |
| Sound | Alt+T | Master audio toggle |
| Ambient Music | Alt+M | Ambient tracks only |
| End Game | Not bound | New Game already returns to the introduction |
| Hall of Fame | Alt+H | Disabled until scoring/frontend exists |
| Version | Alt+V | Port information, not the original game's version |
| Full Screen | Alt+Enter | Aspect-preserving nearest-neighbor scaling |

The version key is handled in CODE 2:4838-486a rather than relying on the
Edit menu's V entry. Pause and gameplay bindings are unchanged.

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
