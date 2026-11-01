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

## Contents

- [Gameplay Status](#gameplay-status)
- [Features & Improvements](#features--improvements)
  - [Game Menu (F1)](#game-menu-f1)
  - [Save & Load](#save--load)
  - [Screenshot Gallery (F2)](#screenshot-gallery-f2)
  - [Developer Tools (F3)](#developer-tools-f3)
  - [Cutscene Pausing](#cutscene-pausing)
  - [Lava Overhaul](#lava-overhaul)
  - [Cavern Artwork](#cavern-artwork)
  - [Stone Gates](#stone-gates)
  - [Gate Sounds](#gate-sounds)
- [Other Quality of Life Improvements](#other-quality-of-life-improvements)
- [Run](#run)
- [Controls](#controls)
- [Development](#development)
- [License](#license)

<br/>

## Gameplay Status

Levels 1–9 are playable from start to finish, although I'm still finding and fixing differences here and there.
The horse cutscene that leads to the temple (9-10) is a bit broken.
Levels 10–13 are now in the game too. They can already be explored, with some of their mechanics working, but there's still quite a bit left to do before they're fully playable.

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

## Cavern Artwork

22 cavern rooms have been touched up to soften harsh shadows and smooth abrupt joins between scenery pieces. I also blended the odd rectangular edges around the cavern doorways into the surrounding rock.

Here are a few examples:

<p align="center">
  <img src="docs/github readme/cavern-artwork/cavern-artwork-preview.gif" alt="Cavern artwork retouches: level 3 rooms 1 and 28, level 5 room 25, and doorway edges; Macintosh and Port" width="1005">
</p>

<h3 align="center">
  <a href="docs/CAVERN_ARTWORK_COMPARISONS.md">View all 19 full-room comparisons →</a>
</h3>

<br/>

## Stone Gates

The stone gate closing animation in the Macintosh version looks pretty rough, especially when crushing the Prince. The DOS version handles this much better, with a nice bouncing effect when the gate slams shut, so I recreated its closing animation frame by frame for the port and adjusted the timing of the original slam sound to match.

<br/>
<img src="docs/github readme/stone-gate-macintosh-dos-port.gif" alt="Stone gate closing animation comparison between Macintosh, DOS and the port" >

<br/>

## Gate Sounds

I smoothed out the gate opening sound for every type. It now plays continuously and fades out gently when the gate stops.

<br/>

<table>
  <tr>
    <th width="50%">Original</th>
    <th width="50%">Corrected</th>
  </tr>
  <tr>
    <td valign="top"><video controls width="100%" src="https://github.com/user-attachments/assets/c515ea65-b26d-4a24-9eb8-73df7e1dc63d"></video></td>
    <td valign="top"><video controls width="100%" src="https://github.com/user-attachments/assets/59302ec2-5b36-4cfc-97b2-ac47dafdd015"></video></td>
  </tr>
  <tr>
    <td valign="top"><video controls width="100%" src="https://github.com/user-attachments/assets/defd1068-93d3-4b8e-abbf-ceac87edae8c"></video></td>
    <td valign="top"><video controls width="100%" src="https://github.com/user-attachments/assets/9538508f-22b0-43e5-9f8c-16faa653b446"></video></td>
  </tr>
</table>

<br/>

## Other Quality of Life Improvements

- The original Macintosh copy protection can be disabled.
- Window resizing and fullscreen scaling preserve the original aspect ratio without stretching the image.
- The game automatically pauses when switching to another window and stays paused until manually resumed.
- Confirmation before starting a new game, to prevent accidental progress loss.
- Clouds keep moving during cutscene fades, like the DOS version does.
- The level 1 screen 7-8 drop landing animation is no longer interrupted, matching the DOS version.
- Really small but the dock guards stay in standby once the Prince catches the boat, instead of switching back and forth into combat mode. More cinematic.

<br/>

## Download & Play

Download the latest Windows build from the [Releases](https://github.com/Pessegos/prince-of-persia-2-macintosh-native/releases/latest) page.

Extract the ZIP to a folder and run `PoP2Mac.exe`. No Python installation is required.

On the first launch, you'll be asked to select your original Macintosh Prince of Persia 2 disk image. If you don't have one, [PoPOT's Macintosh release page](https://www.popot.org/get_the_games.php?game=2_Mac) lists an English version: [download `pop2.hfs` (17 MB)](https://www.popot.org/get_the_games/software/pop2.hfs).

The game will then extract and prepare the necessary files. This currently takes a minute and may take longer as more content is added. I plan to optimize this process eventually to make the initial setup faster.

The original game files are not included or downloaded automatically. PoPOT is an independent archive, and the availability of the disk image there does not grant redistribution rights.

## Running from Source

If you'd rather run the game directly from the source code, you'll need Python 3.10 or newer with Tcl/Tk support.

Download or clone the repository, then run `Launch.cmd`. It will create a local Python environment and install the required dependencies automatically.

Once everything is set up, the game can also be started with:

```powershell
.\.venv\Scripts\python.exe run_game.py
```

The original Macintosh disk image is still required for the first launch.

<br/>

## Controls

| Key               | Action                                           |
| ----------------- | ------------------------------------------------ |
| Left / Right      | Run, turn or move in sword mode                  |
| Up                | Jump, climb or block with the sword              |
| Down              | Crouch, descend or sheath the sword              |
| Shift + Direction | Careful step or manual turn with the sword drawn |
| Shift             | Hold onto ledges                                 |
| Ctrl              | Draw the sword or attack                         |
| Esc               | Pause the game                                   |
| Space             | Skip supported cutscenes                         |
| Alt + Enter       | Toggle fullscreen                                |
| F1                | Game Menu                                        |
| F2                | Screenshot Gallery                               |
| F3                | Developer Tools                                  |
| F8                | Take a clean screenshot                          |
| Shift + F8        | Take a screenshot including menus and overlays   |

The F1 menu also includes the rest of the shortcuts for starting or restarting a game, saving and loading, audio controls, the Hall of Fame, version info, and fullscreen.

<br/>

## Development

Most of the game code is in `pop2/`, while `tools/` contains the asset extraction and reverse-engineering utilities. I've also kept a lot of the research and technical notes in [`docs/`](docs/).

To run the tests after setting up the project:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -q
```

Some tests require the original Macintosh game files to have been imported first.

For more details, there's the [reverse-engineering index](docs/RECOVERY_INDEX.md), [enemy AI research](docs/AI_RECOVERY.md), and [Windows build instructions](docs/WINDOWS_BUILDS.md).

<br/>

## License

Newly written port code is licensed under [MIT](LICENSE). Original game content
is not covered by that license. See [third-party notices](THIRD_PARTY_NOTICES.md)
for the scope and dependency licenses.
