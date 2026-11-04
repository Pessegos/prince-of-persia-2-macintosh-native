# Post-alpha playtest fixes

## Time display and native window focus

Space had no gameplay handler, although `StoryProgress` already advanced the
clock and emitted its automatic messages. Connect a fresh unmodified Space to
the existing message formatter/duration, once the campaign clock has started.
The original request is ReadKeyboard CODE2:4850-485e. Scene regressions cover
levels6-9 after teleport and the deferred clock in level3. This is HUD wiring,
not a new clock or input-queue policy.

F9/F10 already stop Tk's default menu bindings. A native menu can nevertheless
leave Tk without a focused widget while the game remains the Windows foreground
window. That state must not count as switching applications. Check the actual
top-level HWND before auto-pausing on empty Tk focus; a real focus transfer to
another window retains the previous pause behavior. Unit checks cover this
distinction without taking physical focus. Reproducing NVIDIA's first-recording
overlay on the user's machine remains a manual check.

## Inverted jump key admission

The inverted key mapping already maps physical Down to logical Up. Grounded
running uses the migrated directional bank and correctly starts a held jump.
The remaining host paths were inconsistent: upright Up used `up_key` on the
press, whereas inverted Down reached a generic branch which deferred the same
request until release. Both now call one logical-Up press handler, after the
existing mapping and modal guards. No new queue, expiry or native rule is added.

Hidden scene checks compare upright/inverted held run-jump traces and a second
jump press during an ongoing jump. The latter failed before the correction:
only the upright key created the deferred request. This is host input parity,
not a claim that all upside-down controls match the Macintosh frame for frame.

## Retry report

The user retested Alt+R and could no longer reproduce the reported gate state
problem. Existing checkpoint-world restoration remains unchanged, including
its saved collected-item state and intentional persistent native globals.

## Ruins slab surfaces and the reported clipping

**Corrected 2026-11-04 using the user's Macintosh recording.** The former
full-slab actor mask was excessive: it erased the hands and forearms during
the reach/catch poses79,80,91. In `macintosh correct arms hands.mp4`, around
2.03 seconds, the hands cross the slab's perspective surface intact. The
corresponding pose around2.28 seconds in `port clippedarms hands.mp4` loses
both hands. The later supplied stills isolate the same difference. These are
pose comparisons, not a replay of identical recorded inputs.

The matching scene is level6 native room4 (port room3), lower row2, facing
left, after loose cells12,13,22,23 have fallen. Starting at X108 and pressing
Up reaches poses79,80,91 at X122 before climbing. The old tests instead forced
a right-facing hang over intact slabs. That different geometry did not
establish how the original should layer the hands in this route.

Remove the additional alpha mask made from back-layer Ruins SHAPs3514-3519.
Ordinary foreground masks and the exported native QuickFloor/DrawFloorBuf
and DrawHalf repaints continue to determine occlusion. Cutting the extra mask
only at the logical floor plane would still erase the lower forearm visible
in the recording. No sprite, movement or native repaint command changes.

The scene regression follows the fallen-slab jump through the three affected
poses and the completed climb. It checks the fingers at viewport(124,224) and
forearm at(125,230), including the one-pixel room origin. It fails at all three
poses against the preceding production code. The older tests that required
the entire back-drawn slab to cover every actor pixel are superseded by this
Macintosh evidence. Existing DrawHalf/pillar and falling-floor regressions
still cover native foreground order. No new native execution probe or claim
of complete room drawing equivalence is made here.

The room8 body split during climb poses135-144 is separate: the native DrawHalf
surface pass itself crosses the body. The committed repair preserves it. A
local comparison prototype draws the Prince in front of the slab lip during
those poses, retaining the original sprite and movement. It removes the split
but changes apparent depth; keep that subjective proposal out of production
until the user reviews it. A larger downward occlusion was rejected locally
because it concealed too much of the legs and caused a visible reappearance.

## Wall spikes: deferred by the user

Reproduced armed retreat at level5 room23. At some starting alignments the
Prince dies with the existing backward impalement; at others the outward
poses1/2 end before contact and he reaches an extended stationary trap.
MobSpikes5:3fa4 and CheckSpikeHit5:3af8 distinguish those phases. No stationary
trap lethality change is justified from this reproduction alone. The user
explicitly deferred this point until a Macintosh recording is available.
Resolved 2026-10-31 without a recording: the whole-frame order matches the
original and only alignments X 237-240 die (docs/CAVERN_RECOVERY.md).
