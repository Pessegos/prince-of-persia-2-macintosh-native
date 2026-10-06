# Prince of Persia 2 Macintosh Native (WIP)

A work-in-progress native Windows port of the Macintosh version of Prince of
Persia 2. The goal is to preserve the original game's look, movement and gameplay
without requiring a Macintosh emulator.

It uses the original artwork, animation sequences and level data, with gameplay
logic being recovered from the Macintosh executable through reverse engineering.

## Run

Install Python 3.10 or newer with Tcl/Tk support, then double-click `Launch.cmd`.
The launcher prepares a local `.venv` and installs Pillow on the first run;
internet access is needed for that installation. It does not change your
global Python installation.

Original game files are not bundled. At the first launch, select your Macintosh
Prince of Persia 2 disk image. The importer extracts the resources and enemy
data, then starts the game. Subsequent launches use those local files without
asking for the disk image again.

Compatible images contain an HFS volume, the four named resource files below,
and the `Prince of Persia 2` application. Raw or wrapped `.hfs`, `.hfv`, `.dsk`
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

The same import can be performed without a file picker:

```powershell
.\.venv\Scripts\python.exe extract_assets.py "C:\path\to\pop2.hfs"
```

The importer leaves the disk image unchanged and does not retain the game
executable or any ROM or system files. Generated game files are ignored by Git.

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
| Esc | Pause; any new key or mouse click resumes |
| Alt + Enter | Toggle fullscreen |
| F2 | Developer menu: screen selection and peaceful mode |
| F5 | Restart the opening encounter |

The developer menu accepts mouse, Tab/Shift+Tab and arrow navigation.
Left/Right moves between `Go to screen` and `Resume`; Enter/Space activates
a control. Escape closes the dropdown before closing the menu.
`python run_game.py --peaceful` starts with guards disabled and terrain intact.

## Current Progress

Development currently covers part of level 1.

- Seven supported level-1 route screens and the right-hand secret room.
- Window escape, locomotion, ledge movement, sword combat and rooftop guards.
- Original 512x384 viewport, aspect-preserving nearest-neighbor scaling.
- Movement at 12 fps and ordinary sword combat at 10 fps.

Audio and intro movies are not yet implemented.

## Development

```powershell
python -m pip install -r requirements-dev.txt
python -m ruff check --select F,E9 .
python -m unittest -q test_bootstrap test_extract_assets test_mac_resources test_run_game test_setup_game test_recovery_catalog
python recovery_catalog.py --check
```

These checks run without original game files and are used in GitHub Actions.
After importing the game files, run the full gameplay suite with
`python -m unittest discover -q`.

Python 3.10 with Pillow 10.4 and 12.3 has been tested. The gameplay suite needs
the generated files in `assets/`, but not external research folders.
An optional developer test re-extracts enemy
data from the original Macintosh game files and checks that it matches
`assets/enemy_profiles.json`. Without those original files, this test is skipped.
To enable it, set `POP2_RESEARCH_DIR` to a recovery directory containing
`resource_forks/`.
The routine catalog can also be rebuilt from that directory with
`python recovery_catalog.py --source PATH_TO_RECOVERY`.

The old isolated animation comparison remains available through
`python scene_prototype.py --no-guard`. It is a test harness with simplified
opening-room boundaries, not the playable terrain mode.

- `scene_prototype.py`: player control, simulation order and scene composition.
- `window_controls.py` / `game_ui.py`: Tk window, modal input and menu rendering.
- `sequence_runtime.py` / `animation_data.py`: original animation data and interpreter.
- `terrain.py`: supporting-foot coordinates, collisions, ledges and room links.
- `combat.py` / `opponent_generation.py`: combat, guard AI and reinforcements.
- `mac_resources.py`: standalone resource-fork and HFS readers.
- `bootstrap.py` / `setup_game.py` / `extract_assets.py`: local environment and
  first-run game import.

[Behavior map](BEHAVIOR_MAP.md), [rule recovery index](RECOVERY_INDEX.md),
[collision notes](COLLISION_RECOVERY.md), [enemy AI notes](AI_RECOVERY.md),
[development history](DEVELOPMENT_HISTORY.md).

Source addresses in comments identify the recovered Macintosh routine behind a
condition. Passing tests cover those documented subsets, not full-game parity.

## License

Newly written port code is licensed under [MIT](LICENSE). Original game content
is not covered by that license. See [third-party notices](THIRD_PARTY_NOTICES.md)
for the scope and dependency licenses.
