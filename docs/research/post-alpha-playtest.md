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
