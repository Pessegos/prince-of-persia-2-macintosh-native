# Death And Checkpoints

Addresses refer to the Macintosh executable. Room numbers in this document
are native, one-based LEVL IDs, not the F2 route labels. Runtime room IDs are
zero-based.

## Retry Gate

`PlayerCtrl` (4:3b88-3ca6) waits for a settled dead pose, as selected by
`IsDeadPos` (4:47a0): 185, 242, 243, 271 or 266 for the Prince. Its death
counter advances from 0 through 6; at 6 it queues the death song and advances
to 7. This controller runs before `AnimChar` (2:6354/6372): a newly drawn
dead pose is counted on the next simulation update. Initial sound completion
is also a native prerequisite, except for
the exempt sound IDs 272, 17 and 192.

`ReadKeyboard`'s dead-player branch (2:47e6-4820) accepts an event key or
the raw action-button state only when the copied counter is greater than 6.
It does not require the restart message to be visible. A released early key
is not a queued retry. The port also polls held Space, so holding it through
the death animation works without depending on Windows key-repeat settings.
Held Shift/Ctrl are polled as action buttons; a held arrow alone is not.
Retry keys are consumed until release, rather than becoming a jump/attack
in the new life. F2, F5 and Alt+Enter retain their host functions.

At counter 7, the native controller waits for both current and pending sound
to finish before drawing `Press key to continue` (3:433a; DATA aa96). This is
not a fixed delay after the hit or water contact. The port now uses actual
current/pending audio playback for this wait. The prompt clears the HUD band
(3:4378-4398), hiding both actors' health bottles until the retry. Ordinary
pause still shows health; pausing after the retry prompt does not restore it.
Reference MIDI event durations:

| Death method | MIDI cue | Duration (seconds) |
| --- | --- | --- |
| Default (0) | 64 | 7.900000 |
| Skeleton stab (2, reference) | 62 | 11.275144 |
| Fatal landing (3) | 6 | 11.520000 |
| Ordinary guard stab / quay offscreen-right (14) | 38 | 5.333328 |
| Water (15) | 39 | 9.333324 |

These durations come from the tempo/event tracks in `MIDISnd.dat`, resource
ID `9752 + cue`, selected through DATA bc6a / `AddKidDeathSong` (5:4afc).
The importer extracts that mapping and measures the rendered audio too.
`DEATH_CUE_SECONDS` has been removed: native counter gates still advance on
simulation frames, while final completion comes from SDL's playback state,
including the prepared sampler's release tail. Pause/F2 freezes both. Tests
that reproduce the earlier event-duration timing use a deterministic backend
in the test suite, not a timer table in the runtime. See [AUDIO_RECOVERY.md](AUDIO_RECOVERY.md)
for the distinction between MIDI events and host sampler output.

`CheckStab` dispatches on the attacker's type, not the victim's type
(6:5704-570c). The type-2 entry in the indirect jump table at 570e leads to
5738: a zero LEVL word at 21a4 selects death method 14 (`GardKill.mmf`);
nonzero selects method 10, outside the supported ordinary-guard levels.
Method 2 selects `SkelKill.mmf`, not the ordinary-guard cue. This table branch
was absent from the recursive disassembly and must be read from CODE bytes.
Using method 2 for every fatal sword hit incorrectly added about six seconds.
The combat event now carries the selected method to the scene's death state.

The MIDI-event-clock guard-hit regression takes 66 updates at 10 fps from fatal
contact to the message (6.6 seconds). In the original reference recording,
the fatal wound flash is at 4.266667 and the prompt at 10.883333 (6.616666
seconds, within one video frame). An unarmed vulnerable-jump death instead
takes 76 updates at 12 fps (6.333333 seconds). Comparisons must use the same
starting pose and sword state: time from the wound flash is not time from
the later kneeling/flat pose.

`DrawRestartMessage` (3:43c8) selects foreground palette index 6. The displayed
text color in the original reference is RGB (253, 255, 168); the port uses
that color for the restart prompt without changing the separate pause/menu
colors. The complete native palette conversion is not implemented here.

The original gives the message a 600-frame lifetime, blinks it near expiry,
then returns to its frontend (2:674c/67e8-68aa). This port has no frontend yet;
it keeps waiting for a retry instead of inventing an automatic level restart.

## Death Presentation

After the Prince dies, guard alert mode becomes zero. `EnGarde`
(4:09c0-09e2) requests sword lowering; `OnAlert` (6:2536-254c) accepts it only
at poses 158/170/171 and calls 2592/25ee, clearing sword mode and selecting
SEQS:77 (rest pose 166). An attack or step already underway finishes first.
The port now follows that path instead of leaving the guard in combat idle.

`CheckStab` (6:551c-5558) applies flat-death edge alignment to SEQS:85 for
the Prince as well as guards, using each actor's own loaded frame record.
`IsCharNonViewable` (4:474c-477c) additionally suppresses settled corpses on
rooftops, except in native rooms 15/16/19 (descent/water). This is an explicit
visibility rule, not a lower floor height or an enlarged parapet mask. It
now applies to the Prince and ordinary guards, including their settled
alternate pose 228 (`IsDeadPos` 4:4846-485c). The previous guard-corpse strip
exception is removed: it could also expose a whole body over a sloping roof
edge. Death animations remain visible until the settled pose; position,
tumble selection, water effects and corpse bank records are unchanged.

## Checkpoint Records

Each LEVL has two `(room, tile)` records at byte offset `0x39a6`. Tile is
`row * 10 + column`, both zero-based. Room 0 disables a slot. Unused records
in levels 6/10 also contain out-of-range room 90; these are not destinations.
Slots must retain their original indices when a preceding slot is disabled.

| Level | Slot 1: room / tile | Slot 2: room / tile |
| --- | --- | --- |
| 1 | - | 15 / 5 |
| 2 | - | - |
| 3 | - | - |
| 4 | - | - |
| 5 | 16 / 20 | 12 / 11 |
| 6 | - | - |
| 7 | - | 3 / 0 |
| 8 | 9 / 25 | 12 / 15 |
| 9 | - | - |
| 10 | - | - |
| 11 | - | 6 / 17 |
| 12 | 11 / 10 | 2 / 9 |
| 13 | 32 / 19 | - |
| 14 | - | 4 / 14 |

These are resource records, not a claim that later-level checkpoint paths
have been implemented or validated. Level 8's room-9 trigger additionally
requires story flag aff6 == 1.

The trigger (2:6b46-6c1a) requires a live Prince in the recorded room/cell,
excludes animation mode 4 and vetoes pending fatal damage. The column comes
from the supporting foot (`LoadFrame` 4:2a72 -> `GetFCharX`/`GetCharCol`),
not merely the sprite anchor. Revisiting the current slot does not recapture
it; reaching a different slot can replace it.

Level 1's checkpoint is native room 15, row 0, column 5: **F2 screen 8**, at
the landing after descending from screen 7. Retry places the Prince at
`column * 51 + 22` (X=277), with saved facing, restored maximum/full life
and idle SEQS:2, without replaying the palace window escape. Before the
checkpoint, retry starts the level normally. F5 always starts a fresh level.
F2 screen jumps seed the latest LEVL checkpoint on the selected route up to
that screen, so testing the quay does not require another rooftop run. A jump
back before the checkpoint, to the opening or to the secret screen clears it.
This is a developer convenience, not a recovered original trigger: ordinary
play still requires the recorded room/cell and live nonfalling state. Low-level
room jumps clear the checkpoint unless explicitly preserving a retry snapshot.

## Saved World

`SaveRebirthPtStatus` / the save block around 2:1674 and restore block
2:19ba-1a34 preserve more than a position: tile/scenery maps, opponent banks,
generation points, level, maximum life, facing and story state. Native startup
reanchors the player to the checkpoint cell; it does not restore exact X/Y.

For the supported level-1 subset, the port snapshots its visited opponent
and generator banks and restores an independent copy on each retry. Later
changes must not mutate that snapshot. Static LEVL geometry is shared;
dynamic tile normalization, later-level story state and the complete native
bank reinitialization pipeline still require translation. Harbor objects
restart fresh: level 1's checkpoint precedes ship activation.

`tests/test_rebirth.py` covers the resource table, trigger boundaries, real
screen-7 descent, combat/fall/water deaths, held and early keys, prompt
placement, world restore, repeated retries, pause and developer controls.
