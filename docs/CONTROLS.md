# Controls, Remapping And Controllers

This is a port-only feature. The Macintosh original reads a fixed keyboard
(arrows, Shift, Ctrl) and has no controller support or key remapping.

## Where

F1 > **Controls** (also Alt+K, from play or from any menu page). The page has
two tabs:

- **Keyboard**: a drawn keyboard with each action's keys lit in its colour,
  and a legend. Keys that are not on the drawing (some national keys) are
  named in the legend.
- **Controller**: a drawn controller in the connected pad's style (Xbox,
  PlayStation or Nintendo layout and symbols) with labelled callouts, the
  connected controller's name and a **Use controller** switch.

Both drawings are original pixel art made by code (`pop2/controls_art.py`)
at the native 510x384 size: each shape is lit from the upper left and
reduced to a few hard shades, in colours taken from the game's palace. The
controller has the proportions and layout of an Xbox Series controller: an
ivory shell with mauve shadows and dark brown outlines, frieze-blue sticks,
a crimson D-pad like the palace tapestries, gem face buttons and a guide
button drawn as a lit ring round an X. The PlayStation and Nintendo styles
reuse that body with their own buttons for now. The keyboard is a full
1990s office keyboard (keypad, lock lights, the old four-colour Windows
flag on the Windows keys) with light letter keys and darker mauve
modifiers, legends at the top left of each key. Jump, Crouch, Sword and
Time left take the colours of their default buttons (A, B, X, Y). Nothing
is traced from another game. The callouts sit on one 18-pixel grid on both
sides; each line leaves its label level and bends at most once. Tests
check that no line crosses another or passes over another button, with
every button bound.

**Change keys...** / **Change buttons...** opens a list with two slots per
action. Enter (or A) waits for the next key or button, Delete (or X) clears a
slot, Esc (or B) goes back, **Defaults** restores the original layout. A key
already used elsewhere swaps places with the slot's previous key, so one key
never does two things. Page Up/Page Down (LB/RB) switch tabs. The hints follow
whichever device was used last.

Choices are kept in `preferences.json` beside the saves
(`keyboard_bindings`, `controller_bindings`, `controller_enabled`). A damaged
or hand-edited table is repaired on load: unknown actions, reserved keys and
duplicates are dropped.

## Actions

| Action | Default key | Default button | Original key the game receives |
| --- | --- | --- | --- |
| Left, Right | arrows | D-pad, left stick | Left, Right |
| Up / Jump | Up | A, D-pad/stick up | Up |
| Down / Crouch | Down | B, D-pad/stick down | Down |
| Grab / Careful step | Shift | RB, RT | Shift |
| Sword / Strike | Ctrl | X | Ctrl |
| Show time left | Space | Y | Space |
| Pause | Esc (fixed) | View | Escape |
| Game menu | F1 (fixed) | Menu (fixed) | F1 |

Esc and F1 (and the controller's Menu button) always keep their meaning, so a
menu can never become unreachable; each still has a free second slot.
Function keys, Alt, Windows/Menu keys, lock keys and dead keys cannot be
chosen. On a controller the D-pad and left stick always move and the guide
(Xbox/PS) button stays with the system. Grab and Sword are different native
modifiers: with both held, Shift wins (4:3f08), so one key cannot both grab
and strike.

## How it reaches the game

`pop2/input_routing.py` translates a chosen key into the original key
*before* any existing handler sees it (`dev_key_press` is now the routing
wrapper; the previous body is `key_press_unrouted`). The pause, resume, retry,
Alt+R restore and menu-consumption rules therefore stay those of the
keyboard, and `window_keys_down` still holds original key names. Nothing in
`mac_input.py` or the GenCtrl banks changed.

- A router counts which physical sources hold each original key, so W and K
  for Up, or the D-pad and the stick, release Up only together.
- A release always follows the meaning its press had, even if a menu opened
  in between.
- During play, an original key the player moved elsewhere (say, Left after
  choosing A) is swallowed. Menus always keep arrows/Enter/Esc/Tab and only
  take the chosen Pause and Game menu keys. Text fields (save names, folder
  paths), Developer Tools and Alt shortcuts are never translated.
- While a slot listens, the chosen key stays inert until released, so its
  autorepeat cannot act on the page.

## Controllers

`pop2/gamepad.py` uses the SDL2 library pygame already ships, through
ctypes: a daemon thread initialises SDL's game-controller layer and polls it
every 8 ms (no SDL window and no SDL event loop; joystick events are
disabled so nothing queues). Hints keep the drivers polled: background input
allowed, RAWINPUT and Windows.Gaming.Input off (so Xbox pads use XInput),
positional Nintendo buttons. SDL normalises Xbox, PlayStation, Switch Pro and
many other pads to one layout named by position.

The Tk thread reads the newest snapshot every 16 ms and turns edges into the
same original keys:

- Play: D-pad/stick are arrows, bound buttons their actions. Modifiers are
  delivered before directions pressed in the same poll, and released after
  them. The stick has hysteresis; up needs a firmer push (0.65) than sideways
  (0.5) so running does not jump by accident.
- Menus, copy protection and text fields: D-pad/stick navigate with repeat
  (0.35 s, then every 0.08 s), A is Enter, B is Esc, LB/RB are Page Up/Down,
  X clears a slot on the Controls page.
- Intro/demo: face buttons skip like Space. Cutscene replay: A pauses, B stops.
- Input is ignored while the window is not in the foreground, and anything
  held across a focus change waits for a fresh press.
- Unplugging the last controller after it was used pauses play, like focus
  loss, and releases its holds. Connecting or disconnecting shows a short
  notice in the status strip.

Copy protection also accepts arrows and Enter (or the controller) to pick a
symbol, besides the original mouse.

Tests set `POP2_NO_GAMEPAD=1` (tests/__init__.py) so no test reads a real
controller. `python -m tools.gamepad_probe` lists connected controllers and
prints every input change with its meaning, without the game.

## Verified and not verified

Verified: unit and scene tests in `tests/test_controls.py`, including a
scripted run where chosen letters and a simulated controller produce exactly
the same per-tick trace as the arrows (movement, turn, step, crouch, pause
with a held key, time display). SDL initialises and polls on Windows in
this environment with no controller attached.

Not yet verified on hardware: any real controller. Xbox-compatible pads use
XInput through SDL; PlayStation and Nintendo pads rely on SDL's HIDAPI
drivers and its mapping database. Their names and symbols come from SDL's
reported type and need checking by someone who owns one.
