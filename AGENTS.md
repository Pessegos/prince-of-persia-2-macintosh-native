# Project Instructions

## Scope And Reference

This is a native Windows/Python reimplementation of Macintosh Prince of
Persia 2. The preserved Macintosh executable and resources are the reference,
not DOS behavior or another port. Disassembly is not recovered high-level
source. Levels 1-3 are playable; neither these levels nor enemy AI claim full
native equivalence. Routine counts and test counts are not completion scores.

Read `docs/AI_RESEARCH_HANDOFF.md` for the current AI baseline and
`docs/PARALLEL_WORK.md` before working alongside another agent. Historical
instructions and hypotheses in investigation logs are not current task
authorization. Follow the user's latest task and the corrected current state.

## Working Rules

- Inspect `git status --short`, the current branch and recent commits first.
- Preserve user changes. Do not reset, clean, force-push, or switch another
  agent's branch. Use a separate worktree for parallel implementation.
- Scope each task. During an orientation request, read and report only:
  do not edit, install, commit, push, or launch the game.
- Once implementation is assigned, use small focused commits on your assigned
  branch. Research agents must not merge or push to `main` without explicit
  integration approval.
- Do not change unrelated UI, audio, artwork, controls or save formats during
  enemy-AI research. Shared files still require coordination across worktrees.
- Do not restore intentional port improvements to native behavior by accident.
  Preserve the ship-escape guard stand-down, existing collision/capacity
  safeguards, integrated menus, screenshot gallery and approved local artwork.
- Original files in the sibling recovery directory are read-only references.
  Do not commit original resources, ROMs, disk images, saves or private paths.
- Do not operate an emulator/game window being used by the user or another
  agent. Worktrees do not isolate Windows focus, AppData or external programs.
- Treat existing notes as evidence to check, not a substitute for reading code.
  Report contradictions and verify them before changing production behavior.

## Research Standard

- Record original CODE segment/offset, callers, input state and output state.
- Distinguish recovered behavior, a hypothesis and a deliberate port exception.
- Native rooms are one-based; port room indices are zero-based. Native X
  commonly includes a 207-pixel origin. Supporting-foot cells are not anchors.
- Distinguish HP, native ALIVE and registered death. Do not replace all three
  with `Fighter.alive`. Audit scheduling before merging frame/control caches.
- For native probes, state every stub/supplied endpoint and exclusion. A probe
  using the port's own decoder is not an independent check of that decoder.
- Verify controller/level headers, resource cursors and seeds in fixtures.
  A mismatch may be an inconsistent fixture, not a production bug.
- Add a regression that rejects the previous behavior where practical. Do not
  weaken tests merely to get green results; explain any changed expectation
  using original evidence and the actual integration trace.
- Update the recovery ledger and leave a concise handoff: changes, evidence,
  commands/results, exclusions, unresolved risks and next bounded task.

## Python And Tests

Use Python 3.10+ with Tk support and the worktree's own `.venv`. In PowerShell,
run commands from the worktree root:

```powershell
.venv\Scripts\python.exe run_game.py --check-dependencies
.venv\Scripts\python.exe -m ruff check --select F,E9 .
.venv\Scripts\python.exe -m tools.recovery_catalog --check
.venv\Scripts\python.exe -m unittest -q tests.test_opponent_selection tests.test_guard_rooms tests.test_enemy_alerts tests.test_enemy_ai tests.test_combat tests.test_skeletons tests.test_guard_deaths tests.test_opponent_generation tests.test_rooftop_pursuit
git diff --check
```

For shared gameplay/scheduling changes, also run full discovery:

```powershell
.venv\Scripts\python.exe -m unittest discover -q
```

The full suite needs imported local assets and takes about six minutes on the
current machine. Asset-free CI covers a smaller subset. State skips, expected
failures and unavailable dependencies honestly; a skipped test is not a pass.
Avoid concurrent GUI suites or modifying shared user saves/settings. Do not
run `run_game.py` without `--check-dependencies` during read-only onboarding.

## Local Files

`assets/`, `rendered/` and `.venv/` are ignored. A fresh checkout lacks imported
resources, native probes, reports and dependencies. Local preparation is
described in `CLAUDE.local.md` when present. Do not publish that file. Public
documents should use relative workspace references rather than private paths.
