# Parallel Work And First Orientation

## Division Of Work

The intended split is Claude researching enemy AI/game rules while the user
and Codex work on other features. This document sets up that collaboration;
it does not authorize an open-ended AI implementation or an automatic merge.

Use separate Git worktrees and branches. The primary working directory stays
on `main`. The prepared research worktree uses `claude/ai-research`. Changes
are not shared until explicitly integrated. Commits are safe in the research
branch once an implementation task has been assigned; do not push to or merge
into `main` yourself. Both worktrees share Git history, not conversation state.

Worktrees do NOT prevent semantic conflicts. Agree on the task and affected
files before editing shared gameplay code, especially `combat.py`,
`scene_prototype.py`, `sequence_runtime.py` and save schemas. After integration
of either branch, reassess dependent changes and rerun the appropriate tests.
Do not casually rebase another agent's branch or cherry-pick an unfinished
series. Integration belongs to the user/assigned integrator.

Original game data and recovery files are local, not included in Git. The
prepared worktree has its own asset/probe copies and Python environment;
original recovery files remain shared read-only. Do not assume a Git checkout
or future pull refreshes ignored files. Do not operate the same game window,
modify shared saves, or run multiple Tk/GUI test suites concurrently.

## Reading Order

1. `CLAUDE.md`, `AGENTS.md` and `CLAUDE.local.md` if present.
2. `docs/AI_RESEARCH_HANDOFF.md`, the current-state summary.
3. `README.md` for the playable scope and intentional improvements.
4. `docs/RECOVERY_INDEX.md` for coverage notation and branch ledger.
5. Relevant sections of `docs/AI_RECOVERY.md`, then the END of
   `docs/AI_INVESTIGATION_LOG.md` for corrections and provenance.
6. The relevant implementation, tests and original CODE instructions.

`BEHAVIOR_MAP.md` is a navigation aid, not an authoritative current checklist.
Some broad gap descriptions and early chronological conclusions are stale.
Do not read every historical document into context before doing a small task.

## First Message

The following is a suitable first message after opening the research folder:

```text
Read CLAUDE.md and follow the first-orientation instructions in
docs/PARALLEL_WORK.md. Do not edit files, install anything, launch the game,
or make commits yet.

Explain in European Portuguese, in your own words:
- What this port does, what is playable, and what is still incomplete.
- What is established about enemy AI versus hypotheses or partial coverage.
- The important corrections and intentional port improvements to preserve.
- Whether the local original-code files, assets and probe tools are available.
- Which small research task you recommend first, and how you would validate it.

Distinguish the repository's recorded evidence from anything you personally
verified. Flag conflicting or stale notes. Wait for approval before changing
anything.
```

Orientation may inspect status, code, resources, instructions and tool versions,
but must not run probes that write reports or launch a GUI. It should identify
what would need execution later, rather than claim historical checks as its
own fresh results. Do not change the workspace to repair onboarding problems
without reporting them first.

## First Assigned Research Block

Start with the bounded scheduler/cache investigation proposed in the handoff,
not "finish all AI". A good first deliverable is an evidence report and a
small reproducer on the research branch. Production changes are a separate
explicit assignment after the report establishes a real difference.

For each completed block, report the base and resulting commits, affected
files, native addresses, reproduction commands, tests and their outcomes,
supplied/stubbed endpoints, limitations and the next specific question.
Do not claim full AI parity or game-wide coverage from a passing subset.
