<p align="center">
  <img src="docs/github readme/pop2-mac-banner.png"
       alt="Prince of Persia 2 Macintosh"
       width="1200">
  </p>
<br/>
<br/>


I'm working on a native Windows reimplementation of the Macintosh version of *Prince of Persia 2: The Shadow & the Flame*. It uses the original game's graphics, animations, levels and sounds.

The gameplay is being rebuilt in Python for now, with the help of Codex. To understand how the original game works, Codex is reverse-engineering the Macintosh executable and I'm doing a ton of side-by-side playtesting, comparing both versions and fixing differences as I find them.

I'm trying to stay as close to the original as possible, while still making some changes and improvements where they make sense.

<br/>

## Contents

- [Gameplay Status](#gameplay-status)
- [Features & Improvements](#features--improvements)
  - [Game Menu (F1)](#game-menu-f1)
  - [Port & Themes](#port--themes)
  - [Save & Load](#save--load)
  - [Controls](#controls)
  - [Screenshot Gallery (F2)](#screenshot-gallery-f2)
  - [Cutscene Viewer)](#cutscene-viewer)
  - [Developer Tools (F3)](#developer-tools-f3)
  - [Overlapping Sound Effects](#overlapping-sound-effects)
  - [Ledge Masking](#ledge-masking)
  - [Lava Overhaul](#lava-overhaul)
  - [Cave Ambience](#cave-ambience)
  - [Game Artwork](#game-artwork)
  - [Stone Gates](#stone-gates)
  - [Gate Sounds](#gate-sounds)
- [Other Quality of Life Improvements](#other-quality-of-life-improvements)
- [Download & Play](#download--play)
- [Controls](#controls)
- [Development](#development)
- [License](#license)

<br/>

## Gameplay Status

Levels 1-9 are playable from start to finish, including the horse cutscene leading into Level 10.

Levels 10-13 can be played through too, but they're not as polished as the earlier levels yet.

Level 14 is in the game as well and can be reached and explored, but it still needs a lot more work.

<br/>

# Features & Improvements

## Game Menu (F1)

The original Macintosh version uses the system menu bar for its File and Game options. Since that isn't available in the Windows port, I added an in-game F1 menu to provide similar functionality.

It brings together the game commands, saves, controls, Cutscene Viewer and Hall of Fame. Settings have their own Options page, so everything in the main menu fits without scrolling.

### Original Macintosh

<p>
  <img src="docs/github readme/macintosh-file.png" alt="Original Macintosh File menu" width="350">
  <img src="docs/github readme/macintosh-game.png" alt="Original Macintosh Game menu" width="350">
</p>

<br/>

### Port & Themes

I wanted the menus to feel like part of the game itself, so I gave them different pixel art themes inspired by each area, from the palace and desert to the caverns, ruins and temple. The frames, textures and colours change depending on where you are, and the themes carry over to the other menus too.

<img src="docs/github readme/menus/menu-themes.gif" alt="The F1 menu in its palace, desert, cavern, ruins and temple themes" width="700">

### Options

Here you can adjust the sound and display settings, enable extras like Cave Ambience, or disable the original copy protection. I also added sounds for navigating the menus, which can be turned off separately from the game's audio.

<img src="docs/github readme/menus/options.png" alt="Options page with Sound, Display and Game settings" width="700">

<br/>

## Save & Load

The F1 menu includes a Save & Load system with named saves, previews, and options to rename, overwrite or delete them.

Saving follows the original game's checkpoint system. Loading a save takes you back to the beginning of the level or the last activated checkpoint, and the preview shows exactly where you'll resume.

In widescreen windows, the page makes room for a larger preview, with the save's name and details beside it.

<img src="docs/github readme/menus/save-load-preview.gif" alt="Creating and renaming a save, loading the level start and a saved checkpoint, with cavern, ruins and palace menu themes" width="850">

<br/>

## Controls

Keys and controller buttons can be changed through the F1 menu (or Alt+K).

Each action can have up to two keys, and controllers work both in-game and throughout the menus. I've tested it with an Xbox controller, but PlayStation controllers should work too, although I haven't tested them myself.

I tried to make the controller designs fit the game's pixel art style, taking inspiration from the palace in Level 1, with different designs depending on which controller is connected. For the keyboard, I went with a classic 90s look.<br/>
I'm pretty happy with how they turned out!

### Keyboard & Controllers

<img src="docs/github readme/menus/controls.gif" alt="Controls page: the keyboard, then the Xbox controller, then a DualSense connected in its place" width="700">

### Changing Keys and Buttons

<p>
  <img src="docs/github readme/menus/controls-remap-keys.png" alt="Changing keyboard keys" width="350">
  <img src="docs/github readme/menus/controls-remap-buttons.png" alt="Changing controller buttons" width="350">
</p>

<br/>

## Cutscene Viewer

The Cutscene Viewer lets you revisit the story through a gallery of illustrated chapter covers. The opening chapters are available from the start, and the rest unlock as you reach them in the game. The collection is kept with each save.

New chapters reveal their covers and titles in a pixelated animation, with a brief glint across the picture. I picked the scene and crop for each cover to give every chapter its own little illustration.

Click a chapter to watch it, or browse with the keyboard or controller. Replaying a cutscene leaves your current game where it was.

Cutscenes can also be paused and resumed at any time with Esc, whether you're replaying them here or watching them during the game.

<img src="docs/github readme/menus/cutscene-reveal.gif" alt="Cutscene Viewer at the level 1 harbor: the introduction's three chapters reveal their covers and titles one after another, The Palace Escape plays and pauses, and the shelf scrolls to the later chapters, still under their veils" width="850">

<br/>

## Screenshot Gallery (F2)

The F2 menu lets you browse and manage your screenshots directly in-game, with previews, resolution and folder options. In widescreen windows, it shows four columns of thumbnails and a larger preview.

You can even delete screenshots by tossing them into the lava, Minecraft style. The picture falls into the pool and burns away as it sinks, with a fire sound to go with it.

Pressing F8 takes a clean PNG screenshot without menus or overlays, while Shift+F8 captures the screen as it appears, including menus and paused scenes. A small notification appears whenever a screenshot is saved.

<img src="docs/github readme/menus/screenshots-burn.gif" alt="Taking a screenshot with F8, browsing the widescreen Screenshot Gallery, capturing it with its menus and tossing that picture into the lava, where it burns away" width="850">

<br/>

## Developer Tools (F3)

The F3 Developer Tools menu was originally made to help me with playtesting during development, rather than as a feature for players.

But I think it turned out so well that I might include it in the final release as an optional feature, hidden behind a cheat mode like the original Macintosh one: hold down the 1, 2 and 3 keys while the game starts, and you get the message "You are worthy of the powers of Jaffar!".

### Game Map

An interactive map that allows browsing through levels and teleporting directly to individual rooms, without having to play through the entire level.

<img src="docs/github readme/menus/developer-map.gif" alt="Developer Tools - Game Map: browsing rooms and teleporting through the caverns, the ruins and the palace, with the menus in each level's theme" width="700">

### Cutscene Viewer

The developer version of the Cutscene Viewer makes every chapter already available for testing, without changing the collection in the current game.

<br/>

## Overlapping Sound Effects

Different sound effects can now play at the same time. <br/> In this example, the pressure plates finish their sound while gates move, and the skeletons can rattle over the gate sound.

<br/>

<table>
  <tr>
    <th width="50%">Macintosh</th>
    <th width="50%">Port</th>
  </tr>
  <tr>
    <td valign="top"><video controls width="100%" src="https://github.com/user-attachments/assets/9d0cd65e-20e7-4138-a1e0-38e2f7418d8d"></video></td>
    <td valign="top"><video controls width="100%" src="https://github.com/user-attachments/assets/4b82128e-c92a-434c-bc1c-4cacdf9c8a3e"></video></td>
  </tr>
</table>

<br/>

## Ledge Masking

In the Macintosh version, parts of the Prince's body can show through the stone while climbing up or lowering himself from a ledge. I improved the masking in both animations to make the movement around the ledge look more natural.

<br/>
<p align="center">
<img src="docs/github readme/ledge-masking-before-after.gif" alt="Before and after comparison of the Prince descending and climbing a ledge, with improved masking around the stone">

<img src="docs/github readme/ledge-left-fall-ruins-before-after.gif" alt="Before and after comparison of the Prince falling off a ledge to the left, with the rear leg masked by the diagonal floor edge">
</p>

*Slowed down for comparison.*

<br/>

## Lava Overhaul

The lava in the original Macintosh release looks pretty botched, especially around the upper edges. I've checked several playthroughs, including one reportedly recorded on real hardware, and they all have the same issue.

I honestly think something went wrong with the rendering and somehow made it into the final release. Reconstructing the lava from the original Macintosh assets produces something that looks much closer to what I believe was intended, but even then, it still looks a bit plain and out of place compared to the rest of the game.

So I decided to take it a step further and give the lava a proper overhaul, with more detailed edges and depth, taking some inspiration from the DOS version.

The animation also required some careful masking to prevent overlapping, and I fixed a brief pause in the original animation loop.

<p align="center">
<img src="docs/github readme/lava-macintosh-reconstructed-dos-port.gif" alt="Comparison of the original Macintosh lava, reconstructed Macintosh lava, DOS lava and overhauled lava" width="800">
</p>

<br/>

## Cave Ambience

I wanted the caverns to feel a little more alive, so I added optional visual ambience throughout levels 3-5. Torches and lava cast a subtle, shifting glow with a little heat haze, while water drips from stalactites and ash and dust float through the air.

<p align="center">
  <img src="docs/github readme/cave-ambience-preview.gif" alt="Cave ambience off for two seconds, then on for four seconds, as droplets land on the cavern floor and in lava" width="700">
</p>

The Prince also kicks up dust when running or landing, along with gates, doors and falling floors. I tried to keep everything subtle and close to the game's original palette.

<p align="center">
  <img src="docs/github readme/cave-ambience-action.gif" alt="Cave ambience off and on as the Level 4 entrance closes and the Prince runs a short distance to the left" width="700">
</p>

The effects are off by default, but can be enabled through F1 > Options or with Alt+A. The setting is saved between sessions.

<br/>

## Game Artwork

### Desert Artwork

In the original Macintosh version, the Room 2 artwork in Level 2 sits 20 pixels lower than Room 1, so the horizon, water and hills don't line up. This looks especially odd in the Game Map, and would also cause problems if I ever wanted to experiment with wider aspect ratios.

So I moved the artwork up and retouched the sand, rocks, water and sky gradient to make the two screens connect naturally.</br>The trees had to be cut down a bit for the greater good.

<p align="center">
  <img src="docs/github readme/desert-artwork/desert-artwork.gif" alt="Macintosh and Port comparisons of Room 1 and 2 from Level 2" height="772">
</p>
<br/>

### Cavern Artwork

Cavern artwork has been touched up across levels 3-5 to soften harsh column shadows and blend abrupt joins between walls and floors. This also includes the floor edges around column bases and dart traps, and the rectangular outlines around cavern doorways.

Here are a few examples:

<p align="center">
  <img src="docs/github readme/cavern-artwork/cavern-artwork-preview.gif" alt="Macintosh and Port comparisons of column shadows, wall and floor joins, floor edges around column bases and traps, and wall shading" width="690">
</p>

<h3 align="center">
  <a href="docs/CAVERN_ARTWORK_COMPARISONS.md">View artwork comparisons →</a>
</h3>

<br/>

## Stone Gates

The stone gate closing animation in the Macintosh version looks pretty rough, especially when crushing the Prince. The DOS version handles this much better, with a nice bouncing effect when the gate slams shut, so I recreated its closing animation frame by frame for the port and adjusted the timing of the original slam sound to match.

<br/>
<p align="center">
<img src="docs/github readme/stone-gate-macintosh-dos-port.gif" alt="Stone gate closing animation comparison between Macintosh, DOS and the port" >
</p>
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
    <td valign="top"><video controls width="100%" src="https://github.com/user-attachments/assets/b9b49599-d2ff-4411-9f2a-811f425bf877"></video></td>
    <td valign="top"><video controls width="100%" src="https://github.com/user-attachments/assets/7bdcae83-9034-4c46-8428-6ba3882bb9c0"></video></td>
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
- The transition from the horse cutscene into the temple now has a fade-in, with the cutscene music flowing smoothly into the temple music. In the original, the music just cuts abruptly from one track to the other.

<br/>

## Download & Play

Download the latest Windows build from the [Releases](https://github.com/Pessegos/prince-of-persia-2-macintosh-native/releases/latest) page.

Extract the ZIP to a folder and run `PoP2Mac.exe`. No Python installation is required.

On the first launch, you'll be asked to select your original Macintosh Prince of Persia 2 disk image. If you don't have one, [PoPOT's Macintosh release page](https://www.popot.org/get_the_games.php?game=2_Mac) lists an English version: [download `pop2.hfs` (17 MB)](https://www.popot.org/get_the_games/software/pop2.hfs).

The file picker lists `.hfs`, `.hfv`, `.dsk`, `.img`, `.iso` and `.dmg` images. These must contain the original Macintosh HFS volume; compressed DMG images and DOS-only CDs are not supported.

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

| Key               | Controller        | Action                                           |
| ----------------- | ----------------- | ------------------------------------------------ |
| Left / Right      | D-pad, left stick | Run, turn or move in sword mode                  |
| Up                | A, up             | Jump, climb or block with the sword              |
| Down              | B, down           | Crouch, descend or sheath the sword              |
| Shift + Direction | RB/RT + direction | Careful step or manual turn with the sword drawn |
| Shift             | RB, RT            | Hold onto ledges                                 |
| Ctrl              | X                 | Draw the sword or attack                         |
| Space             | Y                 | Show the time left / skip supported cutscenes    |
| Esc               | View              | Pause the game                                   |
| F1                | Menu              | Game Menu                                        |
| Alt + P           |                   | Options                                          |
| Alt + K           |                   | Controls                                         |
| Alt + C           |                   | Cutscene Viewer                                  |
| Alt + Enter       |                   | Toggle fullscreen                                |
| F2                |                   | Screenshot Gallery                               |
| F3                |                   | Developer Tools                                  |
| F8                |                   | Take a clean screenshot                          |
| Shift + F8        |                   | Take a screenshot including menus and overlays   |

These are the defaults. Keys and controller buttons can be changed in F1 > Controls. PlayStation and Nintendo controllers use the same positions (for example, A is Cross on PlayStation).

The F1 menu also includes the rest of the shortcuts for starting or restarting a game, saving and loading, the Hall of Fame and version info. Audio, fullscreen and the other settings are in F1 > Options.

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
