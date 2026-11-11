# Level 14 handoff for Claude

Prepared 2026-11-11 from published main `fd167a9`. The user asked for this
handoff because Codex weekly usage is nearly exhausted. This milestone makes
no gameplay changes and does not claim either newly reported bug is fixed.
Continue the assigned final-level integration without asking for authorization
again for routine research, fixes, tests and publication.

Read `docs/PARALLEL_WORK.md`, the shared `../COORDINATION.local.md`,
[final-level-preparation.md](final-level-preparation.md), and
[the Macintosh video reference](final-level-video-reference.md) before editing.
Use a separate worktree. Reserve an integration slot before publishing main.
Do not operate the player's live game/emulator or shared saves/settings.

## First priority: two current playtest failures

The player launches `run_game.py` in the primary workspace. Do not ask again
which executable they use. Latest reports, received after `fd167a9`:

1. Descending native room 1 -> 2 triggers NIS 5 as soon as the Prince lands,
   still crouching. The original video shows him land outside, then walk into
   the tower window before the spell starts.
2. After entering the tower and reaching native room 4, the Prince draws his
   sword and the game freezes, leaving no usable controls.

These reports supersede any earlier statement that the room-2/4 route works.
The earlier missing `scene-0-31030` audio registration was a real separate
failure, repaired in `7c5e98c`; it does not establish that the current route is
correct. The local primary and Codex audio manifests were repaired, but an
already running game retains its old AudioEngine until restarted.

### Bug 1: admission geometry lead

`Final.frame_start` in `pop2/environments.py` snapshots
`scene.player_bounds()[2]`, and `Final.frame_hook` compares it directly with
486. CODE 9:0760-077c reads the saved Prince room, native right drawing edge
at a5-0x3566 and saved animation state. The native gate is room 2, edge <=486,
animation state !=4. The native X origin is commonly 207, whereas the port
sprite bounds are local scene coordinates. An omitted origin conversion is
therefore a strong lead for the early trigger; it has not been independently
verified for this exact cached edge. Trace `GetCharEdges` 4:5cbc and the
inclusive rectangle convention before applying the correction.

The existing 27-case `tools.probe_final_spell_gate` supplies the bound as an
input. It proves the native comparison, not the host bound's coordinate
conversion. Do not replace the spatial condition with a crouch delay or a
timer to make the video appear to match.

The current `test_room_two_full_animation_loop_with_audio_reaches_room_four`
in `tests/test_final_spell_flow.py` synthesizes a room-1 fall at local X250
and expects the cutscene shortly afterwards. That test can admit the reported
premature trigger. Replace its route fixture with a real outside landing and
window approach, retaining an explicit regression for the previous behavior.

Acceptance: landing/crouching outside leaves gameplay active in room 2;
walking inside the window triggers NIS 5 once. Compare the video at 00:42.5
(hanging), 00:43.5 (window), 00:44-00:44.5 (entry), and 00:45.5 (scene).

### Bug 2: continue beyond the NIS callback

Audit `Final.finish_spell`, `ScenePrototype.finish_tree`, `advance_animation`,
`run_world_phases`, `start_sequence`, and the subsequent control/audio/render
tick. The host currently places the Prince in native room 4, row 1, initial
native X484/local X277, retains life/capacity and mode 13, selects SEQS55 and
advances it to action207/local X283. These post-scene choices are only partly
recovered; do not treat them all as proven Macintosh state.

The current full-loop regression stops when `scene.intro` becomes None and
asserts room 4. It does not establish that gameplay remains responsive after
the sword draw. Capture the first exception through Tk's callback exception
handler, then run enough post-scene ticks and synthetic press/release inputs
to exercise movement, turning and sword controls with a real AudioEngine.
SDL's dummy audio device avoids interfering with the user's sound output.
Do not swallow an exception or merely reschedule the tick around corrupted
state. Preserve frame-phase ordering and the existing control/cache safeguards.

Acceptance: the real 13 -> NIS3 -> tower/window -> NIS5 route and F3 room-2
entry both complete, then room 4 responds to controls for at least several
dozen ticks. Cover the landing/window boundary and the first gameplay ticks
after NIS completion, not just direct callback invocation.

## New manual evidence: Shadow Man and fireball

The user supplied a screenshot from the official manual's Magic section.
The numeric keys shown there refer to keypad directions: 4/6 are left/right,
and 5 is down. Preserve the port's approved bindings while implementing the
underlying actions.

- Rapidly alternate left and right, repeatedly turning, to become Shadow Man.
- Transformation requires at least nine strength units.
- The physical body falls and remains motionless while the shadow moves.
- Stand beside the body and crouch/down to rejoin it.
- A bluish glow indicates possession of the magic fire.
- A fireball requires at least three strength units; face the enemy and press
  Control (or keypad 0 in the manual). Throwing costs one strength unit.

The user reports a maximum capacity of 12 and suspects at least 11 is needed
to finish. The video appears to show 12 before transformation and four after
it. If the transformation costs eight and fireball admission requires three,
11 would follow as a minimum for that route. This is an inference, not a
recovered native rule. Probe admission, the per-turn accumulation/drain,
floor/clamping, life versus capacity, and flame ownership separately. Do not
hard-code a whole-level minimum of 11 from this calculation.

## Room 3 is an optional recovery mechanic

The user deliberately skipped the tree/tarantula room in the winning video
because they already had enough health capacity. They explain that its
respawning opponents can drop a Life Enhancement Potion, allowing a player
who missed earlier increases to prepare for the final transformation. Keep
this route in the integration; it is not decorative or obsolete content.

The [archived strategy-guide page](https://popuw.com/story/pop2-14-15.html)
supports respawning opponents and both enhancement/healing drops. It also
describes careless copy encounters as potentially fatal in one strike, a
sword-resistant final Jaffar, and reversal of the pursuit after a missed
fireball until a healing potion restores the flame. These are secondary
reference leads: verify their Macintosh rules in the executable. The page
labels sections 14/15; the user explicitly identifies this entire sequence
as Macintosh level 14. Its title attributes it to the official strategy guide;
that provenance was not independently authenticated in this handoff.

Source boundary already identified: CODE 9 `FinlCheckDeadOpp` 9:00e2-01ec,
called for final room-3 type-2 opponents from GenCtrl 6:07b8-07d6. The reading
around 9:00ea-0194 tests the death-counter phase, tile/support state, object
capacity and a random result before writing a potion tile/attribute and
requesting redraw. Follow the two nonzero `Rnd(2)` outcomes through the potion
decoder to establish enhancement versus healing and their actual chances.
Do not confuse the guard's death timer/registered death with HP or the
generator's room-bank count. The 216-case admission probe excludes this drop
routine and does not verify it.

## What is integrated and what remains

- `7c5e98c`: final story audio validation and the earlier local audio-manifest
  repair. Current landing-trigger and room-4-freeze reports remain open.
- `708e490`: raw kind 3 -> actor 6, room-6 SEQS2/Kid pose15, room-11
  SEQS197/pose297, false-Prince CTBL25008, snapshot support. Six original
  selector/frame-bank cases passed with explicit supplied endpoints/handles.
  Scripted copies currently animate without ordinary guard AI/terrain;
  their riddle/controller is not implemented.
- `fd167a9`: winning-video timeline and a 12-case native completion-caller
  probe. Final dispatch is NIS11 then HallOfFameDialog(remaining minutes),
  with both endpoints supplied. Runtime final epilogue/Hall/intro return are
  not implemented by that research commit.
- Existing `ending.json` and `start_ending` are the level-1 -> 2 voyage,
  NIS9/CODE15:0cf2. Final victory must recover NIS11/CODE15:3c76 with Happy
  resources; do not route it into the voyage.
- Native rooms 3/9 and 8/10 retain different links/terrain/actor records despite
  shared artwork. Room 11 is a scripted bedroom destination, hidden from F3
  walkable-room selection. Keep the user's vertical F3 layout 1 -> 2 -> 4.

After the two bugs, continue the bounded order in the video reference:
room-6 controller 9:1526 and SEQS240 removal/last-copy handoff; final actor
path 9:16fe; separate body/blue form and fireball; victory bedroom and NIS11;
Hall of Fame and intro return. The winning video does not show the player's
death/laughter variant or a palace visit before the copy sequence, so those
conditions remain unverified.

## Validation and local material

Use the worktree's own `.venv`, imported assets and the project checks in
AGENTS.md. Native probes are `tools.probe_final_spell_gate`,
`probe_final_clone_frames`, `probe_final_jaffar_generation`, and
`probe_final_completion`; read their supplied endpoint/exclusion comments.
Tests to start with include `tests.test_final_spell_flow`, `test_final_clones`,
`test_final_jaffars`, `test_development_map`, `test_frame_phases`, and the
appropriate control/sequence/audio tests after diagnosing the freeze.

The last full discovery covered 4,101 cases in separate module processes to
avoid Tk memory accumulation: 4,090 passed, 10 skipped, one existing menu-size
failure (row bottom371 > panel357), independently reproduced on the earlier
main. Do not spend this assigned milestone fixing that unrelated menu test.
Physical-focus tests remain excluded while the user's desktop is in use.

The shared local coordination board records the original video location.
The primary ignored `rendered/final-video-reference/reference-overview.jpg`
is a reviewed visual index; detailed half-second frames/contact sheets are
in the Codex worktree's matching rendered directory. The source recording
and original recovered Macintosh resources remain read-only references.
