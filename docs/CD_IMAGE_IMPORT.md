# CD image import verification

Verified on 2026-11-12 following [Crinkem's report in issue 9](https://github.com/Pessegos/prince-of-persia-2-macintosh-native/issues/9).
The report describes importing an original Prince of Persia CD Collection
through ISO creation followed by an HFSExplorer volume export.

## Direct ISO check

An archived hybrid PC/Mac CD Collection image linked from
[PoPUW's CD Collection listing](https://www.popuw.com/download2.html) was
checked independently of the reporter's physical disc:

- Size: 29,329,408 bytes.
- SHA-256: `6934420aee86190804fe97c8d1fd0d9b2993f560c85225e73459ab24229842f7`.
- ISO 9660 primary volume descriptor at sector 16 (2,048-byte sectors).
- HFS volume starts at byte 47,616; its master directory block is at 48,640.
- Macintosh application `vers:1` identifies version 1.0.
- All 25 required resource files and the application resource fork were read
  directly with the existing HFS reader. Every resource payload matches the
  project's preserved recovery reference. Whole resource-fork files differ,
  so this is not a claim of byte-identical files or identical metadata.
- Full `tools.extract_assets` completed successfully into an isolated output
  directory, including scenery, animation, enemy profiles and audio
  (574 audio files, 454,974,261 bytes).

No HFS reader change was needed. The setup window now lists `.iso` and `.dmg`
alongside the existing extensions. For this CD image, selecting the ISO after
step 4 of the issue guide avoids the HFSExplorer conversion entirely.

## Validation and limits

Focused tests cover raw/wrapped HFS, a synthetic hybrid ISO at this volume
offset, ISO without HFS rejection, selection/import of ISO and DMG, extraction,
the worker process and Windows distribution. Dependency, Ruff, recovery
catalogue and whitespace checks also pass.

The full extraction can be repeated without replacing installed assets:

```powershell
.venv\Scripts\python.exe -m tools.extract_assets YOUR_CD.iso --output rendered\cd-import-check
```

This verifies one archived mastering, not every physical CD edition. No live
game, emulator or packaged EXE was launched. The tests use synthetic data;
the CD image and generated assets are ignored local files and are not shipped.
Compressed DMG, ISO-only DOS media and raw 2,352-byte CD sector dumps are not
supported formats. A different failing disc should first be checked for its
HFS partition offset, catalog extents and complete Macintosh resource set.
