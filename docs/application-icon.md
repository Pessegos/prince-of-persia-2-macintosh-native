# Application Icon

The game window and first-run importer share the Macintosh Prince icon through
`pop2.app_window.create_root`. Windows also receives a stable AppUserModelID so
the game is not grouped with unrelated Python windows in the taskbar.

`pop2/icons/prince.png` is the user-supplied transparent 512 x 512 pixel-art
image, with editor metadata removed. `prince.ico` contains 16, 24, 32, 48, 64,
128 and 256 pixel versions, all resized directly from that PNG with nearest
neighbour sampling. Other Tk platforms use 32 and 64 pixel PNG versions.

These files are bundled with the application, not extracted into `assets`, so
the icon is available before importing the original game files. On Windows it
is also the default icon for additional Tk windows and owned dialogs. This does
not change the Explorer icon of `Launch.cmd` or the Python executable.

Run `python -m unittest -q tests.test_app_window` to check pixel preservation,
transparency, platform selection, native window icons and the Windows app ID.
