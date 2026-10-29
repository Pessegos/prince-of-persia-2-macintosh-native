# Windows portable builds

These packages are development builds. Preparing a package does not declare
the game complete or publish a release. The first public alpha is planned
after the current input-queue milestone and a playtest of the packaged game.
Later releases should group meaningful playable improvements; research-only
temple modules do not require a new executable release.

## Build locally

Use 64-bit Windows and Python 3.12 in a separate build environment. The source
launcher continues to support Python 3.10+, but Python 3.10.0 has a bytecode
inspection bug that breaks PyInstaller analysis. Do not patch the user's
global Python installation to work around it.

```powershell
py -3.12 -m venv rendered/build-venv
rendered/build-venv/Scripts/python.exe -m pip install -r requirements-build.txt
rendered/build-venv/Scripts/python.exe -m tools.prepare_windows_bootloader
rendered/build-venv/Scripts/python.exe -m tools.build_windows --version dev
```

The ZIP and SHA-256 checksum are written to `rendered/windows/`. Unique build
directories preserve diagnostics and never overwrite a previously imported
installation. Build dependencies are pinned separately from source development.
`BUILD-INFO.json` records the commit, dirty status, source digest, interpreter,
packager and runtime dependency versions. A public release should use a clean,
checked commit; local dirty builds are identified as such.

Preparing the import bootloader needs Visual Studio C++ build tools (already
available on the Windows Actions runner), or an explicit MinGW compiler bin
directory supplied via `--compiler-directory`. This compiler is needed on the
build machine only. The preparation downloads the pinned PyInstaller source,
verifies its SHA-256, and builds with `--no-cfg` as required by Unicorn's
documented callback/longjmp incompatibility with Control Flow Guard. It does
not change Windows security settings or the installed PyInstaller bootloaders.
Only the import helper and its pool workers use custom bootloaders; the game keeps
the stock CFG-enabled one. Build and smoke checks verify that distinction.

The package contains the windowed `PoP2Mac.exe`, the background console helper
`PoP2Mac-tools.exe`, the windowed pool entry `PoP2Mac-worker.exe`, `_internal`,
instructions and license notices. The game launches the helper without a console;
the pool entry also avoids console flashes when new workers start.
The importer and cache warmup use explicit helper modes; multiprocessing spawn
is handled before app argument parsing. Original game files, imported audio,
disk images, saves and user settings are excluded and the output is audited.

Bundled support art and the MIDI renderer live under `_internal`. Imported
assets, diagnostics and the default user data live beside the executables in
`assets/` and `rendered/`. Extract the ZIP to a writable folder. Source-mode
paths and the `POP2_USER_DATA` override keep their previous behavior.

## Verify the ZIP

```powershell
rendered/build-venv/Scripts/python.exe -m tools.smoke_windows rendered/windows/PoP2Mac-dev-windows-x64.zip --report rendered/windows-smoke.json
```

This extracts to a temporary folder containing spaces, removes Python and
dependency directories from PATH and checks both executables, native libraries,
hidden Tk startup, bundled support art, multiprocessing and a native M68k
callback/stop. The native check reproduces the CFG failure without original
game files. No imported game data is needed.
It does not prove compatibility with every Windows machine; test the release
on another PC or clean Windows VM as well.

For a local original-image integration check, add `--image PATH_TO_IMAGE.hfs`.
That runs the actual hidden first-run UI through cancellation and full import,
validates the resulting installation, renders the intro and levels 1-9, and
prepares map caches through the frozen helper. All generated files and user
data stay inside the disposable test directory. Never upload the disk image
or the imported installation as build artifacts.

Do not enable `faulthandler` in the packaged entry. Unicorn 2.1.4 uses Windows
vectored exception handling for demand paging; Python's fault handler can
intercept those handled exceptions and disrupt initialization during import.
The compatibility issues are documented by
[PyInstaller](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html)
and [Unicorn](https://github.com/unicorn-engine/unicorn/issues/2264).
Normal Python exceptions still go to the application/import logs.

## GitHub builds and releases

The **Windows portable build** workflow runs manually from Actions, or for a
`v*` tag. It builds and checks a ZIP without original game files, then uploads
the ZIP, checksum and smoke report as an Actions artifact. It does not run for
every ordinary commit and does not publish a release or request write access.

When a milestone is ready:

1. Test the exact clean commit, including the packaged first-run import locally.
2. Create the version tag and let the workflow build/check that commit.
3. Download the artifact and playtest that ZIP. Actions' outer artifact ZIP
   contains the actual portable ZIP and its checksum.
4. Create a draft GitHub prerelease, attach the portable ZIP and checksum, and
   write notes describing playable changes and known limitations.
5. Publish after review. Keep prior releases available and use a new version
   for a hotfix, rather than silently replacing an existing release's ZIP.

Full source code remains available normally. No reply to an issue, version tag
or public release is created merely by running the build workflow.
