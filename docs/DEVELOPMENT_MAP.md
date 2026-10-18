# F3 Level Map

F3 opens a compact, tabless Developer Tools panel with Open map, Playback,
Peaceful mode and Resume. No level selectors or room dropdowns occupy this
entry panel. Open map enters a separate full-viewport workspace. Playback
opens a [visual scene gallery](PLAYBACK_GALLERY.md), with a back arrow and the
optional debug status bar. During attract playback only Playback and Resume are offered.
These are host development tools, not recovered Macintosh features.

## Source And State

`pop2/development_map.py` follows the actual LEVL room links. Each room covers
510 by 360 physical pixels: three 120-pixel rows, without HUD or viewport
overdraw. Shared rounded edges keep neighboring thumbnails stitched and their
hit regions consistent. The level-three map includes all 32 rooms. Levels 1
and 2 retain their existing supported teleport destinations and route labels.

Maps are regenerated from current `LevelRenderer` scenery, not loaded from an
old `level3-clean-map.png`. A private cavern/harbor state supplies stationary
torches, lava and flasks. Retained scenery uses the same deterministic route
as the clean map exporter. Setup preserves the global RNG; no live actor,
gate, potion, animation clock or room buffer is borrowed or advanced.

Original opponent records and artwork are included at their initial positions
and poses. Skeletons remain bones, including inert decorative piles; they are
not awakened for the map. Actor-aware masks and cavern foreground redraws use
the current room implementation, including overlap fixes. No AI ticks run.

## Interaction And Presentation

The map workspace removes the tools heading, tabs and floating panel frame,
and covers the full 510x384 viewport including the health/status strip. The
compact tools hub remains centered over the playfield, excluding that strip.
Its top bar contains a back arrow, a single level selector, and previous/next
level arrows with pointer tooltips. Back returns to the compact tools without
teleporting or resuming; the selected destination is retained. The map's lower
command strip contains Return to [room], Go and Resume. Peaceful mode remains
only in the tools hub. Return is disabled until a room has been recorded for
the selected level. Restart Level (including the death restart) records the
room before resetting; opening F3 while dead also records the death room. Each
level retains its own last room for this session. Return uses the ordinary
safe-entry teleport, not a save-state restore, and preserves the prior pause.

The actual current room has a cyan outline, shown only for the live level.
Keyboard destination selection is white only after arrow-key navigation; opening
the map, changing levels or moving the mouse clears that pending marker. It does
not move the current-room marker to a different room/level. Hovering brightens only the room
under the pointer and shows a gold outline and transient room label. Blank
map space is not selectable; leaving the map clears the hover. Clicking a room
uses the existing safe F3 entry path and restores the prior pause state.

With map focus, arrows select spatially rather than by numeric room order;
Enter activates the destination. Tab moves only between visible controls.
Escape closes the level dropdown first, then returns from the map to tools,
then closes F3 on a new press. Held Enter cannot skip Open map and teleport;
held Escape cannot dismiss both pages. Playback also returns to tools on Back
or Escape, retaining the selected part; a further Escape closes F3.

The native menu buffer retains the pixel-art font. At presentation time,
the map is composed directly at the actual fitted window resolution from
the original 510x360 room images, rather than enlarging the tiny native menu
thumbnail. Room hit regions stay in native viewport coordinates. Hover
outlines/tooltips scale with the map. The overview is uniformly fitted inside
the taller workspace, preserving room aspect ratios and inverse pointer
mapping. The level popup and toolbar tooltips are restored above the detailed
map without changing the rest of the presented frame.

Map creation waits for Open map, not F3 itself, with no startup precomputation
or bundled image-file dependency. A disposable local archive in
`assets/.developer-cache/level-N.zip` retains the lossless RGB room sources and
overview between launches. A content fingerprint of imported resources/programs
and Python rendering code rejects stale artwork after updates. Invalid or
missing archives rebuild normally; write failures do not prevent use of the map.
Only the first build after import or a relevant update needs full rendering.
Native room frames and the compact overview are reused. A bounded two-size
memory cache retains both the native menu image and the HD
map, avoiding eviction/reconstruction as the two presentations alternate.

Pointer changes redraw the developer overlay over the frozen clean game image,
without rendering scenery, actors or animation layers again. At unchanged
display size the existing Tk photo is retained; only its changed pixel region
is uploaded, including removal of the previous highlight/label. Resize rebuilds
the presentation, while closing F3 releases the retained display frame. There
is no loss of map resolution or change to gameplay timing. A local profiled
32-room sweep at a fitted 1912x1440 display dropped from approximately 133 ms to
22 ms per changed hover; this is a host measurement, not a cross-PC guarantee.
F8 still captures the clean game, not the developer overlay.

## Export And Verification

`python -m tools.render_cavern_map` regenerates `rendered/level3-clean-map.png`
at 5610x2160, without labels or actors. `--enemies` writes the separate
`rendered/level3-map-with-enemies.png`, preserving the clean version.
`--output` and `--labels` remain available.

`tests/test_development_map.py` covers topology, all selectable rooms, spatial
keys, nested page/back/Escape navigation, key-repeat protection, uniform fit,
hover/click/gaps, popup/tooltip priority, lazy caching, RNG and live-world
isolation, original bone poses, actor-only pixel differences, native-source
high-resolution presentation, alternating native/HD cache reuse, tabless
tools/playback navigation and actual safe F3 teleport. Real Tk photo tests at
four viewport sizes compare partial hover updates byte-for-byte against full
redraws, including tooltips, blank-space/leave cleanup and unchanged live state.
Existing menu, cavern map/export, screenshot and attract tests remain part of
verification.
