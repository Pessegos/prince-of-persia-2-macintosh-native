# Input Recovery Audit

This audit compares the Macintosh controller with the current host buffer.
It records recovered conditions and known differences, not complete game
parity. Addresses use `CODE:offset` in the original executable. The local
recursive disassembly has unmapped ranges and indirect calls.

## Native State

The original does not store one chronological next-command slot. It maintains
four independent directional latches and one modifier latch.

| Field | Keyboard coordinates | Controller coordinates |
| --- | --- | --- |
| `cb78` | Left | Forward |
| `cb7a` | Right | Backward |
| `cb7c` | Up | Up, unless the vertical inversion flag is set |
| `cb7e` | Down | Down, unless the vertical inversion flag is set |
| `cb80` | Shift/Ctrl | Modifier |

`4:3d96-3e38` remaps horizontal latches for facing before `GenCtrl`, then
restores keyboard coordinates using the facing captured on entry. A request
must be interpreted at the controller gate, not permanently classified as
a turn or run when a host key event arrives.

`ReadKeyboard` (`2:55d2-56be`) samples the current key map: Left wins over
Right, Up over Down, and Shift over Ctrl. Two directional latches can still
be pending after different samples, despite one raw horizontal direction
per sample. This is not a FIFO of key events.

Directional update at `4:3e84-3f08`:

| Previous value | Raw direction inactive | Raw direction active |
| --- | --- | --- |
| `-1`: pending/unconsumed | Keep `-1` | Keep `-1` |
| `0`: inactive | Keep `0` | Set `-1` |
| `1`: consumed | Set `0` | Keep `1` |

A released directional tap can survive until a legal controller gate, but
`ClearControls` discards it. A held consumed direction is not a fresh press;
a reset or release/repress can make it fresh again.

Modifier update (`4:3f08-3f42`) is different:

- Raw Shift: keep consumed `1`, otherwise set pending `-1`.
- Raw Ctrl: keep consumed `2`, otherwise set pending `-2`.
- Neither modifier: set `0`, even if a negative request was pending.

Releasing Ctrl before a legal attack gate can therefore cancel the attack.
Holding Ctrl after an accepted attack does not itself create a fresh attack.
Two independent host modifier booleans do not fully represent this state.

## Frame Order And Resets

The ordinary player path (`4:3cae-3d14`) restores the saved bank `cb6e..cb76`,
samples keys, applies an active-control gate, updates latches, remaps facing,
runs `GenCtrl`, calls the recording helper, then saves the consumed/reset
bank. The active-control gate can zero raw directions without zeroing an
already-pending negative latch. NPC automatic control has a separate bank
lifecycle; it must not overwrite the saved player bank.

`ClearControls` (`4:3e3a`) sets the four directions to `0`, leaves `cb80`
alone, and returns `1`. Many callers then mark the accepted direction as
consumed. This is neither a single-command consume nor a host focus reset.

For a living actor, the first `GenCtrl` gate (`6:0576-059c`) clears directions
in animation modes **4, 5 or 9**, or while the current **sequence ID is 27 or
110**. Those two numbers refer to `afd2`, not pose field `afb4`. Later, the
ordinary unarmed dispatcher clears at **pose 26 or 44** (`6:074a-0760`).
There is no equivalent unconditional pose-27/pose-110 test.

Examples from original SEQS data:

- Standing forward jump: pose 26 clears. Earlier released requests must
  not survive; a request sampled after that reset can survive.
- Running jump: pose 44 clears; the next run pass samples held keys afresh.
  This subset is implemented in `update_running_jump_controls`.
- Vertical landing: pose 83 is mode 5; later landing poses return to mode 1.
- Crouch rise: poses 110-116 are mode 5; 117-119 return to mode 1.
- Ordinary climb: pose 149 is mode 5 before 118/119.
- Long sheath: pose 50 is mode 5. The same pose in a standing turn or run
  brake is not mode 5, so a pose-only gate is insufficient.

## Ordinary Controller Gates

Terrain, health, sword state and special-level exclusions can prevent these
branches. `fresh` means a negative latch; `active` means any nonzero latch.

| Context | Recovered gate / priority | Source | Port status |
| --- | --- | --- | --- |
| Rest/stop poses 15, 50-52 | Standing handler, after mode/sequence reset gate | 6:05fe-0618, 0c32 | Tested subset; mode-5 exception missing |
| Standing without Shift | Fresh Forward + fresh Up: jump; otherwise fresh Forward, Backward, Up, Down; active Forward is final run fallback | 6:0db0-0e16 | Common chords tested; independent pending inputs missing |
| Standing with Shift pending/consumed | Fresh Backward, Up, Down before a fresh Forward-only step | 6:0d4c-0db0 | Step/turn tested; buffered host modifier classification can be stale |
| Draw from rest | Fresh Ctrl and no directional latches; consume modifier, clear directions, DoEngarde | 6:0c90-0cb6, 1e78 | Draw implemented; simultaneous-input gates partial |
| Turn poses 45-49 | Pose 48: active Forward, no Up/Down, modifier >= 0 resumes run; otherwise protected | 6:1014-1066 | Held-run transition tested; host-held state replaces latches |
| Run start poses 1-3 | Fresh Up AND fresh Forward: forward jump; clear directions | 6:15b6-15da | Port deliberately buffers a run jump during forward startup; see Intentional Port Extensions |
| Vertical preparation 67-69 | Active Forward: standing forward jump | 6:15de-15e8 | Chord tested; 35 ms host chord delay is an approximation |
| Running 4-14 | Both horizontals zero: brake only at 7/11; otherwise Backward before fresh Up, then fresh Down; finally consume fresh Forward | 6:11e4-1274 | Ordinary flow tested, including release at pose 8 waiting for 11; latest-command slot cannot reproduce every conflict |
| Run-jump takeoff | Legal run poses plus two-cell geometry; accepted jump clears directions, consumes Up | 6:1c14-1d5e | Ordinary geometry tested |
| Other unarmed poses | No general dispatch; pending latches remain unless reset/special branch intervenes | 6:0560-07e0 | Full native lifecycle missing |
| Crouch pose 109 | Down active: fresh Forward selects crawl, then clear/consume; Down zero: rise unless terrain vetoes | 6:099a-0b58 | Tap/hold/crawl tested; low-hold and mode-5 resets missing |
| Cautious step | Consume Forward and modifier; no unconditional ClearControls at ordinary step entry | 6:1276-128a | Common repeat/late requests tested |
| Ledge poses 87-99 | Up active, grip delay zero: climb before release check; otherwise zero modifier or sequence-mode 11 releases | 6:18e0-1994 | Up/Shift and expiry tested; modifier/special branches partial |
| Climb/release | Clear directions; consume Up + modifier on climb, Down on release | 6:1998-19d0, 1a84-1a8c | Terrain transitions tested; full latch reset missing |
| Sword controls | Fresh Ctrl before fresh Down, Up, Forward, Backward; retreat requires modifier zero | 6:24bc-2584 | Actions tested; conflict priority and modifier-suppressed retreat missing |
| Attack | Legal poses 157/158/170/171/165 or block 150/161; consume Ctrl and clear directions | 6:2780-281c | Gates/chains tested; released pending Ctrl differs |
| Block | Ordinary legal poses 158/170/171/168/165; special branch at 167; consume Up without clearing other latches | 6:282a-28ee | Ordinary block/attack chain tested; opponent-dependent branches partial |
| Sword steps/sheath | Steps at 158/170/171 clear/consume Forward or Backward; sheath clears/consumes Down | 6:1d6e-1e68, 2592-25ec | Common flow tested; host buffer is not complete native state |

The sword handler is reached through `6:2166-238c`, which also checks mode,
health, target/range, floor and actor state. The local action gates cannot be
applied outside those outer checks. Pickup routines, stairs, special actors
and later-level scripts are not certified by this audit.

## Decoded ClearControls Calls

The available disassembly contains **31 direct calls** to `4:3e3a`: 28 in
CODE 6, two in CODE 7, one in CODE 9. This counts decoded sites, not all game
rules or proof that indirect/unmapped calls do not exist. F/B/U/D below are
facing-relative latches and M is the modifier. Post-clear writes use the
returned value `1` unless noted.

| Call site(s) | Context | Immediate post-clear state / scope |
| --- | --- | --- |
| 6:059c | Mode 4/5/9 or SEQS 27/110 | No accepted direction; later-level exception pending |
| 6:075c | Ordinary unarmed pose 26/44 | No accepted direction; pose-44 subset translated |
| 6:092a | Special handler 07ee, selects SEQS 124 | U=1; special terrain context pending |
| 6:0956, 096e, 0990 | Same handler: forward/backward/cleanup | Selects 122/123 or clears; not ordinary run/crouch |
| 6:0a58 | Crouch forward | F=1 |
| 6:0b34 | Crouch Down active | D=1, including holding low without a new crawl |
| 6:0b4c | Successful crouched object interaction | M=1; pickup not ported |
| 6:0cb6 | Ctrl draw gate | M was consumed as 2 before the call |
| 6:10d6 | Standing crouch entry | D=1 |
| 6:10e8 | Standing turn | B=1 |
| 6:11d6 | Run start/restart | F=1 |
| 6:1202 | Run brake | F=1 |
| 6:121c | Running reversal | B=1 |
| 6:1252 | Running crouch | D=1 |
| 6:15ca | Run-start forward jump chord | F=1, U=1 |
| 6:1608, 177c | DoJumpUp and terrain helper | U=1; special destinations partial |
| 6:19c8 | Ledge climb | M=1, U=1 |
| 6:1a88 | Ledge release | D=1 |
| 6:1d48 | Accepted DoRunJump | U=1 |
| 6:1db6 | Sword retreat | B=1 |
| 6:1e5a | Sword advance branch | F=1 |
| 6:1e80 | DoEngarde | F=1, M=2 |
| 6:233c | Player-specific Shift/backward sword branch | M set to 2 before clear; B=1; outer gates partial |
| 6:2598 | PutSwordAway | D=1 |
| 6:2812 | Accepted attack | M consumed as 2 before clear |
| 7:379a, 39ca; 9:0646 | Scripted actor/scene initialization | Modifier separately zeroed; not ordinary player buffering |

Other state writers are separate from that count:

- `4:3e70`, called at `2:5bdc`, zeroes all five saved latches on initialization.
- `6:4f1e-4f42` zeroes all five current latches and raw controls at AutoCtrl
  entry; it is not the player-facing ClearControls routine.
- `4:0006-0064` synthesizes automatic controls; `5:6232-6288` restores five
  packed latches for recorded playback, independently of keyboard update.
  Playback is not implemented in the port.
- `4:407a` consumes the modifier during object removal; `4:49dc` consumes
  Down in special actor control. Their full callers remain partial.

## Demonstrated Host Differences

`BufferedCommand` is one latest-wins slot. Handlers can enqueue on host key
callbacks before the next simulation tick and classify a request using the
current movement/modifier. Native decisions use independent latches at the
legal pose, with explicit resets.

`tests/test_input_recovery.py` records four source-backed discrepancies as
**expected failures**, alongside a passing late-input boundary test:

1. A released opposite tap early in a standing jump survives pose 26 in the
   port and produces a turn after landing.
2. A released direction during mode-5 crouch rise survives in the port.
3. Ctrl sampled at block pose 169, released before the legal pose-150 pass,
   still produces a block-attack in the port.
4. Shift + backward in sword guard starts a retreat, despite native OnAlert
   requiring a zero modifier for that branch.

These are missing translations, not intermittent defects. Expected failures
track mismatches, not successful parity tests. Remove the decorator when
fixing a case, and update older tests that encode host-buffer behavior.
Early-jump tap and released-Ctrl block-chain tests must not be treated as
authoritative original-game requirements.

## Intentional Port Extensions

Ctrl pressed while running preserves a request to stop running and draw the
sword once the current run segment reaches its transition. A short Ctrl tap
is sufficient; no second press is required. The user's Macintosh comparison
instead stopped the Prince without drawing, and the port behavior is retained
as a preferred QoL difference, not a parity defect.

`test_ctrl_during_run_retains_intentional_stop_and_draw_extension` covers
running poses 4-14, both facings and tapped/held Ctrl. It checks that the
current pose is not immediately overwritten and that the original draw poses
207-210 reach sword guard. Native-latch integration must preserve this explicit
extension separately from ordinary attack buffering.

Up pressed during run startup now retains a running-jump request until the
first legal run pose (7). It does not rewind startup poses 1-3 into a standing
jump. This is an intentional input-tolerance extension; Up before Forward
still selects a standing jump, and takeoff alignment/range are unchanged.

Rapid Ctrl repeats during the first two attack poses do not buffer another
swing. Normal attacks close the buffer at poses 151/152; counters at 162/152.
The buffer opens at pose 153, about 200 ms into either attack at 10 fps.
This is another intentional extension, not a recovered native timing rule.
Drawing the sword still accepts a first queued attack, and block/counter,
movement and sheathing commands are not delayed. Using animation poses keeps
the window frozen while paused and avoids depending on OS key-repeat timing.

## Run Stop and Ledge Entry Audit

Executing the original GenCtrl, AnimChar, LoadFrame, CheckFloor and
StairClimbing instructions confirms that release at running pose 8 must wait
for pose 11. The old host-only pose-8 brake exception is removed. Both
facings retain the SEQS:13 displacement of 33 pixels; standing turn retains
its resource displacement of 9 pixels toward the new facing.

On level 1 screen 7, starting left-facing at X=468 and releasing at poses
8-11 stops at X=339. Turning right finishes at X=348 and Down selects
SEQS:68. Starting instead at X=495 stops at X=366, turns to X=375 and Down
selects crouch SEQS:50 in the original as well. These are executed native
instruction results, not positions inferred from scaled video pixels.

Developer navigation now uses the existing entry-cell inset of 30 pixels
for ordinary right-side spawns, just as for the secret-room entry. This
changes its X from 495 to 489 and allows the stop/turn/descent route from
multiple release poses. It is a developer spawn choice, not a recovered
universal original-game entry position. Normal room cuts, stop displacement,
the ledge-distance predicate and falling are unchanged. No screen-specific
brake, automatic edge clamp or wider descent window is introduced.

The continued run from the screen-6 landing can also miss this window in the
original. Executing the native player frame and CutAllOpponents routines from
the same test approach produces screen-7 entry X=494 at pose 7, stop X=368,
turn X=377 and crouch rather than descent. The user confirmed the same
approach-dependent behavior in both versions; no edge protection is added.

## Downward Room Cuts

CutChar 6:4c90-4cd2 vetoes downward cuts in native room 11 for environment 5,
and native rooms 3/5 for environment 6, even when their LEVL lower links exist.
The shared geometry layer now checks these source-backed room/environment
pairs before following a lower link. This keeps a failed screen-6 jump in the
screen-6 viewport through death without breaking the screen-7 dock drop.
Executing the original CutChar confirms no cut from rooms 11 (environment 5)
or 3/5 (environment 6), while room 12 (environment 5) cuts down normally.
NPCs use the separate Cut routine (6:472a) and retain their lower-link behavior;
the camera veto is not applied to guard falls.

## Implementation Order

1. Translate five native latches, sampling, facing remap and consume/reset
   operations in `mac_input`. Test every directional/modifier transition.
2. Integrate standing/turn/step/run, jump resets, crouch, ledges, then sword
   gates. Remove each superseded host queue path; do not run two buffers as
   simultaneous authorities. Preserve documented intentional port extensions
   rather than treating every original-game difference as a defect.
3. At protected poses, test input before/at/after reset, released versus held,
   both facings, modifier changes and conflicts. Check pose order/offsets too.
4. Run real scene tests with terrain, combat, screen transitions, pause/F2
   and focus loss. Host modal resets stay distinct from native ClearControls.
5. Use original recordings or traces for unresolved sampling/update timing
   and special branches instead of assigning unsupported semantics.

The native-latch audit adds documentation and executable mismatch cases only.
The run-stop correction does not replace the runtime buffer, change animation
clocks or change the approved running-jump fix. Routine-level progress is in
[RECOVERY_INDEX.md](RECOVERY_INDEX.md).
