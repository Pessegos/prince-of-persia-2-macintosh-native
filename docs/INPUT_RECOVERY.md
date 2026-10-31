# Input Recovery Audit

This audit compares the Macintosh controller with the port's input handling.
It records recovered conditions and known differences, not complete game
parity. Addresses use `CODE:offset` in the original executable. The local
recursive disassembly has unmapped ranges and indirect calls.

Since 2026-10-30 the directional bank is the only store of pending requests:
the host's single pending command (`pending_action`) and its dispatcher are
removed ([census and retirement](research/remaining-host-slot.md)). Sections
below that mention the "host buffer" describe the stage at which they were
written; their tolerances now live in the bank or were removed with it.

## Tolerance Audit (2026-10-31)

On the user's request every remaining host input tolerance was compared
with the native rule; it now follows the original unless it only emulates
the original's once-per-frame keyboard sample. This supersedes the
"retained tolerance" statements in older sections below.

| Former tolerance | Native rule | Decision |
| --- | --- | --- |
| Ctrl strike survives its release; Ctrl at 151-153 discarded | Release writes 0 (4:3f38); DoStrike admits a pending -2 at 157/guard | Removed; a double tap swings once (512 native frame traces, `tools/probe_attack_taps.py`) |
| 300 ms rapid-repeat filters (step, low step, jump) | A re-tap is a fresh -1 (4:3e84) | Removed: a re-tap is the next action |
| Held Shift step repeats | DoStepFwd writes Forward=1, modifier=1 (6:1286-128a), no clear | Removed: a held step steps once |
| Held low step repeats seamlessly | 109 consumes Down with ClearControls (6:0b2e) | Native repeat with one 109 frame to rearm Forward |
| Release cancels a held Up/Down re-read after a clear (run, arc, low step) | Release keeps -1; before the next sample the word is still 0 | Removed (no marker needed) |
| Taps kept through the climb; chord re-latch; completion auto-repeat; Shift+Backward no-run | Climb pose 149 is mode 5 (6:0576-059c clears) | Removed; held keys are fresh after 149; the completion 15 is shown before its gate |
| Back+Up held turns only | DoTurn clears; the Up handler 6:0e7a sees Forward set and calls DoFwdJump 6:15ea | Removed: turn, then a forward jump |
| Shift tap during a skid picks up at pose 50 | 6:0c50 needs -1 at the gate; release writes 0 | Removed; a tap at rest is still tried at the next tick |
| Up 35 ms window at rest; Forward/Backward + Up chord in run pose 1 (1-3 reversed); chord before the first pose loads | Keys within one frame are one sample | Kept: the port dispatches at event time, these windows (at most one frame) stand in for the frame sample |
| Source46 wall-bump recovery | Mode-5 clears in 46/47/49 | Already native since 2026-10-30 (low bank owns 46/47) |

Not changed and still different: the port acts at a ready pose (15, 158)
in the same tick in which it is loaded, one frame earlier than the
original, which shows it first; only the climb's completion now shows it.

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
  This subset is implemented in `AirborneControls.update_airborne_controls`.
- Hard-fall recovery: SEQS:20 -> 212 -> 49 stays in mode 5 through pose 116.
  The low bank's mode-5 clear discards directional taps during that part;
  held keys become fresh requests afterward.
- Wall bump SEQS:46 (102-109, rising through 49 to 116) and wall stop
  SEQS:47 (50-52) are mode 5 too and, since 2026-10-30, belong to the same
  low bank: a tap made before or during the bump is discarded, and a key
  still held at the end is a fresh request (Up alone climbs; Up and Forward
  still held jump forward again). The former host wall-climb slot is removed.
- Vertical landing: pose 83 is mode 5; later landing poses return to mode 1.
- Crouch rise: poses 110-116 are mode 5; 117-119 return to mode 1.
- Ordinary climb: pose 149 is mode 5 before 118/119.
- Long sheath: pose 50 is mode 5 (raw SEQS 92: `-7 5, 50, -7 1, 51`). The
  same pose in a standing turn or run brake is not mode 5, so a pose-only
  gate is insufficient. `WaitingControls.begin_sheathe_controls` hands the
  bank from PutSwordAway (directions 0, Down 1) to the standing gates:
  pose 48 resumes a pending or held Forward as SEQS 43, pose 50 discards
  taps made during the sheathe, and held keys act at 51. A Down still held
  from the sheathe request therefore crouches at 51; the short sheath
  (SEQS 93, no mode-5 pose) keeps it consumed.

## Ordinary Controller Gates

Terrain, health, sword state and special-level exclusions can prevent these
branches. `fresh` means a negative latch; `active` means any nonzero latch.

| Context | Recovered gate / priority | Source | Port status |
| --- | --- | --- | --- |
| Rest/stop poses 15, 50-52 | Standing handler, after mode/sequence reset gate | 6:05fe-0618, 0c32 | Tested subset, including the long sheath's mode-5 pose 50 |
| Standing without Shift | Fresh Forward + fresh Up: jump; otherwise fresh Forward, Backward, Up, Down; active Forward is final run fallback | 6:0db0-0e16 | Independent pending directions integrated at migrated ready gates; other family handoffs partial |
| Standing with Shift pending/consumed | Fresh Backward, Up, Down before a fresh Forward-only step | 6:0d4c-0db0 | Migrated bank reads current modifier and priorities; native selector compared directly |
| Draw from rest | Fresh Ctrl and no directional latches; consume modifier, clear directions, DoEngarde | 6:0c90-0cb6, 1e78 | Migrated selector and running/braking Ctrl lifecycle tested; armed controller migration remains partial |
| Turn poses 45-49 | Pose 48: active Forward, no Up/Down, modifier >= 0 resumes run; otherwise protected | 6:1014-1066 | Bank remaps against current facing and admits running turn 43; first-pose guard tested |
| Run start poses 1-3 | Fresh Up AND fresh Forward: forward jump; clear directions | 6:15b6-15da | Forward + Up chord retained at pose 1; later forward startup buffers a run jump; see Intentional Port Extensions |
| Vertical preparation 67-69 | Active Forward: standing forward jump | 6:15de-15e8 | Vertical bank integrated, independent route model and actual takeoff windows tested; 35 ms rest chord delay remains a host approximation |
| Running 4-14 | Both horizontals zero: brake only at 7/11; otherwise Backward before fresh Up, then fresh Down; finally consume fresh Forward | 6:11e4-1274 | Grounded run bank integrated; direct production/native routing comparison and scene conflict/geometry regressions; airborne continuity remains partial |
| Run-jump takeoff | Legal run poses plus two-cell geometry; accepted jump clears directions, consumes Up | 6:1c14-1d5e | Ordinary geometry tested |
| Other unarmed poses | No general dispatch; pending latches remain unless reset/special branch intervenes | 6:0560-07e0 | Drink (SEQS 78, 191-205) and sword pickup (SEQS 91, 229-232) keep the bank to the next standing/sheathe gate; the throne collapse/wake (SEQS 237/231; 6:0b5a touches no Prince latch) keep it too, cleared at the pickup and the vision (7:39ca); other special branches not migrated |
| Crouch pose 109 | Down active: fresh Forward selects low step/lie-down, including with Shift; Down zero: rise unless terrain vetoes | 6:099a-0b58 | Low/prone native consumption and saved-player traces recovered; Shift low-step classification corrected; full runtime bank migration missing |
| Cautious step | Consume Forward and modifier; no unconditional ClearControls at ordinary step entry | 6:1276-128a | Common repeat/late requests tested |
| Ledge poses 87-99 | Up active, grip delay zero: climb before release check; otherwise zero modifier or sequence-mode 11 releases | 6:18e0-1994 | Up/Shift and expiry tested; modifier/special branches partial |
| Climb/release | Clear directions; consume Up + modifier on climb, Down on release | 6:1998-19d0, 1a84-1a8c | Terrain transitions tested; full latch reset missing |
| Sword controls | Fresh Ctrl before fresh Down, Up, Forward, Backward; retreat requires modifier zero | 6:24bc-2584 | Actions tested; Shift+Backward selects the voluntary turn instead of a retreat and toggles the automatic turn; conflict priority missing |
| Attack | Legal poses 157/158/170/171/165 or block 150/161; consume Ctrl and clear directions | 6:2780-281c | Gates/chains tested; a released Ctrl cancels a pending strike everywhere (4:3f38), so a double tap swings once unless the second press is held at the gate (512 native frame traces) |
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
| 6:075c | Ordinary unarmed pose 26/44 | No accepted direction; standing-forward-jump pose 26 and running-jump pose 44 translated |
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

`BufferedCommand` is the legacy latest-wins slot. The runtime migration
replaces deferred standing-turn/cautious-step and grounded running input with a directional bank;
see [directional-bank runtime](research/directional-bank-runtime.md) for exact
ownership, observable changes and remaining families. Elsewhere, handlers can enqueue on host key
callbacks before the next simulation tick and classify a request using the
current movement/modifier. Native decisions use independent latches at the
legal pose, with explicit resets.

The four discrepancies previously recorded as expected failures are now
passing regressions. Shift + Backward was already corrected by the voluntary
sword-turn implementation. The 2026-10-25 boundary correction addresses the
other three extra-action cases:

1. A released opposite tap at standing forward-jump poses 16-26 is discarded
   by the pose-26 reset, rather than producing a turn after landing. A new
   tap at pose 27 still survives to the landing gate. An explicit vertical
   follow-up with Up still held remains available for the established
   wall-climb behavior; releasing Up discards it at the reset.
2. Horizontal/crawl requests during crouch-rise mode 5 (poses 110-116) are
   discarded. Physical holds remain available for later sampling. The
   separately documented vertical wall-bump/climb tolerance remains.
3. A queued counter request is cancelled when Ctrl is released before the
   block's legal attack pass. Holding Ctrl still permits the counter. The
   intentionally queued ordinary swing during attack/draw is retained.

All three regressions failed against the previous controller. Tests cover
both facings; the older animation expectations that retained early jump taps
and released-Ctrl counters were changed because they encoded host behavior,
not original-game requirements. The opening-duel integration scripts now
hold Ctrl through the accepting counter tick, retaining all fight, health
and room-exit assertions. The real-terrain held-Up wall-climb tests remain
unchanged. No animation poses, timings or queue timeout
were changed. This is a bounded correction to the existing host buffer, not
integration of the complete native bank.

## Executable Input-Bank Recovery (2026-10-25)

`tools/reference_input_bank.py` is an asset-free research model of the five
latches, with sampling, direction clearing, save/restore representation,
facing/inversion remapping and explicit consumption. It is deliberately not
wired into gameplay yet. `tests/test_input_bank.py` checks released taps,
independent opposite directions, modifier cancellation/consumption, held-key
rearming after reset and reversible remapping.

`tools/probe_input_bank.py` executes original instructions against that model:

| Actual original path | Cases | Supplied context |
| --- | ---: | --- |
| Sample bank, 4:3e84-3f42 | 10,935 | All 405 valid bank states and 27 raw axis/modifier combinations |
| ClearControls, 4:3e3a | 405 | Every bank state; also checks return value 1 |
| Save/restore, 4:3e50/3e60 | 405 | Every bank state, clearing the working bank between calls |
| Horizontal/vertical flips, 4:3dfe/3e1c | 1,620 | Every bank state and all four flip combinations |
| Live unarmed GenCtrl reset gates, 6:0560-07e0 | 900 | Level 5, six modes, five sequence IDs, poses 26/27/44, both facings and five modifier states; executes IsDeadPos too |

All **14,265 cases match**, with no supplied external services. Raw controls
are supplied after ReadKeyboard; the probe does not execute OS key-map
sampling. The reset matrix uses a living unarmed actor and excludes the
level-12 post-reset exception. It does not certify other GenCtrl action or
geometry branches, the whole player wrapper, action consumption sites or
FrameAdv. The flip primitive is verified; restoring with the captured old
facing when an action changes facing still relies on the wrapper audit.

Reproduce locally with the read-only original recovery resources:

```powershell
.venv\Scripts\python.exe -m tools.probe_input_bank --source ..\PoP2-Mac-Code-Recovery --output rendered\native-input-bank.json
```

The remaining architectural gap is explicit: outside the migrated turn/step
family, gameplay still uses the latest-command slot. Independently pending directions, simultaneous-input
priorities and all accepted-action consumption/reset sites are not fully
translated. A complete replacement must map those gates and preserve the
intentional extensions below. The 300 ms host repeat filter is not a native
buffer lifetime; shortening it would not recover the original rules.

## Executable Unarmed Routing (2026-10-27)

`tools/reference_input_routes.py` independently models the ordinary unarmed
GenCtrl router. `tools/probe_input_routes.py` compares it with original
instructions at 6:0560, standing 6:0c32, turn 6:1014, run 6:11e4 and jump
preparation 6:15b6. The 17,415 cases cover all 405 latch states across standing,
run/start, turn, jump preparation and clear poses, protected modes/sequences,
and standing without a sword. All match. Another 36 persistent sampled steps
execute sampling, facing remapping and dispatch for released/held Ctrl,
continued Forward and a second press, in both facings. All match too.

The native run handler ignores Ctrl. Backward has priority over Up, and an
already-consumed Up can suppress Down; a single latest-command slot cannot
represent these rules. With neither horizontal latch active, poses 7/11
request brake sequence 13. Standing draw requires fresh Ctrl and every
directional latch zero; it consumes Ctrl before calling the draw routine.

These probes supply a living Prince (actor 10/type 0), no alert, no pickup and no
opponent target. Action and geometry endpoints are no-op request sinks;
resets/consumption inside those actions are excluded. Trace poses and raw
axes are supplied, not advanced by real animation or OS polling. This proves
the bounded router and its composition with sampling, not complete input,
physics or FrameAdv parity. The action-body and saved-player studies below
extend that evidence; runtime migration now uses it in the bounded families
described above. Other families and complete caller scheduling remain partial.

A separate 7,290-call matrix executes DoStrike 6:2780-281c for Prince type0,
all 405 banks, nine poses and ordinary/serpent opponent types. It verifies
accepted sequence requests 75/96/66, consumption of Ctrl as 2 and clearing
directions, versus rejected poses that leave the bank intact. JumpSeq is a
supplied request sink; this does not recover the outer armed admission or
the attack animation, target geometry and combat update.

The executable resource-fork SHA256 is
`ca2c5886244efa7e19d63fee9317ae5c2341b8a7cc79c7740fdd505575f44bd5`;
the route output digest is
`a66eb501c91c934b3305a599a9c6ddc1f0a4f072e8c506dde73cd0a9e4cf1e7b`.
`tests/test_input_routes.py` runs without original assets in CI. The existing
bank probe also checks production `sample_modifier` against all 10,935 native
sample cases, independently of the research model.

```powershell
.venv\Scripts\python.exe -m tools.probe_input_routes --source ..\PoP2-Mac-Code-Recovery --output rendered\native-input-routes.json
```

## Landing Into Crouch

For the distinct per-action consumption beyond the routing sinks, see
[Ordinary action input consumption](research/input-action-consumption.md).
Those additional native calls do not remove this audit's remaining controller
and frame-order exclusions.

An ordinary landing uses SEQS:17: poses 107/108 in mode 5, then mode 1
and the low pose 109 in SEQS:117. Native GenCtrl clears directional latches
in mode 5 (6:0576-059c); its low-pose handler consumes active Down and clears
directions when selecting crawl (6:099a-0b38). It does not preserve a second
stand-to-crouch request after the actor has already landed low.

The host accepted Down during the first landing poses into its latest-wins
slot. That pending crouch blocked held-direction crawl at pose 109 and was
replayed after releasing Down and completing the rise. The low-pose handler
now removes only that fulfilled crouch request before checking crawl/rise.
Other buffered commands and the repeat-filter window are unchanged; this is
not a complete translation of the native independent input latches.

Execution of the original GenCtrl matched nine ordinary low-pose Down/Forward
combinations, intercepting JumpSeq and supplying no pickup/rise veto. Integrated
tests compare identical cavern movement traces with Down pressed during the
fall, at landing pose 107, or at pose 108, through the next downward room cut.
Released Down rises once; animation tests also cover both facings, release
before/on pose 109 and preservation of other pending commands.

## Intentional Port Extensions

The voluntary sword turn (Shift + fresh Backward, SwordCtrl 6:22f2-2366)
turns, retargets and toggles the automatic-turn flag a5-0x5010 (6:2344)
like the original since 2026-10-30, at the user's request: one voluntary
turn disables the automatic turn until the next one or the next level
(2:5e5c). The former always-enabled exception was removed; see
[voluntary-sword-turn.md](research/voluntary-sword-turn.md).

Alt+R during ordinary gameplay restores currently held gameplay keys after
restarting, in modifier/vertical/horizontal order. The pre-restart command
buffer is discarded; the new entry controller decides when the restored
holds can act. This includes horizontal holds, Shift steps and Up+direction
chords. Inputs already suppressed by a modal transition are not restored.
Restarting through a menu, using Alt+R while dead and starting a new game
retain their input clearing. This Alt+R behavior is a host QoL extension,
not a recovered Macintosh restart rule.

A normal death retry separately preserves currently held gameplay keys once
the existing dead-pose/key gate accepts the retry. It uses the same ordered
restoration, without replaying the old command buffer or restoring keys
suppressed by a modal transition. This matches the reference's held-action
continuation into the new life. Arrow, Up/Down and Shift+arrow retries have
integrated regressions, including protected entry completion and key release.
Modifiers alone still do not retry; an early held arrow is not a retry poll.
Ordinary text/Space retry keys stay consumed until released. See
[Death And Checkpoints](REBIRTH_RECOVERY.md) for the unchanged timing/filter.

An arrow used to resume ordinary gameplay also reaches its normal control
binding in that same press. Up/Down and horizontal jump chords are included,
not only running. Ordinary pause freezes existing holds and repeat/queue state;
key releases and modifier changes during pause update held state without moving
the actor. Resuming with Escape therefore preserves a continuously held Shift
on a ledge, but does not restore a Shift or direction released during pause.
Ctrl newly held during pause is admitted only on explicit resume; releasing it
before resume cancels that request. Unarmed draw uses the standing gate below,
while an armed attack retains its existing buffer. Modifiers and system keys
still do not resume by themselves. A full gameplay frame interval after resume preserves
the existing Up+direction chord window; ordinary key handlers can still start
their action immediately.

All resumed gameplay-key releases reach the ordinary bindings rather than
being swallowed by the resume-key filter. Menus, cutscenes, demos, copy
protection, death and completion states retain their input filters. Focus loss
still explicitly clears physical/logical holds; returning focus does not resume
or restore them. This is host pause integration, not a recovered Macintosh pause
rule or a claimed port-exclusive improvement; the user's Macintosh setup also
preserves held inputs on resume.

The user revoked the former Ctrl stop-and-draw extension on 2026-10-27.
A short Ctrl tap during movement must no longer survive as a future sword-draw
command or bypass the ordinary brake after a running jump. Ctrl alone does not
stop a still-held run. Releasing Forward keeps the normal braking sequence;
releasing Ctrl cancels draw intent on the next sample.

The runtime now uses the native modifier normalization (4:3f08-3f42) for
unarmed draw: Shift wins, fresh Ctrl is -2, accepted Ctrl becomes 2, and a
release becomes 0. Accepted attacks also consume Ctrl (6:280c-2812), so an
attack hold cannot become a new draw after sheathing. Holding Ctrl through
the brake can draw at standing poses
50-52, as admitted by GenCtrl 6:0c90-0cba. A consumed hold cannot draw again
without release. This is not a mandatory second press when Ctrl remains held.
The later turn/step migration uses a production directional bank in that
family; other host rest/pending-action admission remains. Neither migration
establishes full controller parity.
The retained armed buffer/repeat policy owns an attack press as soon as it is
submitted (or deliberately discarded by that policy); the unarmed modifier
is consumed there too. This bridge preserves existing armed buffering rather
than claiming its consumption timing now follows the full native controller.

Regression traces compare Ctrl taps/holds with no-Ctrl movement in both
facings at every run pose 4-14 and running-jump pose 34-44. A released tap keeps
the complete brake (53,54,55,56,49,50,51,52,15), including the real-terrain
jump/landing case. A held Ctrl reaches the native standing brake gate before
drawing. Hard-fall and climb taps no longer queue a future draw either.
The armed attack buffering was later removed (2026-10-31 tolerance audit).

Forward + Up remains a standing jump in either key order. When Forward
arrives first, the initial run pose (1) leaves one full animation interval
for the chord, about 83 ms at 12 fps. From pose 2 onward, Up retains a
running-jump request until the first legal run pose (7), without rewinding
the startup into a standing jump. This narrower input-tolerance extension
preserves the ordinary standing chord; takeoff alignment/range are unchanged.

### Ctrl Taps During An Attack (2026-10-31)

The port used to keep two attack extensions: a Ctrl press survived its
release until the next gate, and a press during poses 151-153 (162 for a
counter) was consumed without a swing. Both are removed (user decision);
the armed bank's modifier word is now the only attack request.
`tools/probe_attack_taps.py` executes the sample 4:3e84-3f42 and OnAlert
6:24bc with its bodies frame by frame over 512 Ctrl patterns from the guard
pose (SEQS 75 poses supplied): zero mismatches against the closed rule. A
strike consumes Ctrl (2); a release writes 0; a new press is -2 and DoStrike
admits it at pose 157 or the guard poses. A second tap released before that
gate is therefore cancelled, so a double tap swings once, as on the Mac.
A second press still held at the gate swings again. The scene regression
(`test_ctrl_taps_during_an_attack_swing_as_the_native_frame_trace`) replays
all 512 patterns in both facings through the key callbacks and gives the
same strike frames; both former extensions fail it.

## Hard-Fall Recovery Input

HitFloor selects SEQS:20 for a surviving, damaging Prince fall. Its link to
212 holds pose 109 for 21 frames, then rises through 49. GenCtrl's mode-5
gate (6:0576-059c) clears directional latches during poses 108/109/110-116;
pose 117 returns to mode 1. Original instruction execution confirmed 72
reset/resampling cases across both facings, nine protected poses, held or
released Up, and fresh or consumed old Up. With Forward still held, a
released Up resumes running at rest; keeping Up held selects a jump instead.

The directional bank owns the whole recovery: SEQS 20 and 212 joined the
low family that already owned 49, so its mode-5 clear runs at 108/109 too
and key callbacks never write the host slot there (the former per-tick
slot discard is removed). Physical holds stay; a held key becomes a fresh
request at the first sample after mode 5 and is admitted at the standing
gate. Ctrl uses the modifier lifecycle above rather than a stored draw
request. Released Up does not produce a delayed standing forward jump.
Requests sampled after the mode-5 portion are ordinary bank requests. Animation poses, recovery duration,
impact damage, ordinary soft landings and wall-impact/climb queues are unchanged.

Controller regressions cover taps and holds at 14 protected recovery updates
in both facings, a late tap at pose 117 and held/released Ctrl. A real-terrain
fall checks that the complete recovery/run trace matches the no-Up baseline
in both directions, with exactly one life lost.

## Input During Falls

Every fall starts in mode 3: StartFall's SEQS 7 (-> 214), 18, 21, 81, 95 and
228 show poses 102-105 (198 starts in mode 5). The free fall is mode 4: pose
106 at the end of 214 and the loop SEQS 12. Every landing starts in mode 5
(SEQS 17 at 107/108, 20 -> 212 -> 49, death 22). PlayerCtrl 4:3cae samples
the keys every frame and GenCtrl runs for the falling Prince, but no branch
matches poses 100-106; mode 4 and mode 5 reach ClearControls at 6:0576-059c.
A directional tap made during a fall therefore never reaches a gate: the
free fall or the landing discards it, and a key still held becomes a fresh
request after the landing's mode-5 poses. The modifier is not cleared there,
so Ctrl held through a landing draws at the standing gate.

The port has no bank while `terrain_motion.falling` (the bank families check it)
and reads held keys at the landing's gates, which gives the same outcomes.
A 2026-10-30 trace (level 3, room 21, collapsing floor, Ctrl held) lands
through 20, 212 and 49 and draws (SEQS 55) after pose 119.

Catch 4:37cc tests the modifier word, not Shift: Shift and Ctrl share it
(4:3f08), so either held key catches. The port caught only with Shift,
although Ctrl already kept the hang (6:18e0); `catch_falling_ledge` now takes
either (regression: `tests.test_ledge_catch` "Ctrl held through the collapse
catches the same ledge").

Catch and SEQS 15 (mode 3), 9 and 210 (mode 2) clear nothing, so a catch
made before the first mode-4 frame keeps the directions still pending. In the
same room-21 collapse the catch comes right after pose 105: an Up pressed at
poses 102-105 is still pending at the catch and climbs once the 12-tick grip
delay ends, released or not. The port discarded it at `begin_ledge_controls`
(a policy retained from the host buffer); on the user's 2026-10-30 decision
it now follows the native rule. The port still keeps no bank in the air, so
`latch_fall_key` records only a fresh Up pressed while a mode-3 fall pose
shows (the hang gate reads no other latch), and the end of a tick with a
mode-4 or mode-5 pose discards it. An Up held from the takeoff keeps its
existing inherited-hold handling: releasing it during the grip cancels the
climb. Regressions in `tests.test_ledge_catch`: an Up at 102-104 climbs 13
ticks after SEQS 15, and the free fall's first mode-4 frame drops it.

## Holding Up After A Climb

The native climb consumes Up at 6:19c8-19d0, but its pose 149 is mode 5.
GenCtrl's mode-5 gate (6:0576-059c) clears the consumed direction. The next
directional update at 4:3e84-3f08 makes a still-held Up fresh again. Original
instruction execution confirms the reset/resampling for both facings, with
Up held and released; the latter leaves no upward request.

The host's native-ledge entry cleared `jump_repeat_armed` without rearming it
after climbing. Climb completion now restores the existing held-jump repeat
only when Up remains held, after the actor has returned to its floor and idle
sequence. It keeps the press marked consumed until the next jump, so releasing
between completion and that jump cannot trigger the short-tap release fallback.
Tests cover repeated jumping, release during/immediately after climbing and two
real cavern climbs across an upper-room link, without fabricated ledge geometry.

## Climb And Turn Command Boundaries

Horizontal commands and fresh Up/Down during the protected climb
can now enter the host buffer without interrupting its poses. At the return
to idle, the old climb's protection and floor-relative offsets are cleared
before dispatching the queued command. A queued Down can deliberately begin
a new ledge descent; it must not be mistaken for stale climb protection.
The native mode-5 gate can clear released directional latches, so preserving
all tapped host commands here remains an input-tolerance extension rather
than a claim of complete native-latch parity.

GenCtrl 6:05fe-0618 routes standing-turn poses 50-52 to the standing
controller, not only after SEQS:5 links to idle. Ordinary buffered commands
now share that gate. Pose 48 can resume a held run even if the host classified
the direction as a turn before facing changed. The cavern entrance uses this
same standing turn; its normal held-arrow behavior is regression-tested
across every pose, independently of Alt+R's separate hold restoration.

Shift plus the opposite direction consumes only the standing turn
(6:0d4c/10e8). The port no longer carries its step request through the turn,
nor synthesizes a forward step from that same held combination afterward.
Releasing/repressing the direction permits a new step. Ordinary forward
Shift-step repetition and the existing repeated-command filter are unchanged.

### Releasing Up Before The Climb Finishes

The climb's mode-5 reset and the following keyboard sample (6:0576-059c,
4:3e84-3f08) discard the old overlap: if only Forward remains held at the
standing gate, 6:0db0-0dd0 selects running, not a forward jump. Executing
the original reset, sample and facing-remapped controller confirms eight
cases across both facings, held/released Up and pending/consumed old Up.

At climb completion, a buffered directional jump is therefore reclassified
as run/turn/Shift-step only when Up is now released and that same horizontal
direction is still held. A still-held Up keeps its jump chord. A complete
released tap chord, a vertical jump, and other buffered actions retain their
existing host semantics. The rule also applies to releases during pause and
does not rewrite jump buffers outside the protected climb.

### A New Up After A Running-Jump Bump

The host formerly kept a vertical request through a grounded wall contact
only when the interrupted sequence was the run brake (13). A running-jump
impact can instead enter 46, link to crouch rise, then contact the same wall
again before standing. That second correction erased the new Up request.

Any unfulfilled vertical jump now survives these grounded wall corrections;
the recovery poses and collision offsets remain unchanged. This is separate
from the already-consumed jump that hit the wall, which must not replay.
Airborne falls, death and directional jump buffers keep their old clearing.
As elsewhere in the host buffer, preserving a released Up tap is an input-
tolerance extension, not a claim that native mode-5 latches preserve it.

Integrated regressions run/jump from room 21 into room 26 using real cavern
geometry, queue Up at six recovery poses, and check that held Up climbs to
the upper floor. A released tap reaches the ledge but does not invent a
second climb request. Existing consumed-Up wall-bump regressions still pass.

### Keeping The Original Up Held After Impact

The previous recovery test released the takeoff Up and pressed it again.
It did not cover keeping that same Up held and releasing only the horizontal
key. The host never enqueued this change from a running-jump chord to vertical
intent, so protecting an existing request at wall contact could not fix it.

Releasing the last horizontal while Up remains held now buffers a vertical
request during SEQS:4 or grounded impact recovery 46/47 (including their linked
poses). It does not interrupt the current animation or rearm Up merely because
a wall was hit. Released Up, locked controls, sword mode and native ledge
sequences do not synthesize this request. Paused releases use the same rule.

Original instruction execution confirms that mode-5 impact recovery clears
the old consumed directions (6:0576-059c); sampling at 4:3e84 makes a held Up
fresh, and the standing controller selects DoJumpUp (6:1600) with no horizontal
held. Both facings and held/released Up were checked. The host buffer remains
an approximation of those native latches, not a complete latch translation.

Real-terrain regressions keep the takeoff Up continuously held, release the
horizontal at 13 arc/recovery/rest poses, and reach the upper floor in room 26.
Each case also runs with the release during pause. Controller tests cover both
facings and released-Up negatives; the previous consumed-jump and climb-chord
regressions remain separate. F3's room-21 entry now uses its lower floor instead
of the isolated upper shelf; this is only a developer spawn hint, not physics.

## Buffered Chords After A Running Reversal

SEQS:6 finishes every drift pose 53-65 before flipping facing and linking to
SEQS:202 at pose 13. GenCtrl does not dispatch a jump from those drift poses.
Once the running poses resume, 6:1216-1242 checks Backward before fresh Up;
Up calls DoRunJump with SEQS:4, whose legal Prince poses are 7-14
(6:1c14-1c34). This choice belongs to the current controller pose, not to
the time when a host key callback entered the buffer.

The host stored `running=False` when Up arrived during a released-direction
gap in the drift. The second chord key updated its direction but kept that
stale classification. It then missed the pose-13 running-jump gate and launched
SEQS:3 at a run-cycle boundary, inserting standing preparation into a running
reversal. Buffered directional jumps now use the live running classification
at dispatch, and the ordinary running/reversal gates no longer require that
classification to have been captured by the first callback. Standing-turn
and run-start chord gates, vertical braking, takeoff geometry and the 300 ms
repeat filter remain unchanged.

Original GenCtrl/DoRunJump execution matched 384 controller/flat-floor cases:
both facings, all drift poses and run poses 4-14, pending/consumed Up/Forward,
and Backward priority. Imported rooftop and animation regressions compare both
chord orders after four/five released-direction ticks, including tapped inputs.
They retain all remaining drift poses and transition 13 -> 34 without the former
standing pose 16 or an extra run-loop displacement.

### Repressing The Drift Direction

During SEQS:6, `run_direction` already names the chosen post-drift direction,
but sprite facing remains unchanged through pose 65. Repressing that direction
was therefore classified as a second turn. Short gaps let the repeat filter
discard it without cancelling the stop request; longer gaps queued a turn that
became a new SEQS:1 run start at the cycle boundary (13 -> 14 -> 1).

Resuming the chosen running direction now cancels the stop request for both
host `run` and `turn` classifications, without queuing a new sequence. Steps,
jump chords, standing turns and the 300 ms repeat filter are unchanged. The
existing sequence remains responsible for 53-65 -> 13 -> 14 -> 7.

GenCtrl 6:11e4-1274 brakes only when both horizontal controls are absent at
poses 7/11. Fresh or consumed Forward otherwise leaves the running sequence
untouched; Backward starts SEQS:6. Native execution confirmed 144 additional
continuation/braking cases across both facings and every run/drift pose.
Regressions compare full pose, position and facing traces with an uninterrupted
held run, including gaps below/above 300 ms and represses after the facing flip,
plus the same release/repress sequence on the imported level-one rooftop.

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

## Windows External Capture Keys

F9 and F10 are reserved for external capture tools in the host input layer.
Press/release and auto-repeat do not change gameplay, retry after death,
skip the intro, operate a modal menu, or resume an intentional pause. This
does not register a global hotkey or invoke NVIDIA capture; F8 remains the
port's own screenshot command.

Windows Tk 8.6.10 installs `tk::WinMenuKey %W %N` on the `all` bindtag for
F10, even when the application has no native menu bar. Allowing F10 through
the host bindtag can therefore invoke native menu activation and interfere
with focus/pause while starting an external recording. The host now stops
that Tk fallback without changing focus-loss pause or recording settings.
Tests exercise all host modes/modifiers, real Tk bindtag dispatch and the
unchanged F8 screenshot command.

A separate NVIDIA screenshot failure remains unresolved in fullscreen,
including paused gameplay and F3 (which use Tk rather than the live bitmap
presenter). Local CaptureCore logs received `CAPTURE_SCREENSHOT` from the
hotkey, then timed out waiting for the DWM capture event (status 258), ending
with `0x80004005`. This establishes that the hotkey reached NVIDIA, not the
cause of its fullscreen capture failure. No renderer replacement, layered
window workaround, screenshot-key remapping or NVIDIA setting change is
claimed as a verified fix.

## Low And Prone Consumption Extension (2026-10-28)

[Low/prone input consumption](research/low-input-consumption.md) reuses earlier
crawl geometry evidence and extends the input audit with 76,357 matching native
calls/steps. It executes actual JumpSeq selection/cursor writes, ordinary
no-gap crouch entry and low/prone controllers. One hundred persistent steps
check held/released inputs through protected lower/rise and crawl boundaries,
including saved-bank ownership. Pose/terrain progression and special action
endpoints remain supplied; this is not whole-frame or complete runtime parity.

The concrete runtime correction allows Shift + Forward to use the existing
low-step path when crouched, including input during lowering. Previously it
was stored as a standing cautious step and the Prince remained stationary.
The directional command slot itself has not yet been replaced. The next
migration work must reuse these results rather than repeat the same isolated
bank/controller audit or add an expiry to the current slot.

## Implementation Order

The first six production stages cover deferred standing-turn,
cautious-step, grounded running, ordinary/running jump3/4 and vertical14/28
through landing11, native hanging/release/climb, and ordinary crouch/prone input:
[scope and validation](research/directional-bank-runtime.md).
The independent research models remain separate from runtime. Continue the
remaining families using the recovered gates, extending native-bank ownership
and removing each superseded producer/consumer together.

The [airborne handoff audit](research/airborne-handoff-audit.md) identifies a
the former late-jump boundary: Up/Down taps replaced one another before
reaching the migrated standing gate. The same eight actual host scenes now
agree with the84 bounded original/model routing steps. Bank ownership through
SEQS3/4 and its pose26/44 clears replaces the old arc slot/reset paths;
The [vertical handoff](research/vertical-input-handoff.md) extends this into
14/28/11, with early67-69 Forward admission and protected83 clearing. Its
16 actual host cases now agree with112 bounded original/model steps. Other
airborne families are still separate work. The
[ledge handoff](research/ledge-input-handoff.md) now carries the bank through
native entry, hanging, release and protected climbing. Its1170 bounded original
gate/prefix cases match the independent model; Ctrl hold and grip-delayed Up
use that gate; the protected-climb tolerances were removed on 2026-10-31.
The [low handoff](research/low-input-handoff.md) now replaces the low/prone
slot and raw-held crawl routing with that bank. Protected rise clears released
Up instead of replaying a jump; low-step conflicts and prone taps use the
recovered priorities.25,928 production/model observations reuse the existing
native audit. Source46 recovery (native since 2026-10-30) and the
low-repeat/release policies (removed 2026-10-31) are no longer exceptions.

The first [armed priority stage](research/armed-input-priority.md) checks
OnAlert6:24bc-2584 against19,440 original/model cases. Its second stage runs
the action bodies too (71,280 cases) and makes the bank the sole owner of
armed requests: refused requests stay pending, accepted ones consume as the
original, and consumed holds no longer repeat sword steps or blocks. The
former attack-survives-Ctrl-release and rapid-attack policies were removed
on 2026-10-31 (native frame traces above). This is not full SwordCtrl parity. SwordCtrl's last step is now
in production as well: with no engaged opponent within reach (alert below 2
and no loose floor or shelf underfoot, or more than 330 ahead), a pending
Down sheathes at once at any mode-0/1 pose (6:2382), ahead of an attack.

The [slot census](research/remaining-host-slot.md) then found no production
writer of the old host slot across all 3,291 tests; the drink and the sword
pickup, which tests did not press through, were the last reachable writers.
Both now keep the bank, and the slot, its dispatcher and every family's
one-shot import are removed. The prototype rooftop without a level map
dropped taps during its host climb; that climb plays the wall stop SEQS
46 -> 49, so the low bank now owns it as it owns the real stop: taps at the
mode-5 poses 107-116 are discarded, taps at 117-119 act at the standing gate,
and a held key acts at the transition to idle (regression:
`tests.test_low_controls` "prototype climb taps follow the low bank"). Its
host hang (SEQS 7/12, fall poses) keeps the Up climb request. The throne collapse and
wake (SEQS 237/231) later joined the waiting bank: the vision's ClearControls
(7:39ca) discards presses made during the collapse, and a press during the
wake waits for the standing gate.
A later census of the producers that fed it found every production call
already latching into a bank; the generic bridge became `latch_request` for
scripted requests, and a release made while paused now follows the owning
family's release rule (it used to turn a running chord into a running jump).
That release rule was then retired for the native one (user decision): a
release creates no request (4:3e84), so an Up pending in a run with no arrow
held takes off as a running jump except at the 7/11 brake gate, in either
order of Up and release (`docs/research/remaining-host-slot.md` section 3).

1. Translate five native latches, sampling, facing remap and consume/reset
   operations in `mac_input`. Test every directional/modifier transition.
2. Integrate standing/turn/step/run, jump resets, crouch, ledges, then sword
   gates. Remove each superseded host queue path; do not run two buffers as
   simultaneous authorities. Preserve documented intentional port extensions
   rather than treating every original-game difference as a defect.
3. At protected poses, test input before/at/after reset, released versus held,
   both facings, modifier changes and conflicts. Check pose order/offsets too.
4. Run real scene tests with terrain, combat, screen transitions, pause/F3
   and focus loss. Host modal resets stay distinct from native ClearControls.
5. Use original recordings or traces for unresolved sampling/update timing
   and special branches instead of assigning unsupported semantics.

The original audit phase added documentation and executable comparisons;
the later runtime stages above now replace the covered parts of the buffer.
Animation clocks and the approved running-jump fix are preserved. Routine-level progress is in
[RECOVERY_INDEX.md](RECOVERY_INDEX.md).
