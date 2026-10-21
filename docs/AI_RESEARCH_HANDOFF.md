# Current AI Research Handoff

Prepared 2026-10-21. Gameplay baseline: `c2d561c` on `main`. This document is
an entry point, not proof of complete recovery. Verify the actual checkout
and any subsequent changes before starting. This handoff adds no gameplay.

## Project And Evidence

Native Windows/Python reimplementation of the Macintosh game, using imported
original resources. Levels 1-3 are playable from start to finish. The core is
substantial, but exact scheduling, exceptional branches, later controllers
and levels 4 onward remain incomplete. All CODE bytes being available does
not imply all conditions are understood. The 1,198 named routine markers and
the other reference port's function counts are not completion percentages.

At the gameplay baseline, full discovery passed 1,958 tests in 365.818 seconds:
one optional skip, four expected failures, no unexpected failures. Existing
Tk teardown warnings were present. These are historical results, not a fresh
execution by the next agent. Tests run 39599875981 for `c2d561c` and run
39597163076 for `7c9b249` both completed successfully on GitHub.

The public repo does not contain original resources or the local native
probes. Preparation and fresh smoke-check results belong in the ignored
`CLAUDE.local.md`. Paths below are relative to a sibling research worktree.

## Where To Look

| Area | Files |
| --- | --- |
| Ordinary guard control, room banks, contacts | `pop2/combat.py` |
| Alert geometry and nearest-bank ordering | `pop2/enemy_alerts.py`, `pop2/opponent_selection.py` |
| Generation, cells, room normalization | `pop2/opponent_generation.py` |
| Ordinary record save/reload | `pop2/opponent_records.py` |
| Skeleton activation, collapse, persistence | `pop2/skeleton.py` |
| Animation interpreter and scene scheduling | `pop2/sequence_runtime.py`, `pop2/scene_prototype.py` |
| Frame physics and supporting geometry | `pop2/terrain.py` |
| Coverage and evidence history | `docs/RECOVERY_INDEX.md`, `docs/AI_RECOVERY.md`, `docs/AI_INVESTIGATION_LOG.md` |
| Native assembly and named markers | `../PoP2-Mac-Code-Recovery/code/02.asm`, `04.asm`, `06.asm`, `../PoP2-Mac-Code-Recovery/symbols.csv` |
| Native executable resources for probes | `../PoP2-Mac-Code-Recovery/resource_forks/Prince of Persia 2.bin` |

Native CODE segment numbers are not level numbers. Rooms shown to users and
native records are one-based; port room IDs are zero-based. Native character
X often includes +207. Distinguish anchors, cached supporting cells, current
versus selected sequence, animation mode, HP and native ALIVE.

## Established Subsets

- Ordinary combat, block/strike probabilities, alerts, pursuit, generation,
  supported obstacles, damage and several death branches have native-backed
  tests. Skeleton lifecycle and room record subsets are also implemented.
- `4aa8b56` introduced the ordinary GuardRoomRecord codec. `b483f41` integrated
  room save/reload, normalization, carried records and active banks. Selected
  current-room records precede visible side imports, with five active slots.
- Stable actor ownership remains in physical source-room lists; side actors
  use rebased views. Do not mistake `self.guards` outside local control for
  the complete active bank. Retain real identity when applying changes.
- `7c9b249` and `c2d561c` corrected whole-bank target selection, projected
  player turns/bumps, unarmed-noise consumption and corpse group/tumble scans.
- Terminal animation -23 rereads the resource pose after a cursor rewind;
  silent AnimCharTap(0) raises the Prince's movement flag without sound.

These statements cover the tested subsets, not all actors/environments.

## Critical Correction: Targets And Death Phases

Main 2:6300-633e retains an opposing-facing FrameAdv target even if dead.
SwordCtrl 6:2174-21fa separately validates a cached target using HP. The port
shares a combat target and MUST retain its HP validation. Copying Main's
retention gate into shared player control stranded the Prince on a corpse;
the broad suite caught it and `c2d561c` corrected it.

GetOppIdxClosestToKid 6:36f2 uses native ALIVE, not HP. A zero-HP candidate
can still win until the next NPC control registers death. One integration
trace is kill -> native-ALIVE pending -> registration during player pose 155
(mode 5, cannot turn) -> ready pose 156 -> turn. The fast carried-guard
regression now expects three ticks, not the prior HP-shortcut's one tick.

The current target probe matches 8,000 selector cases, 7,070 scoped Main
retention cases and 930 separate SwordCtrl dead-cache replacements. The
930 are NOT part of the isolated Main equivalence claim. This does not prove
the complete combined frame/control scheduler. Some earlier log paragraphs
describe the initial interpretation before this correction.

Skeleton selection retains HP-or-resume-flag compatibility; native ALIVE is
not yet unified across every initialization path. Do not globally redefine
`Fighter.alive` or erase the distinction to make a fixture pass.

## Intentional Exceptions To Preserve

- Dock guards stay down after the Prince catches the ship, including climb
  and exit music. This is an approved cinematic improvement, not a bug.
- Full destination-bank retention and swept contact are existing port
  safeguards, not claims of literal native memory behavior.
- Local cavern retouches are approved, room-specific artwork changes.
- Integrated save/load, screenshots, menu controls and other UI work are
  outside an AI assignment. Existing save compatibility must be preserved.

## Open Fronts And First Task

The next candidate is a READ-ONLY map of the target/contact update order:

1. Trace Main, PlayerCtrl/AutoCtrl, FrameAdv and SwordCtrl calls relevant to
   the Prince and ordinary guards. Record which working/cached actor each
   routine reads, writes or copies and when HP/ALIVE/death are updated.
2. Compare that map with scene scheduling, `refresh_target`, local bank views
   and `resolve_contacts`. Use the corrected death/turn trace as a baseline.
3. Identify one still-unproven boundary. If implementation is assigned later,
   construct an independent native comparison and a failing port regression
   before changing production code. Do not assume this audit must find a bug.

Other open fronts include special type 7/8 candidate metadata filtering,
remaining obstacle/hidden-slot rules, cached-FRAM skeleton ledge placement,
the shared global step counter and random stream, full-capacity native record
loss versus the port safeguard, and later controllers/level-four progression.
Do not launch all of these investigations at once.

## Native Probe Caveats

The prepared `rendered/` subset includes NativeClipper/NativeLoose and recent
selector, group, record, animation, alert, skeleton and Cut probes. The local
setup notes list the exact copies. Several helpers use this machine's
absolute native-program path; inspect it before use on another machine.

Probes supply or stub graphics, sound, resource lookup, support columns,
generator permissions, RNG results or other endpoints depending on the test.
Some older reload probes share the port interpreter; only independent
AnimChar variants validate the decoder itself. Original instructions include
68020 operations unsupported by the emulator, with documented adaptations.
Check imports and main guards before running a script; some older scripts
execute loops at import. Reports are local artifacts and must not silently
overwrite another agent's copy. Do not treat old JSON reports as fresh tests.
