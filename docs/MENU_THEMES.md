# Menu Themes

The port's menus (F1, its dialogs, Controls, saves, screenshots and the
developer tools) are an addition of the port, not original behaviour. They
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
stay neutral.

## Themes

| Theme | Levels | Look |
| --- | --- | --- |
| neutral | the last level and cutscenes | grey panel, gold accent |
| palace | 1 | dark blue panel, cream cornice frame with turquoise and orange trim, red selection |
| desert | 2 | dark sea panel, sandstone frame, sun-yellow accent |
| caverns | 3-5 | dark brown panel, rough rock frame, bone text, flame accent, darker room behind |
| ruins | 6-9 | indigo panel, violet stone frame, sand-gold accent |
| temple | 10-13 | dark red panel, red moulding with a candle-gold line, flame accent |

The last level (kind 6) has no theme and uses neutral.

## Frames

`menu_theme.panel(image, rect)` draws a panel's fill and frame. The neutral
theme draws the plain outlined rectangle. A framed theme grows the frame
beyond the panel by its `grow` margins, inside the playfield above the health
strip. A page whose content reaches the panel's sides (Controls, and the F1
menu with its scroll arrows) passes `clear_sides=True`, and the frame then
stands wholly outside the panel there.

There are two kinds of frame, both described by data on the theme: `rock` (a
strip of speckled stone with a worn edge; the theme gives its `grain` and the
extra `shades` for lit and shadowed edges) and `bands` (a straight moulding;
the theme lists its rows from the outside inwards).

Frames are drawn by code from a few hard shades taken from the level's
palette. They contain none of the game's pictures, so they need no imported
resources and the tests run without assets. The rock frame has no outline and
no black: its worn edge lets the room show through, and only its shadow on the
panel is black.

Saves and screenshots are drawn at the window's resolution. They call
`menu_theme.panel_scaled(image, rect, point)`, which draws the same frame at
the game's resolution and enlarges it without smoothing; it returns False for
a theme without a frame and the page then draws its own rectangle. These pages
cover the health strip, so their frame may reach below it. Their smaller
dialogs (rename, delete, choose folder) keep a plain edge, and the Cutscene
Viewer has its own look and is not themed.

## Forcing a theme

`POP2_MENU_THEME=neutral` turns the level themes off; a theme's name
(`palace`, `desert`, `caverns`, `ruins`, `temple`) uses it on every level.
The test package sets it to `neutral` so that layout tests check the same
look whatever level their scene loads;
`tests/test_menu_theme.py` covers the themes themselves.
