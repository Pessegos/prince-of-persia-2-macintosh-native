# Checkpoint Saves

The Save/Load commands in F1, or Alt+S / Alt+O / Alt+L, open an in-game save browser,
not a native file picker.
Only existing `.pop2save` files in `~/Saved Games/PoP2 Macintosh Native` appear
in the library, newest first. Save mode adds a single `New save` action.
The list scrolls continuously using the wheel, scrollbar or keyboard, with a
short menu-only animation rather than discrete pages. Scrolling does not
advance gameplay, select another save or perform disk reads on hover.
Nothing is written merely by opening or navigating the browser.

New saves ask for a name in an integrated text field, with selection, keyboard
editing and clipboard support. Names are optional metadata in the version-two
format, not filenames: new files receive independent UUID names, so duplicate
display names and path separators cannot overwrite or escape another save.
The limit is 48 printable characters; blank names cannot be confirmed.
The pencil control renames a save without changing its progress or path.
Existing numbered slots and older named files remain visible and loadable.

Importing save support and testing progress-only slots does not load original
combat/AI resources. Fighter decoding and legacy RNG handling import those
dependencies only when needed. A subprocess regression test runs the complete
slot suite from a temporary copy with no imported game assets, matching CI.

Each entry shows its name, full `Level N` label and local save date; the detail
pane adds the resume point, banked life capacity and a full-colour preview.
The preview is rendered from the same restored progress used by Load, showing
the level entry or activated checkpoint, not the Prince's position at Save.
It uses an isolated session/renderer and preserves the live world, actor
identity, input, audio and random state. A bounded in-memory cache avoids
rebuilding the same destination on redraw. Old point-of-save thumbnails are
ignored and their progress-based preview is reconstructed without rewriting
the file. New preview metadata explicitly records `preview_at_resume: true`.
The browser is drawn at the fitted window resolution: font glyphs and previews
are scaled directly from their sources, not from an enlarged 512x384 menu.
New previews retain all 510x365 scene pixels, without the HUD. Both old
224x160 and full-resolution PNG fields remain accepted by the file decoder.
Shift+F8 renders the browser and confirmations at the selected PNG scale;
ordinary F8 still exports only the clean game.
Saving to an occupied slot, loading and deleting require an in-game confirmation
which defaults to Cancel. Successful saving stays in the browser. Loading
resumes play; Back preserves an existing user pause and returns to F1 when that
was the entry point. File errors remain inside the browser.

## Resume Rules

New version-two files record progress, not a live simulation snapshot:

- Without an activated checkpoint, loading restarts the level's normal entry.
- With a checkpoint, loading uses its native room/cell, saved facing and full
  checkpoint life, restoring the rebirth opponent/generator snapshot.
- Current X/Y, airborne motion, command queues, enemy combat timing, transient
  gates/projectiles, consumed potions and retained background pixels are not
  restored from the point where Save was pressed.
- Life capacity is banked at the checkpoint or level entry. In level three,
  upgrades collected during the replayed attempt are rolled back with its
  potions, using the same starting capacity as Restart Level.
- Copy-protection verification is retained. Audio/display/peaceful preferences
  remain local preferences, and held keys never become movement after loading.

This follows the recovered rebirth semantics, not the original save-file binary
format. CODE 2:132c-1386 chooses the rebirth bank or initial save header;
2:19ba-1a34 restores the LEVL checkpoint room/cell instead of current X/Y.
See [REBIRTH_RECOVERY.md](REBIRTH_RECOVERY.md) for bank and checkpoint limits.
The currently supported gameplay levels are 1-3; later levels are not claimed.

## Compatibility And Safety

Version-one native-port snapshot files remain readable. They are validated
using the existing decoder and then converted in memory to the new resume
rules. Loading does not rewrite them. New writes always use version two.

Saves remain outside the project, surviving a fresh download. Writes use an
fsynced temporary file and atomic replacement, preserving an existing save if
replacement fails. JSON has a 2 MiB cap, an original-level SHA-256 and strict
checkpoint/type validation. No pickle or executable deserialization is used.
Preview PNGs are size-bounded and are not used to reconstruct gameplay.

A candidate session and its art are prepared before replacing the live game.
Invalid loads leave the current session intact. Slot metadata and thumbnails
are read only when opening or updating the browser, never on pointer hover.

## Verification

`tests/test_save_slots.py` runs without original game files and covers resume
rules, checkpoint anchoring, names, previews, scroll bounds, selection, confirmations,
corrupt files and hover without disk access. `tests/test_save_game.py` covers the
legacy decoder and real game scenes, fresh cavern initialization, potion
rollback, repeated checkpoint retries, legacy conversion, in-game save/load/
delete, pause restoration and failed/cancelled writes. Scene tests compare the
preview pixels with the actual loaded destination across levels 1-3 and a
checkpoint, check isolation and exercise creation, rename, clipboard input,
old previews and menu-only scroll animation. No README changes.
