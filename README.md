<p align="center">
  <img src="docs/github readme/pop2-mac-banner.png"
       alt="Prince of Persia 2 Macintosh"
       width="1200">
<br/>
<br/>
</p>

I'm working on a native Windows reimplementation of the Macintosh version of *Prince of Persia 2: The Shadow & the Flame*. It uses the original game's graphics, animations, levels and sounds.

The gameplay is being rebuilt in Python for now, with the help of Codex. To understand how the original game works, Codex is reverse-engineering the Macintosh executable and I'm doing a ton of side-by-side playtesting, comparing both versions and fixing differences as I find them.

I'm trying to stay as close to the original as possible, while still making some changes and improvements where they make sense.

<br/>

## Gameplay Status

Levels 1-3 are playable from start to finish.

Levels 4 and 5 are available for playtesting, including the original Discovery
and tree cutscenes, story countdown, collapsing rope bridge, ceiling bars and
flying-carpet escape. The countdown starts with the first tree scene, not on
arrival in level 4. Both levels are still being refined through playtesting.

The ruins in levels 6-9 are also available for playtesting, with campaign
progression from level 5. Crawling through crevices, scythes, the upside-down
potion and sword pickups are implemented, along with the flying heads and
serpents. These levels and their enemies still need more side-by-side testing
and refinement.

Campaign progression currently stops after level 9. The temple levels (10-13)
are not playable yet, but research is already underway into their mechanisms,
enemies and special events. Recovered rules are being checked against the
original Macintosh executable before being connected to playable levels;
full collision and frame-by-frame behavior still need work.

A lot of the work so far has gone into building and refining the core gameplay systems rather than just moving through the levels. I'm hoping this groundwork will make the remaining levels quicker to implement.

Enemy AI is already working well, but there's still ongoing research into the original Macintosh executable to better understand and reproduce its more subtle behaviors.

<br/>

# Features & Improvements

## Game Menu (F1)

The original Macintosh version uses the system menu bar for its File and Game options. Since that isn't available in the Windows port, I added a small F1 menu to provide similar functionality.

The idea isn't to turn it into a full settings menu, but simply to keep things close to how they worked on the original Macintosh.

### Original Macintosh

<p>
  <img src="docs/github readme/macintosh-file.png" alt="Original Macintosh File menu" width="350">
  <img src="docs/github readme/macintosh-game.png" alt="Original Macintosh Game menu" width="350">
</p>

### Windows Port (F1)

<img src="docs/github readme/game-menu-v2.png" alt="Windows port F1 game menu" width="700">

<br/>

## Save & Load

The F1 menu includes a Save & Load system with named saves, previews, and options to rename, overwrite or delete them.

Saving follows the original game's checkpoint system. Loading a save takes you back to the beginning of the level or the last activated checkpoint, and the preview shows exactly where you'll resume.

<img src="docs/github readme/save-load-preview-v8.gif" alt="Save & Load menu" width="700">

<br/>

## Screenshot Gallery (F2)

The F2 menu lets you browse and manage your screenshots directly in-game, with previews, resolution and folder options. You can even delete screenshots by tossing them into the lava.

Pressing F8 takes a clean PNG screenshot without menus or overlays, while Shift+F8 captures the screen as it appears, including menus and paused scenes. A small notification also appears whenever a screenshot is saved.

<img src="docs/github readme/screenshots-preview-v3.gif" alt="Screenshot Gallery (F2)" width="700">

<br/>

## Developer Tools (F3)

The F3 Developer Tools menu was originally made to help me with playtesting during development, rather than as a feature for players.

But I think it turned out so well that I might just include it in the final release as an optional feature.
The idea would be to add it to the cheat mode, like the original Macintosh has. Where you hold down the 1, 2 and 3 keys at the same time when starting the game and get the message "You are worthy of the powers of Jaffar!".

### Game Map

An interactive map that allows browsing through levels and teleporting directly to individual rooms, without having to play through the entire level.

<img src="docs/github readme/developer-map-preview-v9.gif" alt="Developer Tools - Game Map" width="700">

### Playback

The Playback tab provides quick access to cutscenes, making it easier to test individual sequences.

<img src="docs/github readme/developer-playback-preview-v3.gif" alt="Developer Tools - Playback" width="700">

<br/>

## Cutscene Pausing

Cutscenes can now be paused and resumed at any time.

<img src="docs/github readme/cutscene-pause.png" alt="Paused cutscene" width="700">

<br/>

## Lava Overhaul

The lava in the original Macintosh release looks pretty botched, especially around the upper edges. I've checked several playthroughs, including one reportedly recorded on real hardware, and they all have the same issue.

I honestly think something went wrong with the rendering and somehow made it into the final release. Reconstructing the lava from the original Macintosh assets produces something that looks much closer to what I believe was intended, but even then, it still looks a bit plain and out of place compared to the rest of the game.

So I decided to take it a step further and give the lava a proper overhaul, with more detailed edges and depth, taking some inspiration from the DOS version.

The animation also required some careful masking to prevent overlapping, and I fixed a brief pause in the original animation loop.

<br/>
<img src="docs/github readme/lava-macintosh-reconstructed-dos-port.gif" alt="Comparison of the original Macintosh lava, reconstructed Macintosh lava, DOS lava and overhauled lava" width="800">

<br/>

## Stone Gates

The stone gate closing animation in the Macintosh version looks pretty rough, especially when crushing the Prince. The DOS version handles this much better, with a nice bouncing effect when the gate slams shut, so I recreated its closing animation frame by frame for the port and adjusted the timing of the original slam sound to match.

<br/>
<img src="docs/github readme/stone-gate-macintosh-dos-port.gif" alt="Stone gate closing animation comparison between Macintosh, DOS and the port" >
<br/>
I also improved the sound played while the gate opens. The original had noticeable gaps between each loop and a loud click at the end. Both issues have been fixed, allowing the sound to play continuously without those interruptions.
<br/>
<br/>
<table>
  <tr>
    <th width="50%">Original</th>
    <th width="50%">Corrected</th>
  </tr>
  <tr>
    <td valign="top"><video controls width="100%" src="https://github.com/user-attachments/assets/de1583ca-61ba-4f8c-a9d9-97d878b25fcf"></video></td>
    <td valign="top"><video controls width="100%" src="https://github.com/user-attachments/assets/527207f5-1f7b-48de-88c3-cde732a694ec"></video></td>
  </tr>
</table>

<br/>

## Cavern Artwork

I've retouched 22 rooms across the cavern levels to soften overly harsh shadows and blend abrupt joins between pieces of scenery, while preserving their original texture and detail. Entrance and exit doorway edges also blend more naturally into the surrounding rock.

<table>
  <tr>
    <td width="50%"><img src="docs/github readme/cavern-artwork/level3-room1.gif" alt="Cavern wall shadow retouch, level 3 room 1: Macintosh and Port" width="490"></td>
    <td width="50%"><img src="docs/github readme/cavern-artwork/level3-room28.gif" alt="Cavern wall shadow retouch, level 3 room 28: Macintosh and Port" width="490"></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/github readme/cavern-artwork/door-edge.gif" alt="Entrance and exit doorway edge retouch: Macintosh and Port" width="490"></td>
    <td width="50%"><img src="docs/github readme/cavern-artwork/level5-room25.gif" alt="Wall and column shadow joins, level 5 room 25: Macintosh and Port" width="490"></td>
  </tr>
</table>

[View full-room comparisons](docs/CAVERN_ARTWORK_COMPARISONS.md)

<br/>

## Quality of Life

- A dedicated in-game menu replacing the original Macintosh menu bar, with game options and settings accessible directly through F1.
- Confirmation before starting a new game, to prevent accidental progress loss.
- An integrated Save & Load browser with named saves, resume-point previews, renaming, smooth scrolling and confirmation before overwriting or deleting. The current save is highlighted and focused automatically.
- Both Alt+O and Alt+L open Load Game; the F1 menu keeps the original Macintosh Alt+O label.
- Capture clean PNG screenshots with F8, or include visible menus and pause overlays with Shift+F8.
- An in-game F2 screenshot gallery with paired thumbnails, a larger preview, capture-size settings and a folder picker supporting typed or pasted paths. Open the destination in Windows Explorer, or delete screenshots by tossing them into animated lava.
- Automatic pause on focus loss; returning to the window, mouse clicks and system or multimedia keys do not resume the game.
- You can pause cutscenes now without skipping them.
- Aspect-preserving window resizing and fullscreen scaling, without stretching the game image.
- A 0.3-second filter for rapid repeated commands in the input queue, while preserving combinations of different commands.
- Pressing Ctrl while running queues a stop-and-draw action, without requiring a second press.
- Clouds keep moving during the intro's fades, like the DOS version does.
- The level 1 screen 7-8 drop preserves the full landing and stand-up animation, matching DOS behavior instead of the abrupt interruption in the Macintosh original.
- Completely overhauled lava pools with detailed rocky edges, convincing depth like the DOS version, seamless bubbling, and properly layered splashes and particles.
- Reworked stone-gate closing and crushing animation, with a timed slam and seamless opening audio without the original gaps or end click.
- Dock guards stay in standby once the Prince catches the boat, instead of switching back into combat during the escape.
- Shift+Back with the sword drawn turns the Prince manually. Unlike the original toggle, this leaves automatic turning enabled.
- While floating, the Prince is pushed back from obstructing scenery instead of scraping along it as in the Macintosh original.
- Original copy protection is optional.


## Run

On 64-bit Windows, install Python 3.10 or newer with Tcl/Tk support, then
double-click `Launch.cmd`.
The launcher prepares a local `.venv` and installs its dependencies on the first run;
internet access is needed for that installation. It does not change your
global Python installation.

Original game files are not bundled. At the first launch, select your Macintosh
Prince of Persia 2 disk image. The importer extracts the resources, enemy data
and audio, then starts the game. The first import prepares all scenery and music
using every processor core: it takes about 20 seconds on an 8-core PC and somewhat
longer on machines with fewer cores. The window shows the current recovery step and elapsed
time; Cancel or closing the window stops the import and removes its temporary files.
Import diagnostics are saved in `rendered/setup.log`.
Subsequent launches use those local files without
asking for the disk image again.

Compatible images contain an HFS volume, the named resource files below,
the `Prince of Persia 2` application, `DigiSnd.dat`, `MIDISnd.dat`,
`NISDIGI.dat` and `NISMIDI.dat`.
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
- `Skeleton.rsrc`
- `Rooftops.rsrc`
- `Desert.rsrc`
- `Caverns.rsrc`, `caverns_entry.json`, `caverns_level4.json` and `caverns_level5.json` (independent scenery for levels 3-5)
- `Ruins.rsrc`, `Head.rsrc`, `ruins_level6.json` and `ruins_level7.json` (ruins scenery; special enemies are not generated yet)
- `TNIS1.rsrc`, `TNIS2.rsrc` and `TNIS3.rsrc` (carpet scene resources)
- `NIS.rsrc`, `NISTree.rsrc` and `Title.rsrc`
- `enemy_profiles.json`
- `intro.json` (recovered scene instructions and audio markers)
- `ending.json` (voyage after level 1)
- `discovery.json` (story sequence after level 3)
- `carpet.json` (flight between levels 5 and 6)
- `tree-1.json` through `tree-9.json` (tree scenes and timeout sequence)
- `attract.json` (original level-one demo and credits program)
- `audio/` (original samples, voices, instruments and prepared music)

The same import can be performed without a file picker:

```powershell
.\.venv\Scripts\python.exe -m tools.extract_assets "C:\path\to\pop2.hfs"
```

To reimport after an update, close the game and rerun the same command from the
project folder. It refreshes generated files in `assets/`, not your saves or
screenshots. Each separate worktree has its own imported assets.

The importer leaves the disk image unchanged and does not retain the game
executable or any ROM or system files. Generated game files are ignored by Git.
Existing installations missing the new scene resources will ask for the disk image once more.
Music is prepared during import using the bundled `smssynth` renderer and the
game's Macintosh instruments, not a General MIDI sound bank. Playback uses SDL
through pygame; the game does not generate diagnostic recordings.
The importer uses Unicorn to recover the scene coordinators' drawing and
timing calls and resolve the original recorded demo into actor states. The game
itself plays the resulting data natively, without a CPU emulator or the original
executable. Demo recovery adds time to the first import, not to later launches.

## Controls

| Key | Action |
| --- | --- |
| Space during intro | Skip to level 1 |
| Space during voyage | Skip to the level-2 arrival |
| Space during Discovery or a tree scene | Finish the scene and continue its transition |
| Gameplay key during demo or credits | Start a new game |
| Left / Right | Run, turn, or move in sword mode |
| Shift + Left / Right | Careful step when unarmed; Shift+Back turns with the sword drawn |
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
| Alt + S | Open Save Game |
| Alt + O / Alt + L | Open Load Game |
| Alt + T | Toggle all sound |
| Alt + M | Toggle ambient music |
| Alt + V | About the port |
| F2 | Screenshot gallery, folder picker, PNG size and capture |
| F3 | Developer Tools: levels 1-5, cutscene/demo playback and debug display |
| F8 | Save a clean PNG screenshot to the configured folder |
| Shift + F8 | Save a PNG including visible menus and pause overlays |
| Resume key after the death prompt | Retry from the checkpoint or level start |

The game menu accepts mouse, arrows and Tab/Shift+Tab; Enter/Space activates
the selected option. New game defaults to Cancel. Escape backs out without
discarding progress. Save and Load are implemented; saving is unavailable during
cutscenes, death and transitions. Hall of Fame remains disabled. There are no
Alt+Q or Alt+F commands; fullscreen remains Alt+Enter.
The original manual-symbol challenge is enabled by default. The F1 option
`Copy protection` disables only that challenge, not the stone puzzle.

The developer menu accepts mouse, Tab/Shift+Tab and arrow navigation.
Its level/map tools include levels 1-3 and the level-4 and level-5 playtests, including
cavern mechanisms and skeletons. Choose `2 (Stones)` to jump directly to the level-2
puzzle without replaying the beach arrival. Left/Right moves between `Go to screen`
and `Resume`; Enter/Space activates
a control. Focus the tab row to switch between `Level`, `Playback` and `Display`
with Left/Right. Escape closes the dropdown before closing the menu.
Screen jumps also set the latest checkpoint along the selected route. During
the attract cycle, only playback and display controls are available. Playback
selects a sequence first, then a story part, animated title, demo screen or
credits page. `Next part` follows playback order across sequence boundaries.
The Windows debug status bar is hidden by default; enable it in `Display`.
F2 opens the integrated screenshot gallery. `Capture PNG` (with `With menus` unchecked) or
F8 captures the game image without window borders, fullscreen letterboxing,
menus or pause overlays. The original in-game HUD remains part of the image.
Sizes range from native 510 x 384 to 4x, using nearest-neighbor integer scaling;
the default is 3x (1530 x 1152). Folder and size are remembered locally in
`rendered/screenshot-settings.json`. The default folder is `rendered/screenshots/`;
captures use Minecraft-style `PoP2_YYYY-MM-DD_HH.mm.ss.png` filenames, with a numeric
suffix if multiple screenshots are saved in the same second. They are not published
by Git.
The gallery's `With menus` option includes menus in a capture; Shift+F8 always
includes the visible UI. `Change folder` chooses the destination inside the game,
while `Open folder` opens it in Windows Explorer for sharing or editing images.
F2 or Escape closes the gallery and restores the previous pause state; Escape
first cancels an open folder picker or deletion confirmation.
`python run_game.py --peaceful` starts with guards disabled and terrain intact.

## Development

[Level loading](docs/LEVEL_LOADING.md) describes the separation between original
level data, gameplay state, scenery and the window host.
[Level transitions](docs/LEVEL_TRANSITION.md) documents the boat-to-beach sequence.
[Desert recovery](docs/DESERT_RECOVERY.md) covers the stones and manual challenge.
[Cavern recovery](docs/CAVERN_RECOVERY.md) tracks level-3 scenery and remaining mechanics.
[Level four and story progression](docs/LEVEL4_RECOVERY.md) covers Discovery,
the tree scenes, countdown and current later-level limitations.

```powershell
python -m pip install -r requirements-dev.txt
python -m ruff check --select F,E9 .
python -m unittest -q tests.test_bootstrap tests.test_extract_assets tests.test_extract_audio tests.test_extract_intro tests.test_extract_attract tests.test_recorded_game tests.test_attract tests.test_intro tests.test_audio tests.test_playback_navigation tests.test_mac_resources tests.test_run_game tests.test_setup_game tests.test_recovery_catalog tests.test_project_layout tests.test_window_controls tests.test_bitmap_presenter tests.test_game_menu.GameMenuModelTests tests.test_palettes tests.test_game_session tests.test_level_ending
python -m tools.recovery_catalog --check
python -m unittest -q tests.test_desert tests.test_caverns tests.test_loose_floors tests.test_ceiling
python -m unittest -q tests.test_screenshots
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
[intro notes](docs/INTRO_RECOVERY.md),
[demo and credits notes](docs/ATTRACT_RECOVERY.md),
[game commands](docs/GAME_COMMANDS.md),
[development history](docs/DEVELOPMENT_HISTORY.md).

Source addresses in comments identify the recovered Macintosh routine behind a
condition. Passing tests cover those documented subsets, not full-game parity.

## License

Newly written port code is licensed under [MIT](LICENSE). Original game content
is not covered by that license. See [third-party notices](THIRD_PARTY_NOTICES.md)
for the scope and dependency licenses.
