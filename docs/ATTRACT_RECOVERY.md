# Attract Cycle

The opening now continues into the level-one demonstration, the original four
credits pages and another opening. Space skips the opening; a gameplay key
leaves the demo or credits and starts a clean game. Pause, window focus loss,
fullscreen and the command menu remain available. Story scenes and credits
show `Cutscene Paused`; the demo retains `Game Paused`. Dev Mode is disabled
throughout the attract cycle, including its command-menu entry. F5 no longer
restarts the opening; use the New Game or Restart Level commands.

## Recorded Controls

Prince's `RECG` resources contain timestamped changes to six controller slots:
five opponents and the Prince. They record facing-relative control latches,
not host key events. Each direction has fresh, inactive and consumed states;
the modifier also distinguishes Shift from Ctrl.

CODE 5:60c0-638a reads these streams. Recording 250 is level 1, frames 0-521.
Recordings 251 and 252 describe levels 4 and 8; those levels are not playable
yet, so this port repeats the level-one cycle. The level-four resource has an
unused tail; only its declared payload is read.

`tools/extract_attract.py` resolves recording 250 through the original movement,
collision, animation and combat routines during import. The jump table comes
from CODE 0, initialized globals from DATA/ZERO, and character/tile resources
from the selected image. The extraction has an instruction budget and checks
that the original recording finishes with the Prince dead in room 10 (screen 5).
No external disassembly directory is required.

The resulting `assets/attract.json` stores actor states, original five/six-VBL
frame intervals and sound requests. Runtime playback uses the existing native
scene renderer and audio engine; it does not run Macintosh code or the live AI.
Ambient music uses the ordinary port audio selection. Playback cannot alter
the real encounter, checkpoint or peaceful setting. The generated trace, like
all extracted game data, stays outside Git.

## Credits

CODE 2:2b70 supplies the four page ranges from A5 -55ba/-55b2. The category
coordinators at 2:2d20/2d80 determine placement; TextInRect's bitmap metrics and
alignment are reproduced when exporting the text runs. TEXT resources retain
the original strings and special glyphs, rendered with NFNT 24878. SHAP 8000/8001
and CTBL 8000 supply the frame and colors. SHAP 8000 contains unrelated trailing
bytes after its final compressed row; they are not image data.

The coordinator provides the 465-tick page hold, 90-tick dissolves and 0x40001
fade flags. Credits music is MIDI 10019 from `MIDISnd.dat`, prepared with the
same original instruments as the game. Dissolves use the recovered two-word
copy pattern with a deterministic fallback permutation; pixel order need not
match a particular emulator run.

## AI Evidence

These recordings are a useful reference for inputs, positions, attack/block
timing, damage and falls. They do not reveal a complete guard decision policy:
playback overwrites the controllers with recorded commands after automatic
control. A matching demo therefore does not establish that live guard AI has
full original-game parity. Keep the recording and imported trace as reference
data when recovering additional AI branches.
