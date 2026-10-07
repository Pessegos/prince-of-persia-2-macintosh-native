# Third-Party Notices

## License Scope

The [MIT license](LICENSE) applies to newly written contributions to the port:
implementation, tools, tests and documentation. Contributors license only
material they have the right to license. It does not relicense original game
content or third-party software.

## Original Game Content

The reference for this project is the Macintosh release of Prince of Persia 2.
Original game content remains the property of its respective rights holders.
This includes:

- `assets/Prince.rsrc`, `assets/Kid.rsrc`, `assets/Guard.rsrc` and
  `assets/Rooftops.rsrc`.
- `assets/enemy_profiles.json`, which contains extracted game data.
- `assets/audio/`, including original samples, instruments, MIDI and rendered music.
- Original artwork, fonts, animation sequences, level data, and other game
  tables, including extracted data embedded in code or tests.
- Any original executable, ROM, disk image, audio, movie or disassembly used
  during research or produced by extraction tools.

Resource names, routine addresses and recovery notes document the reference
material used in development; they do not establish ownership of that material.
No permission to redistribute original game content has been established for
this project. Its presence in a local installation does not grant that
permission, and the MIT license is not a substitute for it.

## Dependencies

Python dependencies are installed separately. Their licenses are independent
of this project's MIT license:

- [Python](https://docs.python.org/3/license.html): Python Software Foundation
  License Version 2, with additional notices for incorporated software.
- [Tcl/Tk](https://www.tcl-lang.org/software/tcltk/license.html): Tcl/Tk license.
- [Pillow](https://pillow.readthedocs.io/en/stable/about.html#license): MIT-CMU
  license; binary wheels include additional third-party notices.
- [pygame](https://www.pygame.org/docs/LGPL.html): LGPL; wheels include SDL
  and its dependency notices. Used for audio playback, not game logic.
- [mido](https://github.com/mido/mido/blob/main/LICENSE): MIT; MIDI parsing.
- [NumPy](https://numpy.org/doc/stable/license.html): BSD; binary wheels include
  notices for incorporated libraries.
- [Ruff](https://github.com/astral-sh/ruff/blob/main/LICENSE): MIT license;
  development tool only.

Distributions that bundle dependencies must retain their applicable license
texts and notices, including those supplied with binary packages.

## Bundled Import Tool

`vendor/smssynth/` contains the unmodified Windows MIDI renderer from
[resource_dasm](https://github.com/fuzziqersoftware/resource_dasm), with its MIT
license, and the LLVM libc++/libunwind runtime DLLs with their notices. See the
directory's README for release provenance and executable checksum. This tool
does not contain the game's sounds or instruments; it renders the user's
imported files locally during setup.
