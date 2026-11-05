# Throne checkpoint and retry playtest

The user clarified that level8/native room9 becomes a retry checkpoint only
after both the vision and physical collection of the floor sword. Until
then Alt+R must use the earlier room12 checkpoint. This is an explicit port
policy: the recovered Checkpoint.matches leaf still checks the logical sword
word, while the host now additionally requires actual item consumption.
The earlier native leaf probe did not establish this complete gameplay rule.

`CavernState.throne_sword_collected` derives completion from `throne_done` and
the existing consumed-item record for room9/cell25 in Potions.tiles. No new
saved field is added. The checkpoint is first captured after pickup, so its
world snapshot already lacks the floor item. Retry and save/load therefore
cannot restore an earlier uncollected version while equipping the new sword.
An older premature room9 snapshot is repaired before immediate retry: use
room12 when uncollected, or recapture the completed pickup state when the
current world has collected it but its older snapshot has not.

When retry restores level8's checkpoint world, the logical sword and loaded
art are reconstructed from that world's pickup state: old sword before the
pickup, father's sword afterwards. Exit admission and the vision's separate
logical sword word retain their existing behavior during ordinary play.

F3 warps previously simulated checkpoint progress using numerically ordered
room labels. Room9 then incorrectly won for a warp to room11, even though
the earlier checkpoint is room12. Warp selection now applies the same throne
eligibility rule and falls back to room12 when that earlier story checkpoint
is absent from the numeric prefix. Other levels keep their existing warp
policy; no room links or level data are changed.

`tests.test_throne_retry` covers the earlier checkpoint followed by wake and
retry without pickup; physical held-Shift pickup and persisted item removal
through retry/save/load; room11 warps before/after the vision; and repair of
an older premature snapshot. The previous implementation fails those routes.
