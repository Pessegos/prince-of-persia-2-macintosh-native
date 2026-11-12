Prince of Persia 2 Macintosh Native - Windows development build

Extract the ENTIRE ZIP to a folder where you can write files, then open
PoP2Mac.exe. Keep the entire _internal folder beside it.
You do not need to install Python or the dependencies separately.

On first launch, select your original Macintosh Prince of Persia 2 disk image.
An ISO made from the hybrid PC/Mac Prince of Persia CD Collection also works;
select it directly, without converting it in HFSExplorer.
Original game resources, music and disk images are not included in this ZIP.
Import may take a minute or longer depending on the PC. Wait for it to finish,
or use Cancel to stop it safely. Later launches use the prepared local files.

This is an unfinished development build. Levels 1-9 have playable campaign
routes. Levels 10-13 are an early temple preview and are not fully playable.
Enemy AI and game rules are still being recovered and tested.
See the project's README for the current playable scope and known limitations:
https://github.com/Pessegos/prince-of-persia-2-macintosh-native

To update, close the game and extract the new ZIP to a separate folder.
Keep the previous folder as a backup. Its assets and rendered folders contain
imported files, saves, settings and screenshots; do not delete them blindly.
Asset compatibility is checked at launch and may require a fresh import.

Diagnostics: rendered/setup.log (import), rendered/game.log (launch),
rendered/error.log (window callbacks). BUILD-INFO.json identifies this build.
The import/cache helpers use the official Python Software Foundation-signed
interpreter inside _internal/python. Do not move or remove its files.
No Python installation, antivirus exclusion or security-setting change is needed.

This port's license is in LICENSE. Third-party library notices are in licenses,
_internal/*.dist-info, _internal/python and _internal/vendor/smssynth.
The original game is separate.
