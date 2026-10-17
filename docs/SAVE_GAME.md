# Native-Port Saves

Save Game and Open Game are available in F1 and through Alt+S / Alt+O.
The native file picker selects a `.pop2save` file. The default directory is
`~/Saved Games/PoP2 Macintosh Native`, outside the downloaded project, so
replacing the project directory does not remove those saves. The user can
choose another destination. Opening a save asks before replacing progress;
cancelling either dialog leaves the current game and menu pause intact.

This is a versioned native-port snapshot format, not a claim to read or
write the original Macintosh game's save-file format. It supports the
currently playable levels 1-3. Save is unavailable during cutscenes,
recorded demos, copy-protection dialogs, death and level-exit transitions;
Open remains available from the menu. Live movement, including airborne
positions, can be saved. Audio playback restarts naturally after loading;
the file does not capture an SDL device, active sound buffers or host input.

## Captured State

`pop2/save_game.py` stores the player sequence cursor, pose, coordinates,
velocities, floor/room and movement state, current/maximum life, sword
state, world frame, combat timers and enemy RNG. It retains all visited
room encounters, individual enemy health/skill/animation, generation
counters and skeleton recovery. Checkpoint snapshots remain usable after
loading and a subsequent death.

World data includes consumed potions, their animation/effect state, gate
and plate phases/timers, loose floors and debris, wall spikes, projectiles,
torches, lava animation, the desert puzzle and harbor/ship state. The
opening animation retains its phase/tick and is reattached to the restored
player runtime. Physical map/world references are rebuilt against the
locally imported resources. Harbor water records are remapped to restored
actor identities rather than retaining stale process object IDs.

The scene restores its non-input movement flags. Held keys and buffered
commands are cleared/consumed rather than replaying the save/load shortcut
as a jump or sword command. Display, audio and peaceful-mode preferences
stay with the current session. Copy-protection verification is progress
state and is included. Cavern retained-background pixels are saved only
where the original renderer leaves holes, preserving route-dependent room
28 scenery without storing complete background images or resource banks.

## Validation And Writes

The JSON header identifies the format, schema version and level resource
SHA-256. The decoder accepts only a fixed list of game-state records and
their declared fields. It never imports a class named by the file and does
not use pickle. Field types, collection forms, current room, actor/sequence
ranges, RNG and retained-pixel coordinates are checked. Input size is
limited to 2 MiB and nested records to 48 levels. Unknown versions and
different original level data are rejected rather than guessed at.

A candidate session and its visible scenery/actor frames are prepared
before replacing the running game. Parsing/preparation does not advance
the current session or consume its random stream. Writes use a uniquely
named temporary file in the destination directory, flush/fsync, then an
atomic replacement. A failed replacement leaves the previous save intact
and removes the temporary file. Save files are excluded from Git.

## Verification

`tests/test_save_game.py` covers all three supported levels, shared runtime/
world references, mega-potion health and consumption, gates/debris, skeleton
recovery, checkpoint reuse, airborne continuation, retained cavern pixels,
exact room rendering after roundtrip, invalid/truncated/oversized files,
wrong versions/originals, failed writes, dialog cancellation, confirmation,
held-key clearing and disabled save during death. F1 model and host-input
tests also cover the newly enabled commands. No README changes accompany
this implementation.
