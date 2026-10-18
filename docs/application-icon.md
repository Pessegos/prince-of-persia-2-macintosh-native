# Application Icon

The game window and first-run importer share the Macintosh Prince icon through
`pop2.app_window.create_root`. Windows also receives a stable AppUserModelID so
the game is not grouped with unrelated Python windows in the taskbar.

`pop2/icons/prince.png` is the user-supplied transparent 512 x 512 pixel-art
image, with editor metadata removed. `prince.ico` contains 16, 20, 24, 32, 40,
48, 64, 96, 128 and 256 pixel versions, all resized directly from that PNG with
nearest neighbour sampling. Other Tk platforms use 32 and 64 pixel PNG versions.

Each ICO entry is a 32-bit Windows DIB, not an embedded PNG. Tk 8.6 can otherwise
fall back to a larger PNG frame and smooth it down, even when the correct size
is present. Both the default and explicit window icon are set. Rebuild the ICO
with `python -m tools.build_app_icon`; no game assets are required.

These files are bundled with the application, not extracted into `assets`, so
the icon is available before importing the original game files. On Windows it
is also the default icon for additional Tk windows and owned dialogs. This does
not change the Explorer icon of `Launch.cmd` or the Python executable.

Run `python -m unittest -q tests.test_app_window` to check pixel preservation,
transparency, platform selection, native window icons and the Windows app ID.
