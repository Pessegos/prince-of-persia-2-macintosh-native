# Prince of Persia 2 Macintosh Native (WIP)

A work-in-progress native Windows port of the Macintosh version of Prince of
Persia 2. The goal is to preserve the original game's look, movement and gameplay
without requiring a Macintosh emulator.

It uses the original artwork, animation sequences and level data, with gameplay
logic being recovered from the Macintosh executable through reverse engineering.

## Run

On 64-bit Windows, install Python 3.10 or newer with Tcl/Tk support, then
double-click `Launch.cmd`.
The launcher prepares a local `.venv` and installs its dependencies on the first run;
internet access is needed for that installation. It does not change your
global Python installation.

Original game files are not bundled. At the first launch, select your Macintosh
Prince of Persia 2 disk image. The importer extracts the resources, enemy data
and audio, then starts the game. Subsequent launches use those local files without
asking for the disk image again.

Compatible images contain an HFS volume, the four named resource files below,
the `Prince of Persia 2` application, `DigiSnd.dat` and `MIDISnd.dat`.
Raw or wrapped `.hfs`, `.hfv`, `.dsk`
and `.img` files can be used; the extension alone does not establish compatibility.
Files whose catalog or resource forks need HFS extents-overflow records are not
supported by this importer.

[PoPOT's Macintosh release page](https://www.popot.org/get_the_games.php?game=2_Mac)
lists an English disk image: [download `pop2.hfs` (17 MB)](https://www.popot.org/get_the_games/software/pop2.hfs).
Select the downloaded file when the launcher asks for a disk image.
PoPOT is an independent archive; availability there is not a redistribution
license. This project does not host or automatically download the game image.

For manual setup:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run `.\.venv\Scripts\python.exe run_game.py` to import the game files or play.
`python run_game.py --check` checks dependencies and required files without
opening a window; `--check-dependencies` checks only the Python installation.
An activated virtual environment can use the shorter `python` commands below.

The project folder is self-contained: no sibling tools, ROM, Macintosh system
disk or other development folders are needed. Import creates these local files
in `assets/`:

- `Prince.rsrc`
- `Kid.rsrc`
- `Guard.rsrc`
- `Rooftops.rsrc`
- `enemy_profiles.json`
- `audio/` (original samples, MIDI, instruments and prepared level-1 music)

The same import can be performed without a file picker:

```powershell
.\.venv\Scripts\python.exe -m tools.extract_assets "C:\path\to\pop2.hfs"
```

The importer leaves the disk image unchanged and does not retain the game
executable or any ROM or system files. Generated game files are ignored by Git.
Existing installations without audio will ask for the disk image once more.
Music is prepared during import using the bundled `smssynth` renderer and the
game's Macintosh instruments, not a General MIDI sound bank. Playback uses SDL
through pygame; the game does not generate diagnostic recordings.

## Controls

| Key | Action |
| --- | --- |
| Left / Right | Run, turn, or move in sword mode |
| Shift + Left / Right | Careful step |
| Up | Jump, climb, or block in sword mode |
| Direction + Up | Forward or running jump |
| Down | Crouch, descend a ledge, or sheath the sword |
| Shift | Retain a ledge grip |
| Ctrl | Draw the sword or attack |
| Esc | Pause; text keys or arrows resume (not mouse clicks, modifiers, F-keys, multimedia, Insert/Delete/Home/End/Page Up/Page Down or system shortcuts) |
| Alt + Enter | Toggle fullscreen |
| F1 | Game menu with command shortcuts |
| Alt + N | New game, after confirmation |
| Alt + R | Restart from the latest checkpoint or level start |
| Alt + T | Toggle all sound |
| Alt + M | Toggle ambient music |
| Alt + V | About the port |
| F2 | Developer menu: screen selection and peaceful mode |
| F5 | Restart the opening encounter |
| Any key after death | Retry from the checkpoint or level start |

The game menu accepts mouse, arrows and Tab/Shift+Tab; Enter/Space activates
the selected option. New game defaults to Cancel. Escape backs out without
discarding progress. Save/Open, End game (return to intro) and Hall of Fame
are shown disabled until those systems are implemented. There are no
Alt+Q or Alt+F commands; fullscreen remains Alt+Enter.

The developer menu accepts mouse, Tab/Shift+Tab and arrow navigation.
Left/Right moves between `Go to screen` and `Resume`; Enter/Space activates
a control. Escape closes the dropdown before closing the menu.
Screen jumps also set the latest checkpoint along the selected route.
`python run_game.py --peaceful` starts with guards disabled and terrain intact.

## Current Progress

The level-1 route is playable from the palace window to boarding the ship.

- Ten level-1 route screens and the right-hand secret room.
- Window escape, locomotion, ledge movement, sword combat and rooftop guards.
- Harbor scenery, water falls and the departing ship's original boarding sequence.
- Death/retry flow and the level-1 checkpoint after the screen-7 descent.
- Four original rooftop music tracks and movement, combat, glass and water sounds.
- Death music with playback-dependent restart messages; pause also pauses audio.
- Losing window focus pauses the game and audio. Returning focus does not resume automatically.
- Original 512x384 viewport, aspect-preserving nearest-neighbor scaling.
- Movement at 12 fps and ordinary sword combat at 10 fps.

The intro, level-ending scenes and later levels are not yet implemented.
Boarding the ship currently ends at a level-complete screen. This remains a WIP;
the recovered rules do not yet cover every original collision or input branch.

## Development

```powershell
python -m pip install -r requirements-dev.txt
python -m ruff check --select F,E9 .
python -m unittest -q tests.test_bootstrap tests.test_extract_assets tests.test_extract_audio tests.test_audio tests.test_mac_resources tests.test_run_game tests.test_setup_game tests.test_recovery_catalog tests.test_project_layout tests.test_window_controls tests.test_game_menu.GameMenuModelTests
python -m tools.recovery_catalog --check
```

These checks run without original game files and are used in GitHub Actions.
After importing the game files, run the full gameplay suite with
`python -m unittest discover -s tests -t . -q`.

Python 3.10 with Pillow 10.4 and 12.3 has been tested. The gameplay suite needs
the generated files in `assets/`, but not external research folders.
An optional developer test re-extracts enemy
data from the original Macintosh game files and checks that it matches
`assets/enemy_profiles.json`. Without those original files, this test is skipped.
To enable it, set `POP2_RESEARCH_DIR` to a recovery directory containing
`resource_forks/`.
The routine catalog can also be rebuilt from that directory with
`python -m tools.recovery_catalog --source PATH_TO_RECOVERY`.

The old isolated animation comparison remains available through
`python -m pop2.scene_prototype --no-guard`. It is a test harness with simplified
opening-room boundaries, not the playable terrain mode.

The launcher stays in the project root. Runtime modules, tests and research
utilities are separate:

```text
Launch.cmd          Windows launcher
bootstrap.py        Local environment setup
run_game.py         Installation checks and game entry point
pop2/               Game runtime and first-run import window
tests/              Regression tests
tools/              Game-file import and recovery utilities
docs/               Technical notes and routine catalog
assets/             Locally imported game files (not bundled)
vendor/             Import-time MIDI renderer and its license notices
.github/            Automated checks
```

[Behavior map](docs/BEHAVIOR_MAP.md), [rule recovery index](docs/RECOVERY_INDEX.md),
[collision notes](docs/COLLISION_RECOVERY.md), [enemy AI notes](docs/AI_RECOVERY.md),
[harbor and ship notes](docs/HARBOR_RECOVERY.md),
[audio notes](docs/AUDIO_RECOVERY.md), [death/checkpoint notes](docs/REBIRTH_RECOVERY.md),
[game commands](docs/GAME_COMMANDS.md),
[development history](docs/DEVELOPMENT_HISTORY.md).

Source addresses in comments identify the recovered Macintosh routine behind a
condition. Passing tests cover those documented subsets, not full-game parity.

## License

Newly written port code is licensed under [MIT](LICENSE). Original game content
is not covered by that license. See [third-party notices](THIRD_PARTY_NOTICES.md)
for the scope and dependency licenses.
