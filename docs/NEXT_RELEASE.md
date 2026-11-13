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

## Deferred launcher work

The user deferred a broader visual and usability redesign of the launcher on
2026-11-13. Keep that as a later task; it is not required for this release.
