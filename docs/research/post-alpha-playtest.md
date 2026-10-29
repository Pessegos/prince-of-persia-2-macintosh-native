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

The room4 screenshot can be reproduced with the stable wall-supported hang
pose91 at X108, physical row2, facing right. Blue turban pixels at viewport
(107,237) and (100,238) appeared on the platform above the near edge. A normal
vertical reach at X95 also leaked through its surface at pose79. The exported
room4 `floor_redraw` list is empty for the intact loose-platform layout;
QuickFloor2:69e6-6ac4 alone cannot repaint those pixels. Static scenery already
contains the corresponding Ruins surface SHAPs3514-3519.

Cache their full clipped surface alpha, and apply it only to the Prince
reaching/hanging below a higher floor. Pixels outside the drawn slab, including
the turban below its face, stay visible. No actor position,
animation, collision, resource or save schema changes. Commands come from the
current scenery variant, so fallen slabs rebuild the cover; reveal redraws
erase previous covers just as they erase other foreground masks. This is a
port drawing repair, not a claim of executing the complete native draw order.

Scene regressions cover both visible leaks and disappearing slab surfaces.
Viewport samples include the one-pixel room origin; background samples must
subtract that origin. Incorrect unshifted samples initially compared neighboring
rock pixels rather than the actual covered pixel.

The user's follow-up screenshot exposed detached fingers above the logical
supporting plane (Y226). The initial cover deliberately omitted that band,
which was incorrect: the perspective surface begins higher than the logical
plane. It now includes the entire surface silhouette. The regression samples
the actual finger pixels at viewport (104,222), (105,223) and (107,224), and
checks all hanging/swing poses87-99 against the scenery under that silhouette.
The former hand-preservation expectation is replaced by the user's corrected
requirement; pixels outside the slab are still tested for visibility.

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
