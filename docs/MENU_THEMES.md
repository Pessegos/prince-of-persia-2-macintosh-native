# Menu Themes

The port's menus (F1, its dialogs, Controls, saves, screenshots, the Cutscene
Viewer and the developer tools) are an addition of the port, not original behaviour. They
take their colours, and on some pages their frame, from the level being
played. The code is in `pop2/menu_theme.py`.

## How pages get their colours

Every page writes the neutral grey-and-gold colour and passes it through
`c(...)`:

```python
draw.rectangle(rect, fill=c('#303030'), outline=c('#f4d873'))
```

A theme is a table of roles (`accent`, `text`, `row`, `selected`, ...).
`NEUTRAL_ROLES` gives the neutral colour of each role, and a theme lists only
the roles it changes. The neutral theme changes none, so its pages are
pixel-identical to the menus before themes existed. A new menu colour needs a
role in `NEUTRAL_ROLES` before a theme can change it; a colour without a role
is drawn as written.

The scene selects the theme before drawing a menu
(`menu_theme.use(menu_theme.theme_for(game))`). Menus opened over a cutscene
take the theme of the level it follows (the ride to the temple after level 9
has the ruins' look); they were neutral at first, which the user noticed as
an oversight.

## Themes

| Theme | Levels | Look |
| --- | --- | --- |
| neutral | the rooms of the last level that have no theme yet | grey panel, gold accent |
| palace | 1 | dark blue panel, the first room's cream cornice with its pearls and the wall's dotted turquoise and orange trim, a soft mauve-grey outline, red selection |
| desert | 2 | dark sea panel, frame of sand with a wet inner edge, sun-yellow accent |
| caverns | 3-5 | dark brown panel, rough rock frame, bone text, flame accent, darker room behind |
| ruins | 6-9 | indigo panel, violet band of square sockets falling apart, the serpent sign as a watermark, sand-gold accent |
| temple | 10-13 | dark red panel, two red columns under a carved frieze, flame accent |
| chess | 14, native rooms 4-5 | violet-black panel, a row of violet and pearl chessboard squares, pearl text, the bronze pieces' gold accent |
| spider | 14, native rooms 3 and 9 | near-black red-brown panel, a tarantula's coat of hair round it, the spider's fur faintly over the whole panel, cream text, tawny accent, wine selection |

The last level (kind 6) changes look from room to room, so its menus follow
the Prince's room, not the level (`_FINAL_ROOM_THEMES`). The tower over the
city (native rooms 1-2) takes the palace theme: the Prince is back at the
palace. The princess's room (native room 11), seen only in the ending, is the
palace too. The chessboard (native rooms 4-5) has the chess theme and the
spider's rooms (native rooms 3 and 9) the spider theme. The crystals (6) and
the Escher maze (7, 8, 10) keep neutral until their own themes are drawn.

## Frames

`menu_theme.panel(image, rect)` draws a panel's fill and frame. The neutral
theme draws the plain outlined rectangle. A framed theme grows the frame
beyond the panel by its `grow` margins, inside the playfield above the health
strip. A page whose content reaches the panel's sides (Controls, and the F1
menu with its scroll arrows) passes `clear_sides=True`, and the frame then
stands wholly outside the panel there.

The pages drawn at the game's resolution start from
`menu_theme.ground(viewport, rect, clear_sides)`: the picture under the
theme's veil (`dim`) with the panel laid over it. Over the picture the scene
holds (`menu_theme.hold`, the game's picture while it is shown under a menu)
each ground is drawn once and kept, so an option the pointer reaches does not
darken the whole picture and lay the frame again. A held picture must not be
drawn into.

Each environment has a frame of its own; a frame drawn for one is not reused
for another. The theme names its kind in `frame`:

| Kind | Theme | What is drawn |
| --- | --- | --- |
| `bands` | palace | a straight moulding; the theme lists its rows from the outside inwards. A row of several colours is speckled with them; a `_Weave` row is laid in its order along each side, over and over: the palace's pearls, stone joints and dotted trim are one 51-pixel stone of the first room's wall, as the wall repeats it |
| `sand` | desert | grainy sand with rounded corners, wind marks that are all different (dunes, hollows, streaks, pebbles), damp where it meets the panel, and one small starfish |
| `rock` | caverns | speckled stone with a worn edge; the theme gives its `grain` and the extra `shades` for lit and shadowed edges |
| `studs` | ruins | the palace wall's band of sunk square sockets with a carved ring at each corner; straight edges, damaged in a different way at each place (a piece broken out, a flake, a nick, a crack, a bite out of the inner edge, a crumbled socket, one lost corner), never deeper than five of its nine rows |
| `columns` | temple | two columns with leaf capitals and plinths between the same carved band above and below: a frieze of rosettes between leaves, laid out in whole motifs for any width, with a rosette block at each corner |
| `chess` | chess | one row of the board's squares, violet and pearl in turn, lit on the upper edge and shaded on the lower and right edges like the room's tiles; an odd number of near-square runs on each side keeps a violet square at every corner, and the board's dark front face runs under the lower row |
| `spider` | spider | a tarantula's coat: a velvet band of dark browns carrying the same lobes as the panel's fur, smaller (deep crevices, shaded sides, lit tops with a glint, a few pores); short fuzz in two layers standing out of it; long bristles in tufts that thicken and thin along each side, each at its own angle, now and then two or three from one root splaying apart, a third of them catching the light; and, only where the coat is thin, a few long guard hairs on their own. Nothing is combed one way. The coat, the band's lobes and the guard hairs have random sequences of their own, so changing one leaves the others as they are |

`_THICKNESS` gives each kind's thickness at the sides, top and bottom. The
temple's bands and columns are thicker than the others, so its frame reaches a
few pixels further into a panel's top and bottom margins.

The pages were laid out to clear the first five frames (palace to temple), so a
later frame's band reaches no deeper into any panel than theirs do
(`test_new_frames_take_no_more_of_a_panel_than_the_first_ones`). The spider's
frame is 18 pixels thick, but its outer 11 are only hairs over the room: it
grows further out (`grow` 7, 11, 13) so that its velvet band lies where the
temple's band lies. The chess frame's foot is one row lower than the others'
(`grow` bottom 8) for its board's front face. A frame that would cross the
area it may cover is drawn smaller; the spider's loose hairs (`_LOOSE`) are cut
off at that edge instead, so that its band keeps its place on the Controls
page, which fills the playfield.

Frames are drawn by code from a few hard shades taken from the level's
palette. They contain none of the game's pictures, so they need no imported
resources and the tests run without assets. The rock frame has no outline and
no black: its worn edge lets the room show through, and only its shadow on the
panel is black. A frame is drawn once for each size and kept; the rock frame is painted
with whole arrays, pixel for pixel as its first painter drew it. The painters
visit only the band of pixels near the edge; visiting the whole panel made a
menu hesitate the first time it opened. For the same reason the spider's lobes
(`_spider_shade`) are looked for only near each lobe's centre, and the frame
skips the lobes that cannot reach its band. The result is the same, pixel for
pixel, as comparing every lobe with every pixel. The spider is still the
costliest theme the first time a page opens, because its band and its fur are
both computed: about a tenth of a second for the F1 menu (the other themes
take one or two hundredths), once per page size.

Saves and screenshots are drawn at the window's resolution. They call
`menu_theme.panel_scaled(image, rect, point)`, which draws the same frame at
the game's resolution and enlarges it without smoothing; it returns False for
a theme without a frame and the page then draws its own rectangle. These pages
cover the health strip, so their frame may reach below it. Their smaller
dialogs (rename, delete, choose folder) are framed the same way, and carry no
sign: the page's sign is drawn before the page is darkened under the dialog.
The Cutscene Viewer fills the window and is themed in the same way: its
neutral colours have roles of their own (`card`, `card_selected`,
`card_hover`, `viewer_edge`, `track`, `track_thumb`, `off`), and a theme that
does not name them uses its row, selection and edge colours instead
(`_ROLE_FALLBACK`). Under a framed theme its panel starts further from the
window's edges and ends lower, so that the frame stands outside it and the
side arrows stay clear. Its covers are the chapters' own pictures and are not
recoloured.

## Wide windows

The game's picture is 4:3, and in a wider window the menus are as narrow as it
is. The saves page uses the extra width instead (`SaveBrowser.wide_layout`):
from about 16:9 its panel is wider, the preview is larger and has a save
picture's own shape, and the save's name and details stand beside the preview
instead of under it. The page reaches 8 units further out on each side than
the shared wide layout (`SaveBrowser.WIDE_PAD`): in 16:9 its panel then has
exactly the screenshots page's sides, and the preview's foot is level with
the list's fifth row and the last detail line ends there too. The
buttons keep their sizes; the page's two actions move to its right edge. On
every page Load game stands alone at the right edge, as wide as New save. A window wider than 16:9 gives the list a little more
room, so that long names fit, and then shows the page centred: stretching it
further only made the list and the buttons oversized. Narrower windows, 16:10 among them, keep the classic
page. The page is then drawn over the whole window, with the
game's picture centred behind it, and one unit is as wide as it is tall. Its
rectangles (`PANEL`, `LIST`, `PREVIEW`, ...) are properties that follow the
layout of the last picture drawn, and the pointer is mapped to the same units.
A picture saved with Shift+F8 "with menus" still shows the classic page.

The screenshots page follows the same rule
(`menu_theme.wide_layout`: from about 16:9, 172 units wider, centred beyond
16:9). The wide screenshots page is the classic one made larger: four columns
of thumbnails instead of two, a larger picture with the file's name, size and
the lava delete button under it as before, and a panel 28 units taller.
Refresh, "With menus", Open folder and Capture PNG move to the right edge. The
folder and delete dialogs are laid out as on the classic page and centred on
the wide one (`dialog_shift`). The page's hint, "Take Screenshots with F8",
keeps to the page's right edge and goes under the taller panel
(`draw_screenshot_notice`'s `inset`). On the classic page it stands 3 units
from the health strip, clear of the themed frame.

The controls page keeps the classic page in every window, fitted like the
game's picture: its keyboard and controller cannot be enlarged, and a wider
panel around the same pieces gained nothing.

## The lava delete button

The screenshots page deletes a picture dropped on a small pool of the
caverns' lava. The pool sits in a rim of rock made from the page's own
background lit by the lava (`rim_shades`): the rim's top takes some of the
lava's orange and its front face falls away a little darker than the page;
four hard shades and a lumpy edge, no outline. A dropped picture falls until
its foot meets the middle of the pool, then sinks into it, in front of the far
half of the lava and under the near half, while it burns from the foot up
(`burn`, one second in all): a ragged bright edge just above the lava, an
orange row, char above, a few sparks. It moves in the game's steps, twelve a
second, and nothing is blended or faded.

## The sign on the page

A theme may leave a sign on its pages like a watermark (`mark`, the colour the
sign leans towards). The ruins have the invaders' serpent, large and darker
than the menu, as it is daubed on the palace walls. Its shape is a list of
points with the line's thickness at each (`_SERPENT`), joined by a smooth
curve and drawn a little unevenly, like a brush.

The spider's sign is its fur, not its shape, over the whole panel
(`_spider_pattern`): rounded lobes packed together, a little stretched and
bent, lit from the upper left. The shadowed side of each lobe and the crevice
under it are a scatter of specks, thick in the crevice and thinning out across
the lobe, as the room's art dithers them, with a few pores on the lit parts.
It is fainter than the serpent (`_MARK_STRENGTH`: 0.3 of the way to the mark
colour instead of 0.4).

A page calls `menu_theme.watermark(image, rect)` after drawing everything
else. Only pixels that still have one of the page's background colours
(panel, row, row_dark, selected, hover) change, each to a darker shade, so text,
outlines and pictures are untouched and drawing the sign twice changes
nothing. Three things a page must take care of:

- A page that keeps a copy of itself and repaints only part of it (the list
  on the saves and screenshots pages) must call `watermark` again after that
  repaint. It may pass that part as `within`, in the image's own pixels: the
  sign's shades are no background colours, so the rest of a page that has
  the sign would not change. The screenshots page does so for its list, the
  delete button's label and the controls the focus lights, which it draws
  again over a page kept whatever has the focus; the spider's fur over its
  whole panel took most of a frame's time at 3440x1440.
- A page with pictures passes their rectangles in `avoid`, in the image's own
  pixels. A slot still waiting for its picture has a background colour, and
  the sign would otherwise show there and vanish when the picture arrives.
- Pages drawn at the window's resolution pass `point`; the sign is drawn at
  the game's resolution and enlarged without smoothing.

These pages are redrawn on every key, so `watermark` looks only at the sign's
own pixels, whose places it keeps for each size (`_spots`). The spider's fur
covers the whole panel and costs about 8 ms a redraw on a 1080p saves page
(the serpent about 4). Each window size has its own enlarged sign, so the
caches keep only the latest two dozen.

The level map, the playback page and the Cutscene Viewer carry no sign: the
viewer's shelf of covers moves over the page and would cover it.

## The level map

The map picture is built on neutral grey and kept on disk, so it cannot hold a
theme's colour. Under a theme, `DevelopmentMenu.map_layer` copies the rooms
onto the theme's backdrop colour instead.

## Pixel-perfect text

Menu text keeps the font's own pixels: every font pixel covers the same
whole number of screen pixels, so no letter has columns of different widths.

- Pages drawn at the game's resolution (512 x 384) never squeeze a label to
  fit with `max_width`: a NEAREST squeeze drops a column in every few (two of
  the three dots in "Change buttons..." lost one). Make the control wide
  enough or the text shorter instead. `ControlsPageFontTests` guards the
  Controls page with the real font.
- Pages drawn at the window's resolution (saved games, screenshots, the
  Cutscene Viewer) pass each label's scale through `bitmap_labels.crisp`,
  which snaps it to a whole number of window pixels when one is near and the
  text still fits (small text: 2.1x -> 2x in a 3x window).
  `WindowPageTextTests` checks the three pages in a 3x window.
- Text shrunk to fit a long value (a folder path) is the only exception.
- Artwork follows the same rule: drawn pixel by pixel and enlarged by whole
  numbers, like the About page's peach.

## Forcing a theme

`POP2_MENU_THEME=neutral` turns the level themes off; a theme's name
(`palace`, `desert`, `caverns`, `ruins`, `temple`, `chess`, `spider`) uses it on every level.
The test package sets it to `neutral` so that layout tests check the same
look whatever level their scene loads;
`tests/test_menu_theme.py` covers the themes themselves.
