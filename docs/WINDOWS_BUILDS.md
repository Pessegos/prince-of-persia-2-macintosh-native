# Windows portable builds

These packages are development builds. Public alphas can be released while
input handling, enemy AI and later levels are still being completed; release
notes must describe the current playable scope and known limitations.
Preparing a package does not automatically publish it. Releases should group
meaningful playable improvements, rather than follow every commit or
research-only temple module.

## Build locally

Use 64-bit Windows and Python 3.12 in a separate build environment. The source
launcher continues to support Python 3.10+, but Python 3.10.0 has a bytecode
inspection bug that breaks PyInstaller analysis. Do not patch the user's
global Python installation to work around it.

```powershell
py -3.12 -m venv rendered/build-venv
rendered/build-venv/Scripts/python.exe -m pip install -r requirements-build.txt
rendered/build-venv/Scripts/python.exe -m tools.prepare_windows_runtime
rendered/build-venv/Scripts/python.exe -m tools.build_windows --version dev
```

The ZIP and SHA-256 checksum are written to `rendered/windows/`. Unique build
directories preserve diagnostics and never overwrite a previously imported
installation. Build dependencies are pinned separately from source development.
`BUILD-INFO.json` records the commit, dirty status, source digest, interpreter,
packager and runtime dependency versions. A public release should use a clean,
checked commit; local dirty builds are identified as such.

The game uses Python 3.12 and PyInstaller's stock CFG-enabled, one-folder
launcher. The import/cache helpers use the unmodified official Python 3.13.17
embeddable distribution from python.org, with pinned CPython 3.13 wheels in
`requirements-import.txt`. No compiler or custom import bootloader is needed.
Preparation checks the official archive's pinned SHA-256 and the valid Python
Software Foundation Authenticode signatures on both interpreters and their
Python DLLs. The runtime manifest records every file checksum; packaging checks
them again. The executable names and signed bytes are preserved.

The package contains the windowed `PoP2Mac.exe`, `_internal`, instructions and
license notices. There are no custom `PoP2Mac-tools.exe`/`PoP2Mac-worker.exe`
executables. The game starts `_internal/python/python.exe` without a console;
pool children use the official signed `pythonw.exe`. `_internal/worker` contains
the ordinary application modules and a fixed portable-root marker. Isolated
mode and the runtime's `_pth` exclude the user's Python installation and
environment; pip is not shipped and no runtime download is needed to play.
The importer and cache warmup use explicit helper modes and native Windows
multiprocessing. Original game files, imported audio,
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
dependency directories from PATH and checks the launcher, signed runtime, native libraries,
hidden Tk startup, bundled support art, multiprocessing and a native M68k
callback/stop. No imported game data is needed for those checks.
It does not prove compatibility with every Windows machine; test the release
on another PC or clean Windows VM as well.

For a local original-image integration check, add `--image PATH_TO_IMAGE.hfs`.
That runs the actual hidden first-run UI through cancellation and full import,
validates the resulting installation, renders the intro and levels 1-13, and
prepares map caches through the signed helper. All generated files and user
data stay inside the disposable test directory. Never upload the disk image
or the imported installation as build artifacts.

`--reference-assets PATH` optionally compares the imported JSON exports with
a local source import. `--defender` records active real-time protection before
and after the test, queries applicable path exclusions, requests a custom scan
and checks for detections belonging to this disposable bundle. An exclusion
query denied to a non-administrator is explicitly reported as unavailable,
never treated as verified. The standalone `tools.check_windows_defender` also
offers `--require-exclusions` for an elevated verification. These checks do not
alter Defender settings or add exclusions. Keep the report's limitations when
describing results; a clean scan on one PC does not guarantee every Defender
version or cloud heuristic will accept a future build.

This packaging replaces the custom import bootloaders used in the first two
alphas after the [first-run Defender report](https://github.com/Pessegos/prince-of-persia-2-macintosh-native/issues/4).
The detection was reported during asset generation rather than ordinary play.
The signed runtime removes that custom-bootloader execution path; it is a
mitigation with functional/scan evidence, not a universal antivirus guarantee.

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
