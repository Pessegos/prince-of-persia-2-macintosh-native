# Checkpoint Saves

The Save/Load commands in F1, or Alt+S / Alt+O, open an in-game save browser,
not a native file picker.
Twelve numbered slots are available across two pages. Additional `.pop2save`
files already in `~/Saved Games/PoP2 Macintosh Native` appear after those slots.
Nothing is written merely by opening or navigating the browser.

Importing save support and testing progress-only slots does not load original
combat/AI resources. Fighter decoding and legacy RNG handling import those
dependencies only when needed. A subprocess regression test runs the complete
slot suite from a temporary copy with no imported game assets, matching CI.

Each slot shows the level, resume point, banked life capacity, local save date
and a full-colour screenshot thumbnail. The thumbnail depicts the room at the
time of saving; it is not a promise to resume at those exact coordinates.
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
rules, checkpoint anchoring, metadata, previews, paging, selection, confirmations,
corrupt files and hover without disk access. `tests/test_save_game.py` covers the
legacy decoder and real game scenes, fresh cavern initialization, potion
rollback, repeated checkpoint retries, legacy conversion, in-game save/load/
delete, pause restoration and failed/cancelled writes. No README changes.
