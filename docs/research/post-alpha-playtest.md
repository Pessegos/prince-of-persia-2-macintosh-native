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
