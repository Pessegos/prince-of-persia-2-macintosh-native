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
| neutral | every level without its own theme, and cutscenes | grey panel, gold accent |
| palace | 1 | dark blue panel, cream cornice frame with turquoise and orange trim, red selection |
| caverns | 3-5 | dark brown panel, rough rock frame, bone text, flame accent, darker room behind |

The desert (level 2), ruins and temple have no theme yet and use neutral.

## Frames

`menu_theme.panel(image, rect)` draws a panel's fill and frame. The neutral
theme draws the plain outlined rectangle. A framed theme grows the frame
beyond the panel by its `grow` margins, inside the playfield above the health
strip. A page whose content reaches the panel's sides (Controls) passes
`clear_sides=True`, and the frame then stands wholly outside the panel there.

Frames are drawn by code from a few hard shades taken from the level's
palette. They contain none of the game's pictures, so they need no imported
resources and the tests run without assets. The rock frame has no outline and
no black: its worn edge lets the room show through, and only its shadow on the
panel is black.

Only pages drawn at the native 512x384 resolution have frames so far: the F1
menu and its dialogs, Controls and the developer tools panel. Saves and
screenshots are drawn at the window's resolution; they take the theme's
colours but keep a plain edge.

## Forcing a theme

`POP2_MENU_THEME=neutral` turns the level themes off; `palace` or `caverns`
uses that theme on every level. The test package sets it to `neutral` so that
layout tests check the same look whatever level their scene loads;
`tests/test_menu_theme.py` covers the themes themselves.
