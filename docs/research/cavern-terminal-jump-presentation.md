# Terminal Jump Pose: Presentation Improvement

The user requested a smoother level-three room19 -> room22 running-jump
transition that preserves the foreground stone and the existing gameplay.

The DOS recording is a visual reference for the requested continuity, not
a source of certified DOS game rules. In particular, its stone still hides
parts of the descending body. The Macintosh-style pipeline consumes jump
pose44 when CheckFloor/StartFall selects and immediately advances SEQS21.
The resulting pose102 is already hidden by the foreground corner. See
CheckFloor4:35ba and StartFall4:4cbe-4d90 for the original transition context.

This improvement retains that actual terminal pose at its drawing
point before fall alignment. On the first bottom-row run-jump -> SEQS21
falling update only, the renderer presents the retained pose44 instead of
the physical pose102. It rebases its Y into the advanced supporting row;
the simulation still executes the complete ordinary fall that update.
On the next update the extra drawing pose is cleared. Dev warps and level
loads clear it as well. The snapshot is host presentation state, never saved.

Admission is by actor/animation/row, not a room-number exception: cave Prince,
bottom supporting row2, running-jump source4/pose44, followed in the same room
by source21/pose102 and falling row3. Other jumps, fall entries, enemies and
ruins retain their existing drawing. Gate-crush drawing keeps priority.

Wall/pillar/custom/gate masks and floor drawing code are entirely unchanged.
The earlier proposal's mask bypass is absent. Tests for actual level3 room19
compare before/after renderings and reject any changed opaque foreground
pixel. Per-frame SequenceState/TerrainMotion/life traces also match, including
the original room22 arrival, unassisted landing damage and audio queues.

Reproduction: start room17 row2 X440 facing right, hold Right for two ticks,
then Up. The retained pose is X202 at floor Y346, rebased to relative Y-120
for supporting row3; the unchanged physical first fall is X217/Y366.
That one-update difference between presented pose and physical state is an
intentional animation exception, not a claim of exact DOS motion recovery.
The user approved the revised comparison on 2026-10-26. The improvement
retains the stone occlusion; it does not translate the DOS collision rules.
Validation includes 98 drawing/phase checks and 271 descent/terrain/UI/save/
cliff/phase checks, all passing. The pure drawing-pose admission tests also
run in CI without original game resources.
