Prince of Persia 2 Macintosh Native - Windows development build

Extract the ENTIRE ZIP to a folder where you can write files, then open
PoP2Mac.exe. Keep _internal, PoP2Mac-tools.exe and PoP2Mac-worker.exe beside it.
You do not need to install Python or the dependencies separately.

On first launch, select your original Macintosh Prince of Persia 2 disk image.
Original game resources, music and disk images are not included in this ZIP.
Import may take a minute or longer depending on the PC. Wait for it to finish,
or use Cancel to stop it safely. Later launches use the prepared local files.

This is an unfinished development build. Enemy AI and game rules are still
being recovered and tested; research for the temple does not enable its levels.
See the project's README for the current playable scope and known limitations:
https://github.com/Pessegos/prince-of-persia-2-macintosh-native

To update, close the game and extract the new ZIP to a separate folder.
Keep the previous folder as a backup. Its assets and rendered folders contain
imported files, saves, settings and screenshots; do not delete them blindly.
Asset compatibility is checked at launch and may require a fresh import.

Diagnostics: rendered/setup.log (import), rendered/game.log (launch),
rendered/error.log (window callbacks). BUILD-INFO.json identifies this build.
PoP2Mac-tools.exe is the background import/cache helper, not the normal launcher.
PoP2Mac-worker.exe runs its background tasks without opening console windows.

This port's license is in LICENSE. Third-party library notices are in licenses,
_internal/*.dist-info and _internal/vendor/smssynth. The original game is separate.
