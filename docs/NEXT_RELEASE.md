# Notes for the next release

Include these changes alongside the current game update in the next release.
These are queued notes, not a complete description of that release's playable
scope. Follow [Windows build and release preparation](WINDOWS_BUILDS.md) when
packaging it.

## Original game image import

- The default file picker now includes `.iso` and `.dmg`, alongside `.hfs`,
  `.hfv`, `.dsk` and `.img`. Choosing "All files" is no longer necessary for
  these extensions.
- The setup window shows a generic supported-images list and a clearer
  "Choose game image..." button, without naming a particular CD edition.
- Hybrid PC/Mac CD ISOs with the original Macintosh HFS game resources can
  be selected directly. The existing reader already handled the verified
  CD Collection image; no decoder change was needed. Compressed DMG and
  DOS-only images remain unsupported.
- Credit Crinkem's [CD guide in issue 9](https://github.com/Pessegos/prince-of-persia-2-macintosh-native/issues/9)
  in the release notes. The verified ISO can be selected after step 4,
  without the HFSExplorer conversion. Evidence and mastering limits are in
  [CD image import verification](CD_IMAGE_IMPORT.md).

## Game-files window

- The window says why it opened. A first import asks for the game image
  as before. When an earlier import is present but this version needs some
  files prepared again, it says "Your game files need refreshing", names the
  parts concerned (for example "the level scenery (level 7) and the audio")
  and says that saved games and settings are kept.
- The image of the last completed import is remembered in the player's
  preferences (`game_image`, beside the saves), so a new installation folder
  or a refresh offers "Use this image" without the file picker. The picker
  opens in that image's folder.
- The import lists its stages (game image, level scenery, music, story
  scenes, demo and credits, installation) with a determinate progress bar,
  the elapsed time and an estimate of the time left. The stages come from
  structured `step` events of `tools.extract_assets --progress-json`; the
  scenery's share follows the cavern export's own messages, now named
  constants in `tools.extract_caverns` and `tools.extract_slots`.
- A file that cannot be used is explained before any import starts, from
  its own signatures: an archive (zip, 7-Zip, RAR, StuffIt, BinHex...), a
  compressed DMG, a raw 2,352-byte CD dump, an HFS+ volume or a PC-only CD.
  A Macintosh disk without the game, an unsupported or incomplete copy, a
  damaged volume, a full drive (about 550 MB needed), an unwritable folder and
  unexpected failures each have their own advice. Failures of a running
  import offer the import log; unexpected ones also link to the issue page.
  Problems that can pass (full drive, unreadable file) offer "Try again".
- Unchanged: Cancel still stops the import without changing installed files,
  and the window keeps the standard Windows look. A themed look matching the
  menus remains a later, separate task for the user's decision.
