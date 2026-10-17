# F3 Level Map

F3 opens a compact Developer Tools panel with Game, Playback and Display tabs.
Game offers Open map, Peaceful mode and Resume; no level selectors or room
dropdowns occupy this entry panel. Open map enters a separate full-playfield
workspace. This is a host development tool, not a recovered Macintosh feature.

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

The map workspace removes the tools heading, tabs and floating panel frame.
Its top bar contains a back arrow, a single level selector, and previous/next
level arrows with pointer tooltips. Back returns to the compact tools without
teleporting or resuming; the selected destination is retained. Peaceful mode,
Go and Resume remain available in the map's lower command strip.

The selected destination has a cyan outline. Hovering brightens only the room
under the pointer and shows a gold outline and transient room label. Blank
map space is not selectable; leaving the map clears the hover. Clicking a room
uses the existing safe F3 entry path and restores the prior pause state.

With map focus, arrows select spatially rather than by numeric room order;
Enter activates the destination. Tab moves only between visible controls.
Escape closes the level dropdown first, then returns from the map to tools,
then closes F3 on a new press. Held Enter cannot skip Open map and teleport;
held Escape cannot dismiss both pages. Playback controls are unchanged.

The native menu buffer retains the pixel-art font. At presentation time,
the map is composed directly at the actual fitted window resolution from
the original 510x360 room images, rather than enlarging the tiny native menu
thumbnail. Room hit regions stay in native viewport coordinates. Hover
outlines/tooltips scale with the map. The overview is uniformly fitted inside
the taller workspace, preserving room aspect ratios and inverse pointer
mapping. The level popup and toolbar tooltips are restored above the detailed
map without changing the rest of the presented frame.

Map creation waits for Open map, not F3 itself, with no startup precomputation
or image-file dependency. Native room frames and the compact overview are reused; only the
most recent display-sized map image is cached, keeping resize memory bounded.
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
high-resolution presentation, bounded resize caching, and actual safe F3
teleport. Existing menu, cavern map/export, screenshot and attract tests remain
part of verification.
